# APAA-S09-C01-P60 — Protected signing-key lifecycle tests

**Date:** 2026-11-16  
**Scope:** Staged signer rotation, overlap, revocation, replay rejection and fail-closed anchor update tests.  
**Status:** Implementation and test commit created; exact-head CI must pass before P60 software-test closure.  
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
