from concurrent.futures import ThreadPoolExecutor
import multiprocessing
import sqlite3

import pytest

from core.storage import TenantKey
from core.sqlite_security_store import DurableAuditEvent, SQLiteSecurityStore


@pytest.fixture
def security_store(tmp_path):
    return SQLiteSecurityStore(tmp_path / "security.sqlite3")


def test_nonce_is_single_use_and_tenant_scoped(security_store):
    alice = TenantKey("https://issuer.example", "alice")
    bob = TenantKey("https://issuer.example", "bob")
    assert security_store.consume_approval_nonce(alice, "nonce-1", 500, now=100)
    assert not security_store.consume_approval_nonce(alice, "nonce-1", 500, now=100)
    assert security_store.consume_approval_nonce(bob, "nonce-1", 500, now=100)


def test_expired_nonce_is_rejected(security_store):
    tenant = TenantKey("https://issuer.example", "alice")
    assert not security_store.consume_approval_nonce(tenant, "expired", 100, now=100)


def test_invalid_nonce_inputs_fail_closed(security_store):
    tenant = TenantKey("https://issuer.example", "alice")
    assert not security_store.consume_approval_nonce(tenant, "", 500, now=100)
    assert not security_store.consume_approval_nonce(tenant, "n", True, now=100)


def test_concurrent_duplicate_nonce_has_exactly_one_winner(security_store):
    tenant = TenantKey("https://issuer.example", "alice")
    def attempt(_):
        return security_store.consume_approval_nonce(tenant, "race-nonce", 500, now=100)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(16)))
    assert sum(results) == 1


def test_nonce_persists_after_store_reopen(tmp_path):
    path = tmp_path / "security.sqlite3"
    tenant = TenantKey("https://issuer.example", "alice")
    assert SQLiteSecurityStore(path).consume_approval_nonce(tenant, "persist", 500, now=100)
    assert not SQLiteSecurityStore(path).consume_approval_nonce(tenant, "persist", 500, now=100)


def test_audit_events_are_payload_free_and_chain_verifies(security_store):
    event = DurableAuditEvent(
        action="project.update",
        result="denied",
        reason_code="tenant_mismatch",
        principal_fingerprint="sha256:principal",
        request_id="req-123",
    )
    security_store.append_audit_event(event)
    security_store.append_audit_event(
        DurableAuditEvent("project.read", "allowed", "ok", "sha256:principal", "req-124")
    )
    assert security_store.verify_audit_chain()


def test_audit_event_rejects_payload_like_or_unbounded_fields(security_store):
    with pytest.raises(ValueError):
        security_store.append_audit_event(
            DurableAuditEvent("x" * 257, "ok", "ok", "fp", "req")
        )


def test_audit_chain_detects_modified_row(security_store, tmp_path):
    path = tmp_path / "tamper.sqlite3"
    store = SQLiteSecurityStore(path)
    store.append_audit_event(DurableAuditEvent("action", "ok", "ok", "fp", "req"))
    import sqlite3
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE durable_audit_events SET action = 'tampered'")
    assert not store.verify_audit_chain()


def test_execution_audit_adapter_satisfies_gateway_append_verify_contract(tmp_path):
    from types import SimpleNamespace
    from core.sqlite_security_store import SQLiteExecutionAuditLog

    store = SQLiteSecurityStore(tmp_path / "adapter.sqlite3")
    tenant = TenantKey("https://issuer.example", "alice")
    audit = SQLiteExecutionAuditLog(store, tenant)
    assert audit.verify() == audit.GENESIS
    audit.append(SimpleNamespace(action="project.create", executed=False, reason="denied"))
    assert audit.verify() != audit.GENESIS
    assert store.verify_audit_chain()


def test_execution_audit_adapter_persists_only_principal_fingerprint(tmp_path):
    from types import SimpleNamespace
    import sqlite3
    from core.sqlite_security_store import SQLiteExecutionAuditLog

    path = tmp_path / "adapter.sqlite3"
    store = SQLiteSecurityStore(path)
    audit = SQLiteExecutionAuditLog(store, TenantKey("https://issuer.example", "alice"))
    audit.append(SimpleNamespace(action="project.create", executed=False, reason="denied"))
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT principal_fingerprint FROM durable_audit_events"
        ).fetchone()
    assert row[0] == __import__("hashlib").sha256(
        b"https://issuer.example\nalice"
    ).hexdigest()
    assert "alice" not in row[0]


