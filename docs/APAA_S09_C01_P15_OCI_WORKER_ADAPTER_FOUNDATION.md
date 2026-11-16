# APAA-S09-C01-P15 — OCI Worker Adapter Foundation

**Status:** implementation foundation committed; no runtime execution or host isolation has been performed.

## Deliverables

- \`core/oci_worker_plan.py\` builds immutable argument vectors for Podman or Docker.
- \`tests/test_oci_worker_plan.py\` covers command shape, hardening flags, input validation, pinned image requirement, explicit network selection, and the no-execution boundary.
- The plan is split into create, inspect, start, stop and remove commands. The create phase must leave the worker in the created/not-running state. Signed inspector evidence must be collected and verified before the start command is authorized.

## Required launch constraints encoded in the plan

- Rootless runtime is required (the \`rootless=True\` value is an operator assertion, not proof).
- Image must be pinned by immutable sha256 digest and pulls are disabled.
- An explicitly named APAA egress network is required; default/host/bridge network names are rejected.
- Non-root UID/GID, read-only root, all Linux capabilities dropped, no-new-privileges, explicit seccomp profile, PID limit, memory limit, CPU limit, private IPC/PID/UTS namespaces, and bounded noexec/nosuid/nodev tmpfs are included.
- No host mounts, secret mounts, persistent browser profile, CDP, host networking, or shell command strings are added.
- All commands are returned as argv tuples. No shell interpolation is used.

## Mandatory external integration contract

This module intentionally does not execute commands. Before any production adapter is implemented or enabled, a separate reviewed executor must:

1. Resolve and verify the rootless runtime binary and version.
2. Verify the image digest against an approved offline image manifest; never pull during job launch.
3. Verify the named network exists and is dedicated to the worker.
4. Verify proxy reachability is the only permitted egress from inside that network using host-enforced firewall policy, including TCP/DNS/UDP/QUIC bypass tests.
5. Create the container and inspect the actual OCI configuration while it is still stopped.
6. Obtain fresh, signed, challenge-bound host inspector evidence for the exact runtime ID, worker ID, launch spec digest, network namespace inode, seccomp, mounts, limits and firewall ruleset.
7. Pass that evidence through \`AttestedBrowserRuntime\`; only its verified worker callback may execute the start command.
8. On timeout, cancellation, proxy outage, failed attestation, or any command error, do not start and remove the stopped worker. After start, enforce bounded stop/kill/remove cleanup with no fallback network or browser mode.
9. Store audit metadata without cookies, credentials, user browsing content or private keys.

## Known blockers — not represented as completed

- P12 proxy/worker topology is still unresolved. The existing proxy binds loopback while the worker contract refers to an internal proxy endpoint. This plan does not change either side or create a network.
- The selected network name is only a selector. The plan cannot prove that the network is proxy-only or that a default route cannot bypass the proxy.
- The host's rootless mode, seccomp profile contents, runtime version, image digest, network namespace and firewall rules must be independently measured by a trusted inspector.
- Docker and Podman flag compatibility must be tested against pinned versions on a disposable Linux host. No such host integration test has been run.
- The plan builder does not create a host/container worker adapter, does not start a browser, and does not qualify Android/Termux.
- Existing signed-evidence collection and verification still depend on an external trusted inspector, externally provisioned keys and one-time challenge lifecycle.

## Safety boundary

No runtime command was executed. No container, network, firewall, namespace, filesystem mount, browser, or website was created/accessed. No secrets, API keys, paid services, payment, purchase, trading, money movement, merge, deployment or production enablement occurred.

**Decision:** P15 plan-builder foundation is implemented; P15 is not operationally complete. Live browsing remains disabled.
