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

The first corrective commit `624841067e663725ca942b307208643ef051dfac` exposed a second fixture issue: Streamlit's secrets mapping is not a mutable plain dictionary, and the non-owner account-switch test still expected the old multi-user state. A follow-up commit `bf745a7ccc3eca1de33e6742f115bc9f36b5f9aa` updates `tests/test_app_smoke.py`:
- Standard authenticated smoke tests now copy the configured secrets mapping, add the synthetic principal as the exact configured owner, and rebind the test fixture.
- Missing-owner, invalid-owner, and valid-but-different-owner tests explicitly opt out of that fixture default and assert fail-closed denial before the workspace renders.
- The logout test explicitly configures its synthetic owner identity. The account-switch test begins as the configured owner and then switches to a different subject, verifying the non-owner is denied and session identity state is cleared.

This is a test-fixture alignment change only. It does not weaken or bypass the runtime owner gate.

## Verification status

CI for the latest corrective commit `bf745a7ccc3eca1de33e6742f115bc9f36b5f9aa` must be checked. Earlier intermediate run `8ee828758324b046da0d74acb2214312d88ee84a` still failed because the first fixture patch did not update Streamlit's immutable secrets mapping and the account-switch expectation. No PASS is claimed in this record until all required workflows finish successfully.

## Safety and project state

- Runtime remains owner-only when authentication is required; missing/invalid owner mapping and non-owner identity fail closed.
- Repository source visibility is a separate owner action and was not changed by this work.
- PR #11 remains Draft / Open / Unmerged.
- No deployment, merge, production activation, host mutation, key operation, paid provider, billing, or purchase.
- Auto-Run OFF; Worker and Browser DISABLED.
- P59–P63 remain the only active C01 sequence. C01 stays OPEN until every mandatory external gate is genuinely qualified. C02 is NOT STARTED.
