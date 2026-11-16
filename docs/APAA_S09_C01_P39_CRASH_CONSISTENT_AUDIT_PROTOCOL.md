# APAA S09 C01 P39 — Crash-Consistent Audit Checkpoint Protocol

**Status:** local reconciliation coordinator + synthetic tests only  
**Production adapter:** NOT IMPLEMENTED  
**Owner-recovery / execution integration:** NOT ENABLED

## Protocol

1. Append one audit event to SQLite using its existing verified, transactional append path.
2. Read the verified local audit head as an immutable (sequence, entry_hash) checkpoint.
3. Read the independent provider checkpoint.
4. If both match, report CONSISTENT.
5. If the local head is exactly one sequence ahead, perform a one-step provider CAS and confirm by read-back. This recovers a process crash after local commit but before external checkpoint advancement.
6. If provider acknowledgement is lost, only exact read-back of the target is accepted as success.
7. If the provider is ahead, hashes differ at the same sequence, or local storage is more than one event ahead, fail closed and require a separately authorized reconciliation procedure.

## Failure matrix

| Failure boundary | Expected outcome |
|---|---|
| Crash before SQLite append commit | No local event; no checkpoint movement |
| Crash after SQLite append commit, before provider CAS | One local event pending; exact one-step reconciliation permitted |
| Provider commits CAS but response is lost | Exact read-back confirms; no second increment |
| Provider unavailable | Keep pending local event; do not claim consistency |
| Local database restored behind provider | Block; never roll provider backward |
| Local audit event altered | Local hash-chain verification blocks checkpoint advance |
| Two or more local events uncheckpointed | Block; no bulk catch-up |
| Same sequence but different hash | Block as divergent history |
| Provider checkpoint malformed | Block before mutation |

## Important limitations

- The coordinator is not connected to owner-generation mutation or protected execution.
- It does not make a distributed transaction atomic. It deliberately chooses append-first with a single-entry recoverable pending state.
- A production system still needs a signed/authorized reconciliation ceremony for divergent or multi-entry states.
- The synthetic provider is in-memory and does not prove durability, linearizability, independent administration, provider identity, or backup/restore resistance.
- Do not treat this protocol as a substitute for external audit retention, key custody, independent review, or operational recovery procedures.

## Safety locks

PR #11 remains Draft/Open/Unmerged. Global Owner inactive. Auto-Run OFF. Worker/browser OFF. No deployment, merge, real credential, paid API, payment, production activation, host mutation, or firewall change.
