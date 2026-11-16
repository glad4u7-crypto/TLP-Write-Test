# APAA S09 C01 — Repository Action Audit Remediation 01

**Assessment date:** 2026-11-16  
**Repository:** `glad4u7-crypto/TLP-Write-Test`  
**Audited code/test head:** `f81be85ef75b3d0b26ee3e3e80dacb921db16ad6`  
**Remediation branch:** `apaa-s09-c01-action-audit-remediation-01`  
**PR:** #12 — Draft / Open / Unmerged  
**Disposition:** Repository findings addressed in code/tests; exact-head CI for the audited code/test head is recorded separately by GitHub Actions. External qualification remains BLOCKED; C01 remains OPEN; C02 NOT STARTED.

## 1. Findings and remediation

| Finding | Remediation | Software status |
|---|---|---|
| Recovery inspection could report CONSISTENT despite a corrupt audit chain | `OfflineOwnerRecoveryService.inspect()` verifies the audit chain and returns `AUDIT_INTEGRITY_BLOCKED` before consistency/resumability dispositions | FIXED |
| P62 tampering tests did not assert the inspection disposition | Field/hash/deletion tampering and audit reordering tests now assert `AUDIT_INTEGRITY_BLOCKED`, and verify recovery is denied without advancing the anchor | FIXED |
| P61 reference anchor's anti-rollback floor was process-local | The reference model now accepts a separately persisted protected floor; tests recreate the adapter and test data-store rollback while retaining that floor | FIXED IN REFERENCE MODEL |
| APAA Security CI used mutable action tags and cancelled in-flight runs | Checkout and setup-python are pinned to full commit SHAs; concurrency is commit/event scoped and `cancel-in-progress: false` | FIXED |
| Workflow policy tests covered only a subset of repository workflows and did not bound each job independently | Repository-wide checks cover all workflow YAML files; every job is required to declare its own timeout and each workflow to use non-cancelling, commit-scoped concurrency | FIXED |

## 2. Verification boundary

The P61 protected-floor fixture is a deterministic software contract model. It does **not** prove that a production anchor is independently administered, separately backed up, or resistant to compromise of both domains. Likewise, CI mocks and software tests do not qualify a physical HSM/token or an independently operated production service.

The P62 tests establish the tested SQLite/audit software behavior. They do not substitute for physical power-loss, multi-host recovery, immutable external audit checkpoint, or owner-host disaster-recovery drills.

## 3. Release and safety disposition

- PR #12 remains Draft / Open / Unmerged.
- No merge, deployment, production activation, host/firewall mutation, or C02 start.
- No paid provider/service, payment, purchase, or new cost.
- No secret, PIN, private key, recovery code, or client credential committed.
- Owner-first authorization and ask-first approval remain in force.
- Auto-Run remains OFF; Worker and Browser remain DISABLED.

## 4. Remaining external blockers

The software findings above do not close the mandatory external gates:
- physical protected-key identity, custody, real rotation/revocation and recovery;
- independently administered production anti-rollback anchor and separate backup domain;
- owner-approved disposable host/runtime and real OCI lifecycle;
- sink-side egress verification and real crash/cleanup drills;
- physical Android owner acceptance and controlled two-account OIDC grant/revoke;
- independent security review and explicit owner acceptance.

**Final disposition:** Repository action-audit remediation is software-complete when the exact candidate head passes its required CI. C01 remains **OPEN / NO-GO** until all mandatory external evidence and independent approval are accepted. C02 remains **NOT STARTED**.
