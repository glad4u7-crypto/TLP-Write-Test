# APAA Personal Edition — Android Owner Acceptance Runbook

**Checkpoint:** APAA-PERSONAL-P74 / ANDROID-PHYSICAL-QUALIFICATION  
**Target:** Owner's physical Android phone  
**Status:** Qualification preparation started; physical acceptance NOT RUN.  
**Application:** Streamlit web prototype; not a native APK or installable PWA.

## Safety and scope

- Run only on the Owner's own Android device with synthetic test data.
- Bind the app to `127.0.0.1` only. Never use `0.0.0.0`, LAN IP, public tunnel or public deployment.
- Open only `http://127.0.0.1:8501` in Android Chrome on the same phone.
- Do not enter real personal content, passwords used elsewhere, OTPs, cookies, API keys, recovery codes or financial data.
- No paid hosting, paid provider, API key, payment, purchase, Auto-Run or external account connection is part of this test.
- If the runtime cannot be installed or launched on Android, record **BLOCKED**. Do not bypass security controls or mark emulated desktop tests as physical Android PASS.

## Stage 0 — Device/runtime preflight (start here)

The repository currently supports a Streamlit Python prototype. Android/Termux compatibility has not been qualified. If using Termux, install it only from its official F-Droid/GitHub distribution source; do not use an untrusted APK mirror. The following commands are a qualification attempt, not a guarantee that every dependency supports Android:

```sh
pkg update
pkg install python git
git clone --branch apaa-personal-edition-foundation https://github.com/glad4u7-crypto/TLP-Write-Test.git
cd TLP-Write-Test
python --version
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If installation succeeds, start the app with an explicit loopback bind:

```sh
streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
```

Then, on the same phone, open Android Chrome and navigate to `http://127.0.0.1:8501`.

**Stop immediately** if Streamlit reports a non-loopback bind, Chrome opens a different origin, a certificate/security warning appears, or the process requires disabling Android security. If a dependency fails to build, capture only the package/error name and mark runtime qualification BLOCKED; do not try random binaries or unreviewed patches.

### Preflight evidence to return to the project

- Android device model and Android version.
- Termux version/source (or the actual Python runtime used).
- Python version.
- Exact repository commit shown by `git rev-parse HEAD`.
- Whether dependency installation completed (yes/no) and the first failing package name if not.
- Whether Streamlit started and its displayed Local URL (redact any local secrets).
- Chrome version and whether `127.0.0.1:8501` displayed the Owner gate.

Never send a passphrase, environment variable dump, secrets file, browser profile, cookies or full private logs.

## A01–A12 physical acceptance cases

| ID | Test | Expected result | Evidence |
|---|---|---|---|
| A01 | Start the app with loopback-only binding; open `http://127.0.0.1:8501` | Same-device access only; Owner gate appears | Redacted screenshot + origin + runtime details |
| A02 | Complete first-run local Owner passphrase setup, logout, sign in | Only configured local Owner passphrase unlocks APAA | Redacted result; never capture passphrase |
| A03 | Open a fresh/incognito browser session without passphrase | Owner data and mutation controls remain locked | Redacted denial |
| A04 | Refresh and reopen app | Permitted projects/checkpoints persist | Synthetic record IDs |
| A05 | Create harmless synthetic project and inspect preview | No mutation before explicit Confirm | Before/after state |
| A06 | Cancel project approval | No project created; denial audit recorded | Audit event IDs |
| A07 | Confirm harmless synthetic project | Exactly one project created; intent/outcome visible in Owner Action history | Audit sequence IDs + redacted history |
| A08 | Replay same approval | Replay rejected; no second mutation | Redacted rejection |
| A09 | Attempt unknown/prohibited action | Fail-closed denial; no handler dispatch | Policy reason code |
| A10 | Logout; test 15-minute idle expiry and 12-hour absolute expiry | Protected data, drafts and approval capabilities inaccessible until re-login | Redacted session result |
| A11 | Backup/restore drill on local Android host/runtime | Restore into new directory; integrity passes; old approvals invalidated by fresh signing key | Manifest digest + restore result |
| A12 | Rotate screen; test narrow viewport, keyboard and touch | No hidden/overlapping controls; readable layout; explicit actions | Device/browser/version + screenshots |

## Execution record

For every case record PASS/FAIL/BLOCKED/NOT RUN, exact commit SHA, Android model/version, Chrome version, viewport/orientation, date/time, synthetic account role, redacted evidence reference, audit correlation ID, failure and remediation.

## Stop conditions

Mark FAIL if a certificate warning or unexpected origin appears; a non-owner sees or mutates Owner data; mutation occurs before approval; approval replays; unknown/prohibited action dispatches; audit failure does not block mutation; or restore overwrites existing data/accepts a corrupt archive.

Mark BLOCKED rather than PASS if Android runtime/dependencies are incompatible or the required device capability is unavailable. Never disable a control to force a pass.

## Current readiness

GitHub Chromium viewport smoke tests are supplemental only, not A01–A12 completion. Owner login, lockout, logout and session-expiry have automated test coverage. Physical Android runtime/Termux compatibility and A01–A12 remain NOT RUN until the Owner performs the steps above.

Remote HTTPS/OIDC is not required for this same-device loopback Personal Edition path. It belongs to a separately approved future remote deployment.

**No physical Android test has been performed by this document.**
