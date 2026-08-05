#!/usr/bin/env python3
"""Isolated, fail-fast ATLAS production gate.

The gate is intentionally dependency-free.  It never executes command strings:
every subprocess is assembled from a closed catalogue of argv vectors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence
from urllib.parse import urlparse


SCHEMA_VERSION = 1
DEFAULT_PORTS = frozenset({3000, 3001, 5173, 8081, 8484})
TEST_LABELS = frozenset(
    {"planning", "python-core", "python-runtime", "node-cli", "rust-gateway"}
)
REQUIRED_LABELS = ("planning-integrity", "gateway-identity", "doctor", "status")
CANARY_NAME = "ATLAS_GATE_SECRET_CANARY"
SECRET_PATTERNS = (
    re.compile(r"(?i)(?:api[_-]?key|authorization|owner[_-]?token|password)\s*[:=]"),
    re.compile(r"\b(?:sk|ghp|github_pat)_[A-Za-z0-9_-]{12,}\b"),
)
RUN_NAME = re.compile(r"^atlas-production-gate-[0-9a-f]{8,64}$")


class GateError(RuntimeError):
    """A hard production-gate failure."""


@dataclass(frozen=True)
class Command:
    id: str
    label: str
    argv: tuple[str, ...]
    cwd: Path


@dataclass(frozen=True)
class GatePaths:
    root: Path
    atlas_home: Path
    database: Path
    config: Path
    npm_prefix: Path
    install_root: Path | None = None


@dataclass(frozen=True)
class GateConfig:
    mode: str
    repo: Path
    paths: GatePaths
    ports: tuple[int, ...]
    gateway_binary: Path
    release_version: str
    test_labels: tuple[str, ...]
    resume: bool = False


Runner = Callable[[Command, dict[str, str]], int]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _is_descendant(path: Path, parent: Path) -> bool:
    try:
        _resolved(path).relative_to(_resolved(parent))
    except ValueError:
        return False
    return _resolved(path) != _resolved(parent)


def validate_paths(paths: GatePaths, *, repo: Path, resume: bool) -> GatePaths:
    root = _resolved(paths.root)
    repo = _resolved(repo)
    if not paths.root.is_absolute() or not RUN_NAME.fullmatch(root.name):
        raise GateError(
            "gate root must be absolute and named atlas-production-gate-<hex>"
        )
    default_home = _resolved(Path.home() / ".atlas")
    if root == repo or _is_descendant(root, repo):
        raise GateError("gate root cannot be the source repository or its descendant")
    if root == default_home or _is_descendant(root, default_home):
        raise GateError("gate root cannot use the default ATLAS home")
    marker = root / ".atlas-production-gate.json"
    if resume:
        if not root.is_dir() or not marker.is_file():
            raise GateError("resume requires an existing gate root with its marker")
    elif root.exists():
        raise GateError("a new gate root must not already exist")

    current_values = {
        _resolved(Path(value))
        for name in ("ATLAS_HOME", "ATLAS_DB", "ATLAS_CONFIG", "npm_config_prefix")
        if (value := os.environ.get(name))
    }
    candidates = {
        "ATLAS_HOME": paths.atlas_home,
        "ATLAS_DB": paths.database,
        "ATLAS_CONFIG": paths.config,
        "npm prefix": paths.npm_prefix,
    }
    if paths.install_root is not None:
        candidates["install root"] = paths.install_root
    normalized: dict[str, Path] = {}
    for label, candidate in candidates.items():
        if not candidate.is_absolute():
            raise GateError(f"{label} must be an explicit absolute path")
        value = _resolved(candidate)
        if not _is_descendant(value, root):
            raise GateError(f"{label} must be a descendant of the gate root")
        if value in current_values:
            raise GateError(f"{label} matches a live environment path")
        normalized[label] = value
    return GatePaths(
        root=root,
        atlas_home=normalized["ATLAS_HOME"],
        database=normalized["ATLAS_DB"],
        config=normalized["ATLAS_CONFIG"],
        npm_prefix=normalized["npm prefix"],
        install_root=normalized.get("install root"),
    )


def validate_ports(ports: Sequence[int]) -> tuple[int, ...]:
    values = tuple(ports)
    if len(values) < 3 or len(set(values)) != len(values):
        raise GateError("at least three distinct isolated ports are required")
    live_ports: set[int] = set()
    for name in (
        "ATLAS_GATEWAY_PORT",
        "ATLAS_COCKPIT_PORT",
        "ATLAS_FREELLMAPI_PORT",
    ):
        raw = os.environ.get(name, "")
        if raw.isdigit():
            live_ports.add(int(raw))
    for name in (
        "ATLAS_GATEWAY_URL",
        "ATLAS_COCKPIT_URL",
        "ATLAS_FREELLMAPI_URL",
    ):
        try:
            parsed_port = urlparse(os.environ.get(name, "")).port
        except ValueError:
            parsed_port = None
        if parsed_port:
            live_ports.add(parsed_port)
    for port in values:
        if not 1024 <= port <= 65535 or port in DEFAULT_PORTS:
            raise GateError(f"port {port} is privileged, default, or invalid")
        if port in live_ports:
            raise GateError(f"port {port} matches a live ATLAS environment")
    return values


def validate_test_labels(labels: Sequence[str]) -> tuple[str, ...]:
    unknown = sorted(set(labels) - TEST_LABELS)
    if unknown:
        raise GateError(f"test command is not allowlisted: {', '.join(unknown)}")
    return tuple(dict.fromkeys(labels))


def _source_cli(python: str, *arguments: str) -> tuple[str, ...]:
    code = "from atlas_runtime.cli.main import app; app()"
    return (python, "-c", code, *arguments, "--json")


def build_commands(config: GateConfig) -> tuple[Command, ...]:
    repo = _resolved(config.repo)
    python = sys.executable
    node = "node"
    commands = [
        Command(
            "gate-01-planning",
            REQUIRED_LABELS[0],
            (
                python,
                str(repo / "scripts/planning_integrity.py"),
                "--strict",
                "--format",
                "json",
            ),
            repo,
        ),
        Command(
            "gate-02-identity",
            REQUIRED_LABELS[1],
            (
                node,
                str(repo / "scripts/ci/verify-gateway-identity.js"),
                "--binary",
                str(config.gateway_binary),
                "--release-version",
                config.release_version,
            ),
            repo,
        ),
    ]
    if config.mode == "source":
        doctor = _source_cli(python, "doctor")
        status = _source_cli(python, "gateway", "status")
    else:
        if config.paths.install_root is None:
            raise GateError("installed mode requires an isolated install root")
        atlas_js = config.paths.install_root / "bin" / "atlas.js"
        doctor = (node, str(atlas_js), "doctor", "--json")
        status = (node, str(atlas_js), "gateway", "status", "--json")
    commands.extend(
        [
            Command("gate-03-doctor", REQUIRED_LABELS[2], doctor, repo),
            Command("gate-04-status", REQUIRED_LABELS[3], status, repo),
        ]
    )
    test_catalog = {
        "planning": (python, "-m", "pytest", "-q", "tests/test_planning_integrity.py"),
        "python-core": (python, "-m", "pytest", "-q", "packages/atlas-core/tests"),
        "python-runtime": (
            python,
            "-m",
            "pytest",
            "-q",
            "services/agent-runtime/tests",
        ),
        "node-cli": ("npm", "test", "--prefix", "packages/atlas-cli"),
        "rust-gateway": (
            "cargo",
            "test",
            "--manifest-path",
            "native/atlas-gateway/Cargo.toml",
        ),
    }
    for index, label in enumerate(config.test_labels, start=5):
        commands.append(
            Command(
                f"gate-{index:02d}-test", f"test:{label}", test_catalog[label], repo
            )
        )
    return tuple(commands)


def safe_environment(config: GateConfig) -> dict[str, str]:
    env = os.environ.copy()
    p = config.paths
    env.update(
        {
            "ATLAS_HOME": str(p.atlas_home),
            "ATLAS_DB": str(p.database),
            "ATLAS_CONFIG": str(p.config),
            "npm_config_prefix": str(p.npm_prefix),
            "ATLAS_GATEWAY_PORT": str(config.ports[0]),
            "ATLAS_GATEWAY_URL": f"http://127.0.0.1:{config.ports[0]}",
            "ATLAS_COCKPIT_URL": f"http://127.0.0.1:{config.ports[1]}",
            "ATLAS_FREELLMAPI_URL": f"http://127.0.0.1:{config.ports[2]}/v1",
            CANARY_NAME: f"canary-{uuid.uuid4().hex}",
        }
    )
    if config.mode == "source":
        runtime = str(config.repo / "services/agent-runtime")
        core = str(config.repo / "packages/atlas-core")
        env["PYTHONPATH"] = os.pathsep.join((runtime, core))
    return env


def scan_for_secrets(payload: object, *, canary: str) -> None:
    rendered = json.dumps(payload, sort_keys=True)
    if canary and canary in rendered:
        raise GateError("secret canary reached evidence")
    if any(pattern.search(rendered) for pattern in SECRET_PATTERNS):
        raise GateError("credential-like material reached evidence")


def atomic_json(path: Path, payload: object, *, canary: str) -> None:
    scan_for_secrets(payload, canary=canary)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def default_runner(command: Command, env: dict[str, str]) -> int:
    completed = subprocess.run(
        command.argv,
        cwd=command.cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=900,
        check=False,
        shell=False,
    )
    if completed.returncode != 0 or command.label != "status":
        return completed.returncode
    try:
        payload = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 1
    if not isinstance(payload, dict):
        return 1
    ready = payload.get("ready", payload.get("running", False))
    return 0 if ready is True else 1


def _fingerprint(config: GateConfig, commands: Sequence[Command]) -> str:
    safe = {
        "mode": config.mode,
        "ports": list(config.ports),
        "release": config.release_version,
        "labels": [command.label for command in commands],
    }
    return hashlib.sha256(json.dumps(safe, sort_keys=True).encode()).hexdigest()


def _load_state(path: Path, fingerprint: str) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if (
        data.get("schema_version") != SCHEMA_VERSION
        or data.get("fingerprint") != fingerprint
    ):
        raise GateError("resume state does not match this gate plan")
    return data


def execute_gate(
    config: GateConfig, *, dry_run: bool = False, runner: Runner = default_runner
) -> dict[str, object]:
    paths = validate_paths(config.paths, repo=config.repo, resume=config.resume)
    config = GateConfig(
        mode=config.mode,
        repo=_resolved(config.repo),
        paths=paths,
        ports=validate_ports(config.ports),
        gateway_binary=_resolved(config.gateway_binary),
        release_version=config.release_version,
        test_labels=validate_test_labels(config.test_labels),
        resume=config.resume,
    )
    commands = build_commands(config)
    fingerprint = _fingerprint(config, commands)
    root = paths.root
    if not config.resume:
        root.mkdir(parents=False)
        marker = {
            "schema_version": SCHEMA_VERSION,
            "gate_id": root.name,
            "created_at": utc_now(),
        }
        atomic_json(root / ".atlas-production-gate.json", marker, canary="")
    for directory in (
        paths.atlas_home,
        paths.database.parent,
        paths.config.parent,
        paths.npm_prefix,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    if paths.install_root is not None:
        paths.install_root.mkdir(parents=True, exist_ok=True)

    env = safe_environment(config)
    canary = env[CANARY_NAME]
    state_path = root / "gate-state.json"
    evidence_path = root / "evidence" / "production-gate.json"
    if config.resume and state_path.exists():
        state = _load_state(state_path, fingerprint)
    else:
        state = {
            "schema_version": SCHEMA_VERSION,
            "fingerprint": fingerprint,
            "passed": [],
        }
    passed = set(state.get("passed", []))
    evidence: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "gate_id": root.name,
        "mode": config.mode,
        "started_at": utc_now(),
        "finished_at": None,
        "status": "dry_run" if dry_run else "running",
        "steps": [],
    }
    steps = evidence["steps"]
    assert isinstance(steps, list)
    for command in commands:
        if command.id in passed:
            steps.append(
                {
                    "id": command.id,
                    "label": command.label,
                    "status": "resumed",
                    "duration_ms": 0,
                }
            )
            continue
        if dry_run:
            steps.append(
                {
                    "id": command.id,
                    "label": command.label,
                    "status": "planned",
                    "duration_ms": 0,
                }
            )
            continue
        started = time.monotonic()
        try:
            returncode = runner(command, env)
        except (OSError, subprocess.SubprocessError) as exc:
            returncode = 127
            failure_kind = type(exc).__name__
        else:
            failure_kind = None
        duration = max(0, round((time.monotonic() - started) * 1000))
        status = "passed" if returncode == 0 else "failed"
        step = {
            "id": command.id,
            "label": command.label,
            "status": status,
            "duration_ms": duration,
        }
        if failure_kind:
            step["failure_kind"] = failure_kind
        steps.append(step)
        if returncode != 0:
            evidence["status"] = "failed"
            evidence["finished_at"] = utc_now()
            atomic_json(evidence_path, evidence, canary=canary)
            raise GateError(f"hard gate failed: {command.label}")
        passed.add(command.id)
        state["passed"] = sorted(passed)
        atomic_json(state_path, state, canary=canary)
    evidence["status"] = "dry_run" if dry_run else "passed"
    evidence["finished_at"] = utc_now()
    atomic_json(evidence_path, evidence, canary=canary)
    cleanup_paths = (
        paths.atlas_home,
        paths.database,
        paths.config,
        paths.npm_prefix,
        *((paths.install_root,) if paths.install_root is not None else ()),
    )
    cleanup = {
        "schema_version": SCHEMA_VERSION,
        "gate_id": root.name,
        "policy": "manifest-only-no-delete",
        "entries": [
            {
                "id": f"cleanup-{i:02d}",
                "kind": "gate-descendant",
                "relative_path": path.relative_to(root).as_posix(),
            }
            for i, path in enumerate(cleanup_paths, 1)
        ],
    }
    atomic_json(root / "cleanup-manifest.json", cleanup, canary=canary)
    return evidence


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("source", "installed"), required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--gate-root", type=Path, required=True)
    parser.add_argument("--atlas-home", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--npm-prefix", type=Path, required=True)
    parser.add_argument("--install-root", type=Path)
    parser.add_argument("--gateway-binary", type=Path, required=True)
    parser.add_argument("--release-version", required=True)
    parser.add_argument("--port", type=int, action="append", required=True)
    parser.add_argument(
        "--test-command", choices=sorted(TEST_LABELS), action="append", default=[]
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config = GateConfig(
        mode=args.mode,
        repo=args.repo,
        paths=GatePaths(
            args.gate_root,
            args.atlas_home,
            args.database,
            args.config,
            args.npm_prefix,
            args.install_root,
        ),
        ports=tuple(args.port),
        gateway_binary=args.gateway_binary,
        release_version=args.release_version,
        test_labels=tuple(args.test_command),
        resume=args.resume,
    )
    try:
        evidence = execute_gate(config, dry_run=args.dry_run)
    except GateError as exc:
        print(f"production gate: {exc}", file=sys.stderr)
        return 1
    print(f"production gate: {evidence['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
