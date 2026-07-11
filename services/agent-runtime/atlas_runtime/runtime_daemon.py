"""ATLAS runtime daemon — long-lived in-process run executor host (WP-1, b).

The alternative to the gateway's detached-subprocess execution (a): a single
long-lived Python process that hosts the in-process async executor
(`run_executor.start_and_execute_async`) and exposes a tiny HTTP API the gateway
(or any client) can POST runs to. Background runs execute on daemon-managed
threads, so the daemon can introspect (`active_run_ids`) and shut down
gracefully — unlike fire-and-forget subprocesses.

Endpoints:
  GET  /health           -> {"status":"ok"}
  GET  /v1/runs/active   -> {"active":[run_id, ...]}
  POST /v1/runs/enqueue  {mission_id, agent?} -> 201 {"run_id":..., "executing":true}

Single-operator scale: ThreadingHTTPServer + a shared WAL connection
(check_same_thread=False) with the run_service lock serializing writes; each
background run opens its own connection via the executor's conn_factory.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from atlas_runtime import db, run_executor


class _Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args) -> None:  # silence default stderr logging
        pass

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, {"status": "ok"})
        elif self.path == "/v1/runs/active":
            self._send(200, {"active": run_executor.active_run_ids()})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/v1/runs/enqueue":
            self._send(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw or b"{}")
        except ValueError:
            self._send(400, {"error": "invalid JSON"})
            return
        mission_id = str(data.get("mission_id") or "").strip()
        agent = str(data.get("agent") or "native").strip() or "native"
        if not mission_id:
            self._send(400, {"error": "mission_id required"})
            return
        server = self.server  # carries conn/lock/conn_factory (set in make_server)
        try:
            run = run_executor.start_and_execute_async(
                server.conn,  # type: ignore[attr-defined]
                server.lock,  # type: ignore[attr-defined]
                mission_id=mission_id,
                agent_name=agent,
                conn_factory=server.conn_factory,  # type: ignore[attr-defined]
            )
        except Exception as exc:  # unknown agent / mission not pending / etc.
            self._send(400, {"error": str(exc)})
            return
        self._send(201, {"run_id": run.id, "executing": True})


def make_server(host: str, port: int, *, db_path: Optional[str] = None) -> ThreadingHTTPServer:
    """Build (but do not start) the daemon HTTP server with a shared connection.

    Exposed for tests: bind port 0 for an ephemeral port, run `serve_forever` in
    a thread, then `shutdown()`.
    """
    server = ThreadingHTTPServer((host, port), _Handler)
    server.conn = db.connect(db_path)  # type: ignore[attr-defined]  # check_same_thread=False
    server.lock = threading.Lock()  # type: ignore[attr-defined]
    server.conn_factory = lambda: db.connect(db_path)  # type: ignore[attr-defined]
    return server


def serve(host: str = "127.0.0.1", port: int = 8585, *, db_path: Optional[str] = None) -> None:
    """Run the daemon until interrupted (blocking)."""
    from atlas_runtime import logging_config

    logging_config.configure_logging()
    server = make_server(host, port, db_path=db_path)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        try:
            server.conn.close()  # type: ignore[attr-defined]
        except Exception:
            pass
