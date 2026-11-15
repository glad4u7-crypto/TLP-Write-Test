# Verification — APAA-S08-C02-P04

## Added security primitives
- Action/payload validation: normalized action identifier, finite JSON only, max 64 KiB, max nesting depth 12, detached validated copy.
- Versioned action policy registry; missing or disabled policy denies.
- Persistent scoped consent ledger with expiry and revocation.
- SQLite online backup, integrity check, HMAC-SHA256 external signature, verified restore.

## Test matrix
15 tests: validation bounds/injection/non-JSON, deny-by-default policy/version mismatch/revocation, consent scope/expiry/revocation, signed backup/restore, wrong key, tampering, missing signature, short key and source immutability.

## Integration boundary
These are security primitives and tested independently. They are not yet enforced as mandatory gates inside every existing ExecutionEngine path. Do not claim full runtime integration or production readiness. Next package should wire these controls into task submission and execution, then re-run all regression suites.

## Key management
Signing key is supplied by caller (minimum 32 bytes), never persisted or committed. HMAC signature is not encryption.
