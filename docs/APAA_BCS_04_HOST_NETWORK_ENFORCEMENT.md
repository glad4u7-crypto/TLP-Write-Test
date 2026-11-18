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


### Run #64 — nftables attestation passed; OCI inspect gate blocked

The corrected nftables parser passed against the live nft 1.0.9 ruleset:
13 exact ACCEPT rules and both default-DROP chains were attested. Namespace,
dual-stack routes, firewall and both pinned proxy listeners were also
provisioned. The run then stopped before browser start because Podman inspect
did not satisfy the script's read-only-rootfs / CapDrop=ALL assertion. Cleanup
was confirmed. No Chromium request or bypass test ran.

The next evidence artifact now records only the relevant non-secret OCI
inspect fields (read-only root, capability drop, security options, resource
limits, user, cgroup parent, network mode and state) to identify whether the
mismatch is a runtime representation issue or a real enforcement defect.


### Run #66 — Podman capability-drop representation

After nftables attestation passed, run #66 exposed a Podman representation
difference: `--cap-drop=ALL` is expanded by Podman inspect into the list of
capabilities available to that runtime (for this runner, 11 `CAP_*` entries),
not the literal string `ALL`. The real-host preflight and read-only observer
now validate a non-empty, unique `CAP_*` drop list, reject any `CapAdd`, and
independently require kernel `/proc/<pid>/status` `CapEff` to be zero after
worker start. Regression tests cover capability additions and non-zero
effective capability masks. This avoids trusting the CLI flag alone.


### Run #70 — OCI hardening passed; cgroup membership gate blocked

The revised preflight accepted Podman's expanded capability-drop list, and the
observer progressed beyond the OCI security assertion. It then rejected the
worker because the live process cgroup path did not fall beneath the declared
dedicated parent. Cleanup was confirmed; no Chromium request or bypass test
ran. The next run records the exact `/proc/<pid>/cgroup` value and includes
the observed/expected paths in the observer error so the cgroup-v2 attachment
can be corrected from evidence rather than weakened.


CI #424 after the capability observer changes: **1,113 passed, 1 failed**.
The sole failure was a stale regression assertion that still expected
`ct.state == "new"` while the fixture and strict verifier had been corrected
to the actual nft JSON `ct.state in "new"`. The assertion has now been
corrected. All TLS, proxy, controller and worker-attestation contract steps
completed successfully in that run; the remaining suite had only this one
failure.


Run #75 identified the cgroup discrepancy precisely: procfs reported
`/sys/fs/cgroup/apaa/worker-p74-01/libpod-<container-id>`, while the
observer compared it with the cgroup path relative to the mounted cgroup-v2
root (`/apaa/worker-p74-01`). The process was in the correct dedicated
subtree; the observer had failed to strip the mount prefix. It now normalizes
only the exact configured cgroup-root prefix before subtree comparison and
uses the normalized path for limit readback. A regression test covers this
mount-prefixed procfs representation. This is a path normalization correction,
not a relaxation of subtree isolation.


Run #78 confirmed that the cgroup path now normalizes into the expected
subtree, but the observer could not resolve the worker leaf directory under
the mounted cgroup root. The next run records a bounded diagnostic of the
candidate leaf, its parent, and sibling entries, and the observer error
includes the exact candidate path plus OS error type. This will distinguish
a missing Podman cgroupfs leaf from a mount-root or delegation mismatch.


Run #81 confirmed the normalized candidate path, but the worker's reported
`libpod-<id>` leaf is absent from the cgroup-v2 filesystem even though its
parent exists. The next diagnostic artifact now includes the parent's
`cgroup.procs`, `cgroup.type`, `cgroup.subtree_control` and
`cgroup.events` values to determine whether Podman attached the process
directly to the delegated parent, used a different cgroup namespace, or failed
to create the expected child. The observer remains fail-closed.


### Run #83 — cgroup child-controller root cause and fix

