"""Tests for `session_message_service` — durable conversation history (0030).

Covers the contract the cockpit and the agent write path depend on: monotonic
per-session seq, redaction at the persistence boundary, windowed reads in both
directions, and FTS search (which also proves the migration's external-content
FTS triggers actually work end to end).
"""
from __future__ import annotations

import multiprocessing
import queue
import sqlite3
import threading
import time

import pytest

from atlas_runtime import db as atlas_db
from atlas_runtime import session_message_service as svc


def _append(db, lock, session, role, content, **kw):
    return svc.append_message(
        db, lock, surface_session_id=session, role=role, content=content, **kw
    )


def _file_backed_copy(db, tmp_path):
    path = tmp_path / "session-messages.db"
    target = atlas_db.connect(path)
    db.backup(target)
    target.close()
    return path


def _process_writer(db_path, session_id, writer_id, count, start, failures):
    conn = atlas_db.connect(db_path)
    try:
        start.wait(timeout=10)
        for index in range(count):
            svc.append_message(
                conn,
                threading.Lock(),
                surface_session_id=session_id,
                role="user",
                content=f"p{writer_id}-{index}",
            )
    except BaseException as exc:  # noqa: BLE001 — reported to the parent process
        failures.put(repr(exc))
    finally:
        conn.close()


def test_seq_is_monotonic_per_session(db, lock, surface_session):
    first = _append(db, lock, surface_session, "user", "one")
    second = _append(db, lock, surface_session, "assistant", "two")
    third = _append(db, lock, surface_session, "user", "three")
    assert [first["seq"], second["seq"], third["seq"]] == [1, 2, 3]


def test_seq_is_scoped_to_one_session(db, lock, surface_session):
    import datetime
    import uuid

    other = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT INTO surface_sessions"
        "(id, surface_kind, surface_session_id, workspace_kind, workspace_root, "
        "agent, model_provider, model_id, permission_mode, prompt_version, "
        "tool_catalog_version, context_policy_version, state, heartbeat_at, "
        "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            other, "cli", "surf-2", "global", "/tmp/atlas", "atlas", "anthropic",
            "claude-opus-4", "ask", "1.0.0", "1.0.0", "1.0.0", "starting", now, now, now,
        ),
    )
    db.commit()

    _append(db, lock, surface_session, "user", "a")
    _append(db, lock, surface_session, "user", "b")
    assert _append(db, lock, other, "user", "c")["seq"] == 1


def test_token_count_is_computed_at_write_time(db, lock, surface_session):
    stored = _append(db, lock, surface_session, "user", "x" * 400)
    assert stored["token_count"] == 100


def test_content_is_redacted_before_persistence(db, lock, surface_session):
    """A transcript is exactly where a pasted credential ends up."""
    stored = _append(
        db, lock, surface_session, "user", 'here is my api_key="sk-live-abcdef123456"'
    )
    assert "sk-live-abcdef123456" not in stored["content"]
    assert "[REDACTED]" in stored["content"]
    on_disk = db.execute(
        "SELECT content FROM session_messages WHERE id=?", (stored["id"],)
    ).fetchone()[0]
    assert "sk-live-abcdef123456" not in on_disk


def test_invalid_role_is_rejected_before_sql(db, lock, surface_session):
    with pytest.raises(ValueError, match="invalid role"):
        _append(db, lock, surface_session, "operator", "nope")


def test_unknown_session_violates_the_foreign_key(db, lock):
    with pytest.raises(sqlite3.IntegrityError):
        _append(db, lock, "no-such-session", "user", "orphan")


def test_tool_metadata_round_trips(db, lock, surface_session, run_id):
    stored = _append(
        db, lock, surface_session, "tool", "exit 0",
        run_id=run_id, tool_call_id="call_7", tool_name="workspace",
        metadata={"exit_code": 0},
    )
    assert stored["tool_call_id"] == "call_7"
    assert stored["tool_name"] == "workspace"
    assert stored["metadata"] == {"exit_code": 0}
    assert stored["run_id"] == run_id


def test_list_messages_returns_the_newest_window_oldest_first(db, lock, surface_session):
    for i in range(5):
        _append(db, lock, surface_session, "user", f"m{i}")
    page = svc.list_messages(db, surface_session, limit=2)
    assert [m["content"] for m in page["messages"]] == ["m3", "m4"]
    assert page["total"] == 5
    assert page["has_more"] is True


def test_list_messages_pages_backwards_with_before_seq(db, lock, surface_session):
    for i in range(5):
        _append(db, lock, surface_session, "user", f"m{i}")
    page = svc.list_messages(db, surface_session, limit=2, before_seq=4)
    assert [m["content"] for m in page["messages"]] == ["m1", "m2"]
    assert page["has_more"] is True


def test_list_messages_pages_forward_with_after_seq(db, lock, surface_session):
    for i in range(5):
        _append(db, lock, surface_session, "user", f"m{i}")
    page = svc.list_messages(db, surface_session, limit=10, after_seq=3)
    assert [m["content"] for m in page["messages"]] == ["m3", "m4"]
    assert page["has_more"] is False


