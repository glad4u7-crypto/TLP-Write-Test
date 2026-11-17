# APAA Personal Edition P88 — Encrypted Android Backup & Restore

**Status:** Implementation and exact-head CI PASS on `3e397a2f501a3d5d6a57c1f19bf69e912ef73ed8` (run #533).
**Scope:** Protect portable Personal Edition backups before they leave the Android device.

## Implemented

- New backups from the Owner UI are encrypted before download; plaintext ZIP is held only inside a private temporary directory and removed when that directory is cleaned up.
- Passphrase-based key derivation uses scrypt; file contents are encrypted/authenticated in 1 MiB chunks using AES-256-GCM.
- The authenticated header includes format/version, chunk size and expected plaintext length. Chunk order, lengths and ciphertext are authenticated; truncation at a complete-chunk boundary is rejected.
- The encryption/decryption routines stream files rather than buffering the entire archive in RAM, enforce a 512 MiB bound, require owner-only source files and a private destination directory, and create output atomically.
- Restore accepts encrypted `.apaa.enc` archives and decrypts into a private temporary file before the existing ZIP inventory/hash/SQLite/audit-chain validation.
- Legacy plain ZIP restore remains available only after an explicit warning acknowledgement.
- The approval signing key remains excluded from backups; restore continues to create a fresh signing key.

## Owner responsibilities

- Use a unique strong backup passphrase and keep it separately from the backup file.
- If the passphrase is lost, APAA cannot recover the backup.
- Do not send the passphrase to anyone or include it in screenshots/logs.
- Keep backup archives in private storage. Encryption does not protect a device already unlocked by an attacker.

## Verification

New tests cover multi-chunk round-trip, wrong passphrase, ciphertext tampering, truncation (including truncation at a complete authenticated-chunk boundary), weak passphrases, source file permissions and destination directory privacy. Exact-head GitHub Actions run [#44044293281](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/44044293281) passed: **1,590 Python tests passed, 9 skipped; compile PASS; dependency audit PASS (no known vulnerabilities); Android-sized Chromium browser smoke 10 passed.** This is browser emulation, not physical Android qualification. Physical Android performance and restore testing remain pending.

## Unchanged safety boundary

- No LAN/public listener, remote control, background startup or Auto-Run.
- Browser/Worker execution remains disabled.
- No payment, purchase, trading or money movement.
- No PR merge or deployment.
