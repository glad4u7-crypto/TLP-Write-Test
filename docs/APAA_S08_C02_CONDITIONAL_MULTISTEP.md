# APAA S08 C02 — Conditional and Multi-step Execution

## P02 — Conditional execution
- Added `core/task_conditions.py` with a declarative condition tree; no eval, exec, expression parser, imports, attribute access, or callable predicates.
- Supported operators: eq, ne, gt, gte, lt, lte, contains, in, exists.
- Boolean composition supports all_of, any_of and negate.
- Context and literal values are bounded JSON primitives; private/empty path segments are rejected.
- Complexity is bounded to 64 nodes, depth 8, data depth 12 and 2,048 data nodes.
- Missing paths do not match; malformed conditions return invalid/false (fail closed).

## P03 — Multi-step execution
- Added `core/multi_step_executor.py` with immutable plan/result records and a finite ordered plan (1–25 steps).
- Each step has a unique ID, allowlisted action candidate, bounded JSON payload and optional declarative condition.
- A false condition skips that step; an invalid condition blocks the plan.
- Each eligible action dispatches only through the existing `ExecutionGateway`, carrying the optional validated tenant scope through approval receipt consumption.
- Actions requiring permission need a fresh one-time ApprovalReceipt from a trusted UI/controller callback; payload is snapshotted before approval and dispatch.
- Execution stops on first failed/blocked step. No retry, loop, dynamic code, handler fallback, rollback, or compensation is implemented.
- Conditions see only caller-supplied bounded context, not prior handler outputs.

## Security and scope limits
- Existing central action policy remains authoritative; this code does not widen its allowlist.
- No payment, purchase, trading, money movement, paid API/provider, API key, shell, arbitrary network, browser/device automation, deployment, or native Android runtime is enabled.
- Trusted approval callback and ApprovalAuthority must remain private to trusted application UI/controller code; Python in-process code is not a hostile-code sandbox.
- These are controller-level Python primitives, not proof of production or Android integration.

## Verification
- Tests: `tests/test_task_conditions_and_multistep.py`.
- Both existing GitHub Actions workflows must pass on the exact final commit before P02/P03 are marked verified.
