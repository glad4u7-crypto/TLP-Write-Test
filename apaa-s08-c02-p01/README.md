# APAA S08-C02 — Durable Execution Foundation

P01 provides guarded in-process task execution. P02 adds a durable SQLite queue, atomic claims, expiring worker leases, bounded retries, idempotency-key duplicate suppression, and an append-only audit event journal.

## Safety boundaries
- Deny by default: both permission grant and explicit user consent are required.
- Only explicitly registered in-process handlers can execute.
- No browser, device, network, payment, purchase, deployment, or firewall actions are included.
- Lease recovery is **at-least-once**, not exactly-once. A process may crash after a handler's external side effect but before recording success; handlers that may later perform side effects must enforce the supplied idempotency key at their own boundary.
- SQLite serializes claims transactionally; leases expire and can be recovered. This is a single-host local journal, not a distributed consensus system.
- Retries are bounded (1–10 attempts); no automatic retry for blocked tasks.

## Run
`python -m unittest discover -s apaa-s08-c02-p01/tests -v`

Python 3.11+, standard library only.
