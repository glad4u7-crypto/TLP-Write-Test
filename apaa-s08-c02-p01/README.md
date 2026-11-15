# APAA S08-C02 — Durable Execution Foundation

P01–P03: guarded in-process execution, durable SQLite queue, leases/retries, idempotency, dead-letter queue, queued cancellation and hash-chained audit.

P04: strict action/payload validation, versioned policy registry, scoped expiring/revocable consent ledger, signed SQLite backup/restore.

P05 integrates P04 controls into the actual execution path:
- Task creation validates normalized action identifiers and JSON-safe bounded payloads.
- Every task records a policy version (default v1).
- Execution requires an explicitly enabled matching action+policy version; missing policy denies.
- Explicit caller consent creates a persisted, task-scoped grant with a default 15-minute expiry.
- Policy and consent are checked again immediately before handler invocation.
- Consent can be revoked with `engine.revoke_consent(task_id)`; policies can be disabled with `engine.set_policy(action, version, False)`.
- Missing, expired, revoked, wrong-scope consent or disabled/missing policy blocks the task before the handler is called.

## Minimal safe usage
```python
engine.register("docs.read", handler)
engine.set_policy("docs.read", "v1", True)  # explicit administrator policy
task = Task.create("docs.read", {"document_id": "example"},
                   permission_granted=True, user_consented=True,
                   policy_version="v1")
task_id = engine.submit(task)  # consent grant expires after 15 minutes by default
engine.run_next()
```

## Critical safety boundaries
- This is still an in-process adapter foundation, not a production autonomous agent.
- The caller-provided `user_consented=True` must only be set after a real, attributable user approval event. The library cannot prove UI identity by itself.
- Policy and consent are re-checked immediately before the handler. A highly concurrent system would need an atomic authorization lease or transaction spanning authorization and side-effect dispatch to eliminate the final check/use race.
- HMAC signing key remains caller-supplied (minimum 32 bytes), never stored in the database; signed backup is not encryption.
- No network, browser, device, payment, purchase, deployment, or firewall action is present.
- Lease recovery remains at-least-once; SQLite is single-host, not distributed consensus.

## Run all tests
`python -m unittest discover -s tests -v`

Python 3.11+, standard library only.
