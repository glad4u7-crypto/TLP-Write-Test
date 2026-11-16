# APAA-S09-C01-P27 — Real-host security qualification evidence pack

**Status:** operator-ready evidence specification drafted; no real-host qualification claimed  
**Parent:** P26 external inspector signing-provider boundary  
**Branch:** `feature/apaa-s09-c01-p16-oci-lifecycle`  
**PR:** #11 (Draft/Open/Unmerged)  
**Execution policy:** read-only preflight first; no worker/browser launch, firewall mutation, deployment, merge or Auto-Run

## Purpose

P26 separates the collector from private-key custody. P27 makes the remaining real-host qualification reproducible and reviewable without pretending that CI or synthetic evidence is a production host. This document defines the evidence package an owner-approved operator must collect on a disposable Linux host.

A completed evidence pack is not itself a security approval. An independent reviewer must verify authenticity, completeness, test isolation and the stated pass/fail results.

## Hard prerequisites

Do not begin runtime tests until all are true:

1. The owner explicitly approves a disposable Linux host, maintenance window, exact runtime and pinned version.
2. The host is isolated from production data and has a rollback/rebuild plan.
3. A local digest-pinned test image is already available; do not pull an unreviewed image during qualification.
4. A dedicated least-privilege host identity and collector package have been reviewed.
5. The trust root and inspector key are provisioned out-of-band; record public fingerprints only. Never put private keys, tokens, environment dumps or credentials in evidence.
6. A separately administered monotonic anchor has documented CAS, persistence and backup/restore anti-rollback behavior.
7. The approved proxy endpoint and expected network policy are documented.
8. A stop condition and human operator are present for every host-mutating test.

If any prerequisite is missing, mark the corresponding gate BLOCKED and stop. Do not substitute CI-generated keys, in-memory anchors, mocks or guessed host facts.

## Evidence directory and manifest

Create a new evidence directory on the disposable host with restrictive permissions. Use a unique run ID and UTC timestamps. The evidence bundle should contain:

- `manifest.json`: schema version, run ID, operator, approval reference, host alias, start/end UTC, runtime name/version, collector/signer versions, test image digest, proxy policy ID and per-file SHA-256.
- `host-preflight.json`: OS/kernel, architecture, non-sensitive runtime info, rootless status, cgroup mode and tool versions.
- `identity.json`: dedicated service account UID/GID, collector binary/package digest and effective privilege review.
- `trust.json`: public root fingerprint, inspector public-key fingerprint, issuer/key IDs, signed bundle digest/sequence/validity and monotonic-anchor backend identity. Public data only.
- `lifecycle.json`: immutable container ID, image digest, launch-spec digest, network namespace inode, timestamps and CREATE/INSPECT/ATTEST/START/STOP/REMOVE results.
- `egress.json`: effective namespace nftables ruleset digest, exact approved proxy tuple, direct TCP/DNS TCP+UDP/UDP-443/IPv6/alternate-interface probe outcomes and sink-side observations.
- `negative-tests.json`: stale, replayed, wrong-host, wrong-worker, wrong-container, wrong-launch-digest, unknown/revoked-key and malformed-signature rejection outcomes.
- `failure-cleanup.json`: injected interruption point, bounded stop/remove deadlines, daemon availability and final orphan-container inventory.
- `anchor-recovery.json`: restart, concurrent CAS, backup/restore and rollback rejection evidence.
- `review.json`: independent reviewer, reviewed manifest digest, findings, exceptions and signed disposition.

The manifest must hash every evidence file except itself. Sign the final manifest digest using the approved evidence-signing identity. Store the package in the owner's approved restricted evidence location; do not commit raw host evidence or identifiers to this public/private code repository.

## Phase A — read-only preflight

The existing P20 preflight command is read-only. Run it only with the owner-approved runtime and exact version pin:

```bash
python -m scripts.qualify_oci_runtime_preflight --runtime podman --pinned-version <OWNER_APPROVED_VERSION>
```

Capture the exit code and sanitized output. Also capture the minimum facts needed to identify the environment, such as OS/kernel, `id`, runtime version and rootless/cgroup status. Do not capture environment variables, process command lines containing secrets, registry credentials or unrelated inventory.

A passing preflight means only that the observed runtime matches the preflight contract. It does not authorize or prove a container lifecycle.

## Phase B — trust and signer qualification

- Confirm the root public-key fingerprint through two independent out-of-band channels.
- Verify the signed trust bundle and issuer identity.
- Demonstrate sequence advancement is atomic and durable before success is returned.
- Restart the control plane and verify the accepted sequence remains unchanged.
- Restore a deliberately older test snapshot in the isolated test environment and prove the anchor refuses rollback.
- Test concurrent writers, unavailable anchor, stale bundle, unknown key, revoked key, expired key and overlap rotation.
- Demonstrate the signer cannot export private key material and that only the approved collector identity can request signatures.

Never export or attach private key material. If a TPM/HSM or equivalent protected signer is unavailable, mark protected key custody BLOCKED.

## Phase C — real daemon lifecycle and attestation

Using only the reviewed APAA executor and approved local image:

