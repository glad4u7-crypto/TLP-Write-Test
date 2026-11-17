# APAA Personal Edition P78 — Safe Read-only Adapters

**Status:** Implemented; exact-head CI required before PASS.

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