The parent cgroup diagnostics showed `cgroup.procs` empty,
`cgroup.subtree_control` empty, and no `libpod-<id>` child directory.
The OCI process reported the child path, but the parent had not delegated
`cpu`, `memory` and `pids` controllers to children. The cgroup provisioner
now enables and verifies all three controllers on the per-worker parent before
Podman creates its child cgroup. New tests cover successful delegation and
fail-closed behavior when controllers are unavailable. The real-host workflow
must verify that Podman now creates the expected leaf and that effective limits
are read back before browser tests can run.


### Run #78 — cgroup path was not backed by a host cgroup directory

The retained evidence showed that the reported procfs membership named a
`libpod-<container-id>` child that did not exist under the delegated cgroup
parent. The parent itself existed, but the evidence did not prove where the
worker PID was actually accounted. The observer has therefore been changed
to locate the host PID by reading `cgroup.procs` throughout only the
dedicated worker subtree (no symlink traversal; bounded to 4,096 directories
and depth 8), requiring exactly one match, and reading limits from that
matched cgroup. It rejects missing or duplicate PID membership. Regression
tests cover namespace-relative/unmapped proc paths, absent PID membership,
and duplicate membership. This is stronger than accepting a procfs path and
does not relax cgroup isolation. A new real-host run is required to establish
whether the worker is actually accounted within the delegated subtree.


### Run #90 — delegated cgroup hierarchy path correction

The real-host evidence showed that the OCI process reported a namespace-visible
path beginning with `/sys/fs/cgroup/apaa/...`, but the corresponding host
cgroup leaf did not exist and the delegated parent had no worker PID. The
provisioner had passed the filesystem mount path to Podman's
`--cgroup-parent`. Podman expects a path in the cgroup hierarchy (for example
`/apaa/worker-p74-01`), not the host filesystem mount prefix
`/sys/fs/cgroup`. The OCI spec now carries only the validated hierarchy path;
the observer resolves it beneath the configured cgroup-v2 mount and still
requires exactly one host-PID match in real `cgroup.procs` files. This is a
path-contract correction, not a relaxation of the kernel-membership gate.
The observer unit fixtures were also corrected to model the kernel-provided
`cgroup.procs` pseudo-file at each directory traversed. The real-host run must
be repeated; no Chromium or network-bypass PASS is claimed until it reaches
those steps.


The cgroup hierarchy-path correction is now committed with a gated disposable-host
requalification trigger. The next exact-head CI and real-host evidence determine
whether the Podman cgroup leaf is actually created and populated.


### Run #100 — cgroup hierarchy path now resolves; image identity and teardown blocked

The corrected Podman cgroup hierarchy path produced the expected real host
`libpod-<container-id>` child directory. The dedicated parent reported
`populated 1`, and the worker process path resolved beneath
`/apaa/worker-p74-01`; the observer therefore advanced beyond the previous
missing-membership failure. It next rejected Podman's reported image ID because
the runtime representation was not the observer's expected canonical
`sha256:<64 hex>` form. The observer now normalizes only a bare, full 64-hex
image ID to that canonical form and rejects all short IDs/tags; sanitized
evidence now records the raw inspect image identity. Cleanup also exposed that
Podman leaves nested `conmon`/container cgroup directories under the
dedicated worker parent. The cleanup path now checks every descendant's
`cgroup.procs`, refuses removal if any process remains, and removes only
empty descendants bottom-up within the dedicated APAA subtree. New regression
tests cover both safe empty-tree cleanup and refusal when a descendant still
contains a process. Run #100 was **BLOCKED**, with cleanup not fully confirmed;
no Chromium request or network-bypass result ran. A fresh disposable-host
qualification is required for both corrections.


The image-identity and recursive-cleanup corrections are queued for the next gated disposable-host qualification.


### Run #111 — independent OCI observation passed; Chromium command diagnostics needed

