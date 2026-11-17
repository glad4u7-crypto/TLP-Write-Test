# APAA Personal Edition — Android Owner Acceptance Runbook

**Checkpoint:** APAA-PERSONAL-P74  
**Target:** Owner's physical Android phone  
**Status:** Test plan prepared; physical acceptance NOT RUN.

## Preconditions
Do not expose the current unauthenticated local app to a LAN or public network. The client is a responsive Streamlit web application, not a native APK or installable PWA. Physical remote-access checks require a separately reviewed private HTTPS and authentication environment. Do not buy hosting, enable paid providers, create API keys or deploy publicly for this runbook.

Record exact commit SHA and app version. Use synthetic data only. Never capture passwords, OTPs, recovery codes, cookies, private keys or personal content.

## A01–A12 acceptance cases
| ID | Test | Expected result | Evidence |
|---|---|---|---|
| A01 | Open approved private test URL in Android Chrome | Secure connection; no certificate warning; correct owner app | Redacted screenshot + origin |
| A02 | Sign in as owner when live OIDC is configured | Verified identity maps to configured owner; no anonymous fallback | Redacted result |
| A03 | Open a second unauthorised account/session | No owner data or controls visible | Redacted denial |
| A04 | Refresh and reopen app | Permitted projects/checkpoints persist | Synthetic record IDs |
| A05 | Create harmless test project and inspect preview | No mutation before explicit Confirm | Before/after state |
| A06 | Cancel project approval | No project created; cancel/denial audit recorded | Audit event IDs |
| A07 | Confirm harmless test project | Exactly one project created; intent and outcome audit recorded | Audit event IDs |
| A08 | Replay same approval | Replay rejected; no second mutation | Redacted rejection |
| A09 | Attempt unknown or prohibited action | Fail-closed denial; no handler dispatch | Policy reason code |
| A10 | Sign out, expire session or revoke access | Protected pages/data inaccessible | Redacted session result |
| A11 | Owner backup/restore drill on intended host | Restore into new directory; integrity passes; old approvals invalidated | Manifest digest + restore result |
| A12 | Rotate screen; test narrow viewport, keyboard and touch | No hidden/overlapping controls; readable layout; explicit actions | Device/browser/version + screenshots |

## Execution record
For each case record case ID and PASS/FAIL/BLOCKED/NOT RUN; exact commit SHA; Android model/version; Chrome version and viewport/orientation; date/time and environment; synthetic account role; redacted evidence reference and audit correlation ID; failure and remediation.

## Stop conditions
Mark FAIL if a certificate warning or unexpected origin appears; a non-owner sees or mutates owner data; mutation occurs before approval; approval replays; an unknown/prohibited action dispatches; audit failure does not block mutation; revocation leaves protected data accessible; or restore overwrites existing data/accepts a corrupt archive.

Mark BLOCKED rather than PASS when HTTPS/OIDC, a second test account or owner-controlled host is unavailable.

## Current readiness
Chromium viewport smoke tests are supplemental only, not A01–A12 completion. A01–A03 and A10 require approved private HTTPS/OIDC; A11 requires an owner-operated recovery drill. UI checks still require the physical Android phone.

No physical Android test has been performed by this document. Complete the table only after running each test on the actual phone.
