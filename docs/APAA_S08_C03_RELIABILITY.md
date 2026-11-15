# APAA-S08-C03 — Execution Reliability

## P01 — Cooperative timeout management
- `ExecutionBudget` uses a monotonic deadline and validates a bounded timeout (greater than zero, at most 300 seconds).
- Controllers must check the budget before starting each step and pass the budget to cooperative handlers.
- Python cannot safely terminate an arbitrary running thread or reverse an external side effect. Expiry therefore prevents new work; an already-dispatched operation may require manual review.
- This module does not claim hard process isolation or forced cancellation.

## P02 — Safe retry and recovery
- Retry attempts are bounded to 1–3.
- An operation must explicitly classify a failure as `PRE_DISPATCH` before retry is allowed.
- `DISPATCH_STARTED` and `OUTCOME_UNKNOWN` outcomes are never retried automatically.
- Unclassified exceptions are treated as outcome-unknown and stop retry.
- No payment, purchase, trading, money movement, paid-provider, or external-provider fallback is introduced.

## P03 — Completion verification
- Optional read-only observer callbacks return JSON-compatible state.
- Expected and observed values are canonicalized and compared using SHA-256 digests.
- Observer errors, invalid data, partial verification configuration, or mismatches fail closed.
- A returned handler value without an observer is described as a successful return, not proof of external state completion.

## Verification scope
- Focused tests cover deadline expiry, timeout bounds, retry limits, pre-dispatch-only retries, uncertain dispatch, observer failures, canonical comparison and manual-review outcomes.
- Full repository tests, compile validation, dependency audit and demo smoke test run in the isolated S08 workflow.
- This is a Python controller-level reliability primitive. It does not implement native Android scheduling, real browser/device adapters, process-kill guarantees or production deployment.
