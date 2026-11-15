"""Verify signed host-inspector evidence and exact proxy-only firewall policy.

This module verifies an offline evidence envelope. It does not execute host
commands, inspect kernel state, configure nftables, resolve DNS, open sockets,
or launch a worker. A separate trusted host-side collector must sign its
observations with an Ed25519 key whose public key is provisioned out-of-band.
"""
from __future__ import annotations

from dataclasses import dataclass
import base64
import binascii
import hashlib
import ipaddress
import json
import re
import time
from collections.abc import Mapping, Sequence
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from core.browser_runtime import (
    RuntimeSecurityAttestation,
    RuntimeAttestationError,
    WorkerLaunchSpec,
    verify_prestart_attestation,
)


class InspectorEvidenceError(ValueError):
    """Raised when signed inspector evidence is invalid or unsafe."""


_ENVELOPE_FIELDS = frozenset({"schema_version", "key_id", "payload", "signature"})
_PAYLOAD_FIELDS = frozenset({"challenge", "runtime_attestation", "firewall"})
_FIREWALL_FIELDS = frozenset({
    "schema_version", "runtime_id", "worker_id", "network_namespace_inode",
    "interface", "backend", "observed_at", "default_egress_policy",
    "allowed_egress", "direct_dns_blocked", "proxy_side_dns_only",
    "ruleset_digest",
})
_RULE_FIELDS = frozenset({"protocol", "destination_ip", "destination_port"})
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
_INTERFACE = re.compile(r"^[A-Za-z0-9_.:-]{1,15}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class VerifiedFirewallEvidence:
    """Normalized firewall facts from a signature-verified host observation."""

    runtime_id: str
    worker_id: str
    network_namespace_inode: int
    interface: str
    backend: str
    observed_at: int
    ruleset_digest: str
    allowed_proxy_addresses: tuple[str, ...]
    proxy_port: int


@dataclass(frozen=True)
class VerifiedInspectorEvidence:
    """Combined P05 runtime attestation and signed host firewall evidence."""

    key_id: str
    challenge: str
    runtime: RuntimeSecurityAttestation
    firewall: VerifiedFirewallEvidence


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise InspectorEvidenceError("Evidence payload is not canonical JSON data.") from exc


def _require_identifier(value: object, field: str) -> str:
    if type(value) is not str or not _IDENTIFIER.fullmatch(value):
        raise InspectorEvidenceError(f"Invalid {field}.")
    return value


def _proxy_config(spec: WorkerLaunchSpec) -> tuple[str, int]:
    parsed = urlsplit(spec.egress_proxy)
    try:
        port = parsed.port
    except ValueError as exc:
        raise InspectorEvidenceError("Launch specification proxy endpoint is malformed.") from exc
    if parsed.scheme != "http" or not parsed.hostname or port is None:
        raise InspectorEvidenceError("Launch specification proxy endpoint is incomplete.")
    return parsed.hostname, port


def _normalize_proxy_addresses(addresses: Sequence[str]) -> tuple[str, ...]:
    if (not isinstance(addresses, Sequence)
            or isinstance(addresses, (str, bytes))
            or not 1 <= len(addresses) <= 8):
        raise InspectorEvidenceError("One to eight explicitly configured proxy IPs are required.")
    normalized: list[str] = []
    for value in addresses:
        if type(value) is not str:
            raise InspectorEvidenceError("Proxy address must be an IP string.")
        try:
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise InspectorEvidenceError("Configured proxy address is malformed.") from exc
        if (address.is_unspecified or address.is_loopback or address.is_link_local
                or address.is_multicast or address.is_reserved):
            raise InspectorEvidenceError("Proxy address is not a usable unicast endpoint.")
        normalized.append(address.compressed.lower())
    if len(set(normalized)) != len(normalized):
        raise InspectorEvidenceError("Duplicate proxy addresses are not permitted.")
    return tuple(sorted(normalized))


def _verify_firewall(
    raw: object,
    *,
    runtime_id: str,
    worker_id: str,
    proxy_addresses: tuple[str, ...],
    proxy_port: int,
    now: int,
    max_age_seconds: int,
) -> VerifiedFirewallEvidence:
    if not isinstance(raw, dict) or set(raw) != _FIREWALL_FIELDS:
        raise InspectorEvidenceError("Firewall evidence has missing or unknown fields.")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise InspectorEvidenceError("Unsupported firewall evidence schema.")
    observed_runtime = _require_identifier(raw["runtime_id"], "firewall runtime_id")
    observed_worker = _require_identifier(raw["worker_id"], "firewall worker_id")
    if observed_runtime != runtime_id or observed_worker != worker_id:
        raise InspectorEvidenceError("Firewall evidence is not bound to the attested runtime and worker.")

    inode = raw["network_namespace_inode"]
    if type(inode) is not int or inode <= 0:
        raise InspectorEvidenceError("A positive network namespace inode is required.")
    interface = raw["interface"]
    if type(interface) is not str or not _INTERFACE.fullmatch(interface):
        raise InspectorEvidenceError("Worker network interface name is malformed.")
    if raw["backend"] != "nftables":
        raise InspectorEvidenceError("Only the reviewed nftables evidence format is accepted.")
    if raw["default_egress_policy"] != "drop":
        raise InspectorEvidenceError("Host firewall default egress policy must be DROP.")
    if type(raw["direct_dns_blocked"]) is not bool or raw["direct_dns_blocked"] is not True:
        raise InspectorEvidenceError("Direct DNS egress must be blocked.")
    if type(raw["proxy_side_dns_only"]) is not bool or raw["proxy_side_dns_only"] is not True:
        raise InspectorEvidenceError("DNS resolution must occur only on the proxy side.")

    timestamp = raw["observed_at"]
    if type(timestamp) is not int or timestamp > now + 5 or now - timestamp > max_age_seconds:
        raise InspectorEvidenceError("Firewall evidence is stale or from the future.")
    ruleset_digest = raw["ruleset_digest"]
    if type(ruleset_digest) is not str or not _HEX64.fullmatch(ruleset_digest):
        raise InspectorEvidenceError("Firewall ruleset digest must be a lowercase SHA-256 digest.")

    rules = raw["allowed_egress"]
    if not isinstance(rules, list) or not rules:
        raise InspectorEvidenceError("An explicit, non-empty firewall egress allowlist is required.")
    observed: list[tuple[str, str, int]] = []
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) != _RULE_FIELDS:
            raise InspectorEvidenceError("Firewall rule has missing or unknown fields.")
        if rule["protocol"] != "tcp":
            raise InspectorEvidenceError("Only TCP egress to the proxy is permitted.")
        try:
            address = ipaddress.ip_address(rule["destination_ip"])
        except (ValueError, TypeError) as exc:
            raise InspectorEvidenceError("Firewall destination must be an exact IP address.") from exc
        port = rule["destination_port"]
        if type(port) is not int or port != proxy_port:
            raise InspectorEvidenceError("Firewall destination port differs from the approved proxy port.")
        observed.append((address.compressed.lower(), "tcp", port))

    expected = [(address, "tcp", proxy_port) for address in proxy_addresses]
    if sorted(observed) != sorted(expected) or len(observed) != len(expected):
        raise InspectorEvidenceError(
            "Firewall must allow exactly the configured proxy IP addresses and port; no other egress."
        )

    return VerifiedFirewallEvidence(
        runtime_id=observed_runtime,
        worker_id=observed_worker,
        network_namespace_inode=inode,
        interface=interface,
        backend="nftables",
        observed_at=timestamp,
        ruleset_digest=ruleset_digest,
        allowed_proxy_addresses=proxy_addresses,
        proxy_port=proxy_port,
    )


