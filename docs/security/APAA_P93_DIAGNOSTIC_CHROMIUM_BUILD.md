# APAA P93 — Diagnostic Chromium FD ownership build

## Purpose

Produce a separate Chromium diagnostic binary that logs the exact FD ownership
transition at the fatal check. This is instrumentation, not a production fix.

## Fatal-path record

The patch adds one structured line immediately before the existing crash:

`APAA_FD_OWNERSHIP_DIAG fd=N operation=acquire|release|close previous_owned=0|1 requested_owned=0|1 pid=N tid=N`

- `acquire`: duplicate ownership acquisition when the FD was already marked owned.
- `release`: release when the FD was already marked unowned.
- `close`: raw close attempted while Chromium still marks the FD owned.
- PID and Linux TID are sampled in the failing process.
- Existing stack trace and immediate crash remain enabled.
- The patch does not change the ownership table, close behavior, sandbox, seccomp,
  namespaces, cgroups, or network policy beyond preserving the existing fatal path.

## Build

Use a disposable Linux build host with a full Chromium source checkout, depot_tools,
GN, Ninja/autoninja, and enough disk/RAM for a Chromium build.

First identify and independently review the exact upstream Chromium source commit corresponding to the Debian 156.0.8078.79-1~deb12u1 package. Do not derive the expected value from the checkout being built. Then pin that reviewed commit:

```bash
export APAA_CHROMIUM_SOURCE_DIR=/work/chromium/src
export APAA_CHROMIUM_EXPECTED_REVISION="<reviewed-40-character-upstream-source-commit>"
export APAA_CHROMIUM_DIAG_OUT_DIR=/work/out/apaa-fd-diagnostic
bash scripts/build_chromium_fd_diagnostic.sh
```

The script refuses an unpinned/mismatched revision, applies the patch only after
`git apply --check`, and builds into a separate output directory. It never
replaces `/usr/bin/chromium` or the production image binary.

**Important:** the patch must be validated against the exact Chromium source revision
corresponding to the Debian 156.0.8078.79-1~deb12u1 binary. Do not assume current
Chromium HEAD is ABI/source equivalent. A patch-context mismatch is a hard stop.

## Evidence interpretation

The first diagnostic record is the ownership failure site. Preserve its PID/TID,
FD number, operation, previous/requested ownership states, stack, and the matching
host/container process start-time + namespace PID mapping. Correlate the FD number
against the same process's closest pre-failure read-only procfs snapshot.

Do not infer a root cause from shared inode candidates alone. A process-local
ownership table is not the kernel FD table; fork/zygote state reset and FD-number
reuse must be evaluated at the exact call site.

## Fix gate

No behavioral fix is included here. Once the first failure is reproduced and the
exact owner/close/acquire/release sequence is known, implement the narrowest fix
at that call site and add a deterministic Chromium regression test reproducing
that sequence. Keep the fatal security invariant intact. Do not suppress the
check, weaken sandboxing, add broad seccomp rules, or add host FD pass-through.

## Current state

Diagnostic patch and build recipe prepared; binary build, real OCI reproduction,
root-cause identification, behavioral fix, and Chromium-native regression test
remain pending until the exact source revision/build environment is available.
Release remains FAILED / NO-GO.

## Verified upstream source provenance

The upstream Chromium release ref `156.0.8078.79` resolves to commit
`a21ce95c24ce3964416f09ae1862f53f319eb4d0` in the Chromium GitHub mirror.
At that commit, `base/files/scoped_file_linux.cc` has Git blob
`f911af6b458272481142431360352ebcbd0e3c04`. The diagnostic patch is now
pinned to that exact source commit and file context; the build script refuses
any other HEAD and a dirty source tree.

This establishes upstream source context, **not** that every Debian packaging
patch in `156.0.8078.79-1~deb12u1` has been applied or audited. Before claiming
binary-identical reproduction, obtain the exact Debian source package and
verify its patch series against the pinned upstream tree. The same file blob
must be confirmed after Debian patches are applied. A successful upstream
build is diagnostic instrumentation validation, not proof of a Debian package
reproduction.

The source provenance was checked against the Chromium release ref and exact
file content. References:
- Chromium release source file: https://github.com/chromium/chromium/blob/a21ce95c24ce3964416f09ae1862f53f319eb4d0/base/files/scoped_file_linux.cc
- Debian source package listing: https://packages.debian.org/bookworm/source/chromium

## Remaining execution boundary

This repository integration environment can write and inspect GitHub files,
but it does not provide a Chromium source checkout, depot_tools, a configured
Linux build host, or a disposable OCI host with the APAA worker image. Therefore
it cannot honestly report a compiled diagnostic binary, an OCI reproduction,
a real failing FD, a root-cause fix, or a defect-specific Chromium regression
test. Those remain explicit release gates rather than being marked complete.

## Local preflight results

- The corrected unified diff was checked with `git apply --check` against a clean fixture containing the exact fetched upstream file content at the pinned commit; result: **PASS**.
- The structured parser's 6 pytest cases were run in an isolated Python 3 environment using the repository module/test contents; result: **6 passed**.
- These are source-patch applicability and parser checks only. They do not compile Chromium or exercise the real Chromium FD ownership checker.
- The dedicated GitHub Actions workflow has been added, but no successful GitHub Actions run result has been observed yet.
