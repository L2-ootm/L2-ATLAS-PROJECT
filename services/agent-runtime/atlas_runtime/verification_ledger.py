"""What the operator declared "done" means, and what checks this workspace has.

`verification_gate` reads one run's audit trail and answers whether the run
checked its own work. It is complete as far as it goes, and it has two blind
spots that this module fills — both taken from what hermes-agent shipped in
v0.18.0 while ATLAS was building the gate independently (see
`docs/research/2026-08-13-upstream-harnesses-and-contribution-surface.md` §3.1;
the shapes are ported, none of the code is).

**The contract.** The gate infers what "done" should have meant from the trail.
That is a judgement. A `.atlas/verification.json` in the workspace root turns it
into a comparison:

    {"required": ["tests", "lint"]}

A run that passes tests but never lints is then not `verified` — it is
`unverified` with `lint` named as the missing half. Nothing is required by
default: an undeclared project keeps exactly today's behaviour, because a gate
that silently raised its own bar would fail runs that met the standard they
were actually held to.

**The ledger.** The trail forgets nothing about one run and carries nothing
between runs. `verification_checks` (migration 0036) is the durable record of
which checks a workspace *has* — detected from marker files, and confirmed by
runs that actually executed them. It is what lets the enforced check turn say
"this workspace runs `pytest -q`" instead of "run a real check", and it is the
only place a later run can find out what verification is even available.

Every function here is best-effort by contract. This module is read by the
verification gate, which is a reporting layer that must never fail a run: an
unreadable contract file, an unwritable table or an unresolvable workspace all
degrade to "no contract, no ledger", never to an exception.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import pathlib
import sqlite3
import threading
from dataclasses import dataclass
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

CONTRACT_RELPATH = ".atlas/verification.json"

# The kinds the gate can actually observe. A contract that requires anything
# else could never be satisfied, so it is rejected at load rather than failing
# every run in the project silently.
KNOWN_KINDS = ("tests", "typecheck", "lint", "build", "exercised")

_MAX_COMMAND = 200
_MAX_HINT_ENTRIES = 6


# -- the operator's contract -------------------------------------------------


@dataclass(frozen=True)
class Contract:
    """What the operator declared a finished change must have passed."""

    required: tuple[str, ...] = ()
    source: str = ""

    def missing(self, passed: Iterable[str]) -> tuple[str, ...]:
        have = set(passed)
        return tuple(kind for kind in self.required if kind not in have)


EMPTY_CONTRACT = Contract()


def load_contract(root: Optional[str]) -> Contract:
    """Read `.atlas/verification.json` from a workspace root.

    A missing file is the normal case and yields the empty contract. A malformed
    one is logged and also yields the empty contract: a typo in a config file
    must not be able to mark every run in a project unverified.
    """
    if not root:
        return EMPTY_CONTRACT
    path = pathlib.Path(root) / CONTRACT_RELPATH
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return EMPTY_CONTRACT
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError) as exc:
        logger.warning("verification contract at %s is not valid JSON: %s", path, exc)
        return EMPTY_CONTRACT
    if not isinstance(parsed, dict):
        return EMPTY_CONTRACT

    declared = parsed.get("required")
    if isinstance(declared, str):
        declared = [declared]
    if not isinstance(declared, list):
        return EMPTY_CONTRACT

    required: list[str] = []
    for item in declared:
        kind = str(item).strip().lower()
        if kind in KNOWN_KINDS and kind not in required:
            required.append(kind)
        elif kind and kind not in KNOWN_KINDS:
            logger.warning(
                "verification contract at %s requires unknown check %r; known kinds: %s",
                path, kind, ", ".join(KNOWN_KINDS),
            )
    if not required:
        return EMPTY_CONTRACT
    return Contract(required=tuple(required), source=str(path))


# -- where a run was working -------------------------------------------------


def workspace_for_run(
    conn: sqlite3.Connection, run_id: str
) -> tuple[Optional[str], str]:
    """(workspace root, project_id) for a run — best effort, never raises.

    Three sources, most specific first. The surface session is the one that
    knows the *declared* root a run was confined to; the mission's project is
    the fallback for runs started without a surface (the async executor, actor
    delegation); and a run with neither has no workspace this module can name.
    """
    try:
        row = conn.execute(
            "SELECT s.workspace_root, s.project_id FROM surface_sessions s "
            "JOIN runs r ON r.session_id = s.id WHERE r.id = ?",
            (run_id,),
        ).fetchone()
        if row and row[0]:
            return _normalise_root(str(row[0])), str(row[1] or "")

        row = conn.execute(
            "SELECT workspace_root, project_id FROM surface_sessions "
            "WHERE run_id = ? ORDER BY updated_at DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        if row and row[0]:
            return _normalise_root(str(row[0])), str(row[1] or "")

        row = conn.execute(
            "SELECT p.root_path, p.id FROM runs r "
            "JOIN missions m ON m.id = r.mission_id "
            "JOIN projects p ON p.id = m.project_id "
            "WHERE r.id = ?",
            (run_id,),
        ).fetchone()
        if row and row[0]:
            return _normalise_root(str(row[0])), str(row[1] or "")
    except Exception as exc:  # noqa: BLE001 — resolution is best-effort
        logger.debug("workspace resolution failed for run %s: %s", run_id, exc)
    return None, ""


def _normalise_root(root: str) -> str:
    try:
        return str(pathlib.Path(root).expanduser().resolve())
    except (OSError, ValueError, RuntimeError):
        return root.rstrip("/\\")


def contract_for_run(conn: sqlite3.Connection, run_id: str) -> Contract:
    root, _ = workspace_for_run(conn, run_id)
    return load_contract(root)


# -- detection ---------------------------------------------------------------


@dataclass(frozen=True)
class DetectedCheck:
    kind: str
    command: str
    detected_from: str


def _read(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return ""


def _node_runner(root: pathlib.Path) -> str:
    if (root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (root / "yarn.lock").exists():
        return "yarn"
    if (root / "bun.lockb").exists():
        return "bun"
    return "npm"


def detect(root: Optional[str]) -> tuple[DetectedCheck, ...]:
    """Canonical checks a workspace declares, from its marker files.

    Deliberately shallow — root-level files only, no recursion, no execution.
    Detection is a hint about what exists, not a promise that it passes; a
    detected command that a run never manages to execute stays in the ledger
    with an empty `last_status`, which is itself worth knowing.
    """
    if not root:
        return ()
    base = pathlib.Path(root)
    if not base.is_dir():
        return ()

    found: list[DetectedCheck] = []

    def add(kind: str, command: str, source: str) -> None:
        if not any(f.kind == kind and f.command == command for f in found):
            found.append(DetectedCheck(kind, command[:_MAX_COMMAND], source))

    pyproject = _read(base / "pyproject.toml")
    if "[tool.pytest" in pyproject or (base / "pytest.ini").exists():
        add("tests", "pytest -q", "pyproject.toml" if pyproject else "pytest.ini")
    elif (base / "tests").is_dir() and (
        pyproject or (base / "setup.py").exists() or (base / "setup.cfg").exists()
    ):
        add("tests", "pytest -q", "tests/")
    if "[tool.ruff" in pyproject or (base / "ruff.toml").exists() or (base / ".ruff.toml").exists():
        add("lint", "ruff check .", "pyproject.toml" if "[tool.ruff" in pyproject else "ruff.toml")
    if "[tool.mypy" in pyproject or (base / "mypy.ini").exists():
        add("typecheck", "mypy .", "pyproject.toml" if "[tool.mypy" in pyproject else "mypy.ini")

    package_json = _read(base / "package.json")
    if package_json:
        try:
            scripts = json.loads(package_json).get("scripts") or {}
        except (TypeError, ValueError):
            scripts = {}
        if isinstance(scripts, dict):
            runner = _node_runner(base)
            for script, kind in (
                ("test", "tests"),
                ("lint", "lint"),
                ("typecheck", "typecheck"),
                ("build", "build"),
            ):
                if isinstance(scripts.get(script), str) and scripts[script].strip():
                    verb = "" if script == "test" else "run "
                    add(kind, f"{runner} {verb}{script}", "package.json")
    if (base / "tsconfig.json").exists():
        add("typecheck", "npx tsc --noEmit", "tsconfig.json")

    if (base / "Cargo.toml").exists():
        add("tests", "cargo test", "Cargo.toml")
        add("lint", "cargo clippy", "Cargo.toml")
        add("build", "cargo build", "Cargo.toml")

    if (base / "go.mod").exists():
        add("tests", "go test ./...", "go.mod")
        add("build", "go build ./...", "go.mod")

    makefile = _read(base / "Makefile")
    if makefile:
        for target, kind in (("test", "tests"), ("check", "tests"), ("build", "build")):
            for line in makefile.splitlines():
                if line.startswith(f"{target}:"):
                    add(kind, f"make {target}", "Makefile")
                    break

    return tuple(found)


# -- the durable ledger ------------------------------------------------------


@dataclass(frozen=True)
class LedgerEntry:
    kind: str
    command: str
    source: str
    last_status: str = ""
    last_run_id: str = ""


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _upsert(
    conn: sqlite3.Connection,
    *,
    root: str,
    kind: str,
    command: str,
    source: str,
    detected_from: str,
    project_id: str,
    observed: Optional[tuple[str, str]] = None,
) -> None:
    """One ledger row. `observed` is (run_id, status) when a run really ran it.

    Detection must never overwrite an observation: a marker file says the check
    could exist, a run says it does. So `source` only ever moves
    detected -> observed, and the observation columns are left alone by a
    detection pass.
    """
    now = _now()
    if observed is None:
        conn.execute(
            "INSERT INTO verification_checks"
            "(root,kind,command,source,detected_from,project_id,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?) "
            "ON CONFLICT(root,kind,command) DO UPDATE SET "
            "detected_from=excluded.detected_from, "
            "project_id=CASE WHEN excluded.project_id<>'' THEN excluded.project_id "
            "ELSE verification_checks.project_id END, "
            "updated_at=excluded.updated_at",
            (root, kind, command, source, detected_from, project_id, now, now),
        )
        return
    run_id, status = observed
    conn.execute(
        "INSERT INTO verification_checks"
        "(root,kind,command,source,detected_from,project_id,"
        "last_run_id,last_status,last_seen_at,created_at,updated_at) "
        "VALUES(?,?,?,'observed',?,?,?,?,?,?,?) "
        "ON CONFLICT(root,kind,command) DO UPDATE SET "
        "source='observed', "
        "project_id=CASE WHEN excluded.project_id<>'' THEN excluded.project_id "
        "ELSE verification_checks.project_id END, "
        "last_run_id=excluded.last_run_id, last_status=excluded.last_status, "
        "last_seen_at=excluded.last_seen_at, updated_at=excluded.updated_at",
        (root, kind, command, detected_from, project_id, run_id, status, now, now, now),
    )


def sync_detected(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    root: Optional[str],
    project_id: str = "",
) -> int:
    """Record the checks a workspace's marker files declare. Returns rows written."""
    if not root:
        return 0
    root = _normalise_root(root)
    checks = detect(root)
    if not checks:
        return 0
    try:
        with lock, conn:
            for check in checks:
                _upsert(
                    conn,
                    root=root,
                    kind=check.kind,
                    command=check.command,
                    source="detected",
                    detected_from=check.detected_from,
                    project_id=project_id,
                )
    except Exception as exc:  # noqa: BLE001 — the ledger never fails a run
        logger.debug("verification ledger detection write failed for %s: %s", root, exc)
        return 0
    return len(checks)


