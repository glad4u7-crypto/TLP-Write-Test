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
| HTTPS URL parsing and canonicalization | Deterministic URL/IDNA/authority/port validation tests | IMPLEMENTED — PASS |
| Exact-origin allowlist | Scheme/host/effective-port exact match; wildcard/suffix/subdomain bypass rejection tests | IMPLEMENTED — PASS |
| Local/private/reserved IP rejection | IPv4/IPv6 loopback, private, link-local, metadata and special-use fixtures | IMPLEMENTED — PASS |
| DNS/SSRF answer policy | Injected resolver; empty, malformed, mixed and non-global answer rejection; resolver failure closed | IMPLEMENTED — OFFLINE ONLY |
| Redirect validation | Relative redirects supported; cross-origin, unsafe protocol and private destination rejected | IMPLEMENTED — PASS |
| Typed job envelope | Closed schema, immutable result, ID/action/expiry/origin/resource-limit validation | IMPLEMENTED — PASS |
| Prohibited browser actions | Click/fill/type/submit/eval/download/upload/clipboard/shell/payment/trading/unknown rejected | IMPLEMENTED — PASS |
| No implicit network activity | Test patches socket.getaddrinfo to fail; validation succeeds without calling it | IMPLEMENTED — PASS |
| Connection-time egress / DNS rebinding | Requires isolated worker + fail-closed proxy/firewall + connection pinning | NOT IMPLEMENTED |
| Browser runtime / handler registration | No browser dependency, worker, handler or ExecutionGateway registration | NOT IMPLEMENTED |
| Android device validation | No real-device browser UX or native device control | NOT STARTED |
| Existing CI workflows | Both existing workflows passed on the exact P03 verification-record commit | PASS |

### P03 interpretation and exit gate

P03 adds offline policy primitives and deterministic tests only. It does not establish an enforceable network boundary, prove SSRF protection at connection time, or authorize browser execution. DNS resolution is injected in tests and is never performed implicitly. Deployment must later enforce DNS/address validation at connection time and block direct worker egress.

**P03 disposition:** IMPLEMENTATION ADDED; the full pytest suite and both existing CI workflows passed on the exact P03 verification-record commit listed below. PR #5 remains Open + Draft + unmerged.


### P03 final implementation snapshot

- Final P03 code/test snapshot: `925a6db8b58dc2944c05ec503f50f2b1222c2ce3`.
- Includes a follow-up hardening pass for legacy numeric IPv4 spellings (shortened dotted, octal-like and hexadecimal forms) and multicast/non-unicast destinations.
- The initial exact code snapshot had no workflow records at first lookup; both existing workflows were subsequently triggered and verified on the exact P03 verification-record commit below.
- The Python Demo CI and Agent Foundation CI each executed the full pytest suite successfully. The CI configuration was not changed and no additional workflow was created.


### P03 exact verification-record CI — PASS

**Verification Matrix commit:** `a6cb05f9eec0f316f4d065c4f0758b02aadb7557`

| Existing workflow | Run | Result | Exact evidence |
|---|---:|---|---|
| Agent Foundation CI | [43712348056](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43712348056) | PASS | 521 passed in 14.89s; dependency install, pip-audit (no known vulnerabilities found), compileall, foundation tests and all post steps succeeded |
| Python Demo CI | [43712348046](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43712348046) | PASS | 521 passed in 14.18s; dependency install, full test suite, demo smoke and all post steps succeeded |

Both workflow jobs and every listed step were re-fetched after completion and reported `success`. These results verify the offline policy code and repository test suite only. They do not establish browser runtime safety, live SSRF resistance, worker isolation or connection-time egress enforcement.


## P04 implementation checkpoint — worker isolation and egress policy harness

**Checkpoint:** `APAA-S07-C01-P04`  
**Implementation:** `core/browser_isolation.py`, `core/browser_egress.py`  
**Tests:** `tests/test_browser_isolation.py`  
**Detailed contract:** `docs/APAA_S07_ISOLATED_WORKER_EGRESS_P04.md`

