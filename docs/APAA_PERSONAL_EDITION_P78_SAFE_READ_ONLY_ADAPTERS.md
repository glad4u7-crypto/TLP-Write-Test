# APAA Personal Edition P78 — Safe Read-only Adapters

**Status:** Implemented; exact branch-head CI PASS on 2026-11-17.

## Scope
P78 adds a narrow read-only adapter boundary without enabling browser/worker execution or arbitrary action handlers.

## Implemented
- `core/read_only_adapters.py` provides a typed allowlist registry with a read-only `read()` surface only.
- `ProjectFileReadAdapter` resolves the selected project root through a trusted server-side resolver, opens each path component relative to a directory descriptor with no-follow semantics, rejects symlinks and non-regular files, enforces a 64 KiB cap, and accepts strict UTF-8 text only.
- `InjectedReadOnlyProviderAdapter` wraps an explicitly supplied read-only provider for web search, HTTPS page reading or YouTube discovery. No network client/provider is instantiated or enabled by default.
- All results pass the P76 immutable result contract and per-request item bounds.
- No adapter is registered with `ExecutionGateway`; there is no write, delete, send, publish, browser launch or execute method.

## Owner Recovery UI
- The authenticated Owner sidebar lists tenant-scoped pending/uncertain execution metadata.
- Pending outcomes remain unresolved and cannot be classified from the UI.
- Uncertain outcomes require the Owner to confirm that the external system was checked, then explicitly choose completed or cancelled.
- Reconciliation does not retry or repeat the underlying action.
- The state transition and a payload-free hash-chain audit event commit in one SQLite transaction.

## Limits / disabled capabilities
- Web search, page reading and YouTube discovery remain unavailable until an independently reviewed provider/transport is explicitly injected.
- DNS pinning, redirect policy, TLS verification, remote-source provenance and network egress are not qualified by this checkpoint.
- Browser/Worker remain DISABLED; Auto-Run OFF; Global Owner remains inactive unless separately provisioned.
- No paid API/provider, API key, payment, purchase, trading or money movement.

## Verification
Exact-head CI is required. Physical Android acceptance, owner-operated backup/restore drill, independent security review and final Owner acceptance remain external gates.


## Real network providers — 2026-11-17

Concrete public read-only providers are now implemented in `core/safe_network_providers.py` and exposed behind an explicit Owner-session `Public Web Research · Read-only` form in the sidebar:

- DuckDuckGo public HTML search
- Public HTTPS HTML/XHTML/plain-text page reader
- YouTube public search result reader (video discovery only)

The providers use direct HTTPS, DNS resolution with globally-routable IP validation, pinned-IP TCP connections, TLS hostname verification, manual bounded redirects, response size/time limits, and no cookies/proxy/browser/JavaScript. The UI performs no request until the Owner explicitly submits the form. Results are displayed as text with explicit source-open links. See `docs/APAA_PERSONAL_EDITION_P78_NETWORK_PROVIDERS.md` for the security boundary and limitations.


## Exact-head verification — 2026-11-17

P73 Verification run [#235](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/44023947699) passed on branch head `70ede93d20e7ff2780c7d4d1dbd68e2803a96a06`:
- Python suite: **1,491 passed, 9 skipped**
- Python compilation: PASS
- Dependency audit: PASS; no known vulnerabilities
- Responsive Android/Desktop Chromium smoke: **9 passed**

This qualifies repository code and automated tests only. It does not qualify a physical Android device, live external provider availability, browser worker, host firewall, or network egress isolation.
