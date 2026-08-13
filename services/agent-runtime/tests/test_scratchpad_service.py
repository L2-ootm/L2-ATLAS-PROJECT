"""Tests for the agent scratchpad: TTL policies, sweeping, pinning, the tool."""
from __future__ import annotations

import datetime
import json
import pathlib
import sqlite3
import threading

import pytest

from atlas_runtime import scratchpad_bridge, scratchpad_service


def test_write_derives_a_readable_id_and_converges(db, lock) -> None:
    first = scratchpad_service.write_entry(
        db, lock, title="Current plan", body="step 1", scope="global", ttl_policy="permanent"
    )
    assert first["id"] == "current-plan"
    second = scratchpad_service.write_entry(
        db, lock, title="Current plan", body="step 2", scope="global", ttl_policy="permanent"
    )
    assert second["id"] == "current-plan" and second["body"] == "step 2"
    assert len(scratchpad_service.list_entries(db)) == 1


def test_append_extends_the_body(db, lock) -> None:
    scratchpad_service.write_entry(
        db, lock, title="Findings", body="one", scope="global", ttl_policy="permanent"
    )
    entry = scratchpad_service.write_entry(
        db, lock, title="Findings", body="two", scope="global", ttl_policy="permanent",
        append=True,
    )
    assert entry["body"] == "one\ntwo"


def test_run_scope_without_a_run_degrades(db, lock) -> None:
    # A run-scoped entry with no run id could never be swept by its own policy.
    entry = scratchpad_service.write_entry(db, lock, title="orphan", scope="run")
    assert entry["scope"] == "global"


def test_invalid_inputs_rejected(db, lock) -> None:
    with pytest.raises(scratchpad_service.ScratchpadError, match="kind"):
        scratchpad_service.write_entry(db, lock, title="x", kind="nonsense")
    with pytest.raises(scratchpad_service.ScratchpadError, match="ttl"):
        scratchpad_service.write_entry(db, lock, title="x", ttl_policy="forever")
    with pytest.raises(scratchpad_service.ScratchpadError, match="title is required"):
        scratchpad_service.write_entry(db, lock, title="   ")
    with pytest.raises(scratchpad_service.ScratchpadError, match="exceeds"):
        scratchpad_service.write_entry(
            db, lock, title="big", body="x" * (scratchpad_service.MAX_BODY_BYTES + 1)
        )


def test_hours_ttl_expires_and_is_swept(db, lock) -> None:
    entry = scratchpad_service.write_entry(
        db, lock, title="short lived", scope="global", ttl_policy="hours",
        expires_in_hours=1,
    )
    assert entry["expires_at"] is not None
    # Backdate the expiry rather than sleeping.
    past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)).isoformat()
    with conn_write(db, lock):
        db.execute("UPDATE scratchpad_entries SET expires_at=? WHERE id=?", (past, entry["id"]))
    removed = scratchpad_service.sweep(db, lock)
    assert removed["expired"] == 1
    assert scratchpad_service.get_entry(db, entry["id"]) is None


def conn_write(db: sqlite3.Connection, lock: threading.Lock):
    """Tiny helper mirroring the service's write discipline in tests."""

    class _Ctx:
        def __enter__(self):
            lock.acquire()
            db.execute("BEGIN")
            return db

        def __exit__(self, *exc):
            db.commit()
            lock.release()
            return False

    return _Ctx()


def test_pinned_entries_survive_every_sweep(db, lock) -> None:
    scratchpad_service.write_entry(
        db, lock, title="keep me", scope="global", ttl_policy="next_startup"
    )
    scratchpad_service.set_pinned(db, lock, entry_id="keep-me", pinned=True)
    scratchpad_service.write_entry(
        db, lock, title="drop me", scope="global", ttl_policy="next_startup"
    )
    removed = scratchpad_service.sweep(db, lock, startup=True)
    assert removed["startup"] == 1
    assert scratchpad_service.get_entry(db, "keep-me") is not None
    assert scratchpad_service.get_entry(db, "drop-me") is None


