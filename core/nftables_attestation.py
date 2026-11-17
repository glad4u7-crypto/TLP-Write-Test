"""Strict read-only semantic attestation for APAA's per-worker nftables JSON."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import ipaddress
import json
from typing import Any, Iterable


class NftablesAttestationError(RuntimeError):
    """Live nftables state is missing, ambiguous, or broader than policy."""


@dataclass(frozen=True)
class NftablesPolicy:
    proxy_ips: tuple[str, ...]
    proxy_port: int

    def __post_init__(self) -> None:
        if type(self.proxy_ips) is not tuple or not 1 <= len(self.proxy_ips) <= 8:
            raise ValueError("one to eight pinned proxy IPs are required")
        normalized = []
        for value in self.proxy_ips:
            if type(value) is not str:
                raise ValueError("proxy IP must be text")
            address = ipaddress.ip_address(value)
            if (not address.is_global or address.is_unspecified or address.is_multicast
                    or address.is_loopback or address.is_link_local or address.is_reserved
                    or address.compressed != value):
                raise ValueError("proxy IP must be canonical public unicast")
            normalized.append(value)
        if len(set(normalized)) != len(normalized):
            raise ValueError("duplicate proxy IPs are forbidden")
        if type(self.proxy_port) is not int or not 1 <= self.proxy_port <= 65535:
            raise ValueError("proxy port is invalid")


@dataclass(frozen=True)
class NftablesAttestation:
    table: str
    chains: tuple[str, ...]
    accept_rule_count: int
    ruleset_sha256: str


def _field(value: Any) -> tuple[str, str]:
    if not isinstance(value, dict) or len(value) != 1:
        raise NftablesAttestationError("unsupported nftables match operand")
    kind, detail = next(iter(value.items()))
    if not isinstance(detail, dict):
        raise NftablesAttestationError("malformed nftables match operand")
    if kind == "payload":
        protocol, name = detail.get("protocol"), detail.get("field")
        if protocol not in {"ip", "ip6", "tcp", "icmpv6"} or not isinstance(name, str):
            raise NftablesAttestationError("unsupported payload field")
        return protocol, name
    if kind == "meta":
        name = detail.get("key")
        if name not in {"iifname", "oifname"}:
            raise NftablesAttestationError("unsupported meta field")
        return "meta", name
    if kind == "ct":
        name = detail.get("key")
        if name != "state":
            raise NftablesAttestationError("unsupported conntrack field")
        return "ct", name
    raise NftablesAttestationError("unsupported nftables match operand type")


def _rule_signature(rule: dict[str, Any]) -> tuple[str, tuple[tuple[str, str, str], ...]]:
    if rule.get("family") != "inet" or rule.get("table") != "apaa":
        raise NftablesAttestationError("rule belongs to an unexpected nftables table")
    chain = rule.get("chain")
    if chain not in {"input", "output"}:
        raise NftablesAttestationError("rule belongs to an unexpected chain")
    expressions = rule.get("expr")
    if not isinstance(expressions, list) or not expressions or expressions[-1] != {"accept": None}:
        raise NftablesAttestationError("only explicit terminal ACCEPT rules are permitted")
    matches = []
    for expression in expressions[:-1]:
        if not isinstance(expression, dict) or set(expression) != {"match"}:
            raise NftablesAttestationError("unknown nftables expression in ACCEPT rule")
        match = expression["match"]
        if not isinstance(match, dict) or match.get("op") not in {"==", "in"}:
            raise NftablesAttestationError("unsupported nftables match operator")
        left = _field(match.get("left"))
        right = match.get("right")
        if isinstance(right, (dict, list)):
            right_value = json.dumps(right, sort_keys=True, separators=(",", ":"))
        elif type(right) in (str, int, bool):
            right_value = json.dumps(right, separators=(",", ":"))
        else:
            raise NftablesAttestationError("unsupported nftables match value")
        matches.append((left[0] + "." + left[1], match["op"], right_value))
    if not matches:
        raise NftablesAttestationError("unconditional ACCEPT is forbidden")
    return chain, tuple(sorted(matches))


def _expected(policy: NftablesPolicy) -> Counter[tuple[str, tuple[tuple[str, str, str], ...]]]:
    eq = lambda field, value: (field, "==", json.dumps(value, separators=(",", ":")))
    inside = lambda field, values: (field, "in", json.dumps(list(values), separators=(",", ":")))
    expected: Counter[tuple[str, tuple[tuple[str, str, str], ...]]] = Counter()

    def add(chain: str, *matches: tuple[str, str, str]) -> None:
        expected[(chain, tuple(sorted(matches)))] += 1

    add("input", eq("meta.iifname", "lo"))
    add("output", eq("meta.oifname", "lo"))
    add("input", eq("ip6.saddr", "fe80::/10"), eq("icmpv6.type", "nd-neighbor-solicit"))
    add("input", eq("ip6.saddr", "fe80::/10"), eq("icmpv6.type", "nd-neighbor-advert"))
    add("output", eq("ip6.saddr", "fe80::/10"), eq("ip6.daddr", "ff02::/16"),
        eq("icmpv6.type", "nd-neighbor-solicit"))
    add("output", eq("ip6.saddr", "fe80::/10"), eq("ip6.daddr", "fe80::/10"),
        eq("icmpv6.type", "nd-neighbor-advert"))
    add("output", eq("ip6.saddr", "fe80::/10"), eq("ip6.daddr", "ff02::/16"),
        eq("icmpv6.type", "nd-neighbor-advert"))
    for raw_ip in policy.proxy_ips:
        address = ipaddress.ip_address(raw_ip)
        family = "ip" if address.version == 4 else "ip6"
        source, destination = family + ".saddr", family + ".daddr"
        add("input", eq(source, raw_ip), eq("tcp.sport", policy.proxy_port),
            inside("ct.state", ("established", "related")))
        add("output", eq(destination, raw_ip), eq("tcp.dport", policy.proxy_port),
            inside("ct.state", ("established", "related")))
        add("output", eq(destination, raw_ip), eq("tcp.dport", policy.proxy_port))
    return expected


def attest_nftables_json(document: str | bytes, policy: NftablesPolicy) -> NftablesAttestation:
    """Require exactly the two default-DROP chains and the exact approved ACCEPT set."""
    if not isinstance(policy, NftablesPolicy):
        raise TypeError("policy must be NftablesPolicy")
    if isinstance(document, bytes):
        try:
            raw = document.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise NftablesAttestationError("nftables JSON is not UTF-8") from exc
    elif isinstance(document, str):
        raw = document
    else:
        raise TypeError("nftables JSON must be text or bytes")
    if not raw or len(raw) > 1_000_000:
        raise NftablesAttestationError("nftables JSON is empty or exceeds the size limit")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise NftablesAttestationError("nftables returned malformed JSON") from exc
    items = payload.get("nftables") if isinstance(payload, dict) else None
    if not isinstance(items, list) or len(items) > 512:
        raise NftablesAttestationError("nftables JSON has an unexpected top-level shape")

    tables = []
    chains: dict[str, dict[str, Any]] = {}
    rules = []
    for item in items:
        if not isinstance(item, dict) or len(item) != 1:
            raise NftablesAttestationError("nftables JSON contains an unknown object")
        kind, value = next(iter(item.items()))
        if kind == "metainfo":
            continue
        if not isinstance(value, dict):
            raise NftablesAttestationError("nftables object is malformed")
        if kind == "table":
            if value.get("family") == "inet" and value.get("name") == "apaa":
                tables.append(value)
        elif kind == "chain":
            if value.get("family") == "inet" and value.get("table") == "apaa":
                name = value.get("name")
                if name in chains:
                    raise NftablesAttestationError("duplicate nftables chain")
                chains[name] = value
        elif kind == "rule":
            rules.append(value)
        else:
            raise NftablesAttestationError("unknown nftables object type")

    if len(tables) != 1 or set(chains) != {"input", "output"}:
        raise NftablesAttestationError("expected exactly one APAA table and input/output chains")
    for name, hook in (("input", "input"), ("output", "output")):
        chain = chains[name]
        if (chain.get("type") != "filter" or chain.get("hook") != hook
                or chain.get("policy") != "drop"):
            raise NftablesAttestationError("both base chains must have their exact default-DROP hook")
    observed: Counter[tuple[str, tuple[tuple[str, str, str], ...]]] = Counter()
    for rule in rules:
        observed[_rule_signature(rule)] += 1
    expected = _expected(policy)
    if observed != expected:
        raise NftablesAttestationError("live nftables ACCEPT rules differ from the exact approved policy")
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return NftablesAttestation("apaa", ("input", "output"), sum(observed.values()), digest)
