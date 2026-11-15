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
| CI baseline | Agent Foundation CI #647 / `43708893269`: 427 passed, audit and compile passed on design baseline `436a6c925d7a490f01104510ae8d0040815c44fa` | PASS (baseline) |
| CI baseline | Python Demo CI #738 / `43708893252`: 427 passed and demo smoke passed on design baseline `436a6c925d7a490f01104510ae8d0040815c44fa` | PASS (baseline) |
| Final record commit CI | Both existing workflows must pass on the final documentation record commit | PENDING |
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


## Design baseline CI evidence

- Agent Foundation CI #647 / `43708893269`: **PASS**, 427 tests passed in 16.37s; dependency audit, compileall and all post steps succeeded.
- Python Demo CI #738 / `43708893252`: **PASS**, 427 tests passed in 15.05s; demo smoke check and all post steps succeeded.
- Exact design baseline: `436a6c925d7a490f01104510ae8d0040815c44fa`.
- The final scope/matrix record commit is separately gated by both existing workflows; no additional workflow was created.

## P02 design checkpoint — exact-commit CI closure

**P02 design commit:** `08c107b59ebaa1f3cd4f0914fd939587f012b775`

| Workflow | Run | Exact commit | Result | Verified steps |
|---|---:|---|---|---|
| Agent Foundation CI | [43711409883](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43711409883) | `08c107b59ebaa1f3cd4f0914fd939587f012b775` | PASS | dependency install, pip-audit, compile, foundation tests, post steps |
| Python Demo CI | [43711409874](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43711409874) | `08c107b59ebaa1f3cd4f0914fd939587f012b775` | PASS | dependency install, test suite, demo smoke, post steps |

Both workflow runs were re-fetched after completion. Each job and every listed step completed with `success`. These results verify the repository's current foundation/demo checks on the P02 design commit; they do **not** verify browser-specific security behavior.

| Browser security area | Current evidence status |
|---|---|
| URL/origin/redirect/DNS/SSRF policy tests | DESIGN — not implemented or executed |
| Read-only behavior and prompt-injection fixtures | DESIGN — not implemented or executed |
| Worker/container isolation and enforced egress | DESIGN — operational proof not available |
| Approval binding, tenant isolation and ephemeral cleanup | DESIGN — not implemented or executed |
| Android real-device usability | NOT STARTED |
| Browser runtime | NOT AUTHORIZED / NOT INSTALLED |

**P02 disposition:** DESIGN PACKAGE + EXISTING CI BASELINE VERIFIED. No browser runtime, browser dependency, worker, handler or live website operation was introduced. Implementation remains a separate approval gate. PR #5 remains Open + Draft + unmerged.


## P03 implementation checkpoint — offline browser security policy

**P03 scope:** `core/browser_security.py` + `tests/test_browser_security.py`  
**Documentation:** `docs/APAA_S07_BROWSER_SECURITY_POLICY_P03.md`

| Area | P03 evidence | Status |
|---|---|---|
| HTTPS URL parsing and canonicalization | Deterministic URL/IDNA/authority/port validation tests | IMPLEMENTED — CI PENDING |
| Exact-origin allowlist | Scheme/host/effective-port exact match; wildcard/suffix/subdomain bypass rejection tests | IMPLEMENTED — CI PENDING |
| Local/private/reserved IP rejection | IPv4/IPv6 loopback, private, link-local, metadata and special-use fixtures | IMPLEMENTED — CI PENDING |
| DNS/SSRF answer policy | Injected resolver; empty, malformed, mixed and non-global answer rejection; resolver failure closed | IMPLEMENTED — OFFLINE ONLY |
| Redirect validation | Relative redirects supported; cross-origin, unsafe protocol and private destination rejected | IMPLEMENTED — CI PENDING |
| Typed job envelope | Closed schema, immutable result, ID/action/expiry/origin/resource-limit validation | IMPLEMENTED — CI PENDING |
| Prohibited browser actions | Click/fill/type/submit/eval/download/upload/clipboard/shell/payment/trading/unknown rejected | IMPLEMENTED — CI PENDING |
| No implicit network activity | Test patches socket.getaddrinfo to fail; validation succeeds without calling it | IMPLEMENTED — CI PENDING |
| Connection-time egress / DNS rebinding | Requires isolated worker + fail-closed proxy/firewall + connection pinning | NOT IMPLEMENTED |
| Browser runtime / handler registration | No browser dependency, worker, handler or ExecutionGateway registration | NOT IMPLEMENTED |
| Android device validation | No real-device browser UX or native device control | NOT STARTED |
| Existing CI workflows | Both existing workflows must pass on the exact final P03 record commit | PENDING |

### P03 interpretation and exit gate

P03 adds offline policy primitives and deterministic tests only. It does not establish an enforceable network boundary, prove SSRF protection at connection time, or authorize browser execution. DNS resolution is injected in tests and is never performed implicitly. Deployment must later enforce DNS/address validation at connection time and block direct worker egress.

**P03 disposition:** IMPLEMENTATION ADDED; final verification remains pending until the full pytest suite and both existing CI workflows complete successfully on the exact final commit. PR #5 remains Open + Draft + unmerged.


### P03 final implementation snapshot

- Final P03 code/test snapshot: `925a6db8b58dc2944c05ec503f50f2b1222c2ce3`.
- Includes a follow-up hardening pass for legacy numeric IPv4 spellings (shortened dotted, octal-like and hexadecimal forms) and multicast/non-unicast destinations.
- The exact-commit workflow lookup returned no workflow-run records for this snapshot. Therefore **pytest and both CI workflows are NOT VERIFIED for P03**; no PASS status is claimed.
- The regression suite is committed but remains pending execution in the repository's existing CI. The CI configuration was not changed and no additional workflow was created.
