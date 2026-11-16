# APAA-S09-C01-P50 — PKCS#11 Ed25519 protected signer adapter

**Status:** adapter and mocked contract tests committed; exact-head CI pending.  
**Production hardware status:** NOT QUALIFIED.  
**PR:** #11 Draft/Open/Unmerged.

## Delivered

Added `core/pkcs11_ed25519_signer.py` implementing the existing `InspectorSigningProvider` interface through a PKCS#11 token:

- Requires a PKCS#11 module at an explicit absolute regular-file path, token label, object ID and caller-supplied PIN.
- Looks up an Ed25519 public-key object and checks the Ed25519 curve OID before returning the 32-byte public key.
- Looks up the corresponding private-key object and requests `CKM_EDDSA` signing; private-key bytes are never requested or exported.
- Before each signing operation, requires the token to report `CKA_SENSITIVE=true`, `CKA_EXTRACTABLE=false`, `CKA_ALWAYS_SENSITIVE=true`, `CKA_NEVER_EXTRACTABLE=true` and `CKA_SIGN=true`; unsupported or weaker token attributes fail closed.
- Bounds message size and validates the returned 64-byte signature.
- PIN is not accepted from environment variables or command-line arguments and is not written to disk/logs by this adapter.
- Fails closed for missing token, missing key, unsupported curve/mechanism, invalid point, malformed signature and module errors.
- Does not provision, generate, rotate or delete token keys; those ceremonies remain under separate token administration.

Added `tests/test_pkcs11_ed25519_signer.py` with an injected PKCS#11 contract fake to test public-key extraction, signature verification, absence of a private-key export API, bounds, invalid module, unavailable-token failure and rejection of an extractable private key.

## Deployment requirements

The configured token must support PKCS#11 `CKK_EC_EDWARDS` and `CKM_EDDSA`. Many TPM 2.0 devices expose ECDSA/RSA but not Ed25519; they cannot be used with this adapter without changing the APAA signature algorithm and verifier as a separately reviewed migration.

A production rollout requires:
1. A physical HSM/token or independently protected signing service that supports Ed25519 PKCS#11 mechanisms.
2. Key generation inside that token, with the private key marked sensitive and non-extractable; no import of plaintext private keys.
3. Separate PIN custody and a least-privilege service identity; PIN delivery through a protected broker, not a source file, command line or environment dump.
4. Out-of-band public-key fingerprint pinning and binding of token serial, slot, label and key ID to the approved inspector identity.
5. Tested key rotation/revocation, token loss, backup/recovery, audit and access revocation.
6. Independent review and live signing/verification on the actual token.

Mocked tests prove the adapter contract only. They do not prove the token, module, PIN custody, non-extractability or physical HSM security. A software PKCS#11 emulator/soft token is not equivalent to hardware protection.

## Status

P48 encrypted software signer and P50 PKCS#11 adapter are development/integration code. P50 provides a concrete path to a real Ed25519-capable HSM without moving private-key bytes into APAA. The TPM/HSM production gate remains OPEN until a real compatible token is provisioned and independently qualified. No hardware, credential, paid provider, production host or deployment is used by this commit.
