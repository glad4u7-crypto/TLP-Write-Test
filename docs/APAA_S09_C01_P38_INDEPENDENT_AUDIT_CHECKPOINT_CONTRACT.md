# APAA S09 C01 P38 — Independent Audit Checkpoint Contract

**Status:** provider-neutral interface and synthetic contract tests only  
**Production adapter:** NOT IMPLEMENTED  
**SQLite integration:** NOT ENABLED  
**Credentials / cloud accounts / HSM / TPM:** NOT USED

## Objective

P37 established that the SQLite hash chain and AUTOINCREMENT sequence detect ordinary event mutation and tail deletion. They do not protect against an attacker who can rewrite the database and its metadata. P38 defines the next trust boundary: an independently administered monotonic checkpoint that records the exact audit sequence and entry hash outside the SQLite backup/restore and administrative domain.

## Contract added

- `core/audit_checkpoint.py` defines an immutable `AuditCheckpoint(sequence, entry_hash)`, a narrow `read` / conditional-advance protocol, strict state validation and a fail-closed advance helper.
- A transition advances exactly one sequence and changes the entry hash.
- A stale expected state cannot overwrite a newer checkpoint.
- A lost acknowledgement is reconciled only when a fresh read returns the exact requested target.
- Malformed, unavailable, conflicting or ambiguous provider responses fail closed.
- The helper is not connected to the SQLite audit writer and cannot itself establish that a local audit log is authentic.

## Synthetic verification

`tests/test_audit_checkpoint_contract.py` exercises concurrent writers, stale writers, monotonic sequence validation, malformed provider state, outage handling, lost-ack reconciliation and a simulated adapter restart over shared test state. All provider state and hashes are synthetic and in-memory.

## Required integration design before use

The integration must define an explicit crash-consistent protocol between the SQLite audit transaction and the independent checkpoint. It must not claim atomicity across two systems. A safe implementation must handle at least:

1. SQLite audit append commits but checkpoint CAS does not occur.
2. Checkpoint CAS commits but the acknowledgement is lost.
3. Process crash between local append, checkpoint advance and owner-state mutation.
4. Local backup restore behind the independent checkpoint.
5. Checkpoint provider restore, deletion, recreation, stale reads and identity revocation.
6. Concurrent appenders and recovery operations attempting to checkpoint different hashes for the same sequence.

Any mismatch or unknown outcome blocks owner recovery and protected execution until an explicit dual-control reconciliation ceremony. Never reset the external checkpoint to match a restored local database.

## Production acceptance gates

A future provider must be independently administered, durable across host/process restart and backup/restore, linearizable for compare-and-advance, authenticated with narrowly scoped identity, independently audited, and tested under partition, timeout-after-commit and revocation. No provider is selected in this phase. Any paid provider needs separate explicit selection and cost approval; no paid service is part of this free-only work.

## Safety locks

PR #11 remains Draft/Open/Unmerged. Global Owner remains inactive. Auto-Run and Worker/browser remain OFF. No deployment, merge, real credential, paid API, payment, production activation, host mutation or firewall change is authorized.
