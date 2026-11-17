"""Local SQLite-backed owner anchor for development and single-host use.

This adapter provides crash-consistent, cross-process CAS on one filesystem.
It is NOT independently administered or rollback resistant: a privileged host
operator or restoration of an older file can roll it back. Never use it as a
production substitute for an independently administered monotonic anchor.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import os
import re
import sqlite3
import stat
from typing import Final, Iterator

from core.offline_owner_recovery import AnchorState

_DIGEST: Final = re.compile(r"^[0-9a-f]{64}$")
_CHANGE_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
_SCHEMA: Final = """
CREATE TABLE owner_anchor (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    revision INTEGER NOT NULL CHECK (revision >= 0),
    generation TEXT,
    change_id TEXT,
    CHECK (
        (revision = 0 AND generation IS NULL AND change_id IS NULL)
        OR (revision > 0 AND change_id IS NOT NULL)
    )
)
"""


class LocalAnchorError(RuntimeError):
    """Local anchor is unsafe, malformed, or unavailable."""


class LocalSQLiteOwnerAnchor:
    """Crash-consistent local adapter; deliberately not a production trust root."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path).expanduser()
        if not self.path.is_absolute():
            raise ValueError("Local owner anchor path must be absolute.")
        if not self.path.parent.is_dir() or self.path.parent.is_symlink():
            raise LocalAnchorError("Anchor parent directory must exist and be non-symlink.")
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            self._check_file()
        except OSError:
            raise LocalAnchorError("Local owner anchor file could not be created.") from None
        else:
            os.close(fd)
            try:
                os.chmod(self.path, 0o600)
                with self._connection() as db:
                    db.execute(_SCHEMA)
                    db.execute(
                        "INSERT INTO owner_anchor(singleton, revision, generation, change_id) "
                        "VALUES (1, 0, NULL, NULL)"
                    )
            except Exception:
                raise LocalAnchorError(
                    "New local owner anchor initialization failed; manual recovery required."
                ) from None
        self._check_file()
        self.read()

    def _check_file(self) -> None:
        try:
            info = self.path.lstat()
        except OSError:
            raise LocalAnchorError("Local owner anchor file is unavailable.") from None
        if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise LocalAnchorError("Local owner anchor must be a regular non-symlink file.")
        if os.name == "posix" and stat.S_IMODE(info.st_mode) & 0o077:
            raise LocalAnchorError("Local owner anchor permissions are too broad.")

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self._check_file()
        db = sqlite3.connect(str(self.path), timeout=5.0, isolation_level=None)
        try:
            db.execute("PRAGMA busy_timeout=5000")
            db.execute("PRAGMA synchronous=FULL")
            yield db
        finally:
            db.close()

    @staticmethod
    def _validate_state(state: AnchorState) -> AnchorState:
        if (
            not isinstance(state, AnchorState)
            or type(state.revision) is not int or state.revision < 0
            or (state.generation is not None and (
                type(state.generation) is not str or not _DIGEST.fullmatch(state.generation)
            ))
            or (state.change_id is not None and (
                type(state.change_id) is not str or not _CHANGE_ID.fullmatch(state.change_id)
            ))
            or (state.revision == 0 and (state.generation is not None or state.change_id is not None))
            or (state.revision > 0 and state.change_id is None)
        ):
            raise LocalAnchorError("Local owner anchor state is malformed.")
        return state

    def read(self) -> AnchorState:
        try:
            with self._connection() as db:
                row = db.execute(
                    "SELECT revision, generation, change_id FROM owner_anchor WHERE singleton=1"
                ).fetchone()
            if row is None:
                raise LocalAnchorError("Local owner anchor state is missing.")
            return self._validate_state(AnchorState(*row))
        except LocalAnchorError:
            raise
        except Exception:
            raise LocalAnchorError("Local owner anchor read failed closed.") from None

    def compare_and_advance(self, *, expected: AnchorState, target: AnchorState) -> bool:
        self._validate_state(expected)
        self._validate_state(target)
        if target.revision != expected.revision + 1 or target.change_id is None:
            return False
        try:
            with self._connection() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT revision, generation, change_id FROM owner_anchor WHERE singleton=1"
                ).fetchone()
                if row is None:
                    db.execute("ROLLBACK")
                    raise LocalAnchorError("Local owner anchor state is missing.")
                if self._validate_state(AnchorState(*row)) != expected:
                    db.execute("ROLLBACK")
                    return False
                changed = db.execute(
                    "UPDATE owner_anchor SET revision=?, generation=?, change_id=? "
                    "WHERE singleton=1 AND revision=? AND generation IS ? AND change_id IS ?",
                    (target.revision, target.generation, target.change_id,
                     expected.revision, expected.generation, expected.change_id),
                ).rowcount
                if changed != 1:
                    db.execute("ROLLBACK")
                    return False
                db.execute("COMMIT")
            return True
        except LocalAnchorError:
            raise
        except Exception:
            raise LocalAnchorError("Local owner anchor compare-and-advance failed closed.") from None