| Area | P04 evidence | Status |
|---|---|---|
| Worker launch profile schema | Closed schema; unknown/missing keys rejected | IMPLEMENTED — PASS |
| Non-root identity | UID/GID must be non-zero and bounded | IMPLEMENTED — PASS |
| Container privilege / namespaces | Privileged, host network/PID/IPC all denied | IMPLEMENTED — PASS |
| Filesystem boundary | Read-only root required; host/secret mounts denied; writable paths restricted to ephemeral /tmp children | IMPLEMENTED — PASS |
| Linux capabilities | Drop ALL required | IMPLEMENTED — PASS |
| Browser profile / CDP | Persistent profile and exposed CDP prohibited | IMPLEMENTED — PASS |
| Network egress manifest | Direct egress denied; proxy-only and proxy-side DNS required | IMPLEMENTED — PASS |
| Proxy endpoint | Explicit named internal .internal endpoint required | IMPLEMENTED — PASS |
| Resource bounds | Memory, CPU, PID and job timeout ranges validated | IMPLEMENTED — PASS |
| Proxy CONNECT decision | HTTPS/TCP 443 and exact approved origin only | IMPLEMENTED — PASS |
| Connection-time address set | Injected resolver answers checked for public-unicast and returned for IP pinning | IMPLEMENTED — OFFLINE ONLY |
| DNS rebinding / TOCTOU | Pure policy provides validated address set; real proxy must connect to that exact pinned IP without re-resolving | DEPLOYMENT NOT IMPLEMENTED |
| Worker network namespace / firewall | No container, namespace, firewall or proxy service created | NOT IMPLEMENTED |
| Browser runtime / handler | No Playwright/Chromium, worker process or ExecutionGateway registration | NOT IMPLEMENTED |
| Existing CI workflows | Both existing workflows passed on the exact P04 verification-record commit | PASS |

### P04 interpretation and exit gate

P04 adds deterministic validators and regression tests only. A valid manifest is not an enforced sandbox. A returned address set is not a live proxy connection. Actual isolation requires a separately implemented deployment adapter, effective runtime inspection, firewall enforcement proving proxy-only egress, packet-level DNS leak tests, proxy connection pinning tests, TLS validation and independent security review. Browser execution remains disabled.

**P04 disposition:** OFFLINE POLICY + VERIFICATION HARNESS COMPLETE; full pytest and both existing CI workflows passed on the exact P04 verification-record commit listed below. No new workflow was added. PR #5 remains Open + Draft + unmerged.


### P04 exact verification-record CI — PASS

**Verification Matrix commit:** `91951a956e576b6db17d015f11919bda03d83315`

| Existing workflow | Run | Result | Exact evidence |
|---|---:|---|---|
| Agent Foundation CI | [43713013008](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43713013008) | PASS | 569 passed in 15.25s; dependency install, pip-audit (no known vulnerabilities found), compileall, foundation tests and all post steps succeeded |
| Python Demo CI | [43713013015](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43713013015) | PASS | 569 passed in 14.71s; dependency install, full test suite, demo smoke and all post steps succeeded |

Both workflow jobs and every listed step were re-fetched after completion and reported `success`. The two workflows ran on the exact Verification Matrix commit above.

**CI correction record:** Early intermediate runs caught an omitted `ipaddress` import and an overly strict `/tmp` path check. Both were corrected before the final verification-record commit; the final full suite passed in both workflows.

These CI results verify offline validators and deterministic tests only. They do not prove an actual container sandbox, firewall enforcement, proxy operation, packet-level DNS leak prevention, IP pinning in a live socket, browser runtime safety or production readiness.



## P05 implementation checkpoint — worker launch contract and runtime attestation

**Checkpoint:** `APAA-S07-C01-P05`  
**Implementation:** `core/browser_runtime.py`  
**Tests:** `tests/test_browser_runtime.py`  
**Detailed contract:** `docs/APAA_S07_WORKER_RUNTIME_ATTESTATION_P05.md`

