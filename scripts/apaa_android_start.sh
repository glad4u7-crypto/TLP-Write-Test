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
DATA_DIR="${APAA_PERSONAL_DATA_DIR:-${HOME:?HOME must be set}/.apaa_personal}"

# Fail closed before starting Streamlit if the local data path or runtime is unsafe.
python scripts/apaa_android_preflight.py --data-dir "$DATA_DIR" --port "$PORT"
export APAA_PERSONAL_DATA_DIR="$DATA_DIR"

echo "Starting APAA on this Android device only."
echo "Open http://127.0.0.1:$PORT in the Android browser."
echo "Keep this terminal session running. Press Ctrl+C to stop APAA."
exec python -m streamlit run "$ROOT_DIR/app.py" \
  --server.address 127.0.0.1 \
  --server.port "$PORT" \
  --server.headless true