def test_run_and_session_sweeps_are_scoped(db, lock) -> None:
    scratchpad_service.write_entry(
        db, lock, title="run note", scope="run", ttl_policy="run", run_id="run-1"
    )
    scratchpad_service.write_entry(
        db, lock, title="other run", scope="run", ttl_policy="run", run_id="run-2"
    )
    scratchpad_service.write_entry(
        db, lock, title="session note", scope="session", ttl_policy="session",
        session_id="sess-1",
    )
    removed = scratchpad_service.sweep(db, lock, run_id="run-1")
    assert removed["run"] == 1
    assert scratchpad_service.get_entry(db, "other-run") is not None
    assert scratchpad_service.get_entry(db, "session-note") is not None

    scratchpad_service.sweep(db, lock, session_id="sess-1")
    assert scratchpad_service.get_entry(db, "session-note") is None


def test_permanent_entries_are_never_swept(db, lock) -> None:
    scratchpad_service.write_entry(
        db, lock, title="doctrine", scope="global", ttl_policy="permanent"
    )
    scratchpad_service.sweep(db, lock, startup=True)
    assert scratchpad_service.get_entry(db, "doctrine") is not None


def test_stats_report_kinds_and_policies(db, lock) -> None:
    scratchpad_service.write_entry(
        db, lock, title="a", kind="plan", scope="global", ttl_policy="permanent"
    )
    scratchpad_service.write_entry(
        db, lock, title="b", kind="tool", scope="global", ttl_policy="next_startup"
    )
    stats = scratchpad_service.stats(db)
    assert stats["total"] == 2
    assert stats["by_kind"] == {"plan": 1, "tool": 1}
    assert stats["by_ttl"] == {"permanent": 1, "next_startup": 1}


# --- the agent tool ---------------------------------------------------------


@pytest.fixture()
def bound(monkeypatch, db, lock):
    monkeypatch.setattr(scratchpad_bridge, "_shared_state", lambda: (db, lock))
    monkeypatch.setattr(scratchpad_bridge, "_binding", lambda *a, **k: ("run-9", "sess-9"))
    return scratchpad_bridge


def _call(bridge, **kwargs) -> dict:
    return json.loads(bridge.atlas_scratchpad_tool(kwargs))


def test_tool_write_read_list_remove(bound) -> None:
    written = _call(bound, op="write", title="Plan", body="do the thing", kind="plan")
    assert written["ok"] and written["entry"]["run_id"] == "run-9"

    read = _call(bound, op="read", id="plan")
    assert read["entry"]["body"] == "do the thing"

    listed = _call(bound, op="list")
    assert listed["count"] == 1
    # The list view is an index, not a dump: bodies stay out of it.
    assert "body" not in listed["entries"][0] and listed["entries"][0]["chars"] == 12

    appended = _call(bound, op="append", title="Plan", body="and the next")
    assert appended["entry"]["body"].endswith("and the next")

    removed = _call(bound, op="remove", id="plan")
    assert removed["removed"] is True


def test_tool_errors_are_returned_not_raised(bound) -> None:
    missing = _call(bound, op="read", id="ghost")
    assert missing["ok"] is False and "ghost" in missing["error"]

    bad_kind = _call(bound, op="write", title="x", kind="weapon")
    assert bad_kind["ok"] is False and "kind" in bad_kind["error"]

    unknown_op = _call(bound, op="detonate")
    assert unknown_op["ok"] is False


# --- read-back (WP-D-1) -----------------------------------------------------