| Area | P05 evidence | Status |
|---|---|---|
| P04 profile revalidation | Revalidates the closed P04 profile before creating a launch contract | IMPLEMENTED — TESTED |
| Immutable launch contract | Frozen launch spec with stable SHA-256 digest and exact namespace/resource requirements | IMPLEMENTED — TESTED |
| Runtime image identity | Requires immutable `sha256:<64 hex>` image digest | IMPLEMENTED — TESTED |
| Attestation schema | Closed schema; unknown/missing fields rejected | IMPLEMENTED — TESTED |
| Launch-spec binding | Evidence digest must refer to exact launch-spec digest | IMPLEMENTED — TESTED |
| Runtime identity | Runtime, worker and attestor identifiers required | IMPLEMENTED — TESTED |
| Pre-start state | Requires runtime state `created` and process_started=false | IMPLEMENTED — TESTED |
| Effective privilege checks | UID/GID, empty effective capabilities, no privileged mode, no host/secret mounts, no persistent profile/CDP | IMPLEMENTED — TESTED |
| Kernel/runtime isolation evidence | Requires namespaces, seccomp and no-new-privileges attestation | CONTRACT ONLY — INSPECTOR NOT IMPLEMENTED |
| Network enforcement evidence | Requires isolated network namespace, host default-deny firewall, proxy-only egress and direct DNS block | CONTRACT ONLY — FIREWALL NOT DEPLOYED |
| Freshness | Rejects stale/future timestamps; default 60-second window | IMPLEMENTED — TESTED |
| Resource enforcement | Exact memory/CPU/PID/job-timeout comparison | IMPLEMENTED — TESTED |
| Trusted inspector authenticity | Evidence digest is not a signature; external authenticated inspector still required | NOT IMPLEMENTED |
| Runtime adapter / OCI deployment | Launch spec is inert data; no container API or process start | NOT IMPLEMENTED |
| Browser runtime / ExecutionGateway handler | No browser dependency, worker process or handler registration | NOT IMPLEMENTED |
| Existing CI workflows | Final exact-commit runs required on both existing workflows | PENDING |

### P05 interpretation and exit gate

P05 adds an inert launch contract and an offline validator for externally supplied pre-start observations. It does not create or start a container, inspect effective kernel state, authenticate the inspector, deploy a firewall/proxy or establish real network isolation. The attestation must come from a trusted host-side inspector and must be independently reviewed before any future start operation. Browser execution remains disabled.

**P05 code + matrix snapshot:** `2cc4729b11d63edd6bc6a03465945b189d104e2e`

| Existing workflow | Run | Result | Exact evidence |
|---|---:|---|---|
| Agent Foundation CI | [43713569838](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43713569838) | PASS | 615 passed in 16.71s; pip-audit reported no known vulnerabilities; compileall, tests and all job steps succeeded |
| Python Demo CI | [43713569733](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43713569733) | PASS | 615 passed in 16.37s; demo smoke printed the expected `Hello TradeLab Pro`; all job steps succeeded |

Both runs executed on the exact P05 code + matrix snapshot above. Their jobs and every listed step were re-fetched after completion and reported success. These results verify offline launch-contract and attestation logic only.

**P05 disposition:** IMPLEMENTATION ADDED; both existing CI workflows passed on the exact P05 code + matrix snapshot. The final documentation-record commit `3eeaedf3bdb339c234a91c413975446bf86170cd` was also checked by both existing workflows: Agent Foundation CI run 43713691718 (615 passed; pip-audit and compileall passed) and Python Demo CI run 43713691714 (615 passed; demo smoke passed). Both jobs and all steps completed successfully. No new workflow created. PR #5 remains Open + Draft + unmerged. No merge or deployment.



## P06 implementation checkpoint — signed trusted-inspector and host-firewall evidence

**Checkpoint:** `APAA-S07-C01-P06`  
**Implementation:** `core/browser_inspector.py`  
**Tests:** `tests/test_browser_inspector.py`  
**Detailed contract:** `docs/APAA_S07_TRUSTED_INSPECTOR_FIREWALL_P06.md`  
**Dependency:** `cryptography>=50,<51` for Ed25519 verification

