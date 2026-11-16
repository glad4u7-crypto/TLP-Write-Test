# APAA S08 — Task Execution Engine

**Roadmap identity:** S08 Task Execution Engine, defined in the APAA Master Roadmap.
**Working branch:** `feature/approval-ui-e2e-p06`
**Base:** `feature/agent-v0.3-zero-cost-core`
**Current checkpoint:** `APAA-S08-C01-P01` — Task Lifecycle.

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
