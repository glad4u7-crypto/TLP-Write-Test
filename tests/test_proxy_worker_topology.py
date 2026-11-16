import pytest
from core.proxy_worker_topology import ProxyWorkerTopology, ProxyWorkerTopologyError

def topology(**overrides):
    values = dict(network_name="apaa-worker-net", subnet="172.30.0.0/28",
                  proxy_address="172.30.0.2", worker_address="172.30.0.3", proxy_port=3128)
    values.update(overrides)
    return ProxyWorkerTopology.build(**values)

def test_topology_produces_fixed_worker_proxy_endpoint_and_invariants():
    item = topology()
    assert item.worker_proxy_url == "http://172.30.0.2:3128"
    assert item.expected_proxy_addresses == ("172.30.0.2",)
    assert len(item.deployment_invariants()) >= 8
    item.validate_worker_proxy_url(item.worker_proxy_url)

@pytest.mark.parametrize("overrides", [
    {"network_name": "bridge"}, {"subnet": "0.0.0.0/0"},
    {"subnet": "192.0.2.0/28"},
    {"proxy_address": "172.30.1.2"}, {"proxy_address": "172.30.0.3"},
    {"worker_address": "172.30.0.2"}, {"proxy_address": "172.30.0.1"},
    {"proxy_port": 80}, {"proxy_port": True}, {"proxy_address": "2001:db8::2"},
])
def test_rejects_non_private_or_ambiguous_topology(overrides):
    with pytest.raises(ProxyWorkerTopologyError):
        topology(**overrides)

@pytest.mark.parametrize("endpoint", [
    "http://127.0.0.1:3128", "http://localhost:3128",
    "http://172.30.0.4:3128", "https://172.30.0.2:3128",
    "http://172.30.0.2:8080", "http://user@172.30.0.2:3128",
    "http://172.30.0.2:3128/path",
    "http://172.30.0.2:03128", "http://172.30.0.2:3128?",
    "http://172.30.0.2:3128#", "http://172.30.0.2:3128/",
    " http://172.30.0.2:3128", "http://172.30.0.2:3128 ",
])
def test_rejects_proxy_url_not_equal_to_private_proxy_endpoint(endpoint):
    with pytest.raises(ProxyWorkerTopologyError):
        topology().validate_worker_proxy_url(endpoint)
