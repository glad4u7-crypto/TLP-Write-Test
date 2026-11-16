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
- Added a dedicated **disposable rootless Podman runtime CI qualification**. Podman is daemonless; this is not a Podman daemon test. It installs Podman on an ephemeral GitHub-hosted Ubuntu runner, verifies non-root/rootless mode and cgroup v2, builds a local scratch+static-BusyBox image without pulling a base image, and runs CREATE → INSPECT → START → STOP → REMOVE by immutable container ID. Inspect assertions cover stopped pre-start state, read-only rootfs, all capabilities dropped, no-new-privileges, explicit seccomp, no network, and no privileged/host PID/IPC mode. A final orphan check and short-retention evidence artifact are included.

## Exact-head CI evidence

For PR head `ee1b181fe5d048cc18f4d8f6f9b8407c201b884f`, observed 2026-11-16:
- [Agent Foundation CI #878](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43803510263): **PASS** — dependency audit found no known vulnerabilities, Python 3.12 compile passed, **1002 tests passed**, and disposable namespace egress qualification passed.
- [Python Demo CI #953](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43803510287): **PASS** — **1002 tests passed** and demo output matched `Hello TradeLab Pro`.
- [Rootless Podman Runtime Qualification #7](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43803510418): **PASS** — real rootless Podman 4.9.3 on Ubuntu 24.04, rootless=true, cgroup v2; local image built without pulling; CREATE, stopped INSPECT, START, live process capability check, STOP and REMOVE all passed by immutable ID; final orphan check passed. The stop operation reached its 2-second timeout and used SIGKILL fallback; it completed and the container was removed. This is recorded as bounded stop/cleanup evidence, not graceful-stop evidence.
- [Evidence artifact](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43803510418/artifacts/14197467322): sanitized Podman info, image ID, container ID, inspect JSON and process capability status; 7-day retention.

The namespace egress PASS is not proof of the full OCI worker/proxy topology or alternate-interface bypass resistance.

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


## P21 follow-on — inspect capability normalization (CI pending)

During the P20 follow-on integration review, the APAA inspect normalizer was found to require the literal `CapDrop: ["ALL"]`. The qualified Podman runtime expands `--cap-drop=ALL` into the complete explicit Linux capability-name list. This mismatch could reject a correctly hardened Podman worker before the attestation stage.

P21 updates `core/oci_inspect_normalizer.py` to accept either the literal `ALL` marker or the complete recognized Linux capability set (including newer kernel capabilities such as PERFMON, BPF and CHECKPOINT_RESTORE), while rejecting empty, incomplete or unknown lists. It also rejects any non-empty `CapAdd`. P23's live Podman 4.9.3 integration then identified an additional runtime-specific inspect representation: Podman reports the exact 11-entry default capability grant set in `HostConfig.CapDrop` for `--cap-drop=ALL`. The normalizer now accepts only that exact Podman set (not subsets), still rejects non-empty `CapAdd`, and P23 separately verifies zero live process capability masks after START.

P21 commits currently on the PR branch:
- `2be42d8496469928f99a442fd3cb69dbe798aa90` — normalizer capability expansion support.
- `9e41b198e512d1850f768f0a444ebbc44316f530` — capability allowlist correction.
- `b61ec319fe36894440527679ba83d99eaa230808` — regression fixture update.

**Verification status:** P21 exact-head CI passed on `92c03c629230579be91fd052ee9fbd31bd88eb34` (2026-11-16):
- [Agent Foundation CI #883](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43804273609): **PASS** — both `test` and `Disposable Linux egress namespace qualification` jobs completed successfully; dependency audit, compile and foundation test steps passed.
- [Python Demo CI #958](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43804273602): **PASS**.
- [Rootless Podman Runtime Qualification #12](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43804273605): **PASS**.
The workflow-run jobs for Agent Foundation CI #883 both completed successfully. The P21 inspect-normalization change is therefore CI-verified at this exact head. This does not constitute APAA-integrated signed-attestation qualification or full production egress qualification.

## P22 — signed-attestation executor regression qualification

The OCI executor path in `core/oci_worker_executor.py` performs CREATE → immutable-ID INSPECT → tenant-bound durable challenge issuance → Ed25519 evidence verification and one-time challenge consumption → START. Stateless launch is deliberately blocked.

Executor-level fake-runner regression coverage now verifies:
- Valid evidence is accepted in the required CREATE → INSPECT → ATTEST → START order.
- Invalid signature blocks START and removes the created worker.
- Revoked inspector key blocks START and removes the created worker.
- Evidence signed for a different worker blocks START and removes the created worker.
- Replaying the previous launch's challenge blocks the second START and removes the second created worker.
- Host-inspector interruption blocks START and removes the created worker.

P22 code commits:
- `4db4600925a996d70edbe3b1c2f053552e2b7073` — revoked-key and wrong-worker rejection.
- `ea2c9c199ea31250c97bb2058970f0d80af84bd4` — syntax correction after the first CI run exposed malformed test source.
- `defed5766c5b9e557916aa740e66b9509300b142` — replay and inspector-interruption cleanup cases.

**Exact-head P22 CI PASS:** `defed5766c5b9e557916aa740e66b9509300b142`
- [Agent Foundation CI #887](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43804779558): **PASS** — dependency audit found no known vulnerabilities, compile passed, **1009 tests passed**, disposable Linux egress namespace qualification passed.
- [Python Demo CI #962](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43804779535): **PASS** — **1009 tests passed** and demo step passed.
- [Rootless Podman Runtime Qualification #16](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43804779519): **PASS** — rootless Podman, cgroup v2, local image build, hardened inspect, immutable-ID lifecycle, no-orphan check and evidence upload passed.
- [P22 Podman evidence artifact](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43804779519/artifacts/14197513360).

**Qualification boundary:** the new executor regression tests use a fake runtime runner. The Podman workflow separately qualifies the runtime CLI and hardened lifecycle; it does not call APAA's signed-attestation executor. Therefore APAA-integrated signed attestation against a real OCI runtime remains unqualified. Podman STOP used the bounded 2-second SIGTERM window and SIGKILL fallback; this is not graceful-stop proof.


## P23 — real rootless Podman executor integration (test-only signer)

Added `tests/test_oci_worker_executor_podman_integration.py` and `.github/workflows/apaa-p23-rootless-podman-executor-integration.yml`. On an ephemeral Ubuntu 24.04 runner, the workflow installs rootless Podman 4.9.3, verifies cgroup v2, builds a local static BusyBox image without pulling a base image, creates an internal-only named network, and runs APAA's actual `OCIWorkerExecutor` against the real Podman CLI.

The positive integration case exercises:
- CREATE and capture of the immutable runtime container ID.
- Real Podman INSPECT normalization, including Podman's `HostConfig.NetworkMode=bridge` plus the exact named `NetworkSettings.Networks` attachment.
- Durable tenant-bound challenge issuance and one-time consumption through SQLite.
- Ed25519 evidence signature verification using an ephemeral CI-only signer.
- START only after the attestation gate accepts the evidence.
- Live `CapInh`, `CapPrm`, `CapEff` and `CapBnd` masks all equal zero.
- Handle-bound STOP and force-REMOVE by immutable ID, followed by an absent-container check.

The negative integration case supplies a corrupted signature and verifies that START is not called and the real created Podman container is removed. A final workflow cleanup checks that no APAA-managed container remains.

P23 also fixes two real Podman 4.9.3 inspect mismatches:
- A named bridge is represented as generic `HostConfig.NetworkMode=bridge`; APAA now accepts it only when `NetworkSettings.Networks` contains exactly the one approved named network and no additional attachment.
- Podman's `CapDrop` inspect field lists its exact 11 default capabilities for `--cap-drop=ALL`; APAA accepts only that exact Podman set, rejects partial/unknown sets and rejects any `CapAdd`.

**Exact-head P23 verification:** `ebd2d8e46f6ca1b2d82f64d68d8d189d28c0b113` (2026-11-16):
- [Agent Foundation CI #903](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43806208788): **PASS** — dependency audit found no known vulnerabilities, Python compile passed, **1013 tests passed / 2 skipped**, disposable Linux egress namespace qualification passed.
- [Python Demo CI #978](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43806208755): **PASS**.
- [Rootless Podman Runtime Qualification #32](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43806208806): **PASS**.
- [P23 Rootless Podman Executor Integration #14](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43806208763): **PASS** — real executor lifecycle, valid evidence gate, bad-signature rejection, zero live capability masks, cleanup and no-orphan check.
- [P23 sanitized Podman evidence artifact](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43806208763/artifacts/14198142305).

**Critical trust boundary:** the P23 Ed25519 signer is generated inside disposable CI solely to exercise executor/control-plane wiring. The signed firewall/runtime evidence is synthetic test data, not a trusted host observation. P23 therefore qualifies real Podman lifecycle integration and the software attestation gate, but does NOT qualify a production trusted host collector, out-of-band key provisioning, firewall truth, proxy-only egress, or production worker enablement. Browser/worker remains disabled.

## Remaining operational qualification

1. Install and independently trust a real host-side collector; provision its Ed25519 public key out-of-band and test rotation, revocation and recovery. P23 uses an explicitly synthetic CI signer.
2. Real-runtime tenant/runtime mismatch, replayed/revoked-key, cancellation/daemon interruption and orphan-cleanup drills against the trusted collector path.
3. Full worker/proxy egress topology, alternate-interface bypass resistance, external DNS policy, IPv6 UDP and firewall hook precedence. P23 uses an internal-only network and synthetic firewall claims; it is not egress qualification.
4. Rootless Docker qualification if Docker remains an enabled supported runtime; otherwise keep Docker execution disabled until separately qualified.
5. Android/Termux OCI remains unsupported/unqualified. Android may be used as a control-plane client, but the OCI worker must remain on a separately qualified Linux host until Android runtime compatibility is proven.

Independent control-plane unit tests cover wrong-tenant isolation, challenge expiry, single-use consumption and revoked/expired keys. These tests are not a substitute for integrated real-runtime evidence.


P21 CI evidence above supersedes the earlier P21 “CI pending” note.
