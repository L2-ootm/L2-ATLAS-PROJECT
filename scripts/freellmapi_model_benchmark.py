#!/usr/bin/env python3
"""Benchmark FreeLLMAPI models using the local unified key from SQLite.

Reads the unified API key from FreeLLMAPI's local DB, then tests selected
models via /v1/chat/completions. Does not print secrets.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path
from urllib import request, error

DEFAULT_DB = Path("C:/Users/Davi/AppData/Local/Temp/freellmapi/server/data/freeapi.db")
DEFAULT_BASE = "http://127.0.0.1:3001/v1"

CANDIDATES = [
    # Paid/free-key providers user configured
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "zai-glm-4.7",
    "gpt-oss-120b",
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "qwen/qwen3-32b",
    "groq/compound-mini",
    "mistral-large-latest",
    "mistral-medium-latest",
    "codestral-latest",
    "qwen/qwen3-coder:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "openai/gpt-oss-120b:free",
    "z-ai/glm-4.5-air:free",
    "moonshotai/Kimi-K2.6",
    "Qwen/Qwen3-Coder-Next",
    "deepseek-ai/DeepSeek-V4-Flash",
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
    "@cf/openai/gpt-oss-120b",
    "@cf/zai-org/glm-4.7-flash",
    # Keyless fallbacks
    "stepfun/step-3.7-flash:free",
    "openai-fast",
    "codestral-latest",  # LLM7 and Mistral share ID; routing may choose enabled provider
]

TESTS = [
    {
        "name": "exact",
        "prompt": "Reply with exactly this token and nothing else: ATLAS_BENCH_OK",
        "check": "ATLAS_BENCH_OK",
        "max_tokens": 24,
    },
    {
        "name": "reasoning",
        "prompt": "A box has 3 red balls and 2 blue balls. I add 4 red balls, then remove 1 blue ball. Reply with only the final counts as: red=X blue=Y",
        "check": "red=7 blue=1",
        "max_tokens": 48,
    },
]


def get_key(db_path: Path) -> str:
    conn = sqlite3.connect(str(db_path))
    row = conn.execute("select value from settings where key='unified_api_key'").fetchone()
    if not row:
        raise RuntimeError("unified_api_key not found in FreeLLMAPI settings")
    return row[0]


def call(base: str, key: str, model: str, prompt: str, max_tokens: int, timeout: int) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{base}/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    t0 = time.perf_counter()
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            latency_ms = round((time.perf_counter() - t0) * 1000)
            parsed = json.loads(body)
            content = parsed.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
            return {
                "ok": True,
                "status": resp.status,
                "latency_ms": latency_ms,
                "content": content.strip(),
                "routed_via": parsed.get("_routed_via"),
                "usage": parsed.get("usage"),
            }
    except error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        return {"ok": False, "status": e.code, "latency_ms": round((time.perf_counter() - t0) * 1000), "error": body}
    except Exception as e:
        return {"ok": False, "status": None, "latency_ms": round((time.perf_counter() - t0) * 1000), "error": repr(e)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--timeout", type=int, default=45)
    ap.add_argument("--out", default="C:/Users/Davi/Desktop/Projects/L2-ATLAS-PROJECT/docs/research/FREELLMAPI_MODEL_BENCHMARK_2026-06-07.json")
    args = ap.parse_args()

    key = get_key(Path(args.db))
    results = []
    seen = set()
    candidates = [m for m in CANDIDATES if not (m in seen or seen.add(m))]
    for model in candidates:
        model_result = {"requested_model": model, "tests": []}
        print(f"TEST {model}", flush=True)
        for test in TESTS:
            r = call(args.base, key, model, test["prompt"], test["max_tokens"], args.timeout)
            content_norm = (r.get("content") or "").lower().replace(" ", "")
            check_norm = test["check"].lower().replace(" ", "")
            r["test"] = test["name"]
            r["passed"] = bool(r.get("ok") and check_norm in content_norm)
            # Keep output compact, no secrets.
            print(json.dumps({
                "model": model,
                "test": test["name"],
                "ok": r.get("ok"),
                "passed": r.get("passed"),
                "status": r.get("status"),
                "latency_ms": r.get("latency_ms"),
                "routed_via": r.get("routed_via"),
                "content": (r.get("content") or r.get("error") or "")[:160],
            }, ensure_ascii=False), flush=True)
            model_result["tests"].append(r)
            time.sleep(0.4)
        # scoring: correctness primary, then availability, then speed
        ok_count = sum(1 for t in model_result["tests"] if t.get("ok"))
        pass_count = sum(1 for t in model_result["tests"] if t.get("passed"))
        latencies = [t["latency_ms"] for t in model_result["tests"] if t.get("ok")]
        avg_latency = round(sum(latencies) / len(latencies)) if latencies else None
        model_result["summary"] = {
            "ok_count": ok_count,
            "pass_count": pass_count,
            "avg_latency_ms": avg_latency,
            "score": pass_count * 1000 + ok_count * 100 - (avg_latency or 99999) / 100,
        }
        results.append(model_result)

    ranked = sorted(results, key=lambda x: x["summary"]["score"], reverse=True)
    out = {"base": args.base, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ranked": ranked}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nTOP 10")
    for i, r in enumerate(ranked[:10], 1):
        route = next((t.get("routed_via") for t in r["tests"] if t.get("routed_via")), None)
        print(f"{i}. {r['requested_model']} score={r['summary']['score']:.1f} pass={r['summary']['pass_count']}/2 ok={r['summary']['ok_count']}/2 avg_ms={r['summary']['avg_latency_ms']} route={route}")
    print(f"Saved: {args.out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
