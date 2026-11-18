# S09-C02 visible DOM inspector — bounded offline integration

This branch adds `core/browser_dom_inspector.py`, a read-only asynchronous
Playwright-page adapter for extracting rendered body text from an already
injected page object.

## Guarantees and limits

- Revalidates the current page URL against the exact approved HTTPS origin list.
- Requires exactly one visible body locator.
- Uses Playwright's rendered `inner_text` API; does not use `text_content`,
  arbitrary selectors, page JavaScript evaluation, or hidden DOM traversal.
- Enforces a hard asynchronous deadline and a strict character ceiling; it
  fails closed rather than silently truncating oversized content.
- Redacts common email, phone, bearer-token and labelled-secret patterns.
- Builds read-only target evidence for a unique visible/enabled same-origin link or a unique labelled native text/email/number/date/select control. It scans a bounded number of links, rejects duplicates and secret/unsupported input types, and never clicks or fills.\n- Extracts bounded visible search-result cards using a single simple CSS selector, requires one visible/enabled link per card, ignores off-origin links, enforces a deadline, and routes records through the existing normalizer for page binding, deduplication, URL allowlisting and PII/secret redaction.
- Performs no navigation, click, form fill, submit, download, upload, network
  dispatch, approval lookup, or job execution.

## Security boundary

The returned `page_id` is a caller-supplied correlation label. Target evidence is passed through the existing controller validator for interaction/page binding, exact destination, uniqueness, control type and freshness. The adapter
does not prove browser-process identity, page lineage, cryptographic evidence
authenticity, site semantics, or that an injected page object is trustworthy.
Its output is untrusted observation data and cannot authorize a click/fill.
No production dispatcher is connected. S09-C01 browser/worker qualification
and Owner approval integration remain mandatory before live execution.

## Tests

`tests/test_browser_dom_inspector.py` uses a fake asynchronous Playwright
surface to test visible-body requirement, exact-origin rejection, bounds,
deadline cancellation, malformed inputs, sensitive-text redaction, unique link matching, native form-control type checks, duplicate-target rejection and no-action preview behavior. These tests do not replace
real Chromium or Android qualification.
\n\n## Search extraction constraints\n\n`extract_visible_search_results` accepts only a validated `SearchIntent`. Its selector grammar is intentionally narrow (tag, `.class`, `#id`, or a bare attribute selector); XPath, text selectors, selector chains and arbitrary page scripts are rejected. The result-card count is capped, each card must be visible, and only a single visible/enabled anchor is considered. This is a read-only preview adapter: it does not execute the search query, apply filters, paginate, click a result, or navigate. Search submission and pagination remain separate future work behind approval and host-egress qualification.\n