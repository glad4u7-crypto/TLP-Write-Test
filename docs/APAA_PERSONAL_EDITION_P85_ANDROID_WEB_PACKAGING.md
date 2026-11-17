# APAA Android Web Packaging — P85

APAA's first Personal Edition target remains a browser-based web platform, not a mandatory APK or Home Screen installation.

## Included launcher

`scripts/apaa_android_start.sh` starts the existing Streamlit app from Termux and binds the server to `127.0.0.1` only. It sets the default private data directory to `$HOME/.apaa_personal` and applies mode 0700. An optional `APAA_PORT` can select a port from 1024 through 65535.

## Android setup (Termux)

1. Install Termux from a trusted distribution source.
2. Install Python and Git inside Termux.
3. Clone the APAA repository and enter its directory.
4. Install the repository dependencies with `python -m pip install -r requirements.txt`.
5. Start APAA with `bash scripts/apaa_android_start.sh`.
6. Open `http://127.0.0.1:8501` in the browser on the same Android device.
7. Complete first-run Owner passphrase setup. Keep the passphrase private.

## Security boundaries

- The launcher never binds to `0.0.0.0`, a LAN interface or a public interface.
- Do not change the bind address to expose the unauthenticated local Owner runtime remotely.
- Do not share the device's private data directory or unencrypted backup archives.
- Stop the server with Ctrl+C in Termux.
- This launcher does not run at boot, install an APK, create a Home Screen app or bypass Android permission prompts.
- Physical Android A01–A12 acceptance remains NOT RUN; browser viewport emulation is not device qualification.

## Packaging status

This is a source-based Termux/browser launch path for Android-first development and local use. It is not a signed APK, Play Store package, installable PWA or production remote-hosting package. Those formats are deliberately not introduced in this Personal Edition checkpoint.
