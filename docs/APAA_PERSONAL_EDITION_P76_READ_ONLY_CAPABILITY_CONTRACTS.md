# APAA Personal Edition P76 — Read-only Capability Contracts

**Checkpoint:** APAA-PERSONAL-P76  
**Status:** Contract implementation started; adapters intentionally absent.

## Scope

Define bounded, typed request/result contracts for the first useful read-only capabilities:
- public web search;
- reading a specific HTTPS page;
- inspecting a file selected within an Owner project;
- discovering YouTube videos.

## Implemented

- `core/capabilities.py` defines exact capability identifiers, immutable request/result data classes, bounded query/result sizes and strict field validation.
- Web targets require credential-free HTTPS, default port, non-IP hostname and reject local/reserved hostnames.
- File inspection requires a project identifier and a normalized project-relative path; absolute paths, parent traversal, Windows separators, empty segments and control characters are rejected.
- YouTube result locators are limited to the known YouTube hostnames.
- Result collections are immutable tuples and bounded to 20 items; titles and excerpts have explicit size limits.
- `tests/test_capabilities.py` covers invalid types, ambiguous requests, unsafe URLs, path traversal, result spoofing and the absence of an execution handler.

## Explicit non-capabilities

This checkpoint does **not** perform network requests, launch a browser, access the filesystem, call YouTube, invoke an AI provider, or register any action handler. These are contracts only. DNS resolution, redirect checks, connected-IP pinning, file descriptor/symlink-safe access, content sanitization, source provenance, cancellation and audit integration must be implemented and verified in a later adapter checkpoint before any capability is exposed in the UI.

## Safety invariants

- Read-only means no create/edit/delete/send/publish/share action.
- Contracts never grant approval or execution authority.
- Unknown actions continue to fail closed through `ExecutionGateway`.
- Browser/Worker remain disabled; Auto-Run remains OFF.
- Free-only; no API keys, paid providers, payment, purchase, trading or money movement.

## Verification

The exact-head GitHub Actions workflow is required before this checkpoint can be marked automated-PASS. A passing unit suite does not qualify a live network or filesystem adapter.

**Next:** P77 — implement one bounded read-only adapter at a time, starting with a connector whose transport and source allowlist can be independently tested.
