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

## Step 3 — Remaining lifecycle gate

The read-only preflight is not the real daemon lifecycle qualification. Before any worker can be enabled, a separate disposable-host harness must demonstrate:

1. A locally available digest-pinned image and pre-provisioned proxy-only network.
2. CREATE results in exactly one stopped container.
3. INSPECT returns the expected immutable ID, image digest, network, read-only rootfs, dropped capabilities, no-new-privileges and seccomp.
4. A trusted host collector signs a fresh, tenant-bound, single-use challenge bound to the exact container ID, worker name and launch-spec digest.
5. Invalid, stale, replayed, revoked-key or mismatched evidence blocks START and removes the stopped container.
6. Valid evidence permits START only once; timeout/cancellation/daemon interruption stops and removes the worker within bounded deadlines.
7. No orphaned containers remain after every pass/fail path.

Do not fabricate evidence or use test keys as production trust roots. Out-of-band Ed25519 key provisioning, rotation and revocation must be tested independently.

## Step 4 — Live egress isolation gate

Run `scripts/qualify_linux_egress_namespace.sh` only on a disposable Linux runner that supports network namespaces, veth, namespace-local nftables with CAP_NET_ADMIN, and usable IPv6 sockets/addresses. The current GitHub-hosted runner attempt failed because its IPv6/network capabilities were insufficient; the script now fails early with an actionable capability diagnostic. It creates a temporary namespace and veth pair and deletes them on exit. It must not change host firewall chains.

The current script validates an exact IPv4 TCP proxy destination and blocked direct IPv4 TCP, DNS TCP/UDP, UDP/443 and IPv6 TCP probes. It does **not** prove alternate-interface bypass resistance, external DNS resolution policy, IPv6 UDP, host firewall hook precedence, or the full production topology. Those remain separate acceptance tests.

## Exit criteria

P20 remains **DAEMON QUALIFICATION PENDING** until real daemon lifecycle, signed attestation, bounded cleanup and live egress evidence are reviewed and recorded. A green unit-test job, mocked command runner or skipped hosted-runner job is not operational qualification.