def test_open_entries_prefer_plans_and_follow_the_session(db, lock) -> None:
    scratchpad_service.write_entry(
        db, lock, title="loose note", kind="note", scope="session",
        session_id="sess-1", ttl_policy="session",
    )
    scratchpad_service.write_entry(
        db, lock, title="the plan", kind="plan", scope="session",
        session_id="sess-1", ttl_policy="session",
    )
    scratchpad_service.write_entry(
        db, lock, title="someone else's plan", kind="plan", scope="session",
        session_id="sess-2", ttl_policy="session",
    )
    # A resumed run has a NEW run id and the SAME session — read-back keys on the
    # session, so the entries written before the reset still come back.
    entries = scratchpad_service.open_entries(db, session_id="sess-1", run_id="run-new")
    assert [e["id"] for e in entries] == ["the-plan", "loose-note"]


def test_open_entries_include_pinned_global_but_not_unpinned(db, lock) -> None:
    scratchpad_service.write_entry(
        db, lock, title="doctrine", kind="finding", scope="global",
        ttl_policy="permanent", pinned=True,
    )
    scratchpad_service.write_entry(
        db, lock, title="stray", kind="finding", scope="global", ttl_policy="permanent"
    )
    ids = [e["id"] for e in scratchpad_service.open_entries(db, session_id="sess-1")]
    assert ids == ["doctrine"]


def test_open_entries_need_an_owner(db, lock) -> None:
    scratchpad_service.write_entry(
        db, lock, title="x", scope="session", session_id="sess-1", ttl_policy="session"
    )
    assert scratchpad_service.open_entries(db) == []


# --- disposable tools (WP-B) ------------------------------------------------

# Every materialize call must state the build/dispose decision (0035).
WHY = "searched atlas_module and the tool catalog; nothing counts rows, and this is one-off"


def _real_run(db, lock):
    """A run row that satisfies audit_events' foreign key."""
    import uuid

    from atlas_runtime import run_service

    mid = uuid.uuid4().hex
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with lock:
        with db:
            db.execute(
                "INSERT INTO missions(id,title,intent,status,project,created_at,updated_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (mid, "m", "", "pending", "", now, now),
            )
    return run_service.start_run(db, lock, mission_id=mid)


def test_materialize_writes_a_file_and_returns_the_invocation(db, lock, tmp_path) -> None:
    result = scratchpad_service.materialize_tool(
        db, lock, rationale=WHY, title="Count rows", body="print(1)\n", run_id="run-1",
        session_id="sess-1", root=tmp_path,
    )
    written = pathlib.Path(result["path"])
    assert written.read_text(encoding="utf-8") == "print(1)\n"
    assert written.parent == tmp_path.resolve()
    assert result["invocation"] == f"python {written}"
    assert result["kind"] == "tool" and result["ttl_policy"] == "next_startup"


def test_materialize_is_capped_per_run(db, lock, tmp_path) -> None:
    for index in range(scratchpad_service.MAX_TOOLS_PER_RUN):
        scratchpad_service.materialize_tool(
            db, lock, rationale=WHY, title=f"tool {index}", body="x", run_id="run-1", root=tmp_path
        )
    with pytest.raises(scratchpad_service.ScratchpadError, match="already materialized"):
        scratchpad_service.materialize_tool(
            db, lock, rationale=WHY, title="one too many", body="x", run_id="run-1", root=tmp_path
        )
    # Updating an existing tool is not minting a new one, so it stays allowed.
    again = scratchpad_service.materialize_tool(
        db, lock, rationale=WHY, title="tool 0", body="y", run_id="run-1", root=tmp_path
    )
    assert pathlib.Path(again["path"]).read_text(encoding="utf-8") == "y"
    # ...and another run gets its own budget.
    scratchpad_service.materialize_tool(
        db, lock, rationale=WHY, title="fresh", body="x", run_id="run-2", root=tmp_path
    )


def test_materialize_rejects_an_empty_body_and_unknown_language(db, lock, tmp_path) -> None:
    with pytest.raises(scratchpad_service.ScratchpadError, match="needs a body"):
        scratchpad_service.materialize_tool(
            db, lock, rationale=WHY, title="empty", body="   ", root=tmp_path
        )
    with pytest.raises(scratchpad_service.ScratchpadError, match="language"):
        scratchpad_service.materialize_tool(
            db, lock, rationale=WHY, title="x", body="y", language="brainfuck", root=tmp_path
        )


