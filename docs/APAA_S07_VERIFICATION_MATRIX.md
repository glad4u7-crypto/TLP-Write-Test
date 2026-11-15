# APAA S07 — Browser Automation Verification Matrix

**Checkpoint:** APAA-S07-C01-P01  
**Status:** DESIGN CHECKLIST ONLY — NO BROWSER RUNTIME / NO TEST PASS CLAIMED

| Area | Required future evidence | Status |
|---|---|---|
| URL parsing and canonicalization | Fuzz tests for IDN, userinfo, IPv6, encoded hosts, ports and malformed URLs | DESIGN |
| Exact-origin allowlist | Unit tests for scheme/host/port exact match; suffix and wildcard bypass rejection | DESIGN |
| Redirect handling | Multi-hop redirect tests; every hop revalidated | DESIGN |
| DNS/SSRF protection | DNS rebinding, mixed answers, private/reserved IPv4/IPv6 and metadata endpoint tests | DESIGN |
| Network egress | Packet-level proof that worker cannot directly reach arbitrary internet, localhost or private networks | DESIGN |
| Prompt injection | Malicious page corpus; secret canaries remain undisclosed; page instructions never alter policy | DESIGN |
| Read-only behavior | Verify no form submission, upload, download, clipboard write or state mutation | DESIGN |
| Approval binding | Exact origin/action/target/payload/user/session/job binding, expiry and one-time consumption | DESIGN |
| TOCTOU | Page/DOM/target changes after preview invalidate approval | DESIGN |
| Tenant isolation | Concurrent identities cannot access each other's job, cookies, result or audit | DESIGN |
| Ephemeral context | Fresh context per job; no default-profile access; cleanup on completion/cancel/failure | DESIGN |
| Worker isolation | Separate unprivileged process/container; no host mounts, secrets or CDP exposure | DESIGN |
| Resource limits | Time, memory, CPU, request, response, page and popup limits | DESIGN |
| Secret-safe audit | Canary credentials absent from logs; durable intent before mutation | DESIGN |
| Failure handling | Fail closed on audit, policy, auth, worker or egress failure | DESIGN |
| Prohibited action boundary | Payment/purchase/checkout/trading/money movement always denied | DESIGN |
| Typed browser job/action/result contract | Schema strictness, unknown action rejection, approval digest binding, job expiry and replay tests | DESIGN |
| Mobile approval UX | Exact origin/action preview, no preselected consent, cancellation and stale-state invalidation | DESIGN |
| CI | Existing Agent Foundation CI and Python Demo CI on exact final documentation commit | PENDING |
| Real deployment review | Independent review of browser binary, container, OS identity, egress firewall and incident handling | NOT STARTED |
| Android compatibility | Browser-based mobile UI and real-device usability test; no native control claim | NOT STARTED |

## Exit criteria before any implementation proposal

- Architecture and threat model reviewed.
- Permission matrix explicitly accepted.
- Worker isolation and egress topology selected and testable.
- Origin and approval UX specified.
- No prohibited action can reach a handler.
- Automated test plan and independent operational evidence plan agreed.
- Separate user authorization for a narrowly scoped implementation checkpoint.

**Important:** S07-C01-P01 does not pass browser security tests because no browser runtime exists yet.


## Additional design deliverables

- `APAA_S07_BROWSER_ACTION_CONTRACT.md`: job envelope, closed action types, locator rules, approval digest and worker result contract.
- `APAA_S07_MOBILE_APPROVAL_UX.md`: mobile-first review card, one-action approval, cancellation, accessibility and Android boundary.

These are specifications only. No schema validator, UI screen or browser worker is implemented.
