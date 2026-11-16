from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from core.sqlite_security_store import (
    GlobalOwnerStateConflict,
    SQLiteSecurityStore,
)


GEN_A = "a" * 64
GEN_B = "b" * 64


def test_owner_state_starts_unprovisioned_and_is_shared_across_instances(tmp_path):
    path = tmp_path / "owner-state.sqlite3"
    first = SQLiteSecurityStore(path)
    second = SQLiteSecurityStore(path)

    assert first.read_global_owner_state().revision == 0
    assert first.read_global_owner_state().generation is None

    updated = first.compare_and_set_global_owner_generation(
        expected_revision=0, generation=GEN_A, change_id="owner-change-001"
    )
    assert updated.revision == 1
    assert updated.generation == GEN_A
    assert second.read_global_owner_state() == updated
    assert second.verify_audit_chain()


def test_owner_state_rekey_and_revocation_advance_monotonic_revision(tmp_path):
    store = SQLiteSecurityStore(tmp_path / "owner-rekey.sqlite3")
    first = store.compare_and_set_global_owner_generation(
        expected_revision=0, generation=GEN_A, change_id="owner-change-101"
    )
    second = store.compare_and_set_global_owner_generation(
        expected_revision=first.revision, generation=GEN_B, change_id="owner-change-102"
    )
    revoked = store.compare_and_set_global_owner_generation(
        expected_revision=second.revision, generation=None, change_id="owner-revoke-103"
    )

    assert (first.revision, second.revision, revoked.revision) == (1, 2, 3)
    assert revoked.generation is None
    assert store.read_global_owner_state() == revoked
    assert store.verify_audit_chain()


def test_stale_revision_and_duplicate_generation_are_rejected(tmp_path):
    store = SQLiteSecurityStore(tmp_path / "owner-cas.sqlite3")
    store.compare_and_set_global_owner_generation(
        expected_revision=0, generation=GEN_A, change_id="owner-change-201"
    )
    with pytest.raises(GlobalOwnerStateConflict):
        store.compare_and_set_global_owner_generation(
            expected_revision=0, generation=GEN_B, change_id="owner-change-202"
        )
    with pytest.raises(ValueError, match="alter"):
        store.compare_and_set_global_owner_generation(
            expected_revision=1, generation=GEN_A, change_id="owner-change-203"
        )
    assert store.read_global_owner_state().generation == GEN_A
    assert store.verify_audit_chain()


def test_concurrent_owner_state_cas_has_exactly_one_winner(tmp_path):
    path = tmp_path / "owner-cas-race.sqlite3"
    SQLiteSecurityStore(path)

    def attempt(pair):
        generation, change_id = pair
        try:
            return SQLiteSecurityStore(path).compare_and_set_global_owner_generation(
                expected_revision=0, generation=generation, change_id=change_id
            )
        except GlobalOwnerStateConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [(GEN_A, "owner-race-301"), (GEN_B, "owner-race-302")]))
    winners = [result for result in results if result is not None]
    assert len(winners) == 1
    assert SQLiteSecurityStore(path).read_global_owner_state().revision == 1
    assert SQLiteSecurityStore(path).verify_audit_chain()


@pytest.mark.parametrize(
    "generation,change_id",
    [
        ("not-a-digest", "owner-change-401"),
        ("A" * 64, "owner-change-402"),
        ("a" * 64, "bad"),
        ("a" * 64, "contains spaces"),
    ],
)
def test_owner_state_rejects_malformed_inputs_without_mutation(tmp_path, generation, change_id):
    store = SQLiteSecurityStore(tmp_path / "owner-invalid.sqlite3")
    with pytest.raises(ValueError):
        store.compare_and_set_global_owner_generation(
            expected_revision=0, generation=generation, change_id=change_id
        )
    assert store.read_global_owner_state().revision == 0
    assert store.read_global_owner_state().generation is None
    assert store.verify_audit_chain()


def test_owner_state_change_and_audit_are_atomic_when_audit_chain_is_tampered(tmp_path):
    path = tmp_path / "owner-audit-atomic.sqlite3"
    store = SQLiteSecurityStore(path)
    store.append_audit_event(
        __import__("core.sqlite_security_store", fromlist=["DurableAuditEvent"]).DurableAuditEvent(
            "preexisting", "ok", "ok", "fp", "owner-audit-501"
        )
    )
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE durable_audit_events SET reason_code = 'tampered'")

    with pytest.raises(ValueError, match="audit"):
        store.compare_and_set_global_owner_generation(
            expected_revision=0, generation=GEN_A, change_id="owner-change-502"
        )

    assert store.read_global_owner_state().revision == 0
    assert store.read_global_owner_state().generation is None
    assert not store.verify_audit_chain()


def test_owner_audit_contains_change_metadata_not_raw_generation(tmp_path):
    path = tmp_path / "owner-audit-privacy.sqlite3"
    store = SQLiteSecurityStore(path)
    store.compare_and_set_global_owner_generation(
        expected_revision=0, generation=GEN_A, change_id="owner-change-601"
    )
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT action, result, reason_code, principal_fingerprint, request_id "
            "FROM durable_audit_events"
        ).fetchone()
    assert row == (
        "global_owner.generation.change",
        "committed",
        "operator_cas_update",
        "external_operator_identity_not_verified",
        "owner-change-601",
    )
    assert GEN_A not in repr(row)
