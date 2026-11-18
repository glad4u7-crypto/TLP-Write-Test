# APAA on Android — Termux + Debian PRoot Quick Start

## Supported Android role

The Android phone runs the **Owner control interface**. Android Chrome opens the local APAA UI; it is not the browser automation worker and it does not gain cross-app control. Browser/Worker dispatch, accessibility automation, shell automation, payments, purchases and Auto-Run remain disabled.

Recommended layout:

- Termux: package manager and PRoot-Distro launcher.
- Debian userland inside PRoot: Python/Streamlit app and its virtual environment.
- Android Chrome: same-phone Owner console at `http://localhost:8501`.
- APAA state: private app/container home, not shared storage.

PRoot is a Linux userland compatibility layer, **not a security sandbox, VM, or root isolation boundary**. Do not run untrusted workloads in it. The browser worker remains disabled regardless.

## 1. Prepare Termux

Use the Termux installation already on the phone. In Termux:

```sh
pkg update && pkg upgrade
pkg install git proot-distro
proot-distro install debian
proot-distro login debian
```

The commands above install a Debian userland in Termux. PRoot-Distro supports logging in as a non-root user and passing environment variables into the guest; see the official [PRoot-Distro guide](https://github.com/termux/proot-distro).

## 2. Prepare a dedicated non-root Debian user

Inside the first Debian root shell:

```sh
apt update && apt upgrade -y
apt install -y ca-certificates git python3 python3-venv python3-pip
adduser --disabled-password --gecos "" apaa
exit
```

Do not run the APAA UI as the Debian PRoot root user. PRoot's simulated root is not Android root, but APAA's diagnostic expects a non-root process.

## 3. Enter Debian as the APAA user

Back in Termux:

```sh
proot-distro login debian --user apaa \
  --env ANDROID_ROOT=/system \
  --env ANDROID_DATA=/data \
  --env PREFIX=/data/data/com.termux/files/usr
```

These environment markers let APAA identify that the Debian userland was launched from Termux. They are compatibility hints only, not security credentials.

## 4. Get APAA and install Android-compatible app dependencies

Inside Debian as user `apaa`:

```sh
cd ~
git clone https://github.com/glad4u7-crypto/TLP-Write-Test.git
cd TLP-Write-Test
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-android.txt
```

The Android requirements file intentionally excludes Playwright/Chromium. It installs only the Owner UI runtime dependencies. If a dependency cannot be installed on the handset, stop and report the exact package/error; do not install random wheels or disable package verification.

## 5. Configure Owner login safely

You need an OIDC provider account/application and its client ID, client secret, and HTTPS discovery URL. Register this exact callback URL with the provider:

```
http://localhost:8501/oauth2callback
```

Then run:

```sh
python scripts/android_termux_setup.py
```

The wizard:
- prompts for the OIDC client secret without echoing it;
- generates a fresh 48-byte-class cookie secret and 32-byte approval-signing key;
- writes `.streamlit/secrets.toml` with file mode `0600` and directory mode `0700`;
- refuses to overwrite an existing secrets file;
- does not print secret values, start the server, or enable browser execution.

At startup, APAA now rejects a symlinked/non-regular secrets file, a symlinked `.streamlit` directory, or group/world-readable permissions. Keep the directory at `0700` and the file at `0600`. If Android/PRoot cannot preserve these permissions, do not bypass the check; stop and report the redacted diagnostic.

The secrets file is git-ignored. Never paste it into chat, GitHub, shared storage, screenshots, or logs. Keep the OIDC client secret private. If you need to change credentials, handle the existing file manually and securely; this wizard deliberately does not overwrite it.

## 6. Run automated handset diagnostics

```sh
python scripts/android_device_acceptance.py
```

Expected: D01–D08 PASS. D04 checks that the app process is non-root. D05 checks OIDC presence; D07 checks durable approval-signing configuration; D06 checks loopback TCP; D08 checks that the secrets directory/file are non-symlink and private (0700/0600). The script never prints secret values.

A failed check means **do not start the Owner UI** until the cause is understood.

## 7. Start APAA and open Chrome

```sh
python scripts/android_owner_ui.py
```

Keep Termux in the foreground while using APAA. In Android Chrome, open:

```
http://localhost:8501
```

Sign in through the configured OIDC provider. Every protected action must still be reviewed and explicitly approved. Use Chrome's menu → **Add to Home screen** only if you want a convenient shortcut; this is not a native APK or a background service.

The app launcher binds the Streamlit server to `127.0.0.1` only. Do not change it to `0.0.0.0`, expose the port to Wi-Fi/LAN, create a tunnel, or forward the port.

## 8. Stop and resume

Stop the foreground app with `Ctrl+C` in Termux. On a later session, repeat the Debian login command, activate the virtual environment, enter the repository, and run the launcher again. Android may suspend or kill background processes; APAA is not claimed to run continuously in the background. Check durable project/checkpoint state after restart.

## 9. Physical acceptance checklist

Run the diagnostics first, then record redacted PASS/FAIL only:

- [ ] D01–D08 automated diagnostics pass
- [ ] A02 app starts as the non-root `apaa` user
- [ ] A03 listener is only `127.0.0.1:8501`
- [ ] A04 Chrome opens the Owner login page
- [ ] A05 portrait and landscape layouts have no clipped critical controls
- [ ] A06 OIDC Owner login and logout work; no passphrase login is claimed
- [ ] A07 idle/absolute expiry forces re-login
- [ ] A08 approval and cancel paths both work; no implicit approval
- [ ] A09 action history and audit verification work
- [ ] A10 restart recovers Owner/project/checkpoint state
- [ ] A11 LAN binding and Android browser-worker launch are blocked
- [ ] A12 stop is clean; secrets remain in private app/container storage

Evidence must omit passwords, OIDC tokens, cookies, session IDs, signing keys, database contents and unredacted logs. Record handset model, Android version, Termux source/version, Debian/Python version, test ID and outcome only.

## Current status

Repository-side Android setup, OIDC validation, private secret provisioning, dependency separation, launcher and diagnostics are implemented as code. **Physical handset acceptance is not complete until the Owner runs these commands and supplies the redacted D01–D08/A01–A12 outcomes.** A GitHub CI run cannot prove that Chrome, OIDC redirects, Android process lifecycle, or storage permissions work on the actual phone.