def verify_signed_inspector_evidence(
    spec: WorkerLaunchSpec,
    envelope: object,
    *,
    trusted_public_keys: Mapping[str, bytes],
    expected_challenge: str,
    expected_proxy_addresses: Sequence[str],
    now: int | None = None,
    max_age_seconds: int = 60,
) -> VerifiedInspectorEvidence:
    """Verify Ed25519 authenticity, challenge freshness and exact firewall scope.

    The trusted public-key map and expected challenge must be supplied by a
    control plane outside the inspected worker. Challenge generation, one-time
    consumption, key provisioning/rotation and host collection are external
    responsibilities; this function is intentionally stateless and offline.
    """
    if not isinstance(envelope, dict) or set(envelope) != _ENVELOPE_FIELDS:
        raise InspectorEvidenceError("Inspector envelope has missing or unknown fields.")
    if type(envelope["schema_version"]) is not int or envelope["schema_version"] != 1:
        raise InspectorEvidenceError("Unsupported inspector envelope schema.")
    key_id = _require_identifier(envelope["key_id"], "key_id")
    if not isinstance(trusted_public_keys, Mapping) or key_id not in trusted_public_keys:
        raise InspectorEvidenceError("Inspector signing key is not trusted.")
    public_bytes = trusted_public_keys[key_id]
    if type(public_bytes) is not bytes or len(public_bytes) != 32:
        raise InspectorEvidenceError("Trusted Ed25519 public key must be exactly 32 bytes.")

    payload = envelope["payload"]
    if not isinstance(payload, dict) or set(payload) != _PAYLOAD_FIELDS:
        raise InspectorEvidenceError("Signed inspector payload has missing or unknown fields.")
    challenge = payload["challenge"]
    if (type(challenge) is not str or not _HEX64.fullmatch(challenge)
            or type(expected_challenge) is not str or not _HEX64.fullmatch(expected_challenge)
            or challenge != expected_challenge):
        raise InspectorEvidenceError("Inspector challenge mismatch or malformed challenge.")

    signature_text = envelope["signature"]
    if type(signature_text) is not str:
        raise InspectorEvidenceError("Inspector signature must be base64 text.")
    try:
        signature = base64.b64decode(signature_text, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise InspectorEvidenceError("Inspector signature encoding is invalid.") from exc
    if len(signature) != 64:
        raise InspectorEvidenceError("Ed25519 signature must be exactly 64 bytes.")

    signed_content = _canonical_json({
        "schema_version": 1,
        "key_id": key_id,
        "payload": payload,
    })
    try:
        Ed25519PublicKey.from_public_bytes(public_bytes).verify(signature, signed_content)
    except (InvalidSignature, ValueError) as exc:
        raise InspectorEvidenceError("Inspector signature verification failed.") from exc

    current = int(time.time()) if now is None else now
    if type(current) is not int or type(max_age_seconds) is not int or max_age_seconds < 1:
        raise InspectorEvidenceError("Evidence freshness parameters are invalid.")

    try:
        runtime = verify_prestart_attestation(
            spec, payload["runtime_attestation"],
            now=current, max_age_seconds=max_age_seconds,
        )
    except RuntimeAttestationError as exc:
        raise InspectorEvidenceError("Signed runtime attestation failed P05 validation.") from exc

    _proxy_host, proxy_port = _proxy_config(spec)
    normalized_proxy_ips = _normalize_proxy_addresses(expected_proxy_addresses)
    firewall = _verify_firewall(
        payload["firewall"],
        runtime_id=runtime.runtime_id,
        worker_id=runtime.worker_id,
        proxy_addresses=normalized_proxy_ips,
        proxy_port=proxy_port,
        now=current,
        max_age_seconds=max_age_seconds,
    )
    return VerifiedInspectorEvidence(
        key_id=key_id,
        challenge=challenge,
        runtime=runtime,
        firewall=firewall,
    )
