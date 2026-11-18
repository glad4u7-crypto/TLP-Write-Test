# APAA-S09-C02 — Website Interaction

**Status:** CONTROLLER FOUNDATION IMPLEMENTED; PREVIOUS EXACT-HEAD CI PASSED; TARGET-EVIDENCE AND SEARCH-RESULT EXTENSIONS AWAITING EXACT-HEAD CI; LIVE EXECUTION BLOCKED BY S09-C01 RELEASE GATES.  
**Checkpoint family:** `APAA-S09-C02-P01`, `APAA-S09-C02-P02`, `APAA-S09-C02-P03`  
**Repository:** `glad4u7-crypto/TLP-Write-Test`  
**Branch:** `feature/apaa-s09-c02-website-interaction`  
**Base:** `feature/apaa-s09-c01-action-history-clean`, commit `445e2bfa92d89984b620110ae15bc6a0244b4ac7`.

## 1. Objective

Provide bounded, typed controller-side intent validation for:
- P01: Click and Form Filling.
- P02: Search and Filtering.
- P03: Multi-page Navigation.

This chapter must integrate with the existing BrowserJob, exact-origin policy, approval correlation, recovery ledger and isolated-worker contracts before any execution adapter is enabled. It must not create a second permission system or bypass the existing fail-closed dispatch boundary.

## 2. Dependency and release gate

S09-C01 is **not complete or security-approved for live browsing**. The recorded blockers include failed real-host Chromium qualification caused by an FD ownership violation, production approval-receipt consumption not connected to the production BrowserExecutionCoordinator, Android physical-device qualification, and independent security review.

Therefore this C02 branch is limited to offline schemas, deterministic validators, unit tests, documentation and mock-only planning. It must NOT launch Chromium, connect to a live website, submit a form, click a live control, dispatch a worker, or enable public/live browsing until all C01 release gates are passed and explicitly accepted by the Owner.

## 3. Non-negotiable safety rules

- Owner-first, private by default; no public signup or unauthorised users.
- Default permission is **Ask First**. Every mutating action needs fresh, exact, one-time approval bound to Owner, session, tenant, job and canonical action payload.
- Read-only inspection is limited to an explicitly approved HTTPS origin and bounded page/result sizes.
- Clicks are not assumed read-only. Any click that may submit, purchase, publish, send, delete, change account settings, or trigger an external side effect is classified as mutation and blocked absent exact approval.
- Form filling is draft-only by default. No submit/confirm/send action is included in a fill operation.
- Payment, purchase, checkout, subscription, trading, money movement and financial transactions are permanently out of scope.
- No password, OTP, recovery code, payment data, API key or other secret may be collected, stored in action history, or emitted in logs.
- No Auto-Run, blind retries, replay after uncertain outcomes, arbitrary JavaScript, eval/exec, shell, extension installation, downloads, uploads, or persistent browser profile.
- Redirects and every network destination must remain under the C01 enforced egress boundary. Page-level routing alone is not a network sandbox.
- Browser/Worker dispatch remains disabled until C01 qualification and Owner acceptance.

## 4. Implemented controller foundation

File: `core/browser_interaction.py`

- Frozen typed records: `ClickIntent`, `FillIntent`, `SearchFilter`, `SearchIntent`, `NavigationStep`, and `NavigationPlan`.
- Closed-schema validation rejects unknown/missing fields and malformed identifiers.
- All URLs are canonicalized and checked against exact approved HTTPS origins through `core.browser_security.validate_destination`.
- P01 click intent is restricted to explicit link navigation; generic buttons and submit controls are rejected.
- P01 form filling is draft-only, bounded, and rejects unsupported/secret field types. It has no submit operation.
- P02 query/filter intent is bounded, structured, and capped at 10 filters and 100 results.
- P03 navigation plans are finite (1–8 steps), unique-ID, exact-origin-bound, and capped at 60 seconds.
- Prohibited financial/purchase wording checks are defense-in-depth only. They are not semantic classification and must never be treated as the primary safety boundary.\n- `validate_target_evidence` adds a pure controller-side gate requiring one unique, visible, enabled locator, exact interaction/page correlation, same approved origin, matching link destination or form-control type, and a timestamp no older than five seconds by default. It revalidates the frozen intent object because dataclasses can be directly constructed.\n- This evidence validator does not inspect a real DOM, attest the adapter, cryptographically bind evidence to a browser process, or consume an Owner approval receipt. It cannot authorize execution.\n- `validate_search_results` adds a bounded normalizer for adapter-reported visible search results. It enforces the approved result count, exact page ID, allowlisted HTTPS destinations, unique URLs, per-field and total byte limits, and redacts email/phone/bearer/labelled-secret text plus sensitive URL query parameters (including API keys). Excessive query parameters fail closed.\n- This is not a browser extractor or proof that content was visible. The adapter must prove visibility and must treat all page text as untrusted data, never as instructions.