def test_has_more_is_false_when_the_window_covers_everything(db, lock, surface_session):
    _append(db, lock, surface_session, "user", "only")
    page = svc.list_messages(db, surface_session, limit=50)
    assert page["has_more"] is False
    assert page["total"] == 1


def test_search_finds_a_message_by_content(db, lock, surface_session):
    _append(db, lock, surface_session, "user", "the deployment pipeline broke")
    _append(db, lock, surface_session, "assistant", "unrelated answer")
    hits = svc.search_messages(db, "pipeline")
    assert [h["content"] for h in hits] == ["the deployment pipeline broke"]


def test_search_can_be_scoped_to_one_session(db, lock, surface_session):
    _append(db, lock, surface_session, "user", "shared keyword here")
    assert svc.search_messages(db, "keyword", surface_session_id=surface_session)
    assert svc.search_messages(db, "keyword", surface_session_id="other") == []


def test_search_index_drops_deleted_rows(db, lock, surface_session):
    """The migration's FTS delete trigger must subtract the same text it indexed."""
    stored = _append(db, lock, surface_session, "user", "ephemeral phrase")
    db.execute("DELETE FROM session_messages WHERE id=?", (stored["id"],))
    db.commit()
    assert svc.search_messages(db, "ephemeral") == []


@pytest.mark.parametrize(
    "query",
    [
        'unbalanced "quote',  # bundled SQLite: "unterminated string"
        "dangling OR",  # bundled SQLite: 'fts5: syntax error near ""'
        ")",  # bundled SQLite: 'fts5: syntax error near ")"'
    ],
)
def test_malformed_search_query_returns_empty_not_an_error(
    db, lock, surface_session, query
):
    _append(db, lock, surface_session, "user", "anything")
    assert svc.search_messages(db, query) == []


class _FailingSearchConnection:
    def __init__(self, error: sqlite3.OperationalError):
        self.error = error

    def execute(self, _sql, _params):
        raise self.error


def _operational_error(message: str, code: int) -> sqlite3.OperationalError:
    error = sqlite3.OperationalError(message)
    error.sqlite_errorcode = code
    return error


@pytest.mark.parametrize(
    ("message", "code"),
    [
        ("database is locked", sqlite3.SQLITE_BUSY),
        ("database table is locked", sqlite3.SQLITE_LOCKED),
        ("no such table: session_messages_fts", sqlite3.SQLITE_ERROR),
        ('near "SELECT": syntax error', sqlite3.SQLITE_ERROR),
        ("disk I/O error", sqlite3.SQLITE_IOERR),
        ("database disk image is malformed", sqlite3.SQLITE_CORRUPT),
    ],
)
def test_search_propagates_non_fts_operational_errors(message, code):
    error = _operational_error(message, code)

    with pytest.raises(sqlite3.OperationalError) as raised:
        svc.search_messages(_FailingSearchConnection(error), "anything")

    assert raised.value is error


def test_search_requires_sqlite_error_code_before_downgrading_fts_message():
    error = _operational_error("unterminated string", sqlite3.SQLITE_BUSY)

    with pytest.raises(sqlite3.OperationalError) as raised:
        svc.search_messages(_FailingSearchConnection(error), "anything")

    assert raised.value is error


def test_session_token_total_sums_stored_counts(db, lock, surface_session):
    _append(db, lock, surface_session, "user", "x" * 400)
    _append(db, lock, surface_session, "assistant", "y" * 200)
    assert svc.session_token_total(db, surface_session) == 150


