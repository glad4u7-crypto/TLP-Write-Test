# APAA-S09-C01-P59 — P58 CI verification and remaining qualification matrix

**Assessment date:** 2026-11-16  
**Scope:** Verify the P58 documentation commit and consolidate the remaining C01 qualification work.  
**Pull request:** #11 — preserve Draft / Open / Unmerged.  
**Decision:** P59 repository-CI verification PASS; S09/C01 remains OPEN.

## 1. P58 exact-commit CI verification

P58 documentation commit:
- Commit: `dd73f1fa4b853015579cdba31510e244e486ceaf`
- File: `docs/APAA_S09_C01_P58_EXTERNAL_SECURITY_QUALIFICATION_AND_CLOSURE_GATE.md`

GitHub Actions returned four workflow runs for this exact commit. All four completed with conclusion `success`:

| Workflow | Run | Result |
|---|---:|---|
| Agent Foundation CI | 1183 | PASS |
| Python Demo CI | 1272 | PASS |
| P23 Rootless Podman Executor Integration | 294 | PASS |
| P20 Rootless Podman Runtime Qualification | 312 | PASS |

**P58 result: 4/4 returned PR-triggered workflows PASS.** This verifies the P58 documentation commit against the repository's PR CI workflows. It is not evidence of a physical HSM, an independently administered remote anchor, or real-host production qualification. The P57 implementation head separately recorded seven checks PASS; those results must not be conflated with P58's four returned runs.

## 2. Consolidated remaining work

### P60 — Protected signing-key lifecycle tests
- Exercise key rotation and verify signatures across the defined transition.
- Verify old-key revocation is enforced and stale/revoked keys fail closed.
- Exercise recovery after key loss or interrupted rotation; ensure no silent fallback to an unprotected software key.
- Separate software/mock contract evidence from physical-token qualification.
- Physical qualification remains BLOCKED until an owner-approved Ed25519-capable hardware token is available and independently identified.

### P61 — Independent anchor durability and anti-rollback
- Exercise atomic compare-and-advance under concurrent clients.
- Verify persistence across service/process restart and acknowledged-write recovery.
- Test timeout-after-commit reconciliation, outage and stale-state fail-closed behavior.
- Test backup/restore, deletion/recreation and disaster recovery against high-water-mark rollback.
- Verify separate administration and backup domain.
- Independent-service qualification remains BLOCKED until an owner-approved zero-cost service/host exists in a separate administrative domain. Local SQLite and mocked HTTP tests do not satisfy this gate.

### P62 — Recovery, crash and audit integrity
- Concurrent owner-recovery race tests; prove one valid winner and no partial state.
- Crash injection around prepare, anchor CAS, local commit and audit append.
- Audit tampering, truncation, deletion, reordering and invalid-chain detection.
- Verify failure leaves owner state locked/fail-closed and that safe recovery is possible.
- Keep all tests disposable and non-production; no live credentials or irreversible key operation without explicit approval.

### P63 — Final evidence review and closure decision
- Reconcile exact commit and CI evidence for each code/test change.
- Confirm each mandatory external gate as PASS, BLOCKED or NOT APPLICABLE with evidence.
- Independent human review and owner approval remain required.
- C01 may close only when every mandatory gate has accepted evidence; otherwise report the precise blocker and keep C01 OPEN.

## 3. External qualification gates that remain unproven

1. Physical HSM/token identity, firmware, Ed25519 support, non-extractability and custody.
2. Real-token key rotation, revocation, restart continuity and recovery.
3. Independent remote anchor identity, separate administration and backup domain.
4. Durable monotonic behavior across restart, concurrent access, backup/restore and disaster recovery.
5. Independent security review and explicit owner approval.

No mock, local-only, documentation-only or ordinary CI result may be promoted to real-world qualification.

## 4. Safety and release locks

- PR #11 remains Draft / Open / Unmerged.
- Auto-Run OFF; Worker and Browser DISABLED.
- No merge, deployment, production activation, host/firewall mutation or C02 start.
- No paid API/provider, paid service, payment, purchase or new cost.
- No secrets, PINs, private keys, client credentials or recovery codes in repository evidence.
- Preserve owner-first authorization and ask-first approval for external connections and irreversible operations.

## 5. P59 outcome

**P59: COMPLETE** for the defined scope: exact P58 commit CI was checked and all four returned workflows succeeded; remaining tests and external dependencies are consolidated above.

**S09/C01: OPEN / NOT COMPLETE. C02: NOT STARTED.**
