# APAA Architecture — v0.4.0 zero-cost foundation

## Product boundary

This repository contains a reusable general-purpose personal agent foundation. TradeLab Pro may later be a separate project workspace; market/trading execution is not part of this agent's permission scope. The current interface is a Streamlit web prototype, not a native Android app and not a fully autonomous device-control system.

## Runtime modes

### Authenticated mode

- Streamlit OIDC login supplies the verified identity claims.
- `core.streamlit_auth.principal_from_oidc_claims` validates required issuer, subject, expiry and issued-at constraints before creating a trusted `Principal`.
- Authenticated data ownership is keyed by the exact issuer + subject pair (`TenantKey`); project queries and mutations are tenant-scoped.
- Project persistence uses `SQLiteProjectStore` through `PersistentProjectRegistry`.
- Approval nonces and execution audit events use `SQLiteSecurityStore`; authenticated mode requires a configured stable signing secret (at least 32 bytes after hex decoding).
- Identity changes, logout, authentication loss and unsafe startup paths clear identity-bound capabilities and stop before protected UI/actions.
- Deployment must set `[apaa].require_auth = true`; this is an operator setting, not proof that a deployment has been hardened.

### Local prototype mode

- Authentication is not enforced. The UI warns that this mode must not be exposed publicly.
- Projects are held in session state and reset with the session.
- Approval authority is session-local and audit uses a local JSONL file.
- This mode is for private local development/testing only, not a public deployment or production security boundary.

## Provider boundary and zero-cost default

- The dashboard uses `RuleBasedProvider`, a deterministic offline planner.
- The active provider makes no network requests and requires no API key.
- External model adapters are dormant extension points and must remain disabled by default. No automatic fallback to a paid provider is permitted.
- A future paid provider requires a separate explicit user opt-in and separate cost approval; no credentials or billable service are needed for the current build.

## Approval and execution boundary

- The UI's current mutation is project creation only.
- Project creation requires a review step followed by a separate explicit Confirm-button event.
- The trusted controller issues a short-lived, HMAC-signed, canonical-payload-bound, single-use receipt. In authenticated mode it is additionally bound to tenant and session scope and consumed through durable nonce storage.
- The execution gateway accepts only explicitly registered handlers and records payload-free audit events.
- Durable audit intent is written before dispatch; if intent persistence fails, the handler is not called. Completion/failure is recorded after dispatch where available.
- Auto-Run defaults to an empty allowlist and remains disabled.
- No arbitrary shell, browser, email, network, filesystem or device adapter is registered. A task description or planner output cannot create a handler or grant approval.

## Persistence and audit

- Authenticated project data is stored in SQLite with issuer + subject ownership predicates.
- Authenticated approval nonce and audit events are stored transactionally in SQLite.
- Local prototype mode uses session-only project state and JSONL audit.
- SQLite backup/restore and audit tamper/fail-closed behavior have automated regression coverage; these tests establish local mechanics only, not off-site disaster recovery or independent tamper-proofing.
- JSONL locking is process-local; do not use the local fallback as a multi-process audit service.
- SQLite path checks and private-directory controls do not eliminate all hostile same-UID pathname races. Use a dedicated unprivileged OS identity, private non-writable parent paths and a supported single-writer topology.

## CI and verification

Two existing workflows are retained:
- **Agent Foundation CI** — pinned GitHub Actions, least-privilege read-only token permissions, bounded job time, dependency audit, compile check and automated tests.
- **Python Demo CI** — dependency installation, automated test suite and exact demo-output smoke test.

Do not add redundant workflows for the same checks. Treat every CI result as exact-commit, point-in-time evidence.

## Release blockers — production NOT APPROVED

The following require separate external or operational evidence; passing offline tests does not close them:

1. Live OIDC login/logout with two controlled identities and isolated browser profiles.
2. Real-browser cookies, CSRF, redirect allowlist, callback and reverse-proxy/TLS verification.
3. Repository-admin branch protection and required-check enforcement.
4. Independently administered immutable/append-only audit anchoring and rollback/outage tests.
5. Encrypted off-site backup, retention, monitoring, RPO/RTO and recurring restore drills.
6. Dedicated unprivileged OS identity, private paths, single-writer topology, host/container isolation and adversarial tests.
7. Named operational owner, incident response, evidence retention and independent review.

## Non-negotiable constraints

- Keep the default build zero-cost and offline.
- No payment, purchase, checkout, trading or money movement.
- Do not activate paid providers, request API keys or incur charges without a later separate explicit approval.
- Keep Auto-Run disabled.
- Do not register real-world action handlers as part of this S04 checkpoint.
- PR #5 remains Open + Draft. Do not merge, deploy or change its base branch.
