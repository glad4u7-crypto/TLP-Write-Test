# APAA Personal Edition P73 — Backup and Restore

**Checkpoint:** APAA-PERSONAL-P73  
**Status:** Repository implementation and automated tests added; exact-head CI verification required.

## What is backed up

The backup archive contains consistent SQLite snapshots of:
- `projects.sqlite3` — owner projects;
- `security.sqlite3` — consumed approval nonces and durable action-audit hash chain;
- `memory.sqlite3` — consented memories, knowledge, conversation turns, preferences and task checkpoints;
- `manifest.json` — format version, file sizes and SHA-256 digests.

The local approval signing key is deliberately **not** exported. Restore generates a new owner-only key, so all outstanding approval receipts become invalid. Previously consumed nonce records and the durable audit chain are preserved.

## Safety properties

- Source data directory, database files, backup file and restored directory are checked for symlinks and owner-only permissions.
- Each database is snapshotted using SQLite's online backup API, then checked with `PRAGMA integrity_check`.
- The security database audit chain is verified before export and after restore.
- The archive has an exact file allowlist, duplicate-entry rejection, bounded sizes, CRC checks and per-file SHA-256 verification.
- Restore writes into a staging directory and atomically renames it to a **new, non-existing** destination. It never overwrites a live data directory.
- Restore rejects malformed manifests, path traversal entries, symlinks and corrupted databases.

**Important:** The archive is not encrypted. It is created with owner-only filesystem permissions, but anyone who obtains a copy can read its project and memory data. Store it only in a private, owner-controlled location. For a cross-database consistent snapshot, stop APAA before creating the backup; SQLite guarantees consistency per database, not a single transaction across all three databases.

## Create a backup

Stop APAA first, then run from the repository root:

```bash
python scripts/backup_personal_data.py \
  --output /absolute/private/path/APAA-Personal.apaa-backup
```

The source data directory defaults to `$APAA_PERSONAL_DATA_DIR`, or `~/.apaa_personal` if the environment variable is not set.

## Restore to a new directory

The destination must not already exist. Its parent directory must already exist.

```bash
python scripts/restore_personal_data.py \
  --backup /absolute/private/path/APAA-Personal.apaa-backup \
  --destination /absolute/private/path/apaa-restored
```

Then start APAA using the restored data directory:

```bash
APAA_PERSONAL_DATA_DIR=/absolute/private/path/apaa-restored \
  streamlit run app.py --server.address=127.0.0.1
```

The application remains loopback-only in unauthenticated Personal Edition mode. Do not expose it to a LAN or the public internet.

## Recovery verification

After restore:
1. Confirm the app opens with no storage or audit-integrity error.
2. Confirm the expected owner projects and checkpoints appear.
3. Confirm the latest action-audit chain verifies.
4. Confirm the approval signing key was regenerated and old approval receipts are rejected.
5. Keep the original data directory unchanged until the restored instance is reviewed.

A successful automated restore test is software evidence only; it is not a substitute for an owner-operated recovery drill on the actual Android/host environment.
