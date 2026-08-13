"""Tests for the run verification gate.

Two halves. The classifier is pure and gets table-driven cases covering the
distinctions the gate exists to make (mutation vs read, strong vs weak signal,
before vs after the change). The reader half goes through real audit events
emitted by the real `audit_service`, for each of the three runtime event
shapes — a classifier that is right about ObservedCall but cannot rebuild one
from the trail would verify nothing.
"""
from __future__ import annotations

import datetime
import json
import threading
import uuid

import pytest

from atlas_runtime import audit_service, run_executor, verification_gate
from atlas_runtime import db as db_module
from atlas_runtime.agents.base import AgentRuntime, RunOutcome
from atlas_runtime.run_service import start_run
from atlas_runtime.verification_gate import ObservedCall, classify

# -- classifier --------------------------------------------------------------


def _shell(command: str, *, failed: bool = False) -> ObservedCall:
    return ObservedCall(tool="terminal", args={"command": command}, failed=failed)


def _write(path: str) -> ObservedCall:
    return ObservedCall(tool="write_file", args={"path": path})


def test_read_only_run_has_nothing_to_verify():
    verdict = classify(
        [
            ObservedCall(tool="read_file", args={"path": "a.py"}),
            _shell("git log --oneline -5"),
            _shell("rg TODO src/"),
        ]
    )
    assert verdict.state == "no_mutations"
    assert verdict.mutations == ()


def test_write_then_passing_tests_is_verified():
    verdict = classify([_write("src/a.py"), _shell("pytest tests/ -q")])
    assert verdict.state == "verified"
    assert verdict.signals == ("tests",)
    assert len(verdict.mutations) == 1


def test_write_with_no_check_is_unverified():
    verdict = classify([_write("src/a.py"), ObservedCall(tool="read_file", args={"path": "b.py"})])
    assert verdict.state == "unverified"


def test_write_then_failing_tests_contradicts_a_success_claim():
    verdict = classify([_write("src/a.py"), _shell("pytest -q", failed=True)])
    assert verdict.state == "contradicted"
    assert verdict.failed_signals == ("tests",)
    assert verdict.signals == ()


def test_one_passing_check_wins_but_the_failure_is_still_recorded():
    verdict = classify(
        [_write("src/a.py"), _shell("ruff check .", failed=True), _shell("pytest -q")]
    )
    assert verdict.state == "verified"
    assert verdict.signals == ("tests",)
    assert verdict.failed_signals == ("lint",)


def test_tests_run_before_the_change_do_not_verify_it():
    """The check has to come after the thing it is checking."""
    verdict = classify([_shell("pytest -q"), _write("src/a.py")])
    assert verdict.state == "unverified"
    assert verdict.signals == ()


def test_git_status_alone_never_promotes_a_run_to_verified():
    verdict = classify([_write("src/a.py"), _shell("git status --short")])
    assert verdict.state == "unverified"
    assert verdict.weak_signals == ("review",)


def test_reading_back_a_written_file_is_a_weak_signal_only():
    verdict = classify(
        [
            _write("docs/plan.md"),
            ObservedCall(tool="read_file", args={"path": "docs\\plan.md"}),
        ]
    )
    assert verdict.state == "unverified"
    assert verdict.weak_signals == ("read_back",)


def test_reading_an_unrelated_file_is_not_a_read_back():
    verdict = classify(
        [_write("docs/plan.md"), ObservedCall(tool="read_file", args={"path": "src/other.py"})]
    )
    assert verdict.weak_signals == ()


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m 'wip'",
        "rm -f build/out.js",
        "sed -i 's/a/b/' f.txt",
        "echo hello > notes.txt",
        "npm install left-pad",
        "Set-Content -Path a.txt -Value b",
    ],
)
def test_mutating_shell_commands_are_seen(command: str):
    assert classify([_shell(command)]).state == "unverified"


@pytest.mark.parametrize(
    "command",
    [
        "cargo build 2>&1",
        "pytest -q > /dev/null",
        "dir > NUL",
        "grep -rn 'rm -rf' docs/",
    ],
)
def test_discards_and_mentions_are_not_mutations(command: str):
    """Redirection to a discard, and a command that merely names a dangerous one."""
    assert classify([_shell(command)]).state == "no_mutations"


def test_scratchpad_notes_are_working_memory_not_state_changes():
    verdict = classify(
        [ObservedCall(tool="atlas_scratchpad", args={"op": "write", "kind": "plan"})]
    )
    assert verdict.state == "no_mutations"


