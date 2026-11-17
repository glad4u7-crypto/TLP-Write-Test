#!/usr/bin/env bash
set -euo pipefail

# APAA Personal Edition: same-device Android browser launcher for Termux.
# This intentionally binds only to loopback; it is not a LAN/public server.
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v python >/dev/null 2>&1; then
  echo "Python is required. Install Python in Termux first." >&2
  exit 1
fi

PORT="${APAA_PORT:-8501}"
if [[ ! "$PORT" =~ ^[0-9]{1,5}$ ]] || (( PORT < 1024 || PORT > 65535 )); then
  echo "APAA_PORT must be a TCP port from 1024 to 65535." >&2
  exit 1
fi

export APAA_PERSONAL_DATA_DIR="${APAA_PERSONAL_DATA_DIR:-$HOME/.apaa_personal}"
mkdir -p "$APAA_PERSONAL_DATA_DIR"
chmod 700 "$APAA_PERSONAL_DATA_DIR"

echo "Starting APAA on this Android device only."
echo "Open http://127.0.0.1:$PORT in the Android browser."
echo "Keep this terminal session running. Press Ctrl+C to stop APAA."
exec python -m streamlit run app.py \
  --server.address 127.0.0.1 \
  --server.port "$PORT" \
  --server.headless true


## Android launcher safety

See [P86 Android Launcher Preflight](docs/APAA_PERSONAL_EDITION_P86_ANDROID_LAUNCHER_PREFLIGHT.md) for fail-closed Termux launch checks.
