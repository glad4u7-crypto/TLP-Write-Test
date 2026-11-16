import pytest
from core.browser_nftables import HostCollectionError, parse_nftables_egress

PROXY = "172.20.0.2"
PORT = 3128

def match(left, right):
    return {"match": {"op": "==", "left": left, "right": right}}

def base_ruleset():
    return {"nftables": [
        {"metainfo": {"version": "1.0.9"}},
        {"table": {"family": "inet", "name": "filter"}},
        {"chain": {"family": "inet", "table": "filter", "name": "egress",
                   "type": "filter", "hook": "output", "prio": 0, "policy": "drop"}},
        {"rule": {"family": "inet", "table": "filter", "chain": "egress", "expr": [
            match({"meta": {"key": "l4proto"}}, "tcp"),
            match({"payload": {"protocol": "ip", "field": "daddr"}}, PROXY),
            match({"payload": {"protocol": "tcp", "field": "dport"}}, PORT),
            {"accept": None},
        ]}},
    ]}

def parse(doc):
    return parse_nftables_egress(doc, expected_proxy_addresses=[PROXY], expected_proxy_port=PORT)

@pytest.mark.parametrize("protocol,address,port", [
    ("udp", PROXY, 53),
    ("udp", PROXY, 443),
    ("tcp", "1.1.1.1", 443),
    ("tcp", "8.8.8.8", 53),
    ("tcp", PROXY, 53),
])
def test_rejects_dns_quic_and_direct_network_bypass(protocol, address, port):
    doc = base_ruleset()
    doc["nftables"].append({"rule": {"family": "inet", "table": "filter", "chain": "egress", "expr": [
        match({"meta": {"key": "l4proto"}}, protocol),
        match({"payload": {"protocol": "ip", "field": "daddr"}}, address),
        match({"payload": {"protocol": "tcp" if protocol == "tcp" else "udp", "field": "dport"}}, port),
        {"accept": None},
    ]}})
    with pytest.raises(HostCollectionError):
        parse(doc)

def test_rejects_ipv6_egress_allow_rule_even_if_ipv4_proxy_rule_is_present():
    doc = base_ruleset()
    doc["nftables"].append({"rule": {"family": "inet", "table": "filter", "chain": "egress", "expr": [
        match({"meta": {"key": "l4proto"}}, "tcp"),
        match({"payload": {"protocol": "ip6", "field": "daddr"}}, "2606:4700:4700::1111"),
        match({"payload": {"protocol": "tcp", "field": "dport"}}, 443),
        {"accept": None},
    ]}})
    with pytest.raises(HostCollectionError):
        parse(doc)

@pytest.mark.parametrize("extra", [
    {"set": {"family": "inet", "table": "filter", "name": "bypass", "type": "ipv4_addr"}},
    {"element": {"family": "inet", "table": "filter", "name": "bypass", "elem": ["1.1.1.1"]}},
    {"counter": {"family": "inet", "table": "filter", "name": "c"}},
])
def test_rejects_unmodelled_nftables_objects_instead_of_ignoring_them(extra):
    doc = base_ruleset()
    doc["nftables"].append(extra)
    with pytest.raises(HostCollectionError):
        parse(doc)

def test_rejects_multiple_tables_or_non_inet_table():
    doc = base_ruleset()
    doc["nftables"].append({"table": {"family": "ip6", "name": "other"}})
    with pytest.raises(HostCollectionError):
        parse(doc)
