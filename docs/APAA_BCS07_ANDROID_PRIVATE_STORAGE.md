# APAA BCS-07 — Android Owner Secret-Storage Hardening

## Objective

Prevent APAA's Android Owner UI from starting when its OIDC client secret, cookie secret, or approval-signing key is stored in a symlinked or group/world-readable configuration location.

## Implemented

- validate_private_secret_storage uses lstat to reject symlinked .streamlit directories and symlinked secret files.
- Requires .streamlit to be a real directory and secrets.toml to be a regular file.
- Requires directory permissions to exclude group/other access (expected 0700) and file permissions to exclude group/other access (expected 0600).
- load_owner_secrets enforces the storage check before reading TOML, so the launcher and handset diagnostics share the same fail-closed rule.
- Added D08 to the handset diagnostics; output reports only a safe status and never displays secret values.
- Added tests for valid private storage, world-readable files, and symlinked secrets; Owner launcher tests now create valid private configuration fixtures.

## Safety boundary

- No permission repair or chmod is attempted at runtime. APAA refuses unsafe storage rather than silently changing it.
- The setup wizard remains responsible for creating a private directory/file.
- No credentials are copied, exported, printed, or transmitted.
- This does not encrypt the secrets file at rest and does not protect against a compromised Android account, compromised Termux process, or malicious code running as the same OS user.
- PRoot is not a security sandbox. Android Chrome remains an Owner UI only; Browser/Worker dispatch remains disabled.
- No Auto-Run, payment, purchase, trading, money movement, public access, merge, or deployment.

## Verification plan

Automated tests cover permission and symlink rejection. Exact-head APAA Security CI must pass before this code is treated as CI-verified. Physical Android D08 must be run on the actual handset later; the Owner explicitly deferred physical handset tests, so no handset result is claimed.

## Status

Implementation added on feature/apaa-bcs07-android-storage-hardening. Draft PR only; do not merge until exact-head CI and required reviews are complete.