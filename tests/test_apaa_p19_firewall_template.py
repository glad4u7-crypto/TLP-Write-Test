from pathlib import Path

def test_worker_firewall_template_is_scoped_and_fail_closed():
    path = Path(__file__).resolve().parents[1] / "infra" / "nftables" / "apaa-worker-egress.nft"
    text = path.read_text(encoding="utf-8")
    assert "table inet apaa_worker" in text
    assert "chain output" in text and "policy drop" in text
    assert "ip daddr $APAA_PROXY_IPV4 tcp dport $APAA_PROXY_TCP_PORT accept" in text
    assert "chain input" in text and "ct state established,related accept" in text
    assert "flush ruleset" not in text
    assert "0.0.0.0/0" not in text
    assert "ip6" not in text
