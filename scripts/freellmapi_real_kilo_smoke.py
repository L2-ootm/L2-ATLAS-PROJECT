#!/usr/bin/env python3
"""Real-provider FreeLLMAPI smoke test using Kilo keyless free route.

No provider API key is used. This makes a real outbound API call via FreeLLMAPI
through Kilo Gateway's anonymous/free route, so it depends on current network and
upstream availability/terms.
"""
from __future__ import annotations

import argparse, json, os, re, shutil, subprocess, threading, time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def http_json(method, url, payload=None, token=None, timeout=45):
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, dict(resp.headers), json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try: body = json.loads(raw) if raw else {}
        except Exception: body = {"raw": raw}
        return exc.code, dict(exc.headers), body


def wait_ready(url, timeout_s=30):
    end = time.time() + timeout_s
    while time.time() < end:
        try:
            status, _, _ = http_json("GET", url, timeout=2)
            if status in (200, 401, 403, 404): return True
        except Exception:
            time.sleep(0.25)
    return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--freellmapi", required=True)
    p.add_argument("--port", type=int, default=3018)
    p.add_argument("--model", default="stepfun/step-3.7-flash:free")
    args = p.parse_args()
    root = Path(args.freellmapi).resolve()
    entry = root / "server" / "dist" / "index.js"
    if not entry.exists():
        print(f"FAIL: missing built server {entry}"); return 2
    data_dir = root / "server" / "data"
    if data_dir.exists():
        shutil.rmtree(data_dir, ignore_errors=True)
    env = os.environ.copy()
    env.update({"HOST":"127.0.0.1", "PORT":str(args.port), "NODE_ENV":"production", "ENCRYPTION_KEY":"b"*64})
    proc = subprocess.Popen(["node", str(entry)], cwd=str(root), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    logs=[]; key=None
    def reader():
        nonlocal key
        assert proc.stdout
        for line in proc.stdout:
            logs.append(line.rstrip())
            m=re.search(r"(freellmapi-[A-Za-z0-9_-]+)", line)
            if m: key=m.group(1)
    threading.Thread(target=reader, daemon=True).start()
    base=f"http://127.0.0.1:{args.port}"
    try:
        if not wait_ready(base+"/api/auth/status"):
            print("FAIL: server not ready"); print("\n".join(logs[-80:])); return 3
        time.sleep(1)
        if not key:
            print("FAIL: no unified key captured"); print("\n".join(logs[-80:])); return 4
        print(f"FreeLLMAPI: {base}")
        print(f"Unified key: {key[:18]}...[redacted]")
        status, _, setup = http_json("POST", base+"/api/auth/setup", {"email":"atlas-real@example.local", "password":"atlas-real-password"})
        print("auth/setup:", status, {"email": setup.get("email"), "token": (setup.get("token","")[:12]+"...[redacted]") if setup.get("token") else None})
        dash=setup.get("token")
        if status not in (200,201) or not dash: return 5
        status, _, add = http_json("POST", base+"/api/keys/", {"platform":"kilo", "label":"kilo-keyless-real-smoke"}, token=dash)
        print("keys/kilo:", status, add)
        if status not in (200,201): return 6
        status, _, models = http_json("GET", base+"/v1/models", token=key)
        print("models status:", status, "first_ids:", [m.get('id') for m in models.get('data',[])[:10]])
        payload={"model": args.model, "messages":[{"role":"user", "content":"Reply with exactly: ATLAS_REAL_SMOKE_OK"}], "max_tokens": 80}
        status, headers, chat = http_json("POST", base+"/v1/chat/completions", payload, token=key, timeout=60)
        print("chat status:", status)
        print("x-routed-via:", headers.get("x-routed-via"), "x-fallback-attempts:", headers.get("x-fallback-attempts"))
        print(json.dumps(chat, indent=2)[:2500])
        if status != 200: return 7
        content = chat.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content.strip(): return 8
        print("\nPASS: real FreeLLMAPI provider call returned content.")
        return 0
    finally:
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill()

if __name__ == "__main__":
    raise SystemExit(main())
