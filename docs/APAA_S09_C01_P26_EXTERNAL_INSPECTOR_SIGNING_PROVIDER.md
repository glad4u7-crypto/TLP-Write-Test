# APAA-S09-C01-P26 — External host-inspector signing provider boundary

**Status:** implementation committed; exact-head CI verification pending  
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

Exact-head CI must pass before P26 is marked implementation-verified. Tests use only ephemeral in-memory test keys. No deployment, firewall change, live browser, worker activation, paid service, API key, merge or Auto-Run.