def record_run(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    run_id: str,
    verdict: Any,
    root: Optional[str] = None,
    project_id: Optional[str] = None,
) -> None:
    """Write what this run's checks proved into the ledger.

    Called once per terminal run from the verification gate. Two writes: the
    workspace's detected checks (cheap, idempotent, and the only chance a
    never-verified project gets to appear in the ledger at all), then one
    observation row per command the gate classified as a real check.
    """
    if root is None or project_id is None:
        resolved_root, resolved_project = workspace_for_run(conn, run_id)
        root = root if root is not None else resolved_root
        project_id = project_id if project_id is not None else resolved_project
    if not root:
        return
    root = _normalise_root(root)

    sync_detected(conn, lock, root=root, project_id=project_id or "")

    observations = [
        (kind, command, "passed")
        for kind, command in getattr(verdict, "signal_commands", ())
        if command
    ]
    observations += [
        (kind, command, "failed")
        for kind, command in getattr(verdict, "failed_signal_commands", ())
        if command
    ]
    if not observations:
        return
    try:
        with lock, conn:
            for kind, command, status in observations:
                _upsert(
                    conn,
                    root=root,
                    kind=kind,
                    command=command[:_MAX_COMMAND],
                    source="observed",
                    detected_from="",
                    project_id=project_id or "",
                    observed=(run_id, status),
                )
    except Exception as exc:  # noqa: BLE001 — the ledger never fails a run
        logger.debug("verification ledger observation write failed for %s: %s", run_id, exc)


