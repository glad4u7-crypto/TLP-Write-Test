#!/usr/bin/env bash
set -euo pipefail

# Separate diagnostic build only. Never overwrite the system/production browser.
: "${APAA_CHROMIUM_SOURCE_DIR:?set to a full Chromium checkout at the pinned release commit}"
: "${APAA_CHROMIUM_DIAG_OUT_DIR:?set an isolated output directory}"

readonly expected_revision="a21ce95c24ce3964416f09ae1862f53f319eb4d0"
src="$(realpath "$APAA_CHROMIUM_SOURCE_DIR")"
out="$(realpath -m "$APAA_CHROMIUM_DIAG_OUT_DIR")"
script_dir="$(cd "$(dirname "$0")" && pwd)"
patch_file="$script_dir/../patches/chromium-156-fd-ownership-diagnostics.patch"

test -f "$src/base/files/scoped_file_linux.cc"
test -f "$src/BUILD.gn"
actual_revision="$(git -C "$src" rev-parse HEAD)"
if [[ "$actual_revision" != "$expected_revision" ]]; then
  echo "Refusing source revision: expected=$expected_revision actual=$actual_revision" >&2
  exit 2
fi
if [[ -n "$(git -C "$src" status --porcelain)" ]]; then
  echo "Refusing dirty Chromium source tree; use a clean disposable checkout" >&2
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
'
autoninja -C "$out" chrome base_unittests

printf 'diagnostic_binary=%s/chrome\n' "$out"
printf 'source_revision=%s\n' "$actual_revision"
printf 'patched_file_sha256=%s\n' "$(sha256sum "$src/base/files/scoped_file_linux.cc" | cut -d' ' -f1)"
printf 'build_args_sha256=%s\n' "$(gn args "$out" --list | sha256sum | cut -d' ' -f1)"
