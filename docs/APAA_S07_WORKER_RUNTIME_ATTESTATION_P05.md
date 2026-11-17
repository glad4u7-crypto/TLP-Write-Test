# APAA S07 — P05 Worker Deployment Adapter and Runtime Security Attestation

**Checkpoint:** APAA-S07-C01-P05  
**Disposition:** INERT LAUNCH CONTRACT + OFFLINE ATTESTATION VALIDATOR  
**Branch:** feature/approval-ui-e2e-p06  
**PR:** #5 — keep Open + Draft + unmerged  
**Worker deployment:** NOT PERFORMED  
**Browser process:** NOT STARTED  
**Proxy / firewall:** NOT DEPLOYED  
**Browser execution:** DISABLED

## 1. Objective

P05 bridges the P04 declarative isolation policy to a future deployment integration without creating a worker or activating browser execution. It defines an immutable launch contract and a strict pre-start attestation schema. A trusted runtime/host inspector must independently collect the effective runtime and firewall facts; the validator rejects missing, stale, altered or unsafe evidence.

## 2. Implementation

### core/browser_runtime.py

- `build_worker_launch_spec(profile)` accepts only the P04 profile type and independently revalidates its values.
- Produces an immutable, inert `WorkerLaunchSpec` containing non-root UID/GID, read-only root, no-new-privileges, drop-all capabilities, isolated namespace requirements, no host/secret mounts, ephemeral writable paths, disabled persistent profile/CDP, proxy-only egress, resource caps, mandatory seccomp evidence and a required pre-start state.
- A stable SHA-256 digest binds the runtime evidence to the exact launch specification.
- `verify_prestart_attestation(spec, raw)` enforces a closed schema, pinned SHA-256 image digest, runtime/worker/attestor identifiers, evidence digest, freshness window, exact launch-spec binding, exact UID/GID and resource limits.
- It requires the worker to remain in the `created` state with `process_started=false`.
- It checks effective capabilities are empty; required namespaces are isolated; host and secret mounts are absent; seccomp, no-new-privileges, network namespace and host firewall evidence are present; default-deny egress allows only the configured internal proxy; direct DNS egress is blocked and proxy-side DNS is exclusive.
- Any unknown field, missing field, mismatch, stale evidence or failed boolean check raises `RuntimeAttestationError`.

### tests/test_browser_runtime.py

Offline tests cover launch-spec creation, P04 profile revalidation, forged spec rejection, exact spec digest binding, complete attestation acceptance, schema drift, runtime started/running rejection, privilege/capability/mount/namespace escapes, egress and DNS bypass, proxy mismatch, resource/identity drift, image digest pinning, stale/future timestamps, malformed evidence and absence of socket/process activity.

## 3. Trust boundary and limitations

The attestation validator does not inspect the kernel, container runtime, namespaces, cgroups, mount table, seccomp state, firewall, routing table or proxy. It does not authenticate the inspector or independently prove that the evidence digest corresponds to genuine host observations. The mapping must be delivered by a separately trusted, authenticated inspector running outside the worker's trust boundary. The evidence digest is an integrity identifier, not a signature or proof by itself.

The launch specification is inert data. It is not an OCI bundle, container command or executable deployment adapter. No Docker/Podman/containerd API, privileged helper, root operation, firewall command, network request, DNS lookup, socket, browser binary, Playwright dependency, worker process or browser handler was introduced.

Before any future launch, an independently reviewed deployment adapter must:
1. translate the contract into the selected runtime's supported isolation controls;
2. configure a dedicated network namespace and host-enforced default-deny firewall;
3. permit only the fixed proxy address and port, with direct DNS/UDP/QUIC and other egress blocked;
4. collect effective runtime and host-firewall observations from a trusted host-side inspector;
5. bind fresh evidence to the exact launch spec and immutable image digest;
6. verify the attestation while the worker is still created and before starting its process;
7. fail closed on inspector failure, stale evidence, configuration drift or firewall uncertainty;
8. independently test packet-level egress and DNS leakage, proxy-side DNS resolution, IP pinning, TLS validation, cancellation and cleanup.

## 4. Security invariants retained

- Auto-Run remains OFF; default permission remains Ask First.
- No payment, purchase, checkout, trading, investment order, money movement or financial transaction.
- No paid/external provider, API key, billable service or automatic fallback.
- No shell, arbitrary filesystem, email, credential, cookie, token, clipboard, Android device-control or unrestricted network handler.
- No browser handler registered in ExecutionGateway.
- No new CI workflow; the existing two workflows remain the verification gate.
- PR #5 remains Open + Draft + unmerged. No merge or deployment.

## 5. P05 disposition

P05 implementation is limited to an inert launch contract and offline pre-start attestation validator. Passing unit tests can verify the contract logic only; it cannot establish that an operating-system sandbox, firewall or proxy is deployed or effective. Browser execution remains disabled and deployment remains a separate authorization gate.
