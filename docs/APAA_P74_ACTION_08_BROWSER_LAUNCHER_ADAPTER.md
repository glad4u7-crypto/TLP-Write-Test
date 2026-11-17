# APAA P74 Action 08 — Browser Launcher Adapter

**Status:** Adapter and deterministic tests committed; CI verification pending.  
**Branch:** `feature/apaa-s09-c01-p01-browser-launch`

## Previous-action audit

- The numeric pinned-IP connector dials only validated numeric addresses and checks the actual peer IP and port.
- IPv4 and IPv6 are supported. A failed attempt may move only to another already-authorized pin.
- DNS is not re-resolved by the connector. A new navigation must obtain a new authorization result; stale pins must not be carried into a later navigation.
- The CONNECT proxy authorizes the requested host before dialing and uses the pinned connector.
- The proxy is only a tunnel. It does not itself inspect TLS certificates; browser TLS verification is required.
- Redirect policy validates each supplied hop, but live browser redirect integration remains outstanding.
- OS/container egress denial is an external deployment control. Python code cannot prove or install it.

## Adapter added

- `core/browser_launcher.py`
- `tests/test_browser_launcher.py`

The adapter requires a fresh pre-start runtime attestation, bound to the exact immutable worker launch-spec digest. It rejects missing, unknown, stale, unsafe, or already-running evidence before invoking the browser engine.

Chromium launch uses only the attested proxy endpoint, sandboxing, and a fixed argument list. The context explicitly sets `ignore_https_errors=False`, blocks service workers, and disables downloads. No caller-supplied executable path, arbitrary arguments, certificate-ignore flag, persistent profile, or direct-network fallback is exposed.

If launch or context creation fails, the adapter closes any partially created browser and raises a fail-closed error. Session cleanup is idempotent.

## Test coverage authored

- Approved attestation launches through the exact proxy.
- TLS verification remains enabled in the browser context.
- Unsafe firewall, direct-egress, DNS-egress, worker-state, and missing-field evidence blocks launch before browser startup.
- Stale attestation blocks launch.
- Context creation failure closes the browser.
- Browser launch failure has no direct fallback.
- Session close is idempotent.

## Remaining acceptance work

- [ ] CI test suite passes on the latest commit.
- [ ] Execute Chromium integration tests with a locally generated trusted test CA.
- [ ] Prove hostname mismatch and expired certificate rejection in a real browser.
- [ ] Test IPv4/IPv6 fallback against a controlled local test endpoint.
- [ ] Test redirect chains and loops in a real browser through the mandatory proxy.
- [ ] Verify DNS answer changes cause fresh authorization and no stale-pin reuse.
- [ ] Independently prove OS/container direct-egress denial.
- [ ] Independent security review.

**Safety state:** No browser session has been launched. No live browsing, login, form submission, downloads, purchases, payments, trading, money movement, paid services, Auto-Run, deployment, or firewall changes are enabled.
