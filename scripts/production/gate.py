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
import shutil
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
REQUIRED_LABELS = (
    "planning-integrity",
    "prepare-config",
    "prepare-database",
    "gateway-identity",
    "start-core",
    "status-ready",
    "start-idempotent",
    "doctor",
)
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
    expectation: str = "zero"


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
    installed_launcher: Path | None = None
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
    if normalized["ATLAS_CONFIG"] != normalized["ATLAS_HOME"] / "config.yaml":
        raise GateError("ATLAS_CONFIG must be <isolated ATLAS_HOME>/config.yaml")
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


def _source_cli(python: str, *arguments: str, json_out: bool = True) -> tuple[str, ...]:
    code = "from atlas_runtime.cli.main import app; app()"
    suffix = ("--json",) if json_out else ()
    return (python, "-c", code, *arguments, *suffix)


def resolve_node_executable() -> Path:
    """Resolve Node to an explicit executable; never dispatch through a shim."""
    found = shutil.which("node")
    if not found:
        raise GateError("allowlisted Node executable was not found")
    node = _resolved(Path(found))
    if not node.is_file():
        raise GateError("resolved Node executable is not a file")
    if os.name == "nt" and node.suffix.lower() not in {".exe", ".com"}:
        raise GateError("resolved Node command is a shell wrapper")
    if os.name != "nt" and not os.access(node, os.X_OK):
        raise GateError("resolved Node command is not executable")
    return node


def resolve_npm_cli(node: Path) -> Path:
    """Resolve npm's JavaScript CLI beside Node, bypassing npm.cmd on Windows."""
    candidates = (
        node.parent / "node_modules" / "npm" / "bin" / "npm-cli.js",
        node.parent.parent / "lib" / "node_modules" / "npm" / "bin" / "npm-cli.js",
        Path("/usr/local/lib/node_modules/npm/bin/npm-cli.js"),
        Path("/usr/lib/node_modules/npm/bin/npm-cli.js"),
    )
    for candidate in candidates:
        resolved = _resolved(candidate)
        if resolved.is_file():
            return resolved
    raise GateError("npm-cli.js was not found beside the allowlisted Node executable")


