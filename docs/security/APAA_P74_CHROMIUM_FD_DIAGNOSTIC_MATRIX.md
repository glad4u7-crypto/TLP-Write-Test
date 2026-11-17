# APAA P74 — Chromium FD Ownership Diagnostic Matrix

Status: diagnostic plan / implementation gate. This document does not claim the root cause is known.

## Incident baseline

- Repository: `glad4u7-crypto/TLP-Write-Test`
- Parent PR: #14 — APAA P74 Action 12, OCI runtime and isolated network provisioners
- Baseline head: `db0eb1dad2d7aa34f7db72f31ef7006f77ced62b`
- Failed real-host qualification run: `44144480688`
- Failed job: `134255751175`, step 8, “Run real Chromium inside isolated OCI worker”
- Observed: `podman exec python3` timed out at 45 seconds with zero stdout; Chromium logged `Network service crashed or was terminated` and `Crashing due to FD ownership violation`.
- Preparation, cgroup-v2, image build and seccomp-profile preparation passed. This is not evidence that Chromium's process/FD hand-off passed.
- Release remains NO-GO. Browser/Worker dispatch disabled; Auto-Run OFF.

## Security invariants (must not change)

1. Keep rootless/non-root execution, user and PID namespaces, read-only rootfs, dropped capabilities, no-new-privileges, seccomp, cgroup limits and network namespace.
2. Keep nftables default-DROP and the exact approved proxy egress policy. No direct network fallback.
3. Do not add `--no-sandbox`, privileged mode, host networking, broad seccomp allowances, host /proc exposure, or host descriptor pass-through as a workaround.
4. Diagnostics are read-only. Never duplicate, reopen, transfer, or mutate a Chromium FD to “test” ownership.
5. Evidence must redact command-line secrets, environment values, URLs with credentials, cookies, tokens and file contents. Record FD metadata and sanitized target classes only.
6. Do not enable production Browser/Worker dispatch, merge, or deploy based on diagnostic results.

## Diagnostic Test Matrix

| ID | Test / observation | Capture point | Expected / interpretation | Gate |
|---|---|---|---|---|
| D01 | Record launcher process FD inventory before container exec | Host-side launcher, immediately before Podman exec | Baseline FD number, target class, device/inode, FD flags, owner UID/GID; no raw sensitive paths | Required |
| D02 | Record OCI init and exec process FD inventory | Host PID namespace, after exec process starts | Identify descriptors present at process birth and unexpected inherited descriptors | Required |
| D03 | Snapshot every Chromium process | Repeated snapshots during startup, network-service launch, page load and shutdown | PID/PPID, executable basename, start time, UID/GID, namespace IDs, cgroup, FD count and per-FD metadata | Required |
| D04 | Build process ancestry and Chromium role map | Same snapshots + Chromium logs | Attribute browser, zygote, renderer, GPU and network-service processes; identify exact PID/role at first failure | Required |
| D05 | Compare FD inheritance across parent→child exec boundaries | Before/after each observed fork/exec boundary | Detect descriptors unexpectedly surviving exec or disappearing before hand-off; inspect CLOEXEC flags without changing them | Required |
| D06 | Inspect `/proc/<pid>/fdinfo/<n>` and symlink metadata | For each captured process/FD | Compare flags, mount/inode identity, access mode and target class; do not read descriptor contents | Required |
| D07 | Correlate FD ownership violation with stderr timestamp and process exit | Monotonic timestamped event stream | Determine whether failure is first in browser, zygote or network service and whether another process exits first | Required |
| D08 | Repeat baseline with no navigation, then reserved example.com navigation | Disposable host, identical pinned image and policy | Separate Chromium startup/FD failure from proxy, DNS, TLS or navigation failure | Required |
| D09 | Compare direct container Chromium invocation vs existing `podman exec python3` harness | Same container image, user, seccomp, namespaces and policy | Isolate whether the Python subprocess/pipe/stdio hand-off contributes; no relaxation of isolation | Required |
| D10 | Verify stdio and control-channel descriptors | Launcher, exec wrapper and Chromium parent | Confirm stdin/stdout/stderr and control pipes have intended ownership/lifetime and no accidental reuse | Required |
| D11 | Verify descriptor cleanup after timeout/crash | Host observer after worker termination | No orphan Chromium process, leaked host FD, stale container, namespace, veth, cgroup or firewall rule | Required |
| D12 | Re-run under repeated cold starts | At least 10 disposable-host trials after candidate fix | Stable startup and identical FD invariants; capture each first-failure event if any | Release gate |

## Required per-process FD snapshot schema

For every process snapshot, capture only:

- monotonic timestamp, host PID, container PID (if available), PPID, process start-time, executable basename and Chromium role
- UID/GID, PID/user/mount namespace identifiers, cgroup path
- each FD number, sanitized target category (pipe/socket/eventfd/memfd/file/anon_inode/other), device + inode, access mode and FD flags from fdinfo
- whether `O_CLOEXEC` / `FD_CLOEXEC` is set where observable; distinguish descriptor status from open-file-description status
- process state and exit code/signal when available

Do not record file contents, socket payloads, environment values, full argv, credential-bearing paths or raw browser profile data. Use stable per-run pseudonyms for pipe/socket endpoints so relationships can be compared without exposing data.

## Hypothesis buckets — not conclusions

