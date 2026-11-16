# APAA-S09-C01-P20 — OCI runtime compatibility and CI qualification

**Repository:** `glad4u7-crypto/TLP-Write-Test`  
**Branch:** `feature/apaa-s09-c01-p16-oci-lifecycle`  
**PR:** [#11 — Gated OCI Worker and Proxy Isolation](https://github.com/glad4u7-crypto/TLP-Write-Test/pull/11)  
**P20 real-runtime workflow:** [apaa-p20-rootless-podman-qualification.yml](../.github/workflows/apaa-p20-rootless-podman-qualification.yml)  
**Release posture:** Draft only; no merge, deployment, live browser enablement or production claim.

## Delivered in P20

- `core/oci_runtime_compat.py`: fail-closed Docker/Podman compatibility assessment for exact version, rootless mode, cgroup v2, lifecycle CLI, read-only rootfs, dropped capabilities and seccomp.
- `core/oci_runtime_probe.py`: bounded, read-only version, info and CLI-help probes.
- `scripts/qualify_oci_runtime_preflight.py`: host-invokable read-only preflight; emits JSON and returns nonzero for missing/incompatible runtime. It never creates, starts, stops or removes containers and does not change host networking.
- `core/oci_inspect_normalizer.py`: strict Docker/Podman inspect normalization; mismatches fail closed.
- Lifecycle executor gates CREATE → INSPECT → signed ATTEST → START, with bounded command timeouts. It captures the immutable ID returned by CREATE, then addresses INSPECT, START, STOP and force-REMOVE by that exact ID (and rejects an inspect-ID mismatch). Explicit handle-bound STOP → force-REMOVE is available; cleanup always attempts force-remove even when graceful stop fails, and reports an unremoved worker as a cleanup failure.
- Regression tests cover compatibility, version mismatch, runtime policy drift, inspect normalization, preflight output, immutable-ID lifecycle, failed graceful stop/force-remove, inspect timeout and daemon-disconnect fail-closed cleanup.
- Added a dedicated **disposable rootless Podman daemon CI qualification**. It installs Podman on an ephemeral GitHub-hosted Ubuntu runner, verifies non-root/rootless mode and cgroup v2, builds a local scratch+static-BusyBox image without pulling a base image, and runs CREATE → INSPECT → START → STOP → REMOVE by immutable container ID. Inspect assertions cover stopped pre-start state, read-only rootfs, all capabilities dropped, no-new-privileges, explicit seccomp, no network, and no privileged/host PID/IPC mode. A final orphan check and short-retention evidence artifact are included.

## Exact-head CI evidence

The latest code head before the Podman workflow addition was `cc73d761945fcc8329d052816b69abccd3bd0740`:
- [Agent Foundation CI #871](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43801811437): **PASS** — tests, compile, dependency audit and disposable namespace egress job.
- [Python Demo CI #946](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43801811398): **PASS** — tests and demo smoke.
- The new rootless Podman workflow was added after those runs; its own run must be observed on the new PR head before it can be marked PASS.

The namespace egress PASS is not proof of the full OCI worker/proxy topology or alternate-interface bypass resistance. Earlier code snapshot `e669a8767fa7471056e3695fca36d413d435675a` reported 1002 tests passed; that count is not asserted for later heads.

## Operational qualification still pending

1. The new CI workflow must complete successfully and its actual rootless Podman evidence must be reviewed.
2. Real rootless Docker runtime qualification.
3. Actual inspect schema from each separately pinned runtime.
4. APAA-integrated CREATE → INSPECT → signed ATTEST → START → STOP/REMOVE on a disposable daemon. The Podman CI smoke verifies runtime lifecycle and inspect hardening, but deliberately does not simulate or bypass APAA's trusted attestation gate.
5. Invalid, stale, replayed, revoked-key and mismatched attestation rejection against a real runtime.
6. Real-daemon timeout, cancellation, daemon interruption and bounded cleanup drills; prove no orphaned containers remain. Timeout and daemon-disconnect at INSPECT have unit regression coverage, not real-runtime drills.
7. Runtime namespace inspection and no-host-port proof for the integrated worker topology.
8. Egress alternate-interface bypass resistance, external DNS policy, IPv6 UDP, host firewall hook precedence and full worker/proxy topology.
9. Trusted host collector installation; out-of-band Ed25519 key provisioning, rotation, revocation and recovery.
10. Android/Termux OCI support.

Runtime probe tests use injected command runners. They prove deterministic policy behavior, not live runtime lifecycle. The namespace egress test is not a substitute for the daemon-integrated worker topology.

## Host preflight

Follow [P20 Disposable Linux Host Runbook](APAA_S09_C01_P20_DISPOSABLE_HOST_RUNBOOK.md). Run the read-only preflight on a disposable Linux host with the exact operator-approved runtime version:

```bash
python -m scripts.qualify_oci_runtime_preflight --runtime podman --pinned-version 5.4.2
```

The version above is an example only. Use the exact version separately approved for the target host. Exit 0 means only that the read-only runtime contract passed; it does not qualify full lifecycle, signed attestation or production egress isolation.

## Safety

Free-only. No API keys, paid providers, payments, purchases, checkout, trading or money movement. Auto-Run remains disabled. Browser/worker stays disabled. This PR remains draft; no merge or deployment is authorized.