The real-host evidence confirms the worker PID was found in the actual delegated
cgroup subtree, kernel memory/CPU/PID limits matched, seccomp mode was active,
network namespace inode matched, and the exact 13-rule dual-stack default-DROP
policy was attested. Cleanup was confirmed. The run then stopped at a Podman
command used after preflight; the old harness reported only the executable name,
so it did not distinguish a Chromium launch failure from a Podman exec/setup
failure. The harness now reports a sanitized command label, exit code and
redacted bounded diagnostic. The direct-egress probes were also tightened:
a nonzero command exit is no longer treated as proof of firewall blocking;
only recognized socket-level network-unreachable/no-route/timeout outcomes
count, and their hashes/status are retained. The earlier run's direct-probe
flags are therefore not accepted as conclusive evidence. No Chromium HTTPS
success, packet-capture proxy-only proof or proxy-outage fallback test has yet
passed on the disposable host.

### Signed host-inspector nftables parser alignment

The offline signed-inspector parser now accepts only the complete APAA
dual-stack policy: one inet apaa table, exactly input/output filter chains with
default DROP, exact loopback rules, narrowly scoped IPv6 neighbour discovery,
and exact proxy source/return plus destination/new TCP rules for every pinned
proxy IP. It rejects additional chains, tables, unknown objects, altered input
rules, extra ACCEPT paths, jumps and unreviewed expressions. Regression tests
now model the complete 13-rule live nft 1.0.9 JSON observed on the disposable
host. This parser change still requires exact-head CI and integration
qualification before it can be considered production-ready.

The latest parser, direct-egress probe and cleanup changes are queued for exact-head CI and disposable-host requalification.


### HTTPS CONNECT hostname binding to TLS SNI

The pinned CONNECT proxy now parses the bounded TLS ClientHello before forwarding
any TLS bytes upstream and requires exactly one canonical host_name SNI matching
the approved CONNECT authority. Missing, malformed, duplicate, non-ASCII or
mismatched SNI is rejected; TLS remains end-to-end and certificate verification
stays in Chromium. ClientHello records may be fragmented, but the pre-forward
read is size- and time-bounded. Proxy shutdown now closes active sockets and
waits for non-daemon handler threads before reporting completion. Pinned socket
verification also checks the connected peer port, not only its IP address.
Focused tests cover SNI parsing, fragmentation, malformed/no/duplicate SNI,
shutdown behavior boundaries and exact upstream peer identity. These changes
require exact-head CI and a new real Chromium qualification.


The latest changes are queued for a fresh disposable-host Chromium and network-bypass run.


## BCS-04 — durable browser recovery, cancellation and audit hardening

Added `core/browser_recovery.py`, an owner-private SQLite job journal:
- Atomic unique `job_id` claims with a SHA-256 request fingerprint; a completed, failed,
  cancelled, timed-out or interrupted ID can never be replayed.
- Explicit one-way states (`accepted → running → terminal`), with a bounded
  cancellation-request state. State changes are persisted with SQLite
  `synchronous=FULL` and owner-only database permissions.
- On process restart, `recover_interrupted()` converts accepted/running/cancelling
  jobs to `interrupted`. It deliberately does not auto-retry: after a crash the
  system cannot prove whether an external operation happened before failure.
- A durable dispatch-block latch prevents new jobs after audit or recovery-state
  failure and survives process restarts.
- `BrowserExecutionCoordinator` accepts the durable ledger; its attested-runtime
  factory requires one and marks pre-crash jobs interrupted before constructing
  a new coordinator. Duplicate completed-job replay is blocked.

`core/audit.py` now redacts credential assignments, bearer/basic authorization
values, URL paths/query/fragments and email addresses from event text, and
bounds the resulting text. Audit-write failures latch the coordinator and,
when configured, persist a dispatch block before any subsequent job can start.

New regression coverage:
- `tests/test_browser_recovery.py`: restart recovery, durable duplicate rejection,
  concurrent single-winner claims, terminal-state protection and durable
  dispatch blocking.
- `tests/test_browser_recovery_integration.py`: coordinator-level completed-job
  replay prevention and audit-failure dispatch stop.
- `tests/test_audit_redaction.py`: credential, URL and email redaction.

