# APAA S08-C02 — Durable Execution Foundation

P01–P03 provide the SQLite task queue, lease/retry/dead-letter handling, cancellation and hash-chained audit.
P04 adds bounded input validation, versioned policies, scoped expiring consent and signed SQLite backup.
P05 integrates validation, policy and consent checks into the ExecutionEngine.

## P06 — Runtime Reliability & Concurrency Hardening
Added `apaa_reliability.py`:
- `AtomicSQLiteClaimer`: uses SQLite `BEGIN IMMEDIATE` and a conditional status update so independent workers cannot claim the same queued task.
- `ExecutionBudget`: cooperative deadline, cancellation and step-budget guard. Trusted handlers must call `check()` or `consume()`; Python cannot safely kill arbitrary running threads.
- `validate_result_size`: rejects non-JSON/non-finite results and enforces a configurable serialized result size limit.

Tests cover simultaneous claims from independent connections, crash-after-claim lease recovery, cancellation, deadline, step limits, invalid/oversized outputs and empty queue behavior.

## Integration boundary
P06 primitives are implemented and independently tested, but AtomicSQLiteClaimer and ExecutionBudget are not yet wired into the existing ExecutionEngine's claim/handler dispatch. Existing engine lease recovery remains the recovery mechanism. Do not claim hard process termination or full P06 runtime integration.

## Safety boundaries
- No browser, network, device, payment, purchase, deployment or firewall operation.
- SQLite is a single-host persistence mechanism, not distributed consensus.
- Crash recovery is at-least-once; external side effects require destination idempotency.
- Cooperative timeout cannot stop non-cooperative handler code.

## Tests
Run `python -m unittest discover -s tests -v` with Python 3.11+; standard library only.
