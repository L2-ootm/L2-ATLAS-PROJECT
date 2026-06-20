"""Tests for the runtime daemon (WP-1, b — in-process executor host).

Boots the HTTP server on an ephemeral port in a thread, enqueues a run, and
asserts it executes to a terminal state. Uses a temp FILE DB (the daemon and its
worker threads open their own connections).
"""
from __future__ import annotations

import datetime
import json
import threading
import urllib.error
import urllib.request
import uuid

import pytest

from atlas_runtime import db as db_module
from atlas_runtime import run_executor, runtime_daemon


@pytest.fixture(name="daemon")
def daemon_fixture(tmp_path):
    path = tmp_path / "atlas.db"
    conn = db_module.connect(path)
    db_module.apply_migrations(conn)
    # A pending mission to enqueue.
    mid = uuid.uuid4().hex
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with conn:
        conn.execute(
            "INSERT INTO missions(id,title,intent,status,project,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (mid, "daemon test", "", "pending", "", now, now),
        )
    server = runtime_daemon.make_server("127.0.0.1", 0, db_path=str(path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base = f"http://{host}:{port}"
    try:
        yield base, mid, path
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        conn.close()


def _get(url: str):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, json.loads(resp.read())


def _post(url: str, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read())


def test_health(daemon):
    base, _mid, _path = daemon
    status, body = _get(f"{base}/health")
    assert status == 200 and body["status"] == "ok"


def test_enqueue_executes_run(daemon):
    base, mid, path = daemon
    status, body = _post(f"{base}/v1/runs/enqueue", {"mission_id": mid, "agent": "native"})
    assert status == 201
    run_id = body["run_id"]
    assert body["executing"] is True
    # Worker thread is tracked in the shared executor registry; await it.
    assert run_executor.await_run(run_id, timeout=5) is True
    conn = db_module.connect(path)
    try:
        assert conn.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()[0] == "succeeded"
    finally:
        conn.close()


def test_enqueue_requires_mission_id(daemon):
    base, _mid, _path = daemon
    try:
        _post(f"{base}/v1/runs/enqueue", {"agent": "native"})
        assert False, "expected HTTP 400"
    except urllib.error.HTTPError as exc:
        assert exc.code == 400