Qualification limits: these are code-level implementation and automated tests;
they do not prove physical Android process supervision or real-host Chromium
crash recovery. The application must configure a durable owner-private ledger
and call the startup recovery boundary before exposing browser dispatch.
The existing injected `IsolatedWorkerBackend` is still not a production backend.
Browser/Worker dispatch and Public Live Browsing remain DISABLED; Auto-Run OFF.
No merge or deployment.


### Browser protocol and DNS confinement

The signed Playwright Chromium launcher and disposable-host qualification now
disable HTTP/2 (preventing cross-origin HTTP/2 connection coalescing), disable
QUIC/HTTP/3, and apply a Chromium host-resolver rule that prevents local DNS
resolution. The proxy address is numeric and pinned by signed firewall evidence;
origin DNS is resolved only by the host-side pinned proxy. UDP DNS/QUIC probes
showed the runner's default seccomp profile denies UDP socket creation with
EPERM. The harness now records this explicitly as
`seccomp_socket_creation_denied` for UDP probes only; it does not mislabel it
as an nftables drop. TCP direct-egress probes still require a real
network-unreachable/no-route/timeout result. IPv4 and IPv6 UDP/443 probes are
both recorded. No seccomp rule was weakened.

These protocol-confinement changes are queued for exact-head CI and disposable-host requalification.


### Additional hardening and regression coverage

Cgroup teardown now checks both every descendant cgroup's `cgroup.procs`
and `cgroup.threads` before removing empty nested directories, so a live
thread cannot be missed by process-leader-only inspection. The signed browser
launcher disables HTTP/2 and QUIC and blocks local hostname resolution; this
closes HTTP/2 origin-coalescing and local DNS paths around the CONNECT proxy.
The CONNECT proxy now has socket-pair integration tests proving a mismatched
TLS SNI is never forwarded upstream, while a matching SNI is forwarded only
after validation. The pinned egress connector verifies both peer IP and peer
port. The dual-stack nftables fixture now mirrors live nft 1.0.9 metadata and
handle fields. These are code/test changes only until the exact-head CI and
disposable-host run complete.

The complete latest security set is queued for a fresh exact-head CI and real OCI Chromium run.


### DNS rebinding and proxy-outage evidence gates

The proxy now counts DNS/IP-pin rejection explicitly. A live socket-pair
regression test exercises two successive CONNECT attempts for the same hostname:
a public DNS answer is pinned and succeeds, then a changed answer to loopback
is rejected before any second upstream socket is opened. Mixed public/private
answer sets are also rejected. The outage harness no longer treats any failed
Podman/Chromium command as a successful proxy outage: it requires Chromium's
explicit `ERR_PROXY_CONNECTION_FAILED` or `ERR_TUNNEL_CONNECTION_FAILED`
result and still verifies that the allowed-page marker is absent. Canonical
CONNECT port spelling is enforced (exactly `:443`, without alternate numeric
forms). These checks still require exact-head CI and disposable-host execution.

The latest DNS-rebinding and outage-gate changes are queued for exact-head verification.


### Critical launch-boundary correction — host Playwright is not the OCI worker

A source audit found that the legacy signed-gate callback used
`browser_type.launch()` in the host Python process after verifying a separate
OCI worker's network namespace. That did not place Chromium inside the attested
worker and could therefore bypass the worker's namespace/firewall boundary.
The callback now always fails closed with an explicit isolated-backend-required
error. The separate P01 local Playwright launcher is also disabled by default
and can be used only through an explicit test/developer opt-in; it is not a
production action path. The Streamlit app does not expose LiveBrowsingController
or BrowserExecutionCoordinator as user-facing actions. No public browsing or
browser dispatch is enabled.

**Remaining integration blocker:** implement and independently qualify a real
`IsolatedWorkerBackend` that creates the OCI worker, gathers live host evidence,
starts Playwright/Chromium inside that worker, streams only bounded job results
back over a private worker channel, and destroys the worker on success, timeout,
cancellation and crash. A host-local Playwright callback is not an acceptable
substitute. Android additionally needs a real VpnService/worker transport and
physical-device bypass qualification; the repository currently has no Android
application module.


