"""Foundation delegation observer bridge (F2).

Proves the real round trip: ensure_foundation_bridge registers atlas_audit's
hooks with the foundation PluginManager singleton, and a `subagent_stop`
fired through `hermes_cli.plugins.invoke_hook` — the exact call
`delegate_tool.py` makes when a child agent finishes — lands as a
`subagent_run` AuditEvent row attributed to the run.
"""
from __future__ import annotations

from atlas_runtime import subagent_service


def test_ensure_foundation_bridge_registers_and_emits(db, run_id):
    import atlas_audit

    try:
        assert subagent_service.ensure_foundation_bridge(db, run_id=run_id) is True

        from hermes_cli.plugins import invoke_hook

        invoke_hook(
            "subagent_stop",
            parent_session_id=run_id,
            child_role="researcher",
            child_summary="delegated work finished",
            child_status="completed",
            duration_ms=42,
        )
        row = db.execute(
            "SELECT data FROM audit_events WHERE event_type='subagent_run' AND run_id=?",
            (run_id,),
        ).fetchone()
        assert row is not None
        assert "researcher" in row[0]
    finally:
        atlas_audit.set_connection(None)


def test_ensure_foundation_bridge_maps_surface_session(db, run_id):
    import atlas_audit

    try:
        assert (
            subagent_service.ensure_foundation_bridge(
                db, run_id=run_id, session_id="surface-abc"
            )
            is True
        )
        with atlas_audit._STATE_LOCK:
            assert atlas_audit._CURRENT_RUN.get(run_id) == run_id
            assert atlas_audit._CURRENT_RUN.get("surface-abc") == run_id
    finally:
        atlas_audit.set_connection(None)


def test_ensure_foundation_bridge_fail_open_without_foundation(db, run_id, monkeypatch):
    monkeypatch.setattr(subagent_service, "_foundation_on_path", lambda: False)
    assert subagent_service.ensure_foundation_bridge(db, run_id=run_id) is False
