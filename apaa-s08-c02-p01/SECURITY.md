# Security invariants — P01

1. Deny by default: only registered handlers are callable.
2. Consent and permission are independent mandatory gates.
3. No payment, purchase, deployment, firewall, shell, browser, or network handler is supplied.
4. Task payloads are JSON data; they are never interpreted as code.
5. A task may move only QUEUED -> RUNNING -> SUCCEEDED/FAILED, or QUEUED -> BLOCKED.
6. The execution lock enforces one active handler per engine instance.
7. SQLite records lifecycle status, result, and failure details.
8. Handler failures are contained and recorded; they do not silently become success.

Limitations: this initial component provides process-local serialization, not distributed
locking across multiple application processes. Production deployment must add a
cross-process lease/lock, authenticated principal identity, signed consent evidence,
secret redaction, cancellation, and recovery for tasks left RUNNING after a crash.
