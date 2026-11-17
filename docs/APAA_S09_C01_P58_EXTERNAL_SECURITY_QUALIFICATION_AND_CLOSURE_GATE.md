# APAA-S09-C01-P58 — External security qualification and closure gate

**Assessment date:** 2026-11-16  
**Repository head assessed:** c727bc5634f15b1b392e828d6da31b5b0bf4b7d4  
**Pull request:** #11 (open, draft, unmerged)  
**Decision:** C01 remains OPEN. Do not mark either external security requirement complete.

## Verified repository evidence

- The P50 PKCS#11 Ed25519 signer adapter is present. It requires sensitive, non-extractable key attributes and fails closed when the token does not report the required attributes.
- The P54 provisioning utility requests in-token Ed25519 key generation, requires explicit `--confirm-create`, prompts for the PIN without echo, refuses an existing key ID, requires the EdDSA mechanism hardware flag, and performs a sign/verify self-test.
- The P51 HTTPS+mTLS independent-anchor client is present. It enforces HTTPS, certificate validation, optional server-certificate pinning, bounded requests/responses, exact one-step CAS transitions, conflict handling, and fail-closed ambiguous-outcome handling.
- P56 lost-acknowledgement reconciliation re-reads the authoritative anchor and accepts only an exact target-state match.
- The assessed commit reports seven completed successful CI checks. This is repository CI evidence only, not physical HSM or independent-service qualification.

## Requirement A — TPM/HSM or equivalent protected signing key

**Repository implementation:** PRESENT  
**Physical hardware qualification:** NOT DONE  
**Production acceptance:** BLOCKED

Required evidence before closure:
1. Identify the exact physical HSM/token model, firmware, PKCS#11 module and serial/attested identity.
2. Confirm Ed25519 `CKK_EC_EDWARDS` and `CKM_EDDSA` support on that exact device; do not assume every TPM 2.0 supports Ed25519.
3. Generate a fresh key inside the device; prove private-key attributes are sensitive and non-extractable, and that private key material cannot be exported.
4. Independently verify the token identity and public-key fingerprint out of band.
5. Demonstrate signing after restart, PIN custody controls, access revocation, key rotation, old-key revocation, and the approved recovery/loss procedure.
6. Obtain independent review of device configuration, firmware, custody and test evidence.

A SoftHSM or mocked PKCS#11 provider is integration evidence only and must never be described as physical hardware qualification.

## Requirement B — Independent anti-rollback anchor

**Repository client implementation:** PRESENT  
**Independent production service:** NOT PROVISIONED / NOT CONNECTED  
**Provider durability and administrative independence:** NOT VERIFIED  
**Production acceptance:** BLOCKED

Required evidence before closure:
1. Select an owner-approved, free/owner-controlled service and document its cost and data location. No paid provider may be enabled without separate explicit approval.
2. Operate the anchor under a separate administrative identity and backup/restore domain from the APAA host and its primary database.
3. Provision narrowly scoped mTLS client identity, verify CA/server identity out of band, and test client-certificate revocation.
4. Demonstrate atomic compare-and-advance with concurrent clients and across service/process/host restarts.
5. Demonstrate durable acknowledgement, timeout-after-commit reconciliation, network partition, stale replica and fail-closed outage behavior.
6. Prove backup restore, deletion/recreation and disaster recovery cannot lower or reset the high-water mark. Use a separately protected immutable receipt/history or hardware monotonic root if the provider's ordinary backup model permits rollback.
7. Obtain independent review of service implementation, administration, storage durability, audit retention and recovery.

A remote database, TLS connection, local SQLite database, or mocked HTTP response is not by itself an independent anti-rollback anchor.

## Owner actions required

The repository cannot manufacture or attest physical hardware, provision an independently administered remote service, obtain device PINs/certificates, or perform real-world custody and disaster-recovery drills without the owner's approved hardware and environment. No credentials or secrets should be committed to GitHub.

When the owner provides an Ed25519-capable hardware token and approves a separate zero-cost anchor host/service, run the documented provisioning and qualification procedures and attach sanitized evidence (device model/firmware, public-key fingerprint, test results, anchor identity, CAS/restart/restore results). Never include PINs, private keys, client private keys, recovery secrets or raw credentials.

## Closure rule

P58 is a gate/evidence record, not a claim that external qualification has occurred. Keep PR #11 draft/open and keep S09/C01 OPEN until both requirements have all required evidence and independent review. Do not start C02 before then.

## Cost and permission guardrails

No paid API, paid provider, purchase, deployment, remote account, credential generation, hardware mutation or production change is authorized by this record. Preserve ask-first approval for any external connection or irreversible key operation.
