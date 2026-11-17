# APAA Personal Edition — P79 Approved Mutation Safety

**Checkpoint:** APAA-PERSONAL-P79  
**Date:** 2026-11-17  
**Branch:** `apaa-personal-edition-foundation`  
**Status:** Core safety implementation and first Personal Edition Owner UI integration committed; latest exact-head CI pending. External adapter workflows remain gated on P78.  
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
- The gateway snapshots the caller's JSON payload before approval verification and passes only that private snapshot to the handler, preventing post-approval mutation of the caller-owned mapping from changing the dispatched request. Non-finite/non-JSON payloads fail closed.
- The existing project-create UI now configures the durable idempotency ledger. Each reviewed project draft receives a fresh random request key; the gateway requires the validated Owner tenant and key, and a repeated key cannot create a second project.
- Memory, knowledge, conversation, preference and checkpoint UI mutations now consume fresh one-time `ApprovalAuthority` receipts bound to action + exact JSON payload + Owner tenant + current session. The mutation operation receives only the approved private JSON snapshot. Audit intent is still persisted before the operation; missing, invalid, expired, replayed or mismatched receipts block dispatch.
- Durable intent audit is written before the handler. Audit failure blocks dispatch.
- A cancellation callback is checked immediately before the handler starts. A pre-dispatch cancellation becomes terminal and cannot be replayed. A synchronous handler already in progress is not represented as cancellable.
- Handler exceptions and post-side-effect audit/ledger failures are treated as uncertain outcomes, not safe-to-retry failures.
- Pending/uncertain requests are visible through a metadata-only owner-scoped recovery query. An uncertain outcome can only be reconciled through a separate method requiring explicit `owner_confirmed=True`; that storage method is not itself an authentication boundary and must only be called from the trusted authenticated Owner controller.
- Regression tests cover tenant isolation, action/payload conflict, restart persistence, duplicate/replay blocking, concurrent claims, cancellation, ambiguous handler failure, and explicit Owner reconciliation.

## Important limitations

- This is a generic dispatch/storage safety primitive. The current project-create handler is wired through the durable ledger, and existing local memory/knowledge/conversation/preference/checkpoint UI mutations use the payload-bound receipt wrapper. It does not register new file/email/YouTube mutation handlers.
- P78's bounded read-only adapters are not present on the current branch. Browser/file/YouTube research and subsequent mutation workflows are therefore not available. P79 recovery records can be inspected through the storage API, but a dedicated Owner UI for reconciling uncertain external outcomes remains outstanding.
- The current cancellation contract is pre-dispatch only. Long-running external operations require adapter-specific cooperative cancellation and remote outcome reconciliation.
- A local SQLite ledger protects against accidental duplicate dispatch and process restart; it is not an external anti-tamper anchor against an attacker controlling the same OS account.

## Verification

- Exact-head GitHub Actions run [#160](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/44019306207) passed for its tested head `1429ee69aa637b0927e0ef234ab0e6432e4d8b5d` (Python, compile, dependency audit and responsive browser smoke). The subsequent Owner UI receipt and project idempotency integration commits are newer and require a fresh exact-head run.
- P78 remains a prerequisite for end-to-end mutation workflows.

## Safety

- Auto-Run remains OFF.
- No handler is enabled by this checkpoint.
- Payment, purchase, checkout, trading, investment orders, money movement, paid services and external paid providers remain denied.
- Browser/Worker remain disabled. No deployment, merge, or public exposure.

**Disposition:** P79 safety primitives implemented; integration and exact-head verification pending.


## Verification update

- Earlier P79 integration head `63174c17cbb60958ca746aaf76886b7bb12eb355`, P73 Verification run #148: **PASS** — Python **1,463 passed, 9 skipped**; compile PASS; dependency audit found no known vulnerabilities; responsive browser smoke **9 passed**.
- Follow-up hardening after #148: handler dispatch now uses a private JSON snapshot of the approved payload; malformed ledger transition values are rejected; regression tests cover payload snapshot isolation and malformed state inputs.
- Latest follow-up head `a9cf556de7f38a6bae876c9cd3fbe9d8e1526df4`, P73 Verification run #157: **IN PROGRESS** at the time of this update. Do not treat #148 as verification of the later snapshot/input-validation commits.
- P79 remains implementation-pending-final-exact-head-verification and Owner UI integration.