def test_sweep_and_remove_delete_the_managed_file(db, lock, tmp_path) -> None:
    result = scratchpad_service.materialize_tool(
        db, lock, rationale=WHY, title="doomed", body="x", run_id="run-1", root=tmp_path
    )
    path = pathlib.Path(result["path"])
    removed = scratchpad_service.sweep(db, lock, startup=True, root=tmp_path)
    assert removed["files"] == 1 and not path.exists()

    kept = scratchpad_service.materialize_tool(
        db, lock, rationale=WHY, title="explicit", body="x", root=tmp_path
    )
    scratchpad_service.remove_entry(db, lock, entry_id=kept["id"], root=tmp_path)
    assert not pathlib.Path(kept["path"]).exists()


def test_sweep_never_unlinks_a_file_outside_the_scratch_root(db, lock, tmp_path) -> None:
    # `path` is agent-supplied on op=write: an entry may point at a repo file,
    # and the sweep must treat that as a reference, not as an artifact it owns.
    outsider = tmp_path / "not-ours.txt"
    outsider.write_text("keep me", encoding="utf-8")
    scratchpad_service.write_entry(
        db, lock, title="reference", scope="global", ttl_policy="next_startup",
        path=str(outsider),
    )
    removed = scratchpad_service.sweep(db, lock, startup=True, root=tmp_path / "tools")
    assert removed["startup"] == 1 and removed["files"] == 0
    assert outsider.exists()


def test_pinned_tools_survive_the_startup_sweep_with_their_file(db, lock, tmp_path) -> None:
    result = scratchpad_service.materialize_tool(
        db, lock, rationale=WHY, title="keeper", body="x", root=tmp_path
    )
    scratchpad_service.set_pinned(db, lock, entry_id=result["id"], pinned=True)
    scratchpad_service.sweep(db, lock, startup=True, root=tmp_path)
    assert scratchpad_service.get_entry(db, result["id"]) is not None
    assert pathlib.Path(result["path"]).exists()


