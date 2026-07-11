"""Cross-module E2E: Rust gateway + Python CLI dispatch + SQLite as one system.

Covers the seam no per-package suite exercises (deep-audit F14): the gateway
binary spawned as a real process, dispatching real `atlas` CLI writes
(D-022), against an isolated ATLAS_DB — then reading its own writes back over
HTTP (missions, the /v1/runs feed, audit events).

Run: python -m pytest tests/e2e -q   (from the repo root)
Skips when the gateway binary is not built.
"""
from __future__ import annotations

import json
import os
import pathlib
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
AGENT_RUNTIME = REPO_ROOT / "services" / "agent-runtime"
sys.path.insert(0, str(AGENT_RUNTIME))

from atlas_runtime import db as atlas_db  # noqa: E402


def _gateway_binary() -> pathlib.Path | None:
    env = os.environ.get("ATLAS_GATEWAY_BIN", "").strip()
    if env and pathlib.Path(env).is_file():
        return pathlib.Path(env)
    name = "atlas-gateway.exe" if os.name == "nt" else "atlas-gateway"
    for profile in ("release", "debug"):
        candidate = REPO_ROOT / "native" / "atlas-core-rs" / "target" / profile / name
        if candidate.is_file():
            return candidate
    return None


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _get(base: str, path: str) -> dict:
    with urllib.request.urlopen(f"{base}{path}", timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post(base: str, path: str, body: dict) -> dict:
    request = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


@pytest.fixture(scope="module")
def gateway(tmp_path_factory):
    binary = _gateway_binary()
    if binary is None:
        pytest.skip("atlas-gateway binary not built (cargo build -p atlas-gateway)")

    home = tmp_path_factory.mktemp("atlas-home")
    db_path = home / "atlas.db"
    conn = atlas_db.connect(db_path)
    atlas_db.apply_migrations(conn)
    conn.close()

    port = _free_port()
    env = os.environ.copy()
    env.update(
        {
            "ATLAS_HOME": str(home),
            "ATLAS_DB": str(db_path),
            "ATLAS_GATEWAY_PORT": str(port),
            "ATLAS_REPO_ROOT": str(REPO_ROOT),
            # Dispatch writes through this interpreter's atlas_runtime — the
            # env-aware db.default_db_path() makes the CLI hit ATLAS_DB above.
            "ATLAS_CLI": f"{sys.executable} -m atlas_runtime.cli.main",
            "PYTHONPATH": str(AGENT_RUNTIME),
        }
    )
    proc = subprocess.Popen(
        [str(binary)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 15
        while True:
            try:
                _get(base, "/health")
                break
            except (urllib.error.URLError, ConnectionError):
                if time.monotonic() > deadline:
                    proc.terminate()
                    pytest.fail("gateway did not become healthy in 15s")
                time.sleep(0.3)
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_mission_run_audit_round_trip(gateway: str) -> None:
    if " " in sys.executable:
        pytest.skip("interpreter path contains spaces; ATLAS_CLI cannot be tokenized")

    # 1. Create a mission over HTTP -> gateway dispatches `atlas mission create`.
    created = _post(gateway, "/v1/missions", {"title": "e2e mission", "intent": "prove the seam"})
    mission_id = created["mission"]["id"]
    assert created["mission"]["title"] == "e2e mission"

    # 2. The gateway reads its own dispatched write back.
    missions = _get(gateway, "/v1/missions")
    assert any(m["id"] == mission_id for m in missions["missions"])

    # 3. Start a run (record-only: execute defaults false, deterministic).
    started = _post(gateway, f"/v1/missions/{mission_id}/run", {"agent": "native"})
    run_id = started["run"]["id"]
    assert started["run"]["status"] == "running"
    assert started["executing"] is False

    # 4. Cross-mission run feed (F10 endpoint) joins the mission title.
    runs = _get(gateway, "/v1/runs")
    match = next((r for r in runs["runs"] if r["id"] == run_id), None)
    assert match is not None
    assert match["mission_title"] == "e2e mission"

    # 5. The start transition was audited (audit-first runtime, D-002).
    events = _get(gateway, f"/v1/runs/{run_id}/events")
    payloads = [e.get("data", {}) for e in events["events"]]
    assert any(p.get("transition") == "started" for p in payloads)