| Area | P06 evidence | Status |
|---|---|---|
| Signed evidence envelope | Closed canonical JSON envelope; Ed25519 signature over schema, key ID and complete payload | IMPLEMENTED — OFFLINE TESTED |
| Trusted key lookup | Requires out-of-band 32-byte public key keyed by trusted key ID | VERIFIER IMPLEMENTED; KEY PROVISIONING EXTERNAL |
| Challenge binding | Signed 256-bit challenge must exactly match caller challenge | IMPLEMENTED — TESTED |
| Replay prevention | Stateless verifier; caller must issue unpredictable one-time challenge and atomically consume it | CONTROL-PLANE RESPONSIBILITY |
| P05 runtime attestation | Delegates to strict P05 validator after signature verification | IMPLEMENTED — TESTED |
| Host firewall evidence | Signed normalized nftables snapshot, runtime/worker identity and namespace inode | SCHEMA + VALIDATOR IMPLEMENTED |
| Default-deny egress | Requires default DROP and direct DNS blocked | IMPLEMENTED — OFFLINE TESTED |
| Exact proxy-only allowlist | Exact configured proxy IPs + TCP port only; rejects extra destinations, UDP, wildcard/CIDR and port drift | IMPLEMENTED — OFFLINE TESTED |
| Firewall ruleset integrity | Requires signed SHA-256 digest of effective ruleset | FORMAT VALIDATED; LIVE COLLECTION NOT IMPLEMENTED |
| Host-side inspector collector | No kernel/runtime/nftables reader or signing daemon | NOT IMPLEMENTED |
| Live firewall / packet proof | No nft command, packet capture, routing inspection or egress mutation | NOT IMPLEMENTED |
| Browser worker / runtime | No worker process or browser activation | NOT IMPLEMENTED |
| Existing CI workflows | Exact final P06 record commit must pass both existing workflows | PENDING |

### P06 interpretation and exit gate

P06 verifies that a trusted Ed25519 key signed a fresh, challenge-bound report whose normalized runtime and firewall fields satisfy the P05 launch contract and exact proxy-only firewall policy. It does not collect those facts itself. A valid signature is not proof that the collector is uncompromised or that the firewall is effective; the signer must be isolated from the worker and must read actual effective host state. One-time challenge generation/consumption, key provisioning/rotation and packet-level leak tests remain external requirements.

**P06 code-bearing snapshot:** `049629a3d9f55c4adc84d42947dd233e0b49a5a5`

| Existing workflow | Run | Result | Exact evidence |
|---|---:|---|---|
| Agent Foundation CI | [43715421652](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43715421652) | PASS | 639 passed in 12.79s; pip-audit reported no known vulnerabilities; compileall and all job steps succeeded |
| Python Demo CI | [43715421711](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43715421711) | PASS | 639 passed in 16.76s; demo smoke printed `Hello TradeLab Pro`; all job steps succeeded |

Both existing workflows passed on the exact P06 code-bearing snapshot. The initial P06 CI run exposed one test-call omission and seven dependency advisories against cryptography 47.0.0. The test invocation was corrected and the dependency floor raised to cryptography 50.0.0; the final code-bearing runs above passed and pip-audit reported no known vulnerabilities.

**P06 disposition:** SIGNED EVIDENCE VERIFIER + OFFLINE FIREWALL POLICY VALIDATOR IMPLEMENTED; exact code-bearing CI verified. The final documentation-record commit must also be checked by both workflows. No new workflow. No host collector, firewall mutation, browser runtime, worker process or browser handler. PR #5 remains Open + Draft + unmerged.


## P07 implementation checkpoint — read-only host snapshot collection + nftables parser

**Checkpoint:** APAA-S07-C01-P07  
**Implementation:** core/browser_nftables.py  
**Tests:** tests/test_browser_nftables.py  
**Detailed contract:** docs/APAA_S07_HOST_COLLECTOR_NFTABLES_P07.md  
**CI:** PASS on P07 code-bearing and verification-matrix commits