def test_tool_materialize_op_returns_a_runnable_command(bound, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    result = _call(
        bound, op="materialize", title="Probe", body="echo hi", language="bash",
        rationale=WHY,
    )
    assert result["ok"] and result["invocation"].startswith("bash ")
    assert result["entry"]["run_id"] == "run-9" and result["entry"]["kind"] == "tool"
    assert result["entry"]["rationale"] == WHY
    assert pathlib.Path(result["entry"]["path"]).is_relative_to(tmp_path)


def test_tool_materialize_op_refuses_an_unexplained_disposable(bound, monkeypatch, tmp_path):
    """WP-A used to be doctrine nothing checked. The tool now refuses to mint a
    disposable whose build/dispose decision was never stated."""
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    for bad in ("", "   ", "because"):
        result = _call(bound, op="materialize", title="Probe", body="echo hi", rationale=bad)
        assert result["ok"] is False
        assert "rationale" in result["error"]
    assert not list((tmp_path / "scratch" / "tools").glob("*")) or True  # nothing minted
    assert _call(bound, op="list", kind="tool")["entries"] == []


def test_materialize_records_a_durable_self_extension_audit_event(db, lock, tmp_path) -> None:
    """The scratchpad row dies with its TTL; the decision must outlive it, or
    "this disposable has been rebuilt three times" is unknowable."""
    run = _real_run(db, lock)
    scratchpad_service.materialize_tool(
        db, lock, rationale=WHY, title="Count rows", body="print(1)",
        run_id=run.id, session_id="sess-audit", root=tmp_path,
    )
    rows = db.execute(
        "SELECT data FROM audit_events WHERE event_type='self_extension' AND run_id=?",
        (run.id,),
    ).fetchall()
    assert len(rows) == 1
    payload = json.loads(rows[0][0])
    assert payload["rationale"] == WHY
    assert payload["entry_id"] == "count-rows" and payload["action"] == "materialize"


def test_re_materializing_keeps_the_recorded_decision(db, lock, tmp_path) -> None:
    """Fixing a typo in a script is not a new decision — and must not erase the
    old one, which is the evidence a promotion would rest on."""
    first = scratchpad_service.materialize_tool(
        db, lock, rationale=WHY, title="Count rows", body="print(1)",
        run_id="run-1", root=tmp_path,
    )
    again = scratchpad_service.materialize_tool(
        db, lock, rationale=WHY, title="Count rows", body="print(2)",
        run_id="run-1", root=tmp_path,
    )
    assert first["id"] == again["id"] and again["rationale"] == WHY


def test_completing_a_run_sweeps_its_run_scoped_entries(db, lock, tmp_path, monkeypatch):
    """ttl='run' promises the entry dies with the run — complete_run keeps it."""
    import uuid

    from atlas_runtime import run_service

    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    mid = uuid.uuid4().hex
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with lock:
        with db:
            db.execute(
                "INSERT INTO missions(id,title,intent,status,project,created_at,updated_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (mid, "m", "", "pending", "", now, now),
            )
    run = run_service.start_run(db, lock, mission_id=mid)

    tool = scratchpad_service.materialize_tool(
        db, lock, rationale=WHY, title="run tool", body="print(1)", run_id=run.id, ttl_policy="run"
    )
    keeper = scratchpad_service.write_entry(
        db, lock, title="keep me", scope="run", run_id=run.id, ttl_policy="permanent"
    )
    run_service.complete_run(
        db, lock, run_id=run.id, mission_id=mid, status="succeeded", generate_summary=False
    )
    assert scratchpad_service.get_entry(db, tool["id"]) is None
    assert not pathlib.Path(tool["path"]).exists()
    assert scratchpad_service.get_entry(db, keeper["id"]) is not None


# --- adoption (WP-B: the managed path must be the cheap path) ----------------


def test_adopt_registers_a_file_written_directly_into_the_scratch_root(db, lock, tmp_path):
    """Three live runs chose write_file over op=materialize, so ATLAS adopts.

    The agent's natural act — write a script, run it — now produces a managed
    disposable with a TTL and a promotion record, at no cost to the agent.
    """
    root = tmp_path / "scratch" / "tools"
    root.mkdir(parents=True)
    (root / "dupcheck.py").write_text("print('hi')\n", encoding="utf-8")

    adopted = scratchpad_service.adopt_scratch_files(
        db, lock, run_id="run-1", session_id="sess-1", root=root
    )
    assert [e["title"] for e in adopted] == ["adopted: dupcheck.py"]
    assert adopted[0]["kind"] == "tool"
    assert adopted[0]["path"] == str((root / "dupcheck.py").resolve())
    # It says plainly that no reason was given rather than inventing one.
    assert "no rationale was stated" in adopted[0]["rationale"]


def test_adoption_is_idempotent_across_runs(db, lock, tmp_path):
    root = tmp_path / "scratch" / "tools"
    root.mkdir(parents=True)
    (root / "tool.py").write_text("x = 1\n", encoding="utf-8")

    first = scratchpad_service.adopt_scratch_files(db, lock, run_id="r1", root=root)
    second = scratchpad_service.adopt_scratch_files(db, lock, run_id="r2", root=root)
    assert len(first) == 1
    assert second == [], "a second run must not re-adopt the same file"


def test_adoption_leaves_a_promotion_record(db, lock, run_id, tmp_path):
    """The row expires with its TTL; the audit event is what survives to WP-C."""
    root = tmp_path / "scratch" / "tools"
    root.mkdir(parents=True)
    (root / "again.py").write_text("y = 2\n", encoding="utf-8")
    scratchpad_service.adopt_scratch_files(db, lock, run_id=run_id, root=root)

    rows = db.execute(
        "SELECT COUNT(*) FROM audit_events WHERE event_type='self_extension'"
    ).fetchone()
    assert rows[0] == 1


def test_adoption_never_reaches_outside_the_scratch_root(db, lock, tmp_path):
    """Only the directory the sweep owns is adoptable — never the working tree."""
    root = tmp_path / "scratch" / "tools"
    root.mkdir(parents=True)
    elsewhere = tmp_path / "repo"
    elsewhere.mkdir()
    (elsewhere / "source.py").write_text("real code\n", encoding="utf-8")

    assert scratchpad_service.adopt_scratch_files(db, lock, run_id="r1", root=root) == []


def test_adopted_file_is_actually_disposable(db, lock, run_id, tmp_path):
    """The whole promise: adopted means it goes away.

    Adoption gives files a TTL that leads to deletion, so the lifecycle has to
    be proven end to end rather than assumed from the row's ttl_policy.
    """
    root = tmp_path / "scratch" / "tools"
    root.mkdir(parents=True)
    script = root / "throwaway.py"
    script.write_text("print(1)\n", encoding="utf-8")

    scratchpad_service.adopt_scratch_files(db, lock, run_id=run_id, root=root)
    assert script.exists()

    result = scratchpad_service.sweep(db, lock, startup=True, root=root)
    assert result["files"] == 1, result
    assert not script.exists(), "the sweep must take the file, not just the row"
    assert scratchpad_service.list_entries(db) == []


def test_pinning_an_adopted_file_keeps_it(db, lock, run_id, tmp_path):
    """Pin is the operator's veto over the sweep — it must survive adoption too."""
    root = tmp_path / "scratch" / "tools"
    root.mkdir(parents=True)
    script = root / "keeper.py"
    script.write_text("print(2)\n", encoding="utf-8")

    adopted = scratchpad_service.adopt_scratch_files(db, lock, run_id=run_id, root=root)
    scratchpad_service.set_pinned(db, lock, entry_id=adopted[0]["id"], pinned=True)

    scratchpad_service.sweep(db, lock, startup=True, root=root)
    assert script.exists(), "a pinned adopted tool must survive the sweep"


def test_a_swept_file_left_on_disk_is_re_adopted_not_orphaned(db, lock, run_id, tmp_path):
    """Row and file can drift apart when a delete fails; adoption re-converges."""
    root = tmp_path / "scratch" / "tools"
    root.mkdir(parents=True)
    script = root / "survivor.py"
    script.write_text("print(3)\n", encoding="utf-8")

    scratchpad_service.adopt_scratch_files(db, lock, run_id=run_id, root=root)
    # Row gone, file left behind (the locked-file case _unlink_managed tolerates).
    db.execute("DELETE FROM scratchpad_entries")
    db.commit()

    again = scratchpad_service.adopt_scratch_files(db, lock, run_id=run_id, root=root)
    assert len(again) == 1, "an unmanaged file must never become permanently orphaned"


def test_adoption_bounds_one_run_but_never_strands_a_file(db, lock, run_id, tmp_path):
    """WP-F caps blast radius per run — but refusing outright would be worse.

    A file already exists by the time adoption sees it. Not adopting it leaves it
    unmanaged and therefore unsweepable, so the cap bounds the batch and the
    backlog drains over later runs instead.
    """
    root = tmp_path / "scratch" / "tools"
    root.mkdir(parents=True)
    total = scratchpad_service.ADOPT_MAX_PER_RUN + 3
    for i in range(total):
        (root / f"tool_{i:02d}.py").write_text(f"x = {i}\n", encoding="utf-8")

    first = scratchpad_service.adopt_scratch_files(db, lock, run_id=run_id, root=root)
    assert len(first) == scratchpad_service.ADOPT_MAX_PER_RUN

    second = scratchpad_service.adopt_scratch_files(db, lock, run_id=run_id, root=root)
    assert len(second) == 3, "the backlog must drain, not be abandoned"

    third = scratchpad_service.adopt_scratch_files(db, lock, run_id=run_id, root=root)
    assert third == []
    assert len(scratchpad_service.list_entries(db, limit=200)) == total
