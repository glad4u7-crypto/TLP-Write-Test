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

The version values above are examples only. Use the exact versions separately approved and pinned for the target host.

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

## Step 3 — Real daemon lifecycle gate (still pending)

The read-only preflight is not the real daemon lifecycle qualification. Before any worker can be enabled, a separate disposable-host harness must demonstrate:

1. A locally available digest-pinned image and pre-provisioned proxy-only network.
2. CREATE results in exactly one stopped container.
3. INSPECT returns the expected immutable ID, image digest, network, read-only rootfs, dropped capabilities, no-new-privileges and seccomp.
4. A trusted host collector signs a fresh, tenant-bound, single-use challenge bound to the exact container ID, worker name and launch-spec digest.
5. Invalid, stale, replayed, revoked-key or mismatched evidence blocks START and removes the stopped container.
6. Valid evidence permits START only once; timeout/cancellation/daemon interruption stops and removes the worker within bounded deadlines.
7. No orphaned containers remain after every pass/fail path.

Do not fabricate evidence or use test keys as production trust roots. Out-of-band Ed25519 key provisioning, rotation and revocation must be tested independently.

## Step 4 — Disposable namespace egress evidence

Latest exact-head evidence for code commit [e669a8767fa7471056e3695fca36d413d435675a](https://github.com/glad4u7-crypto/TLP-Write-Test/commit/e669a8767fa7471056e3695fca36d413d435675a): [Agent Foundation CI run 43801033918](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43801033918) — **PASS**. The job executed `sudo -n bash scripts/qualify_linux_egress_namespace.sh` on a disposable GitHub-hosted Linux runner. It created a temporary network namespace and veth pair, applied namespace-local nftables policy, allowed only the exact IPv4 TCP proxy destination, and verified that direct TCP, DNS TCP/UDP, UDP/443 and IPv6 probes did not reach the host-side sink. The script cleans up its namespace and veth on exit and does not edit host firewall chains.

This is a successful isolated namespace test, **not** proof of the complete OCI worker/proxy topology. Separate tests remain required for alternate-interface bypass resistance, external DNS policy, IPv6 UDP, host firewall hook precedence and daemon-integrated network configuration.

## Exit criteria

P20 remains **DAEMON QUALIFICATION PENDING** until real rootless daemon lifecycle, signed attestation, bounded cleanup and full worker-topology egress evidence are reviewed and recorded. A green unit-test job, mocked command runner or namespace-only egress test is not operational qualification.
