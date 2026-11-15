# APAA S07 — Memory & Knowledge System (separate track)

This is the user's S07 track: memory architecture, knowledge management and context management. It is intentionally named separately from the historical browser-automation S07 documents already present in this repository. Those browser documents are not counted as progress for this memory track.

## Scope and parts

| Chapter | Part | Capability | Implementation |
|---|---|---|---|
| C01 Memory Architecture | P01 Short-term memory | Conversation turn history and bounded context retrieval | `SQLiteMemoryStore.append_turn`, `conversation_context` |
| C01 Memory Architecture | P02 Long-term memory | Explicitly consented, categorized facts/preferences with expiry and pinning | `add_memory`, `list_memories`, `delete_memory` |
| C01 Memory Architecture | P03 Persistent storage | Private local SQLite database, tenant keys, durable records | `SQLiteMemoryStore` |
| C02 Knowledge Management | P01 Collection | User-approved knowledge document intake and source/tags | `add_knowledge` |
| C02 Knowledge Management | P02 Organization | Categories, tags, source metadata, tenant scope | Memory and knowledge schemas |
| C02 Knowledge Management | P03 Search & retrieval | Deterministic lexical ranking, bounded result count | `search` |
| C03 Context Management | P01 Conversation continuity | Ordered recent turns by conversation ID | `conversation_context` |
| C03 Context Management | P02 Preference storage | Explicitly consented JSON preferences, tenant-scoped upsert/delete | `save_preference`, `get_preferences` |
| C03 Context Management | P03 Checkpoint/task recovery | Project-scoped checkpoint save and latest recovery | `save_checkpoint`, `latest_checkpoint` |

## Security and operating boundaries

- No paid service, API, model, embeddings, network call or cloud database is used.
- Every operation requires a validated `TenantKey`; every SQL query is tenant-scoped.
- Persistent writes require explicit `consent=True`. Authentication is not consent.
- Credential-like strings/private-key headers are rejected by a conservative pattern filter.
- Database file permissions are 0600 and its parent directory must be owner-only (0700) on POSIX; symlinked parents/targets are rejected.
- Conversation roles are limited to user/assistant. Context is bounded to 100 turns per read.
- Search is lexical, deterministic and explainable; it is not semantic/vector search.
- Users can delete memories, knowledge documents, preferences and conversation histories. Expiry purge excludes pinned records.
- This is a storage/retrieval library, not an autonomous agent execution permission. Memory content is untrusted data and must never grant tool permissions.
- No arbitrary filesystem browsing, shell, browser, email, payment, trading, purchase or device actions are added.
- No automatic migration or adoption of legacy unscoped user data.

## Known integration boundary

The module exposes the complete storage API and is covered by unit tests. The existing authenticated UI does not yet expose user-facing memory controls or consent screens; those UI controls and a real Android client are separate integration work and must not be represented as complete here. Live multi-user OIDC verification, device-level backup/restore, encryption-at-rest beyond OS file permissions, and multi-host operation remain release gates.

## Local verification

```bash
python -m compileall -q core tests
python -m pytest -q
```

Do not mark production readiness from offline unit tests alone.
