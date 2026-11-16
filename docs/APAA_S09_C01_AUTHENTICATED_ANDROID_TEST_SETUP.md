# APAA S09 C01 — Authenticated Android Test Setup Runbook

**Purpose:** prepare the minimum owner-controlled, non-production environment needed to complete the live Android authentication, session and permission-revocation checks. This is a preparation guide only: it does not deploy, publish, connect an identity provider, or enable task execution.

## Safety boundaries

- Use a dedicated non-production APAA test instance and test data only.
- Keep the instance private until OIDC is enforced and independently checked.
- Do not use the unauthenticated local-prototype mode on a public or shared network.
- Do not commit `.streamlit/secrets.toml`, client secrets, cookie secrets, signing secrets, access tokens, ID tokens, cookies, recovery codes or personal identity data.
- Keep Auto-Run OFF. Do not enable browser/worker execution, arbitrary tools, payments, purchases, paid APIs, host mutation, firewall changes, merge or deployment as part of this test.
- PC testing is optional. Android Chrome is the required client for this checkpoint.
- Do not use production accounts or production data.

## Owner prerequisites

The owner must arrange these before live testing can start:

1. A private, owner-controlled, non-production Streamlit test instance with HTTPS and a stable callback URL.
2. An OIDC provider / test tenant controlled by the owner.
3. Two separate test identities: one owner account and one reader account. Both must be controlled by the owner; do not share passwords.
4. A private persistent data location for the security and project SQLite databases. It must not be a temporary filesystem that disappears on restart.
5. A protected way to enter runtime secrets (platform secret manager or a local secrets file outside version control).
6. A way to inspect redacted server logs and browser storage without exporting secrets.

If any prerequisite is missing, mark live authentication or revocation checks **BLOCKED** and state the missing item. Do not create a public unauthenticated deployment as a workaround.

## OIDC configuration checklist

Configure the OIDC provider using its official setup instructions and the exact HTTPS callback URL for the chosen Streamlit test instance. Register only that callback URL; do not use wildcard redirect URIs.

Provide Streamlit's documented `[auth]` OIDC settings through the protected secret store, including the provider's redirect URI, client ID, client secret, cookie secret and discovery metadata URL as required by the selected provider. Generate unique high-entropy secrets for this test instance. Never place their values in this repository or in screenshots.

In the same protected configuration, set:

```toml
[apaa]
require_auth = true
approval_signing_secret_hex = "<64-or-more-hex-characters>"
security_db_path = "<private-persistent-path>/security.sqlite3"
project_db_path = "<private-persistent-path>/projects.sqlite3"
memory_db_path = "<private-persistent-path>/memory.sqlite3"
```

The signing secret must decode from hex to at least 32 random bytes. Generate it locally with a cryptographically secure random generator; do not reuse the OIDC client secret or cookie secret. Keep database paths private, persistent and writable only by the application identity. Do not put real secret values or machine-specific private paths in this file.

Before allowing a test account to sign in, verify that the app refuses to continue if `require_auth` is true but OIDC configuration is missing, that unauthenticated sessions are stopped, and that invalid/expired claims clear identity-bound state. The repository's automated AppTest suite covers these fail-closed cases, but does not prove the provider's live login flow.

## Android operator procedure

Use Android Chrome on the owner's phone. Record only non-sensitive environment metadata: date/time, Android version, Chrome version, test-instance build/commit and viewport orientation.

1. Open the private HTTPS test instance. Confirm the OIDC sign-in gate appears; do not proceed if the app displays the unauthenticated local-prototype warning.
2. Sign in as the owner. Confirm the displayed identity is the expected test subject.
3. Create a harmless test project using the review-then-confirm UI. Confirm no project is created before the explicit confirmation.
4. Sign out. Confirm the UI returns to the sign-in gate and identity-bound session state is cleared.
5. Sign in again. Confirm the prior session's approval receipt/capability cannot be reused.
6. On a separate browser profile/device controlled by the owner, sign in as the reader account. Before revocation, confirm only the explicitly granted read permission works.
7. As owner, revoke the reader's permission. Verify denial in the reader's already-open session and again after a fresh sign-in. A UI refresh alone is not sufficient evidence unless the backend authorization check is also observed.
8. Check portrait and landscape, keyboard overlap, scrolling, background/resume and reconnect behavior.
9. Inspect browser storage and URLs. Confirm no access tokens, ID tokens, approval receipts, private evidence or session secrets are exposed in local storage, URL parameters or service-worker caches.
10. Record each result as PASS, FAIL or BLOCKED with redacted evidence. Never include credentials, tokens, cookies, private project content or personal data.

## Evidence record template

- Test date/time (timezone):
- App commit:
- Android version / Chrome version:
- OIDC provider type (no tenant secrets):
- Owner test identity label (pseudonym only):
- Reader test identity label (pseudonym only):
- OIDC login / logout:
- Identity switch and stale receipt rejection:
- Owner grant / reader read:
- Owner revoke / existing reader denial:
- Fresh reader session denial:
- Browser storage and URL inspection:
- Portrait / landscape / keyboard / resume:
- Redacted evidence references:
- Failures and remaining blockers:

Do not mark physical Android or live OIDC PASS until the owner-run test has actually been completed and reviewed.

## What this runbook does not qualify

This procedure does not qualify a native Android APK, Android local hostile-code isolation, a Linux worker host, signer custody, durable anti-rollback, sink-side network enforcement, PC physical behavior or independent security review. Those remain separate gates. It also does not authorize production deployment.

**C01 remains OPEN / NOT COMPLETE. C02 must not start until all mandatory C01 gates are independently evidenced and approved.**
