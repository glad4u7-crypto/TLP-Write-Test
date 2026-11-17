# APAA BCS-05 — Security Qualification

Status: IN PROGRESS. This document is a qualification plan, not a claim that qualification has passed.

## Safety boundary

- Public Live Browsing remains DISABLED.
- Browser/Worker dispatch remains DISABLED; Auto-Run remains OFF.
- All Chromium and hostile-network tests MUST run in a disposable, isolated Linux runner.
- Never run namespace, nftables, route, cgroup, or firewall mutation on a developer workstation or non-disposable host.
- No payment, purchase, trading, money movement, production credentials, or real user data.
- The real-host workflow is manually gated and must not be enabled by an ordinary push or pull request.
- Do not merge or deploy based solely on unit tests or a local Chromium fixture.

## Qualification layers

### Q1 — Real Chromium browser-surface tests

Run a pinned Playwright/Chromium build against loopback-only fixtures with no external network access. Record browser version, Playwright version, OS image digest, test commit SHA, and machine-readable results.

| Surface | Required positive case | Required negative case |
|---|---|---|
| Redirect | Same approved origin redirect completes | Cross-origin redirect is blocked before navigation/action |
| Subresource | Approved same-origin script/image/style loads | Unapproved cross-origin subresource is blocked |
| Popup | Explicitly permitted same-origin popup is observed and constrained | Unapproved popup is denied and cannot navigate elsewhere |
| Iframe | Approved same-origin frame is constrained to the same policy | Cross-origin frame cannot access or escape the policy boundary |
| WebSocket | Explicitly approved endpoint can connect in fixture | Unapproved host/port and direct socket path are denied |
| TLS | Trusted test CA succeeds; hostname mismatch and expired certificate fail | No ignore-certificate-errors or insecure TLS fallback |

These tests establish Chromium behavior only. They do NOT establish OCI isolation or host network enforcement.

### Q2 — OCI and host network boundary

Use only the existing explicitly gated real-host qualification harness on a disposable Linux runner. Verify the actual container, namespaces, cgroup, seccomp, nftables, proxy pinning, and host packet capture.

Required negative probes:
- direct IPv4 TCP and UDP;
- direct IPv6 TCP and UDP;
- UDP/443 (QUIC);
- direct DNS over UDP and TCP;
- loopback, link-local, private, metadata, and unapproved public destinations;
- IPv4-mapped IPv6 and IPv6 scope edge cases;
- proxy DNS rebinding / answer-set changes;
- proxy peer-IP mismatch and TLS hostname mismatch.

Every negative probe must demonstrate denial at the intended enforcement boundary and include evidence artifacts. A test that merely observes a browser error is insufficient.

### Q3 — Lifecycle and evidence

- Worker crash, timeout, cancellation, orphan detection, cleanup, and restart recovery.
- Verify no worker is reported closed until OS process exit and ephemeral-storage cleanup are confirmed.
- Verify audit-store failure blocks dispatch durably.
- Verify logs/artifacts contain no cookies, authorization headers, credentials, page bodies, raw URLs with query values, or secrets.
- Evidence must be tied to the exact tested commit SHA and must not contain secrets.

### Q4 — Exact-head CI and independent review

- Required CI must run against the exact PR head SHA; record SHA and run URL.
- Keep ordinary unit/policy CI distinct from gated disposable-host qualification.
- A green unit-test suite is not a real-host qualification pass.
- Obtain an independent security review covering threat model, policy bypasses, evidence integrity, and cleanup.
- Track each finding to a fix and retest before qualification is accepted.

## Release gates

BCS-05 is complete only when Q1, Q2, Q3, and Q4 all have reproducible evidence, exact-head CI is green, independent review findings are resolved or explicitly accepted by the Owner, and the Owner approves the release decision.

Until then: NOT QUALIFIED. Dispatch remains disabled.
