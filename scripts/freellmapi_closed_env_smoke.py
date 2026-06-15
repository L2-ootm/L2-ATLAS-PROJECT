#!/usr/bin/env python3
"""Closed-environment FreeLLMAPI smoke test.

This script does not use real provider keys and does not call external LLM APIs.
It starts:
  1. a local mock OpenAI-compatible provider;
  2. the FreeLLMAPI built server;
  3. registers the mock provider as a custom endpoint through the dashboard API;
  4. calls FreeLLMAPI's /v1/models and /v1/chat/completions with model=auto.

Expected use from repo root (point --freellmapi at your local FreeLLMAPI clone):
  python scripts/freellmapi_closed_env_smoke.py --freellmapi <path-to-freellmapi-clone>
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def http_json(method: str, url: str, payload: dict | None = None, token: str | None = None, timeout: float = 10.0) -> tuple[int, dict]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {"raw": raw}
        return exc.code, parsed


class MockOpenAIHandler(BaseHTTPRequestHandler):
    server_version = "MockOpenAI/0.1"
    requests_seen: list[dict] = []

    def log_message(self, fmt: str, *args) -> None:
        return

    def _send(self, status: int, obj: dict) -> None:
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == "/v1/models":
            self._send(200, {
                "object": "list",
                "data": [{"id": "mock-free-model", "object": "model", "created": 0, "owned_by": "mock"}],
            })
            return
        self._send(404, {"error": {"message": "not found"}})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8", "replace") if length else "{}"
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"raw": raw}
        self.requests_seen.append({"path": self.path, "headers": dict(self.headers), "payload": payload})

        if self.path == "/v1/chat/completions":
            self._send(200, {
                "id": "chatcmpl-mock-001",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": payload.get("model", "mock-free-model"),
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "mock-ok: FreeLLMAPI routed this request through a local custom provider.",
                    },
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 8, "completion_tokens": 9, "total_tokens": 17},
            })
            return
        self._send(404, {"error": {"message": "not found"}})


def wait_for_server(url: str, timeout_s: float = 30.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            status, _ = http_json("GET", url, timeout=2.0)
            if status in (200, 401, 403, 404):
                return True
        except (URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(0.25)
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freellmapi", required=True, help="Path to freellmapi checkout")
    parser.add_argument("--port", type=int, default=3017)
    parser.add_argument("--mock-port", type=int, default=43117)
    parser.add_argument("--keep-db", action="store_true")
    args = parser.parse_args()

    root = Path(args.freellmapi).resolve()
    server_entry = root / "server" / "dist" / "index.js"
    if not server_entry.exists():
        print(f"FAIL: built server not found: {server_entry}")
        print("Run `npm install && npm rebuild better-sqlite3 && npm run build` in FreeLLMAPI first.")
        return 2

    db_dir = root / "server" / "data"
    if not args.keep_db and db_dir.exists():
        shutil.rmtree(db_dir)

    mock = ThreadingHTTPServer(("127.0.0.1", args.mock_port), MockOpenAIHandler)
    thread = threading.Thread(target=mock.serve_forever, daemon=True)
    thread.start()
    print(f"Mock OpenAI provider: http://127.0.0.1:{args.mock_port}/v1")

    env = os.environ.copy()
    env.update({
        "HOST": "127.0.0.1",
        "PORT": str(args.port),
        "NODE_ENV": "production",
        "ENCRYPTION_KEY": "a" * 64,
    })

    proc = subprocess.Popen(
        ["node", str(server_entry)],
        cwd=str(root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    unified_key = None
    logs: list[str] = []

    def reader() -> None:
        nonlocal unified_key
        assert proc.stdout is not None
        for line in proc.stdout:
            logs.append(line.rstrip())
            m = re.search(r"(freellmapi-[A-Za-z0-9_-]+)", line)
            if m:
                unified_key = m.group(1)

    log_thread = threading.Thread(target=reader, daemon=True)
    log_thread.start()

    try:
        base = f"http://127.0.0.1:{args.port}"
        if not wait_for_server(f"{base}/api/auth/status", timeout_s=30):
            print("FAIL: FreeLLMAPI server did not become ready")
            print("\n".join(logs[-40:]))
            return 3
        time.sleep(0.5)
        if not unified_key:
            # Give stdout reader a moment; migration prints the key on first DB creation.
            time.sleep(1.0)
        if not unified_key:
            print("FAIL: could not capture unified API key from server stdout")
            print("\n".join(logs[-80:]))
            return 4

        print(f"FreeLLMAPI server: {base}")
        print(f"Captured unified key: {unified_key[:18]}...[redacted]")

        status, auth_status = http_json("GET", f"{base}/api/auth/status")
        print("auth/status:", status, auth_status)

        email = "atlas-smoke@example.local"
        password = "atlas-smoke-password"
        status, setup = http_json("POST", f"{base}/api/auth/setup", {"email": email, "password": password})
        print("auth/setup:", status, {"token": (setup.get("token", "")[:12] + "...[redacted]") if setup.get("token") else None, "email": setup.get("email")})
        if status not in (200, 201):
            return 5
        dashboard_token = setup["token"]

        status, custom = http_json("POST", f"{base}/api/keys/custom", {
            "baseUrl": f"http://127.0.0.1:{args.mock_port}/v1",
            "model": "mock-free-model",
            "displayName": "Mock Free Model",
            "apiKey": "no-key",
            "label": "closed-env-mock",
        }, token=dashboard_token)
        print("keys/custom:", status, custom)
        if status not in (200, 201):
            return 6

        status, models = http_json("GET", f"{base}/v1/models", token=unified_key)
        model_ids = [m.get("id") for m in models.get("data", [])[:8]]
        print("v1/models:", status, model_ids)
        if status != 200 or "auto" not in model_ids:
            return 7

        status, chat = http_json("POST", f"{base}/v1/chat/completions", {
            "model": "auto",
            "messages": [{"role": "user", "content": "Return a short smoke-test confirmation."}],
        }, token=unified_key, timeout=20)
        print("v1/chat/completions:", status, json.dumps(chat, indent=2)[:1200])
        if status != 200:
            return 8
        content = chat["choices"][0]["message"]["content"]
        if "mock-ok" not in content:
            print("FAIL: response did not come from mock provider")
            return 9

        print("\nPASS: FreeLLMAPI routed model=auto through the local mock custom provider.")
        print(f"Mock provider requests seen: {len(MockOpenAIHandler.requests_seen)}")
        return 0
    finally:
        mock.shutdown()
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
