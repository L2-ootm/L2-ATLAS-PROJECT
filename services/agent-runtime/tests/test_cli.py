"""Tests for atlas_runtime.cli.main — Typer CLI subcommands.

All tests are marked xfail(strict=True) because the service functions are stubs
in Wave 0. Wave 1 executors must implement the service layer to make these pass.

Uses typer.testing.CliRunner for CLI invocation without requiring the atlas
console script to be installed. _get_connection and _get_lock are monkeypatched
to inject the test in-memory database.

Fixtures from conftest.py (injected by name — do NOT import):
  db      — in-memory SQLite, WAL + FK ON + 0001_core.sql applied
  lock    — threading.Lock()
"""
import json

from typer.testing import CliRunner

from atlas_runtime.cli.main import app

runner = CliRunner()


def test_create_command_exits_zero(db, monkeypatch):
    """atlas mission create exits 0 and prints a 36-character UUID."""
    import atlas_runtime.cli.main as cli_main

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    result = runner.invoke(app, ["mission", "create", "--title", "Test", "--intent", "do X"])
    assert result.exit_code == 0
    assert len(result.output.strip()) == 36


def test_run_command_exits_zero(db, lock, monkeypatch):
    """atlas mission run <id> exits 0 after successfully starting a run."""
    import atlas_runtime.cli.main as cli_main
    from atlas_runtime import mission_service

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    mission = mission_service.create_mission(db, lock, title="Run Test")
    result = runner.invoke(app, ["mission", "run", mission.id])
    assert result.exit_code == 0


def test_run_command_attaches_surface_session(db, lock, monkeypatch):
    """A surface-started run keeps the owning surface id on the run row."""
    import atlas_runtime.cli.main as cli_main
    from atlas_runtime import mission_service

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    mission = mission_service.create_mission(db, lock, title="Surface Run")
    result = runner.invoke(
        app,
        ["mission", "run", "--session-id", "surface-1", mission.id],
    )
    assert result.exit_code == 0, result.output
    session_id = db.execute(
        "SELECT session_id FROM runs WHERE id=?",
        (result.output.strip(),),
    ).fetchone()[0]
    assert session_id == "surface-1"


def test_cancel_command_exits_zero(db, lock, monkeypatch):
    """atlas mission cancel <id> exits 0 after cancelling an active run."""
    import atlas_runtime.cli.main as cli_main
    from atlas_runtime import mission_service, run_service

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    mission = mission_service.create_mission(db, lock, title="Cancel Test")
    run_service.start_run(db, lock, mission_id=mission.id)
    result = runner.invoke(app, ["mission", "cancel", mission.id])
    assert result.exit_code == 0


def test_retry_command_reopens_and_prints_run_id(db, lock, monkeypatch):
    """atlas mission retry <id> reopens a failed mission and prints a new run id."""
    import atlas_runtime.cli.main as cli_main
    from atlas_runtime import mission_service

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    mission = mission_service.create_mission(db, lock, title="Retry CLI")
    db.execute("UPDATE missions SET status='failed' WHERE id=?", (mission.id,))
    db.commit()

    result = runner.invoke(app, ["mission", "retry", mission.id])
    assert result.exit_code == 0
    assert len(result.output.strip()) == 36  # a fresh run UUID
    status = db.execute("SELECT status FROM missions WHERE id=?", (mission.id,)).fetchone()[0]
    assert status == "running"  # start_run moved pending -> running


def test_retry_command_rejects_non_terminal(db, lock, monkeypatch):
    """atlas mission retry on a pending mission exits 1."""
    import atlas_runtime.cli.main as cli_main
    from atlas_runtime import mission_service

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    mission = mission_service.create_mission(db, lock, title="No Retry")
    result = runner.invoke(app, ["mission", "retry", mission.id])
    assert result.exit_code == 1
    assert "Cannot retry" in result.output


def test_run_show_context_prints_brief_and_starts_no_run(db, lock, monkeypatch):
    """atlas mission run <id> --show-context prints the brief and starts no run."""
    import atlas_runtime.cli.main as cli_main
    from atlas_runtime import focus_service, mission_service

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    focus_service.create_focus(db, lock, title="Ship the executor loop")
    mission = mission_service.create_mission(db, lock, title="Ctx Mission")

    result = runner.invoke(app, ["mission", "run", mission.id, "--show-context"])
    assert result.exit_code == 0
    assert "# context:" in result.output
    assert "ATLAS Operator Context" in result.output
    # Pure inspector — no run was created.
    count = db.execute(
        "SELECT COUNT(*) FROM runs WHERE mission_id=?", (mission.id,)
    ).fetchone()[0]
    assert count == 0


