# APAA S08 — Task Execution Verification Matrix

**Current subject:** Task Execution Engine
**Current checkpoint:** APAA-S08-C03-P03 — implementation added; exact-head CI verification pending

| Checkpoint | Scope | Implementation | Tests | Status |
|---|---|---|---|---|
| S08-C01-P01 | Task lifecycle | `core/task_lifecycle.py`: transition graph, immutable snapshots/events, versions, approval-state bookkeeping | `tests/test_task_lifecycle.py` | PASS — 709 tests; exact-head CI PASS |
| S08-C01-P02 | Task queue | `core/task_queue.py`: bounded in-memory priority queue, stable FIFO ties, duplicate protection, capacity rejection, immutable snapshots | `tests/test_task_queue.py` | PASS — exact code snapshot CI PASS |
| S08-C01-P03 | Task state | `core/task_state_store.py`: consent-gated, tenant-scoped SQLite snapshots/events; atomic CAS transitions; recovery and immutable event history | `tests/test_task_state_store.py` | PASS — exact code snapshot CI PASS |
| S08-C02-P01 | Sequential execution | `core/sequential_executor.py`: one-at-a-time queue/lifecycle/gateway coordination; fresh trusted receipt for approval-required work | `tests/test_sequential_executor.py` | PASS — exact-head Agent Foundation CI + Python Demo CI on `b0389b736bbfdc05941ea597812d0064cc6c5843` |
| S08-C02-P02 | Conditional execution | `core/execution_control.py`: bounded path lookup and allowlisted typed predicates; no expression evaluation | `tests/test_execution_control.py` | IMPLEMENTED — CI pending |
| S08-C02-P03 | Multi-step execution | `MultiStepExecutor`: bounded linear plan, unique IDs, sequential gateway-adapter callback, fail-stop | `tests/test_execution_control.py` | IMPLEMENTED — CI pending |
| S08-C03-P01 | Timeout | `ExecutionDeadline`: bounded cooperative deadline; distinguishes pre-dispatch timeout from uncertain post-dispatch outcome | `tests/test_execution_control.py` | IMPLEMENTED — CI pending |
| S08-C03-P02 | Retry/recovery | `SafeRetryPolicy`: bounded retry only for explicit pre-dispatch failures; unknown outcomes never retried | `tests/test_execution_control.py` | IMPLEMENTED — CI pending |
| S08-C03-P03 | Completion verification | `CompletionVerifier`: read-only expected/observed verification; mismatch and verifier errors fail closed | `tests/test_execution_control.py` | IMPLEMENTED — CI pending |
| S08-C04-P01 | Pre-execution validation | Not started | Pending | PENDING |
| S08-C04-P02 | Permission check | Not started; must use trusted approval gateway | Pending | PENDING |
| S08-C04-P03 | Audit | Not started; must use payload-free durable audit | Pending | PENDING |

## P01 invariants

- Only explicitly listed lifecycle transitions are accepted.
- Succeeded, failed and cancelled are terminal in P01; retry/recovery is a later Part.
- Mutating tasks cannot move directly from planned to running when approval is required.
- Awaiting-approval to running requires an approval-recorded marker, but this marker is not a credential and cannot authorize side effects.
- The trusted ExecutionGateway remains the only current registered-handler dispatch boundary.
- In-memory task records disappear on process restart; persistence is deliberately deferred to P03.

## Global project constraints

Android-first; free-only implementation; Ask First by default; no payment, purchase, trading, money movement, paid APIs/providers, or API keys. No merge, deployment, or base-branch modification without explicit authorization.

**P01 disposition:** Implementation and unit tests added. Exact-head CI is pending; do not mark verified until both existing workflows pass.


## Exact-head verification

**Verified snapshot:** `b78ce04c56bf0f5dfd88bff2ebaa401764e711d9`

| Workflow | Run | Result |
|---|---:|---|
| Agent Foundation CI | [43724507507](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43724507507) | PASS — 709 tests in 12.61s; compileall passed; dependency audit clear |
| Python Demo CI | [43724507501](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43724507501) | PASS — 709 tests in 18.48s; demo smoke test passed |

P01 is verified at repository/CI level. The lifecycle is in-memory only and is not integrated into the dashboard or an Android app. P02 queue, P03 durable task state, execution control, reliability and dedicated safety Parts remain pending.


## P02 implementation review (verification pending)

- Queue is bounded (default capacity 100; configurable 1–10,000) and rejects overflow without dropping existing work.
- Larger integer priority is dequeued first; equal priorities preserve FIFO order.
- Duplicate task IDs are rejected while queued. IDs may be reused after removal/dequeue; heap sequence tokens prevent stale-entry corruption.
- Thread-safe enqueue/dequeue/peek/remove/size and immutable sorted snapshots.
- Stores task IDs only. No task execution, dispatch, persistence, permission grant or handler integration.
- Tests cover ordering, priority ties, duplicate IDs, overflow, removal/peek, empty queue, invalid inputs, concurrency, immutable snapshots and ID-reuse regression.
- Code/test commits: `7663b3b359c77022cfc01f2436890f76fec6ed04`, `8d03ce9489e28fe0f2aba5bf539e035e4bfc68be`, `8b158f1c76a08e100ee6409f478626738ef8ec84`, `7b5a0ac0a89be2b0210ff1ff7097fbfb8b19a3dd`.
- Exact-head Agent Foundation CI and Python Demo CI have not yet reported for `7b5a0ac0a89be2b0210ff1ff7097fbfb8b19a3dd`; P02 must remain unverified until both pass.


