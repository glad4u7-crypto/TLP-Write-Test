# APAA S08-C02 — Durable Execution Foundation

P01–P03: guarded in-process execution, durable SQLite queue, leases/retries, idempotency, dead-letter queue, queued cancellation and hash-chained audit.

P04 adds a security-hardening module:
- strict JSON payload/action validation (64 KiB default payload cap, depth limit 12, no NaN/Infinity);
- versioned action policy registry (missing policy is deny);
- durable, scope-bound consent grants with expiry and immediate revocation;
- SQLite-consistent backups and restore with external HMAC-SHA256 signature files.

## Critical safety boundaries
- P04 security controls are reusable primitives; they are not yet wired as mandatory gates into every P01–P03 execution path. Integration is a separately verified next step.
- HMAC key is caller-supplied, must be at least 32 bytes, and is never stored in the database. Keep it in a secure secret store; never commit it.
- Signed backup protects integrity/authenticity only while the HMAC key remains secret. It does not encrypt backup contents.
- Restore verifies signature and SQLite integrity before writing to target.
- No network, browser, device, payment, purchase, deployment, or firewall action is present.
- Lease recovery remains at-least-once; SQLite is single-host, not distributed consensus.

## Run all tests
`python -m unittest discover -s tests -v`

Python 3.11+, standard library only.
