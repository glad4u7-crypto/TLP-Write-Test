# APAA-S09-C01-P66 — Authenticated Android deployment preflight

**Checkpoint:** P66  
**Date:** 2026-11-16  
**Branch:** `feature/apaa-s09-c01-p16-oci-lifecycle`  
**Status:** Preflight implementation committed; exact-head CI verification pending; no deployment performed.

## 1. What was added

- `scripts/preflight_android_deployment.py` — read-only deployment configuration preflight.
- `tests/test_android_deployment_preflight.py` — tests for required OIDC configuration, strict boolean authentication, HTTPS URL validation, signing-key format/length, absolute/private/distinct database paths, missing directories, and secret-file privacy.
- `requirements.txt` — conditional `tomli` dependency for Python 3.10; Python 3.11+ uses standard-library `tomllib`.

## 2. Fail-closed checks

The preflight blocks unless all of the following are true:

1. A Streamlit `[auth]` OIDC section exists with client ID, client secret and cookie secret.
2. OIDC redirect URI and discovery metadata URL are HTTPS URLs without ambiguous credentials or fragments.
3. `[apaa].require_auth` is the literal TOML boolean `true` (not a string, integer or false).
4. `approval_signing_secret_hex` is valid hexadecimal and decodes to at least 32 bytes.
5. Security, project and memory SQLite paths are explicitly configured, absolute, distinct, outside the application checkout, and have existing writable parent directories.
6. The supplied secrets file is a regular non-symlink file and, on POSIX, is owner-readable only (0600 or stricter).

Secret values are never printed. The tool reports only pass/fail categories.

## 3. How the deployment operator runs it

Run this on the private deployment host or its trusted administrative shell, not inside a public browser session:

```bash
python scripts/preflight_android_deployment.py --secrets /absolute/private/path/secrets.toml
```

The secrets file must be provisioned through the deployment's protected secret mechanism. Do not upload it to GitHub, ChatGPT, chat, screenshots or the repository. If a hosting provider supplies secrets through a managed secret store rather than a mounted TOML file, do not export them to make this script pass; use an approved protected mount or adapt the preflight to the provider's native secret interface in a separately reviewed change.

## 4. Critical limits

A configuration PASS is not a deployment PASS. This utility cannot prove:
- that the host is owner-controlled or private;
- that HTTPS/TLS is correctly terminated end-to-end;
- that the OIDC provider, callback, account ownership and live login work;
- that SQLite paths are backed by durable private persistent volumes or survive restart/restore;
- that server-side revocation works across existing sessions;
- that cookies, CSRF, proxy headers, network isolation, host controls or backups are secure.

Those require owner-operated environment checks and independent evidence. Do not create an unauthenticated public instance as a shortcut. Do not paste secrets into chat.

## 5. Verification state and release locks

The last verified exact-head CI remains P64 commit `200c9e11b08ff087103b70aa3daa3b8846f3469d` (four workflows PASS). P65/P66 changes are newer; the GitHub Actions API has not returned runs for these new commits, so **P66 exact-head CI is PENDING**. Do not carry forward P64 PASS to P66.

- Physical Android A01–A12: BLOCKED until owner-approved private HTTPS instance exists.
- Two-account live OIDC grant/revoke: BLOCKED until owner-controlled test identities and configured provider exist.
- C01: OPEN / NOT COMPLETE.
- C02: NOT STARTED.
- PR #11: Draft / Open / Unmerged.
- Auto-Run OFF; Worker/Browser DISABLED.
- No paid services, API keys, payment/purchase, host mutation, merge or deployment.

## 6. Next real gate

The remaining action is environmental, not another mock test: an owner-approved private test deployment with protected OIDC secrets and private persistent storage must be provisioned. Then run the preflight on that host, perform the physical Android guide P64, complete live two-account grant/revoke checks, and obtain independent review. If no free provider can supply the required private authentication and persistent storage without charges or unsafe public exposure, keep the deployment blocked rather than weakening the controls.
