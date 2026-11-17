import copy
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.browser_isolation import validate_worker_profile
from core.browser_runtime import build_worker_launch_spec
from core.browser_nftables import (
    HostCollectionError,
    collect_signed_inspector_evidence,
    parse_nftables_egress,
)
from core.browser_inspector import verify_signed_inspector_evidence


PROXY_IP = "172.20.0.2"
PROXY_IPV6 = "fd00::2"
PROXY_IPS = [PROXY_IP, PROXY_IPV6]
PROXY_PORT = 3128
NOW = 1_000


def profile():
    return validate_worker_profile({
        "schema_version": 1, "uid": 10001, "gid": 10001,
        "privileged": False, "read_only_root": True,
        "no_new_privileges": True, "capabilities_drop": ["ALL"],
        "host_network": False, "host_pid": False, "host_ipc": False,
        "host_mounts": [], "secret_mounts": [],
        "writable_mounts": ["/tmp/job"],
        "browser_profile_persistence": False, "cdp_exposed": False,
        "direct_egress": False, "proxy_only_egress": True,
        "dns_via_proxy_only": True,
        "egress_proxy": "http://egress-proxy.internal:3128",
        "memory_limit_bytes": 512 * 1024 * 1024,
        "cpu_limit_millis": 1000, "pids_limit": 64,
        "job_timeout_seconds": 30,
    })


def runtime_attestation(spec):
    return {
        "schema_version": 1, "launch_spec_digest": spec.digest,
        "runtime_id": "runtime:test-001", "worker_id": "worker:test-001",
        "image_digest": "sha256:" + "a" * 64,
        "attestor_id": "inspector:test-001", "evidence_digest": "b" * 64,
        "observed_at": NOW, "state": "created", "process_started": False,
        "runtime_config_verified": True, "host_firewall_verified": True,
        "uid": spec.uid, "gid": spec.gid,
        "privileged": False, "read_only_root": True,
        "no_new_privileges": True, "capabilities_effective": [],
        "namespaces": list(spec.namespaces), "host_mounts": [],
        "secret_mounts": [], "writable_mounts": list(spec.writable_mounts),
        "browser_profile_persistence": False, "cdp_exposed": False,
        "direct_egress": False, "proxy_only_egress": True,
        "dns_via_proxy_only": True, "egress_proxy": spec.egress_proxy,
        "memory_limit_bytes": spec.memory_limit_bytes,
        "cpu_limit_millis": spec.cpu_limit_millis,
        "pids_limit": spec.pids_limit, "job_timeout_seconds": spec.job_timeout_seconds,
        "seccomp_enforced": True, "network_namespace_isolated": True,
        "firewall_default_deny": True,
        "egress_allowed": ["egress-proxy.internal:3128"],
        "direct_dns_egress_blocked": True, "proxy_side_dns_only": True,
    }


def match(left, right, op="=="):
    return {"match": {"op": op, "left": left, "right": right}}


def rule(chain, expr):
    return {"rule": {
        "family": "inet", "table": "apaa", "chain": chain, "expr": expr,
    }}


def proxy_expr(address, direction, state):
    import ipaddress
    parsed = ipaddress.ip_address(address)
    family = "ip" if parsed.version == 4 else "ip6"
    ip_field, port_field = (("saddr", "sport") if direction == "input" else ("daddr", "dport"))
    return [
        match({"payload": {"protocol": family, "field": ip_field}}, parsed.compressed),
        match({"payload": {"protocol": "tcp", "field": port_field}}, PROXY_PORT),
        match({"ct": {"key": "state"}}, state, op="in"),
        {"accept": None},
    ]


def allow_rule(address=PROXY_IP, port=PROXY_PORT):
    expr = proxy_expr(address, "output", "new")
    expr[1]["match"]["right"] = port
    return rule("output", expr)