## P02 exact-head verification

**Code-bearing snapshot:** `7b5a0ac0a89be2b0210ff1ff7097fbfb8b19a3dd`

| Existing workflow | Run | Result |
|---|---:|---|
| Agent Foundation CI | [43724798843](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43724798843) | PASS |
| Python Demo CI | [43724798836](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43724798836) | PASS |

P02 is verified at repository CI level. Queue remains an in-memory ordering primitive and performs no task execution.

## P03 implementation review (verification pending)

- Added `core/task_state_store.py`, a separate SQLite persistence adapter reusing S07's validated `TenantKey` contract.
- Stores task snapshots and lifecycle events under the composite issuer+subject+task identity.
- Explicit `consent=True` required for create/update; reads remain tenant-scoped.
- Snapshot update and event append are atomic. Compare-and-swap version check rejects stale writers.
- Event source status must match persisted state. Duplicate initial records and inconsistent event/snapshot versions are rejected.
- Private DB file (0600), owner-only parent directory (0700), symlink rejection, bounded reads, credential-like content rejection.
- Reopen/recovery, tenant isolation, consent, stale-write conflict, transaction rollback, concurrent writers and invalid content covered in `tests/test_task_state_store.py`.
- Adapter is not yet wired into lifecycle/controller or Android UI. It does not execute tasks or authorize actions.
- Code-bearing latest branch commit: `62ac59a968704dc99a3e05518739a4d345135c7e`; exact-head CI results must be checked before P03 can be marked PASS.


## P03 exact-head verification

**Code-bearing snapshot:** `62ac59a968704dc99a3e05518739a4d345135c7e`

| Existing workflow | Run | Result |
|---|---:|---|
| Agent Foundation CI | [43727490665](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43727490665) | PASS — dependency audit, compile and foundation test suite passed |
| Python Demo CI | [43727490670](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43727490670) | PASS — full test suite and demo smoke passed |

P03 is verified for the SQLite persistence adapter and its unit-test contract. It is not yet integrated into the runtime lifecycle/controller, Streamlit application, or native Android client. Those integration and platform checks remain open; P03 PASS does not imply production readiness.


## C02-P01 sequential execution implementation (verification pending)

- Added `core/sequential_executor.py` to coordinate the existing bounded queue, lifecycle state machine and trusted `ExecutionGateway`.
- Each call dequeues at most one task. A runner lock covers dequeue, dispatch and terminal state update so concurrent calls through the same executor cannot overlap handlers.
- Only tasks in `planned` or `awaiting_approval` are eligible. Approval-required tasks must already be `awaiting_approval` and receive a fresh `ApprovalReceipt` from a trusted UI/controller callback.
- The gateway remains responsible for policy, exact action/payload-bound one-time receipt consumption and audit-before-dispatch. The sequential executor does not issue receipts or register handlers.
- Gateway success maps to `succeeded`; a blocked/failed gateway result maps to `failed`. Unexpected controller errors fail closed. No automatic retry, handler fallback, payment, purchase, trading or money movement.
- Added `tests/test_sequential_executor.py` for queue order, non-overlap, approval enforcement, invalid lifecycle state and failed dispatch.
- Code-bearing snapshot: `798a955bf1b0290eb59a058965f20baa43d515ef`.
- Agent Foundation CI run [43728173522](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43728173522) and Python Demo CI run [43728173537](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43728173537) were observed in progress. C02-P01 remains PENDING until both workflows finish successfully on this exact snapshot.
- Scope limitation: this is a Python controller-level implementation, not yet wired to the Android client or production runtime. PR #5 remains Draft/Open/Unmerged; no merge or deployment performed.


## C02-P02 / C02-P03 and C03-P01 / P02 / P03 implementation review

- Added `core/execution_control.py` with five bounded primitives: condition evaluation, linear multi-step coordination, cooperative deadlines, pre-dispatch-only retry, and read-only completion verification.
- Conditional evaluation supports only an enum allowlist of operators and bounded mapping paths. It does not call eval/exec or interpret task text as code. Missing paths fail closed.
- Multi-step plans are limited to 25 steps by default, reject duplicate IDs and invalid payloads, execute serially through a trusted callback, and stop at the first false/exception outcome. The callback is expected to route each action through the existing ExecutionGateway; the primitive does not dispatch handlers itself.
- Timeout is deliberately cooperative: Python cannot safely kill an in-flight handler thread. If a deadline expires after dispatch starts, the result is explicitly marked as potentially completed/uncertain. Such outcomes must not be retried automatically.
- Retry is opt-in and bounded to 3 attempts maximum. Only a caller-classified `RetryablePreDispatchError` is retryable. `DispatchOutcomeUnknown` propagates immediately. No blind retry of mutations.
- Completion verification compares expected and observed evidence through a trusted read-only callback; mismatches and callback errors return unverified.
- Added `tests/test_execution_control.py` covering conditions, code-like path handling, numeric type checks, multi-step fail-stop, duplicate/oversized plans, timeout uncertainty, safe retry classification, and completion verification.
- No Auto-Run, paid API, external provider, payment, purchase, trading, or money movement was added.
- These are controller-level primitives. They are not yet wired into the Android client/dashboard or production runtime. No production-readiness claim is made.
- Code commit: `a75a9fe03966afd23edd181a4cdd6f866ab81ae0`; test commit: `f7cc31f3ba9a06a91036cfdae58f66673416d820`; test-fixture correction: `357cdf70b7892d7d22c436ad7ce07fe1d9442836`.
- Final exact-head CI must pass before these five Parts are marked PASS.