def test_audit_append_fails_closed_when_existing_chain_is_tampered(tmp_path):
    import sqlite3

    path = tmp_path / "tampered-before-append.sqlite3"
    store = SQLiteSecurityStore(path)
    store.append_audit_event(DurableAuditEvent("first", "ok", "ok", "fp", "req-1"))
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE durable_audit_events SET action = 'forged'")
    with pytest.raises(ValueError, match="audit"):
        store.append_audit_event(DurableAuditEvent("second", "ok", "ok", "fp", "req-2"))


def test_audit_chain_detects_deleted_tail_row(tmp_path):
    import sqlite3

    path = tmp_path / "tail-truncated.sqlite3"
    store = SQLiteSecurityStore(path)
    store.append_audit_event(DurableAuditEvent("one", "ok", "ok", "fp", "req-1"))
    store.append_audit_event(DurableAuditEvent("two", "ok", "ok", "fp", "req-2"))
    with sqlite3.connect(path) as connection:
        connection.execute(
            "DELETE FROM durable_audit_events WHERE sequence = "
            "(SELECT MAX(sequence) FROM durable_audit_events)"
        )
    assert not store.verify_audit_chain()
    with pytest.raises(ValueError, match="tail entries"):
        store.append_audit_event(DurableAuditEvent("three", "ok", "ok", "fp", "req-3"))


def test_audit_chain_detects_deletion_of_all_rows(tmp_path):
    import sqlite3

    path = tmp_path / "all-rows-deleted.sqlite3"
    store = SQLiteSecurityStore(path)
    store.append_audit_event(DurableAuditEvent("one", "ok", "ok", "fp", "req-1"))
    with sqlite3.connect(path) as connection:
        connection.execute("DELETE FROM durable_audit_events")
    assert not store.verify_audit_chain()


def test_security_database_file_permissions_are_restricted(tmp_path):
    import os

    path = tmp_path / "private" / "security.sqlite3"
    SQLiteSecurityStore(path)
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.skipif(not hasattr(__import__("os"), "symlink"), reason="symlinks unavailable")
def test_security_database_preexisting_file_permissions_are_restricted(tmp_path):
    import os

    path = tmp_path / "security-existing.sqlite3"
    path.write_bytes(b"")
    if os.name == "posix":
        path.chmod(0o644)

    SQLiteSecurityStore(path)

    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.skipif(__import__("os").name != "posix", reason="POSIX directory permissions required")
def test_security_database_rejects_shared_parent_directory(tmp_path):
    import os

    shared_dir = tmp_path / "shared"
    shared_dir.mkdir(mode=0o700)
    shared_dir.chmod(0o755)

    with pytest.raises(ValueError, match="parent directory must be owner-only"):
        SQLiteSecurityStore(shared_dir / "security.sqlite3")

    assert not (shared_dir / "security.sqlite3").exists()


def test_security_database_rejects_symlink_target(tmp_path):
    target = tmp_path / "outside.sqlite3"
    target.write_bytes(b"do-not-open")
    link = tmp_path / "security.sqlite3"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is not permitted in this environment")

    with pytest.raises(ValueError, match="non-symlink"):
        SQLiteSecurityStore(link)
    assert target.read_bytes() == b"do-not-open"


