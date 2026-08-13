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

from atlas_runtime import (
    audit_service,
    run_executor,
    verification_gate,
    verification_ledger,
)
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


def test_running_the_file_you_just_wrote_is_verification():
    """The exact false negative the first live run produced.

    ATLAS wrote `adder.py` and checked it with
    `python -c "from adder import add; ..."` — a real check, scored `unverified`
    because it was not pytest. Matching on the stem is what makes it work: code
    refers to a module by stem, not by path.
    """
    verdict = classify(
        [
            _write("/tmp/livegate/adder.py"),
            _shell('cd "/tmp/livegate" && python -c "from adder import add; print(add(2,3))"'),
        ]
    )
    assert verdict.state == "verified"
    assert verdict.signals == ("exercised",)


def test_an_exercise_that_fails_contradicts_the_claim():
    verdict = classify(
        [_write("/tmp/adder.py"), _shell("python /tmp/adder.py", failed=True)]
    )
    assert verdict.state == "contradicted"
    assert verdict.failed_signals == ("exercised",)


def test_running_something_unrelated_is_not_verification():
    """Both halves are required: a runner *and* a reference to what was written."""
    verdict = classify([_write("/tmp/adder.py"), _shell("python /tmp/unrelated.py")])
    assert verdict.state == "unverified"


def test_merely_naming_the_file_is_not_running_it():
    verdict = classify([_write("/tmp/adder.py"), _shell("cat /tmp/adder.py")])
    assert verdict.state == "unverified"


def test_a_generic_stem_is_not_evidence_on_its_own():
    """Two-letter stems match almost any command; they are not a signal."""
    verdict = classify([_write("/tmp/io.py"), _shell("python manage.py migrate")])
    assert verdict.state == "unverified"


def test_git_status_alone_never_promotes_a_run_to_verified():
    verdict = classify([_write("src/a.py"), _shell("git status --short")])
    assert verdict.state == "unverified"
    assert verdict.weak_signals == ("review",)


def test_reading_back_a_written_file_is_a_weak_signal_only():
    verdict = classify(
        [
            _write("src/plan.py"),
            ObservedCall(tool="read_file", args={"path": "src\\plan.py"}),
        ]
    )
    assert verdict.state == "unverified"
    assert verdict.weak_signals == ("read_back",)


# -- documentation exemption -------------------------------------------------


def test_a_documentation_only_run_is_exempt_not_unverified():
    """There is no check that proves a README. Demanding one teaches noise."""
    verdict = classify([_write("docs/plan.md"), _write("README.md")])
    assert verdict.state == "exempt"
    assert len(verdict.mutations) == 2


def test_committing_documentation_does_not_lose_the_exemption():
    """git moves a change around; what needs checking is what was changed."""
    verdict = classify([_write("docs/plan.md"), _shell("git commit -am 'docs'")])
    assert verdict.state == "exempt"


def test_one_code_file_among_the_docs_removes_the_exemption():
    verdict = classify([_write("docs/plan.md"), _write("src/a.py")])
    assert verdict.state == "unverified"


def test_a_shell_mutation_beside_the_docs_removes_the_exemption():
    verdict = classify([_write("docs/plan.md"), _shell("rm -rf build/")])
    assert verdict.state == "unverified"


def test_config_is_not_documentation():
    """`.json`/`.toml` break things at runtime; prose does not."""
    assert classify([_write("tsconfig.json")]).state == "unverified"
    assert classify([_write("pyproject.toml")]).state == "unverified"


def test_a_doc_run_whose_check_failed_still_contradicts_its_claim():
    """If the run chose to check, the result of that check still counts."""
    verdict = classify([_write("docs/plan.md"), _shell("pytest -q", failed=True)])
    assert verdict.state == "contradicted"


def test_describe_files_an_exempt_run_as_an_inference_not_a_finding():
    described = verification_gate.describe(classify([_write("README.md")]))
    assert described["inferences"] and not described["uncertainties"]


# -- the operator's contract -------------------------------------------------


def _contract(*required: str):
    return verification_ledger.Contract(required=required, source=".atlas/verification.json")


def test_half_a_contract_is_not_a_verified_run():
    verdict = classify(
        [_write("src/a.py"), _shell("pytest -q")], _contract("tests", "lint")
    )
    assert verdict.state == "unverified"
    assert verdict.signals == ("tests",)
    assert verdict.missing_required == ("lint",)


def test_a_met_contract_verifies():
    verdict = classify(
        [_write("src/a.py"), _shell("pytest -q"), _shell("ruff check .")],
        _contract("tests", "lint"),
    )
    assert verdict.state == "verified"
    assert verdict.missing_required == ()


def test_no_contract_keeps_the_undeclared_behaviour():
    verdict = classify([_write("src/a.py"), _shell("pytest -q")], None)
    assert verdict.state == "verified"
    assert verdict.required == ()


def test_a_contract_is_not_charged_against_a_doc_only_run():
    verdict = classify([_write("README.md")], _contract("tests"))
    assert verdict.state == "exempt"
    assert verdict.missing_required == ()