| Area | P07 evidence | Status |
|---|---|---|
| Host source interface | Injected HostSnapshotSource with runtime, namespace and nftables read methods; no default implementation | INTERFACE IMPLEMENTED |
| Runtime evidence | P05 pre-start attestation revalidated before signing | IMPLEMENTED — OFFLINE TESTED |
| Namespace identity | Runtime/worker binding, positive inode and bounded interface name | IMPLEMENTED — OFFLINE TESTED |
| nftables JSON parser | Narrow inet/filter/output subset; default DROP; exact TCP + IPv4 proxy destination + port | IMPLEMENTED — OFFLINE TESTED |
| Unknown rules / jumps / verdict maps | Unsupported output expressions rejected | IMPLEMENTED — OFFLINE TESTED |
| Ruleset integrity | SHA-256 over canonical JSON snapshot | IMPLEMENTED — OFFLINE TESTED |
| Evidence assembly | Normalizes P06 firewall schema, signs Ed25519 envelope and self-verifies via P06 | IMPLEMENTED — OFFLINE TESTED |
| Concrete host adapter / daemon | No runtime, kernel or nftables reader implementation supplied | NOT IMPLEMENTED |
| Kernel-state authenticity | Source must independently inspect effective state; protocol cannot attest source integrity | EXTERNAL TRUST REQUIREMENT |
| Packet-level / host forwarding proof | No packet capture, routing inspection, host forwarding chain or live egress test | NOT IMPLEMENTED |
| Browser runtime / worker | No worker, browser process or ExecutionGateway handler | NOT IMPLEMENTED |
| Existing CI workflows | Both existing workflows passed on the exact P07 verification-matrix commit | PASS |

### P07 interpretation and exit gate

P07 provides an injected collection protocol and a deliberately narrow nftables JSON parser, not a deployed host inspector. The parser rejects unknown output-chain syntax and accepts only an exact proxy allowlist under default DROP. It is not a general nftables interpreter and does not prove that the snapshot is the effective kernel ruleset or that no alternate route exists. A separately reviewed adapter must collect actual state, bind it to the worker namespace, protect the signing key, and support one-time challenge consumption. Host forwarding and packet-level DNS/egress proofs remain separate operational gates.

**P07 disposition:** SOURCE PROTOCOL + STRICT NFTABLES JSON PARSER + SIGNED EVIDENCE ASSEMBLER IMPLEMENTED; exact code and matrix CI verified. No host daemon, shell command, firewall mutation, live network operation, worker process or browser handler. No new workflow. PR #5 remains Open + Draft + unmerged.

### P07 exact CI verification

Code-bearing commit: dfb2ed9dec2875aaf8fbc750bde69acbbf5ef6cc  
Final verification-matrix commit: de4dcb54f02679421c5e07407ffd13b9cbbb1c2c

| Existing workflow | Code run | Matrix run | Result |
|---|---:|---:|---|
| Agent Foundation CI | [43715954496](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43715954496) | [43715966826](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43715966826) | PASS — 651 tests on each commit; pip-audit reported no known vulnerabilities; compileall and all steps succeeded |
| Python Demo CI | [43715954510](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43715954510) | [43715966694](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43715966694) | PASS — 651 tests on each commit; demo smoke printed Hello TradeLab Pro; all steps succeeded |

All four workflow jobs and every listed step were re-fetched and reported success. The P07 implementation and final verification-matrix commits were both tested by both existing workflows.

## P08 implementation checkpoint — real Linux host inspector adapter

**Checkpoint:** APAA-S07-C01-P08  
**Implementation:** core/linux_host_inspector.py  
**Tests:** tests/test_linux_host_inspector.py  
**Detailed contract:** docs/APAA_S07_REAL_HOST_INSPECTOR_P08.md  
**CI:** PASS on P08 verification-matrix commit `4e9ef613342af52c1df6f04696596cc5532528e1`

