# APAA-S09-C01-P69 — Private Android test environment and owner acceptance preparation

**Date:** 2026-11-17  
**Branch:** `apaa-s09-c01-action-audit-remediation-01`  
**Status:** Repository preparation only; external environment remains BLOCKED.  
**Target:** One owner-controlled, no-cost, private-by-default APAA test instance accessed from the owner's Android phone.

## 1. Purpose and boundary

P69 turns the P64–P68 preparation into an ordered, evidence-driven operator runbook. It does not provision a hosting account, domain, identity provider, test identity, secret, database, key, anchor or network resource. It does not deploy the app.

The Android phone is the owner's control-plane device. It is not an untrusted-code sandbox or a substitute for the separately qualified Linux worker. The current application remains a Streamlit web prototype, not a native APK.

## 2. Non-negotiable safety rules

- Owner-only access initially; no public signup, anonymous access, public demo, self-service invitation or default owner bootstrap.
- Owner identity is the exact trusted OIDC issuer + immutable subject pair. Email/display-name matching is insufficient.
- Keep Auto-Run OFF and Worker/Browser execution DISABLED.
- Use only non-sensitive disposable test data.
- Never place credentials, OIDC codes, cookies, tokens, signing keys, PINs, recovery codes, device identifiers or private screenshots in ChatGPT, GitHub, repository files or issue comments.
- No paid API/provider, paid hosting, payment method, trial conversion, usage charge, domain purchase, payment, purchase, checkout, trading or money movement.
- Do not weaken authentication, persistence, TLS or privacy requirements to fit a free plan.
- No host, DNS, firewall, billing, identity-provider, account, key or production setting changes without direct owner control and explicit approval.
- Any unexpected certificate warning, hostname, redirect, permission prompt, public route or access grant is a STOP condition.

## 3. Gate 0 — repository and code identity

Before external testing, record locally:

1. Exact full Git commit SHA being tested.
2. PR number, branch, and whether all required CI workflows completed successfully on that exact SHA.
3. Application dependency/runtime versions and deployment image/source digest.
4. Whether the working tree and configuration are the reviewed versions.

A CI result from a different SHA is not evidence for the tested build. A documentation/configuration preflight PASS is not deployment PASS.

## 4. Gate 1 — provider and private-host eligibility

The owner must identify an existing account or explicitly approve a named provider before any provisioning. Verify from current provider terms and actual configuration:

| Requirement | Accept condition | Otherwise |
|---|---|---|
| Cost | No required payment method, paid add-on, trial conversion or usage charge for the intended test | BLOCKED |
| Hostname | Provider-issued HTTPS subdomain is available without buying a domain | BLOCKED |
| Privacy | An unauthenticated visitor cannot reach app content or an alternate public route | BLOCKED |
| Identity | Mandatory OIDC or equivalent strong owner-only identity gate, with exact owner issuer + subject | BLOCKED |
| Secrets | Protected runtime secret injection; secrets not baked into source/image | BLOCKED |
| Persistence | Private durable volume outside ephemeral container filesystem | BLOCKED |
| Recovery | Documented restart and backup/restore path with owner-controlled recovery | BLOCKED |
| Operations | Owner can stop, revoke, export and delete the test deployment | BLOCKED |
| Data handling | Acceptable region, logging, retention and deletion terms | BLOCKED |

A free URL or automatic TLS alone is not enough. If a provider cannot meet every mandatory row, do not create the service.

## 5. Gate 2 — owner-controlled configuration

Only on an approved host, the owner/operator configures:

- HTTPS ingress with a valid certificate for the exact hostname; HTTP must not expose application content.
- Mandatory OIDC login and a trusted issuer allowlist.
- One pre-provisioned owner issuer + subject pair; no first-login-wins bootstrap.
- OIDC redirect URI restricted to the exact HTTPS callback.
- Protected OIDC client secret, cookie secret and independent approval-signing secret.
- Four distinct absolute database paths (security, project, memory and trusted identity directory) outside the checkout and on private persistent storage.
- Owner-only directory/file permissions; non-root app process; no public database or admin endpoint.
- Log redaction for credentials, tokens, cookies, authorization headers and private content.
- One application instance only unless multi-instance and SQLite semantics are separately redesigned and qualified.

Do not send real configuration values to ChatGPT or commit them to Git. Use the read-only command documented in P66:

```bash
python scripts/preflight_android_deployment.py --secrets /absolute/private/path/secrets.toml
```

Run it only from the trusted deployment shell using a protected local secret mount. Do not export provider-managed secrets into a plaintext file merely to satisfy this script; adapt through a separately reviewed provider-native integration if necessary.