- H1: an unintended descriptor is inherited by a child across exec because close-on-exec was not set at the correct creation boundary.
- H2: an expected descriptor is closed/replaced too early by the Python harness, exec wrapper or parent lifecycle.
- H3: a pipe/socket endpoint is owned or consumed by the wrong process due to subprocess stdio/pass_fds/session handling.
- H4: Chromium's sandboxed process topology or network-service startup encounters a descriptor hand-off mismatch under the current namespace/seccomp environment.
- H5: the FD message is secondary; the primary failure is a separate startup or IPC failure. Timestamp and process correlation must establish causality.

Do not select a hypothesis until evidence identifies the first violating PID, FD and hand-off boundary.

## Execution sequence

1. Inspect the existing real-worker harness, OCI exec wrapper, worker entrypoint and workflow command; document every subprocess creation and explicit FD pass-through.
2. Add a read-only, bounded FD snapshot collector. Restrict it to the disposable qualification host and worker process tree. Fail closed if process identity cannot be tied to the expected container/worker.
3. Capture snapshots at process start, each Chromium child appearance, first Chromium stderr error, timeout and teardown.
4. Run D08/D09 controls with the same pinned image and unchanged security policy.
5. Identify the first mismatched FD and the responsible creation/close/exec boundary.
6. Implement the narrowest fix at that boundary. Do not change sandbox or egress policy.
7. Add deterministic unit tests for FD allowlist/inheritance metadata parsing, CLOEXEC expectations, process-tree correlation, redaction, missing/racing /proc entries and cleanup.
8. Run regression tests, then the complete disposable-host qualification and inspect sanitized evidence. Require 10 cold-start repetitions before declaring the diagnostic gate passed.

## Regression-test acceptance criteria

- Correctly parse `/proc/<pid>/fd` and `fdinfo` fixture data, including disappearing PIDs/FDs.
- Detect unexpected inherited descriptors and missing required descriptors without opening or transferring them.
- Verify the expected CLOEXEC policy at the launcher boundary.
- Correlate parent/child and Chromium role records deterministically.
- Redact secrets and sensitive paths from all logs/artifacts.
- Bound snapshot count, process count, FD count, runtime and artifact size.
- Prove the collector is observational only and cannot alter descriptors, namespaces, firewall, seccomp or worker permissions.
- Include negative tests for malformed proc data, PID reuse/races, permission denial, truncation and teardown after timeout.

## Completion criteria

Diagnostic phase is complete only when the evidence identifies (a) the first failing Chromium PID/role, (b) the relevant FD number and sanitized identity, (c) the parent/child hand-off boundary, and (d) a reproducible regression test. A code change is not a fix until the full real-host OCI qualification passes with the unchanged security policy.

## Current decision

**NO-GO / NOT QUALIFIED.** This matrix authorizes diagnostic work only. It does not authorize merge, deployment, Browser/Worker dispatch, Auto-Run, payment, purchases or any financial action.


## Evidence update — disposable-host run #272

- Tested commit: `c1f30b449c49444bfe177c2a43d03769b9fce899`.
- OCI preparation, cgroup-v2, image build, seccomp preparation, namespace/routes, dual-stack firewall attestation and OCI hardening passed.
- Chromium local `data:` smoke failed before any proxy/navigation test. Chromium 156.0.8078.79 logged `Network service crashed or was terminated` followed by `Crashing due to FD ownership violation`.
- Read-only collector captured 24 snapshots, with up to 12 Chromium processes observed in one snapshot. Cleanup was confirmed with no cleanup errors.
- Chromium log PID/TID prefix was `16:16`. The host-side process snapshot maps container PID 16 to host PID 8271 (NSpid `8271 16`); it was `chromium`, UID/GID 65532, seccomp mode 2, with 148 FDs observed at the matching snapshot. Its precise Chromium role remains unclassified because the sanitized cmdline contained no recognized process-type flag.
- Parent/child snapshots showed shared pipe/socket/memfd kernel-object candidates, including the same socket inode on several Chromium descendants. These are candidates only; they do not prove an FD ownership bug or identify the crashing FD.
- Chromium's Linux `ScopedFD` implementation maintains a process-local FD ownership table. The exact fatal check is triggered by a duplicate Acquire/Release ownership transition or by calling `close(fd)` while that FD remains marked owned. Therefore, the error is not proof of a kernel-level cross-process FD ownership violation.
- Exact failing FD and call site remain unknown. The captured stack was not symbolicated. The next run now records the complete sanitized numeric stack-frame addresses and maps the Chromium log PID/TID to the host process snapshot.

### Revised diagnosis priority

1. Symbolicate the failing process stack against the exact Debian Chromium 156.0.8078.79 build/debug symbols.
2. Determine whether the fatal path is `ScopedFDCloseTraits::Acquire`, `Release`, or the guarded `close()` wrapper.
3. Inspect same-process FD reuse/close ordering and Chromium fork/zygote ownership-table reset behavior at the identified call site.
4. Only then evaluate whether any inherited descriptor crosses a fork/exec boundary incorrectly.
5. Preserve all sandbox, seccomp, namespace, cgroup and deny-by-default egress controls.

**Qualification remains FAILED / NO-GO.** This run produced useful process-level evidence but did not pass Chromium startup or identify the exact descriptor/call site.
