# P20 — Disposable Linux host qualification runbook

## Purpose and safety boundary

This runbook prepares a **disposable Linux test host** for APAA's real OCI qualification. It does not authorize production use. Use a clean VM or dedicated runner with no user data, no production workloads and no production firewall policy.

- Use a non-root account with rootless Docker or rootless Podman.
- Do not run as root and do not use `sudo docker` / `sudo podman`.
- Do not pull arbitrary images. Use an image already present locally and pinned by sha256 digest.
- Do not enable browser access, host mounts, secrets, host networking or public port publishing.
- Do not change host firewall rules for this preflight.
- Keep the worker disabled unless all later signed-attestation and egress qualification gates pass.

## Step 1 — Record the exact runtime version

Choose exactly one runtime and the version pinned in the APAA deployment policy.

Podman example:

```bash
python -m scripts.qualify_oci_runtime_preflight --runtime podman --pinned-version 5.4.2
```

Docker example:

```bash
python -m scripts.qualify_oci_runtime_preflight --runtime docker --pinned-version 27.5.1
```

The command is read-only. It calls only version, info and CLI-help commands. It never creates, starts, stops or removes a container. Exit code 0 means the observed runtime satisfies the probe's pinned rootless/cgroup/security/CLI contract. Exit code 2 means the runtime is absent, unreachable, unpinned or incompatible; keep OCI execution disabled.

The version values above are examples only. Use the exact versions separately approved for the target host.

## Step 2 — Record daemon facts independently

Save the outputs locally in the disposable host's qualification record:

```bash
id
podman info --format json
podman version
```

For Docker, use:

```bash
id
docker info --format '{{json .}}'
docker version
```

Do not paste secrets, registry credentials, environment variables or unrelated host inventory into issue comments.

## Step 3 — Rootless Podman CI runtime lifecycle smoke

The repository now contains [apaa-p20-rootless-podman-qualification.yml](../.github/workflows/apaa-p20-rootless-podman-qualification.yml). On a pull request or manual dispatch it uses an ephemeral GitHub-hosted Ubuntu runner and:

1. Installs Podman and rootless prerequisites; runs Podman as the non-root runner account and checks rootless mode plus cgroup v2.
2. Builds a local scratch image containing the runner's static BusyBox binary. No external base image is pulled.
3. Creates one stopped container using the local immutable image ID, `--network=none`, read-only rootfs, Podman's normalized capability-drop list with no added capabilities, no-new-privileges, an explicit seccomp profile and resource limits.
4. Inspects the container before start and checks its immutable ID and effective security configuration.
5. Starts, verifies running state, checks the actual process's CapInh/CapPrm/CapEff/CapBnd values are all zero, then stops and force-removes using the exact immutable container ID.
6. Checks that no qualification container remains and uploads a short-retention CI evidence artifact.

A green workflow is evidence for a real **rootless Podman runtime smoke lifecycle** on that disposable runner. It is not proof of APAA's signed-attestation integration, Docker compatibility, the production worker/proxy topology, alternate-interface egress resistance or Android support. Review the actual run and artifact before recording PASS. Do not describe an unobserved or failed run as qualified.

### Latest disposable rootless Podman run (2026-11-16)

[Workflow run #43808654979](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43808654979) completed **PASS** on documentation/code head `e590c46bb0e0fffcfa9abe6edf8e5043844b693c`. Every lifecycle step passed: rootless setup, local digest-addressed image build without a pull, hardened stopped-container CREATE/INSPECT, START and running-state verification, STOP, immutable-ID REMOVE, no-leftover-container check and sanitized evidence upload.

This closes the disposable rootless Podman CI smoke portion of P20. It does **not** close real APAA host qualification, trusted collector/key provisioning, durable monotonic anchor, Docker lifecycle, full worker/proxy topology, or Android/Termux gates.

## Step 4 — Full APAA runtime lifecycle gate (still pending)

Before any worker can be enabled, a separate integrated disposable-host harness must demonstrate:

1. A locally available digest-pinned application image and pre-provisioned proxy-only network.
2. CREATE results in exactly one stopped container.
3. INSPECT returns the expected immutable ID, image digest, network, read-only rootfs, dropped capabilities, no-new-privileges and seccomp.
4. A trusted host collector signs a fresh, tenant-bound, single-use challenge bound to the exact container ID, worker name and launch-spec digest.
5. Invalid, stale, replayed, revoked-key or mismatched evidence blocks START and removes the stopped container.
6. Valid evidence permits START only once; timeout/cancellation/daemon interruption stops and removes the worker within bounded deadlines.
7. No orphaned containers remain after every pass/fail path.

Do not fabricate evidence or use test keys as production trust roots. Out-of-band Ed25519 key provisioning, rotation and revocation must be tested independently.

## Step 5 — Disposable namespace egress evidence

The latest previously verified namespace run was [Agent Foundation CI run 43801811437](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43801811437) — **PASS** on commit `cc73d761945fcc8329d052816b69abccd3bd0740`. It created a temporary network namespace and veth pair, applied namespace-local nftables policy, allowed only the exact IPv4 TCP proxy destination, and verified that direct TCP, DNS TCP/UDP, UDP/443 and IPv6 probes did not reach the host-side sink. It did not edit host firewall chains.

This is a successful isolated namespace test, **not** proof of the complete OCI worker/proxy topology. Separate tests remain required for alternate-interface bypass resistance, external DNS policy, IPv6 UDP, host firewall hook precedence and daemon-integrated network configuration.

## Exit criteria

P20 remains **DAEMON QUALIFICATION PENDING** until the rootless Podman CI run is reviewed, real Docker compatibility is separately assessed, and APAA-integrated signed attestation, bounded cleanup and full worker-topology egress evidence are reviewed and recorded. A green unit-test job or namespace-only egress test is not operational qualification.
