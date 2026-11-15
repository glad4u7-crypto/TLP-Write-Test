# APAA S07 — P10 Inspector Signing-Key Trust Registry Boundary

**Checkpoint:** APAA-S07-C01-P10  
**Implementation:** `core/inspector_key_registry.py`  
**Tests:** `tests/test_inspector_key_registry.py`  
**CI:** pending exact P10 implementation commit verification  
**Private-key generation / import / storage:** NOT IMPLEMENTED  
**Key provisioning / rotation approval:** OUT-OF-BAND ONLY  
**Deployment / firewall / worker / browser:** NOT PERFORMED

## Objective

P10 establishes a narrow trust-registry boundary for the Ed25519 public keys used by the P06 signed inspector-evidence verifier. It makes key validity windows and explicit revocation testable without creating, importing, storing or exposing private signing keys.

## Trust source and API

`InspectorPublicKeyRegistry` accepts typed `InspectorPublicKeyRecord` objects supplied by trusted application configuration. The source of those records must be independently authenticated and provisioned out-of-band. The registry object is not itself a trust anchor and does not read arbitrary files, environment variables, network services, secret stores or GitHub secrets.

Each record contains:
- stable key ID;
- exactly 32 bytes of Ed25519 public-key material;
- inclusive `not_before` timestamp;
- exclusive `not_after` timestamp;
- explicit boolean revocation state.

`active_public_keys(now=...)` returns a fresh mapping containing only keys whose validity window includes the evaluation time and which are not revoked. This mapping can be passed to `verify_signed_inspector_evidence(..., trusted_public_keys=...)`. `require_active_key` resolves one key and fails closed for unknown, expired or revoked IDs.

## Rotation and revocation model

- Planned rotation may use a bounded overlap window where old and new public keys are both active.
- After the overlap, the old key expires and is no longer returned.
- Emergency revocation is represented explicitly and immediately excludes the key, regardless of its validity interval.
- Duplicate key IDs and duplicate public-key material under different IDs are rejected.
- Validity intervals must be non-negative and strictly increasing.
- The caller must obtain an authenticated registry snapshot; no self-service or worker-controlled key enrollment exists.

Rotation approval, publication, rollback, emergency revocation authority, audit trail and out-of-band distribution are operational governance requirements. P10 does not invent an approval workflow or claim those external controls exist.

## Security boundaries

- Public keys only; no private-key bytes, keypair generation, signing API, key import, filesystem persistence or secret retrieval.
- No key is generated or provisioned by tests; tests use fixed synthetic byte strings to validate metadata behavior.
- The registry is immutable after construction and returns fresh dictionaries.
- Exact Ed25519 key encoding/signature validity remains enforced by the P06 cryptographic verifier when a signature is checked.
- The registry does not authenticate its own input source; caller configuration provenance remains a release gate.
- No network listener, runtime handler, worker, browser, shell command or host mutation is added.

## Tests

Offline tests cover active/inactive validity boundaries, rotation overlap, expiration, revocation, duplicate IDs, duplicate key material, malformed records, typed-input enforcement, invalid evaluation time and immutable snapshot behavior.

## Remaining gates

1. Connect an authenticated out-of-band registry source to trusted control-plane configuration.
2. Define named key custodians, dual-control approval, rotation windows, emergency revocation and audited rollback.
3. Integrate registry resolution + P06 signature verification + P09 durable challenge consumption in one trusted control-plane request path, consuming only after every check succeeds.
4. Independently review signer isolation, host/runtime identity and real host/packet-level acceptance.
5. Keep private signing keys outside the repository and outside the inspected worker.

**P10 disposition:** PUBLIC-KEY REGISTRY VALIDATION PRIMITIVE AND OFFLINE TESTS ADDED. OUT-OF-BAND TRUST SOURCE, GOVERNANCE AND CONTROL-PLANE INTEGRATION REMAIN OPEN. No deployment, firewall modification, worker launch or browser activation.