## 6. Gate 3 — host acceptance before login

The owner/operator records sanitized observations:

- Exact hostname and certificate validity from Android Chrome.
- HTTP-to-HTTPS behavior and absence of alternate unauthenticated routes.
- Authentication gate before any workspace data is rendered.
- Owner-only authorization and absence of public signup/invitation.
- Non-root runtime and protected secret injection.
- Private persistent volume and restrictive permissions.
- No public database/admin endpoints.
- No secrets or private content in logs.
- App restart preserves data and owner access.
- Backup/restore preserves data integrity, owner access and revocation state.

A test that cannot be performed is BLOCKED. A failed access-control, TLS, privacy or persistence check is FAIL and requires stopping the test.

## 7. Gate 4 — physical Android owner acceptance

Use the existing P64 A01–A12 checklist on the actual owner's Android phone. Record the exact code SHA, Android major version, browser/version, UTC test time and PASS/FAIL/BLOCKED per test. Do not upload raw screenshots or personal/device identifiers to the repository.

Android browser emulation in CI is supplemental regression only; it never counts as physical-device PASS. PC hardware is not required for the Android-only delivery path.

## 8. Gate 5 — live two-account OIDC grant/revoke

Only after host and owner login checks pass:

1. Use two separately controlled test identities in isolated browser profiles/sessions.
2. Confirm the second identity has no access by default.
3. Owner grants only a supported, explicitly scoped read-only permission to one disposable test project.
4. Verify all ungranted projects and all mutation, execution, administration, memory, checkpoint and resource-write paths are denied.
5. Owner revokes the grant.
6. Verify the already-authenticated second session is denied on its next server authorization check, then verify again after re-login and app restart.
7. Confirm the owner retains access and the audit record contains no secrets.

If the second identity is unavailable, mark BLOCKED. Synthetic principals, mocked OIDC and browser emulation cannot satisfy this gate.

## 9. Evidence handling and acceptance

Keep raw evidence in an owner-controlled restricted location. The repository may contain only sanitized status summaries that disclose no account identifiers, secrets, device serials, private URLs, screenshots or personal data.

Each evidence record must bind:
- exact tested commit SHA;
- test ID and result;
- UTC timestamp;
- test environment class (CI, emulated, physical Android, owner host);
- operator alias;
- redacted observation;
- independent reviewer disposition.

PASS is permitted only for a test actually performed in its required environment. CI PASS cannot be promoted to physical Android, live OIDC, production host, physical signer or independent-anchor PASS. Independent review must be performed by a genuinely separate reviewer and must verify the evidence and exact code SHA.

## 10. Stop, rollback and cleanup

Stop immediately on unexpected public access, owner identity mismatch, stale-session access after revocation, certificate warning, secret exposure, unauthorized action, persistence loss or unexplained cost. The owner/operator then:

1. disables ingress or stops the test service through the provider's owner console;
2. revokes affected test identity sessions and credentials through the trusted provider console;
3. preserves sanitized audit facts without copying secrets;
4. restores only from a known-good owner-controlled backup after integrity verification;
5. deletes the disposable deployment and data when the owner decides testing is complete;
6. records the outcome as FAIL or BLOCKED, never PASS by assumption.

Do not automate provider-console, DNS, firewall, billing or identity-provider changes.

## 11. Current disposition

| Item | Status |
|---|---|
| P64 physical Android procedure | DOCUMENTED; physical execution PENDING |
| P66 read-only configuration preflight | IMPLEMENTED; host execution BLOCKED |
| P67 provider-neutral HTTPS blueprint | DOCUMENTED |
| P68 owner-private/free-subdomain policy | DOCUMENTED |
| P69 operator sequence and evidence gates | DOCUMENTED in this file |
| Approved no-cost private host | BLOCKED — owner/provider approval and current-term verification required |
| OIDC issuer/client and two controlled identities | BLOCKED — owner provisioning required |
| Physical Android A01–A12 | BLOCKED — approved host required |
| Live grant/revoke and restart/restore | BLOCKED — live host and identities required |
| Physical protected signer / independent anchor / real-host network | BLOCKED — separate external qualification |
| Independent review and owner acceptance | BLOCKED |
| C01 | OPEN / NOT COMPLETE |
| C02 | NOT STARTED |

**Release lock:** Keep PR Draft/Open/Unmerged. No deployment, merge, public exposure, production activation, paid service, payment, domain purchase, credential provisioning or host mutation is authorized by P69.
