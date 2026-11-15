# Verification — APAA-S08-C02-P08

## P07 runtime integration
- SQLite claims are serialized using BEGIN IMMEDIATE; transition, lease assignment, attempt increment and audit record share one transaction.
- ExecutionEngine supports opt-in cooperative handler budgets.
- Handler outputs are finite JSON and size-checked before success.
- Legacy one-argument handler interface remains supported.

## P08 end-to-end coverage
- Independent StateStore connections race to claim the same queued task; exactly one succeeds.
- Expired worker lease is recovered and an authorized worker subsequently completes the task.
- Policy revocation and expired consent prevent handler invocation.
- Injected handler failures exhaust retry count and enter the dead-letter queue.
- Complete lifecycle events are present and the audit hash chain verifies.

## Explicit limitations
- Cooperative deadlines cannot kill non-cooperative Python code.
- Step budget is not an OS resource quota; no process sandbox is included.
- At-least-once retries can repeat external effects; adapters must implement destination-side idempotency.
- SQLite remains single-host; no distributed coordination or deployment.
- No browser, network, device, payment, purchase or firewall actions.