def test_materializing_a_disposable_tool_is_a_state_change():
    verdict = classify([ObservedCall(tool="atlas_scratchpad", args={"op": "materialize"})])
    assert verdict.state == "unverified"
    assert verdict.mutations == ("atlas_scratchpad:materialize",)


def test_execute_code_counts_only_when_the_code_writes():
    computing = ObservedCall(tool="execute_code", args={"code": "print(sum(range(10)))"})
    writing = ObservedCall(
        tool="execute_code", args={"code": "open('out.txt','w').write('x')"}
    )
    assert classify([computing]).state == "no_mutations"
    assert classify([writing]).state == "unverified"


def test_unknown_tools_are_ignored_rather_than_guessed_at():
    assert classify([ObservedCall(tool="some_future_tool", args={"x": 1})]).state == "no_mutations"


# -- claim taxonomy ----------------------------------------------------------


def test_describe_files_verified_as_evidence_and_unverified_as_uncertainty():
    verified = verification_gate.describe(classify([_write("a.py"), _shell("pytest -q")]))
    assert verified["evidence"] and not verified["uncertainties"]

    unverified = verification_gate.describe(classify([_write("a.py")]))
    assert unverified["uncertainties"] and not unverified["evidence"]


# -- audit-trail reader ------------------------------------------------------


@pytest.fixture(name="file_db")
def file_db_fixture(tmp_path):
    path = tmp_path / "atlas.db"
    conn = db_module.connect(path)
    db_module.apply_migrations(conn)
    try:
        yield conn
    finally:
        conn.close()


def _mission(conn, lock) -> str:
    mid = uuid.uuid4().hex
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with lock, conn:
        conn.execute(
            "INSERT INTO missions(id,title,intent,status,project,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (mid, "gate test", "", "pending", "", now, now),
        )
    return mid


def test_reader_rebuilds_native_shape(file_db):
    """native: tool_requested(data.tool, data.arguments) + tool_completed(data.call_id)."""
    conn, lock = file_db, threading.Lock()
    mid = _mission(conn, lock)
    run = start_run(conn, lock, mission_id=mid)

    audit_service.emit(
        conn, lock, run_id=run.id, event_type="tool_requested", tool_name="write_file",
        data={"tool": "write_file", "call_id": "c1", "arguments": {"path": "src/a.py"}},
    )
    audit_service.emit(
        conn, lock, run_id=run.id, event_type="tool_completed", tool_name="write_file",
        data={"tool": "write_file", "call_id": "c1", "is_error": False},
    )
    audit_service.emit(
        conn, lock, run_id=run.id, event_type="tool_requested", tool_name="terminal",
        data={"tool": "terminal", "call_id": "c2", "arguments": {"command": "pytest -q"}},
    )
    audit_service.emit(
        conn, lock, run_id=run.id, event_type="tool_failed", tool_name="terminal",
        data={"tool": "terminal", "call_id": "c2", "is_error": True},
    )

    calls = verification_gate.observed_calls(conn, run.id)
    assert [c.tool for c in calls] == ["write_file", "terminal"]
    assert calls[1].failed is True
    assert verification_gate.classify_run(conn, run.id).state == "contradicted"


def test_reader_rebuilds_claude_code_and_codex_shape(file_db):
    """claude_code/codex: tool_call(data.tool_name, data.input) keyed by tool_call_id."""
    conn, lock = file_db, threading.Lock()
    mid = _mission(conn, lock)
    run = start_run(conn, lock, mission_id=mid)

    audit_service.emit(
        conn, lock, run_id=run.id, event_type="tool_call", tool_name="Write",
        tool_call_id="t1",
        data={"tool_name": "Write", "tool_call_id": "t1", "input": {"file_path": "a.py"}},
    )
    audit_service.emit(
        conn, lock, run_id=run.id, event_type="tool_completed", tool_call_id="t1",
        data={"tool_call_id": "t1", "is_error": False},
    )
    audit_service.emit(
        conn, lock, run_id=run.id, event_type="tool_call", tool_name="shell",
        tool_call_id="t2",
        data={"tool_name": "shell", "tool_call_id": "t2", "input": {"command": ["pytest", "-q"]}},
    )
    audit_service.emit(
        conn, lock, run_id=run.id, event_type="tool_completed", tool_call_id="t2",
        data={"tool_call_id": "t2", "is_error": False},
    )

    assert verification_gate.classify_run(conn, run.id).state == "verified"


