# APAA S09 C01 P36 Part 04 — Durable Owner Access Audit Trail

Status: IMPLEMENTED; exact-head CI verification pending.

## Delivered

- Added a durable `project_access_events` SQLite table for owner-initiated grant and revoke events.
- Each event records a unique event ID, project ID, action, exact grantee issuer + subject, exact actor issuer + subject, and UTC timestamp.
- Grant events are written in the same SQLite transaction as the grant/upsert. A failed grant cannot leave a success event.
- Revoke events are written in the same transaction as the active-grant revocation. Repeated revoke attempts that change no grant do not create false events.
- Added `list_events_for_owner`; only the exact immutable project owner can read event history.
- Event history is separate from the current grant row, so revoke/regrant history is retained rather than overwritten.
- SQLite BEFORE UPDATE and BEFORE DELETE triggers reject attempts to alter or erase recorded access events; regression tests exercise both protections.
- Added regression tests for grant/revoke event order and identity binding, no-op revoke behavior, non-owner denial, and persistence after reopening the SQLite store.

## Security boundary

This is an audit persistence primitive, not a collaborator-management UI or a public API. No grant/revoke controls were exposed in Streamlit. Collaborator access remains disabled at the application layer until every project, action, file, memory and checkpoint boundary is reviewed and connected to the ACL. Granting read access does not grant write, execution, secrets, invitations, browser or worker authority.

## CI

Earlier P36 Part 03 exact head `392ec9168d59279ef6549040bf181136ef227dd9` completed all six checks successfully: Python Demo, main tests, Android-sized Chromium viewport, disposable Linux egress namespace, Podman executor plumbing and disposable rootless Podman lifecycle.

The current Part 04 implementation has advanced through immutable-event enforcement and its regression tests. The exact latest head must be checked on GitHub before any PASS claim; earlier runs do not qualify as exact-head evidence.

## Remaining C01 gates

- P36 Part 05 now adds a narrow owner-only read-grant/revoke controller; no UI/API exposure or privilege beyond read is enabled.
- P36 Part 06 records the project/action/file/memory/checkpoint authorization audit. Collaborator access remains disabled; project checkpoint association still needs an independent project-owner guard before any future collaborator/API exposure.
- P36 Part 07 adds deterministic two-principal, immediate revocation, immutable event sequence and session-transition regression tests. Live two-user OIDC and cross-device invalidation remain external.
- P36 Part 08 adds Android Pixel viewport and PC desktop Chromium smoke coverage to Agent Foundation CI. Physical Android/PC browser testing remains external.
- Complete owner-approved real-host OCI/network qualification and independent review required by the existing P31 closure inventory.

PR #11 remains Draft/Open/Unmerged. C01 remains OPEN / NOT COMPLETE. Android-first plus PC support remains a product requirement. Ask First stays enabled, Auto-Run OFF, payments and paid providers prohibited, browser/worker disabled; no host mutation, firewall change, deployment, merge or C02 start is authorized.
