# APAA-S09-C01-P16 — OCI lifecycle executor (gated)

## Delivered
- `core/oci_worker_executor.py` adds a direct argv-only command runner using `subprocess.run(shell=False)`, binary lookup, bounded timeout and captured output.
- Lifecycle order is CREATE (stopped) → INSPECT (effective configuration) → ATTEST (Ed25519 signed runtime + exact proxy-only nftables evidence) → START.
- Inspection checks the stopped state, immutable image reference, named network, read-only root, dropped capabilities, non-privileged host namespace settings, no-new-privileges and seccomp.
- A launch-spec digest mismatch blocks before any command. Stateless attestation is refused; signed evidence must bind the exact inspected OCI container ID, planned worker name and launch-spec digest, and its durable challenge must be consumed once before start. Any create/inspect/attestation/start error blocks and attempts cleanup. No alternate browser/network fallback exists.
- Tests use an injected fake command runner; no host command, container, network or firewall is run by CI tests.

## Explicit limits
- No host command was executed during implementation.
- Successful worker start now requires the durable tenant-bound InspectorEvidenceControlPlane and one-time SQLite challenge consumption. The evidence supplier, signing-key provisioning, trusted host collector, firewall policy deployment and disposable-Linux Docker/Podman compatibility matrix remain external qualification requirements.
- The executor is not enabled by the Streamlit app and live browsing remains disabled.
- Android/Termux does not provide a qualified OCI runtime path; this checkpoint does not claim Android runtime support.
- Docker and Podman inspect output varies by version; only the normalized schema exercised by tests is currently accepted. Version-pinned host integration is still required.

## Verification status
Implementation and tests are committed to a draft feature branch. Mark P16 CI-verified only after exact-head repository workflows pass. No merge, deployment, payment, purchase, paid provider, API key, Auto-Run, or production enablement.
