# APAA S04 — Security Pass / Block Matrix

Checkpoint: APAA-S04-C01-P08-P09-BG  
Verification date: 2026-11-15  
Repository: glad4u7-crypto/TLP-Write-Test  
Pull request: #5 (must remain Draft)  
Implementation head reviewed: 509799b3901d9e25fd539a7ffae507323e0d586c  
Head branch: feature/approval-ui-e2e-p06  
Base branch: feature/agent-v0.3-zero-cost-core

## Exact-head CI evidence

The implementation head above completed both existing required workflows successfully:

| Workflow | Run ID | Result | Verified steps |
|---|---:|---|---|
| Agent Foundation CI | 43697232345 | PASS | pinned checkout/setup actions, dependency installation, pip-audit, compileall, full pytest suite |
| Python Demo CI | 43697232231 | PASS | pinned checkout/setup actions, dependency installation, full pytest suite, demo output check |

The GitHub job and step records show every step completed successfully. The preceding exact head ce1973ec2bc1c3f2fed6e23f89b90f1d14ed51e7 also passed both workflows (43697117613 and 43697117662). The documented suite size at that point was 385 tests. Dependency audit is point-in-time evidence, not a guarantee against future advisories.

## Consolidated S04 security matrix

| Security control / gate | Status | Evidence and boundary |
|---|---|---|
| GitHub Actions external action pinning | PASS | Both existing workflows pin checkout/setup-python to full commit SHAs; regression test checks all action references. |
| CI token permissions | PASS | Both workflows explicitly set contents: read; no pull_request_target or write-all. |
| CI runtime and concurrency | PASS | Both workflows set bounded job timeouts and cancel superseded runs. |
| Dependency vulnerability audit | PASS (point-in-time) | Agent Foundation CI pip-audit step completed successfully on exact head; re-run for every dependency change. |
| Python compilation and automated regression | PASS (CI scope) | Both exact-head workflows completed compile/test steps successfully. |
| Demo smoke test | PASS | Python Demo CI exact-output step passed. |
| OIDC claim validation | PASS (offline tests only) | Adapter validates issuer, subject, expiry, issue time and clock-skew boundaries. Live provider integration is not implied. |
| Authentication-required startup / fail-closed paths | PASS (AppTest scope) | Missing configuration, logged-out, invalid identity and unsafe storage startup branches stop before protected controls. |
| Logout and identity transition cleanup | PASS (automated scope) | Central session cleanup inventory is guarded by AST regression; explicit logout and identity switching clear identity-bound capabilities and drafts. |
| Tenant isolation / project ownership | PASS (automated scope) | Issuer + subject composite tenant predicates; cross-issuer, cross-subject and unauthorized CRUD tests. |
| Approval receipt integrity | PASS (automated scope) | HMAC-signed, action/payload-bound, expiring, single-use receipts; tenant/session scope binding and replay tests. |
| Execution authorization / handler allowlist | PASS (automated scope) | Explicit handler registration; no real-world adapters; payment and arbitrary execution identifiers denied. |
| Audit intent fail-closed behavior | PASS (automated scope) | Durable intent append precedes handler dispatch; audit failure blocks dispatch; completion/failure is recorded where available. |
| SQLite nonce and audit transaction safety | PASS (automated scope) | Transactional writes, uniqueness/replay controls, hash-chain verification, crash/concurrency tests. |
| SQLite project persistence / tenant predicates | PASS (automated scope) | Issuer + subject filtering, owner-only files/directories, symlink checks and CRUD isolation tests. |
| SQLite connection and tenant-store lifecycle | PASS (code review + CI) | Connections are operation-scoped; tenant-bound stores/adapters are reachable through session-owned objects cleared on logout/identity change. |
| Process-global state / lock review | PASS with limitation | The only identified process-global cache is the JSONL audit path-to-thread-lock registry. It retains synchronization locks, not principals, tenants or approval capabilities. The application uses a fixed audit path; no user-controlled arbitrary path is exposed. Lock entries can accumulate if a caller creates loggers for unbounded distinct paths; this is not currently reachable through the app UI. Do not remove shared locks: they prevent same-process concurrent append races. |
| Live OIDC provider login/logout | BLOCKED | Requires a private non-production deployment, configured OIDC client and two controlled test identities. |
| Two-user browser/profile isolation | BLOCKED | Requires isolated browser profiles and real provider sessions; AppTest is not browser evidence. |
| Browser cookies, CSRF, redirect and reverse-proxy controls | BLOCKED | Deployment-specific real-browser/security review has not been performed. |
| Repository branch protection / rulesets | BLOCKED / UNVERIFIED | Base branch metadata currently reports protected=false; administrative protection/ruleset details are not readable through the connected integration. Repository owner must verify and configure required reviews and CI checks. |
| Production hostile-code isolation / sandbox | BLOCKED | Current trust boundaries are in-process. No hostile-code sandbox or production capability isolation exists. |
| Production multi-host topology | BLOCKED | Local SQLite and process-local facilities are not validated for multi-host deployment. |
| Audit backup, retention, monitoring and independent anchoring | BLOCKED | Local hash chains detect ordinary corruption but are not independently tamper-proof against a database/file writer. Operational controls and external anchor are absent. |
| Real-world browser, email, shell, network, filesystem or device handlers | BLOCKED / NOT ENABLED | No such adapters are authorized or registered. Must remain disabled until separate design, sandboxing and negative tests. |
| Auto-Run | BLOCKED / DISABLED | Remains disabled; no task text may grant it. |
| Payment, purchase, checkout, trading or money movement | PROHIBITED | Explicitly outside project permission scope; must remain denied. |
| Paid providers, API keys and billable services | PROHIBITED / DISABLED | Current build remains zero-cost; no provider activation or charge. |

## BG review conclusion

- The two existing CI workflows pass on implementation head 509799b3901d9e25fd539a7ffae507323e0d586c.
- No new offline-verifiable code defect was demonstrated in the process-global lock/cache review. No speculative runtime change was made.
- The two existing workflows are sufficient for this scope; no third workflow was created.
- The code-level automated S04 gates are PASS within their stated test boundaries.
- Full S04 security/release readiness remains BLOCKED by live OIDC/browser verification, repository administration, deployment controls, production sandbox/isolation, and operational audit/backup requirements.

## Required operating constraints

PR #5 remains open and Draft. Keep base branch unchanged. Do not merge, deploy, enable Auto-Run, activate paid providers, request API keys, or register real-world action handlers. Payments, purchases, checkout, trading and money movement remain prohibited. Production is NOT APPROVED.

## Next checkpoint

APAA-S04-C01-P08-P09-BO: review process-global caches and lock registries for cross-session retention and growth. Preserve the shared audit append lock unless a safe replacement is proven.