import json
import pytest
from core.nftables_attestation import (
    NftablesAttestationError, NftablesPolicy, attest_nftables_json,
)

P4="198.18.0.1"
P6="2001:db8:1::1"

def m(field, value, op="=="):
    kind, name = field.split(".",1)
    if kind in ("ip","ip6","tcp","icmpv6"):
        left={"payload":{"protocol":kind,"field":name}}
    elif kind=="meta":
        left={"meta":{"key":name}}
    else:
        left={"ct":{"key":name}}
    return {"match":{"op":op,"left":left,"right":value}}

def rule(chain,*matches):
    return {"rule":{"family":"inet","table":"apaa","chain":chain,
                    "expr":[*matches,{"accept":None}]}}

def fixture():
    items=[
      {"metainfo":{"version":1}},
      {"table":{"family":"inet","name":"apaa","handle":1}},
      {"chain":{"family":"inet","table":"apaa","name":"input","type":"filter","hook":"input","prio":0,"policy":"drop"}},
      {"chain":{"family":"inet","table":"apaa","name":"output","type":"filter","hook":"output","prio":0,"policy":"drop"}},
      rule("input",m("meta.iifname","lo")),
      rule("output",m("meta.oifname","lo")),
      rule("input",m("ip6.saddr",{"prefix":{"addr":"fe80::","len":10}}),m("icmpv6.type","nd-neighbor-solicit")),
      rule("input",m("ip6.saddr",{"prefix":{"addr":"fe80::","len":10}}),m("icmpv6.type","nd-neighbor-advert")),
      rule("output",m("ip6.saddr",{"prefix":{"addr":"fe80::","len":10}}),m("ip6.daddr",{"prefix":{"addr":"ff02::","len":16}}),m("icmpv6.type","nd-neighbor-solicit")),
      rule("output",m("ip6.saddr",{"prefix":{"addr":"fe80::","len":10}}),m("ip6.daddr",{"prefix":{"addr":"fe80::","len":10}}),m("icmpv6.type","nd-neighbor-advert")),
      rule("output",m("ip6.saddr",{"prefix":{"addr":"fe80::","len":10}}),m("ip6.daddr",{"prefix":{"addr":"ff02::","len":16}}),m("icmpv6.type","nd-neighbor-advert")),
    ]
    for ip, fam in ((P4,"ip"),(P6,"ip6")):
      src,dst=fam+".saddr",fam+".daddr"
      rules=[
       rule("input",m(src,ip),m("tcp.sport",3128),m("ct.state",{"set":["established","related"]},"in")),
       rule("output",m(dst,ip),m("tcp.dport",3128),m("ct.state",{"set":["established","related"]},"in")),
       rule("output",m(dst,ip),m("tcp.dport",3128),m("ct.state","new")),
      ]
      items.extend(rules)
    return {"nftables":items}

def policy():
    return NftablesPolicy((P4,P6),3128)

def test_attests_exact_dual_stack_default_drop_policy():
    result=attest_nftables_json(json.dumps(fixture()),policy())
    assert result.table=="apaa"
    assert result.chains==("input","output")
    assert result.accept_rule_count==13
    assert len(result.ruleset_sha256)==64

@pytest.mark.parametrize("mutate",[
    lambda x:x["nftables"][2]["chain"].update(policy="accept"),
    lambda x:x["nftables"].append(rule("output",m("meta.oifname","eth0"))),
    lambda x:x["nftables"].append(rule("output",m("ip.daddr","169.254.169.254"),m("tcp.dport",443))),
    lambda x:x["nftables"].append({"chain":{"family":"inet","table":"apaa","name":"extra","type":"filter","hook":"forward","prio":0,"policy":"drop"}}),
    lambda x:x["nftables"].append(rule("output",m("ip.daddr","1.1.1.1"),m("tcp.dport",443))),
])
def test_rejects_policy_expansion_or_chain_change(mutate):
    data=fixture(); mutate(data)
    with pytest.raises(NftablesAttestationError):
        attest_nftables_json(json.dumps(data),policy())

def test_rejects_nonterminal_or_unconditional_accept():
    data=fixture()
    data["nftables"][4]["rule"]["expr"]=[{"accept":None},m("meta.iifname","lo")]
    with pytest.raises(NftablesAttestationError):
        attest_nftables_json(json.dumps(data),policy())

def test_rejects_unknown_expression_even_when_accept_is_terminal():
    data=fixture()
    data["nftables"][4]["rule"]["expr"]=[{"counter":{"packets":1,"bytes":1}},{"accept":None}]
    with pytest.raises(NftablesAttestationError):
        attest_nftables_json(json.dumps(data),policy())

def test_rejects_wrong_proxy_family_or_port():
    data=fixture()
    data["nftables"][13]["rule"]["expr"][0]["match"]["right"]="198.18.0.9"
    with pytest.raises(NftablesAttestationError):
        attest_nftables_json(json.dumps(data),policy())

def test_rejects_malformed_and_oversized_documents():
    with pytest.raises(NftablesAttestationError):
        attest_nftables_json("{",policy())
    with pytest.raises(NftablesAttestationError):
        attest_nftables_json(" " * 1_000_001,policy())

def test_policy_rejects_private_or_noncanonical_proxy_addresses():
    for bad in ("127.0.0.1","10.0.0.1","169.254.1.1","::1","::ffff:127.0.0.1"):
        with pytest.raises(ValueError):
            NftablesPolicy((bad,),3128)


@pytest.mark.parametrize("bad_rule",[
    None,
    {"family":"inet","table":"apaa","chain":"output","expr":[{"accept":None}]},
    {"family":"inet","table":"apaa","chain":"output","expr":[
        {"match":{"op":"==","left":{"meta":{"key":"oifname","unexpected":"x"}},"right":"lo"}},
        {"accept":None},
    ]},
    {"family":"inet","table":"apaa","chain":"output","expr":[
        {"match":{"op":"==","left":{"meta":{"key":"oifname"}},"right":"lo","extra":True}},
        {"accept":None},
    ]},
])
def test_rejects_malformed_rule_or_unknown_match_fields(bad_rule):
    data=fixture()
    data["nftables"].append({"rule":bad_rule})
    with pytest.raises(NftablesAttestationError):
        attest_nftables_json(json.dumps(data),policy())


def test_requires_explicit_conntrack_new_match_for_new_proxy_connections():
    data=fixture()
    # The live nft JSON represents "ct state new" as a scalar equality.
    assert data["nftables"][14]["rule"]["expr"][2] == m("ct.state","new")
    result=attest_nftables_json(json.dumps(data),policy())
    assert result.accept_rule_count == 13
