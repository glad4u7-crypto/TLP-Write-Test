# APAA S09 C01 P37 — Recovery Concurrency, Rollback and Audit Adversarial Tests

Status: implementation/test batch only; not a production qualification.

## Scope

P37 extends the synthetic offline-owner recovery test suite with:
- Two simultaneous dual-signed recovery requests competing for one owner-state revision. A linearizable test anchor must permit exactly one transition.
- SQLite backup/restore to a revision-zero snapshot while the independent monotonic anchor has advanced two revisions. Inspection must report `DIVERGED_BLOCKED`; another recovery must fail closed. A one-revision lead is intentionally classified as potentially resumable because it is observationally indistinguishable from a crash after anchor CAS and before local SQLite CAS; only the exact still-valid dual-signed target envelope can resume it.
- Audit event-field mutation and tail deletion detection. Recovery must not proceed when the local audit chain is invalid. Recovery now verifies the audit chain before any anchor mutation and the SQLite store re-verifies it inside the owner-state transaction; pre-existing tampering or tail deletion therefore leaves both local owner state and anchor unchanged.
- Operator and approver key rotation. A service configured only with the replacement trust set rejects the old signatures and accepts a new envelope signed by the replacement independent key pair.
- Key revocation by removing the old key from the trusted policy.
- Audit-commit failure injection. SQLite owner-state and audit writes roll back atomically; the external anchor remains ahead and the state is explicitly resumable only through the dual-control recovery protocol.

## Security boundaries

All private keys and owner generations in these tests are synthetic. The in-memory/linearizable test anchor is not a production adapter. SQLite's audit hash chain and AUTOINCREMENT sequence high-water mark detect ordinary mutation/truncation but are not tamper-proof against an attacker able to rewrite the database and its metadata. A production design still requires an independently protected durable audit checkpoint, independent monotonic anchor with linearizable compare-and-advance, protected operator/approver key custody and revocation distribution, live OIDC identity enrollment, physical Android and production Linux host qualification, and independent security review.

## Required verification

Run the full repository CI against the exact P37 commit. A previous commit's successful checks do not qualify this commit. Inspect any failing job logs and correct failures before claiming closure.

## Safety locks

PR #11 stays Draft/Open/Unmerged. Global Owner remains inactive. Auto-Run and Worker/browser remain OFF. No deployment, merge, real credentials, paid API, payment, production activation, or host/firewall mutation is authorized by this batch.
