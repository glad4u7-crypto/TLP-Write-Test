# APAA Personal Edition P82 — Owner Backup & Restore UI

**Status:** Implemented; exact-head CI verification required.
**Scope:** Local Personal Edition Owner-only backup and non-destructive restore controls.

## Owner interface

The local Owner sidebar exposes a collapsed **Personal Backup & Restore** panel after successful Owner authentication.

- Create a consistent SQLite backup using the existing tested backup service.
- Download the archive from the authenticated local session.
- Upload a prior APAA ZIP backup for validation and restore.
- Restore always targets a newly generated sibling directory. It never overwrites the live data directory.
- The Owner must stop APAA and explicitly point `APAA_PERSONAL_DATA_DIR` to the restored directory before using that copy.
- Restore creates a fresh approval signing key, invalidating outstanding approval receipts.

## Security properties

- The panel is hidden in the OIDC deployment path and is available only in local Personal Edition mode.
- Uploads larger than 512 MiB are rejected before writing to disk.
- The temporary uploaded archive is created with owner-only file permissions and removed after restore attempts.
- Existing backup service verifies archive inventory, file sizes and hashes, SQLite integrity, action audit chain, Owner authentication event chain, and creates a fresh signing key.
- Backup archives are **not encrypted**. The UI warns the Owner to keep the archive private and never share or upload it publicly.
- No backup or restore runs automatically. The Owner must explicitly click the relevant control.
- No live data directory is replaced or deleted.

## Run-time limits

The restore destination is a separate directory. This UI deliberately does not switch the running application to that restored directory, restart the process, or silently replace the active data. The Owner must perform that cutover deliberately after stopping APAA.

Physical Android backup/restore acceptance remains a later Owner-operated check. Automated CI does not substitute for it.