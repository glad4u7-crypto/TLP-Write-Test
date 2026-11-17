# APAA S09-C01 — Owner, Permission & Approval Security

## Personal Edition local Owner authentication

- Local mode remains loopback-only. It does not become a remote/LAN authentication design.
- First launch requires the Owner to create a passphrase of at least 12 characters and confirm it.
- The passphrase is stored only as a salted scrypt verifier; plaintext is never persisted.
- Failed login attempts are throttled in the owner-private SQLite authentication database. Five consecutive failures cause a five-minute lockout, which survives application restarts.
- Owner can rotate the passphrase from the authenticated sidebar after authenticating with the current passphrase; successful rotation revokes the current session and requires a fresh login.
- Authentication state is separate from project/task content and approval receipts.
- Payload-free local security events record first-run setup, successful/failed/locked login, logout and passphrase rotation/failure; a SQLite SHA-256 hash chain is verified before history is displayed or appended. A separately stored local chain head detects accidental tail truncation. Legacy event rows are sealed during one-time schema migration. Passphrases and submitted values are never included. This is tamper-evident, not immutable against an attacker who controls the local database and can recompute both records and head.
- The Owner sidebar also exposes the latest 25 tenant-scoped action-history records. The reader verifies the complete SQLite audit hash chain before showing metadata-only action/status/reason/timestamp; payloads and secrets are excluded. A tampered chain is displayed as unverified.
- Every enabled memory, knowledge, conversation, preference and checkpoint UI mutation now requires a fresh one-time ApprovalAuthority receipt bound to the exact action, canonical JSON payload, Owner tenant and current session. The wrapper snapshots the approved JSON once and passes only that private snapshot to the mutation operation; the operation cannot receive caller-mutated form values. Content-save forms require explicit consent; deletion buttons are the named confirmation event. Missing, malformed, expired, replayed or mismatched approvals block before audit intent and mutation.
- This module is a local single-owner gate, not a substitute for HTTPS/OIDC on any network-exposed deployment.

## App integration now present

- The local Owner gate runs before the local Principal, approval authority, gateway, memory store, project registry or task surfaces are initialized.
- First launch requires Owner passphrase setup; subsequent visits require explicit unlock.
- Successful login creates a fresh approval session scope.
- Logout and idle/absolute expiry clear identity-bound state, pending drafts and cached approval/runtime objects.
- Idle expiry: 15 minutes. Absolute session lifetime: 12 hours.
- Login throttling and payload-free authentication event history are persisted across restarts. The authenticated sidebar now exposes passphrase rotation and recent security events.
- The Owner authentication SQLite database is included in private backups and restored with the existing Owner verifier; the signing key remains excluded and is regenerated on restore.

## Verification

- Focused unit tests cover first-run setup, scrypt storage, wrong-password rejection, persistent lockout, passphrase rotation, payload-free security event persistence, hash-chain mutation/deletion detection, legacy event migration and symlink rejection.
- Streamlit AppTest coverage has been added for first-run gating, login, logout, idle expiry, absolute expiry and failed-login isolation.
- UI mutation tests verify fresh payload-bound receipts, approval-authority failure, non-JSON rejection, private payload snapshot isolation, missing/non-boolean approval blocking, prohibited/unknown action denial, and fail-closed intent/completion/failure audit semantics.
- Streamlit AppTest verifies the action-history UI after project creation and verifies that Owner passphrase rotation revokes the current session and requires reauthentication.
- Project creation is wired to the durable tenant-scoped idempotency ledger. Each reviewed project draft receives a fresh request key; duplicate/replayed dispatches are blocked. Current memory/knowledge/conversation/preference/checkpoint UI mutations use payload-bound receipts and metadata-only audit; they do not register external handlers.
- Backup/restore tests now verify Owner credential preservation.
- Earlier Owner-auth source head `b975d14f351bf42d72940fcea54103a2b4b384fe` completed PASS in run [#112](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/44008562833): Python 1,417 passed / 9 skipped, compile PASS, dependency audit PASS, browser smoke 9 passed. Later P79 exact-head run [#160](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/44019306207) also passed its Python, compile, dependency-audit and responsive browser jobs before the latest UI-boundary changes. The new payload-bound UI receipt and project idempotency integration changes require a fresh exact-head run. Physical Android acceptance remains separate and is not inferred from browser tests.
