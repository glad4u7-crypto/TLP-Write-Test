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


def _nft_match(left: dict, right: object, *, op: str = "==") -> dict:
    return {"match": {"left": left, "op": op, "right": right}}


def _proxy_rule_expr(address: str, port: int, *, direction: str, state: object) -> list[dict]:
    parsed = ipaddress.ip_address(address)
    family = "ip" if parsed.version == 4 else "ip6"
    if direction == "input":
        ip_field, port_field = "saddr", "sport"
    elif direction == "output":
        ip_field, port_field = "daddr", "dport"
    else:
        raise HostCollectionError("Unsupported nftables proxy direction.")
    return [
        _nft_match({"payload": {"protocol": family, "field": ip_field}}, parsed.compressed),
        _nft_match({"payload": {"protocol": "tcp", "field": port_field}}, port),
        _nft_match({"ct": {"key": "state"}}, state, op="in"),
        {"accept": None},
    ]


def _expected_dual_stack_rules(
    proxies: tuple[str, ...], port: int,
) -> dict[str, list[list[dict]]]:
    """Exact input/output allowlist for the APAA dual-stack proxy namespace."""
    link_local = {"prefix": {"addr": "fe80::", "len": 10}}
    link_multicast = {"prefix": {"addr": "ff02::", "len": 16}}
    loopback_input = [
        _nft_match({"meta": {"key": "iifname"}}, "lo"),
        {"accept": None},
    ]
    loopback_output = [
        _nft_match({"meta": {"key": "oifname"}}, "lo"),
        {"accept": None},
    ]
    ndp_input = [
        [
            _nft_match({"payload": {"protocol": "ip6", "field": "saddr"}}, link_local),
            _nft_match({"payload": {"protocol": "icmpv6", "field": "type"}}, kind),
            {"accept": None},
        ]
        for kind in ("nd-neighbor-solicit", "nd-neighbor-advert")
    ]
    ndp_output = [
        [
            _nft_match({"payload": {"protocol": "ip6", "field": "saddr"}}, link_local),
            _nft_match({"payload": {"protocol": "ip6", "field": "daddr"}}, destination),
            _nft_match({"payload": {"protocol": "icmpv6", "field": "type"}}, kind),
            {"accept": None},
        ]
        for destination, kind in (
            (link_multicast, "nd-neighbor-solicit"),
            (link_local, "nd-neighbor-advert"),
            (link_multicast, "nd-neighbor-advert"),
        )
    ]
    established_related = ["established", "related"]
    input_rules = [loopback_input, *ndp_input]
    output_rules = [loopback_output, *ndp_output]
    for address in proxies:
        input_rules.append(_proxy_rule_expr(
            address, port, direction="input", state=established_related,
        ))
        output_rules.append(_proxy_rule_expr(
            address, port, direction="output", state=established_related,
        ))
        output_rules.append(_proxy_rule_expr(
            address, port, direction="output", state="new",
        ))
    return {"input": input_rules, "output": output_rules}


def parse_nftables_egress(
    raw: Mapping[str, object] | str | bytes,
    *,
    expected_proxy_addresses: Sequence[str],
    expected_proxy_port: int,
) -> ParsedNftablesEgress:
    """Attest the complete APAA dual-stack input/output default-DROP ruleset.

    The parser accepts exactly one inet apaa table, one input and one output
    filter base chain (both default DROP), and the exact loopback, bounded IPv6
    neighbour-discovery, and proxy-only TCP rules. Every ACCEPT expression is
    compared with the complete reviewed policy; unknown chains, rules, matches,
    jumps, sets, or extra ACCEPT paths fail closed.
    """
    document = _json_object(raw)
    if set(document) != {"nftables"} or not isinstance(document["nftables"], list):
        raise HostCollectionError("Unexpected nftables JSON top-level schema.")
    proxies = _normalize_proxy_addresses(expected_proxy_addresses)
    if type(expected_proxy_port) is not int or not 1 <= expected_proxy_port <= 65535:
        raise HostCollectionError("Approved proxy port is invalid.")

    tables: list[dict] = []
    chains: dict[str, dict] = {}
    rules_by_chain: dict[str, list[list[dict]]] = {"input": [], "output": []}
    metainfo_count = 0
    for item in document["nftables"]:
        if not isinstance(item, dict) or len(item) != 1:
            raise HostCollectionError("Malformed nftables object.")
        kind, value = next(iter(item.items()))
        if kind == "metainfo":
            metainfo_count += 1
            if not isinstance(value, dict):
                raise HostCollectionError("Malformed nftables metainfo.")
        elif kind == "table":
            if not isinstance(value, dict) or not {"family", "name"}.issubset(value):
                raise HostCollectionError("Malformed nftables table.")
            if set(value) - {"family", "name", "handle"}:
                raise HostCollectionError("Nftables table contains unknown fields.")
            tables.append(value)
        elif kind == "chain":
            if not isinstance(value, dict):
                raise HostCollectionError("Malformed nftables chain.")
            if set(value) - {"family", "table", "name", "type", "hook", "prio", "policy", "handle"}:
                raise HostCollectionError("Nftables chain contains unknown fields.")
            name = value.get("name")
            if type(name) is not str or name in chains:
                raise HostCollectionError("Nftables chain names are missing or duplicated.")
            chains[name] = value
        elif kind == "rule":
            if not isinstance(value, dict):
                raise HostCollectionError("Malformed nftables rule.")
            if set(value) - {"family", "table", "chain", "expr", "handle"}:
                raise HostCollectionError("Nftables rule contains unknown fields.")
            chain_name = value.get("chain")
            if chain_name not in rules_by_chain:
                raise HostCollectionError("Rule exists outside the reviewed input/output chains.")
            if (value.get("family") != "inet" or value.get("table") != "apaa"
                    or not isinstance(value.get("expr"), list)):
                raise HostCollectionError("Nftables rule is attached to an unexpected table or schema.")
            rules_by_chain[chain_name].append(value["expr"])
        else:
            raise HostCollectionError("Unsupported nftables object type.")

    if metainfo_count != 1 or len(tables) != 1 or tables[0].get("family") != "inet" or tables[0].get("name") != "apaa":
        raise HostCollectionError("Exactly one inet apaa nftables table and metainfo record are required.")
    if set(chains) != {"input", "output"}:
        raise HostCollectionError("Exactly the reviewed input and output base chains are required.")
    for name, hook in (("input", "input"), ("output", "output")):
        chain = chains[name]
        if (chain.get("family") != "inet" or chain.get("table") != "apaa"
                or chain.get("type") != "filter" or chain.get("hook") != hook
                or chain.get("policy") != "drop" or type(chain.get("prio")) is not int
                or chain.get("prio") != 0):
            raise HostCollectionError("Both base chains must be inet/filter, priority zero and default DROP.")

    expected = _expected_dual_stack_rules(proxies, expected_proxy_port)
    for chain_name in ("input", "output"):
        actual_encoded = sorted(_canonical_json(expr) for expr in rules_by_chain[chain_name])
        expected_encoded = sorted(_canonical_json(expr) for expr in expected[chain_name])
        if actual_encoded != expected_encoded or len(actual_encoded) != len(expected_encoded):
            raise HostCollectionError(
                f"Effective {chain_name} rules differ from the exact APAA dual-stack policy."
            )

    digest = hashlib.sha256(_canonical_json(document)).hexdigest()
    allowed = tuple((ip, "tcp", expected_proxy_port) for ip in proxies)
    return ParsedNftablesEgress("drop", allowed, digest)

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
