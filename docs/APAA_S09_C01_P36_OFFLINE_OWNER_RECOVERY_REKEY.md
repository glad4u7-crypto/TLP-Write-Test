# APAA S09-C01 — P36 Offline Owner Recovery & Re-key

**Status:** implementation added; exact-head CI pending; production trust provisioning NOT QUALIFIED  
**PR:** #11 — Draft / Open / Unmerged  
**Checkpoint:** APAA-S09-C01-P36-OFFLINE-OWNER-RECOVERY-REKEY

## Implemented protocol

- \`core/offline_owner_recovery.py\` verifies an offline recovery envelope signed with Ed25519 by an authorized operator key and a distinct independently administered approver key.
- The signed canonical payload binds action, expected revision, old/new owner-generation digests, change ID, reason code, nonce, validity window and both key IDs.
- Operator and approver trust domains reject duplicate IDs and shared public keys. Public keys are supplied by trusted offline policy; no private key or credential is stored in the repository.
- Requests are short-lived and there is no browser, Streamlit, task, model or ordinary API route to initiate recovery.
- SQLite owner-generation CAS and hash-chain audit commit atomically. Audit records contain key fingerprints and bounded metadata, not raw owner subjects, tokens or private keys.
- An independently administered monotonic anchor is mandatory. Local SQLite is never treated as the rollback anchor.
- If the anchor advances but local SQLite commit is interrupted, the same still-valid dual-signed envelope can resume the exact transition. No rollback is attempted.

## Crash and recovery semantics

The external anchor and local SQLite cannot share one atomic transaction. The protocol advances the independent anchor first, then performs local CAS. A crash between them leaves the anchor one revision ahead; \`inspect()\` reports \`ANCHOR_AHEAD_RESUMABLE\`. Re-presenting the identical, valid, unexpired, dual-signed envelope resumes local commit. Other divergence is blocked as \`DIVERGED_BLOCKED\`; there is no automatic rollback or owner fallback.

## Test coverage

Dual-control re-key, invalid approval, same-key rejection, expiry and malformed requests, stale generation/revision, anchor outage, crash/resume, tampered resume, revocation, and audit privacy/integrity. Tests use ephemeral Ed25519 keys and a test-only in-memory anchor; neither is a production credential or anchor.

## NOT IMPLEMENTED / NOT QUALIFIED

- Production monotonic-anchor adapter, HSM/TPM, independent account or protected offline key custody.
- Human operator/approver identity enrollment and verification.
- Production signing ceremony or protected key rotation.
- Global Admin API/UI activation and deployment config integration.
- Live OIDC, physical Android, production Linux host and independent security review.

A test anchor is never a deployment option. Production activation remains blocked until independent durable anchor and out-of-band key custody are qualified.

## Safety

Global Owner remains inactive. No real credentials, private keys, tokens, paid providers, payment, deployment, merge, worker activation or Auto-Run were used or enabled. PR #11 remains Draft/Open/Unmerged. S09-C01 remains OPEN / NOT COMPLETE.
