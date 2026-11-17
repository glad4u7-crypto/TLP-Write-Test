# APAA Personal Edition P86 — Android Launcher Preflight Hardening

**Status:** Implementation and exact-head CI PASS on `ce9d2e82849d33719d7e33749400d2a4d513d09f` (run #447).
**Target:** Android-first Termux/browser launch path. This is a local launcher hardening checkpoint, not a native APK project.

## Implemented

- Added a dedicated Python preflight before Streamlit starts.
- Validates the configured TCP port strictly (decimal digits, 1024–65535).
- Requires an absolute Personal Edition data directory.
- Creates the data directory if absent, rejects symlink/non-directory targets, verifies current-user ownership on POSIX, and enforces mode 0700.
- Uses directory-only and no-follow open flags when verifying the POSIX data directory.
- Confirms Streamlit is installed in the active Termux Python environment before launching, with a clear non-secret error.
- Launcher remains bound to 127.0.0.1 only; no LAN/public binding, boot persistence, Auto-Run or background worker is introduced.
- Does not install packages, modify Android permissions, create an Owner, rotate keys or change application databases.

## Verification

Automated tests cover valid/invalid ports, relative paths, private directory creation and permissions, symlink/non-directory rejection and missing Streamlit dependency handling. Exact-head P73 Verification run [#447](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/44034637645) passed on the implementation head: **1,557 Python tests passed, 9 skipped; compile PASS; dependency audit PASS (no known vulnerabilities); responsive browser smoke 9 passed.**

## External acceptance still required

- Physical Android A01–A12 on the actual device.
- Owner-operated backup → clean restore → project-file hash/content verification.
- Independent security review before remote exposure or production deployment.

## Safety

Browser/Worker DISABLED; Auto-Run OFF. No paid APIs/providers, API keys, payments, purchases, trading or money movement. PR #13 remains Draft/Open/Unmerged; no merge/deployment.
