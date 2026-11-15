# APAA S08-C02 — Durable Execution Foundation

P01–P03 provide the SQLite task queue, lease/retry/dead-letter handling, cancellation and hash-chained audit.
P04 adds bounded input validation, versioned policies, scoped expiring consent and signed SQLite backup.
P05 integrates validation, policy and consent checks into the ExecutionEngine.

## P06 — Reliability primitives
`apaa_reliability.py` provides atomic SQLite claim support, cooperative execution budgets and bounded JSON result validation.

## P07 — Unified Runtime Integration
The main `ExecutionEngine` now:
- Claims tasks inside an explicit SQLite `BEGIN IMMEDIATE` transaction; state transition, lease owner, attempt increment and audit event commit together.
- Serializes claims across independent SQLite connections, not only a single engine's in-process lock.
- Supports optional cooperative handlers registered with `cooperative=True`; these receive an `ExecutionBudget` and can call `check()`, `consume()`, or `cancel()`.
- Checks the execution budget after handler return and validates finite JSON output against a configurable byte limit before marking success.
- Preserves one-argument handlers for existing adapters.

Runtime limits are configurable through `ExecutionEngine(..., execution_timeout_seconds=30, max_execution_steps=10000, max_result_bytes=65536)`.

## P08 — End-to-End Verification
Integration tests exercise independent runtime stores racing for one task, lease-expiry recovery followed by authorized execution, policy revocation, expired consent, retry exhaustion/dead-letter routing and full lifecycle audit verification.

## Safety and operational limits
- Cooperative timeouts only: Python cannot safely terminate arbitrary non-cooperative handler threads. A non-cooperative handler can overrun the deadline; process isolation is required for hard termination.
- Step budgets are cooperative, not OS CPU/memory quotas.
- SQLite is single-host persistence, not distributed consensus.
- Crash recovery is at-least-once; external side effects require destination idempotency.
- Hash-chained audit detects edits/deletion/reordering but is not a digital signature or externally anchored immutable log.
- No browser, network, device, payment, purchase, deployment or firewall operation is included.
- This isolated test branch is not production deployment.

## Tests
Run `python -m unittest discover -s tests -v` with Python 3.11+; standard library only.