def nftables():
    link_local = {"prefix": {"addr": "fe80::", "len": 10}}
    link_multicast = {"prefix": {"addr": "ff02::", "len": 16}}
    items = [
        {"metainfo": {"version": "1.0.9", "release_name": "test"}},
        {"table": {"family": "inet", "name": "apaa"}},
        {"chain": {
            "family": "inet", "table": "apaa", "name": "input",
            "type": "filter", "hook": "input", "prio": 0, "policy": "drop",
        }},
        {"chain": {
            "family": "inet", "table": "apaa", "name": "output",
            "type": "filter", "hook": "output", "prio": 0, "policy": "drop",
        }},
        rule("input", [
            match({"meta": {"key": "iifname"}}, "lo"), {"accept": None},
        ]),
        rule("input", [
            match({"payload": {"protocol": "ip6", "field": "saddr"}}, link_local),
            match({"payload": {"protocol": "icmpv6", "field": "type"}}, "nd-neighbor-solicit"),
            {"accept": None},
        ]),
        rule("input", [
            match({"payload": {"protocol": "ip6", "field": "saddr"}}, link_local),
            match({"payload": {"protocol": "icmpv6", "field": "type"}}, "nd-neighbor-advert"),
            {"accept": None},
        ]),
        rule("output", [
            match({"meta": {"key": "oifname"}}, "lo"), {"accept": None},
        ]),
        rule("output", [
            match({"payload": {"protocol": "ip6", "field": "saddr"}}, link_local),
            match({"payload": {"protocol": "ip6", "field": "daddr"}}, link_multicast),
            match({"payload": {"protocol": "icmpv6", "field": "type"}}, "nd-neighbor-solicit"),
            {"accept": None},
        ]),
        rule("output", [
            match({"payload": {"protocol": "ip6", "field": "saddr"}}, link_local),
            match({"payload": {"protocol": "ip6", "field": "daddr"}}, link_local),
            match({"payload": {"protocol": "icmpv6", "field": "type"}}, "nd-neighbor-advert"),
            {"accept": None},
        ]),
        rule("output", [
            match({"payload": {"protocol": "ip6", "field": "saddr"}}, link_local),
            match({"payload": {"protocol": "ip6", "field": "daddr"}}, link_multicast),
            match({"payload": {"protocol": "icmpv6", "field": "type"}}, "nd-neighbor-advert"),
            {"accept": None},
        ]),
    ]
    for address in PROXY_IPS:
        items.append(rule("input", proxy_expr(address, "input", ["established", "related"])))
        items.append(rule("output", proxy_expr(address, "output", ["established", "related"])))
        items.append(rule("output", proxy_expr(address, "output", "new")))
    return {"nftables": items}


def _first_proxy_output_rule(document):
    return next(
        item["rule"] for item in document["nftables"]
        if "rule" in item and item["rule"]["chain"] == "output"
        and item["rule"]["expr"][0].get("match", {}).get("left", {}).get("payload", {}).get("field") == "daddr"
        and item["rule"]["expr"][2].get("match", {}).get("right") == "new"
    )

class FakeHostSource:
    def __init__(self, spec, rules=None):
        self.runtime = runtime_attestation(spec)
        self.namespace = {
            "runtime_id": "runtime:test-001",
            "worker_id": "worker:test-001",
            "inode": 4026533001,
            "interface": "eth0",
        }
        self.rules = nftables() if rules is None else rules
        self.calls = []

    def read_runtime_attestation(self):
        self.calls.append("runtime")
        return copy.deepcopy(self.runtime)

    def read_network_namespace_identity(self):
        self.calls.append("namespace")
        return copy.deepcopy(self.namespace)

    def read_nftables_json(self):
        self.calls.append("nftables")
        return copy.deepcopy(self.rules)


def test_parser_accepts_exact_proxy_only_output_policy_and_digest():
    parsed = parse_nftables_egress(
        json.dumps(nftables()), expected_proxy_addresses=PROXY_IPS,
        expected_proxy_port=PROXY_PORT,
    )
    assert parsed.default_policy == "drop"
    assert parsed.allowed_egress == ((PROXY_IP, "tcp", PROXY_PORT), (PROXY_IPV6, "tcp", PROXY_PORT))
    assert len(parsed.ruleset_digest) == 64


