"""Owner-only, read-only view adapter for verified browser Action History.

This module never creates or mutates the recovery database. It requires an
explicit Owner identity match and a configured existing ledger path.
"""
from __future__ import annotations

import hmac
import os
from pathlib import Path
import sqlite3
import stat
from typing import Any

from core.browser_recovery import RecoveryLedgerError, SQLiteBrowserRecoveryLedger


def read_owner_action_history(principal: Any, settings: Any) -> list[dict[str, object]]:
    """Return verified, payload-free records for the configured Owner only."""
    if principal is None or not isinstance(settings, dict):
        raise PermissionError("Owner authentication is required.")
    owner_issuer = settings.get("owner_issuer")
    owner_subject = settings.get("owner_subject")
    if (
        type(owner_issuer) is not str or not owner_issuer
        or type(owner_subject) is not str or not owner_subject
        or getattr(principal, "issuer", None) != owner_issuer
        or getattr(principal, "subject", None) != owner_subject
    ):
        raise PermissionError("Only the configured Owner may view Action History.")

    raw_path = settings.get("browser_recovery_db_path")
    if type(raw_path) is not str or not raw_path:
        return []
    path = Path(raw_path)
    if not path.is_absolute():
        raise RecoveryLedgerError("Configured recovery ledger path must be absolute.")
    # Reject symlinks in every existing path component, not only the leaf.
    for component in reversed((path, *path.parents)):
        try:
            component_info = component.lstat()
        except OSError as exc:
            raise RecoveryLedgerError("Configured recovery ledger path is unavailable.") from exc
        if stat.S_ISLNK(component_info.st_mode):
            raise RecoveryLedgerError("Recovery ledger path must not contain symlinks.")
    parent = path.parent
    parent_info = parent.lstat()
    file_info = path.lstat()
    if (
        not stat.S_ISDIR(parent_info.st_mode)
        or parent_info.st_uid != os.geteuid() or stat.S_IMODE(parent_info.st_mode) & 0o077
        or not stat.S_ISREG(file_info.st_mode)
        or file_info.st_uid != os.geteuid() or stat.S_IMODE(file_info.st_mode) & 0o077
    ):
        raise RecoveryLedgerError("Recovery ledger permissions are not Owner-private.")

    try:
        db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2.0)
        try:
            db.execute("PRAGMA query_only=ON")
            integrity = db.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise RecoveryLedgerError("Recovery ledger SQLite integrity check failed.")
            rows = db.execute(
                """SELECT sequence,job_id,state,occurred_at,outcome_code,
                          previous_hash,entry_hash
                   FROM browser_job_history ORDER BY sequence"""
            ).fetchall()
        finally:
            db.close()
    except (sqlite3.Error, OSError) as exc:
        raise RecoveryLedgerError("Owner Action History could not be read safely.") from exc

    previous_hash = "0" * 64
    visible: list[dict[str, object]] = []
    for expected_sequence, row in enumerate(rows, start=1):
        sequence, job_id, state, occurred_at, outcome_code, stored_previous, stored_hash = row
        if sequence != expected_sequence or stored_previous != previous_hash:
            raise RecoveryLedgerError("Action History sequence or hash chain is broken.")
        expected_hash = SQLiteBrowserRecoveryLedger._history_entry_hash(
            previous_hash, job_id, state, occurred_at, outcome_code
        )
        if not isinstance(stored_hash, str) or not hmac.compare_digest(expected_hash, stored_hash):
            raise RecoveryLedgerError("Action History integrity verification failed.")
        previous_hash = stored_hash
        visible.append({
            "sequence": sequence,
            "job_id": job_id,
            "state": state,
            "occurred_at": occurred_at,
            "outcome_code": outcome_code,
            "entry_hash": stored_hash,
        })
    return visible
