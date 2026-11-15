# APAA-S04-C01-P08-P06 — Live Authentication & Cross-Session Verification

Status: **Verification plan prepared; live provider/browser tests not run**

## Entry checks completed
- Pull request #5 remains open and draft.
- Current PR head at inspection: `befe532b6a77f3fadf4274be7ebe410d2b4ee54d`.
- GitHub Actions Python Demo CI Run #213 completed successfully.
- Job `test-demo`: success; dependency installation, pytest, and `demo.py` smoke test steps all succeeded.
- The repository contains the strict OIDC claim adapter and unit tests for missing/malformed claims, expired identities, future-issued identities, and bounded clock skew.

## Live verification prerequisites
These are deployment/operator prerequisites, not values to commit:
- A dedicated test OIDC client and a controlled HTTPS deployment URL (or documented localhost test setup).
- Correct provider redirect URI ending in `/oauth2callback`.
- Private runtime secrets configured outside source control: `[auth]` client configuration and `[apaa].require_auth = true`.
- Two separately authenticated test identities and two isolated browser profiles (or equivalent independent browser contexts).
- A disposable test environment with no real execution handlers or sensitive user data.

Never paste client secrets, cookie secrets, ID tokens, access tokens, or refresh tokens into GitHub, logs, screenshots, or chat.

## Manual test matrix

| ID | Test | Expected result | Evidence to record |
|---|---|---|---|
| P06-01 | Open deployment without OIDC secrets while auth is required | App stops with configuration error; protected workspace is not rendered | Redacted screenshot/log |
| P06-02 | Open configured deployment while logged out | Login prompt only; protected workspace is not rendered | Redacted screenshot |
| P06-03 | Complete login as User A | Valid issuer/subject principal; A sees only A-owned projects | Redacted issuer/subject fingerprint and screenshot |
| P06-04 | Complete login as User B in separate browser profile | B sees no A-owned projects and cannot access A project IDs | Redacted denial/result |
| P06-05 | Logout User A | Session returns to unauthenticated/login state; protected actions unavailable | Redacted screenshot |
| P06-06 | Login as User B in the same browser profile after A logout | A's pending project draft, selection, approval authority, gateway, and task draft do not carry over | Before/after state evidence without tokens |
| P06-07 | Replay A's approval receipt as B or after logout | Execution denied; receipt is not accepted across authority/session boundary | Test result and audit event with secrets redacted |
| P06-08 | Expired/invalid identity session | Protected workspace/actions fail closed and require re-authentication | Redacted result |
| P06-09 | Inspect logs and browser-visible output | No ID/access/refresh tokens or client secrets are exposed | Redacted log review |

## Acceptance criteria
- Every applicable test above passes in a configured deployment.
- User A and User B are distinct identities from the configured issuer.
- No cross-user project visibility or action authorization is possible.
- Logout/account-switch does not preserve prior identity-bound authority or drafts.
- No credentials or bearer tokens are exposed in evidence.
- Any failure blocks production approval and is recorded with a reproducible issue.

## Current limitations / stop conditions
- No OIDC provider has been configured or exercised as part of this repository verification.
- No live deployment URL or two real test identities were available during this task.
- CI success validates automated tests and demo startup only; it does not validate provider redirects, cookies, logout, browser isolation, CSRF behavior, or production session security.
- Do not mark P06 live verification complete until the operator runs the matrix and records evidence.
- Keep PR #5 in draft. Do not merge or enable production execution.

## Safety constraints
No payments, purchases, checkout, trading, money movement, paid APIs, API billing, shell, arbitrary network, browser automation, email, filesystem, or device-control handlers are enabled. Auto-Run remains disabled.