def test_a_large_write_still_names_the_file_it_wrote(file_db):
    """End to end over the exact case the live history got wrong.

    A 40 KB write goes through the real audit preview, into a real audit event,
    and back out through the reader. Before the preview kept its shape over the
    cap, the path was lost here and every large write was an anonymous mutation
    that could not be matched against a later read-back.
    """
    from atlas_runtime.agents.native import _json_safe_preview

    conn, lock = file_db, threading.Lock()
    mid = _mission(conn, lock)
    run = start_run(conn, lock, mission_id=mid)
    target = "C:/Users/Davi/Desktop/notes.md"

    audit_service.emit(
        conn, lock, run_id=run.id, event_type="tool_requested", tool_name="write_file",
        data={
            "tool": "write_file", "call_id": "w1",
            "arguments": _json_safe_preview({"path": target, "content": "z" * 40_000}, 2000),
        },
    )
    audit_service.emit(
        conn, lock, run_id=run.id, event_type="tool_requested", tool_name="read_file",
        data={"tool": "read_file", "call_id": "r1", "arguments": {"path": target}},
    )

    verdict = verification_gate.classify_run(conn, run.id)
    assert verdict.mutations == (f"write_file: {target}",)
    assert verdict.weak_signals == ("read_back",)


def test_arguments_recorded_as_a_json_string_are_still_read():
    """Runtimes disagree on whether args arrive as a mapping or as JSON text."""
    call = verification_gate.ObservedCall(
        tool="terminal", args=verification_gate._as_args('{"command": "pytest -q"}')
    )
    assert classify([_write("a.py"), call]).state == "verified"


# -- integration through the executor ---------------------------------------


class _TracingAgent(AgentRuntime):
    """An agent that writes a file and never checks it — the case the gate is for."""

    name = "tracing"

    def execute(self, conn, lock, *, mission_id, run_id, prompt, cancel_token=None):  # type: ignore[override]
        audit_service.emit(
            conn, lock, run_id=run_id, event_type="tool_requested", tool_name="write_file",
            data={"tool": "write_file", "call_id": "w1", "arguments": {"path": "src/a.py"}},
        )
        audit_service.emit(
            conn, lock, run_id=run_id, event_type="tool_completed", tool_name="write_file",
            data={"tool": "write_file", "call_id": "w1", "is_error": False},
        )
        return RunOutcome(status="succeeded", summary="refactored the module")


def test_executor_marks_an_unchecked_run_unverified(file_db):
    conn, lock = file_db, threading.Lock()
    mid = _mission(conn, lock)
    run = start_run(conn, lock, mission_id=mid)

    outcome = run_executor.execute_run(
        conn, lock, agent=_TracingAgent(), mission_id=mid, run_id=run.id, prompt="go",
    )

    assert outcome.status == "succeeded"  # the gate reports; it does not fail runs
    assert any("unverified" in u for u in outcome.uncertainties)

    row = conn.execute(
        "SELECT data FROM audit_events WHERE run_id=? AND event_type='verification_verdict'",
        (run.id,),
    ).fetchone()
    assert row is not None, "the verdict must be durable, not only in the returned outcome"
    assert json.loads(row[0])["state"] == "unverified"


def test_verdict_reaches_the_next_run_through_the_compounding_observation(file_db):
    """uncertainties already flow into goal observations — the gate rides that path."""
    conn, lock = file_db, threading.Lock()
    mid = _mission(conn, lock)
    run = start_run(conn, lock, mission_id=mid)

    run_executor.execute_run(
        conn, lock, agent=_TracingAgent(), mission_id=mid, run_id=run.id, prompt="go",
    )

    bodies = [
        row[0]
        for row in conn.execute(
            "SELECT body FROM observations WHERE run_id=?", (run.id,)
        ).fetchall()
    ]
    assert any("unverified" in body for body in bodies)


def test_gate_can_be_switched_off(file_db, monkeypatch):
    conn, lock = file_db, threading.Lock()
    monkeypatch.setenv("ATLAS_VERIFICATION_GATE", "0")
    mid = _mission(conn, lock)
    run = start_run(conn, lock, mission_id=mid)

    outcome = run_executor.execute_run(
        conn, lock, agent=_TracingAgent(), mission_id=mid, run_id=run.id, prompt="go",
    )
    assert outcome.uncertainties == ()