File: `tests/test_browser_interaction.py`

- Positive and adversarial tests cover link-only click, rejected buttons/submit, cross-origin and checkout URL rejection, secret form-field rejection, bounded fill, query/filter constraints, result caps, navigation origin escape, duplicate IDs, excessive steps and invalid runtime.\n- Target-evidence tests cover unique match, visible/enabled state, page and interaction correlation, changed href, locator mismatch, control type, stale/future observations, malformed flags, unknown fields and forged dataclass inputs.\n- Search-result tests cover visible-only records, page binding, allowlisted URLs, deduplication, count/field bounds, email/phone/bearer/API-key redaction, excessive URL parameters and malformed forged search intents.

## 5. Verification evidence

Previously verified code-bearing commit: `8cc845171d323c41a42771a8b315e635b993c956`.\n\nLatest controller implementation commit: `d19c05a8377861c93ece7babeda754653e21b394`. Exact-head CI for the target-evidence and search-result extensions is pending and must pass before these extensions are marked verified.

- GitHub Actions workflow: **APAA Security CI**
- Run: [44214923346](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/44214923346)
- Result: **completed / success**.
- The single `Python security tests` job completed successfully, including Chromium TLS trusted-CA acceptance, hostname-mismatch rejection, expired-certificate rejection, controller/lifecycle tests, test-only local Chromium fixture, production worker adapter contract, Linux host inspector contract, and remaining security test suite.

This is evidence for the exact commit above only. It does not prove live browser execution safety, OCI isolation, Android compatibility, site-specific semantics, approval-receipt consumption in production, or independent security approval.

## 6. Checkpoint status

| Checkpoint | Controller foundation | Full acceptance status |
|---|---|---|
| C02-P01 — Click and Form Filling | Intent validators plus offline unique/fresh target-evidence gate implemented | NOT COMPLETE: no real DOM adapter/target preview, cryptographic evidence attestation, approval binding/consumption, or real adapter qualification |
| C02-P02 — Search and Filtering | Bounded intent plus visible-result normalization/redaction gate implemented | NOT COMPLETE: no real DOM extraction, pagination/deadline enforcement, adapter visibility proof, or site-semantic side-effect classification |
| C02-P03 — Multi-page Navigation | IMPLEMENTED; exact-head CI passed | NOT COMPLETE: no redirect/popup/frame enforcement at runtime, page lineage, cancellation/recovery proof, or egress qualification |
| C02 overall | CONTROLLER FOUNDATION VERIFIED | BLOCKED FOR EXECUTION by C01 and missing C02 runtime acceptance evidence |

**Do not label P01, P02, P03, or C02 fully Completed.** The current verified milestone is the offline controller foundation only.

## 7. Remaining engineering sequence

1. Complete S09-C01: fix and re-qualify real-host Chromium FD ownership; connect production one-time approval receipt consumption to BrowserExecutionCoordinator; complete Android physical-device qualification; obtain independent security review.
2. Reconcile C02 intent records and target evidence with the production BrowserJob, Owner/session/tenant/job identity, action-history and approval-correlation contracts. Avoid a parallel permission system. The new target-evidence validator is not a replacement for these contracts.
3. Add a reviewed execution contract for P01 that proves locator uniqueness, page identity/freshness, safe preview, exact approval binding, and fill-without-submit.
4. Add P02 browser-adapter extraction from visible DOM only, bounded pagination/deadlines, deterministic normalization, adapter visibility proof, and no-hidden-submit proof. The new normalizer is not itself an extractor.
5. Add P03 runtime redirect/popup/frame re-authorization, page lineage, stop-on-first-failure, cancellation, and no-replay-after-uncertain-outcome proof.
6. Run exact-head CI and independent security review for each integration milestone. Keep live execution disabled until C01 and Owner acceptance gates pass.

## 8. Authorization boundary

No PR merge, deployment, default-branch modification, payment, purchase, Auto-Run, public access, or live browsing is authorized by this document.
