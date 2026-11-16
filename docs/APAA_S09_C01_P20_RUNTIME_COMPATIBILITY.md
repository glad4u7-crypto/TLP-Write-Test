# APAA-S09-C01-P20 — OCI runtime compatibility and CI qualification

**Repository:** `glad4u7-crypto/TLP-Write-Test`  
**Branch:** `feature/apaa-s09-c01-p16-oci-lifecycle`  
**Verified implementation head:** `c8104c4ab49ceaaa378d2fa3c6dda61468d1bb29`  
**PR:** [#11 — Gated OCI Worker and Proxy Isolation](https://github.com/glad4u7-crypto/TLP-Write-Test/pull/11)  
**Status:** Implementation + repository CI verified; real daemon qualification remains pending.  
**Release posture:** Draft only; no merge, deployment, live browser enablement or production claim.

## Delivered in P20

- `core/oci_runtime_compat.py`: pure, fail-closed compatibility assessment for Docker or Podman against an exact operator-pinned version, rootless mode, cgroup v2, lifecycle CLI contract, read-only root filesystem, dropped capabilities and seccomp.
- `core/oci_runtime_probe.py`: bounded read-only version, info and CLI-help probes. It does not create, start or modify containers.
- `core/oci_inspect_normalizer.py`: strict Docker/Podman inspect normalization. It requires one stopped/created container, the digest-pinned image, the exact approved network, read-only rootfs, all capabilities dropped, no-new-privileges and seccomp; mismatches fail closed.
- The normalized inspect result is integrated into the gated OCI worker executor.
- Positive and negative tests cover supported Docker/Podman shapes, version pin mismatch, rootless/cgroup/seccomp requirements and inspect-policy drift.

## Exact-head CI evidence

The exact implementation head `c8104c4ab49ceaaa378d2fa3c6dda61468d1bb29` has completed both required workflows:

| Workflow | Run | Result |
|---|---:|---|
| Agent Foundation CI | [43795182589](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43795182589) | PASS |
| Python Demo CI | [43795182578](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43795182578) | PASS |

Observed Agent Foundation CI details:
- Python 3.12 compile check: PASS.
- Dependency audit: **No known vulnerabilities found**.
- Full test suite: **992 passed in 14.64s**.
- Python Demo CI test suite and demo smoke step: PASS.

## Qualification boundaries — not yet passed

The following are explicitly **NOT QUALIFIED** by the above CI:

1. Real rootless Docker daemon qualification.
2. Real rootless Podman daemon qualification.
3. Runtime-created container inspect schema against the pinned runtime versions.
4. CREATE → INSPECT → signed ATTEST → START → STOP/REMOVE using a disposable real daemon.
5. Timeout, cancellation, daemon interruption and bounded cleanup drills.
6. Runtime network namespace inspection and proof that no host port is published.
7. Live host firewall hook precedence and direct TCP, DNS TCP/UDP, UDP/443 (QUIC), IPv6 and alternate-interface bypass tests.
8. Trusted host collector installation, out-of-band Ed25519 key provisioning, rotation/revocation and recovery.
9. Android/Termux OCI support.

### Important CI interpretation

The workflow job titled **Disposable Linux egress namespace qualification** completed successfully, but its executed step was **Report hosted-runner qualification limitation**. That step reports the qualification as skipped because the hosted runner lacks the required namespace/veth/nftables/IPv6 capabilities. Therefore, this green job is **not** evidence of live egress isolation. It must not be described as an operational PASS.

The P20 runtime probe tests use injected command runners. They prove deterministic parsing and fail-closed policy behavior, not a real Docker/Podman daemon.

## Acceptance gate for operational P20

P20 operational qualification remains blocked until a disposable Linux host/runner with a verified rootless Docker and/or Podman daemon can:

- record exact runtime version, rootless status, cgroup version and security options;
- run the read-only probe against the operator-pinned version;
- create a disposable worker from a locally available digest-pinned test image using the approved OCI plan;
- inspect and normalize the actual stopped container configuration;
- demonstrate that failed/mismatched attestation prevents START;
- demonstrate successful START only after valid single-use signed evidence;
- execute bounded timeout/cancellation and confirm cleanup without orphaned workers;
- remove all test resources and preserve host firewall state;
- run the live egress bypass matrix in an isolated disposable namespace.

No production firewall or network should be changed for qualification. If any required control cannot be proven, the runtime must remain disabled.

## Safety

Free-only. No API keys, paid providers, payments, purchases, checkout, trading or money movement. Auto-Run remains disabled. The browser/worker is not enabled by this report. No merge or deployment is authorized.
