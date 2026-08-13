"""Tests for the verification contract and the workspace check ledger.

Three halves, matching the three things this module has to get right. The
contract loader is graded on what it *refuses* — an unknown check kind and a
malformed file must both degrade to "no contract", because a config typo that
marked every run in a project unverified would be worse than no contract at all.
Detection runs against real directories built in tmp_path rather than mocked
filesystems, since the whole point is reading marker files. And the ledger is
tested through the gate as well as directly: a durable record that the gate
never writes is a table, not a ledger.
"""
from __future__ import annotations

import datetime
import json
import threading
import uuid

import pytest

from atlas_runtime import db as db_module
from atlas_runtime import verification_gate, verification_ledger
from atlas_runtime.run_service import start_run
from atlas_runtime.verification_gate import ObservedCall, classify


@pytest.fixture(name="conn")
def conn_fixture(tmp_path):
    connection = db_module.connect(tmp_path / "atlas.db")
    db_module.apply_migrations(connection)
    try:
        yield connection
    finally:
        connection.close()


def _write_contract(root, payload) -> None:
    target = root / ".atlas"
    target.mkdir(parents=True, exist_ok=True)
    (target / "verification.json").write_text(
        payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8"
    )


# -- the contract ------------------------------------------------------------


def test_a_workspace_without_a_contract_requires_nothing(tmp_path):
    assert verification_ledger.load_contract(str(tmp_path)).required == ()
    assert verification_ledger.load_contract(None).required == ()


def test_a_declared_contract_is_read(tmp_path):
    _write_contract(tmp_path, {"required": ["tests", "lint"]})
    contract = verification_ledger.load_contract(str(tmp_path))
    assert contract.required == ("tests", "lint")
    assert contract.source.endswith("verification.json")


def test_a_contract_may_name_a_single_check_as_a_string(tmp_path):
    _write_contract(tmp_path, {"required": "tests"})
    assert verification_ledger.load_contract(str(tmp_path)).required == ("tests",)


def test_a_check_the_gate_cannot_observe_is_dropped(tmp_path):
    """Requiring something unobservable would mark every run in the project
    unverified forever, with no command that could ever satisfy it."""
    _write_contract(tmp_path, {"required": ["tests", "vibes"]})
    assert verification_ledger.load_contract(str(tmp_path)).required == ("tests",)


def test_a_malformed_contract_is_no_contract(tmp_path):
    _write_contract(tmp_path, "{not json at all")
    assert verification_ledger.load_contract(str(tmp_path)).required == ()


def test_a_contract_missing_the_required_key_is_no_contract(tmp_path):
    _write_contract(tmp_path, {"note": "we test everything, honest"})
    assert verification_ledger.load_contract(str(tmp_path)).required == ()


def test_the_contract_is_satisfied_by_what_actually_passed():
    contract = verification_ledger.Contract(required=("tests", "lint"))
    assert contract.missing(["tests"]) == ("lint",)
    assert contract.missing(["lint", "tests"]) == ()


# -- detection ---------------------------------------------------------------


def _kinds(checks) -> set[str]:
    return {check.kind for check in checks}


def _commands(checks) -> set[str]:
    return {check.command for check in checks}


def test_detects_a_python_project(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n[tool.ruff]\n[tool.mypy]\n", encoding="utf-8"
    )
    checks = verification_ledger.detect(str(tmp_path))
    assert _kinds(checks) == {"tests", "lint", "typecheck"}
    assert "pytest -q" in _commands(checks)
    assert "ruff check ." in _commands(checks)


def test_a_tests_directory_alone_is_not_a_suite(tmp_path):
    """A `tests/` folder in a repo with no python packaging proves nothing."""
    (tmp_path / "tests").mkdir()
    assert verification_ledger.detect(str(tmp_path)) == ()


