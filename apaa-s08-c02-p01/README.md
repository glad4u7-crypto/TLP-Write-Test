# APAA S08-C02 — Durable Execution Foundation

P01: guarded in-process execution. P02: durable SQLite queue, leases, bounded retries and idempotency. P03: dead-letter queue, safe queued-task cancellation, and tamper-evident audit chain.

## Safety boundaries
- Deny by default: permission grant AND explicit user consent are both required.
- Only explicitly registered in-process handlers execute.
- No browser, device, network, payment, purchase, deployment, or firewall actions.
- Lease recovery is at-least-once, not exactly-once. Side-effecting adapters must enforce idempotency at the destination.
- Cancellation is supported only while QUEUED. Running Python handlers cannot be safely force-killed; cancellation returns false rather than pretending the work stopped.
- Retry exhaustion and exhausted leases move tasks to DEAD_LETTER for inspection; no automatic replay from that queue.
- Audit events use a global SHA-256 hash chain. This detects edits/deletions/reordering relative to the retained chain, but a local attacker able to rewrite the entire database can recompute it. Production requires an external append-only/WORM anchor or signed checkpoints.
- SQLite is a single-host persistence layer, not distributed consensus.

## Run tests
`python -m unittest discover -s tests -v`

Python 3.11+, standard library only.