def build_commands(config: GateConfig) -> tuple[Command, ...]:
    repo = _resolved(config.repo)
    python = sys.executable
    node_path = resolve_node_executable()
    node = str(node_path)
    if config.mode == "source":

        def cli(*args: str, json_out: bool = True) -> tuple[str, ...]:
            return _source_cli(python, *args, json_out=json_out)
    else:
        if config.paths.install_root is None or config.installed_launcher is None:
            raise GateError("installed mode requires an isolated launcher entry point")
        launcher_prefix = (
            (node, str(config.installed_launcher))
            if config.installed_launcher.suffix.lower() == ".js"
            else (str(config.installed_launcher),)
        )

        def cli(*args: str, json_out: bool = True) -> tuple[str, ...]:
            suffix = ("--json",) if json_out else ()
            return (*launcher_prefix, *args, *suffix)

    commands: list[Command] = [
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
            "gate-02-config",
            REQUIRED_LABELS[1],
            (
                python,
                str(repo / "scripts/production/prepare_config.py"),
                "--path",
                str(config.paths.config),
                "--gateway-port",
                str(config.ports[0]),
                "--cockpit-port",
                str(config.ports[1]),
            ),
            repo,
        ),
        Command(
            "gate-03-database",
            REQUIRED_LABELS[2],
            cli("db", "init", json_out=False),
            repo,
        ),
        Command(
            "gate-04-identity",
            REQUIRED_LABELS[3],
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
        Command(
            "gate-05-start",
            REQUIRED_LABELS[4],
            cli("up", "--services", "gateway,cockpit"),
            repo,
        ),
        Command(
            "gate-06-ready",
            REQUIRED_LABELS[5],
            cli("gateway", "status"),
            repo,
            "ready",
        ),
        Command(
            "gate-07-idempotent",
            REQUIRED_LABELS[6],
            cli("up", "--services", "gateway,cockpit"),
            repo,
            "idempotent",
        ),
        Command("gate-08-doctor", REQUIRED_LABELS[7], cli("doctor"), repo),
    ]
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
        "node-cli": (
            node,
            str(resolve_npm_cli(node_path)),
            "test",
            "--prefix",
            "packages/atlas-cli",
        ),
        "rust-gateway": (
            "cargo",
            "test",
            "--manifest-path",
            "native/atlas-core-rs/Cargo.toml",
            "-p",
            "atlas-gateway",
        ),
    }
    for index, label in enumerate(config.test_labels, start=9):
        commands.append(
            Command(
                f"gate-{index:02d}-test", f"test:{label}", test_catalog[label], repo
            )
        )
    commands.extend(
        (
            Command("gate-90-stop", "stop-ordered", cli("down"), repo),
            Command(
                "gate-91-stopped",
                "status-stopped",
                cli("gateway", "status"),
                repo,
                "stopped",
            ),
            Command(
                "gate-92-recover",
                "recover-state",
                cli("gateway", "recover", json_out=False),
                repo,
            ),
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
            "ATLAS_GATEWAY_BIN": str(config.gateway_binary),
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
    if completed.returncode != 0 or command.expectation == "zero":
        return completed.returncode
    try:
        payload = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 1
    if not isinstance(payload, dict):
        return 1
    if command.expectation == "ready":
        ready = payload.get("ready", payload.get("running", False))
        return 0 if ready is True else 1
    if command.expectation == "stopped":
        state = payload.get("state")
        stopped = payload.get("running") is False and state in {
            None,
            "stopped",
            "not_managed",
            "not_installed",
        }
        return 0 if stopped else 1
    if command.expectation == "idempotent":
        components = payload.get("components")
        if not isinstance(components, list):
            return 1
        core = [
            item
            for item in components
            if isinstance(item, dict)
            and item.get("component") in {"gateway", "cockpit"}
        ]
        idempotent = len(core) == 2 and all(
            item.get("ok") is True and item.get("code") == "already_ready"
            for item in core
        )
        return 0 if idempotent else 1
    return 1


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
    if config.mode not in {"source", "installed"}:
        raise GateError("mode must be source or installed")
    gateway_binary = _resolved(config.gateway_binary)
    if not config.gateway_binary.is_absolute():
        raise GateError("gateway binary must be an explicit absolute path")
    if not dry_run and not gateway_binary.is_file():
        raise GateError("gateway binary does not exist")
    installed_launcher = config.installed_launcher
    if config.mode == "installed":
        if paths.install_root is None or installed_launcher is None:
            raise GateError("installed mode requires install root and launcher")
        if not installed_launcher.is_absolute():
            raise GateError("installed launcher must be an explicit absolute path")
        installed_launcher = _resolved(installed_launcher)
        if not _is_descendant(installed_launcher, paths.install_root):
            raise GateError(
                "installed launcher must be below the isolated install root"
            )
        if not _is_descendant(gateway_binary, paths.install_root):
            raise GateError(
                "installed gateway binary must be below the isolated install root"
            )
        suffix = installed_launcher.suffix.lower()
        allowed_suffixes = {".js", ".exe", ".com"} if os.name == "nt" else {".js", ""}
        if suffix not in allowed_suffixes:
            raise GateError(
                "installed launcher must be .js or a direct native executable"
            )
        if not dry_run:
            if not installed_launcher.is_file():
                raise GateError("installed launcher does not exist")
            if (
                suffix != ".js"
                and os.name != "nt"
                and not os.access(installed_launcher, os.X_OK)
            ):
                raise GateError("installed launcher is not executable")
    config = GateConfig(
        mode=config.mode,
        repo=_resolved(config.repo),
        paths=paths,
        ports=validate_ports(config.ports),
        gateway_binary=gateway_binary,
        release_version=config.release_version,
        test_labels=validate_test_labels(config.test_labels),
        installed_launcher=installed_launcher,
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
    primary = tuple(
        command for command in commands if not command.id.startswith("gate-9")
    )
    teardown = tuple(command for command in commands if command.id.startswith("gate-9"))
    if dry_run:
        for command in commands:
            steps.append(
                {
                    "id": command.id,
                    "label": command.label,
                    "status": "planned",
                    "duration_ms": 0,
                }
            )

    def run_one(command: Command) -> int:
        started = time.monotonic()
        try:
            returncode = runner(command, env)
        except Exception as exc:  # noqa: BLE001 - teardown must survive runner faults
            returncode = 127
            failure_kind = type(exc).__name__
        else:
            failure_kind = None
        duration = max(0, round((time.monotonic() - started) * 1000))
        step = {
            "id": command.id,
            "label": command.label,
            "status": "passed" if returncode == 0 else "failed",
            "duration_ms": duration,
        }
        if failure_kind:
            step["failure_kind"] = failure_kind
        steps.append(step)
        return returncode

    failure_label: str | None = None
    for command in () if dry_run else primary:
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
        returncode = run_one(command)
        if returncode != 0:
            failure_label = command.label
            break
        passed.add(command.id)
        state["passed"] = sorted(passed)
        atomic_json(state_path, state, canary=canary)

    for command in () if dry_run else teardown:
        if run_one(command) != 0 and failure_label is None:
            failure_label = command.label

    if failure_label:
        # Teardown stops the services. A resumed failed run must replay the
        # lifecycle from start even if a later test was the original failure.
        passed = {
            item
            for item in passed
            if item.startswith(("gate-01", "gate-02", "gate-03", "gate-04"))
        }
        state["passed"] = sorted(passed)
        atomic_json(state_path, state, canary=canary)

    evidence["status"] = (
        "dry_run" if dry_run else "failed" if failure_label else "passed"
    )
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
    if failure_label:
        raise GateError(f"hard gate failed: {failure_label}")
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
    parser.add_argument("--installed-launcher", type=Path)
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
        installed_launcher=args.installed_launcher,
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
