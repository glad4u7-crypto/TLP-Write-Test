# APAA-S09-C01-P60 — Protected signing-key lifecycle tests

**Date:** 2026-11-16  
**Scope:** Staged signer rotation, overlap, revocation, replay rejection and fail-closed anchor update tests.  
**Status:** Software lifecycle test scope verified by exact-commit CI (4/4 PASS on both the test commit and documentation commit); physical-token qualification remains BLOCKED.

**Verified commits:** test `b1cabf206b2666cc1c4d4892544fd013010e4f3e`; documentation `66130651790b2e87f23d571ee6d02b0082bf905a`.

**CI evidence:** Agent Foundation CI #1185/#1186, Python Demo CI #1274/#1275, P20 Rootless Podman Qualification #314/#315, and P23 Executor Integration #296/#297 all completed successfully on the respective commits (4/4 each).  
**Production HSM status:** NOT QUALIFIED. No physical token was accessed or modified.

## Changes

Added `tests/test_apaa_p60_pkcs11_key_lifecycle.py` to exercise the existing signed inspector trust-bundle and monotonic sequence interfaces.

The tests cover:

1. **Initial key activation:** accept the current signer under a signed trust bundle.
2. **Staged rotation:** publish a new public key while the old key remains valid for a bounded overlap.
3. **Dual verification:** verify signatures from both keys during the explicit overlap window.
4. **Revocation:** publish a later signed bundle marking the old key revoked; confirm the new key remains active and the old key is rejected.
5. **Replay resistance:** reject the earlier overlap bundle after the sequence high-water mark has advanced.
6. **CAS failure:** reject a rotation if the monotonic anchor refuses the compare-and-advance operation; do not expose an accepted registry.
7. **Tamper resistance:** reject a modified revocation bundle and leave the anchor unchanged.

All test signing keys and the in-memory anchor are ephemeral test fixtures. They are not production keys or a production anchor.

## Security interpretation

These tests verify the software trust-policy lifecycle. They do **not** provision, rotate, delete or revoke an object inside a physical PKCS#11 HSM. The current provisioner deliberately refuses to overwrite an existing key ID and does not delete old keys. A real token rotation therefore remains a controlled ceremony:

- independently identify the physical token and firmware;
- generate a fresh key under a distinct object ID inside the approved token;
- verify its public fingerprint out of band;
- publish a signed trust bundle with an explicit overlap;
- verify new-key signing on the actual token;
- publish a later bundle revoking the old key;
- confirm old signatures are rejected by every relying verifier;
- retain vendor-approved recovery material and independently review custody.

No software-token result, fake PKCS#11 provider, CI result or mechanism self-report is evidence of physical HSM identity or non-extractability.

## Safety

No token, PIN, private key, production credential, paid service, host or deployment was used. No key deletion was attempted. PR #11 remains Draft/Open/Unmerged; Auto-Run OFF; Worker/Browser disabled; no merge, deployment or C02 start.

## P60 acceptance

P60 software lifecycle tests are accepted only after exact-head CI is green. Physical-token lifecycle qualification remains BLOCKED until a compatible owner-approved device is available and independently verified. C01 remains OPEN.


## 6. Latest branch-head regression verification

The P60 tests remain included in the current branch head `c5908fe926c1e3ba37b446d26fe765652d6e4fdb`. On that exact head, Agent Foundation CI #1214, Python Demo CI #1303, P20 #343 and P23 #325 all completed successfully (4/4 PASS); each pytest job reported 1,348 passed and 9 skipped. This is regression evidence for the current tree, not a physical-token test. P60 software lifecycle scope remains COMPLETE; real hardware key rotation/revocation/recovery remains BLOCKED.
