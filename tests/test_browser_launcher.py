import pytest
from core.browser_isolation import validate_worker_profile
from core.browser_runtime import build_worker_launch_spec
from core.browser_launcher import BrowserLaunchError, launch_chromium

PROXY = "http://egress-proxy.internal:3128"

def make_spec():
    profile = validate_worker_profile({
        "schema_version": 1, "uid": 10001, "gid": 10001,
        "privileged": False, "read_only_root": True, "no_new_privileges": True,
        "capabilities_drop": ["ALL"], "host_network": False, "host_pid": False,
        "host_ipc": False, "host_mounts": [], "secret_mounts": [],
        "writable_mounts": ["/tmp/job"], "browser_profile_persistence": False,
        "cdp_exposed": False, "direct_egress": False, "proxy_only_egress": True,
        "dns_via_proxy_only": True, "egress_proxy": PROXY,
        "memory_limit_bytes": 512 * 1024 * 1024, "cpu_limit_millis": 1000,
        "pids_limit": 64, "job_timeout_seconds": 30,
    })
    return build_worker_launch_spec(profile)

def make_attestation(spec, **overrides):
    raw = {
        "schema_version": 1, "launch_spec_digest": spec.digest,
        "runtime_id": "runtime-001", "worker_id": "worker-001",
        "image_digest": "sha256:" + "a" * 64, "attestor_id": "host-inspector-001",
        "evidence_digest": "b" * 64, "observed_at": 1000, "state": "created",
        "process_started": False, "runtime_config_verified": True,
        "host_firewall_verified": True, "uid": spec.uid, "gid": spec.gid,
        "privileged": False, "read_only_root": True, "no_new_privileges": True,
        "capabilities_effective": [], "namespaces": list(spec.namespaces),
        "host_mounts": [], "secret_mounts": [], "writable_mounts": list(spec.writable_mounts),
        "browser_profile_persistence": False, "cdp_exposed": False, "direct_egress": False,
        "proxy_only_egress": True, "dns_via_proxy_only": True, "egress_proxy": spec.egress_proxy,
        "memory_limit_bytes": spec.memory_limit_bytes, "cpu_limit_millis": spec.cpu_limit_millis,
        "pids_limit": spec.pids_limit, "job_timeout_seconds": spec.job_timeout_seconds,
        "seccomp_enforced": True, "network_namespace_isolated": True,
        "firewall_default_deny": True, "egress_allowed": ["egress-proxy.internal:3128"],
        "direct_dns_egress_blocked": True, "proxy_side_dns_only": True,
    }
    raw.update(overrides)
    return raw

class FakeContext:
    def __init__(self): self.close_calls = 0
    def close(self): self.close_calls += 1

class FakeBrowser:
    def __init__(self, fail_context=False):
        self.context = FakeContext()
        self.fail_context = fail_context
        self.close_calls = 0
        self.context_options = None
    def new_context(self, **kwargs):
        self.context_options = kwargs
        if self.fail_context: raise RuntimeError("context creation failed")
        return self.context
    def close(self): self.close_calls += 1

class FakeBrowserType:
    def __init__(self, browser=None, fail_launch=False):
        self.browser = browser or FakeBrowser()
        self.fail_launch = fail_launch
        self.launch_options = None
        self.calls = 0
    def launch(self, **kwargs):
        self.calls += 1
        self.launch_options = kwargs
        if self.fail_launch: raise RuntimeError("launch failed")
        return self.browser

def test_launch_uses_attested_proxy_and_enforces_tls_verification():
    spec = make_spec()
    browser_type = FakeBrowserType()
    session = launch_chromium(browser_type, spec, make_attestation(spec), now=1000)
    assert browser_type.calls == 1
    assert browser_type.launch_options["proxy"] == {"server": PROXY}
    assert browser_type.launch_options["headless"] is True
    assert browser_type.launch_options["chromium_sandbox"] is True
    assert "--proxy-bypass-list=<-loopback>" in browser_type.launch_options["args"]
    assert browser_type.browser.context_options["ignore_https_errors"] is False
    assert browser_type.browser.context_options["accept_downloads"] is False
    assert browser_type.browser.context_options["service_workers"] == "block"
    session.close()
    session.close()
    assert browser_type.browser.context.close_calls == 1
    assert browser_type.browser.close_calls == 1

@pytest.mark.parametrize("field,value", [
    ("host_firewall_verified", False), ("direct_egress", True),
    ("firewall_default_deny", False), ("direct_dns_egress_blocked", False),
    ("proxy_side_dns_only", False), ("process_started", True), ("state", "running"),
])
def test_unsafe_runtime_evidence_blocks_launch(field, value):
    spec = make_spec()
    browser_type = FakeBrowserType()
    with pytest.raises(BrowserLaunchError):
        launch_chromium(browser_type, spec, make_attestation(spec, **{field: value}), now=1000)
    assert browser_type.calls == 0

def test_missing_attestation_field_blocks_launch():
    spec = make_spec()
    browser_type = FakeBrowserType()
    raw = make_attestation(spec)
    raw.pop("host_firewall_verified")
    with pytest.raises(BrowserLaunchError):
        launch_chromium(browser_type, spec, raw, now=1000)
    assert browser_type.calls == 0

def test_stale_attestation_blocks_launch():
    spec = make_spec()
    browser_type = FakeBrowserType()
    with pytest.raises(BrowserLaunchError):
        launch_chromium(browser_type, spec, make_attestation(spec), now=2000)
    assert browser_type.calls == 0

def test_context_creation_failure_closes_browser_and_does_not_fallback():
    spec = make_spec()
    browser = FakeBrowser(fail_context=True)
    browser_type = FakeBrowserType(browser=browser)
    with pytest.raises(BrowserLaunchError):
        launch_chromium(browser_type, spec, make_attestation(spec), now=1000)
    assert browser.close_calls == 1
    assert browser_type.calls == 1

def test_browser_launch_failure_does_not_attempt_direct_fallback():
    spec = make_spec()
    browser_type = FakeBrowserType(fail_launch=True)
    with pytest.raises(BrowserLaunchError):
        launch_chromium(browser_type, spec, make_attestation(spec), now=1000)
    assert browser_type.calls == 1
