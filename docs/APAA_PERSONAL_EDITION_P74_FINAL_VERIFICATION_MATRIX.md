# APAA Personal Edition — P74 Final Verification Matrix

**Checkpoint:** APAA-PERSONAL-P74  
**Status:** Verification criteria and evidence inventory; final acceptance remains OPEN.

## Repository-level verification
| Area | Required check | P73 status |
|---|---|---|
| Runtime | Compile/import and runtime wiring tests | PASS |
| Persistent storage | SQLite persistence, owner scope, restart and integrity tests | PASS |
| Approval | Project action/payload/tenant/session binding, expiry and one-time nonce | PASS |
| Owner UI mutations | Explicit consent/approval argument on all nine mutation call sites; missing approval blocks before audit/dispatch | PASS — run #112 exact head |
| Owner action history | Tenant-scoped metadata-only history; full audit-chain verification before display; tamper detection | PASS — run #112 exact head |
| Owner passphrase UI | Rotation revokes session; new passphrase required for re-login | PASS — run #112 exact head |
| Owner authentication audit | Payload-free events, full SHA-256 chain + stored local head; verify before display/append and during backup/restore | IMPLEMENTED; exact-head Python suite PASS at `40d86044d04128a0de0a131166489b29af3996fb`; tamper-evident, not externally immutable |
| Audit | Intent-before-dispatch, metadata-only records, fail-closed behavior | PASS |
| Backup/restore | Archive validation, SQLite integrity, action-audit chain + Owner-auth event chain verification, atomic restore and key rotation | Automated tests PASS on code head `40d86044d04128a0de0a131166489b29af3996fb`; owner-operated device drill NOT RUN |
| Dependency security | pip-audit on exact tested head | PASS |
| Python regression | Full suite on exact head `b975d14f351bf42d72940fcea54103a2b4b384fe` | PASS — 1,417 passed, 9 skipped; run #112 |
| Browser smoke | Android/desktop Chromium login-aware viewport and workflow checks | PASS — 9 passed; run #112 |
| Browser execution | Security-qualified implementation and independent review | NOT IMPLEMENTED; DISABLED |
| Android | Physical A01–A12 on the actual phone using local Owner authentication | NOT RUN; Termux/runtime compatibility unqualified |
| Local Owner identity | Passphrase setup/login, lockout, logout, idle/absolute expiry and identity-bound session cleanup | Automated PASS; physical Android run NOT RUN |
| Remote OIDC | HTTPS/OIDC and second-account grant/revoke for a future remote deployment | OUT OF CURRENT PERSONAL EDITION SCOPE |
| Local key protection | Owner-only local signing-key file, backup exclusion and restore key rotation | Automated PASS |
| Enterprise key custody/anti-rollback | HSM/TPM and independent remote anchor | DEFERRED; not a Personal Edition gate |
| Real-host egress | Host/network enforcement and bypass testing | NOT RUN |

## Latest Owner authentication hardening evidence

- P77 code head: `40d86044d04128a0de0a131166489b29af3996fb`.
- P73 Verification run #126: Python complete suite, compile and dependency audit PASS; responsive Android/Desktop browser smoke was still running when this matrix update was prepared. Re-check the exact-head workflow before marking the complete workflow PASS.
- Owner-auth event history now uses a local SHA-256 chain and separately stored local head. It detects row mutation and tail deletion but is not an independent external anchor.

## Evidence rules
- Every PASS identifies exact commit SHA, command/workflow, date and result.
- An earlier commit's result does not prove a later commit.
- Chromium emulation is not physical Android acceptance.
- Unit tests are not independent security review.
- An audit hash chain is tamper-evident, not immutable against an attacker controlling the host/database.
- Documentation of a gate is not implementation or passing evidence.
- Missing environment or unavailable device is BLOCKED/NOT RUN, never PASS.

## Final acceptance criteria
Call the repository verified only when all applicable exact-head automated checks pass. Call it physically accepted only after owner-operated Android and recovery tests pass. Call Browser Control security-qualified only after browser/network transport, host egress enforcement and independent review have evidence. Enterprise HSM/TPM and remote anti-rollback are deferred from Personal Edition.

C01 remains OPEN until mandatory gates are independently evidenced and the owner approves closure. C02 must not start before C01 completion and explicit owner approval.

## Safety invariants
- Owner-first; no public signup by default.
- Ask First; Auto-Run OFF.
- Free-only; no paid provider, hosting, API key or billable service.
- No payment, purchase, checkout, trading, investment order or money movement.
- No merge or deployment without explicit owner approval.
- Browser and Worker execution remain disabled until every browser security gate passes.
