# APAA S04 — Security Pass / Block Matrix

Checkpoint: APAA-S04-C01-P08-P09-BP  
Verification date: 2026-11-15  
Repository: glad4u7-crypto/TLP-Write-Test  
Pull request: #5 (must remain Draft)  
Implementation head reviewed: 9e8d52449eac691cdd442ce3c9d6fe2231ec4760  
Head branch: feature/approval-ui-e2e-p06  
Base branch: feature/agent-v0.3-zero-cost-core

## Exact-head CI evidence

The implementation head above completed both existing required workflows successfully:

| Workflow | Run ID | Result | Verified steps |
|---|---:|---|---|
| Agent Foundation CI | 43697663733 | PASS | pinned checkout/setup actions, dependency installation, pip-audit, compileall, 390 tests passed |
| Python Demo CI | 43697663665 | PASS | pinned checkout/setup actions, dependency installation, 390 tests passed, demo output check |

The GitHub job and step records show every step completed successfully. The preceding exact head ce1973ec2bc1c3f2fed6e23f89b90f1d14ed51e7 also passed both workflows (43697117613 and 43697117662). The documented suite size at that point was 385 tests. Dependency audit is point-in-time evidence, not a guarantee against future advisories.

## Consolidated S04 security matrix

| Security control / gate | Status | Evidence and boundary |
|---|---|---|
| GitHub Actions external action pinning | PASS | Both existing workflows pin checkout/setup-python to full commit SHAs; regression test checks all action references. |
| CI token permissions | PASS | Both workflows explicitly set contents: read; no pull_request_target or write-all. |
| CI runtime and concurrency | PASS | Both workflows set bounded job timeouts; PR runs use SHA-scoped concurrency groups with `cancel-in-progress: false`, avoiding cancellation of active required checks. |
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

## BP filesystem-path review and bounded remediation

The audit and SQLite stores previously retained relative filesystem paths. A process working-directory change after store construction could redirect later operations to a different relative location. This is a reproducible correctness and security-boundary weakness even without a symlink race.

Remediation applied:
- `JsonlAuditLog` now anchors its path with `Path(path).absolute()` at construction.
- `SQLiteSecurityStore` and `SQLiteProjectStore` now anchor their database paths with `Path(database_path).absolute()` at construction.
- Added regression tests that change the process working directory after construction and assert all later writes remain at the original absolute path.
- Existing symlink rejection, owner-only directory checks, regular-file checks, and file permissions remain in place.

Boundary retained:
- This does not eliminate a time-of-check/time-of-use race if a hostile process with the same OS account can rename/replace parent directories between validation and the later file open/SQLite connection. Standard `sqlite3` opens by pathname; robust descriptor-relative control and OS sandboxing require platform-specific design and are not claimed here.
- Do not claim protection against a same-UID hostile process. Production deployment still needs a dedicated OS account, private non-writable parent directories, and process/container isolation.

## BP review conclusion

- Relative-path working-directory drift was reduced with construction-time absolute path anchoring in JSONL and both SQLite stores.
- Both durable SQLite stores reject :memory: before normalization; in-memory mode is incompatible with the per-operation connection lifecycle.
- CI concurrency groups include the event name so push and pull_request runs do not cancel one another.
- Regression coverage was added for JSONL audit, SQLite security nonce storage, and SQLite project storage.
- Exact-head PR CI passed: Agent Foundation CI 43697663733 and Python Demo CI 43697663665; both ran 390 tests. The dependency audit, compile and demo smoke test also passed.
- No third workflow was created. No merge or deployment was performed.
- Full S04 security/release readiness remains BLOCKED by live OIDC/browser verification, repository administration, deployment controls, production sandbox/isolation, and operational audit/backup requirements.

## Required operating constraints

PR #5 remains open and Draft. Keep base branch unchanged. Do not merge, deploy, enable Auto-Run, activate paid providers, request API keys, or register real-world action handlers. Payments, purchases, checkout, trading and money movement remain prohibited. Production is NOT APPROVED.

## Next checkpoint

APAA-S04-C01-P08-P09-BQ: inspect SQLite path revalidation and symlink/rename race boundaries, including connection lifecycle and sidecar handling. Only implement portable mitigations with regression tests; retain explicit OS-isolation blocks.

## P08-P09-BR — CI cancellation remediation and SQLite parent-path replacement test

Review date: 2026-11-15
Verified head: 3f85425e5adff0411e4e1a7534ff3a979e60a6a0

### CI cancellation policy

