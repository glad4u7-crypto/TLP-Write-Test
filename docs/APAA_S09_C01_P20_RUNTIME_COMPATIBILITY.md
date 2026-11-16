# APAA-S09-C01-P20 — OCI runtime compatibility and CI qualification

**Repository:** `glad4u7-crypto/TLP-Write-Test`  
**Branch:** `feature/apaa-s09-c01-p16-oci-lifecycle`  
**Implementation head before host-preflight addition:** `c8104c4ab49ceaaa378d2fa3c6dda61468d1bb29`  
**PR:** [#11 — Gated OCI Worker and Proxy Isolation](https://github.com/glad4u7-crypto/TLP-Write-Test/pull/11)  
**Status:** Read-only host preflight/tests passed on the preceding code head; live egress qualification was attempted and failed on the hosted runner because IPv6/network capabilities were unavailable. A clearer early-capability diagnostic was added; latest-head CI is pending. Real daemon qualification remains pending.  
**Release posture:** Draft only; no merge, deployment, live browser enablement or production claim.

## Delivered in P20

- `core/oci_runtime_compat.py`: pure, fail-closed compatibility assessment for Docker/Podman exact version, rootless mode, cgroup v2, lifecycle CLI, read-only rootfs, dropped capabilities and seccomp.
- `core/oci_runtime_probe.py`: bounded read-only version, info and CLI-help probes; no container mutation.
- `scripts/qualify_oci_runtime_preflight.py`: host-invokable read-only preflight; JSON result and nonzero exit on missing/incompatible runtime. It does not create/start/stop/remove containers or modify host networking.
- `core/oci_inspect_normalizer.py`: strict Docker/Podman inspect normalization; mismatches fail closed.
- Lifecycle executor gates CREATE → INSPECT → signed ATTEST → START, with bounded command timeouts and cleanup path.
- Positive/negative tests cover compatibility, version mismatch, runtime policy drift, inspect normalization and preflight output.

## Existing exact-head CI evidence

At implementation head `c8104c4ab49ceaaa378d2fa3c6dda61468d1bb29`:
- [Agent Foundation CI](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43795182589): PASS; Python 3.12 compile, dependency audit clean, 992 tests passed.
- [Python Demo CI](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43795182578): PASS.

At documentation update head `72ea66fee9823df4f27d13738b482b953cc28f85`, all three checks completed successfully. The egress job's completed step was a hosted-runner limitation notice, not a live network isolation test.

A further code commit adds the host preflight and tests; its CI must be checked separately before it can be called PASS.

## Live egress attempt — not qualified

The first actual run of `scripts/qualify_linux_egress_namespace.sh` on GitHub-hosted Ubuntu failed: the host-side IPv6 test sink could not bind `fd42:aa:19::1:3128`, and the worker-side IPv6 socket probe raised `Operation not permitted`. This is an environment capability failure, not evidence that the egress policy passed. The script now checks host/namespace IPv6 addresses, IPv6 socket creation and namespace-local nftables permissions before starting the test, and emits an explicit failure reason. The updated script has not yet passed a capable runner.

[Failed hosted-runner attempt — Agent Foundation CI run 43795768030](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43795768030).

## Operational qualification still pending

1. Real rootless Docker daemon qualification.
2. Real rootless Podman daemon qualification.
3. Actual inspect schema from each pinned runtime.
4. CREATE → INSPECT → signed ATTEST → START → STOP/REMOVE on a disposable daemon.
5. Timeout, cancellation, daemon interruption and bounded cleanup drills.
6. Runtime namespace inspection and no-host-port proof.
7. Live host firewall hook precedence and direct TCP, DNS TCP/UDP, UDP/443 (QUIC), IPv6 and alternate-interface bypass tests.
8. Trusted host collector installation; out-of-band Ed25519 key provisioning, rotation, revocation and recovery.
9. Android/Termux OCI support.

## Important CI interpretation

The workflow job named **Disposable Linux egress namespace qualification** has previously completed by running a step named **Report hosted-runner qualification limitation**. That was a SKIPPED qualification, not operational PASS. The namespace script exists but has not yet been demonstrated by that job.

Runtime probe tests use injected command runners. They prove deterministic policy behavior, not a live daemon.

## Host preflight and next gate

Follow [P20 Disposable Linux Host Runbook](APAA_S09_C01_P20_DISPOSABLE_HOST_RUNBOOK.md). Run the preflight on a disposable Linux host with the exact operator-approved runtime version:

```bash
python -m scripts.qualify_oci_runtime_preflight --runtime podman --pinned-version 5.4.2
```

The example version is not a universal recommendation; use the exact approved pin. Exit 0 means only that the read-only runtime contract passed. It does not qualify the full lifecycle or egress isolation.

No production firewall/network should be changed. If any required control cannot be proven, keep runtime disabled.

## Safety

Free-only. No API keys, paid providers, payments, purchases, checkout, trading or money movement. Auto-Run remains disabled. Browser/worker stays disabled. No merge or deployment is authorized.
