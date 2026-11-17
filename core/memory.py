"""Tenant-isolated, consent-gated local memory and knowledge store.

Short-term conversation turns, long-term memories, knowledge documents,
preferences and task checkpoints share one private SQLite database. Search is
deterministic lexical retrieval; this module performs no network/API calls.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from uuid import uuid4

from core.storage import TenantKey


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_text(value: str, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty text.")
    value = value.strip()
    if len(value) > maximum:
        raise ValueError(f"{label} must be {maximum} characters or fewer.")
    if _SECRET_PATTERN.search(value):
        raise ValueError("Content resembling a credential or private key cannot be stored.")
    return value


_SECRET_PATTERN = re.compile(
    r"(?i)(-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"\b(?:api[_ -]?key|access[_ -]?token|password|secret)\s*[:=]\s*\S+|"
    r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,})"
)
_ALLOWED_MEMORY_CATEGORIES = {"fact", "preference", "project", "workflow", "learning", "other"}


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    category: str
    content: str
    tags: tuple[str, ...]
    source: str
    created_at: str
    expires_at: str | None
    pinned: bool


@dataclass(frozen=True)
class KnowledgeDocument:
    document_id: str
    title: str
    content: str
    tags: tuple[str, ...]
    source: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ConversationTurn:
    turn_id: str
    conversation_id: str
    role: str
    content: str
    created_at: str


@dataclass(frozen=True)
class TaskCheckpoint:
    checkpoint_id: str
    project_id: str
    label: str
    summary: str
    next_action: str
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class SavedTaskPlan:
    saved_plan_id: str
    project_id: str
    plan_id: str
    task_description: str
    plan_json: str
    created_at: str
    updated_at: str


class SQLiteMemoryStore:
    """Private local store; every read/write is scoped to an explicit TenantKey.

    Writes that persist personal content require consent=True. The class does
    not infer consent from authentication or from the presence of a database.
    """

    def __init__(self, database_path: str | Path, *, timeout: float = 5.0) -> None:
        raw_path = str(database_path)
        if raw_path == ":memory:":
            raise ValueError("Use a filesystem-backed private database for durable memory.")
        self._path = Path(raw_path).absolute()
        self._timeout = timeout
        self._secure_path(create_parent=True)
        self._initialize()
        self._secure_path(create_parent=False)

    @property
    def database_path(self) -> str:
        return str(self._path)

    def _secure_path(self, *, create_parent: bool) -> None:
        for parent in self._path.parents:
            try:
                if stat.S_ISLNK(parent.lstat().st_mode):
                    raise ValueError("Memory database parent must not contain symlinks.")
            except FileNotFoundError:
                continue
        if create_parent:
            self._path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        parent_mode = self._path.parent.stat().st_mode
        if not stat.S_ISDIR(parent_mode):
            raise ValueError("Memory database parent must be a directory.")
        if os.name == "posix" and parent_mode & 0o077:
            raise ValueError("Memory database directory must be owner-only (0700).")
        try:
            metadata = self._path.lstat()
        except FileNotFoundError:
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
            try:
                fd = os.open(self._path, flags, 0o600)
            except FileExistsError:
                metadata = self._path.lstat()
            else:
                os.close(fd)
                metadata = self._path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ValueError("Memory database must be a regular non-symlink file.")
        os.chmod(self._path, 0o600)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self._path), timeout=self._timeout, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout = {int(self._timeout * 1000)}")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        statements = [
            """CREATE TABLE IF NOT EXISTS memory_records (
                memory_id TEXT PRIMARY KEY, issuer TEXT NOT NULL, subject TEXT NOT NULL,
                category TEXT NOT NULL, content TEXT NOT NULL, tags_json TEXT NOT NULL,
                source TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT,
                pinned INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0,1)))""",
            """CREATE INDEX IF NOT EXISTS idx_memory_tenant_time
                ON memory_records(issuer, subject, created_at)""",
            """CREATE TABLE IF NOT EXISTS knowledge_documents (
                document_id TEXT PRIMARY KEY, issuer TEXT NOT NULL, subject TEXT NOT NULL,
                title TEXT NOT NULL, content TEXT NOT NULL, tags_json TEXT NOT NULL,
                source TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
            """CREATE INDEX IF NOT EXISTS idx_knowledge_tenant_time
                ON knowledge_documents(issuer, subject, updated_at)""",
            """CREATE TABLE IF NOT EXISTS conversation_turns (
                turn_id TEXT PRIMARY KEY, issuer TEXT NOT NULL, subject TEXT NOT NULL,
                conversation_id TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                content TEXT NOT NULL, created_at TEXT NOT NULL)""",
            """CREATE INDEX IF NOT EXISTS idx_turns_conversation
                ON conversation_turns(issuer, subject, conversation_id, created_at)""",
            """CREATE TABLE IF NOT EXISTS user_preferences (
                issuer TEXT NOT NULL, subject TEXT NOT NULL, preference_key TEXT NOT NULL,
                value_json TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(issuer, subject, preference_key))""",
            """CREATE TABLE IF NOT EXISTS task_checkpoints (
                checkpoint_id TEXT PRIMARY KEY, issuer TEXT NOT NULL, subject TEXT NOT NULL,
                project_id TEXT NOT NULL, label TEXT NOT NULL, summary TEXT NOT NULL,
                next_action TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL)""",
            """CREATE INDEX IF NOT EXISTS idx_checkpoint_latest
                ON task_checkpoints(issuer, subject, project_id, updated_at)""",
            """CREATE TABLE IF NOT EXISTS saved_task_plans (
                saved_plan_id TEXT PRIMARY KEY, issuer TEXT NOT NULL, subject TEXT NOT NULL,
                project_id TEXT NOT NULL, plan_id TEXT NOT NULL, task_description TEXT NOT NULL,
                plan_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(issuer, subject, project_id, plan_id))""",
            """CREATE INDEX IF NOT EXISTS idx_saved_task_plans_latest
                ON saved_task_plans(issuer, subject, project_id, updated_at)""",
        ]
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                for statement in statements:
                    db.execute(statement)
                db.commit()
            except Exception:
                db.rollback()
                raise

    @staticmethod
    def _tenant(tenant: TenantKey) -> tuple[str, str]:
        if not isinstance(tenant, TenantKey):
            raise TypeError("A validated TenantKey is required.")
        return tenant.issuer, tenant.subject

    @staticmethod
    def _tags(tags: tuple[str, ...] | list[str]) -> tuple[str, ...]:
        if not isinstance(tags, (tuple, list)) or len(tags) > 20:
            raise ValueError("Tags must be a list of at most 20 strings.")
        cleaned = []
        for tag in tags:
            if not isinstance(tag, str) or not tag.strip() or len(tag.strip()) > 40:
                raise ValueError("Each tag must contain 1 to 40 characters.")
            cleaned.append(tag.strip().lower())
        return tuple(dict.fromkeys(cleaned))

    @staticmethod
    def _require_consent(consent: bool) -> None:
        if consent is not True:
            raise PermissionError("Explicit consent=True is required to persist personal content.")

    def add_memory(
        self, tenant: TenantKey, *, category: str, content: str,
        tags: tuple[str, ...] | list[str] = (), source: str = "user",
        expires_in_days: int | None = None, pinned: bool = False, consent: bool = False,
    ) -> MemoryRecord:
        self._require_consent(consent)
        if category not in _ALLOWED_MEMORY_CATEGORIES:
            raise ValueError("Unsupported memory category.")
        content = _validate_text(content, "Memory content", 10000)
        source = _validate_text(source, "Memory source", 120)
        tags = self._tags(tags)
        if expires_in_days is not None and (
            not isinstance(expires_in_days, int) or not 1 <= expires_in_days <= 3650
        ):
            raise ValueError("expires_in_days must be between 1 and 3650.")
        if not isinstance(pinned, bool):
            raise ValueError("pinned must be boolean.")
        issuer, subject = self._tenant(tenant)
        created = _now()
        expires = (datetime.now(timezone.utc) + timedelta(days=expires_in_days)).isoformat() if expires_in_days else None
        memory_id = str(uuid4())
        with closing(self._connect()) as db:
            db.execute(
                """INSERT INTO memory_records VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (memory_id, issuer, subject, category, content, json.dumps(tags),
                 source, created, expires, int(pinned)),
            )
        return MemoryRecord(memory_id, category, content, tags, source, created, expires, pinned)

    def list_memories(self, tenant: TenantKey, *, category: str | None = None) -> list[MemoryRecord]:
        issuer, subject = self._tenant(tenant)
        sql = """SELECT * FROM memory_records WHERE issuer=? AND subject=?
                 AND (expires_at IS NULL OR expires_at > ?)"""
        params: list[object] = [issuer, subject, _now()]
        if category is not None:
            sql += " AND category=?"
            params.append(category)
        sql += " ORDER BY pinned DESC, created_at DESC"
        with closing(self._connect()) as db:
            rows = db.execute(sql, params).fetchall()
        return [MemoryRecord(r["memory_id"], r["category"], r["content"],
            tuple(json.loads(r["tags_json"])), r["source"], r["created_at"],
            r["expires_at"], bool(r["pinned"])) for r in rows]

    def delete_memory(self, tenant: TenantKey, memory_id: str) -> bool:
        issuer, subject = self._tenant(tenant)
        with closing(self._connect()) as db:
            cur = db.execute("DELETE FROM memory_records WHERE memory_id=? AND issuer=? AND subject=?",
                             (memory_id, issuer, subject))
        return cur.rowcount == 1

    def add_knowledge(
        self, tenant: TenantKey, *, title: str, content: str,
        tags: tuple[str, ...] | list[str] = (), source: str = "user", consent: bool = False,
    ) -> KnowledgeDocument:
        self._require_consent(consent)
        title = _validate_text(title, "Knowledge title", 200)
        content = _validate_text(content, "Knowledge content", 100000)
        source = _validate_text(source, "Knowledge source", 300)
        tags = self._tags(tags)
        issuer, subject = self._tenant(tenant)
        now = _now()
        document_id = str(uuid4())
        with closing(self._connect()) as db:
            db.execute("INSERT INTO knowledge_documents VALUES (?,?,?,?,?,?,?,?,?)",
                (document_id, issuer, subject, title, content, json.dumps(tags), source, now, now))
        return KnowledgeDocument(document_id, title, content, tags, source, now, now)

    def list_knowledge(self, tenant: TenantKey) -> list[KnowledgeDocument]:
        issuer, subject = self._tenant(tenant)
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT * FROM knowledge_documents WHERE issuer=? AND subject=?
                   ORDER BY updated_at DESC, document_id""", (issuer, subject)
            ).fetchall()
        return [KnowledgeDocument(r["document_id"], r["title"], r["content"],
            tuple(json.loads(r["tags_json"])), r["source"], r["created_at"],
            r["updated_at"]) for r in rows]

    def delete_knowledge(self, tenant: TenantKey, document_id: str) -> bool:
        issuer, subject = self._tenant(tenant)
        with closing(self._connect()) as db:
            cur = db.execute("DELETE FROM knowledge_documents WHERE document_id=? AND issuer=? AND subject=?",
                             (document_id, issuer, subject))
        return cur.rowcount == 1

    def search(self, tenant: TenantKey, query: str, *, limit: int = 10) -> list[dict[str, object]]:
        """Deterministic lexical search over unexpired memories and knowledge docs."""
        query = _validate_text(query, "Search query", 300)
        if not isinstance(limit, int) or not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50.")
        issuer, subject = self._tenant(tenant)
        terms = tuple(dict.fromkeys(re.findall(r"[a-z0-9_]{2,}", query.lower())))
        if not terms:
            return []
        with closing(self._connect()) as db:
            memories = db.execute(
                """SELECT memory_id AS id, category AS kind, content AS title, content,
                          tags_json, source, created_at
                   FROM memory_records WHERE issuer=? AND subject=?
                   AND (expires_at IS NULL OR expires_at > ?)""", (issuer, subject, _now())
            ).fetchall()
            docs = db.execute(
                """SELECT document_id AS id, 'knowledge' AS kind, title, content,
                          tags_json, source, updated_at AS created_at
                   FROM knowledge_documents WHERE issuer=? AND subject=?""", (issuer, subject)
            ).fetchall()
        ranked = []
        for row in list(memories) + list(docs):
            haystack = (row["title"] + " " + row["content"] + " " + " ".join(json.loads(row["tags_json"]))).lower()
            score = sum(haystack.count(term) for term in terms)
            if score:
                ranked.append((score, row["created_at"], {
                    "id": row["id"], "kind": row["kind"], "title": row["title"],
                    "content": row["content"], "tags": tuple(json.loads(row["tags_json"])),
                    "source": row["source"], "created_at": row["created_at"], "score": score,
                }))
        ranked.sort(key=lambda item: (-item[0], item[1], item[2]["id"]))
        return [item[2] for item in ranked[:limit]]

    def append_turn(
        self, tenant: TenantKey, *, conversation_id: str, role: str,
        content: str, consent: bool = False,
    ) -> ConversationTurn:
        self._require_consent(consent)
        conversation_id = _validate_text(conversation_id, "Conversation ID", 120)
        if role not in {"user", "assistant"}:
            raise ValueError("Conversation role must be user or assistant.")
        content = _validate_text(content, "Conversation content", 20000)
        issuer, subject = self._tenant(tenant)
        turn_id, created = str(uuid4()), _now()
        with closing(self._connect()) as db:
            db.execute("INSERT INTO conversation_turns VALUES (?,?,?,?,?,?,?)",
                (turn_id, issuer, subject, conversation_id, role, content, created))
        return ConversationTurn(turn_id, conversation_id, role, content, created)

    def conversation_context(
        self, tenant: TenantKey, conversation_id: str, *, limit: int = 20,
    ) -> list[ConversationTurn]:
        issuer, subject = self._tenant(tenant)
        conversation_id = _validate_text(conversation_id, "Conversation ID", 120)
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100.")
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT * FROM conversation_turns WHERE issuer=? AND subject=?
                   AND conversation_id=? ORDER BY created_at DESC, rowid DESC LIMIT ?""",
                (issuer, subject, conversation_id, limit)
            ).fetchall()
        rows.reverse()
        return [ConversationTurn(r["turn_id"], r["conversation_id"], r["role"],
                                 r["content"], r["created_at"]) for r in rows]

    def delete_conversation(self, tenant: TenantKey, conversation_id: str) -> int:
        issuer, subject = self._tenant(tenant)
        conversation_id = _validate_text(conversation_id, "Conversation ID", 120)
        with closing(self._connect()) as db:
            cur = db.execute("DELETE FROM conversation_turns WHERE issuer=? AND subject=? AND conversation_id=?",
                             (issuer, subject, conversation_id))
        return cur.rowcount

    def save_preference(
        self, tenant: TenantKey, *, key: str, value: object, consent: bool = False,
    ) -> None:
        self._require_consent(consent)
        key = _validate_text(key, "Preference key", 80)
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if len(encoded) > 4000 or _SECRET_PATTERN.search(encoded):
            raise ValueError("Preference value is too large or resembles a credential.")
        issuer, subject = self._tenant(tenant)
        with closing(self._connect()) as db:
            db.execute(
                """INSERT INTO user_preferences VALUES (?,?,?,?,?)
                   ON CONFLICT(issuer,subject,preference_key)
                   DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
                (issuer, subject, key, encoded, _now())
            )

    def get_preferences(self, tenant: TenantKey) -> dict[str, object]:
        issuer, subject = self._tenant(tenant)
        with closing(self._connect()) as db:
            rows = db.execute("SELECT preference_key,value_json FROM user_preferences WHERE issuer=? AND subject=?",
                              (issuer, subject)).fetchall()
        return {r["preference_key"]: json.loads(r["value_json"]) for r in rows}

    def delete_preference(self, tenant: TenantKey, key: str) -> bool:
        issuer, subject = self._tenant(tenant)
        with closing(self._connect()) as db:
            cur = db.execute("DELETE FROM user_preferences WHERE issuer=? AND subject=? AND preference_key=?",
                             (issuer, subject, key))
        return cur.rowcount == 1

    def save_checkpoint(
        self, tenant: TenantKey, *, project_id: str, label: str, summary: str,
        next_action: str, status: str = "active", consent: bool = False,
    ) -> TaskCheckpoint:
        self._require_consent(consent)
        issuer, subject = self._tenant(tenant)
        project_id = _validate_text(project_id, "Project ID", 120)
        label = _validate_text(label, "Checkpoint label", 160)
        summary = _validate_text(summary, "Checkpoint summary", 10000)
        next_action = _validate_text(next_action, "Next action", 2000)
        if status not in {"active", "blocked", "completed", "cancelled"}:
            raise ValueError("Unsupported checkpoint status.")
        now, checkpoint_id = _now(), str(uuid4())
        with closing(self._connect()) as db:
            db.execute("INSERT INTO task_checkpoints VALUES (?,?,?,?,?,?,?,?,?,?)",
                (checkpoint_id, issuer, subject, project_id, label, summary, next_action, status, now, now))
        return TaskCheckpoint(checkpoint_id, project_id, label, summary, next_action, status, now, now)

    def latest_checkpoint(self, tenant: TenantKey, project_id: str) -> TaskCheckpoint | None:
        issuer, subject = self._tenant(tenant)
        project_id = _validate_text(project_id, "Project ID", 120)
        with closing(self._connect()) as db:
            row = db.execute(
                """SELECT * FROM task_checkpoints WHERE issuer=? AND subject=? AND project_id=?
                   ORDER BY updated_at DESC, rowid DESC LIMIT 1""", (issuer, subject, project_id)
            ).fetchone()
        if row is None:
            return None
        return TaskCheckpoint(row["checkpoint_id"], row["project_id"], row["label"],
            row["summary"], row["next_action"], row["status"], row["created_at"], row["updated_at"])

    def list_checkpoints(
        self, tenant: TenantKey, project_id: str, *, limit: int = 50,
    ) -> tuple[TaskCheckpoint, ...]:
        """Return a bounded, newest-first history for one owner/project."""
        issuer, subject = self._tenant(tenant)
        project_id = _validate_text(project_id, "Project ID", 120)
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("limit must be an integer from 1 to 200.")
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT * FROM task_checkpoints
                   WHERE issuer=? AND subject=? AND project_id=?
                   ORDER BY updated_at DESC, rowid DESC LIMIT ?""",
                (issuer, subject, project_id, limit),
            ).fetchall()
        return tuple(
            TaskCheckpoint(
                row["checkpoint_id"], row["project_id"], row["label"],
                row["summary"], row["next_action"], row["status"],
                row["created_at"], row["updated_at"],
            )
            for row in rows
        )

    def save_task_plan(
        self, tenant: TenantKey, *, project_id: str, plan_id: str,
        task_description: str, plan: dict[str, object], consent: bool = False,
    ) -> SavedTaskPlan:
        """Persist a reviewable plan only after explicit Owner consent."""
        self._require_consent(consent)
        issuer, subject = self._tenant(tenant)
        project_id = _validate_text(project_id, "Project ID", 120)
        if not isinstance(plan_id, str) or re.fullmatch(r"plan-[0-9a-f]{16}", plan_id) is None:
            raise ValueError("Task plan ID is invalid.")
        task_description = _validate_text(task_description, "Task description", 4000)
        if not isinstance(plan, dict) or plan.get("plan_id") != plan_id:
            raise ValueError("Task plan snapshot does not match its plan ID.")
        if plan.get("task_description") != task_description:
            raise ValueError("Task plan snapshot does not match its description.")
        encoded = json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(encoded) > 100000 or _SECRET_PATTERN.search(encoded):
            raise ValueError("Task plan is too large or resembles a credential.")
        now = _now()
        with closing(self._connect()) as db:
            existing = db.execute(
                """SELECT saved_plan_id, created_at FROM saved_task_plans
                   WHERE issuer=? AND subject=? AND project_id=? AND plan_id=?""",
                (issuer, subject, project_id, plan_id),
            ).fetchone()
            if existing:
                saved_plan_id, created_at = existing["saved_plan_id"], existing["created_at"]
                db.execute(
                    """UPDATE saved_task_plans SET task_description=?, plan_json=?, updated_at=?
                       WHERE issuer=? AND subject=? AND project_id=? AND plan_id=?""",
                    (task_description, encoded, now, issuer, subject, project_id, plan_id),
                )
            else:
                saved_plan_id, created_at = str(uuid4()), now
                db.execute(
                    """INSERT INTO saved_task_plans VALUES (?,?,?,?,?,?,?,?,?)""",
                    (saved_plan_id, issuer, subject, project_id, plan_id,
                     task_description, encoded, created_at, now),
                )
        return SavedTaskPlan(
            saved_plan_id, project_id, plan_id, task_description, encoded, created_at, now
        )

    def list_task_plans(
        self, tenant: TenantKey, *, project_id: str, limit: int = 50,
    ) -> list[SavedTaskPlan]:
        issuer, subject = self._tenant(tenant)
        project_id = _validate_text(project_id, "Project ID", 120)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Task plan limit must be between 1 and 100.")
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT * FROM saved_task_plans WHERE issuer=? AND subject=? AND project_id=?
                   ORDER BY updated_at DESC, saved_plan_id LIMIT ?""",
                (issuer, subject, project_id, limit),
            ).fetchall()
        return [
            SavedTaskPlan(
                row["saved_plan_id"], row["project_id"], row["plan_id"],
                row["task_description"], row["plan_json"], row["created_at"], row["updated_at"],
            )
            for row in rows
        ]

    def delete_task_plan(
        self, tenant: TenantKey, *, project_id: str, plan_id: str, consent: bool = False,
    ) -> bool:
        self._require_consent(consent)
        issuer, subject = self._tenant(tenant)
        project_id = _validate_text(project_id, "Project ID", 120)
        if not isinstance(plan_id, str) or re.fullmatch(r"plan-[0-9a-f]{16}", plan_id) is None:
            raise ValueError("Task plan ID is invalid.")
        with closing(self._connect()) as db:
            cur = db.execute(
                "DELETE FROM saved_task_plans WHERE issuer=? AND subject=? AND project_id=? AND plan_id=?",
                (issuer, subject, project_id, plan_id),
            )
        return cur.rowcount == 1

    def purge_expired_memories(self, tenant: TenantKey) -> int:
        issuer, subject = self._tenant(tenant)
        with closing(self._connect()) as db:
            cur = db.execute("DELETE FROM memory_records WHERE issuer=? AND subject=? AND pinned=0 AND expires_at IS NOT NULL AND expires_at<=?",
                             (issuer, subject, _now()))
        return cur.rowcount
