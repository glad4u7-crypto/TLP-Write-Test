# APAA S09-C01 — Owner, Permission & Approval Security

## Personal Edition local Owner authentication

- Local mode remains loopback-only. It does not become a remote/LAN authentication design.
- First launch requires the Owner to create a passphrase of at least 12 characters and confirm it.
- The passphrase is stored only as a salted scrypt verifier; plaintext is never persisted.
- Failed login attempts are throttled in the owner-private SQLite authentication database. Five consecutive failures cause a five-minute lockout, which survives application restarts.
- Owner can rotate the passphrase after authenticating with the current passphrase.
- Authentication state is separate from project/task content and approval receipts.
- This module is a local single-owner gate, not a substitute for HTTPS/OIDC on any network-exposed deployment.

## App integration now present

- The local Owner gate runs before the local Principal, approval authority, gateway, memory store, project registry or task surfaces are initialized.
- First launch requires Owner passphrase setup; subsequent visits require explicit unlock.
- Successful login creates a fresh approval session scope.
- Logout and idle/absolute expiry clear identity-bound state, pending drafts and cached approval/runtime objects.
- Idle expiry: 15 minutes. Absolute session lifetime: 12 hours.
- Login throttling is persisted across restarts. Passphrase rotation is available in the authentication service; a dedicated UI control remains pending.
- The Owner authentication SQLite database is included in private backups and restored with the existing Owner verifier; the signing key remains excluded and is regenerated on restore.

## Verification

- Focused unit tests cover first-run setup, scrypt storage, wrong-password rejection, persistent lockout, passphrase rotation and symlink rejection.
- Streamlit AppTest coverage has been added for first-run gating, login, logout, idle expiry, absolute expiry and failed-login isolation.
- Backup/restore tests now verify Owner credential preservation.
- Exact-head CI is still required before any PASS claim. Physical Android acceptance remains separate and is not inferred from browser tests.
