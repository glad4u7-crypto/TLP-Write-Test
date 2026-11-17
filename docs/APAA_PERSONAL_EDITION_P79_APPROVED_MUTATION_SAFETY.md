# APAA Personal Edition — P79 Approved Mutation Safety

**Checkpoint:** APAA-PERSONAL-P79  
**Date:** 2026-11-17  
**Branch:** `apaa-personal-edition-foundation`  
**Status:** Core safety implementation committed; exact-head CI pending. Adapter/UI integration is gated on P78.  
**PR:** #13 — Draft / Open / Unmerged.

## Scope

Implement the safety boundary for future Owner-approved mutations: exact action and payload approval, durable audit before dispatch, tenant-scoped idempotency, pre-dispatch cancellation, and explicit recovery for ambiguous outcomes. This checkpoint does not enable new external or filesystem mutation adapters.

## Implemented

- Extended `SQLiteSecurityStore` with a tenant-scoped `execution_idempotency` ledger.
- Idempotency keys are unique per Owner tenant and bound to the canonical action plus SHA-256 digest of the canonical JSON payload. Raw payloads and handler outputs are never stored in the ledger.
- The ledger atomically claims a key under SQLite `BEGIN IMMEDIATE`; concurrent duplicate claims have one winner.
- Reuse of a key with a different action or payload returns conflict. Same-payload duplicate requests in pending/completed/uncertain/cancelled states are never automatically dispatched again.
- `ExecutionGateway` can be configured with the durable ledger. When configured, every handler dispatch requires a validated `TenantKey` and an idempotency key.
- Existing one-time approval receipts remain action-, payload-, tenant- and session-bound. Receipt consumption occurs before dispatch and cannot be replayed.
- Durable intent audit is written before the handler. Audit failure blocks dispatch.
- A cancellation callback is checked immediately before the handler starts. A pre-dispatch cancellation becomes terminal and cannot be replayed. A synchronous handler already in progress is not represented as cancellable.
- Handler exceptions and post-side-effect audit/ledger failures are treated as uncertain outcomes, not safe-to-retry failures.
- Pending/uncertain requests are visible through a metadata-only owner-scoped recovery query. An uncertain outcome can only be reconciled through a separate method requiring explicit `owner_confirmed=True`; that storage method is not itself an authentication boundary and must only be called from the trusted authenticated Owner controller.
- Regression tests cover tenant isolation, action/payload conflict, restart persistence, duplicate/replay blocking, concurrent claims, cancellation, ambiguous handler failure, and explicit Owner reconciliation.

## Important limitations

- This is a generic dispatch/storage safety primitive. It does not yet register new project/file/email/YouTube mutation handlers.
- P78's bounded read-only adapters are not present on the current branch. P79 must not be treated as a complete end-to-end user workflow until P78 is implemented and its source provenance and permissions are tested.
- The current cancellation contract is pre-dispatch only. Long-running external operations require adapter-specific cooperative cancellation and remote outcome reconciliation.
- A local SQLite ledger protects against accidental duplicate dispatch and process restart; it is not an external anti-tamper anchor against an attacker controlling the same OS account.

## Verification

- Exact-head GitHub Actions for the P79 commits is pending/not yet observed.
- Do not mark P79 automated PASS until all workflow jobs for the final exact head pass.
- P78 remains a prerequisite for end-to-end mutation workflows.

## Safety

- Auto-Run remains OFF.
- No handler is enabled by this checkpoint.
- Payment, purchase, checkout, trading, investment orders, money movement, paid services and external paid providers remain denied.
- Browser/Worker remain disabled. No deployment, merge, or public exposure.

**Disposition:** P79 safety primitives implemented; integration and exact-head verification pending.