### Run #181 — network boundary passed; Chromium sandbox launch blocked

The latest disposable-host run confirmed the exact dual-stack firewall and
cgroup membership/limits, verified cleanup, and completed the direct-egress
checks: TCP DNS/IPv4/IPv6 probes were blocked at the network boundary, while
UDP DNS and UDP/443 socket creation was denied by seccomp (recorded separately).
Chromium itself did not start: its default setuid/chroot sandbox path attempted
`chroot` and failed under the intentionally dropped `CAP_SYS_CHROOT` and
no-new-privileges policy. No sandbox capability was added and `--no-sandbox`
was not used. The next qualification selects Chromium's user-namespace sandbox
by disabling only its setuid helper; this must still prove a working namespace
sandbox on the disposable host before Chromium is considered qualified.

The user-namespace sandbox configuration is queued for a fresh disposable-host Chromium run.


### Run #196 — direct egress passed; user-namespace sandbox still unavailable

The stricter UDP evidence and TCP firewall probes passed, and OCI/cgroup
cleanup remained confirmed. Chromium still failed at the same `sys_chroot`
sandbox initialization step even with `--disable-setuid-sandbox`; no browser
HTTPS or proxy-outage result was produced. The harness now captures only the
relevant syscall rules from the exact deny-by-default seccomp profile and runs
a separate in-container `unshare(CLONE_NEWUSER)` capability probe. The next
decision will be based on those kernel/profile facts; no capability, SUID
helper, seccomp-unconfined mode or `--no-sandbox` fallback will be introduced.

The seccomp/user-namespace diagnostic run is queued on a fresh disposable host.


## BCS-04 follow-up hardening — exact-head review

The recovery and audit implementation was re-reviewed after the first CI attempt.
The following corrections are now in the branch:

- Every SQLite journal operation now uses an explicitly bounded
  `BEGIN IMMEDIATE` transaction and closes its connection on all paths.
  This serializes read/transition/write lifecycle changes across processes and
  prevents two concurrent terminal transitions from overwriting one another.
- Request fingerprints accept only canonical lowercase SHA-256 hex.
- An unconfirmed timeout or cancellation is **not** recorded as successful
  cancellation. The job is marked `interrupted`, the durable dispatch
  latch is set, and later jobs are refused until Owner review.
- Startup recovery that finds any pre-crash active job marks it interrupted,
  latches dispatch, and refuses to start the runtime gate. No potentially
  orphaned worker is silently left running while new work starts.
- Audit redaction now masks bearer/basic credentials before parsing
  Authorization assignments, including direct dataclass-to-JSONL persistence.
- Updated the signed-runtime test fixture to exercise the exact current
  dual-stack `inet apaa` input/output default-DROP policy rather than an obsolete
  single-chain legacy fixture. Fixed cgroup-v2 test fixtures to model the
  kernel `cgroup.threads` file and restored precise regression-test error wording.

The earlier exact-head run on commit `3225f7055ebdf27ecb3b46effc43be92e974d7fa`
failed with 27 tests and 1,139 passed. The identified failures included the
legacy nftables test fixture, Authorization bearer redaction, cancellation
error wording, cgroup test fixture completeness, and pinned-peer error wording.
Those items have been corrected in later commits. Exact-head CI for the current
branch head must complete successfully before this work can be called CI-verified.

### Remaining non-code acceptance gates

- The real OCI Chromium workflow is intentionally skipped on ordinary pushes;
  it requires its separate disposable-host qualification trigger and
  environment. No real-host PASS is claimed.
- The repository still has no bundled production `IsolatedWorkerBackend`
  and no Android application/VpnService module. The OCI runtime, host observer,
  namespace/firewall provisioners and worker adapter remain separately
  injected components. Real process/container orphan reaping and physical
  Android crash/bypass acceptance therefore remain unqualified.
- Interrupted jobs now fail closed and latch dispatch, but clearing that latch
  requires a separately authenticated Owner recovery/review procedure. No
  automatic replay or automatic latch reset is provided.