def test_an_unmet_contract_names_what_is_missing():
    verdict = classify([_write("src/a.py"), _shell("pytest -q")], _contract("tests", "build"))
    described = verification_gate.describe(verdict)
    assert any("build" in u for u in described["uncertainties"])
    assert "missing_required" in verdict.as_payload()
    assert "build" in verification_gate.summarize(verdict.as_payload())


def test_the_command_behind_a_signal_is_recorded():
    """The ledger stores commands, not kinds — that is what a later run can run."""
    verdict = classify([_write("src/a.py"), _shell("python -m pytest tests/ -q")])
    assert verdict.signal_commands == (("tests", "python -m pytest tests/ -q"),)


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


def test_a_second_argumentless_event_does_not_erase_the_command(file_db):
    """The real native event sequence, taken from a live run.

    A native run emits `tool_requested` carrying the arguments and then a bare
    `tool_call` for the same call id from the tool layer. Letting the second
    overwrite the first blanked the command on every terminal call — the gate
    could not see the check the agent actually ran.
    """
    conn, lock = file_db, threading.Lock()
    mid = _mission(conn, lock)
    run = start_run(conn, lock, mission_id=mid)

    audit_service.emit(
        conn, lock, run_id=run.id, event_type="tool_requested", tool_name="write_file",
        data={"tool": "write_file", "call_id": "c1", "arguments": {"path": "/tmp/adder.py"}},
    )
    audit_service.emit(
        conn, lock, run_id=run.id, event_type="tool_requested", tool_name="terminal",
        data={
            "tool": "terminal", "call_id": "c2",
            "arguments": {"command": 'python -c "from adder import add; print(add(2,3))"'},
        },
    )
    audit_service.emit(  # the bare follow-up that used to clobber it
        conn, lock, run_id=run.id, event_type="tool_call", tool_name="terminal",
        data={"tool": "terminal", "call_id": "c2"},
    )
    audit_service.emit(
        conn, lock, run_id=run.id, event_type="tool_completed", tool_name="terminal",
        data={"tool": "terminal", "call_id": "c2", "is_error": False},
    )

    calls = {c.tool: c for c in verification_gate.observed_calls(conn, run.id)}
    assert calls["terminal"].args.get("command"), "the command must survive the second event"
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


def test_cli_shows_the_verdict_after_a_run(file_db, monkeypatch):
    """A verdict the operator never sees is half a mechanism.

    Asserts the shape too: `status` keeps the first line to itself because
    scripts read it, and the verdict follows on its own.
    """
    from typer.testing import CliRunner

    from atlas_runtime.cli.main import app

    conn, lock = file_db, threading.Lock()
    mid = _mission(conn, lock)
    monkeypatch.setattr("atlas_runtime.cli.main._get_connection", lambda: conn)
    monkeypatch.setattr("atlas_runtime.cli.main._get_lock", lambda: lock)
    monkeypatch.setattr("atlas_runtime.agents.get_agent", lambda name: _TracingAgent())
    monkeypatch.setattr(
        "atlas_runtime.cli.main._execute_run_chain",
        lambda conn_, lock_, **kw: run_executor.execute_run(
            conn_, lock_, agent=_TracingAgent(), mission_id=kw["mission_id"],
            run_id=kw["run_id"], prompt="go",
        ),
    )

    result = CliRunner().invoke(app, ["mission", "run", mid, "--execute"])
    assert result.exit_code == 0, result.output
    lines = [line for line in result.output.splitlines() if line.strip()]
    assert lines[-2] == "succeeded"
    assert lines[-1].startswith("verification: unverified — 1 change(s)")


def test_cli_stays_quiet_about_read_only_runs(file_db, monkeypatch):
    """A line on every run would train the operator to skip the ones that matter."""
    from typer.testing import CliRunner

    from atlas_runtime.cli.main import app

    class _Idle(AgentRuntime):
        name = "idle"

        def execute(self, conn, lock, *, mission_id, run_id, prompt, cancel_token=None):  # type: ignore[override]
            return RunOutcome(status="succeeded", summary="read some files")

    conn, lock = file_db, threading.Lock()
    mid = _mission(conn, lock)
    monkeypatch.setattr("atlas_runtime.cli.main._get_connection", lambda: conn)
    monkeypatch.setattr("atlas_runtime.cli.main._get_lock", lambda: lock)
    monkeypatch.setattr(
        "atlas_runtime.cli.main._execute_run_chain",
        lambda conn_, lock_, **kw: run_executor.execute_run(
            conn_, lock_, agent=_Idle(), mission_id=kw["mission_id"],
            run_id=kw["run_id"], prompt="go",
        ),
    )

    result = CliRunner().invoke(app, ["mission", "run", mid, "--execute"])
    assert result.exit_code == 0, result.output
    assert "verification:" not in result.output


def test_gate_can_be_switched_off(file_db, monkeypatch):
    conn, lock = file_db, threading.Lock()
    monkeypatch.setenv("ATLAS_VERIFICATION_GATE", "0")
    mid = _mission(conn, lock)
    run = start_run(conn, lock, mission_id=mid)

    outcome = run_executor.execute_run(
        conn, lock, agent=_TracingAgent(), mission_id=mid, run_id=run.id, prompt="go",
    )
    assert outcome.uncertainties == ()
