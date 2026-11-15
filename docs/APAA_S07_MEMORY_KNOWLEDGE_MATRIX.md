# APAA S07 Memory & Knowledge — Verification Matrix

**Track identity:** Memory & Knowledge System (user-defined S07).  
**Do not conflate:** Existing `APAA_S07_BROWSER_*` and Inspector P09-P11 documents describe a separate browser automation track.

| Checkpoint | Implementation | Test evidence | Status |
|---|---|---|---|
| S07-C01-P01 Short-term memory | Ordered conversation turns; bounded context | `test_short_term_conversation_continuity_and_deletion` | IMPLEMENTED — CI PENDING |
| S07-C01-P02 Long-term memory | Consent-gated categorized records, expiry, pin, delete | CRUD, consent, expiry and secret-pattern tests | IMPLEMENTED — CI PENDING |
| S07-C01-P03 Persistent storage | Private tenant-scoped SQLite | file mode, isolation, persistence through SQLite tests | IMPLEMENTED — CI PENDING |
| S07-C02-P01 Collection | Consent-gated knowledge intake with source/tags | knowledge collection test | IMPLEMENTED — CI PENDING |
| S07-C02-P02 Organization | tags, metadata, tenant isolation | knowledge and memory tests | IMPLEMENTED — CI PENDING |
| S07-C02-P03 Search/retrieval | deterministic lexical ranking and bounded limit | retrieval/isolation/limit tests | IMPLEMENTED — CI PENDING |
| S07-C03-P01 Conversation continuity | ordered recent turns per conversation | continuity/deletion test | IMPLEMENTED — CI PENDING |
| S07-C03-P02 Preference storage | consent-gated JSON upsert/read/delete | preference isolation test | IMPLEMENTED — CI PENDING |
| S07-C03-P03 Checkpoint recovery | project/tenant-scoped latest checkpoint | checkpoint recovery test | IMPLEMENTED — CI PENDING |

## Global gates

| Gate | Status |
|---|---|
| No paid APIs/providers, no network/embeddings | PASS BY DESIGN — OFFLINE MODULE |
| Explicit consent on all persistent personal-content writes | IMPLEMENTED — TESTS ADDED |
| Tenant issuer + subject isolation | IMPLEMENTED — TESTS ADDED |
| Credential-like content rejection | IMPLEMENTED — TESTS ADDED |
| Local DB file/directory permissions and symlink rejection | IMPLEMENTED — TESTS ADDED |
| Existing CI workflows on exact final commit | PENDING |
| User-facing consent/preferences/memory UI | NOT IMPLEMENTED |
| Native Android client | NOT IMPLEMENTED |
| Live OIDC two-identity verification | NOT RUN |
| Backup/restore and multi-host deployment | NOT VALIDATED |
| Production readiness | NOT APPROVED |

**Exit rule:** The nine software Parts may be marked repository-complete only after exact-head CI passes. S07 overall remains **PARTIALLY COMPLETE / NOT PRODUCTION READY** until UI consent controls, Android client integration and operational release gates are addressed.