- Browser/Worker dispatch and Public Live Browsing remain disabled; Auto-Run
  remains OFF. No merge or deployment.


### Run #200 — user namespaces are available, but Chromium's chroot sandbox still fails

The in-container `unshare(CLONE_NEWUSER)` probe succeeded under the existing
deny-by-default seccomp profile, so the host kernel and container policy permit
unprivileged user namespaces. Chromium nevertheless failed at its zygote
`chroot` step; the earlier probe did not establish UID/GID mapping or
`CAP_SYS_CHROOT` inside the newly created namespace. The next harness version
tests the complete unprivileged UID/GID-map plus chroot sequence, captures the
relevant seccomp syscall rules under a separate evidence field, and retains the
bounded tail of Chromium's sandbox diagnostics. No capabilities or seccomp
permissions have been broadened.

The complete user-namespace mapping/chroot probe is queued for exact-head CI and a new disposable-host run.


## Verification update

APAA Security CI run `44084851998` completed successfully on parent commit
`3b914a582e552f6d436b185dc3bd4905df2a30d8`: **1,170 passed, 0 failed, 1 warning**.
All dedicated Chromium TLS, restricted-proxy Chromium, worker-adapter and
Linux host-inspector stages passed. The latest branch subsequently added a
user-namespace/chroot fail-closed regression test; exact-head CI for the
newer commit must also pass before BCS-04 is declared fully CI-verified.


### CI naming correction

The separate Chromium TLS integration test uses a local-only loopback CONNECT
proxy and a fake runtime callback; it also disables Chromium's internal sandbox
for that test fixture. It validates certificate handling and controller
request policy only. Its CI step and test name now explicitly say
test-only/local and do not claim OCI isolation or production sandbox proof.
Only the disposable P74 real-host workflow can qualify the OCI network boundary
and in-worker Chromium sandbox.


## Real OCI Chromium failure analysis and safe retry

The disposable-host qualification reached the real container and built the
Chromium image, delegated cgroup-v2 subtree and network namespace. The first
real Chromium run exited with code 139 because Crashpad attempted `ptrace`
and `tgkill` operations denied by the worker seccomp policy. This was not
evidence of a network bypass; the browser process itself did not complete.

The qualification now adds Chromium's upstream `--disable-crashpad-for-testing`
switch alongside the existing crash-reporting flags. Chromium documents this
switch as preventing Crashpad initialization (the Crashpad binary is not
started); it does **not** add `--no-sandbox` or relax the worker seccomp,
namespace, capability or firewall policy. A regression test asserts the
Crashpad switch is present and the no-sandbox bypass flag is absent.

A fresh disposable-host run is being requested for this exact code revision.
No success is claimed until both IPv4 and IPv6 Chromium HTTPS tests, direct
egress negative tests, proxy-outage test, packet capture and cleanup evidence
all pass.


### Chromium user-namespace sandbox: narrowly scoped seccomp correction

Run #210 established that unprivileged user-namespace creation works, but the
Podman default seccomp profile conditionally denies `chroot` whenever the
container has no host-user-namespace `CAP_SYS_CHROOT`. That conditional rule
also blocks Chromium's nested user-namespace sandbox after it has legitimately
created and mapped its own user namespace. A new preparation script derives a
profile from the exact host default, preserves `SCMP_ACT_ERRNO` as the global
default, removes only the two capability-conditional `chroot` rules, and adds
one syscall allow rule. It does **not** add `CAP_SYS_CHROOT`; the kernel still
enforces that capability in the caller's current user namespace. The worker's
host-user-namespace `CapEff=0`, `NoNewPrivs=1`, and seccomp mode 2 checks remain
mandatory. The generated profile is owner-only, atomically written, hashed,
and post-validated. Exact-host Chromium qualification is still required.

The minimal chroot-syscall profile is queued for unit tests, exact-head CI and disposable-host Chromium requalification.

