# APAA-S09-C01-P59.1 — Owner-only CI regression triage

**Date:** 2026-11-16  
**Branch:** `feature/apaa-s09-c01-p16-oci-lifecycle`  
**PR:** #11 — Draft / Open / Unmerged  
**Scope:** Diagnose the exact-head CI regression after enforcing the private owner-only runtime gate.

## Finding

The owner-only guard correctly stops an authenticated identity unless the server-side owner issuer + subject matches. The existing authenticated smoke-test helper, however, created a synthetic logged-in user without provisioning the matching synthetic owner mapping. Several legacy tests also asserted the previous multi-user/optional-owner behavior. As a result, the app stopped at the intended security boundary and those tests subsequently failed because expected downstream session state was never initialized.

The failing exact head was `c02dcfe549117a74554df4316e1904c35e5026fc`:
- Agent Foundation CI #1206: FAIL — 10 failed, 1338 passed, 9 skipped.
- Python Demo CI #1295: FAIL — same shared test-suite failures.
- P20 Podman #335: PASS.
- P23 Executor #317: PASS.

Failure class: test fixture/expectation mismatch with the new owner-only policy, not evidence that a non-owner bypassed the guard. The tests did not provide a configured owner for normal authenticated app tests.

## Corrective change

Commit `624841067e663725ca942b307208643ef051dfac` updates `tests/test_app_smoke.py`:
- Standard authenticated smoke tests now provision the synthetic test principal as the exact configured owner.
- Missing-owner, invalid-owner, and valid-but-different-owner tests explicitly opt out of that fixture default and assert fail-closed denial before the workspace renders.
- The account-switch test begins as the configured owner and then switches to a different subject, verifying owner-bound capabilities are cleared.

This is a test-fixture alignment change only. It does not weaken or bypass the runtime owner gate.

## Verification status

CI for corrective commit `624841067e663725ca942b307208643ef051dfac` has been triggered by the PR branch update. Exact-head workflow conclusions must be checked before marking the regression resolved. No PASS is claimed in this record until all required workflows finish successfully.

## Safety and project state

- Runtime remains owner-only when authentication is required; missing/invalid owner mapping and non-owner identity fail closed.
- Repository source visibility is a separate owner action and was not changed by this work.
- PR #11 remains Draft / Open / Unmerged.
- No deployment, merge, production activation, host mutation, key operation, paid provider, billing, or purchase.
- Auto-Run OFF; Worker and Browser DISABLED.
- P59–P63 remain the only active C01 sequence. C01 stays OPEN until every mandatory external gate is genuinely qualified. C02 is NOT STARTED.