def test_security_database_rejects_symlinked_parent_directory(tmp_path):
    target_dir = tmp_path / "actual"
    target_dir.mkdir()
    link_dir = tmp_path / "linked"
    try:
        link_dir.symlink_to(target_dir, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation is not permitted in this environment")

    with pytest.raises(ValueError, match="parent path.*symlinks"):
        SQLiteSecurityStore(link_dir / "security.sqlite3")
    assert not (target_dir / "security.sqlite3").exists()


@pytest.mark.skipif(__import__("os").name != "posix", reason="POSIX file permissions required")
def test_security_sqlite_wal_sidecars_have_owner_only_permissions(tmp_path):
    import os

    path = tmp_path / "security.sqlite3"
    store = SQLiteSecurityStore(path)
    connection = store._connect()
    try:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() == "wal"
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("CREATE TABLE sidecar_permission_probe (value TEXT)")

        for suffix in ("-wal", "-shm"):
            sidecar = path.with_name(path.name + suffix)
            assert sidecar.exists()
            assert sidecar.stat().st_mode & 0o777 == 0o600
        assert path.stat().st_mode & 0o777 == 0o600
    finally:
        connection.rollback()
        connection.close()


@pytest.mark.skipif(__import__("os").name != "posix", reason="POSIX file permissions required")
def test_security_sqlite_rollback_journal_has_owner_only_permissions(tmp_path):
    import os

    path = tmp_path / "rollback-journal.sqlite3"
    store = SQLiteSecurityStore(path)
    connection = store._connect()
    try:
        assert connection.execute("PRAGMA journal_mode=DELETE").fetchone()[0].lower() == "delete"
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("CREATE TABLE rollback_journal_permission_probe (value TEXT)")

        journal = path.with_name(path.name + "-journal")
        assert journal.exists()
        assert journal.stat().st_mode & 0o777 == 0o600
        assert path.stat().st_mode & 0o777 == 0o600
    finally:
        connection.rollback()
        connection.close()


def test_nonce_expiry_cleanup_rolls_back_when_insert_fails(tmp_path):
    import sqlite3

    path = tmp_path / "nonce-rollback.sqlite3"
    store = SQLiteSecurityStore(path)
    tenant = TenantKey("https://issuer.example", "alice")
    assert store.consume_approval_nonce(tenant, "expired-row", 150, now=100)

    trigger_connection = sqlite3.connect(path)
    try:
        trigger_connection.execute(
            """CREATE TRIGGER reject_nonce_insert
               BEFORE INSERT ON consumed_approval_nonces
               WHEN NEW.nonce = 'new-row'
               BEGIN SELECT RAISE(ABORT, 'forced nonce insert failure'); END"""
        )
        trigger_connection.commit()
    finally:
        trigger_connection.close()

    # Duplicate/constraint-style nonce insertion failures are deliberately
    # handled as a rejected nonce by the store API (False), not propagated.
    assert not store.consume_approval_nonce(tenant, "new-row", 500, now=200)

    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT nonce FROM consumed_approval_nonces ORDER BY nonce"
        ).fetchall()
    # The expiry cleanup and failed insert share one transaction: rollback
    # must restore the row deleted during cleanup.
    assert rows == [("expired-row",)]


def test_audit_append_rolls_back_when_sqlite_insert_fails(tmp_path):
    import sqlite3

    path = tmp_path / "audit-rollback.sqlite3"
    store = SQLiteSecurityStore(path)
    first_hash = store.append_audit_event(
        DurableAuditEvent("first", "ok", "ok", "fp", "req-1")
    )

    with sqlite3.connect(path) as connection:
        connection.execute(
            """CREATE TRIGGER reject_audit_insert
               BEFORE INSERT ON durable_audit_events
               BEGIN SELECT RAISE(ABORT, 'forced audit insert failure'); END"""
        )

    with pytest.raises(sqlite3.IntegrityError, match="forced audit insert failure"):
        store.append_audit_event(
            DurableAuditEvent("second", "ok", "ok", "fp", "req-2")
        )

    assert store.verify_audit_chain()
    assert store.last_audit_hash() == first_hash
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM durable_audit_events"
        ).fetchone()[0] == 1


def test_security_store_rejects_unvalidated_tenant_before_database_access(tmp_path):
    store = SQLiteSecurityStore(tmp_path / "invalid-tenant.sqlite3")
    with pytest.raises(TypeError, match="validated TenantKey"):
        store.consume_approval_nonce(("issuer", "alice"), "nonce", 500, now=100)


def _consume_nonce_in_process(database_path, gate, ready_queue, result_queue):
    store = SQLiteSecurityStore(database_path, timeout=20)
    ready_queue.put(True)
    if not gate.wait(timeout=30):
        result_queue.put(("error", "start gate timed out"))
        return
    result_queue.put((
        "ok",
        store.consume_approval_nonce(
            TenantKey("https://issuer.example", "alice"),
            "multiprocess-race-nonce",
            500,
            now=100,
        ),
    ))


def _append_audit_in_process(database_path, gate, ready_queue, result_queue, index):
    store = SQLiteSecurityStore(database_path, timeout=20)
    ready_queue.put(True)
    if not gate.wait(timeout=30):
        result_queue.put(("error", "start gate timed out"))
        return
    event = DurableAuditEvent(
        "concurrent.process.append",
        "ok",
        "ok",
        "process-fingerprint",
        f"process-request-{index}",
    )
    result_queue.put(("ok", store.append_audit_event(event)))


