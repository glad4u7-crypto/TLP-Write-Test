from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import os
import sqlite3
import stat
import pytest

from core.local_owner_anchor import LocalAnchorError, LocalSQLiteOwnerAnchor
from core.offline_owner_recovery import AnchorState


def _race_anchor(path: str, index: int) -> bool:
    anchor = LocalSQLiteOwnerAnchor(path)
    return anchor.compare_and_advance(
        expected=AnchorState(0, None, None),
        target=AnchorState(1, f"{index:064x}", f"process-change-{index:03d}"),
    )


def test_local_anchor_bootstrap_and_private_permissions(tmp_path):
    path = tmp_path / "owner-anchor.sqlite3"
    anchor = LocalSQLiteOwnerAnchor(path)
    assert anchor.read() == AnchorState(0, None, None)
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    corrupt = tmp_path / "corrupt.sqlite3"
    corrupt.touch()
    with pytest.raises(LocalAnchorError):
        LocalSQLiteOwnerAnchor(corrupt)


def test_local_anchor_cas_is_atomic_across_processes(tmp_path):
    path = str(tmp_path / "owner-anchor.sqlite3")
    LocalSQLiteOwnerAnchor(path)
    with ProcessPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(_race_anchor, [path] * 8, range(8)))
    assert sum(outcomes) == 1
    assert LocalSQLiteOwnerAnchor(path).read().revision == 1


def test_local_anchor_rejects_stale_writer_and_revision_jump(tmp_path):
    anchor = LocalSQLiteOwnerAnchor(tmp_path / "owner-anchor.sqlite3")
    initial = anchor.read()
    current = AnchorState(1, "a" * 64, "change-current-001")
    assert anchor.compare_and_advance(expected=initial, target=current)
    assert not anchor.compare_and_advance(
        expected=initial, target=AnchorState(1, "b" * 64, "change-stale-001")
    )
    assert not anchor.compare_and_advance(
        expected=current, target=AnchorState(3, "c" * 64, "change-skip-003")
    )
    assert anchor.read() == current


def test_local_anchor_rejects_symlink_and_broad_permissions(tmp_path):
    real = tmp_path / "real.sqlite3"
    LocalSQLiteOwnerAnchor(real)
    link = tmp_path / "link.sqlite3"
    link.symlink_to(real)
    with pytest.raises(LocalAnchorError):
        LocalSQLiteOwnerAnchor(link)
    if os.name == "posix":
        os.chmod(real, 0o644)
        with pytest.raises(LocalAnchorError):
            LocalSQLiteOwnerAnchor(real)


def test_local_anchor_fails_closed_on_missing_row(tmp_path):
    path = tmp_path / "owner-anchor.sqlite3"
    LocalSQLiteOwnerAnchor(path)
    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM owner_anchor")
    with pytest.raises(LocalAnchorError):
        LocalSQLiteOwnerAnchor(path)
