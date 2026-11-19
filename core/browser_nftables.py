"""Read-only host-inspector collection boundary and strict nftables JSON parser.

This package has no default host adapter and never invokes a shell, runtime API,
DNS resolver, socket or firewall command. A separately reviewed host adapter
must implement HostSnapshotSource and return independently collected snapshots.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import base64
import hashlib
import ipaddress
import json
import re
import time
from typing import Protocol, runtime_checkable

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.browser_runtime import WorkerLaunchSpec, verify_prestart_attestation
from core.browser_inspector import _canonical_json, _normalize_proxy_addresses, _proxy_config


class HostCollectionError(ValueError):
    """Raised when host snapshots are incomplete or fail closed validation."""


@dataclass(frozen=True)
class NetworkNamespaceIdentity:
    runtime_id: str
    worker_id: str
    inode: int
    interface: str


@dataclass(frozen=True)
class ParsedNftablesEgress:
    default_policy: str
    allowed_egress: tuple[tuple[str, str, int], ...]
    ruleset_digest: str


@runtime_checkable
class HostSnapshotSource(Protocol):
    """Injected read-only adapter; implementations are not supplied by APAA."""

    def read_runtime_attestation(self) -> Mapping[str, object]: ...
    def read_network_namespace_identity(self) -> Mapping[str, object]: ...
    def read_nftables_json(self) -> Mapping[str, object] | str | bytes: ...


_INTERFACE = re.compile(r"^[A-Za-z0-9_.:-]{1,15}$")
_NAMESPACE_FIELDS = frozenset({"runtime_id", "worker_id", "inode", "interface"})
_MATCH_FIELDS = frozenset({"op", "left", "right"})


def _json_object(raw: Mapping[str, object] | str | bytes) -> dict:
    if isinstance(raw, (str, bytes)):
        try:
            raw = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HostCollectionError("nftables snapshot is not valid JSON.") from exc
    if not isinstance(raw, Mapping) or any(type(k) is not str for k in raw):
        raise HostCollectionError("nftables snapshot must be a string-keyed JSON object.")
    # Round-trip rejects custom objects and non-JSON values supplied by adapters.
    try:
        normalized = json.loads(json.dumps(raw, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise HostCollectionError("nftables snapshot contains non-JSON values.") from exc
    return normalized


def _match(expr: object) -> tuple[str, object] | None:
    if not isinstance(expr, dict) or set(expr) != {"match"}:
        return None
    value = expr["match"]
    if not isinstance(value, dict) or set(value) != _MATCH_FIELDS or value["op"] != "==":
        return None
    left, right = value["left"], value["right"]
    if left == {"meta": {"key": "l4proto"}} and right == "tcp":
        return ("protocol", "tcp")
    if left in (
        {"payload": {"protocol": "ip", "field": "daddr"}},
        {"payload": {"protocol": "ip6", "field": "daddr"}},
    ) and type(right) is str:
        try:
            address = ipaddress.ip_address(right)
        except ValueError:
            return None
        expected_version = 4 if left["payload"]["protocol"] == "ip" else 6
        if address.version != expected_version:
            return None
        return ("destination_ip", address.compressed.lower())
    if left == {"payload": {"protocol": "tcp", "field": "dport"}} and type(right) is int:
        if 1 <= right <= 65535:
            return ("destination_port", right)
    return None


def parse_nftables_egress(
    raw: Mapping[str, object] | str | bytes,
    *,
    expected_proxy_addresses: Sequence[str],
    expected_proxy_port: int,
) -> ParsedNftablesEgress:
    """Parse a deliberately narrow nft -j ruleset subset; reject unknown output policy.

    Exactly one dedicated inet/filter table and one inet/filter output base
    chain are supported. The chain must have policy drop. Every rule must belong
    to that sole chain and be a simple TCP + exact IPv4/IPv6 destination + exact
    TCP destination-port match followed by accept. Extra tables/chains, NAT or
    forwarding hooks, sets, maps, counters, jumps and unknown objects fail closed.
    """
    document = _json_object(raw)
    if set(document) != {"nftables"} or not isinstance(document["nftables"], list):
        raise HostCollectionError("Unexpected nftables JSON top-level schema.")
    proxies = _normalize_proxy_addresses(expected_proxy_addresses)
    if type(expected_proxy_port) is not int or not 1 <= expected_proxy_port <= 65535:
        raise HostCollectionError("Approved proxy port is invalid.")

    tables: list[dict] = []
    chains: list[dict] = []
    rule_objects: list[dict] = []
    for item in document["nftables"]:
        if not isinstance(item, dict) or len(item) != 1:
            raise HostCollectionError("Malformed nftables object.")
        kind, value = next(iter(item.items()))
        if kind == "metainfo":
            if not isinstance(value, dict) or set(value) - {"version", "release_name", "json_schema_version"}:
                raise HostCollectionError("Unsupported nftables metainfo.")
        elif kind == "table":
            if not isinstance(value, dict) or set(value) - {"family", "name", "handle"}:
                raise HostCollectionError("Malformed or unsupported nftables table.")
            if not {"family", "name"} <= set(value):
                raise HostCollectionError("Nftables table identity is incomplete.")
            tables.append(value)
        elif kind == "chain":
            if not isinstance(value, dict) or set(value) - {
                "family", "table", "name", "type", "hook", "prio", "policy", "handle"
            }:
                raise HostCollectionError("Malformed or unsupported nftables chain.")
            chains.append(value)
        elif kind == "rule":
            if not isinstance(value, dict) or set(value) - {
                "family", "table", "chain", "expr", "handle", "comment"
            }:
                raise HostCollectionError("Malformed or unsupported nftables rule.")
            rule_objects.append(value)
        else:
            # Reject sets, maps, elements, counters, flowtables and every
            # unreviewed object: any may affect the effective packet path.
            raise HostCollectionError("Unsupported nftables object type.")

    if len(tables) != 1 or len(chains) != 1:
        raise HostCollectionError("Exactly one nftables table and one base chain are required.")
    table = tables[0]
    if table.get("family") != "inet" or table.get("name") != "filter":
        raise HostCollectionError("Only the dedicated inet filter table is supported.")
    chain = chains[0]
    if (chain.get("family") != "inet" or chain.get("table") != table["name"]
            or chain.get("type") != "filter" or chain.get("hook") != "output"
            or chain.get("policy") != "drop" or type(chain.get("name")) is not str
            or type(chain.get("prio")) is not int):
        raise HostCollectionError("Only the inet/filter output base chain with default DROP is supported.")
    chain_name = chain["name"]
    rules: list[tuple[str, str, int]] = []
    for value in rule_objects:
        if (value.get("family") != "inet" or value.get("table") != table["name"]
                or value.get("chain") != chain_name):
            raise HostCollectionError("Rule is attached outside the sole approved output chain.")
        expr = value.get("expr")
        if not isinstance(expr, list) or len(expr) != 4 or expr[-1] != {"accept": None}:
            raise HostCollectionError("Output rule is not in the reviewed exact-proxy form.")
        matches = [_match(part) for part in expr[:3]]
        if any(part is None for part in matches):
            raise HostCollectionError("Output rule contains unsupported match expressions.")
        fields = dict(matches)
        if set(fields) != {"protocol", "destination_ip", "destination_port"}:
            raise HostCollectionError("Output rule must constrain protocol, IP and port.")
        if fields["protocol"] != "tcp" or fields["destination_port"] != expected_proxy_port:
            raise HostCollectionError("Output rule permits an unapproved protocol or port.")
        rules.append((fields["destination_ip"], "tcp", fields["destination_port"]))

    expected = sorted((ip, "tcp", expected_proxy_port) for ip in proxies)
    if sorted(rules) != expected or len(rules) != len(expected):
        raise HostCollectionError("Effective output rules do not equal the exact proxy allowlist.")
    digest = hashlib.sha256(_canonical_json(document)).hexdigest()
    return ParsedNftablesEgress("drop", tuple((ip, proto, port) for ip, proto, port in sorted(rules)), digest)


def _namespace_identity(raw: object, runtime_id: str, worker_id: str) -> NetworkNamespaceIdentity:
    if not isinstance(raw, Mapping) or set(raw) != _NAMESPACE_FIELDS:
        raise HostCollectionError("Network namespace identity has missing or unknown fields.")
    inode, interface = raw["inode"], raw["interface"]
    if raw["runtime_id"] != runtime_id or raw["worker_id"] != worker_id:
        raise HostCollectionError("Network namespace identity does not match runtime evidence.")
    if type(inode) is not int or inode <= 0:
        raise HostCollectionError("Network namespace inode must be a positive integer.")
    if type(interface) is not str or not _INTERFACE.fullmatch(interface):
        raise HostCollectionError("Network interface name is invalid.")
    return NetworkNamespaceIdentity(runtime_id, worker_id, inode, interface)


def collect_signed_inspector_evidence(
    source: HostSnapshotSource,
    spec: WorkerLaunchSpec,
    *,
    challenge: str,
    key_id: str,
    signing_key: Ed25519PrivateKey,
    expected_proxy_addresses: Sequence[str],
    now: int | None = None,
    max_age_seconds: int = 60,
) -> dict[str, object]:
    """Collect through an injected read-only source, validate, then sign P06 envelope.

    No source implementation, private key storage, host command or collector
    daemon is included. The caller is responsible for authenticating the source,
    provisioning the key out-of-band and consuming the challenge exactly once.
    """
    if not isinstance(source, HostSnapshotSource):
        raise HostCollectionError("A trusted HostSnapshotSource adapter is required.")
    if type(challenge) is not str or not re.fullmatch(r"[0-9a-f]{64}", challenge):
        raise HostCollectionError("A caller-generated 256-bit challenge is required.")
    if type(key_id) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}", key_id):
        raise HostCollectionError("Inspector key ID is invalid.")
    if not isinstance(signing_key, Ed25519PrivateKey):
        raise HostCollectionError("An externally provisioned Ed25519 private key is required.")
    current = int(time.time()) if now is None else now
    if type(current) is not int:
        raise HostCollectionError("Collection timestamp is invalid.")

    try:
        runtime_raw = source.read_runtime_attestation()
        runtime = verify_prestart_attestation(
            spec, runtime_raw, now=current, max_age_seconds=max_age_seconds,
        )
        namespace = _namespace_identity(
            source.read_network_namespace_identity(), runtime.runtime_id, runtime.worker_id,
        )
        proxy_addresses = _normalize_proxy_addresses(expected_proxy_addresses)
        _proxy_host, proxy_port = _proxy_config(spec)
        nft_raw = source.read_nftables_json()
        parsed = parse_nftables_egress(
            nft_raw, expected_proxy_addresses=proxy_addresses,
            expected_proxy_port=proxy_port,
        )
    except HostCollectionError:
        raise
    except Exception as exc:
        raise HostCollectionError("Trusted host snapshot collection or validation failed closed.") from exc

    firewall = {
        "schema_version": 1,
        "runtime_id": namespace.runtime_id,
        "worker_id": namespace.worker_id,
        "network_namespace_inode": namespace.inode,
        "interface": namespace.interface,
        "backend": "nftables",
        "observed_at": current,
        "default_egress_policy": parsed.default_policy,
        "allowed_egress": [
            {"protocol": protocol, "destination_ip": address, "destination_port": port}
            for address, protocol, port in parsed.allowed_egress
        ],
        "direct_dns_blocked": True,
        "proxy_side_dns_only": True,
        "ruleset_digest": parsed.ruleset_digest,
    }
    payload = {
        "challenge": challenge,
        "runtime_attestation": dict(runtime_raw),
        "firewall": firewall,
    }
    signed = {"schema_version": 1, "key_id": key_id, "payload": payload}
    signature = signing_key.sign(_canonical_json(signed))
    envelope = {
        **signed,
        "signature": base64.b64encode(signature).decode("ascii"),
    }
    # Ensure the emitted envelope is compatible with the P06 verifier before returning.
    from core.browser_inspector import verify_signed_inspector_evidence
    public_key = signing_key.public_key().public_bytes_raw()
    try:
        verify_signed_inspector_evidence(
            spec, envelope, trusted_public_keys={key_id: public_key},
            expected_challenge=challenge, expected_proxy_addresses=proxy_addresses,
            now=current, max_age_seconds=max_age_seconds,
        )
    except Exception as exc:
        raise HostCollectionError("Collected evidence did not pass the P06 verifier.") from exc
    return envelope
