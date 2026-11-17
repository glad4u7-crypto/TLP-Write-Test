# APAA Personal Edition P84 — Owner Project File Workspace

**Status:** Implemented; exact-head CI verification required.
**Scope:** Owner-approved storage and bounded read-only inspection of small project text files.

## Available workflow

- Upload a UTF-8 text file into the selected project's private local directory.
- Explicit Owner consent is required, and the upload passes through the fresh payload-bound approval and audit flow.
- Approval binds the project ID, exact filename, byte count and SHA-256 digest; file contents are not copied into the action audit payload.
- The Owner can list and inspect stored project files through the bounded FILE_INSPECT adapter.
- Inspection returns at most 2,000 excerpt characters and never executes or renders file contents as HTML.

## Storage and validation

- Files are stored under the local Personal Edition data directory in owner-only directories and owner-only files.
- Only approved UTF-8 text extensions are accepted; each file is limited to 64 KiB.
- Path traversal, absolute paths, hidden filenames, symlinks, overwrite, binary/null-containing data and credential-like content are rejected.
- Files are created atomically with exclusive create and no-follow flags.
- Listing uses no-follow file opens and ignores symlinks, non-regular files, oversized files and non-text content.
- Project file upload widget state is cleared on Owner identity/session transitions.

## Limits

- This is not arbitrary filesystem access. It does not expose the Android filesystem, Downloads, Photos, other apps' data, shell or write/delete APIs.
- No arbitrary file execution, macro execution, browser action or external upload is enabled.
- The feature is local Personal Edition only. It does not activate in the OIDC/remote deployment path.
- File storage is included within the existing private Personal Edition data directory; the memory/project backup archive covers the memory database but this P84 folder is not yet included in backup. Treat file-workspace backup as a follow-up implementation requirement before relying on it for important documents.

## Verification

Core tests cover explicit consent, private permissions, overwrite denial, unsafe paths, binary/oversized/credential-like content, symlinked files and symlinked data roots. Exact-head CI is required before marking this checkpoint verified.