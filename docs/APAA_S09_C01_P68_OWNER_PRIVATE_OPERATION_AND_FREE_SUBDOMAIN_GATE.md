# APAA S09 C01 P68 — Owner-Private Operation and Free Subdomain Gate

**Status:** repository policy recorded; external deployment remains BLOCKED.  
**Owner decision date:** 2026-11-16.  
**Target:** one owner-controlled private APAA instance, initially for the owner alone.

## 1. Owner decision

The owner has confirmed:
- No domain is currently owned or available.
- APAA is to remain private and for the owner's personal use for now.
- No other user is to be admitted unless the owner later explicitly authorizes a named identity.
- No public signup, anonymous access, public directory/listing, or publicly usable agent endpoint is permitted.

This decision changes access policy, not the deployment authorization. It does not authorize creating a hosting account, registering a domain, accepting terms, enabling billing, or deploying.

## 2. Required private-by-default controls

A future deployment must satisfy all of the following before it is exposed to the internet:

1. Authentication is mandatory at the ingress and application layers; unauthenticated requests fail closed.
2. The only initially authorized principal is the owner's exact OIDC issuer + subject pair. Email-only matching is insufficient.
3. Public signup, self-service invitations, shared/demo access, anonymous sessions, and default/test identities are disabled.
4. Any future additional principal requires an explicit owner grant, is auditable, and can be revoked by the owner.
5. Session cookies are Secure, HttpOnly and SameSite appropriate; TLS is enforced; HTTP is redirected only where safe and no auth secret is sent over plaintext.
6. Secrets are injected by a protected host secret mechanism and are never stored in Git, image layers, logs, chat, or browser storage.
7. Persistent application data is stored outside ephemeral container filesystems, with tested restart and backup/restore behavior.
8. Administrative endpoints and owner-recovery functions are not publicly exposed; recovery requires the existing owner-controlled recovery protocol.
9. Default-deny network policy, least privilege, bounded resource use, audit integrity and safe shutdown remain in force.
10. Payment, purchases, checkout, trading and money movement remain prohibited. Auto-Run remains OFF. Worker and Browser remain DISABLED until their independent qualification and explicit owner approval.

## 3. Free hostname and hosting acceptance criteria

A provider is not acceptable merely because it offers a free URL or automatic HTTPS. Before selection, verify current terms and technical behavior for:

- provider-issued HTTPS subdomain without buying a domain;
- private access policy with OIDC or an equivalently strong owner-only identity gate;
- persistent storage with documented restart and backup/restore behavior;
- protected secret injection;
- no mandatory payment method, paid tier, trial conversion, or surprise usage charge for the intended workload;
- acceptable data location, account recovery, logging and deletion controls;
- no public access path that bypasses the identity gate.

If any mandatory item is absent or unclear, deployment remains BLOCKED. Do not weaken private access or persistence to make a free tier appear compatible. Do not select or provision a provider without explicit owner approval.

## 4. Android access

Android is the owner's primary client. The initial supported access target is a current Android browser over authenticated HTTPS. This is not proof of native Android packaging, Android device-control capability, or a safe local execution sandbox.

Before acceptance, perform the P64 physical Android checks and a live owner-only OIDC login/logout/session-expiry/revocation test from the actual device. Record the exact tested commit and sanitized evidence.

## 5. Work that can proceed without external services

Repository-only work may continue: static audits, unit/integration tests, policy checks, deployment preflight improvements, documentation, CI reconciliation and evidence tooling. Synthetic tests must be labeled as such. They cannot satisfy live host, live OIDC, physical HSM, independent anchor, physical Android, or independent reviewer gates.

## 6. Explicitly blocked external gates

- Owner-approved no-cost host and provider-issued HTTPS hostname.
- Owner-controlled OIDC issuer/client and exact owner subject.
- Protected persistent storage and secret injection.
- Live deployment preflight and HTTPS/OIDC verification.
- Physical Android acceptance.
- Physical compatible protected signing token and independent key-custody review.
- Independently administered monotonic anchor and backup/restore anti-rollback qualification.
- Real-host network enforcement evidence and independent security review.

## 7. Release state

S09 C01 remains **OPEN / NOT COMPLETE** while any mandatory external gate is blocked. C02 must not start. The existing PR remains Draft/Open/Unmerged. No merge, public deployment, production activation, host/firewall mutation, paid provider, domain purchase, account creation, or credential provisioning is authorized by this document.