@pytest.mark.parametrize("mutate", [
    lambda doc: doc["nftables"][2]["chain"].update(policy="accept"),
    lambda doc: doc["nftables"].append({"chain": {
        "family": "inet", "table": "filter", "name": "other",
        "type": "filter", "hook": "output", "prio": 1, "policy": "drop",
    }}),
    lambda doc: doc["nftables"].append(allow_rule("1.1.1.1", 443)),
    lambda doc: _first_proxy_output_rule(doc)["expr"][1]["match"].update(left={"payload": {"protocol": "udp", "field": "dport"}}),
    lambda doc: _first_proxy_output_rule(doc)["expr"].append({"counter": {"packets": 1, "bytes": 1}}),
    lambda doc: _first_proxy_output_rule(doc)["expr"].__setitem__(3, {"jump": {"target": "allow_all"}}),
    lambda doc: _first_proxy_output_rule(doc)["expr"][0]["match"].update(right="0.0.0.0/0"),
])
def test_parser_rejects_unsafe_or_unknown_output_rules(mutate):
    doc = nftables()
    mutate(doc)
    with pytest.raises(HostCollectionError):
        parse_nftables_egress(
            doc, expected_proxy_addresses=PROXY_IPS, expected_proxy_port=PROXY_PORT,
        )


def test_parser_rejects_wrong_proxy_ip_or_port():
    with pytest.raises(HostCollectionError):
        parse_nftables_egress(
            nftables(), expected_proxy_addresses=["172.20.0.3", PROXY_IPV6],
            expected_proxy_port=PROXY_PORT,
        )
    with pytest.raises(HostCollectionError):
        parse_nftables_egress(
            nftables(), expected_proxy_addresses=PROXY_IPS,
            expected_proxy_port=3129,
        )


def test_collector_emits_p06_compatible_signed_evidence():
    spec = build_worker_launch_spec(profile())
    source = FakeHostSource(spec)
    key = Ed25519PrivateKey.generate()
    envelope = collect_signed_inspector_evidence(
        source, spec, challenge="d" * 64, key_id="host-inspector-prod",
        signing_key=key, expected_proxy_addresses=[PROXY_IP], now=NOW,
    )
    assert source.calls == ["runtime", "namespace", "nftables"]
    public = key.public_key().public_bytes_raw()
    verified = verify_signed_inspector_evidence(
        spec, envelope, trusted_public_keys={"host-inspector-prod": public},
        expected_challenge="d" * 64, expected_proxy_addresses=[PROXY_IP], now=NOW,
    )
    assert verified.firewall.default_egress_policy == "drop"
    assert verified.firewall.ruleset_digest == envelope["payload"]["firewall"]["ruleset_digest"]


def test_collector_fails_closed_when_runtime_identity_or_firewall_is_unsafe():
    spec = build_worker_launch_spec(profile())
    source = FakeHostSource(spec)
    source.namespace["worker_id"] = "worker:wrong-001"
    with pytest.raises(HostCollectionError):
        collect_signed_inspector_evidence(
            source, spec, challenge="d" * 64, key_id="host-inspector-prod",
            signing_key=Ed25519PrivateKey.generate(),
            expected_proxy_addresses=[PROXY_IP], now=NOW,
        )
    source = FakeHostSource(spec, rules={"nftables": [
        {"chain": {"family": "inet", "table": "filter", "name": "egress",
                   "type": "filter", "hook": "output", "prio": 0, "policy": "accept"}}
    ]})
    with pytest.raises(HostCollectionError):
        collect_signed_inspector_evidence(
            source, spec, challenge="d" * 64, key_id="host-inspector-prod",
            signing_key=Ed25519PrivateKey.generate(),
            expected_proxy_addresses=[PROXY_IP], now=NOW,
        )


def test_collector_rejects_invalid_challenge_key_and_source():
    spec = build_worker_launch_spec(profile())
    args = dict(
        spec=spec, key_id="host-inspector-prod",
        signing_key=Ed25519PrivateKey.generate(),
        expected_proxy_addresses=[PROXY_IP], now=NOW,
    )
    with pytest.raises(HostCollectionError):
        collect_signed_inspector_evidence(
            object(), challenge="d" * 64, **args,
        )
    with pytest.raises(HostCollectionError):
        collect_signed_inspector_evidence(
            FakeHostSource(spec), challenge="not-a-challenge", **args,
        )
