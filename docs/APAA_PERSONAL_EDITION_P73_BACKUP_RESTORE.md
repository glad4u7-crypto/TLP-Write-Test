# APAA Personal Edition P73 — Backup and Restore

**Checkpoint:** APAA-PERSONAL-P73  
**Status:** Repository implementation and automated tests added; exact-head CI verification required.

## What is backed up

The backup archive contains consistent SQLite snapshots of:
- `projects.sqlite3` — owner projects;
- `security.sqlite3` — consumed approval nonces and durable action-audit hash chain;
- `owner-auth.sqlite3` — salted Owner passphrase verifier and persistent login-throttling state;
- `memory.sqlite3` — consented memories, knowledge, conversation turns, preferences and task checkpoints;
- `manifest.json` — format version, file sizes and SHA-256 digests.

The local approval signing key is deliberately **not** exported. Restore generates a new owner-only key, so all outstanding approval receipts become invalid. The Owner authentication database is preserved so the configured Owner passphrase remains valid after restore. Previously consumed nonce records, the durable action-audit chain and the Owner authentication event chain/head are preserved.

## Safety properties

- Source data directory, database files, backup file and restored directory are checked for symlinks and owner-only permissions.
- Each database is snapshotted using SQLite's online backup API, then checked with `PRAGMA integrity_check`.
- The security database audit chain and the separate Owner authentication event hash chain are verified before export and after restore. Legacy Owner-auth snapshots are migrated before the final snapshot digest is recorded.
- The archive has an exact file allowlist, duplicate-entry rejection, bounded sizes, CRC checks and per-file SHA-256 verification. The Owner authentication event chain is also verified semantically; a recomputed archive manifest cannot make a tampered event chain valid.
- Restore writes into a staging directory and atomically renames it to a **new, non-existing** destination. It never overwrites a live data directory.
- Restore rejects malformed manifests, path traversal entries, symlinks and corrupted databases.

**Important:** The archive is not encrypted. It is created with owner-only filesystem permissions, but anyone who obtains a copy can read its project and memory data. Store it only in a private, owner-controlled location. For a cross-database consistent snapshot, stop APAA before creating the backup; SQLite guarantees consistency per database, not a single transaction across all four databases.

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


## Automated verification status — 2026-11-17

The current Personal Edition branch head `70ede93d20e7ff2780c7d4d1dbd68e2803a96a06` passed P73 Verification run [#235](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/44023947699): 1,491 Python tests passed, 9 skipped; compile and dependency audit passed; 9 responsive browser smoke tests passed. The full Python suite includes the repository's automated backup/restore integrity, tamper rejection, audit-chain and approval-key rotation coverage.

**Owner-operated Android backup/restore remains NOT RUN.** The Owner must perform the drill on the intended local runtime using synthetic data and a private local path. Do not upload the unencrypted backup archive or share it in chat. Preserve the original data directory until the restored instance is verified.