def available(
    conn: sqlite3.Connection, root: Optional[str], *, limit: int = 20
) -> tuple[LedgerEntry, ...]:
    """The checks this workspace is known to have, observed ones first."""
    if not root:
        return ()
    root = _normalise_root(root)
    try:
        rows = conn.execute(
            "SELECT kind, command, source, last_status, last_run_id "
            "FROM verification_checks WHERE root = ? "
            "ORDER BY CASE source WHEN 'observed' THEN 0 ELSE 1 END, kind, command "
            "LIMIT ?",
            (root, limit),
        ).fetchall()
    except Exception as exc:  # noqa: BLE001 — a reporting read never raises
        logger.debug("verification ledger read failed for %s: %s", root, exc)
        return ()
    return tuple(
        LedgerEntry(
            kind=str(row[0]), command=str(row[1]), source=str(row[2]),
            last_status=str(row[3] or ""), last_run_id=str(row[4] or ""),
        )
        for row in rows
    )


def demand_hint(conn: sqlite3.Connection, run_id: str) -> str:
    """The lines the enforced check turn adds naming this project's own checks.

    Empty when nothing is known — the demand is better generic than wrong, and
    inventing a command the project does not have would teach the agent that the
    checkpoint's suggestions can be ignored.
    """
    root, _ = workspace_for_run(conn, run_id)
    if not root:
        return ""
    entries = available(conn, root, limit=_MAX_HINT_ENTRIES)
    contract = load_contract(root)
    if not entries and not contract.required:
        return ""

    lines: list[str] = []
    if entries:
        lines.append("Checks this workspace is known to have:")
        for entry in entries:
            proven = " (a previous run ran this)" if entry.source == "observed" else ""
            lines.append(f"  - {entry.kind}: `{entry.command}`{proven}")
    if contract.required:
        lines.append(
            "This project's verification contract requires: "
            + ", ".join(contract.required)
            + "."
        )
    return "\n".join(lines)


def enabled() -> bool:
    """Set ATLAS_VERIFICATION_LEDGER=0 to stop reading and writing the ledger."""
    return os.environ.get("ATLAS_VERIFICATION_LEDGER", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


__all__ = [
    "CONTRACT_RELPATH",
    "Contract",
    "DetectedCheck",
    "EMPTY_CONTRACT",
    "KNOWN_KINDS",
    "LedgerEntry",
    "available",
    "contract_for_run",
    "demand_hint",
    "detect",
    "enabled",
    "load_contract",
    "record_run",
    "sync_detected",
    "workspace_for_run",
]
