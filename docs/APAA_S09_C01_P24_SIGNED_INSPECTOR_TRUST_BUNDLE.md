# APAA-S09-C01-P24 — Signed out-of-band inspector trust bundle

**Status:** implementation added; exact-head CI verification pending  
**Branch:** `feature/apaa-s09-c01-p16-oci-lifecycle`  
**PR:** #11 (Draft/Open/Unmerged)  
**Deployment / merge / Auto-Run:** not authorized

## Delivered in P24

- Added `core/inspector_trust_bundle.py`, which accepts a strict UTF-8 JSON trust bundle and verifies its Ed25519 signature against a separately pinned root public key.
- The pinned issuer ID and root public key are supplied by trusted control-plane configuration; values inside the bundle cannot replace the trust anchor.
- The signed payload has a schema version, monotonically increasing sequence, issue/expiry timestamps and up to 64 inspector public-key records.
- Key records are passed through the existing immutable `InspectorPublicKeyRegistry`, preserving validity windows, planned overlap rotation, explicit revocation, duplicate-ID/key rejection and active-key-only resolution.
- Duplicate JSON keys, unknown fields, malformed base64, invalid signatures, wrong issuer, expired/future bundles, sequence rollback, malformed records and bundles with no active key fail closed.
- The loader returns the verified sequence. The caller must atomically persist the highest accepted sequence in durable control-plane state and pass it back as `minimum_sequence` after restart. This module deliberately does not claim to provide rollback-resistant storage.

## Trust model and operational procedure

1. Generate the root signing key on an independently controlled offline system or HSM; never in this repository, CI, worker or Android client.
2. Provision the root Ed25519 public key and issuer ID to the control plane through an authenticated out-of-band channel, with independent verification (for example, two-person fingerprint confirmation).
3. Build and sign a versioned bundle containing inspector public keys only. Private inspector keys remain isolated on the trusted host collector.
4. Publish the bundle through a protected configuration channel. The control plane verifies the signature, issuer, validity and sequence before accepting the registry.
5. Atomically persist the accepted sequence in rollback-protected control-plane storage. Reject any lower sequence after restart or restore.
6. Rotate with a bounded overlap by publishing old and new keys together; after the overlap, expire the old key. Emergency revocation publishes the key with `revoked=true` at a higher sequence.
7. Record bundle digest, sequence, approver identities and activation/revocation events in the independent audit system. Recovery requires a separately approved higher-sequence bundle; do not reset the sequence to recover.

## Verification

Offline tests use ephemeral synthetic Ed25519 keys only in test memory. They cover signature validity/tampering, pinned-root mismatch, issuer mismatch, sequence rollback, validity windows, revocation, duplicate JSON keys, unknown fields and malformed public-key encoding.

The P24 implementation is not yet connected to production configuration or a rollback-protected sequence store. No production root key, host private key, secret, credential or signing material is present in the repository. CI must pass on the exact P24 commit before marking this checkpoint verified.

## Remaining release gates

- Integrate this loader with an authenticated, independently administered control-plane configuration source.
- Implement durable, atomic, rollback-resistant accepted-sequence storage and restore/recovery tests.
- Establish named key custodians, dual-control approval, offline root-key backup and emergency revocation procedure.
- Connect the existing Linux host collector to protected host-side signing-key custody and validate actual host/network observations.
- Run a separately controlled live-host qualification; CI-generated keys and synthetic evidence are not production trust evidence.

No worker start, browser action, firewall mutation, deployment, merge, payment, purchase, trading, paid provider or API key is enabled by P24.
