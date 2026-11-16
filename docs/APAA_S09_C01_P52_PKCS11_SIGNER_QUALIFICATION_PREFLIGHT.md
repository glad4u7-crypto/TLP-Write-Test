# APAA-S09-C01-P52 — PKCS#11 signer qualification preflight

**Status:** read-only self-test script and tests committed; exact-head CI pending.  
**Hardware qualification:** NOT CLAIMED.

## Delivered

Added `scripts/qualify_apaa_pkcs11_signer.py`:

- Accepts only module path, token label and key ID as command-line arguments.
- Prompts for the PKCS#11 PIN with hidden terminal input; it is not accepted on the command line or written to output.
- Uses the P50 PKCS#11 adapter, which requires token-reported `CKA_SENSITIVE`, `CKA_EXTRACTABLE`, `CKA_ALWAYS_SENSITIVE`, `CKA_NEVER_EXTRACTABLE` and `CKA_SIGN` attributes.
- Obtains the public key, signs a fresh random challenge, and verifies the Ed25519 signature locally.
- Emits a sanitized JSON self-test result with public-key fingerprint.
- Explicitly reports hardware identity as NOT_INDEPENDENTLY_VERIFIED, backup/restore qualification as NOT_ASSESSED and independent review as PENDING.
- Does not provision, import, rotate, delete or export any key.

Added tests for successful self-test reporting and fail-closed behavior without PIN or provider diagnostic leakage.

## Operator use

Install the optional Python binding and a vendor-compatible PKCS#11 shared library, then provision an Ed25519 key inside a supported token:

```bash
python -m pip install -r requirements-pkcs11.txt
```

The token vendor's PKCS#11 module must be installed separately.

```bash
python scripts/qualify_apaa_pkcs11_signer.py --module /absolute/path/to/pkcs11.so --token-label APAA-INSPECTOR --key-id inspector-001
```

This script is read-only and does not establish that a token is a physical HSM. The operator must separately verify vendor/model/serial, hardware security claims, key generation ceremony, non-extractability policy, PIN custody, access controls, audit, backup/recovery, rotation/revocation and independent reviewer identity. A SoftHSM token can pass the self-test and still is not hardware protection.

No token, PIN, hardware device, external provider or deployment was used in this repository session. The Protected Signing Key production gate remains OPEN until an actual independently administered protected token is qualified.
