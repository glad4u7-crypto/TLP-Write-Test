# APAA S09 C01 P43 — Exact-Head CI Reconciliation and External Gate Status

**Date:** 2026-11-16  
**Branch:** `feature/apaa-s09-c01-p16-oci-lifecycle`  
**PR:** #11 — Draft / Open / Unmerged  
**Scope:** repository/disposable-CI evidence only; no production qualification is claimed.

## 1. Verified repository checkpoint

The P36–P41 evidence reconciliation was committed as:

`996564865e4830ef3ae55ef335842cfd59052ff7`  
Message: `docs(security): reconcile P36-P41 evidence and C01 blockers`

GitHub returned four PR-triggered workflow runs for this exact commit. All four were completed with conclusion `success`:

| Workflow | Run ID | Result |
|---|---:|---|
| Agent Foundation CI | 43856322213 | PASS |
| Python Demo CI | 43856322121 | PASS |
| APAA P20 Rootless Podman Runtime Qualification | 43856322285 | PASS |
| APAA P23 Rootless Podman Executor Integration | 43856322289 | PASS |

This is an exact-commit CI result, not an inference from an earlier SHA. The combined commit-status endpoint returned no separate legacy status entries; the four workflow-run records above are the evidence used for this result.

## 2. What this CI result establishes

- Repository tests and workflow steps passed for the four workflows listed above on commit `996564865e4830ef3ae55ef335842cfd59052ff7`.
- P20/P23 results refer to disposable rootless Podman CI execution, not an owner-operated production host.
- Foundation CI does not establish physical Android qualification or live OIDC behavior.
- CI success does not establish production key custody, an independently administered durable monotonic anchor, real sink-side egress enforcement, or independent human review.

## 3. External qualification gate ledger

No external G1–G10 gate is promoted by this CI refresh.

| Gate | Required real-world proof | Status |
|---|---|---|
| G1 | Owner-approved disposable Linux host, isolation boundary, maintenance window and rollback plan | BLOCKED |
| G2 | Pinned runtime, local immutable image digest and owner-host preflight | BLOCKED |
| G3 | Least-privilege collector identity and effective privilege proof | BLOCKED |
| G4 | Out-of-band trust roots, protected signer, rotation, revocation and recovery | BLOCKED |
| G5 | Separately administered durable monotonic anchor with concurrency and restore/recovery proof | BLOCKED |
| G6 | Actual owner-host CREATE/INSPECT/ATTEST/START/STOP/REMOVE and negative identity/replay/tamper tests | BLOCKED |
| G7 | Actual worker/proxy enforcement with sink-side IPv4/IPv6, DNS, QUIC, WebSocket, alternate-interface and rebinding evidence | BLOCKED |
| G8 | Real daemon interruption, cancellation, signer/collector loss and bounded orphan-cleanup drills | BLOCKED |
| G9 | Physical Android sign-in/session/revocation/storage/lifecycle assessment and explicit Android control-plane boundary | BLOCKED |
| G10 | Independent reviewer verifies authenticity, host identity, key custody, anchor, sink observations, cleanup, owner access controls, two-user OIDC and exact digests | BLOCKED |

## 4. Required next external sequence

1. Owner explicitly approves a disposable Linux qualification host, isolation boundary, maintenance window and rollback/rebuild plan.
2. Operator confirms the locally available digest-pinned image and performs read-only preflight.
3. Provision trust out-of-band; establish protected signer custody and independently administered monotonic-anchor controls.
4. Execute the P27 G1–G10 runbook on that host. Record failures and skipped tests as FAIL/BLOCKED; never substitute synthetic CI evidence.
5. Verify the exact raw manifest signature and separately pinned reviewer attestation.
6. Have the owner independently establish reviewer identity/independence and explicitly accept the exact code SHA plus evidence-manifest digest.

If these prerequisites are not available, the gates remain BLOCKED. No simulation or documentation-only change can close them.

## 5. Release locks

- S09-C01: **OPEN / NOT COMPLETE**.
- S09-C02: **NOT STARTED**.
- PR #11: **Draft / Open / Unmerged**.
- Auto-Run: **OFF**.
- Browser/Worker: **OFF**.
- No merge, deployment, production activation, host/firewall mutation, real credential provisioning, paid API/service, payment, purchase, checkout, trading or money movement.
- Android remains the primary client direction; Android/Termux is not a hostile-code sandbox.

This document is a CI status reconciliation only. It does not grant qualification approval or authorize a release-state transition.
