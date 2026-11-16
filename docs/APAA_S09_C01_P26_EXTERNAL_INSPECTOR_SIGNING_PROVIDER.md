# APAA-S09-C01-P26 — External host-inspector signing provider boundary

**Status:** implementation committed; exact-head CI PASS on `8f1f41c17306e35cfea30e7b0b28115ef98c7dad`  
**Parent:** P24 signed trust bundle / P25 monotonic sequence gate  
**PR:** #11 (Draft/Open/Unmerged)  
**Production status:** NOT qualified; no host signing key provisioned

## Problem

The prior collector accepted a concrete `Ed25519PrivateKey` object in the APAA process. That is suitable for ephemeral tests, but it makes the collector API assume the private key is exportable into application memory. A production host key should preferably remain non-exportable in an independently protected TPM/HSM or authenticated signing service.

## Delivered

- Added the `InspectorSigningProvider` protocol to `core/browser_nftables.py`.
- The collector now depends on two narrow operations: return the 32-byte Ed25519 public key and sign canonical evidence bytes.
- The collector never requests or receives a private-key export.
- It validates public-key length, signing exceptions and exact 64-byte signature length; all provider errors fail closed.
- The resulting envelope is still verified locally against the provider's public key before returning.
- Updated offline tests to use an explicitly test-only wrapper around ephemeral Ed25519 keys.

## Production adapter contract

A separately reviewed adapter may implement this protocol using a non-exportable host key. Before acceptance it must demonstrate:
1. key generation/import and custody are performed outside the APAA worker/browser process;
2. signing requests are authenticated and authorized for the exact collector identity;
3. the private key cannot be exported through the adapter;
4. public-key fingerprint matches the out-of-band provisioned inspector key ID;
5. signing is rate-limited, audited and rejects malformed/oversized messages;
6. rotation/revocation and disaster recovery use the P24 signed-bundle process;
7. host evidence collection and signing execute under a least-privilege host identity;
8. key custody, hardware/service availability and restore/recovery behavior are independently qualified.

## Explicit limitation

This is an interface boundary, **not a TPM/HSM implementation**. No hardware device, cloud signing API, credentials, key, network endpoint or production host has been configured. A software-backed test signer does not prove non-exportability or host trust. The collector's host observation adapter and runtime/firewall truth still require live disposable-host qualification.

## Verification

P26 software implementation was verified on exact code commit `8f1f41c17306e35cfea30e7b0b28115ef98c7dad`. The latest branch head `c4d7019008dbee0b370b041005039058be3ef0dd` was independently re-run on 2026-11-16; all four relevant workflows completed successfully:

- Agent Foundation CI [#928 / run 43808910233](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43808910233) — PASS, including compile, dependency audit, foundation tests and disposable namespace egress job.
- Python Demo CI [#1003 / run 43808910205](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43808910205) — PASS.
- Rootless Podman Runtime Qualification [#57 / run 43808910362](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43808910362) — PASS.
- P23 Rootless Podman Executor Integration [#39 / run 43808910149](https://github.com/glad4u7-crypto/TLP-Write-Test/actions/runs/43808910149) — PASS.

The latest-head workflow runs verify the repository code and disposable GitHub-hosted Linux/Podman test environment. They do not establish production-host trust or hardware-backed key custody.

## Real-host security qualification — OPEN / BLOCKING

The following evidence must be collected on a separately controlled disposable Linux host before this checkpoint can be called production-host qualified:

1. **Host identity and collector:** install the reviewed collector under a dedicated least-privilege host account; bind its observations to the actual immutable OCI container ID, worker identity, launch-spec digest and network-namespace inode.
2. **Independent key trust:** create/provision the Ed25519 key outside the APAA worker/browser process; record the public-key fingerprint through an independent out-of-band channel; demonstrate the adapter cannot export the private key. A TPM/HSM is preferred, but any equivalent protected signer requires independent review.
3. **Trust lifecycle:** exercise P24 signed trust-bundle provisioning, P25 monotonic anti-rollback sequence, dual-key rotation, revocation, expired/unknown key rejection and recovery from a stale or unavailable trust anchor.
4. **End-to-end attestation gate:** use the real collector and signer through APAA's actual executor; valid evidence permits one START only; corrupted, replayed, stale, wrong-host, wrong-worker, wrong-runtime-ID or revoked-key evidence must block START and remove the stopped container.
5. **Host network truth:** independently verify effective nftables policy, direct IPv4/IPv6 egress denial, DNS restrictions, UDP/443, alternate-interface bypass resistance, proxy-only reachability and firewall hook precedence. Capture sanitized command output and evidence hashes.
6. **Failure and cleanup:** interrupt collector, signer, runtime inspection and executor at each lifecycle boundary; prove bounded STOP/REMOVE and zero orphan containers.
7. **Independent review:** retain host OS/kernel, Podman version, rootless/cgroup details, test timestamps, collector and signer versions, sanitized logs and artifact hashes; obtain a separate security review.

No host signing key, TPM/HSM, production collector service or real deployment host has been provisioned in this repository session. Do not substitute CI ephemeral keys, synthetic firewall claims or a disposable hosted runner for these requirements. Until the evidence above is independently produced and reviewed, **REAL-HOST SECURITY QUALIFICATION remains PENDING**, and OCI worker/browser execution remains disabled.

No deployment, firewall mutation, live browsing, worker activation, paid service, API key, merge or Auto-Run is authorized.