def _run_process_race(context, target, args, worker_count):
    gate = context.Event()
    ready_queue = context.Queue()
    result_queue = context.Queue()
    processes = [
        context.Process(target=target, args=(*args, gate, ready_queue, result_queue))
        for _ in range(worker_count)
    ]
    try:
        for process in processes:
            process.start()
        for _ in processes:
            ready_queue.get(timeout=45)
        gate.set()
        results = [result_queue.get(timeout=45) for _ in processes]
        for process in processes:
            process.join(timeout=45)
        assert all(not process.is_alive() for process in processes)
        assert all(process.exitcode == 0 for process in processes)
        assert all(status == "ok" for status, _ in results), results
        return [value for _, value in results]
    finally:
        gate.set()
        for process in processes:
            if process.is_alive():
                process.terminate()
            process.join(timeout=5)
        ready_queue.close()
        result_queue.close()


def test_nonce_is_single_use_across_independent_processes(tmp_path):
    path = tmp_path / "multiprocess-nonce.sqlite3"
    SQLiteSecurityStore(path)
    context = multiprocessing.get_context("spawn")

    results = _run_process_race(
        context,
        _consume_nonce_in_process,
        (str(path),),
        worker_count=6,
    )

    assert sum(results) == 1
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM consumed_approval_nonces"
        ).fetchone()[0] == 1


def test_concurrent_process_audit_appends_preserve_one_valid_chain(tmp_path):
    path = tmp_path / "multiprocess-audit.sqlite3"
    store = SQLiteSecurityStore(path)
    context = multiprocessing.get_context("spawn")
    gate = context.Event()
    ready_queue = context.Queue()
    result_queue = context.Queue()
    processes = [
        context.Process(
            target=_append_audit_in_process,
            args=(str(path), gate, ready_queue, result_queue, index),
        )
        for index in range(6)
    ]
    try:
        for process in processes:
            process.start()
        for _ in processes:
            ready_queue.get(timeout=45)
        gate.set()
        results = [result_queue.get(timeout=45) for _ in processes]
        for process in processes:
            process.join(timeout=45)
        assert all(not process.is_alive() for process in processes)
        assert all(process.exitcode == 0 for process in processes)
        assert all(status == "ok" for status, _ in results), results
    finally:
        gate.set()
        for process in processes:
            if process.is_alive():
                process.terminate()
            process.join(timeout=5)
        ready_queue.close()
        result_queue.close()

    hashes = [value for _, value in results]
    assert len(set(hashes)) == 6
    assert store.verify_audit_chain()
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM durable_audit_events"
        ).fetchone()[0] == 6

def _crash_with_uncommitted_nonce(database_path, ready_queue):
    import os
    import sqlite3

    connection = sqlite3.connect(database_path, isolation_level=None)
    connection.execute("BEGIN IMMEDIATE")
    connection.execute(
        """INSERT INTO consumed_approval_nonces
           (issuer, subject, nonce, expires_at, consumed_at)
           VALUES (?, ?, ?, ?, ?)""",
        ("https://issuer-crash.example", "crash-owner", "crash-uncommitted-nonce", 9999999999, 100),
    )
    ready_queue.put(True)
    # Simulate abrupt process termination without commit, rollback, or close.
    os._exit(0)


def test_sqlite_recovers_uncommitted_nonce_after_process_crash(tmp_path):
    path = tmp_path / "security-crash-recovery.sqlite3"
    store = SQLiteSecurityStore(path)
    tenant = TenantKey("https://issuer-crash.example", "crash-owner")
    assert store.consume_approval_nonce(tenant, "committed-nonce", 9999999999, now=100)

    context = multiprocessing.get_context("spawn")
    ready_queue = context.Queue()
    process = context.Process(
        target=_crash_with_uncommitted_nonce,
        args=(str(path), ready_queue),
    )
    process.start()
    try:
        assert ready_queue.get(timeout=30) is True
        process.join(timeout=30)
        assert not process.is_alive()
        assert process.exitcode == 0
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
        ready_queue.close()

    recovered = SQLiteSecurityStore(path)
    assert not recovered.consume_approval_nonce(
        tenant, "crash-uncommitted-nonce", 9999999999, now=100
    ) is False
    with sqlite3.connect(path) as connection:
        nonces = connection.execute(
            "SELECT nonce FROM consumed_approval_nonces ORDER BY nonce"
        ).fetchall()
    assert nonces == [("committed-nonce",)]

