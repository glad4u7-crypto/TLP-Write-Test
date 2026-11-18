#!/usr/bin/env bash
set -euo pipefail

# Build a separate, instrumented Chromium tree. Never replace the system or
# production Chromium binary. Run only on a disposable Linux build host.
: "${APAA_CHROMIUM_SOURCE_DIR:?set APAA_CHROMIUM_SOURCE_DIR to a Chromium source checkout}"
: "${APAA_CHROMIUM_EXPECTED_REVISION:?pin the exact Chromium source revision}"
: "${APAA_CHROMIUM_DIAG_OUT_DIR:?set an isolated output directory}"

src="$(realpath "$APAA_CHROMIUM_SOURCE_DIR")"
out="$APAA_CHROMIUM_DIAG_OUT_DIR"
patch_file="$(dirname "$0")/../patches/chromium-156-fd-ownership-diagnostics.patch"

test -f "$src/base/files/scoped_file_linux.cc"
test -f "$src/BUILD.gn"
actual_revision="$(git -C "$src" rev-parse HEAD)"
if [[ "$actual_revision" != "$APAA_CHROMIUM_EXPECTED_REVISION" ]]; then
  echo "Refusing unpinned Chromium source: expected=$APAA_CHROMIUM_EXPECTED_REVISION actual=$actual_revision" >&2
  exit 2
fi

git -C "$src" apply --check "$patch_file"
git -C "$src" apply "$patch_file"

gn gen "$out" --args='
is_debug=false
is_component_build=false
symbol_level=2
blink_symbol_level=0
target_cpu="x64"
enable_nacl=false
'
autoninja -C "$out" chrome base_unittests

printf 'diagnostic_binary=%s/chrome\n' "$out"
printf 'source_revision=%s\n' "$actual_revision"
printf 'build_args=%s\n' "$(gn args "$out" --list | sha256sum | cut -d' ' -f1)"
