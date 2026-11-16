# APAA-S09-C01-P48 — Encrypted software inspector signing provider

**Scope:** First of the two open security gates: protected signing-key provider work.  
**Status:** software fallback implemented; automated CI verification pending.  
**PR:** #11 (Draft/Open/Unmerged).

## Delivered

Added `core/software_inspector_signer.py` with `EncryptedSoftwareEd25519Signer`, a development-only implementation of the existing `InspectorSigningProvider` protocol:

- Generates an Ed25519 key once and refuses to overwrite an existing key file.
- Encrypts the raw private key at rest with AES-256-GCM; derives the encryption key using scrypt (N=32768, r=8, p=1) and a random 16-byte salt.
- Uses a random 12-byte AEAD nonce and authenticates schema/key ID/KDF metadata as associated data.
- Creates the key file exclusively with POSIX mode 0600, fsyncs the file and parent directory, rejects symlinks, hard links, non-regular files, broad permissions and oversized files.
- Requires an explicit caller-supplied passphrase; it is not stored in the repository or environment by this implementation.
- Exposes only `key_id`, `public_key_bytes()` and bounded `sign(message)`; there is no private-key export method.
- Reopens the same key after restart and fails closed for wrong passphrase, malformed/tampered file and unsafe filesystem metadata.

Added `tests/test_software_inspector_signer.py` for create/reopen signature continuity, export API absence, wrong passphrase, tampering, permissions, symlink rejection, no-overwrite behavior, invalid IDs/passphrases and bounded signing input.

## Security boundary — important

This is **not TPM/HSM protection and not an equivalent non-exportable key boundary**. Once unlocked, the Ed25519 private key is present in this Python process's memory. A privileged host attacker, process-memory inspection, compromised runtime, keylogger or stolen passphrase can compromise it. Encryption at rest and the narrow API reduce accidental exposure; they do not make the key hardware-protected.

This provider is not wired as the production host signer and must not be used to satisfy the production gate. It is a free, local development/integration option that makes the signer interface executable and testable without paid APIs or hardware. Production still requires a separately administered TPM/HSM or independently reviewed protected signing service, out-of-band public-key pinning, identity authorization, audit, rotation/revocation and independent qualification.

## Verification and release locks

Exact-head GitHub Actions must pass before this package is called CI-verified. No physical hardware, protected key custody, production host, independent reviewer or production deployment is claimed. PR #11 remains Draft/Open/Unmerged; Auto-Run OFF; Worker/Browser DISABLED; no merge, deployment, host/firewall mutation, paid provider or C02 start.
