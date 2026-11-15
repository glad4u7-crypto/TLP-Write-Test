# APAA-S04-C01-P08-P06 — Live Authentication & Cross-Session Verification

Status: **Current-head CI passed; live provider/browser tests remain blocked on operator-provided OIDC deployment and test identities**

## Entry checks completed
- Pull request #5 remains open and draft.
- Latest verified PR head: `643f9ef22a5f24d4d0e209e3f0df73cc9c49eed8` (verification snapshot; this documentation update will create a newer head).
- Current-head GitHub Actions checks all completed successfully: Agent Foundation CI push #276 (`43676035943`), Python Demo CI push #368 (`43676035947`), Agent Foundation CI pull request #277 (`43676039985`), and Python Demo CI pull request #369 (`43676039990`).
- The earlier workflow-definition failures on commits `db18de13d07ad886576d10c5b142dd0a2e5b7165` and `ebdb886c5b48f28795aba25265b3250369e652b0` were caused by malformed YAML during the trigger/permissions edit. The workflow YAML was corrected in commit `81a07587437e145ebcc683e6e80ba1e42a452a75`; the corrected current-head push and PR runs above pass.
- Foundation CI validates compileall and pytest; Python Demo CI validates dependency installation, pytest, and demo smoke test. These checks do not replace live OIDC/browser testing.
- The repository contains the OIDC claim adapter and unit tests for missing/malformed claims, expired identities, future-issued identities, and bounded clock skew.

## Live verification prerequisites
- A dedicated test OIDC client and controlled HTTPS deployment URL (or documented localhost test setup).
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
| P06-06 | Login as User B in same browser profile after A logout | A's pending project draft, selection, approval authority, gateway, and task draft do not carry over | Redacted before/after evidence |
| P06-07 | Replay A's approval receipt as B or after logout | Execution denied; receipt is not accepted across authority/session boundary | Redacted test result/audit event |
| P06-08 | Expired/invalid identity session | Protected workspace/actions fail closed and require re-authentication | Redacted result |
| P06-09 | Inspect logs and browser-visible output | No ID/access/refresh tokens or client secrets are exposed | Redacted log review |

## Acceptance criteria
- Every applicable test passes in a configured deployment.
- User A and User B are distinct identities from the configured issuer.
- No cross-user project visibility or action authorization is possible.
- Logout/account-switch does not preserve prior identity-bound authority or drafts.
- No credentials or bearer tokens are exposed in evidence.
- Any failure blocks production approval and is recorded with a reproducible issue.

## Current limitations / stop conditions
- No OIDC provider has been configured or exercised as part of this repository verification.
- No live deployment URL or two test identities were available during this task.
- CI success validates automated tests and demo startup only; it does not validate provider redirects, cookies, logout, browser isolation, CSRF behavior, or production session security.
- Do not mark P06 live verification complete until the operator runs the matrix and records evidence.
- Keep PR #5 in draft. Do not merge or enable production execution.

## Safety constraints
No payments, purchases, checkout, trading, money movement, paid APIs, API billing, shell, arbitrary network, browser automation, email, filesystem, or device-control handlers are enabled. Auto-Run remains disabled.
