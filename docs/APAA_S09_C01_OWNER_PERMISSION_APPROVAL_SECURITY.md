# APAA S09-C01 — Owner, Permission & Approval Security

## Personal Edition local Owner authentication

- Local mode remains loopback-only. It does not become a remote/LAN authentication design.
- First launch requires the Owner to create a passphrase of at least 12 characters and confirm it.
- The passphrase is stored only as a salted scrypt verifier; plaintext is never persisted.
- Failed login attempts are throttled in the owner-private SQLite authentication database. Five consecutive failures cause a five-minute lockout, which survives application restarts.
- Owner can rotate the passphrase after authenticating with the current passphrase.
- Authentication state is separate from project/task content and approval receipts.
- This module is a local single-owner gate, not a substitute for HTTPS/OIDC on any network-exposed deployment.

## Session requirements for app wiring

- Do not instantiate the local Owner Principal, approval authority, gateway, memory store or project registry until login succeeds.
- Login creates a fresh approval session scope; logout/expiry clears identity-bound state and invalidates pending approvals.
- Idle expiry: 15 minutes. Absolute session lifetime: 12 hours.
- Explicit logout must clear pending drafts, approval capabilities and cached owner runtime objects.
- Browser refresh must not extend the session unless an authenticated request is actually processed.

## Verification

- Focused tests cover first-run setup, scrypt storage, wrong-password rejection, persistent lockout, passphrase rotation and symlink rejection.
- UI integration, logout/session expiry, exact-head CI and Android acceptance are separate gates and must not be inferred from the unit tests.
