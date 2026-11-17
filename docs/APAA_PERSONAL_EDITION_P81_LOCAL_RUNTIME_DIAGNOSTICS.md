# APAA Personal Edition P81 — Local Runtime Diagnostics

**Status:** Implemented; exact-head CI verification required.  
**Scope:** Read-only diagnostics for the Personal Edition local data directory.

## What it checks

- The data directory exists, is a real directory, and has owner-only POSIX permissions.
- Existing project, security, Owner-authentication and memory SQLite databases pass SQLite `quick_check` opened read-only.
- The local approval signing key is a regular non-symlink file with owner-only POSIX permissions and the expected 32-byte length. Key material is never printed.
- The execution audit-log path is a regular non-symlink file.

Missing databases or an uninitialized data directory are reported as INFO, not errors. Corrupt databases, unsafe paths, invalid key metadata and insecure directory permissions fail closed.

## Run

```bash
python scripts/apaa_doctor.py
```

Or specify the existing Personal Edition data directory:

```bash
python scripts/apaa_doctor.py --data-dir /path/to/.apaa_personal
```

The script does not create the data directory, initialize an Owner, rotate a key, repair a database, change permissions, or modify application state. It prints metadata-only results and exits non-zero if any check fails.

## Limits

This is a local filesystem/SQLite preflight, not a penetration test, independent security review, physical Android acceptance, browser-worker qualification or proof against an attacker controlling the same OS account. It does not enable Browser/Worker, Auto-Run, network providers or any mutation handler.


## Owner UI integration — 2026-11-17

- Added a collapsed **Personal Runtime Health** panel to the authenticated local Owner sidebar.
- Owner can explicitly run the P81 read-only diagnostics and see PASS/FAIL/INFO counts and per-check details.
- The panel is hidden in the OIDC deployment path and appears only in local Personal Edition mode.
- No automatic repair, key rotation, database creation, or state mutation is performed.
- UI integration is subject to exact-head CI; it is not yet marked verified until that run completes.
