# APAA-S09-C01-P64 — Android-only owner acceptance guide

**Purpose:** Provide a safe, practical physical-Android acceptance path for the APAA owner.  
**Target:** Android phone + mobile browser (Chrome or another supported modern browser).  
**PC requirement:** None. A physical PC/Windows device is not required for Android-only qualification.  
**Status:** Test procedure prepared; owner-device execution and signed results are pending.

## 1. Safety boundaries

- Use only an owner-controlled test deployment and non-sensitive test data.
- Do not paste passwords, OIDC codes, PINs, API keys, private keys, recovery codes, cookies, or session tokens into ChatGPT, GitHub issues, screenshots, or evidence JSON.
- Keep Auto-Run OFF. Keep Worker and Browser execution DISABLED. Do not enable production task execution during this test.
- Do not install APKs from unknown sources or grant Accessibility, VPN, device-admin, notification, file, or screen-capture permissions for this acceptance test.
- Do not use Termux as a hostile-code sandbox or as proof of OCI isolation.
- Stop if the site shows an unexpected login, certificate warning, permission request, redirect, or unrecognized hostname.
- This is a UI/session acceptance test only. It does not qualify the Linux worker, HSM, remote anchor, production network isolation, or disaster recovery.

## 2. Preconditions

The owner/operator must have:
1. An Android phone under the owner's control, updated enough to run a supported browser.
2. A known HTTPS URL for the owner-approved test deployment. Do not expose an unauthenticated prototype to the public internet.
3. A test project containing non-sensitive sample data.
4. If authentication/revocation is being assessed, two separately controlled OIDC test accounts and an owner-configured trusted issuer. Do not share their credentials.
5. A rollback contact/procedure for the test deployment.

If any precondition is absent, mark the corresponding test BLOCKED, not PASS.

## 3. Android physical-device checks

Record only test ID, PASS/FAIL/BLOCKED, UTC time, app/browser version, Android major version, and a redacted note. Do not record account identifiers or secrets.

| ID | Action on Android | Expected result |
|---|---|---|
| A01 | Open the owner-approved HTTPS URL in the mobile browser | Correct APAA origin loads; no certificate or hostname warning |
| A02 | Use portrait orientation at default display/text scaling | No page-level horizontal scrolling; headings and controls remain visible |
| A03 | Rotate to landscape and return to portrait | Layout remains usable; no stuck overlay or lost session |
| A04 | Focus each visible text input | Keyboard does not permanently obscure the active field; text remains readable |
| A05 | Tap primary buttons with touch | Controls respond without requiring a mouse/hover |
| A06 | Enter a harmless planning request and prepare its structured plan | Plan is review-only; no task executes and no external side effect occurs |
| A07 | Navigate away and return using browser back/forward | No privilege escalation; session state is consistent and no stale approval is resurrected |
| A08 | Lock phone, wait, unlock and return | Session follows configured expiry policy; no expired approval is reused |
| A09 | Sign out, then use browser back | Protected owner content is not accessible from a stale cached page; server-side access is denied |
| A10 | Sign in again as the owner | Only the authenticated owner's data and projects appear |
| A11 | Check browser permission prompts/site settings | APAA does not require Accessibility, VPN, device-admin, camera, microphone, contacts or broad file access for this workflow |
| A12 | Check the task planning screen | No Auto-Run, execute-now, payment, purchase, checkout, trading or money-movement control is enabled |

A01–A12 are physical-device checks. Browser emulation in GitHub Actions does not count as completing them.

## 4. Two-account owner grant/revoke test

Run only when two controlled OIDC accounts are available and the owner has explicitly configured the trusted issuer. Use a disposable test project with no private content.

1. Sign in on Android as the owner. Confirm the owner identity is established by the configured OIDC provider, not by typed issuer/subject fields.
2. Sign in with the second controlled account in a separate private browser profile/session (or a separate browser with isolated storage).
3. Confirm the second account has no project access by default.
4. From the owner session, grant only the explicitly supported read-only project permission to the second account, after reviewing the exact project and confirming the action.
5. Confirm the second account can read only the intended project metadata/content explicitly covered by the grant.
6. Attempt prohibited operations from the second account: project mutation, task execution, settings changes, file/resource writes, memory/conversation access, checkpoint mutation, and owner administration. Each must be denied.
7. Revoke the grant from the owner session.
8. Without signing out, refresh and retry from the second account's already-open session. Access must be denied immediately on the next server authorization check.
9. Close/reopen the second session and repeat the denial check.
10. Restart/reconstruct the test application/store if supported, then verify the revoked grant remains revoked.
11. Confirm the owner still retains access and the audit trail records grant/revoke without leaking secrets.

If any prohibited operation succeeds, stop the test and mark FAIL. If the two-account setup or physical second session is unavailable, mark this section BLOCKED. Never substitute synthetic principals for live OIDC evidence.

## 5. Evidence record template

Create the record locally in the approved restricted evidence location. Do not commit raw screenshots, account identifiers, tokens, device serial numbers, or personal data to the repository.

```json
{
  "schema_version": 1,
  "qualification": "APAA_ANDROID_OWNER_ACCEPTANCE",
  "code_commit": "<exact-tested-commit-sha>",
  "device": {
    "platform": "Android",
    "android_major": "<major-version>",
    "browser": "<browser-and-version>"
  },
  "tests": [
    {"id": "A01", "result": "PASS|FAIL|BLOCKED", "tested_at_utc": "<ISO-8601-UTC>", "note": "<redacted-note>"}
  ],
  "oidc_two_account": "PASS|FAIL|BLOCKED|NOT_RUN",
  "secrets_included": false,
  "operator": "<owner-approved-operator-alias>",
  "review": "PENDING"
}
```

This small template is a human worksheet, not one of the signed P27 host evidence artifacts. It must not be used to claim HSM, worker, anchor or host qualification.

## 6. Acceptance rules

- A test is PASS only after it is actually performed on the physical Android phone.
- Missing test, missing second account, uncertain identity, or unavailable test deployment = BLOCKED.
- Any unauthorized data exposure, permission escalation, stale-session access, or prohibited action = FAIL and stop.
- Preserve redacted evidence privately and have an independent reviewer verify it.
- Bind the final review to the exact APAA code commit and evidence digest.
- PC testing is optional and only needed if the owner later chooses to support/qualify a PC client.

## 7. Current disposition

**Android procedure:** COMPLETE.  
**Physical Android execution:** PENDING owner-operated test.  
**Two-account live OIDC test:** PENDING controlled identities.  
**PC physical-device test:** NOT REQUIRED for Android-only delivery.  
**C01:** OPEN / NOT COMPLETE until all mandatory G1–G10 evidence and independent approval pass.  
**C02:** NOT STARTED.
