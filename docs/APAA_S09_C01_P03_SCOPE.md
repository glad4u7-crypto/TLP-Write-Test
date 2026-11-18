# APAA-S09-C01-P03 — Page and Element Inspection

**Status:** Read-only page inspection primitives present; generic element-inspection coverage and latest branch CI remain incomplete/unverified.
**Branch:** `feature/apaa-s09-c01-p01-browser-launch`
**PR:** #10 (Draft; unmerged)

## Scope

Inspect a page only after a separately authorized, bounded navigation. Expose limited read-only information; do not click, fill, submit, upload, download, log in, or mutate a page in this part.

## Implemented repository components

- `core/live_browsing.py`: read-only actions for page title, visible body text, link metadata and transient screenshot, using a fresh attested browser session.
- Request policy restricts methods to GET/HEAD, checks each routed request against exact allowed HTTPS origins, caps request count, blocks WebSockets, enforces response byte/runtime limits, and closes the browser session.
- Audit acceptance/completion/failure events are required; URLs, credentials and page text are not written into the audit event payload.
- `tests/test_live_browsing.py` provides fake-browser coverage for read-only inspection, blocked cross-origin requests, mutating methods, audit failure, byte limits, expiry and WebSocket policy.

## Remaining P03 work

- [ ] Define and implement a bounded generic element-inspection schema (stable selector/role/label metadata only; no action execution).
- [ ] Add tests for hidden/disabled elements, duplicate matches, stale handles, selector timeouts, oversized DOM/text and malformed element metadata.
- [ ] Verify inspection output is sanitized, bounded and does not expose cookies, local storage, credentials or hidden page state.
- [ ] Full repository CI successful on the latest branch head.
- [ ] Real browser/host qualification after the signed runtime and proxy/firewall boundary is independently verified.

## Security boundary

The current read-only inspection controller is not proof of production isolation. Its worker launch requires signed runtime/firewall evidence; the host collector, key provisioning/rotation, challenge lifecycle and actual host boundary are separate responsibilities. Do not enable live browsing based only on fake tests or controller code.

Browser/Worker dispatch remains disabled; Auto-Run remains OFF. No payment, purchase, login, form submission, download, upload, or other mutation is part of P03.