def test_detects_a_node_project_and_its_package_manager(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"test": "vitest run", "build": "vite build"}}),
        encoding="utf-8",
    )
    (tmp_path / "pnpm-lock.yaml").write_text("", encoding="utf-8")
    commands = _commands(verification_ledger.detect(str(tmp_path)))
    assert "pnpm test" in commands
    assert "pnpm run build" in commands


def test_an_empty_script_is_not_a_check(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"test": "   "}}), encoding="utf-8"
    )
    assert verification_ledger.detect(str(tmp_path)) == ()


def test_detects_rust_and_go(tmp_path):
    (tmp_path / "Cargo.toml").write_text("[package]\n", encoding="utf-8")
    rust = _commands(verification_ledger.detect(str(tmp_path)))
    assert {"cargo test", "cargo clippy", "cargo build"} <= rust

    other = tmp_path / "go"
    other.mkdir()
    (other / "go.mod").write_text("module example.com/x\n", encoding="utf-8")
    assert "go test ./..." in _commands(verification_ledger.detect(str(other)))


def test_detects_a_makefile_target(tmp_path):
    (tmp_path / "Makefile").write_text("test:\n\techo hi\n", encoding="utf-8")
    assert "make test" in _commands(verification_ledger.detect(str(tmp_path)))


def test_a_directory_that_does_not_exist_detects_nothing():
    assert verification_ledger.detect("/no/such/place/at/all") == ()
    assert verification_ledger.detect(None) == ()


# -- the durable ledger ------------------------------------------------------


def test_detected_checks_land_in_the_ledger(conn, tmp_path):
    (tmp_path / "Cargo.toml").write_text("[package]\n", encoding="utf-8")
    written = verification_ledger.sync_detected(
        conn, threading.Lock(), root=str(tmp_path), project_id="p1"
    )
    assert written == 3
    entries = verification_ledger.available(conn, str(tmp_path))
    assert {e.command for e in entries} == {"cargo test", "cargo clippy", "cargo build"}
    assert all(e.source == "detected" for e in entries)


def test_a_run_records_the_command_it_actually_ran(conn, tmp_path):
    verdict = classify(
        [
            ObservedCall(tool="write_file", args={"path": "src/a.py"}),
            ObservedCall(tool="terminal", args={"command": "pytest -q tests/"}),
        ]
    )
    verification_ledger.record_run(
        conn, threading.Lock(), run_id="r1", verdict=verdict,
        root=str(tmp_path), project_id="p1",
    )
    entries = verification_ledger.available(conn, str(tmp_path))
    assert [(e.kind, e.command, e.source, e.last_status) for e in entries] == [
        ("tests", "pytest -q tests/", "observed", "passed")
    ]
    assert entries[0].last_run_id == "r1"


def test_a_failing_check_is_recorded_as_failed(conn, tmp_path):
    verdict = classify(
        [
            ObservedCall(tool="write_file", args={"path": "src/a.py"}),
            ObservedCall(tool="terminal", args={"command": "pytest -q"}, failed=True),
        ]
    )
    verification_ledger.record_run(
        conn, threading.Lock(), run_id="r1", verdict=verdict,
        root=str(tmp_path), project_id="",
    )
    entries = verification_ledger.available(conn, str(tmp_path))
    assert entries[0].last_status == "failed"


