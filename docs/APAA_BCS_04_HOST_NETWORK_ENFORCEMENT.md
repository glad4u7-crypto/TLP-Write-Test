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


## Verification correction record

- APAA Security CI run #333 tested commit `766dfedbe3722fc08ad9d85e4bc7eb8103d88c73`.
- The run completed with **1,085 passed and 2 failed**. The failures were isolated to the newly added nftables attestation fixture: one IPv6 conntrack-set representation mismatch and one over-broad non-global proxy-IP validation rule. The existing TLS, browser-worker adapter, Linux host-inspector and other suite tests passed in that run.
- Corrected the IPv6 fixture to the nft JSON `{"set":[...]}` representation and restricted non-global proxy IPs to the explicit APAA disposable-veth ranges. Added malformed-rule/unknown-field regression cases.
- Corrections are committed after the failed run; **a successful exact-head CI result for the corrected branch head has not yet been independently observed**. Do not mark BCS-04 CI PASS.


## One-time host-attestation challenge replay protection

The worker adapter now rejects a challenge already consumed by that adapter
instance, and consumes it before collection so failed collection cannot make
the nonce reusable. An injectable atomic ledger is supported for deployments
that need replay protection to survive process restarts and coordinate multiple
adapter processes.

`core/attestation_challenge_ledger.py` provides an owner-path-configured
SQLite ledger. It uses a primary-key uniqueness constraint and an immediate
write transaction so concurrent consumers have one winner; the database is
restricted to owner-only file permissions. The adapter fails closed if the
ledger errors or reports an already-consumed challenge.

For a real host deployment, configure this ledger on durable owner-controlled
storage and protect its parent directory. The adapter's in-memory fallback is
only process-lifetime protection and is not a production substitute.

## Remaining integration and qualification gates

- The `IsolatedWorkerBackend` remains an injected protocol, not a bundled
  production Podman/Android backend. No backend is auto-selected.
- The SQLite challenge ledger is optional at construction for test/development
  compatibility. A production backend must supply a durable ledger and
  out-of-band managed signing keys before it can be considered deployable.
- The independent Podman observer is not yet wired into a concrete trusted
  host snapshot source that produces signed attestation from live kernel state.
- Real-host Chromium, proxy TLS, direct TCP/DNS/UDP/QUIC bypass, crash/orphan
  cleanup and physical Android VpnService tests remain unrun.
- Browser dispatch and Public Live Browsing remain disabled. No merge or
  deployment is authorized by this implementation work.
