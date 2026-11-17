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


## Local attestation key lifecycle foundation

Added `core/attestation_keyring.py` with explicit initial-key creation,
rotation, retirement, revocation and trust-set export. The keyring requires an
existing owner-owned 0700 directory, stores raw Ed25519 private keys and
metadata as 0600 files, atomically replaces metadata, verifies private/public
key correspondence, and removes a revoked private-key file after publishing
the revocation state. Retired public keys remain trusted for verification of
older evidence; revoked public keys are excluded.

This is a local software keyring, not an HSM/TPM or out-of-band identity
authority. Unlinking a file is not guaranteed secure media erasure, and
backups may retain copies. Production signing requires independently managed
key custody, protected backups, controlled distribution of trusted public
keys, and a reviewed revocation propagation process. Do not treat this
foundation as production key custody.

## Verification note — CI #363

APAA Security CI #363 on commit `711947a9fd13784c278befcd87e745a4426923e9`
completed with **1,102 passed and 1 failed**. The only failure was a test
assertion expecting the phrase "direct fallback" while the implementation
correctly raised "browser reached the allowed page while its proxy was
unavailable". The three Chromium TLS checks, restricted-proxy Chromium test,
worker-adapter tests and host-inspector tests passed in that run. The assertion
was corrected in a follow-up commit. The keyring additions and the correction
still require exact-head CI verification.


The worker adapter now exposes `from_keyring(..., challenge_ledger=...)`,
which constructs the signer and trusted-key map from the active keyring entry
and refuses construction without an atomic durable replay ledger. Rotation
therefore takes effect when a fresh adapter instance is created from the
rotated keyring; already-running instances retain their original in-memory
key material and must be retired by the owner-controlled supervisor.


## Disposable Linux qualification — first real-host observations

- Run #50 exposed two workflow defects before host provisioning: the workflow
  passed Podman's bare local image ID without the required `sha256:` prefix,
  and the root-created evidence file was unreadable to the artifact uploader.
  Both workflow issues were corrected.
- Run #51 then built the pinned local image and provisioned the disposable
  namespace, dual-stack routes and firewall. It stopped at strict live nftables
  JSON semantic attestation with
  `NftablesAttestationError: live nftables ACCEPT rules differ from the exact approved policy`.
  Cleanup was confirmed; the evidence artifact uploaded successfully.
- The private artifact contained the human-readable firewall ruleset but not
  the exact JSON that the verifier rejected. The harness now retains a bounded
  exact JSON snapshot in the sanitized evidence artifact to diagnose the
  mismatch. No browser request or network-bypass result was recorded in run #51.
- The run #51 result is **FAIL / qualification incomplete**, not a host security
  PASS. The next run is intended to identify and correct the exact nftables
  JSON expression mismatch before Chromium or bypass tests can proceed.

## Adapter factory CI correction

APAA Security CI #386/#387 on the earlier factory commit failed because the
new `from_keyring` classmethod had been inserted before the adapter's runtime
state initialization, leaving `_states` and `_lock` unset. The initialization
was moved back into `__init__` before the factory method. The correction is
committed; exact-head CI is still required.


### Run #54 nftables JSON root cause and correction

The retained exact nftables JSON showed that nft 1.0.9 serializes the
firewall's explicit `ct state new` condition as a scalar equality match:
`{"ct":{"key":"state"}} == "new"`. The strict policy inventory had expected
the output-new rule without this condition, so it correctly rejected the
live ruleset as different from its declared policy. The attestor now requires
the exact `ct.state == "new"` condition, and its dual-stack fixture/regression
test models the live JSON representation. The real-host test must be rerun;
no Chromium or bypass tests ran in #54.


Run #58 retained the exact nft JSON and refined the diagnosis: nft 1.0.9
encodes the scalar new-state condition with operator `in` and right operand
`"new"` (not `==`). The policy verifier and regression fixture now require
that exact operator/value pair. The firewall's semantics remain unchanged;
this only makes the attestor match the actual kernel ruleset representation.
A further disposable-host run is required to verify the correction.


Run #61 showed the remaining representation mismatch: nft 1.0.9 emits
conntrack state sets as a JSON array (for example
`["established","related"]`), not the nft JSON object form
`{"set":[...]}`. The strict verifier and fixture now require the observed
array representation, alongside the scalar `in "new"` form. No Chromium
requests or bypass tests ran in #61. Requalification is required.
