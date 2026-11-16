# APAA-S09-C01-P55 — Remote anchor CAS conformance runner

**Status:** explicit test-only conformance runner and tests committed; exact-head CI pending.  
**Provider qualification:** NOT CLAIMED.

## Delivered

Added `scripts/qualify_apaa_remote_anchor.py`:

- Requires HTTPS+mTLS endpoint inputs, a dedicated test anchor ID beginning `apaa-test-`, and explicit `--confirm-write-tests`.
- Requires the test anchor to be pre-provisioned at revision zero; refuses to bootstrap or overwrite an existing/nonzero record.
- Sends two concurrent compare-and-advance requests from separate client instances with the same expected state and different target states.
- Requires exactly one successful writer, authoritative read-back of the winner, rejection of the stale losing target, and read consistency through a fresh client instance.
- Emits provider backup/restore anti-rollback, independent administration, independent review and production qualification as NOT_ASSESSED / PENDING / NOT_QUALIFIED.
- Does not touch the owner production anchor unless an operator deliberately violates the dedicated test-ID policy and misconfigures the provider's namespace.

Tests use a thread-safe test backend to verify one-winner CAS, stale-write rejection, refusal of non-test IDs, refusal of nonzero initial state and mandatory explicit write confirmation.

## Operator use

After the provider has separately created an isolated `apaa-test-...` anchor at revision zero:

```bash
python scripts/qualify_apaa_remote_anchor.py \
  --endpoint https://anchor.example.test \
  --ca-file /path/to/anchor-ca.pem \
  --client-cert /path/to/apaa-anchor-client.pem \
  --client-key /path/to/apaa-anchor-client.key \
  --test-anchor-id apaa-test-owner-001 \
  --confirm-write-tests
```

This performs real writes to the named test anchor. Do not use the production owner-anchor ID. The test anchor will be advanced to revision one and should be discarded/recreated only through the provider's separately approved test-resource lifecycle.

## Remaining provider qualification

A passing run proves the actual API's two-client CAS behavior and read-back at that time. It does not prove durable acknowledgement after power loss, server restart, backup restore, deletion/recreation, immutable audit retention, separate administration, provider identity revocation or protection against a malicious provider administrator. Those require separate provider-specific drills, external evidence and independent review.
