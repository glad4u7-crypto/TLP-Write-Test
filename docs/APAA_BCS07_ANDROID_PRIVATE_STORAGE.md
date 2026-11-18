# APAA BCS-07 — Android Owner Secret-Storage Hardening

## Objective

Prevent APAA's Android Owner UI from starting when its OIDC client secret, cookie secret, or approval-signing key is stored in a symlinked or group/world-readable configuration location.

## Implemented

- Opens the .streamlit directory with directory/no-follow flags, then opens secrets.toml relative to the pinned directory descriptor with no-follow semantics.
- Checks file type and POSIX permissions using fstat on the opened descriptors. This avoids the ordinary lstat-then-open symlink-swap window for the final directory/file components.
- Requires .streamlit to be a real directory and secrets.toml to be a regular file.
- Requires directory permissions to exclude group/other access (expected 0700) and file permissions to exclude group/other access (expected 0600).
- load_owner_secrets parses TOML from the already-open file descriptor, so validation and reading use the same opened file object.
- Malformed redirect/metadata ports are converted into safe configuration errors; only the fixed loopback OIDC callback and HTTPS discovery metadata are accepted.
- Added D08 to the handset diagnostics; output reports only a safe status and never displays secret values.
- Added tests for valid private storage, world-readable files, symlinked secret files, and symlinked .streamlit directories; Owner launcher fixtures include required signing material and private permissions.

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