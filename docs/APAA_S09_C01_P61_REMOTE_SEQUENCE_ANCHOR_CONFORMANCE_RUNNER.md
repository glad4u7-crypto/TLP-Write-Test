# APAA-S09-C01-P61 — Remote monotonic sequence-anchor conformance runner

**Status:** Executable operator runner and mocked contract tests committed; no remote provider was contacted.  
**Purpose:** Exercise the actual HTTPS+mTLS sequence API through the existing provider-neutral `HTTPSMonotonicAnchor` adapter.

## Added files

- `scripts/qualify_apaa_remote_sequence_anchor.py`
- `tests/test_qualify_apaa_remote_sequence_anchor.py`

## Safe execution contract

The runner requires all of the following:

- explicit `--confirm-write-tests`;
- a pre-provisioned disposable issuer whose identifier begins `apaa-test-`;
- initial authoritative sequence exactly zero;
- HTTPS endpoint, trusted CA, client certificate and protected client-key file;
- a separately administered test service and credentials supplied by the operator outside the repository.

It performs two concurrent compare-and-advance attempts from expected sequence 0 to 1, requires exactly one winner, checks authoritative read-back through fresh client instances, and verifies that a stale write from expected sequence 0 is rejected.

The runner deliberately has no bootstrap, reset, delete, restore, or cleanup operation. A successful run consumes the test issuer's initial sequence and must be treated as a one-shot disposable test record. Never point it at a production issuer.

## Output boundary

A successful run reports only remote CAS conformance. It explicitly leaves provider backup/restore anti-rollback, independent administration, independent review and production qualification as NOT_ASSESSED/PENDING/NOT_QUALIFIED. Fresh-client read-back is not a disaster-recovery or physical-restart proof.

## Validation

Mocked tests verify the unique-winner contract, stale-write rejection, non-test issuer refusal, nonzero initial sequence refusal and explicit write confirmation. CI on the exact commit is required before accepting the software runner.

No endpoint, certificate, private key, paid service, deployment or production data was used. PR #11 remains Draft/Open/Unmerged; Auto-Run OFF; Worker OFF; C02 NOT STARTED; C01 remains OPEN.
