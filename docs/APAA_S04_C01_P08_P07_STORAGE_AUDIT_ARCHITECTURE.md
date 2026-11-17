# APAA-S04-C01-P08-P07 — Persistent Tenant Storage & Audit Architecture

Status: **Architecture review prepared; implementation not started**

## Why P07 is next
P08-P06 automated CI is green, but live OIDC/browser verification remains blocked until a controlled provider, deployment URL, and two test identities are available. In parallel, the repository's current project registry is in-memory and session-scoped, while the audit log is a local JSONL file. These are explicit production-readiness gaps. P07 begins with architecture and threat-boundary definition; it does not bypass P06 or authorize production.

## Current implementation observed
- `ProjectRegistry` stores records in a Python dictionary and the Streamlit app instantiates it in `st.session_state`.
- Project ownership is keyed by `owner_subject`; owner-scoped list/read/update/delete methods exist.
- `JsonlAuditLog` uses a local JSONL file, SHA-256 hash chain, symlink avoidance, restrictive file mode, fsync, and an in-process per-path thread lock.
- The hash chain detects accidental modification but is not tamper-proof against an attacker able to rewrite the file and recompute hashes.
- The in-process lock does not coordinate multiple worker processes or hosts.
- Approval receipt nonces are stored in memory within one `ApprovalAuthority`; this is not a distributed replay-prevention store across workers/restarts.

## P07 design requirements

### Tenant-aware project persistence
1. Define a storage interface before choosing an implementation.
2. Every read and mutation must be scoped by both `issuer` and `subject`, not subject alone, to avoid collisions across identity providers.
3. Derive tenant identity exclusively from the validated server-side Principal; never accept owner/issuer from task text, query parameters, or client payload.
4. Use parameterized queries and database constraints; enforce owner checks at the persistence boundary, not only in UI code.
5. Add migration/version strategy and explicit handling for legacy projects with missing ownership. Never silently assign legacy records to the first user who logs in.
6. Add transaction boundaries and concurrency tests for create/update/delete and receipt consumption.
7. Keep development storage local and zero-cost; do not introduce hosted paid services or request API keys.

### Audit durability and integrity
1. Separate audit interface from storage implementation.
2. Define event schema with timestamp, action, result, reason code, principal issuer/subject fingerprint, request/correlation ID, and previous-entry reference. Do not store task payloads, secrets, bearer tokens, or raw OIDC claims.
3. Use process-safe atomic append/transaction semantics. A thread lock alone is insufficient for multiple processes.
4. Define file/database permissions, retention, rotation, backup, recovery, and access review.
5. For stronger tamper evidence, use an HMAC/signature key stored outside the audit data store or an independently protected append-only sink. Never commit keys.
6. Execution must fail closed if required audit persistence fails.

### Approval replay protection
1. Replace per-process consumed-nonce memory with a transactional, shared one-time-consumption store before multi-worker execution is considered.
2. Bind approval to issuer + subject, action, canonical payload digest, expiry, and nonce.
3. Consume atomically; concurrent duplicate submissions must have exactly one winner.
4. Keep explicit user confirmation required. No Auto-Run.

## Suggested implementation sequence
- P07-A: storage/audit interfaces and threat model.
- P07-B: local SQLite implementation with tenant composite key and migrations (only after design review).
- P07-C: process-safe audit and transactional receipt nonce store.
- P07-D: adversarial tests: cross-issuer subject collision, cross-tenant read/write/delete, concurrent receipt replay, restart persistence, audit corruption and unavailable storage.
- P07-E: migration/recovery notes and security review.

## Acceptance gates
- Tests prove a user cannot access another issuer/subject tenant's records by guessing IDs.
- Legacy unowned data remains quarantined until an explicit reviewed migration.
- Restart and separate app-process tests preserve tenant isolation and receipt single-use.
- Concurrent duplicate approval attempts result in one success at most.
- Audit failure blocks execution; no secrets or payload content appear in logs.
- Database and audit files are excluded from Git; no credentials are committed.
- CI covers all new migrations and adversarial tests.
- P06 live OIDC and two-user browser checks remain mandatory before production approval.

## Safety and cost boundaries
- Free/local-first implementation only. SQLite is a candidate, not yet approved.
- No paid database, hosted provider, external AI API, API key, or billable service is to be activated.
- No payment, purchase, checkout, trading, money movement, or financial execution.
- No shell, arbitrary network, browser automation, email, filesystem, or device-control handlers.
- Auto-Run remains disabled. PR remains draft; do not merge or deploy publicly.
