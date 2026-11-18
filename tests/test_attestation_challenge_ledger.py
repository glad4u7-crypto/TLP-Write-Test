from concurrent.futures import ThreadPoolExecutor
import os
import stat

import pytest

from core.attestation_challenge_ledger import (
    ChallengeLedgerError,
    SQLiteChallengeLedger,
)


def test_challenge_is_consumed_once_and_survives_ledger_reopen(tmp_path):
    path = tmp_path / "state" / "attestation.sqlite3"
    path.parent.mkdir(mode=0o700)
    first = SQLiteChallengeLedger(path)
    challenge = "a" * 64
    assert first.consume(challenge, now=100) is True
    assert first.consume(challenge, now=101) is False

    reopened = SQLiteChallengeLedger(path)
    assert reopened.consume(challenge, now=102) is False
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_concurrent_consumers_have_exactly_one_winner(tmp_path):
    ledger_path = tmp_path / "attestation.sqlite3"
    ledgers = [SQLiteChallengeLedger(ledger_path) for _ in range(8)]
    challenge = "b" * 64
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda item: item.consume(challenge, now=200), ledgers))
    assert results.count(True) == 1
    assert results.count(False) == 7


@pytest.mark.parametrize("challenge", ["", "A" * 64, "g" * 64, "a" * 63, "a" * 65])
def test_ledger_rejects_malformed_challenges(tmp_path, challenge):
    ledger = SQLiteChallengeLedger(tmp_path / "attestation.sqlite3")
    with pytest.raises(ValueError):
        ledger.consume(challenge)


def test_ledger_rejects_symlink_database_path(tmp_path):
    target = tmp_path / "target.sqlite3"
    target.write_text("not a database")
    link = tmp_path / "attestation.sqlite3"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        SQLiteChallengeLedger(link)


def test_ledger_persists_only_challenge_digests(tmp_path):
    import hashlib

    challenge = "c" * 64
    path = tmp_path / "attestation.sqlite3"
    ledger = SQLiteChallengeLedger(path)
    assert ledger.consume(challenge) is True
    raw = path.read_bytes()
    assert challenge.encode("ascii") not in raw
    assert hashlib.sha256(challenge.encode("ascii")).hexdigest().encode("ascii") in raw


def test_ledger_rejects_non_private_parent_directory(tmp_path):
    parent = tmp_path / "shared"
    parent.mkdir(mode=0o700)
    os.chmod(parent, 0o755)
    with pytest.raises(ValueError, match="owner-owned and private"):
        SQLiteChallengeLedger(parent / "attestation.sqlite3")