| Area | P08 evidence | Status |
|---|---|---|
| Concrete host adapter | LinuxHostInspectorAdapter implements the P07 HostSnapshotSource read contract | IMPLEMENTED — UNIT TESTS ADDED |
| Runtime identity/PID mapping | Supplied only by a separately trusted runtime integration; no container discovery | EXTERNAL TRUST REQUIREMENT |
| Namespace identity | Read-only procfs namespace inode and interface observation; exactly one non-loopback interface required | IMPLEMENTED — SYNTHETIC PROCFS TESTS |
| Effective nftables observation | Fixed nsenter + nft -j list ruleset argument vector in target netns | IMPLEMENTED — MOCKED SUBPROCESS TESTS |
| Command safety | shell=False, fixed executable paths/arguments, no stdin, minimal environment, closed FDs, 5s timeout, 1 MiB output cap | IMPLEMENTED — TESTS ADDED |
| Namespace TOCTOU | Namespace inode checked before and after nftables read | IMPLEMENTED — UNIT TEST ADDED |
| Failure handling | Missing binaries, invalid PID, ambiguous interfaces, command failure, timeout and oversized output fail closed | IMPLEMENTED — UNIT TESTS ADDED |
| Secret minimization | No command line, process environment, credentials, home directory, cookies or tokens read | CODE REVIEW REQUIRED |
| Ed25519 signing | Reuses P07 collector and P06 envelope; key supplied by trusted caller | EXISTING P06/P07 PATH |
| One-time challenge replay prevention | P06 verifier is stateless; durable issue/consume remains control-plane responsibility | NOT IMPLEMENTED IN P08 |
| Key custody / rotation | Out-of-band protected signing key and trusted public-key registry | EXTERNAL RELEASE GATE |
| Live host acceptance | Dedicated Linux host + real namespace + unprivileged account | NOT RUN |
| Packet-level egress/DNS proof | Independent IPv4/IPv6, UDP/QUIC, DNS, routing and forwarding tests | NOT RUN |
| Deployment/firewall/browser | No deployment, firewall mutation, worker start or browser activation | NOT PERFORMED |
| Existing CI workflows | Agent Foundation CI + Python Demo CI on exact matrix commit `4e9ef613342af52c1df6f04696596cc5532528e1` | PASS — 661 tests each |

### P08 interpretation and exit gate

P08 adds a concrete Linux adapter, but it does not make the host trustworthy by itself. The runtime integration must authenticate the runtime/worker-to-PID mapping. The adapter executes only a fixed read-only nftables listing command without a shell or privilege escalation. Namespace inode checks reduce ordinary PID/namespace replacement races but are not a substitute for independent runtime lifecycle review. The resulting snapshot still passes through the P07 parser and P06 signature verifier.

Unit tests use synthetic procfs and mocked process execution. They do not count as live host evidence. Durable one-time challenge consumption, out-of-band key custody, live host acceptance and packet-level enforcement remain release blockers.

**P08 disposition:** CONCRETE READ-ONLY LINUX ADAPTER + DETERMINISTIC UNIT TESTS ADDED. CI AND INDEPENDENT HOST ACCEPTANCE PENDING. No new workflow; no deployment, firewall changes, worker start or browser activation. PR #5 remains Open + Draft + unmerged.


### P08 exact CI verification — PASS

**P08 verification-matrix commit:** `4e9ef613342af52c1df6f04696596cc5532528e1`

| Existing workflow | Run | Result | Exact evidence |
|---|---:|---|---|
| Agent Foundation CI | [43716609001](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43716609001) | PASS | 661 passed in 18.24s; pip-audit reported no known vulnerabilities; compileall and every job step succeeded |
| Python Demo CI | [43716609027](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43716609027) | PASS | 661 passed in 16.35s; demo smoke printed `Hello TradeLab Pro`; every job step succeeded |

Both workflow jobs and all listed steps were re-fetched after completion and reported success. The two existing workflows ran on the exact P08 verification-matrix commit above. This verifies repository tests and offline adapter behavior; it is not live host acceptance or packet-level firewall evidence.

**Correction record:** An intermediate P08 implementation commit failed one new test because the test called nftables inspection before capturing namespace identity. The adapter's fail-closed ordering was retained; the test was corrected to capture and pin the namespace first. The subsequent code-bearing commits and exact matrix commit passed both existing workflows. No CI workflow was added or modified.


### Final P08 documentation commit verification

The final documentation-only P08 record commit `fe38d77e2250d76cd77658bf782907aef6969148` was independently checked after completion:

- [Agent Foundation CI — run 43716747245](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43716747245): completed, conclusion SUCCESS.
- [Python Demo CI — run 43716745798](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43716745798): completed, conclusion SUCCESS.

Both workflows ran against the exact final documentation commit. This closes the P08 repository CI verification checkpoint. It does not close the separately listed live-host, key-custody, durable challenge-consumption or packet-level acceptance gates.
