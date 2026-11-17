from __future__ import annotations

import os
import pytest

from core.personal_auth import LocalOwnerAuthStore


def _store(tmp_path):
    return LocalOwnerAuthStore(tmp_path / ".apaa_personal" / "owner-auth.sqlite3")


def test_owner_auth_is_unconfigured_until_explicit_first_run_setup(tmp_path):
    store = _store(tmp_path)
    assert store.is_configured() is False
    assert store.authenticate("not configured") is False
    store.configure("correct horse battery staple", "correct horse battery staple")
    assert store.is_configured() is True


def test_owner_passphrase_is_scrypt_hashed_and_not_stored_in_database(tmp_path):
    store = _store(tmp_path)
    phrase = "correct horse battery staple"
    store.configure(phrase, phrase)
    raw = store.path.read_bytes()
    assert phrase.encode() not in raw
    assert len(raw) > 0
    if os.name == "posix":
        assert store.path.stat().st_mode & 0o077 == 0


def test_owner_auth_rejects_mismatch_and_short_passphrases(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(ValueError, match="at least 12"):
        store.configure("short", "short")
    with pytest.raises(ValueError, match="do not match"):
        store.configure("correct horse battery staple", "different passphrase")


def test_owner_auth_success_and_wrong_password(tmp_path):
    store = _store(tmp_path)
    store.configure("correct horse battery staple", "correct horse battery staple")
    assert store.authenticate("wrong password", now=1000) is False
    assert store.authenticate("correct horse battery staple", now=1001) is True


def test_owner_auth_persistent_lockout_survives_store_recreation(tmp_path):
    store = _store(tmp_path)
    store.configure("correct horse battery staple", "correct horse battery staple")
    for _ in range(5):
        assert store.authenticate("wrong password", now=1000) is False
    reopened = _store(tmp_path)
    assert reopened.authenticate("correct horse battery staple", now=1001) is False
    assert reopened.authenticate("correct horse battery staple", now=1299) is False
    assert reopened.authenticate("correct horse battery staple", now=1300) is True


def test_owner_auth_passphrase_rotation_requires_current_passphrase(tmp_path):
    store = _store(tmp_path)
    store.configure("correct horse battery staple", "correct horse battery staple")
    assert store.change_passphrase(
        "wrong password", "a replacement owner passphrase", "a replacement owner passphrase"
    ) is False
    assert store.change_passphrase(
        "correct horse battery staple",
        "a replacement owner passphrase",
        "a replacement owner passphrase",
    ) is True
    assert store.authenticate("correct horse battery staple", now=2000) is False
    assert store.authenticate("a replacement owner passphrase", now=2001) is True


def test_owner_auth_rejects_symlink_database(tmp_path):
    if os.name != "posix":
        pytest.skip("symlink permissions are POSIX-specific")
    real_dir = tmp_path / "real"
    real_dir.mkdir(mode=0o700)
    real = real_dir / "auth.sqlite3"
    real.write_bytes(b"")
    link = tmp_path / "link.sqlite3"
    link.symlink_to(real)
    with pytest.raises(ValueError, match="symlinks"):
        LocalOwnerAuthStore(link)


def test_owner_auth_security_events_are_payload_free_and_persisted(tmp_path):
    store = _store(tmp_path)
    store.configure("correct horse battery staple", "correct horse battery staple")
    assert store.authenticate("wrong password", now=1000) is False
    assert store.authenticate("correct horse battery staple", now=1001) is True
    assert store.change_passphrase(
        "wrong password", "a replacement owner passphrase",
        "a replacement owner passphrase", now=1002,
    ) is False
    assert store.change_passphrase(
        "correct horse battery staple", "a replacement owner passphrase",
        "a replacement owner passphrase", now=1003,
    ) is True
    reopened = _store(tmp_path)
    events = reopened.list_events()
    assert [event for event, _ in events] == [
        "passphrase_changed", "passphrase_change_failed",
        "login_success", "login_failed", "owner_setup",
    ]
    assert [timestamp for _, timestamp in events[:4]] == [1003, 1002, 1001, 1000]
    raw = reopened.path.read_bytes()
    assert b"correct horse battery staple" not in raw
    assert b"wrong password" not in raw
    assert b"replacement owner passphrase" not in raw


def test_owner_auth_event_api_rejects_unknown_event_and_invalid_limit(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(ValueError, match="Unsupported"):
        store.record_event("password_was_secret")
    with pytest.raises(ValueError, match="limit"):
        store.list_events(limit=0)


def test_owner_auth_event_hash_chain_detects_mutation_and_deletion(tmp_path):
    store = _store(tmp_path)
    store.configure("correct horse battery staple", "correct horse battery staple")
    assert store.authenticate("wrong password", now=1000) is False
    assert len(store.verify_events()) == 64
    import sqlite3
    with sqlite3.connect(store.path) as db:
        db.execute(
            "UPDATE local_owner_auth_events SET event_type=? WHERE event_id=2",
            ("login_success",),
        )
    with pytest.raises(ValueError, match="integrity"):
        store.list_events()


def test_owner_auth_event_hash_chain_is_verified_before_new_append(tmp_path):
    store = _store(tmp_path)
    store.configure("correct horse battery staple", "correct horse battery staple")
    import sqlite3
    with sqlite3.connect(store.path) as db:
        db.execute("DELETE FROM local_owner_auth_events WHERE event_id=1")
    with pytest.raises(ValueError, match="integrity"):
        store.record_event("logout", occurred_at=1001)
    with pytest.raises(ValueError, match="integrity"):
        store.list_events()


def test_legacy_owner_auth_events_are_migrated_to_hash_chain(tmp_path):
    import sqlite3
    path = tmp_path / ".apaa_personal" / "owner-auth.sqlite3"
    path.parent.mkdir(mode=0o700)
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE local_owner_auth_events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "event_type TEXT NOT NULL, occurred_at INTEGER NOT NULL)"
        )
        db.execute(
            "INSERT INTO local_owner_auth_events (event_type, occurred_at) VALUES (?, ?)",
            ("login_success", 1234),
        )
    store = LocalOwnerAuthStore(path)
    assert store.verify_events() != store._EVENT_GENESIS
    assert store.list_events() == (("login_success", 1234),)
