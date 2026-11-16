# APAA-S09-C01-P20 — OCI runtime compatibility and CI qualification

**Repository:** `glad4u7-crypto/TLP-Write-Test`  
**Branch:** `feature/apaa-s09-c01-p16-oci-lifecycle`  
**PR:** [#11 — Gated OCI Worker and Proxy Isolation](https://github.com/glad4u7-crypto/TLP-Write-Test/pull/11)  
**Latest code commit:** [e669a8767fa7471056e3695fca36d413d435675a](https://github.com/glad4u7-crypto/TLP-Write-Test/commit/e669a8767fa7471056e3695fca36d413d435675a)  
**Latest exact-head CI:** [Agent Foundation CI run 43801033918](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43801033918) — PASS; [Python Demo CI run 43801033691](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43801033691) — PASS.  
**Release posture:** Draft only; no merge, deployment, live browser enablement or production claim.

## Delivered in P20

- `core/oci_runtime_compat.py`: fail-closed Docker/Podman compatibility assessment for exact version, rootless mode, cgroup v2, lifecycle CLI, read-only rootfs, dropped capabilities and seccomp.
- `core/oci_runtime_probe.py`: bounded, read-only version, info and CLI-help probes.
- `scripts/qualify_oci_runtime_preflight.py`: host-invokable read-only preflight; emits JSON and returns nonzero for missing/incompatible runtime. It never creates, starts, stops or removes containers and does not change host networking.
- `core/oci_inspect_normalizer.py`: strict Docker/Podman inspect normalization; mismatches fail closed.
- Lifecycle executor gates CREATE → INSPECT → signed ATTEST → START, with bounded command timeouts. It captures the immutable ID returned by CREATE, then addresses INSPECT, START, STOP and force-REMOVE by that exact ID (and rejects an inspect-ID mismatch). Explicit handle-bound STOP → force-REMOVE is available; cleanup always attempts force-remove even when graceful stop fails, and reports an unremoved worker as a cleanup failure.
- Regression tests cover compatibility, version mismatch, runtime policy drift, inspect normalization, preflight output, immutable-ID lifecycle, failed graceful stop/force-remove, inspect timeout and daemon-disconnect fail-closed cleanup.

## Exact observed CI evidence

Runs [43801033918](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43801033918) and [43801033691](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43801033691), observed 2026-11-16, for code commit `e669a8767fa7471056e3695fca36d413d435675a`:

- Agent Foundation CI: **PASS**.
- Python 3.12 compile check: **PASS**.
- Dependency audit: **PASS — no known vulnerabilities found**.
- Foundation test suite: **1002 passed**.
- Python Demo test suite: **1002 passed**; `demo.py` output check: **PASS**.
- Disposable Linux egress namespace qualification: **PASS**.
- Egress test confirms the exact TCP proxy destination was allowed and direct TCP, DNS TCP/UDP, UDP/QUIC and IPv6 probes were blocked.

The egress job ran `sudo -n bash scripts/qualify_linux_egress_namespace.sh`, created an isolated namespace/veth pair and namespace-local nftables policy, and completed the probes. It did not edit host firewall chains. This is meaningful disposable namespace test evidence, not proof of the eventual production worker topology.

## Operational qualification still pending

1. Real rootless Docker daemon qualification.
2. Real rootless Podman daemon qualification.
3. Actual inspect schema from each separately pinned runtime.
4. End-to-end CREATE → INSPECT → signed ATTEST → START → STOP/REMOVE on a disposable daemon.
5. Invalid, stale, replayed, revoked-key and mismatched attestation rejection against a real daemon.
6. Real-daemon timeout, cancellation, daemon interruption and bounded cleanup drills; prove no orphaned containers remain. Timeout and daemon-disconnect at INSPECT now have unit regression coverage and exact-head CI PASS, but are not real-daemon drills.
7. Runtime namespace inspection and no-host-port proof.
8. Egress alternate-interface bypass resistance, external DNS policy, IPv6 UDP, host firewall hook precedence and full worker/proxy topology.
9. Trusted host collector installation; out-of-band Ed25519 key provisioning, rotation, revocation and recovery.
10. Android/Termux OCI support.

Runtime probe tests use injected command runners. They prove deterministic policy behavior, not live daemon lifecycle. The namespace egress test is not a substitute for the daemon-integrated worker topology.

## Host preflight and next gate

Follow [P20 Disposable Linux Host Runbook](APAA_S09_C01_P20_DISPOSABLE_HOST_RUNBOOK.md). Run the preflight on a disposable Linux host with the exact operator-approved runtime version:

```bash
python -m scripts.qualify_oci_runtime_preflight --runtime podman --pinned-version 5.4.2
```

The version above is an example only. Use the exact version separately approved for the target host. Exit 0 means only that the read-only runtime contract passed; it does not qualify full lifecycle or production egress isolation.

## Safety

Free-only. No API keys, paid providers, payments, purchases, checkout, trading or money movement. Auto-Run remains disabled. Browser/worker stays disabled. This PR remains draft; no merge or deployment is authorized.