1. CREATE exactly one stopped container with the expected immutable image digest and hardened configuration.
2. INSPECT and independently compare immutable ID, launch-spec digest, network, read-only rootfs, capability drop, no-new-privileges and seccomp.
3. Collect a fresh challenge-bound host snapshot and sign it through the external provider.
4. Verify the signature and all host/container/worker/network bindings before START.
5. Prove valid evidence permits exactly one START.
6. Prove stale, replayed, tampered, wrong-host, wrong-worker, wrong-container, wrong-network-namespace, wrong-launch-spec and revoked-key evidence prevents START.
7. Exercise cancellation, timeout, collector loss, signer loss and daemon interruption at each lifecycle boundary.
8. Verify bounded STOP/REMOVE and zero remaining qualification containers after every path.

Do not run these steps on a production host or with production workloads.

## Phase D — network enforcement

Verify the effective worker namespace policy, not merely the intended configuration. The approved proxy endpoint must be the only allowed egress destination and protocol/port tuple. Test direct IPv4 and IPv6, DNS TCP and UDP, UDP/443, QUIC, alternate interfaces, unexpected routes and firewall hook precedence. Include sink-side observations so a local client error is not mistaken for network denial.

Any unexplained packet, alternate route, unknown nftables object, missing observation or incomplete probe is FAIL/BLOCKED. Do not change host firewall rules as part of this evidence collection unless a separate change plan is approved; use an isolated disposable namespace/host and record the exact approved change separately.

## Phase E — evidence integrity and review

- Hash every artifact and validate the manifest.
- Remove secrets and personal data before export; preserve enough context for independent reproduction.
- Record every skipped test as SKIPPED with reason; skipped is never PASS.
- Have a reviewer independent of the implementer verify the host identity, key custody, test logs, sink observations, cleanup and manifest signature.
- Record findings and remediation; rerun the complete affected gate on the final code commit after any change.

## Result vocabulary

Use only these values per gate:

- **PASS:** observed on the approved real host, artifacts complete and independently reviewed.
- **FAIL:** a required assertion failed.
- **BLOCKED:** prerequisite, host, key, anchor, permission or evidence unavailable.
- **SKIPPED:** explicitly not run; never counts toward completion.

The overall real-host qualification is PASS only if every mandatory gate is PASS and the independent reviewer approves the exact code commit and evidence manifest. Otherwise it remains OPEN.

## Current repository evidence

As of commit `1230e97fd8f83d5efc154bf18bf7cabc9c4a35c9`, the following exact-head workflows completed successfully:

- Agent Foundation CI #929 — PASS.
- Python Demo CI #1004 — PASS.
- P20 Rootless Podman Runtime Qualification #58 — PASS.
- P23 Rootless Podman Executor Integration #40 — PASS.

These are disposable CI checks. They do not satisfy any real-host, production key-custody, independent monotonic-anchor, full topology or Android/Termux gate in this evidence pack.

## Exit criteria

P27 documentation is ready for operator use when the pack is reviewed for completeness. P27 does not close C01. C01 remains OPEN until the owner-approved real-host evidence package is collected, independently reviewed and linked from a restricted qualification record. Keep browser and worker execution disabled until all preceding operational gates pass.

No host is provisioned by this document. No firewall mutation, deployment, live browsing, worker activation, paid provider, API key, merge or Auto-Run is authorized.


## P27 manifest integrity validator

The repository now includes a standard-library-only validator:

```bash
python -m scripts.validate_apaa_p27_evidence <EVIDENCE_DIRECTORY>
```

The directory must contain `manifest.json` and all nine required artifacts listed above. The manifest uses schema version 1, UTC start/end timestamps, a SHA-256 digest-pinned test image, and a path-to-SHA-256 map for every artifact except the manifest itself. The validator rejects missing/unlisted files, symlinks, path traversal, mutable image tags, invalid timestamps and digest mismatches.

A successful result means **artifact integrity only**. It explicitly reports `authenticity=NOT_CHECKED` and `host_qualification=NOT_ASSESSED`; it does not verify the detached signature, prove host identity, or turn BLOCKED/SKIPPED observations into PASS. Independent signature verification and review remain mandatory.


## Detached manifest signature verification

The P27 validator supports Ed25519 verification of the exact raw bytes of manifest.json. The detached signature is canonical base64 text in a sidecar stored outside the evidence directory. The raw 32-byte public key is also stored outside that directory and must be provisioned independently. Supply the independently pinned SHA-256 fingerprint:

```bash
python -m scripts.validate_apaa_p27_evidence EVIDENCE_DIRECTORY \
  --signature /secure/evidence/manifest.sig \
  --public-key /secure/trust/evidence-signing.pub \
  --expected-key-sha256 OUT_OF_BAND_PINNED_SHA256
```

A successful check reports authenticity=VERIFIED_ED25519 and the signer fingerprint. Without all trust inputs, authenticity remains NOT_CHECKED. This does not prove that the key belongs to an approved real host, that the signer is hardware-protected, or that observations are truthful. Those remain separate provisioning and independent-review gates. Test signing keys are ephemeral and test-only.