def test_status_command_exits_zero(db, monkeypatch):
    """atlas mission status <id> exits 0 and prints 'pending' for a new mission."""
    import atlas_runtime.cli.main as cli_main
    from atlas_runtime import mission_service

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    mission = mission_service.create_mission(db, cli_main._get_lock(), title="Status Test")
    result = runner.invoke(app, ["mission", "status", mission.id])
    assert result.exit_code == 0
    assert "pending" in result.output


def test_status_unknown_id_exits_one(db, monkeypatch):
    """atlas mission status <nonexistent-id> exits 1.

    This test is NOT marked xfail because the status command queries the DB
    directly (no service stub involved) and correctly returns exit code 1
    for an unknown mission ID without invoking any Wave 1 stub.
    """
    import atlas_runtime.cli.main as cli_main

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    result = runner.invoke(app, ["mission", "status", "nonexistent-uuid"])
    assert result.exit_code == 1


def test_archive_command_exits_zero_for_succeeded(db, lock, monkeypatch):
    import atlas_runtime.cli.main as cli_main
    from atlas_runtime import mission_service

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    mission = mission_service.create_mission(db, lock, title="Archive CLI")
    db.execute("UPDATE missions SET status='succeeded' WHERE id=?", (mission.id,))
    db.commit()

    result = runner.invoke(
        app,
        ["mission", "archive", "--delete-after-days", "7", mission.id],
    )

    assert result.exit_code == 0
    assert mission.id in result.output
    assert db.execute(
        "SELECT status FROM missions WHERE id=?", (mission.id,)
    ).fetchone()[0] == "archived"


def test_purge_archived_command_prints_count(db, lock, monkeypatch):
    import atlas_runtime.cli.main as cli_main
    from atlas_runtime import mission_service

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    mission = mission_service.create_mission(db, lock, title="Purge CLI")
    db.execute("UPDATE missions SET status='succeeded' WHERE id=?", (mission.id,))
    db.commit()
    mission_service.archive_mission(db, lock, mission_id=mission.id, delete_after_days=1)
    db.execute(
        "UPDATE mission_archive SET delete_after='2000-01-01T00:00:00+00:00' WHERE mission_id=?",
        (mission.id,),
    )
    db.commit()

    result = runner.invoke(app, ["mission", "purge-archived"])

    assert result.exit_code == 0
    assert result.output.strip() == "1"


def test_focus_create_show_list_archive(db, lock, monkeypatch):
    """atlas focus create/show/list/archive round-trip."""
    import atlas_runtime.cli.main as cli_main

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)

    created = runner.invoke(
        app,
        ["focus", "create", "--title", "Ship loop", "--framework", "GSD",
         "--priorities", "wp-1, wp-2", "--drivers", "wedge"],
    )
    assert created.exit_code == 0
    focus_id = created.output.strip()
    assert len(focus_id) == 36

    shown = runner.invoke(app, ["focus", "show"])
    assert shown.exit_code == 0
    body = json.loads(shown.output)
    assert body["title"] == "Ship loop"
    assert json.loads(body["priorities"]) == ["wp-1", "wp-2"]

    listed = runner.invoke(app, ["focus", "list"])
    assert listed.exit_code == 0
    assert len(json.loads(listed.output)) == 1

    archived = runner.invoke(app, ["focus", "archive", focus_id])
    assert archived.exit_code == 0
    assert runner.invoke(app, ["focus", "show"]).output.strip() == "none"


def test_run_exec_executes_started_run(db, lock, monkeypatch):
    """atlas run exec <run_id> drives an already-started run to terminal."""
    import atlas_runtime.cli.main as cli_main
    from atlas_runtime import mission_service, run_service

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    mission = mission_service.create_mission(db, lock, title="Exec Test", intent="do the thing")
    run = run_service.start_run(db, lock, mission_id=mission.id)

    result = runner.invoke(app, ["run", "exec", run.id])
    assert result.exit_code == 0
    assert result.output.strip() == "succeeded"
    assert db.execute("SELECT status FROM runs WHERE id=?", (run.id,)).fetchone()[0] == "succeeded"


def test_run_exec_unknown_run_exits_one(db, monkeypatch):
    import atlas_runtime.cli.main as cli_main

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    result = runner.invoke(app, ["run", "exec", "no-such-run"])
    assert result.exit_code == 1