def test_detection_never_downgrades_an_observation(conn, tmp_path):
    """A marker file says a check could exist; a run says it does."""
    lock = threading.Lock()
    (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n", encoding="utf-8")
    verdict = classify(
        [
            ObservedCall(tool="write_file", args={"path": "src/a.py"}),
            ObservedCall(tool="terminal", args={"command": "pytest -q"}),
        ]
    )
    verification_ledger.record_run(
        conn, lock, run_id="r1", verdict=verdict, root=str(tmp_path), project_id=""
    )
    verification_ledger.sync_detected(conn, lock, root=str(tmp_path))

    observed = [
        e for e in verification_ledger.available(conn, str(tmp_path))
        if e.command == "pytest -q"
    ]
    assert observed and observed[0].source == "observed"
    assert observed[0].last_status == "passed"


def test_observed_checks_are_offered_before_guessed_ones(conn, tmp_path):
    lock = threading.Lock()
    (tmp_path / "Cargo.toml").write_text("[package]\n", encoding="utf-8")
    verification_ledger.sync_detected(conn, lock, root=str(tmp_path))
    verdict = classify(
        [
            ObservedCall(tool="write_file", args={"path": "src/a.rs"}),
            ObservedCall(tool="terminal", args={"command": "cargo nextest run"}),
        ]
    )
    verification_ledger.record_run(
        conn, lock, run_id="r1", verdict=verdict, root=str(tmp_path), project_id=""
    )
    assert verification_ledger.available(conn, str(tmp_path))[0].source == "observed"


def test_a_run_with_no_workspace_writes_nothing(conn):
    verification_ledger.record_run(
        conn, threading.Lock(), run_id="r1",
        verdict=classify([ObservedCall(tool="write_file", args={"path": "a.py"})]),
        root=None, project_id="",
    )
    assert conn.execute("SELECT COUNT(*) FROM verification_checks").fetchone()[0] == 0


# -- wiring: run -> workspace -> contract -> gate -----------------------------


def _project_run(conn, lock, root) -> str:
    """A run whose mission belongs to a project rooted at `root`."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    pid, mid = uuid.uuid4().hex, uuid.uuid4().hex
    with lock, conn:
        conn.execute(
            "INSERT INTO projects(id,name,root_path,created_at,updated_at) VALUES(?,?,?,?,?)",
            (pid, "ledger test", str(root), now, now),
        )
        conn.execute(
            "INSERT INTO missions(id,title,intent,status,project,project_id,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (mid, "ledger test", "", "pending", "", pid, now, now),
        )
    return start_run(conn, lock, mission_id=mid).id


def test_the_workspace_is_resolved_through_the_missions_project(conn, tmp_path):
    run_id = _project_run(conn, threading.Lock(), tmp_path)
    root, project_id = verification_ledger.workspace_for_run(conn, run_id)
    assert root == str(tmp_path.resolve())
    assert project_id


def test_the_gate_grades_a_run_against_its_projects_contract(conn, tmp_path):
    from atlas_runtime import audit_service

    lock = threading.Lock()
    _write_contract(tmp_path, {"required": ["tests", "lint"]})
    run_id = _project_run(conn, lock, tmp_path)

    audit_service.emit(
        conn, lock, run_id=run_id, event_type="tool_requested", tool_name="write_file",
        data={"tool": "write_file", "call_id": "c1", "arguments": {"path": "src/a.py"}},
    )
    audit_service.emit(
        conn, lock, run_id=run_id, event_type="tool_requested", tool_name="terminal",
        data={"tool": "terminal", "call_id": "c2", "arguments": {"command": "pytest -q"}},
    )

    graded = verification_gate.classify_run(conn, run_id)
    assert graded.state == "unverified"
    assert graded.missing_required == ("lint",)

    raw = verification_gate.classify_run(conn, run_id, use_contract=False)
    assert raw.state == "verified"


def test_the_demand_hint_names_this_projects_own_checks(conn, tmp_path):
    lock = threading.Lock()
    (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n", encoding="utf-8")
    _write_contract(tmp_path, {"required": ["tests"]})
    run_id = _project_run(conn, lock, tmp_path)
    verification_ledger.sync_detected(conn, lock, root=str(tmp_path))

    hint = verification_ledger.demand_hint(conn, run_id)
    assert "pytest -q" in hint
    assert "requires: tests" in hint


def test_the_demand_hint_is_silent_when_nothing_is_known(conn, tmp_path):
    run_id = _project_run(conn, threading.Lock(), tmp_path)
    assert verification_ledger.demand_hint(conn, run_id) == ""


def test_the_ledger_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("ATLAS_VERIFICATION_LEDGER", "0")
    assert verification_ledger.enabled() is False
