# APAA Personal Edition — Android Owner Acceptance Runbook

**Checkpoint:** S09-C01 / Android Integration  
**Target:** Owner's physical Android phone  
**Status:** Physical acceptance A01–A12 NOT RUN.  
**Application:** Android-first, same-device Streamlit web interface launched from Termux; not a native APK or installable PWA.

## 1. Safety and scope

- Use only the Owner's own Android device and synthetic test data.
- Bind to `127.0.0.1` only. Never use `0.0.0.0`, a LAN address, public tunnel or public deployment.
- Open only `http://127.0.0.1:8501` in Android Chrome on the same phone.
- Local Owner passphrase authentication is required by the Personal Edition app. Do not enable unauthenticated prototype mode.
- Each supported mutation requires explicit Owner approval. Auto-Run remains OFF.
- Android Chrome is the Owner control surface, not an automation worker. Browser/Worker dispatch remains DISABLED.
- Do not enter real personal content, reused passwords, OTPs, cookies, API keys, recovery codes or financial data.
- No paid hosting/providers, payment, purchase, trading, money movement, root access, accessibility automation, LAN exposure or public signup.
- If a dependency or runtime fails, record **BLOCKED**. Never bypass a security control to force a pass.

## 2. Install and prepare Termux

Install Termux only from its official F-Droid or GitHub distribution source; do not use an untrusted APK mirror.

In Termux:

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

If a dependency cannot be installed, stop and report only the failing package name and sanitized error category. Do not install random binaries or unreviewed patches.

## 3. Read-only runtime diagnostic

Run:

```sh
python scripts/apaa_android_doctor.py
git rev-parse HEAD
```

The diagnostic checks Python/runtime metadata, Streamlit and cryptography availability, AES-GCM/scrypt availability, and whether a loopback socket can bind. It does not read secrets or personal files, create directories, start the app, or make network connections.

A diagnostic PASS is only a preflight result. It is not physical Android acceptance.

## 4. Start APAA using the hardened launcher

Use the repository launcher so its port, absolute data path, private directory permissions and Streamlit dependency checks run before startup:

```sh
bash scripts/apaa_android_start.sh
```

The default data directory is `$HOME/.apaa_personal`; the launcher enforces owner-private directory permissions and binds Streamlit to `127.0.0.1:8501`. To choose another port, set `APAA_PORT` to a decimal port from 1024 through 65535 before launch.

Keep Termux in the foreground. Do not configure boot startup or background execution. Open Android Chrome on the same phone and navigate to:

```
http://127.0.0.1:8501
```

Stop immediately if the app binds to a non-loopback address, Chrome opens another origin, a certificate/security warning appears, or startup asks you to disable Android security. Stop the app with Ctrl+C in Termux.

## 5. Physical acceptance A01–A12

Use synthetic project/task names only. Record PASS, FAIL, BLOCKED or NOT RUN for each case.

| ID | Test | Expected result | Evidence |
|---|---|---|---|
| A01 | Start with the hardened launcher; open the exact loopback URL in Chrome | Same-device Owner gate appears; no LAN/public listener | Redacted result, origin and runtime details |
| A02 | First-run local Owner passphrase setup; logout; sign in again | Only the configured Owner can unlock the app | Result only; never capture the passphrase |
| A03 | Open a fresh/incognito browser session without Owner authentication | Owner data and mutation controls remain locked | Redacted denial |
| A04 | Refresh, close Chrome, reopen the app | Owner identity, permitted project and checkpoint state persist | Synthetic record IDs |
| A05 | Submit a harmless synthetic task/project and inspect its plan/preview | No mutation occurs merely by submitting or previewing | Before/after state |
| A06 | Cancel the approval prompt | No mutation; denial/cancellation is recorded where applicable | Redacted history/event reference |
| A07 | Explicitly approve one harmless supported mutation | Exactly one mutation; Owner Action History shows its outcome | Audit correlation/event ID |
| A08 | Attempt to reuse/replay the same approval or request | Replay rejected; no second mutation | Redacted rejection |
| A09 | Attempt an unsupported/prohibited action, including browser-worker launch | Fail-closed denial; no handler/worker dispatch | Policy reason code |
| A10 | Logout; verify idle expiry and absolute session expiry using the defined session limits | Protected data and approval capabilities require fresh Owner login | Redacted session result |
| A11 | Create an encrypted backup; restore to a new empty directory; verify integrity and synthetic project/file hashes | Restore does not overwrite live data; integrity checks pass; fresh approval signing key is used | Archive digest and restore result; never share backup passphrase |
| A12 | Test portrait/landscape, narrow screen, keyboard, touch targets, Action History and approval controls | No critical control is clipped or inaccessible; touch interaction is usable | Device/Chrome version and redacted screenshots |

**Important:** A11 is a physical Owner-operated backup/restore drill. Do not use the live data directory as the restore destination. Use a separate empty test directory and synthetic data. If the device cannot safely complete the drill, mark BLOCKED.

## 6. Evidence format and privacy

For each test record:
- Test ID and PASS/FAIL/BLOCKED/NOT RUN.
- Exact `git rev-parse HEAD` commit SHA.
- Android model/version, Termux version/source, Python version and Chrome version.
- Orientation/viewport where relevant.
- Redacted evidence reference, synthetic record ID and audit correlation ID.
- Sanitized failure category and remediation needed.

Never send passphrases, backup passphrases, environment dumps, `.streamlit/secrets.toml`, tokens, cookies, session IDs, private databases, browser profiles or unredacted logs.

## 7. Stop conditions

Mark FAIL if a non-Owner can view or mutate Owner data; a mutation occurs before approval; approval replay succeeds; an unsupported/prohibited action dispatches; audit failure does not block the mutation; the listener is not loopback-only; or restore overwrites existing data/accepts a corrupt archive.

Mark BLOCKED rather than PASS if Android runtime/dependencies are incompatible or the required device capability is unavailable. Do not disable controls to force a pass.

## 8. Qualification boundary

Automated Python tests and Android-sized Chromium viewport smoke tests are supplemental software evidence only. They do not prove physical Android compatibility or A01–A12 acceptance.

Android Chrome is the same-device Owner interface. Android/Termux browser-worker execution remains unsupported and disabled. Physical handset acceptance and the Owner-operated encrypted backup/restore drill remain pending until the Owner runs them on the actual phone.

**No physical Android test is claimed as completed by this runbook.**
