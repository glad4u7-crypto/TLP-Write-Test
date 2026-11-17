# APAA Personal Edition — Android Owner Acceptance Runbook

**Checkpoint:** APAA-PERSONAL-P74  
**Target:** Owner's physical Android phone  
**Status:** Local Personal Edition test plan prepared; physical Android acceptance NOT RUN.

## Preconditions
Do not expose the local app to a LAN or public network. The client is a responsive Streamlit web application, not a native APK or installable PWA. For the Personal Edition acceptance path, the app must run on the same Android device and bind only to loopback; open it in Android Chrome at `http://127.0.0.1:8501`. Android/Termux Python runtime compatibility is not yet qualified and must be recorded as BLOCKED if the app cannot be run locally. Remote access, HTTPS and OIDC are future deployment concerns, not prerequisites for this local single-Owner chapter. Do not buy hosting, enable paid providers, create API keys or deploy publicly for this runbook.

Record exact commit SHA and app version. Use synthetic data only. Never capture passwords, OTPs, recovery codes, cookies, private keys or personal content.

## A01–A12 acceptance cases
| ID | Test | Expected result | Evidence |
|---|---|---|---|
| A01 | Start the app on the Android device with loopback-only binding; open `http://127.0.0.1:8501` in Android Chrome | App is reachable only on the same device; no LAN/public binding; Owner gate appears | Redacted screenshot + loopback origin + runtime details |
| A02 | Complete first-run local Owner passphrase setup, then logout and sign in | Only the configured local Owner passphrase unlocks APAA; no anonymous fallback | Redacted result; never capture passphrase |
| A03 | Open a fresh/incognito browser session without the Owner passphrase | Owner data and mutation controls remain locked until the local Owner authenticates | Redacted denial |
| A04 | Refresh and reopen app | Permitted projects/checkpoints persist | Synthetic record IDs |
| A05 | Create harmless test project and inspect preview | No mutation before explicit Confirm | Before/after state |
| A06 | Cancel project approval | No project created; cancel/denial audit recorded | Audit event IDs |
| A07 | Confirm harmless test project | Exactly one project created; intent and outcome audit recorded | Audit event IDs |
| A08 | Replay same approval | Replay rejected; no second mutation | Redacted rejection |
| A09 | Attempt unknown or prohibited action | Fail-closed denial; no handler dispatch | Policy reason code |
| A10 | Logout; test 15-minute idle expiry and 12-hour absolute expiry | Protected pages/data, pending drafts and approval capabilities are inaccessible until re-login | Redacted session result |
| A11 | Owner backup/restore drill on the local Android host/runtime | Restore into a new directory without overwriting; integrity passes; Owner verifier preserved and old approvals invalidated by fresh signing key | Manifest digest + restore result |
| A12 | Rotate screen; test narrow viewport, keyboard and touch | No hidden/overlapping controls; readable layout; explicit actions | Device/browser/version + screenshots |

## Execution record
For each case record case ID and PASS/FAIL/BLOCKED/NOT RUN; exact commit SHA; Android model/version; Chrome version and viewport/orientation; date/time and environment; synthetic account role; redacted evidence reference and audit correlation ID; failure and remediation.

## Stop conditions
Mark FAIL if a certificate warning or unexpected origin appears; a non-owner sees or mutates owner data; mutation occurs before approval; approval replays; an unknown/prohibited action dispatches; audit failure does not block mutation; revocation leaves protected data accessible; or restore overwrites existing data/accepts a corrupt archive.

Mark BLOCKED rather than PASS when HTTPS/OIDC, a second test account or owner-controlled host is unavailable.

## Current readiness
GitHub Chromium viewport smoke tests are supplemental only, not A01–A12 completion. Local Owner login, lockout, logout and session-expiry behavior have automated test coverage, but actual Android runtime/Termux compatibility and all physical A01–A12 checks remain NOT RUN. Remote HTTPS/OIDC is not required for this local Personal Edition path; it belongs to a separately approved future remote deployment.

No physical Android test has been performed by this document. Complete the table only after running each test on the actual phone.