def test_concurrent_appends_never_collide_on_seq(db, lock, surface_session):
    """The UNIQUE (session, seq) index is the guard; the retry loop is the recovery."""
    errors: list[BaseException] = []

    def _writer(n: int) -> None:
        try:
            for i in range(5):
                _append(db, lock, surface_session, "user", f"w{n}-{i}")
        except BaseException as exc:  # noqa: BLE001 — surfaced by the assert below
            errors.append(exc)

    threads = [threading.Thread(target=_writer, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, errors
    seqs = [r[0] for r in db.execute(
        "SELECT seq FROM session_messages WHERE surface_session_id=? ORDER BY seq",
        (surface_session,),
    )]
    assert seqs == list(range(1, 21))


def test_common_connection_has_explicit_bounded_busy_timeout(tmp_path):
    conn = atlas_db.connect(tmp_path / "timeout.db")
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == (
            atlas_db.SQLITE_BUSY_TIMEOUT_MS
        )
        assert 0 < atlas_db.SQLITE_BUSY_TIMEOUT_MS <= 1000
    finally:
        conn.close()


def test_independent_connections_allocate_contiguous_sequences(
    db, surface_session, tmp_path
):
    path = _file_backed_copy(db, tmp_path)
    connections = [atlas_db.connect(path) for _ in range(4)]
    barrier = threading.Barrier(len(connections))
    failures: list[BaseException] = []

    def writer(index, conn):
        try:
            barrier.wait(timeout=5)
            for message in range(10):
                svc.append_message(
                    conn,
                    threading.Lock(),
                    surface_session_id=surface_session,
                    role="user",
                    content=f"c{index}-{message}",
                )
        except BaseException as exc:  # noqa: BLE001 — surfaced below
            failures.append(exc)

    threads = [
        threading.Thread(target=writer, args=(index, conn))
        for index, conn in enumerate(connections)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    for conn in connections:
        conn.close()

    assert not failures, failures
    reader = atlas_db.connect(path)
    try:
        seqs = [
            row[0]
            for row in reader.execute(
                "SELECT seq FROM session_messages WHERE surface_session_id=? "
                "ORDER BY seq",
                (surface_session,),
            )
        ]
    finally:
        reader.close()
    assert seqs == list(range(1, 41))


def test_independent_processes_append_without_loss(db, surface_session, tmp_path):
    path = _file_backed_copy(db, tmp_path)
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    failures = context.Queue()
    process_count = 3
    messages_per_process = 8
    processes = [
        context.Process(
            target=_process_writer,
            args=(
                str(path),
                surface_session,
                writer,
                messages_per_process,
                start,
                failures,
            ),
        )
        for writer in range(process_count)
    ]
    for process in processes:
        process.start()
    start.set()
    for process in processes:
        process.join(timeout=15)
        assert process.exitcode == 0

    process_failures = []
    while True:
        try:
            process_failures.append(failures.get_nowait())
        except queue.Empty:
            break
    assert not process_failures

    reader = atlas_db.connect(path)
    try:
        seqs = [
            row[0]
            for row in reader.execute(
                "SELECT seq FROM session_messages WHERE surface_session_id=? "
                "ORDER BY seq",
                (surface_session,),
            )
        ]
    finally:
        reader.close()
    assert seqs == list(range(1, process_count * messages_per_process + 1))


def test_writer_lock_retries_then_succeeds_after_release(
    db, surface_session, tmp_path, monkeypatch
):
    path = _file_backed_copy(db, tmp_path)
    blocker = atlas_db.connect(path)
    writer = atlas_db.connect(path)
    writer.execute("PRAGMA busy_timeout = 1")
    blocker.execute("BEGIN IMMEDIATE")
    monkeypatch.setattr(svc, "_busy_backoff", lambda _attempt: 0.02)
    started = threading.Event()
    result = {}

    def append_after_lock():
        started.set()
        try:
            result["message"] = svc.append_message(
                writer,
                threading.Lock(),
                surface_session_id=surface_session,
                role="user",
                content="eventually durable",
            )
        except BaseException as exc:  # noqa: BLE001 — surfaced below
            result["error"] = exc

    thread = threading.Thread(target=append_after_lock)
    thread.start()
    assert started.wait(timeout=2)
    time.sleep(0.03)
    blocker.commit()
    thread.join(timeout=5)
    blocker.close()
    writer.close()

    assert "error" not in result
    assert result["message"]["seq"] == 1


def test_writer_lock_exhaustion_has_stable_classification(
    db, surface_session, tmp_path, monkeypatch
):
    path = _file_backed_copy(db, tmp_path)
    blocker = atlas_db.connect(path)
    writer = atlas_db.connect(path)
    writer.execute("PRAGMA busy_timeout = 1")
    blocker.execute("BEGIN IMMEDIATE")
    monkeypatch.setattr(svc, "_BUSY_RETRIES", 3)
    monkeypatch.setattr(svc, "_busy_backoff", lambda _attempt: 0)

    try:
        with pytest.raises(
            svc.DatabaseBusyExhausted, match="^database_busy_exhausted$"
        ) as raised:
            svc.append_message(
                writer,
                threading.Lock(),
                surface_session_id=surface_session,
                role="user",
                content="cannot persist yet",
            )
        assert raised.value.attempts == 3
        assert isinstance(raised.value.__cause__, sqlite3.OperationalError)
        assert svc._is_retryable_busy_error(raised.value.__cause__)
    finally:
        blocker.rollback()
        blocker.close()
        writer.close()


class _NonBusyConnection:
    in_transaction = False

    def __init__(self, error):
        self.error = error
        self.calls = 0

    def execute(self, _sql):
        self.calls += 1
        raise self.error


def test_non_busy_operational_error_is_not_retried(monkeypatch):
    error = _operational_error("disk I/O error", sqlite3.SQLITE_IOERR)
    conn = _NonBusyConnection(error)
    sleeps = []
    monkeypatch.setattr(svc.time, "sleep", sleeps.append)

    with pytest.raises(sqlite3.OperationalError) as raised:
        svc.append_message(
            conn,
            threading.Lock(),
            surface_session_id="session",
            role="user",
            content="message",
        )

    assert raised.value is error
    assert conn.calls == 1
    assert sleeps == []


def test_unique_constraint_failure_is_not_retried(
    db, lock, surface_session, monkeypatch
):
    fixed_id = "00000000-0000-0000-0000-000000000001"
    monkeypatch.setattr(svc.uuid, "uuid4", lambda: fixed_id)
    _append(db, lock, surface_session, "user", "first")
    sleeps = []
    monkeypatch.setattr(svc.time, "sleep", sleeps.append)

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        _append(db, lock, surface_session, "user", "duplicate id")

    assert sleeps == []