- Feature-branch push triggers were removed for these PR-focused workflows; feature changes are validated by pull_request, while main retains push validation.
- Concurrency groups now include workflow, event name and commit SHA, with cancel-in-progress: false. A newer commit therefore cannot cancel an older in-flight verification in the same workflow/event stream.
- The regression test was updated to assert the intended policy. The earlier failure was a stale test expectation for cancel-in-progress: true; no runtime security test failed for that reason.
- Historical Cancelled runs remain recorded as Cancelled. They were obsolete commit attempts and are not represented as passes or retroactively changed.

### Exact-head verification

| Workflow | Run | Exact head | Result |
|---|---:|---|---|
| Agent Foundation CI | 43698205731 | 3f85425e5adff0411e4e1a7534ff3a979e60a6a0 | PASS |
| Python Demo CI | 43698205658 | 3f85425e5adff0411e4e1a7534ff3a979e60a6a0 | PASS |

Both workflows completed all steps successfully, including dependency audit, compile, foundation test suite, demo test suite and demo execution. The new SQLite parent-directory rename/symlink regression test is included in this exact-head test run.

### SQLite parent-path replacement

- Added a parameterized regression test for SQLiteSecurityStore and SQLiteProjectStore.
- Each store is initialized under a private parent; the parent is then renamed and replaced with a symlink to the moved directory.
- A subsequent connection attempt must reject the symlinked lexical parent before SQLite opens the path.
- Exact-head Agent Foundation CI passed with this test present.

### Residual security boundary

This is a deterministic post-initialization path-replacement check, not proof against a hostile same-UID process racing the validation and SQLite pathname open. Standard sqlite3 path-based opens do not pin an already-validated inode. Keep dedicated OS-account, non-writable parent directory, and process/container isolation requirements as production blockers.

## Current disposition

- PR #5 remains Open and Draft; no merge or deployment.
- Auto-Run and real-world execution handlers remain disabled.
- Payments, purchases, checkout, trading and money movement remain prohibited.
- Paid providers/API keys remain disabled; current build remains zero-cost.
- Production remains NOT APPROVED.

### Next checkpoint

APAA-S04-C01-P08-P09-BS: review JSONL audit path handling and SQLite journal/WAL sidecar lifecycle for cleanup, permission persistence, and tamper-detection limits. Do not claim protection beyond the tests and OS boundary above.


## Latest exact-head verification — 2026-11-15

Reviewed head: `9e8d52449eac691cdd442ce3c9d6fe2231ec4760` (PR #5, feature/approval-ui-e2e-p06).

| Workflow | Run ID | Conclusion | Verified job steps |
|---|---:|---|---|
| Agent Foundation CI | 43698548471 | PASS | dependency install, pip-audit, compileall, foundation tests |
| Python Demo CI | 43698548468 | PASS | dependency install, full test suite, demo smoke test |

Both runs completed on the exact reviewed SHA; all reported job steps succeeded. This confirms the JSONL parent-directory replacement regression test is included in a passing exact-head CI run.

## Audit durability and concurrency boundaries

- JSONL append uses a process-local per-path thread lock. It serializes threads and multiple logger objects in the same Python process, but it is **not an inter-process lock**. Concurrent writers from separate OS processes are not supported or verified; deployment must enforce a single writer process until an inter-process locking design is separately implemented and tested.
- Each append flushes and fsyncs the file descriptor, but creation of a new audit file does not fsync the containing directory. Power-loss durability of the new directory entry is therefore not guaranteed.
- A truncated or malformed trailing JSONL record fails verification closed. There is no automatic truncation/repair recovery; preserve the file for investigation rather than silently repairing it.
- The SHA-256 chain detects accidental corruption and ordinary edits, but has no independent external anchor. An attacker able to rewrite the entire log and recompute hashes can forge a replacement chain. Protected backup, retention, monitoring and independently stored checkpoints remain deployment blockers.
- Parent-directory symlink replacement is now covered by a regression test, but hostile same-UID path races between validation and pathname-based open are not eliminated. Dedicated OS identity, non-writable private parent and process/container isolation remain required deployment controls.

## Updated decision

Code-level and offline CI gates for this exact head: **PASS**. Full S04 release readiness: **BLOCKED** by live OIDC/browser verification, repository branch-protection verification, production isolation, single-writer topology enforcement, and operational audit durability/backup/independent anchoring. PR #5 remains Open + Draft. Do not merge or deploy. Auto-Run and real-world handlers remain disabled; payment, purchases, trading and money movement remain prohibited. Production remains **NOT APPROVED**.

Next checkpoint: `APAA-S04-C01-P08-P09-BU` — add explicit single-writer runtime guard or enforceable deployment contract, then test audit crash/truncation fail-closed behavior and update the matrix from evidence.
