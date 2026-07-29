"""Operator-run acceptance helpers for live ATLAS reality testing.

The stochastic agent and browser steps remain observable UAT. This helper owns
the deterministic edges: install preflight, secret-safe transcripts, and a
before/after Git working-tree oracle for the project under analysis.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "tests" / "reality" / "scenarios.json"
SECRET_KEY = re.compile(r"(api[_-]?key|token|secret|password|authorization)", re.IGNORECASE)
SECRET_TEXT = re.compile(
    r"\b(?:freellmapi|sk|key)-[a-z0-9_-]{12,}\b|"
    r"(authorization\s*:\s*bearer\s+)\S+",
    re.IGNORECASE,
)


def redact(value: Any) -> Any:
    """Recursively redact credential-shaped fields before writing artifacts."""
    if isinstance(value, dict):
        return {
            key: ("[REDACTED]" if SECRET_KEY.search(str(key)) else redact(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return SECRET_TEXT.sub(
            lambda match: f"{match.group(1)}[REDACTED]" if match.lastindex else "[REDACTED]",
            value,
        )
    return value


def _run(command: list[str], *, cwd: pathlib.Path | None = None, timeout: int = 60) -> dict[str, Any]:
    executable = None
    if command[0].lower() == "atlas":
        override = os.environ.get("ATLAS_REALITY_BIN", "").strip()
        npm_shim = pathlib.Path(os.environ.get("APPDATA", "")) / "npm" / "atlas.cmd"
        if override:
            executable = override
        elif sys.platform == "win32" and npm_shim.is_file():
            # The repository also contains atlas.cmd for source development.
            # Reality tests must exercise the globally installed release shim.
            executable = str(npm_shim)
    executable = executable or shutil.which(command[0])
    if executable:
        command = [executable, *command[1:]]
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return redact(
        {
            "command": command,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    )


def _git(project: pathlib.Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(project), *args],
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return completed.stdout


def project_snapshot(project: pathlib.Path) -> dict[str, Any]:
    """Return a content-sensitive snapshot without writing inside the project."""
    project = project.resolve()
    top = pathlib.Path(_git(project, "rev-parse", "--show-toplevel").strip()).resolve()
    tracked = [item for item in _git(top, "ls-files", "-z").split("\0") if item]
    digest = hashlib.sha256()
    missing: list[str] = []
    for relative in sorted(tracked):
        path = top / relative
        digest.update(relative.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")
        if not path.is_file():
            missing.append(relative)
            digest.update(b"[MISSING]")
            continue
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return {
        "project": str(top),
        "head": _git(top, "rev-parse", "HEAD").strip(),
        "status_porcelain": _git(top, "status", "--porcelain=v1", "--untracked-files=all"),
        "tracked_file_count": len(tracked),
        "tracked_content_sha256": digest.hexdigest(),
        "missing_tracked_files": missing,
    }


def compare_snapshot(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = ("head", "status_porcelain", "tracked_file_count", "tracked_content_sha256")
    changes = {key: {"before": before.get(key), "after": after.get(key)} for key in keys if before.get(key) != after.get(key)}
    return {"unchanged": not changes, "changes": changes}


def preflight() -> dict[str, Any]:
    checks = [
        _run(["atlas", "--version"]),
        _run(["atlas", "doctor", "--install-only", "--json"]),
        _run(["atlas", "db", "status"]),
        # Known 0.1.5 builds expose a credential here; redact() is mandatory.
        _run(["atlas", "freellmapi", "status", "--json"]),
        _run(["atlas", "provider", "status"]),
    ]
    return {
        "recorded_at": datetime.now(UTC).isoformat(),
        "checks": checks,
        "ok": all(check["exit_code"] == 0 for check in checks),
    }


def initialize_run(project: pathlib.Path, output: pathlib.Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    suite = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    data = {
        "schema": 1,
        "started_at": datetime.now(UTC).isoformat(),
        "project": str(project.resolve()),
        "preflight": preflight(),
        "before": project_snapshot(project),
        "suite": suite,
    }
    (output / "run.json").write_text(json.dumps(redact(data), indent=2), encoding="utf-8")
    return data


def finalize_run(run_dir: pathlib.Path) -> dict[str, Any]:
    run_file = run_dir / "run.json"
    data = json.loads(run_file.read_text(encoding="utf-8"))
    after = project_snapshot(pathlib.Path(data["project"]))
    result = {
        "finished_at": datetime.now(UTC).isoformat(),
        "after": after,
        "mutation_oracle": compare_snapshot(data["before"], after),
    }
    (run_dir / "result.json").write_text(json.dumps(redact(result), indent=2), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.add_argument("--project", type=pathlib.Path, required=True)
    start.add_argument("--output", type=pathlib.Path, required=True)
    finish = sub.add_parser("finish")
    finish.add_argument("--run-dir", type=pathlib.Path, required=True)
    args = parser.parse_args(argv)

    if args.command == "start":
        result = initialize_run(args.project, args.output)
        print(json.dumps({"ok": result["preflight"]["ok"], "run_dir": str(args.output.resolve())}))
        return 0 if result["preflight"]["ok"] else 1
    result = finalize_run(args.run_dir)
    print(json.dumps(result["mutation_oracle"]))
    return 0 if result["mutation_oracle"]["unchanged"] else 2


if __name__ == "__main__":
    sys.exit(main())