The generated profile has been updated to use only OCI-standard syscall fields; no capability is added. The full workflow is queued for exact-head requalification.


## Chromium user-namespace chroot compatibility correction

The second disposable OCI run confirmed that Crashpad was no longer the blocker.
The independent user-namespace probe successfully created/mapped a nested user
namespace but reported `USERNS_CHROOT_ERR 1`. The Podman baseline seccomp
profile conditionally allowed `chroot` only when `CAP_SYS_CHROOT` was
already present in the container's capability set; the worker intentionally
drops that capability. Chromium's own user-namespace sandbox requires the
`chroot` syscall after entering its nested user namespace, where the kernel
grants the process namespace-scoped capabilities.

Added `scripts/prepare_chromium_seccomp_profile.py` to derive an owner-private
profile from the exact Podman default. It changes only the capability-conditional
`chroot` rule into a syscall allow rule, while preserving
`SCMP_ACT_ERRNO` as the default action and all other syscall rules. The
kernel still enforces `CAP_SYS_CHROOT` in the caller's current user namespace;
the OCI worker has no such capability in the host user namespace. The helper
validates the source rule shape, output file permissions, derived profile and
SHA-256 digest. Tests cover the derivation and reject altered source rules.

The real-worker workflow now locates the Podman baseline profile first, then
derives the Chromium-compatible profile and passes that exact path to the OCI
worker. The workflow order is deliberate: it must never overwrite the derived
profile with the unmodified system profile.

The previous disposable run confirmed the complete dual-stack namespace,
nftables default-DROP policy, proxy-only direct-egress blocks, kernel cgroup
limits, OCI security options and independent host observation; it also
confirmed cleanup (`cleanup_confirmed=true`, no cleanup errors). Chromium
execution remains BLOCKED pending the new seccomp profile qualification.


### Workflow ordering correction

The first run of the derived-profile workflow stopped before host setup because
the profile-generation step had been placed before the step that exports the
system seccomp profile path. The workflow order is corrected: locate the
system-default profile first, then derive the owner-only Chromium profile, then
create the worker. That run produced no host qualification evidence.

The corrected profile-step ordering is queued for a new disposable-host run.


The first retry attempt after adding the profile generator stopped before
container creation because the workflow step order still referenced the
baseline seccomp path before it had been located. The workflow is corrected:
it now locates the Podman baseline, derives the private Chromium profile, then
provisions cgroup/image and passes the derived profile to the OCI runtime.
The failed attempt skipped all destructive provisioning steps.


## Chromium proxy-path diagnostic follow-up

The next real OCI run passed the user-namespace and `chroot` probe, retained all default-DROP and direct-egress negative checks, and no longer crashed in the zygote. Chromium itself exited successfully but did not return the expected `Example Domain` marker over the IPv4 proxy. The sanitized evidence confirmed both user-namespace checks true; container cleanup was confirmed with no cleanup errors.

Added bounded, redacted Chromium stdout/stderr diagnostics to the qualification evidence so the next run distinguishes proxy CONNECT failure, TLS failure, browser error page, and controlled-page content mismatch without recording credentials, email addresses or URL paths/query values. A regression test checks this redaction. A fresh disposable-host run is requested for this diagnostic revision.


The next diagnostic revision also records per-family proxy accept/reject counts and pinned dialed IPs before failing, plus bounded redacted Chromium stderr head/tail and known browser/proxy error markers. This distinguishes failure to reach the proxy from a rejected CONNECT or a browser-side TLS/navigation problem.


## Resolver-to-proxy diagnostic correction

The third real OCI attempt confirmed Chromium's user-namespace sandbox was healthy but the proxy recorded zero accepted connections, zero rejected CONNECT requests and zero upstream dials. The target resolver rule `MAP * ~NOTFOUND` did not explicitly exempt the numeric proxy endpoint. The qualification now uses `MAP * ~NOTFOUND, EXCLUDE <proxy-IP>` for both IPv4 and IPv6, keeping target DNS fail-closed while permitting resolution/connection to the numeric mandatory proxy. The same explicit proxy exemption is used in the proxy-outage test so that it actually reaches the stopped proxy instead of passing because proxy name resolution was blocked. Added regression tests for both address families.

