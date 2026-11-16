# APAA-S09-C01-P54 — Explicit PKCS#11 Ed25519 key provisioning

**Status:** provisioning utility and fake-token tests committed; exact-head CI pending.  
**Physical token:** NOT CONNECTED / NOT QUALIFIED.

## Delivered

Added `scripts/provision_apaa_pkcs11_signer.py`:

- Requires an explicit `--confirm-create` flag before any token write.
- Prompts for the user PIN without echo; never accepts PIN on command line or from environment.
- Requires an absolute, regular, non-symlink PKCS#11 module path and validates token label, key ID, label and PIN length before opening a write session.
- Refuses to create a key if any existing token object already uses the requested object ID.
- Generates an Ed25519 keypair inside the token using `CKK_EC_EDWARDS` / `CKM_EC_EDWARDS_KEY_PAIR_GEN`.
- Requests a persistent token object with private-key attributes `CKA_PRIVATE=true`, `CKA_SENSITIVE=true`, `CKA_EXTRACTABLE=false`, `CKA_SIGN=true`; public key is verify-enabled.
- Does not import or export private key bytes. It never deletes an existing key or performs rotation.
- After creation, reopens the token through the P50 signer adapter, checks `CKA_ALWAYS_SENSITIVE` and `CKA_NEVER_EXTRACTABLE` as well as other required attributes, signs a random challenge and verifies it locally.
- Emits a sanitized public-key fingerprint and explicitly marks hardware identity, rotation/revocation, backup/restore and independent review as not yet qualified.

Added fake-token tests for mandatory confirmation, hidden PIN handling, non-extractable attribute requests, successful self-test and refusal to overwrite an existing key ID.

## Operator use

Install the optional Python binding and the vendor's PKCS#11 module, then run:

```bash
python -m pip install -r requirements-pkcs11.txt
python scripts/provision_apaa_pkcs11_signer.py \
  --module /absolute/path/to/vendor-pkcs11.so \
  --token-label APAA-INSPECTOR \
  --key-id inspector-001 \
  --confirm-create
```

Run only against the intended token after confirming its identity and backing up the vendor's approved recovery material. The key ID is never overwritten. To rotate, provision a distinct new key ID and follow a separately approved trust-bundle update/revocation ceremony; this utility does not delete the old key.

## Security boundary

The script can request non-extractable attributes and verify the token's reported flags. It cannot prove that the module is connected to a physical HSM rather than SoftHSM, that the vendor firmware is genuine, that PIN custody is independent, or that the token survives backup/restore and disaster recovery. A software token can pass the fake or local self-test but is not hardware protection.

No actual token, PIN, key, HSM, paid service, host or deployment was used here. Protected Signing Key production qualification remains OPEN pending real-token execution, out-of-band fingerprint pinning, key custody, lifecycle testing and independent review.
