# APAA S08 — Task Execution Engine

**Roadmap identity:** S08 Task Execution Engine, defined in the APAA Master Roadmap.
**Working branch:** `apaa/s08-c02-c03-reliability`
**Base:** `feature/agent-v0.3-zero-cost-core`
**Current checkpoint:** `APAA-S08-C03-COMPLETE` — C02-P02 through C03-P03 exact-head CI verified; C04-P01 next.

## Scope

| Chapter | Parts |
|---|---|
| C01 Execution Architecture | P01 Task lifecycle; P02 Task queue; P03 Task state |
| C02 Execution Control | P01 Sequential execution; P02 Conditional execution; P03 Multi-step execution |
| C03 Reliability | P01 Timeout; P02 Retry/recovery; P03 Completion verification |
| C04 Safety | P01 Pre-execution validation; P02 Permission check; P03 Audit |

## C01-P01 — Task Lifecycle

Implemented in `core/task_lifecycle.py`:
- Explicit lifecycle states reuse `core.models.TaskStatus`: draft, planned, awaiting_approval, running, succeeded, failed, cancelled.
- Strict transition graph; terminal succeeded/failed/cancelled states cannot be reopened by this Part.
- Immutable task snapshots and event records; per-task monotonic version and stale-write rejection.
- Description/reason bounds and thread-safe in-process registry.
- Approval-required tasks must pass through awaiting_approval before running. A recorded approval flag is only lifecycle bookkeeping, not authorization.
- The lifecycle never calls handlers, performs I/O, or grants permission. Real side effects must continue through the trusted `ExecutionGateway`, with action/payload-bound one-time approval and audit.

## Explicit boundaries

- This Part is an in-memory architecture primitive. Durable state belongs to C01-P03; queue/scheduling belong to C01-P02.
- No automatic execution, Auto-Run, shell, browser, device, email, filesystem or arbitrary network adapter is introduced.
- No payment/purchase/financial action or paid API/provider is enabled.
- No Android client or dashboard integration is claimed by this Part.
- Failure retry/recovery is intentionally deferred to C03-P02.

## Verification gates

- Unit tests: `tests/test_task_lifecycle.py`.
- Existing CI workflows must pass on the exact final commit before P01 is marked verified.
- S08 production readiness is not implied by completion of individual development Parts.


## C02-P02 — Conditional Execution

Implemented in `core/execution_control.py`:
- Typed condition model with an explicit operator allowlist (equality, numeric comparisons, membership, contains, exists, truthy).
- Bounded mapping-path resolution (maximum depth 8); missing paths resolve false except explicit exists checks.
- Numeric comparisons reject booleans and non-numeric values.
- No eval/exec, dynamic imports, or executable task-description parsing.
- The decision object selects a branch; it does not itself authorize or dispatch an action.

## C02-P03 — Multi-step Execution

Implemented in `MultiStepExecutor`:
- Linear plans bounded to 25 steps by default, unique bounded step IDs, mapping-only payloads.
- Serial callback execution; callback must route every step through the trusted ExecutionGateway.
- Fail-stop on false result or exception; later steps are not attempted after a failure.
- No parallel fan-out, hidden handler registration, or automatic retry.

## C03-P01 — Timeout

Implemented in `ExecutionDeadline`:
- Monotonic-clock deadline with a 1–300 second configured range.
- Cooperative checks before dispatch and at trusted adapter checkpoints.
- Expiry before dispatch is distinguishable from expiry after dispatch.
- Python cannot safely terminate an in-flight handler. A post-dispatch timeout is marked uncertain and must not be blindly retried.

## C03-P02 — Retry and Recovery

Implemented in `SafeRetryPolicy`:
- Retry is opt-in, bounded to at most three attempts, with bounded backoff.
- Only explicit `RetryablePreDispatchError` may be retried.
- `DispatchOutcomeUnknown` is never retried automatically.
- This avoids duplicate mutations when the remote/local side effect may already have happened.

## C03-P03 — Completion Verification

Implemented in `CompletionVerifier`:
- Compares expected and observed state through a trusted read-only verifier callback.
- Callback exceptions and non-boolean results fail closed.
- A completion report records verified/unverified status; verification does not mutate or repair state.

## C02/C03 verification and integration boundary

- Unit tests: `tests/test_execution_control.py`.
- C02-P01 sequential runner is separately implemented in `core/sequential_executor.py`; its exact-head CI passed on commit `b0389b736bbfdc05941ea597812d0064cc6c5843`.
- C02-P02 through C03-P03 are verified on code-bearing snapshot `b9d0b08797fba78de97725d98a535132c470542a`: Agent Foundation CI run `43732335321` PASS and Python Demo CI run `43732335307` PASS.
- These are Python controller-level primitives, not yet connected to the Android client, dashboard, or production runtime.
- The trusted ExecutionGateway remains the only authorized action-dispatch boundary. The multi-step adapter must use it.
- No payment, purchase, trading, money movement, paid API/provider, API key, Auto-Run, deployment, or merge is enabled by this work.


## C02-C03 exact-head verification

- Verified code-bearing snapshot: `b9d0b08797fba78de97725d98a535132c470542a`.
- Agent Foundation CI (`43732335321`) and Python Demo CI (`43732335307`) both completed successfully.
- C02-P02, C02-P03, C03-P01, C03-P02 and C03-P03 pass repository CI. This does not imply production readiness or Android/dashboard integration.
- Next checkpoint: C04-P01 — pre-execution validation.