This is a targeted hypothesis from the observed zero-connection telemetry; a new real-host run must confirm the result before any PASS is claimed.


## Chromium proxy configuration correction

Explicitly exempting the numeric proxy IP from host-resolver rules did not change the observed result: Chromium still made zero connections to the proxy. The qualification therefore removes the unnecessary host-resolver override and now passes a single explicit `http://<numeric-proxy-IP>:<port>` proxy URI for each address family. Chromium's HTTP proxy mode defers target hostname resolution to the proxy and uses CONNECT for HTTPS; the independent nftables default-DROP boundary continues to block direct DNS and direct TCP/UDP. The proxy outage test uses the same HTTP proxy URI with the listener stopped, so it tests actual proxy failure rather than a local resolver failure. IPv4/IPv6 URI formatting is covered by tests.

A fresh disposable-host qualification is required to verify this configuration; no real Chromium pass is claimed yet.


## Chromium proxy reachability preflight

The explicit HTTP proxy URI still resulted in zero browser connections to the listener, so the qualification now adds two isolated diagnostics before the network request: a numeric-IP TCP preflight from the unprivileged worker to the mandatory proxy, and a local `data:` URL `--dump-dom` smoke test. The first proves the namespace route/firewall can reach the proxy; the second proves the Chromium binary and stdout capture can render DOM without network access. Browser proxy connection counters are measured before/after the real HTTPS request. These checks separate container/network reachability from Chromium proxy configuration and page rendering. No sandbox or firewall relaxation is made.


The fourth/fifth diagnostic runs established that the namespace/chroot and default-DROP checks remain intact, but Chromium did not connect to the proxy. The latest retry adds an explicit TCP reachability probe from the unprivileged container, a local `data:` URL DOM smoke test, per-family proxy accept/reject/dial deltas, bounded redacted timeout stderr, and unique writable `/tmp` profiles with `--disable-dev-shm-usage`. This will distinguish browser startup/profile issues from network reachability and proxy selection. No browser sandbox bypass has been introduced.


## Chromium FD-ownership failure diagnosis

The latest sanitized timeout evidence exposed Chromium's `Crashing due to FD ownership violation` followed by network-service restart. Chromium's own `base/files/scoped_file_linux.cc` documents the FD-ownership guard, and `base/metrics/histogram_shared_memory.cc` documents a known case where utility processes receive a read-only histogram shared-memory FD and later attempt to acquire it as writable, triggering this exact ownership failure. The `PassHistogramSharedMemoryOnLaunch` feature is enabled for Linux in Chromium's field-trial configuration. The disposable worker now passes `--disable-features=PassHistogramSharedMemoryOnLaunch` to prevent that optional metrics-FD handoff; this does not change the browser sandbox, seccomp policy, or network restrictions. A regression test asserts the feature is disabled on all Chromium invocations and that `--no-sandbox` remains absent.

A fresh disposable OCI run is requested to verify the browser now starts and traverses the mandatory proxy. The previous run's cleanup was confirmed.


## Chromium inherited-descriptor isolation retry

Disabling the optional histogram shared-memory handoff did not eliminate the network-service FD-ownership crash. Chromium's upstream `ScopedFD` tracker crashes when the same descriptor ownership transition is attempted twice; this is a process-level descriptor-lifecycle invariant, not a reason to disable the browser sandbox. The worker qualification now launches Chromium through a tiny Python `exec` shim that closes inherited file descriptors above stdio (0/1/2) before `execvp` replaces the shim with Chromium. This narrows the browser's inherited descriptor set while preserving stdout/stderr capture, all Chromium sandbox flags, seccomp, namespaces, and network policy. A regression test checks that only stdio is preserved and `--no-sandbox` is absent.

This is a defensive hypothesis, not a proven fix. A new disposable-host run is requested; if Chromium still fails, the worker remains unqualified and dispatch stays disabled.
