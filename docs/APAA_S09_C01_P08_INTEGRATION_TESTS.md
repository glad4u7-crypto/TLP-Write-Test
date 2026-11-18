# APAA-S09-C01-P08 — Integration & Regression Test Plan

**Status:** Integration test suite committed; execution and exact-head CI evidence pending.

## Cross-module coverage

`tests/test_s09_c01_integration.py` connects the P02 navigation policy, P05 egress authorization contract, P06 context-level request routing and P07 Android runtime gate using injected DNS and fake browser surfaces.

Coverage includes:
- Destination authorization and connector peer-IP pin-set verification.
- Rejection when a connector reports an IP outside the authorized set.
- Context-level blocking of an untrusted subresource.
- Route cleanup after blocked requests and simulated browser failures.
- Initial allowlist rejection before route installation.
- Android/Termux browser capability denial.
- Explicitly limited interpretation of non-Android runtime detection.

## Regression scope

Existing focused suites remain in place:
- `tests/test_browser_navigation.py`
- `tests/test_egress_policy.py`
- `tests/test_browser_launch.py`
- `tests/test_safe_navigation.py`
- `tests/test_runtime_support.py`

The repository does not currently contain a separate redirect-policy module/test file; redirect-chain behavior is tested in `tests/test_browser_navigation.py`.

## Safety properties

- Tests inject a deterministic resolver and do not make DNS/network requests.
- Browser interactions use fake context/page/route objects; no real browser is launched.
- Android checks use supplied environment mappings; no device configuration is changed.
- No live browsing, login, form submission, payment, purchase, deployment, firewall/proxy modification, paid API or Auto-Run is performed.

## Verification status and exit criteria

- Test code is authored and committed; this is not proof that tests pass.
- Execute the full suite on the exact branch head with the repository's supported Python version and retain output/CI run identifiers.
- Resolve any failures before calling P08 verified.
- P08 does not close SEC-01/SEC-02: there is still no operational pinned-IP connector or OS-level egress sandbox. WebSocket and browser background traffic remain outside the demonstrated policy boundary.
- Android Playwright browser automation remains blocked pending physical-device qualification.

**Decision:** P08 test integration is implemented, but C01 remains not security-approved for live browsing.
