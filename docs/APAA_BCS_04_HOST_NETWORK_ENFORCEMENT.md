# APAA P74 / BCS-04 — Independent OCI Runtime Observation

Added a read-only \`PodmanWorkerObserver\` foundation.

It does not trust the worker launch request as evidence. It independently:
- inspects the immutable container ID through Podman;
- checks read-only rootfs, dropped capabilities, no-new-privileges, exact
  seccomp profile, non-root UID/GID, namespace path and OCI CPU/memory/PID limits;
- reads the host PID's \`/proc\` start-time before and after observation to detect
  PID reuse during the snapshot;
- compares the process network-namespace inode with the provisioned namespace;
- reads unified cgroup-v2 membership and effective memory/cpu/pids limits from
  the host cgroup filesystem;
- requires kernel \`Seccomp: 2\` and a canonical immutable image ID.

The observer is a read-only primitive and has not yet been connected to signed
host attestation, the Owner approval controller, or production browser dispatch.
Its filesystem and runtime evidence must be captured on the disposable host and
bound to a one-time challenge before it can be treated as trusted attestation.

Tests use fake Podman/procfs/cgroup fixtures. They are not real-host evidence.
