# APAA S04 — Final Security Closure Plan

Checkpoint: APAA-S04-C01-P08-P09-BY  
Repository: glad4u7-crypto/TLP-Write-Test  
PR: #5  
Working branch: feature/approval-ui-e2e-p06  
Base branch: feature/agent-v0.3-zero-cost-core  
Status: code-level CI verified; production/release blocked

## 1. Verified code and CI baseline

The BX matrix addendum commit `cb0664dae5874d15abdf3a3f88ed84c292afdc03` passed both existing workflows:
- Agent Foundation CI run `43700453545`: dependency audit passed (no known vulnerabilities at run time), compileall passed, 399 tests passed.
- Python Demo CI run `43700453429`: 399 tests passed; exact demo output `Hello TradeLab Pro` passed.

All prior CI claims remain scoped to the exact commit/run and the tests actually executed. A CI PASS is not live identity, browser, infrastructure or production-security evidence.

## 2. Release blocker register and acceptance evidence

| ID | Blocker | Required acceptance evidence | Current state |
|---|---|---|---|
| BY-01 | Live OIDC authentication | Private non-production deployment; two controlled identities; valid/invalid issuer, subject, audience, expiry, nonce/state and callback tests; logout and identity-switch cleanup | BLOCKED — no deployment/test identities |
| BY-02 | Browser/session perimeter | Real-browser evidence for Secure/HttpOnly/SameSite cookies, CSRF, redirect allowlist, TLS/reverse-proxy trust, callback and session fixation cases | BLOCKED — no target topology |
| BY-03 | Repository branch protection | Repository-admin evidence that required reviews, required CI checks, stale-review dismissal and force-push restrictions are enforced on the intended base | BLOCKED / ADMIN UNVERIFIED |
| BY-04 | Independent audit anchoring | Separate trust boundary, immutable/append-only checkpoints, authenticated transport, sequence/rollback detection, outage and credential-revocation tests | BLOCKED — no independent anchor |
| BY-05 | Backup/retention/restore operations | Encrypted off-site backups, access policy, retention schedule, monitoring, documented RPO/RTO and recurring restore exercise | BLOCKED — only local backup/restore mechanics tested |
| BY-06 | Host/process isolation | Dedicated unprivileged OS identity, private non-writable parent directories, one supported writer topology, OS/container sandbox, deny-by-default capabilities and adversarial tests | BLOCKED — not deployed |
| BY-07 | Operational ownership | Named owner, incident response, audit verification alerts, backup-age/storage monitoring, evidence retention and independent review | BLOCKED — operational owner/evidence absent |

## 3. Work ordering and stop conditions

1. Repository administrator first verifies branch protection and required checks. Stop if required checks can be bypassed or force-push policy is unsafe.
2. Establish a private non-production environment with no production data and no real-world action handlers. Store OIDC/signing secrets only in a secret manager.
3. Run two-identity OIDC and real-browser tests using isolated profiles. Stop immediately on cross-user data/capability leakage, retained approval state after logout, invalid callback acceptance or unsafe redirect.
4. Define and test the audit anchor in a separately administered trust boundary. Stop if rollback, duplicate/conflicting sequence, missed checkpoint or anchor outage is silently accepted.
5. Establish encrypted backup/retention/monitoring and perform restore drills. Stop if restore fails integrity/chain verification or the required recovery objective cannot be met.
6. Establish and adversarially test host/process isolation and the supported single-writer topology. Do not claim same-UID race resistance without platform-level evidence.
7. Collect sanitized evidence, assign owners, obtain independent review, and only then conduct a separate production-readiness decision.

## 4. Non-negotiable safety constraints

- PR #5 remains Open + Draft. Do not merge or deploy as part of this checkpoint.
- Do not change the base branch.
- Auto-Run remains disabled.
- Do not register or activate browser, email, shell, arbitrary network, filesystem or device handlers.
- Payment, purchase, checkout, trading and money movement remain prohibited.
- Paid providers, API keys and billable services remain disabled. No payment or charge may be incurred.
- Never commit OIDC secrets, signing keys, tokens, cookies or personal identity data.
- No production use until every applicable blocker has independently reviewed evidence and explicit approval.

## 5. BY conclusion

The existing automated/code-level CI baseline is green. This closes the repository-only test work evidenced so far, including the SQLite backup/restore and tamper-append tests. It does **not** close S04 production readiness. The blockers above require an actual deployment, repository-admin action or separately controlled operational infrastructure and must remain BLOCKED until evidence exists.

Next checkpoint: APAA-S04-C01-P08-P09-BZ — verify the latest matrix and this closure plan on the exact PR head, confirm CI for both commits, then record the final S04 code-complete/release-blocked decision without merging or deploying.
