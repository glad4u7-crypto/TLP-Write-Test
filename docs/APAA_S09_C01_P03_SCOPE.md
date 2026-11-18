# APAA-S09-C01-P03 — Page and Element Inspection

**Status:** Generic read-only element-inspection implementation and focused tests added; execution and latest branch CI remain unverified.
**Branch:** `feature/apaa-s09-c01-p01-browser-launch`
**PR:** #10 (Draft; unmerged)

## Scope

Inspect a page only after a separately authorized, bounded navigation. Expose limited read-only information; do not click, fill, submit, upload, download, log in, or mutate a page in this part.

## Implemented repository components

- `core/live_browsing.py`: read-only actions for page title, visible body text, link metadata, transient screenshot, and bounded generic element metadata, using a fresh attested browser session.
- `inspect_elements` returns at most 100 element records (tag, role, accessible label, visible text, disabled/visible flags, and approved same-origin link URL). It never returns input values, HTML, cookies, storage, or hidden element text.
- Response metadata is byte-bounded by the job's existing `max_response_bytes` limit; disallowed link targets are omitted.
- Request policy restricts methods to GET/HEAD, checks each routed request against exact allowed HTTPS origins, caps request count, blocks WebSockets, enforces response byte/runtime limits, and closes the browser session.
- Audit acceptance/completion/failure events are required; URLs, credentials and page text are not written into the audit event payload.
- `tests/test_live_browsing.py` provides fake-browser coverage for read-only inspection, blocked cross-origin requests, mutating methods, audit failure, byte limits, expiry and WebSocket policy.

## Remaining P03 work

- [x] Define and implement a bounded generic element-inspection schema (stable tag/role/label/text/visibility/disabled metadata only; no action execution).
- [x] Add focused tests for hidden/disabled elements and response-byte-limit enforcement.
- [ ] Add further edge-case tests for duplicate matches, stale handles, selector timeouts and malformed element metadata.
- [ ] Verify inspection output is sanitized, bounded and does not expose cookies, local storage, credentials or hidden page state.
- [ ] Full repository CI successful on the latest branch head.
- [ ] Real browser/host qualification after the signed runtime and proxy/firewall boundary is independently verified.

## Security boundary

The current read-only inspection controller is not proof of production isolation. Its worker launch requires signed runtime/firewall evidence; the host collector, key provisioning/rotation, challenge lifecycle and actual host boundary are separate responsibilities. Do not enable live browsing based only on fake tests or controller code.

Browser/Worker dispatch remains disabled; Auto-Run remains OFF. No payment, purchase, login, form submission, download, upload, or other mutation is part of P03.

## Implementation update — 2026-11-18

- Added the `inspect_elements` read-only action to the closed browser-job allowlist.
- Added bounded element metadata collection in `LiveBrowsingController`: maximum 100 records; no input values, HTML, cookies, storage or hidden text are returned; links are included only when they pass the job's exact-origin policy.
- Added focused tests for visible/hidden and disabled element metadata and response-byte-limit rejection.
- Commits: `079c574` (controller), `73f1d6e` (job action allowlist), `7912bcb` (focused tests).
- These commits have not yet been executed by GitHub Actions in the available verification evidence. P03 remains IN PROGRESS until tests and exact-head CI pass.