# APAA-S09-C01-P67 — Private HTTPS deployment blueprint

**Status:** Provider-neutral preparation only. No hosting account or service has been provisioned.  
**Target:** One owner-controlled, non-production APAA instance usable from Android Chrome.  
**Release posture:** C01 OPEN / NOT COMPLETE; production NOT APPROVED.

## 1. What private HTTPS means

HTTPS transport means the browser connects to the exact approved hostname using a valid TLS certificate. Private application access means OIDC is required before workspace data is shown, and the exact owner identity is provisioned server-side as an issuer + subject pair. No anonymous access, public registration or first-login owner bootstrap is allowed.

An internet-routable HTTPS hostname is not automatically a private network. If network-level privacy is required, the selected host must additionally support an owner-controlled private network/VPN path that works from Android. Do not assume an ordinary hosted app URL meets that stronger requirement.

## 2. Required deployment topology

Use one application instance until the application is redesigned and independently qualified for multi-instance operation:

1. Android Chrome.
2. HTTPS ingress / TLS termination with strict host routing.
3. Streamlit application running as a dedicated non-root identity.
4. One private persistent volume mounted outside the code checkout.
5. Protected platform secret store injected at runtime.

Expose only the required HTTPS application endpoint. Do not expose database files or administrative interfaces through the app hostname. The current app uses SQLite and process-local Streamlit session state; do not run multiple replicas against one shared SQLite volume or claim high availability. Restart must preserve all four databases. Backup/restore must be tested before production claims.

## 3. Required server-side settings

The selected host's protected secret store must provide the OIDC [auth] settings and these [apaa] settings. The values below are descriptive placeholders only and must be replaced locally by the owner/operator; never paste real values into chat or GitHub.

    [apaa]
    require_auth = true
    approval_signing_secret_hex = "GENERATE-64-OR-MORE-HEX-CHARACTERS-LOCALLY"
    trusted_identity_issuers = ["https://OWNER-IDP.example"]
    security_db_path = "/private-data/security.sqlite3"
    project_db_path = "/private-data/projects.sqlite3"
    memory_db_path = "/private-data/memory.sqlite3"
    trusted_identity_directory_db_path = "/private-data/identities.sqlite3"

    [apaa.global_owner]
    issuer = "https://OWNER-IDP.example"
    subject = "OWNER-OIDC-SUBJECT-FROM-TRUSTED-ADMIN-PROVISIONING"

Configure OIDC redirect_uri to the exact HTTPS callback URL registered with the selected identity provider. Do not use wildcard redirect URIs. OIDC client secret, cookie secret and approval signing secret belong only in the platform's protected secret store.

Rules:

- Global owner issuer must exactly match an entry in the unique trusted_identity_issuers list.
- Owner subject is the immutable OIDC sub claim, not a display name or email. Provision it through the identity provider's trusted admin view; do not send it to ChatGPT.
- All four database paths must be absolute, distinct, outside the application checkout and on private persistent storage.
- Each database parent directory must be owner-only (POSIX 0700 or stricter); existing database files must be owner-only (0600 or stricter).
- Approval signing secret must be generated using a cryptographically secure random source and decode to at least 32 bytes. Do not reuse OIDC secrets.
- Never commit a real secrets file or expose secret values in logs, screenshots, issues or evidence.

Run the read-only configuration preflight from the trusted deployment shell:

    python scripts/preflight_android_deployment.py --secrets /absolute/private/path/secrets.toml

A configuration PASS does not prove that the host is private, TLS is correct, OIDC login works or persistent storage survives restart.

## 4. Host and network acceptance

Before the first owner login, verify and record only non-sensitive facts:

- Owner controls the hosting account, project, hostname, DNS and billing settings.
- The plan is confirmed free and does not auto-upgrade, require paid add-ons or incur usage charges. If this cannot be guaranteed, stop.
- TLS certificate hostname and chain validate from Android Chrome; HTTP redirects to HTTPS.
- Only the required ingress endpoint is reachable; database files and admin interfaces are not internet-accessible.
- App process is non-root; secrets are not baked into source or container image.
- App data is on a private persistent volume with owner-only directory permissions.
- Restart preserves data; backup/restore preserves owner access, tenant isolation and revocation state.
- Logs redact OIDC codes, tokens, cookies, authorization headers, secret values and private user content.
- No public signup, anonymous workspace, Auto-Run, browser worker, task execution or paid provider is activated.

Do not make DNS, firewall, billing, identity-provider or host-account changes automatically. Those require the owner's direct control and explicit approval.

## 5. Android acceptance sequence

After host checks pass:

1. Open the exact HTTPS URL in Android Chrome; verify certificate and hostname.
2. Confirm the OIDC sign-in gate appears immediately; local prototype mode must not be visible.
3. Sign in with the owner's controlled test identity.
4. Confirm only the exact configured issuer + subject receives owner privileges. A different account must not become owner by logging in first.
5. Use a harmless test project; confirm review-then-confirm and no task execution.
6. Sign out and use browser back; protected content must be denied server-side.
7. Use a second owner-controlled test identity in a separate browser profile; confirm no access by default.
8. Grant only a supported read-only permission, verify exact scope, revoke it, and verify immediate denial in the existing session and after re-login.
9. Restart the app and verify persistence, owner access and revocation state.
10. Complete physical Android P64 A01–A12.

Missing host, account, device or evidence means BLOCKED, not PASS.

## 6. Provider selection gate

The repository contains no owner-approved hosting provider or identity provider. Do not silently choose a vendor or create a hosted service. The owner must identify an existing private server/hosting account or explicitly approve a named free provider after checking current privacy, persistent-volume, OIDC, data-residency and cost terms.

If no free tier can provide protected secrets, durable private storage and owner-controlled access without surprise charges, deployment stays BLOCKED. Do not weaken authentication or storage requirements to fit a free tier.

## 7. Status

- Provider-neutral deployment architecture: DOCUMENTED.
- Owner-first preflight: IMPLEMENTED in P67 code changes; exact-head CI pending.
- Host/provider chosen: PENDING owner approval.
- OIDC tenant and two test identities: PENDING owner provisioning.
- Protected secrets and private persistent volume: PENDING host provisioning.
- TLS, live login, restart/restore and physical Android tests: BLOCKED pending host.
- Production: NOT APPROVED.
- C01: OPEN / NOT COMPLETE; C02: NOT STARTED.
- No deployment, billing change, paid service, API key, merge or production activation performed.
