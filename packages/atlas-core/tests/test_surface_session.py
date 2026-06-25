"""Tests for SurfaceSession / SurfaceEvent frozen models, migration 0016, and
audit event_type literals — Phase 10.3 plan 01 (SURF-01, AUD-01, D-013).
"""
import pathlib
import sqlite3

import pytest
from pydantic import ValidationError

from atlas_core.schemas.agent_contract import (
    ModelIdentity,
    SurfaceIdentity,
    WorkspaceIdentity,
)
from atlas_core.schemas.core import AuditEvent
from atlas_core.schemas.surface_session import (
    EventKind,
    SessionState,
    SurfaceEvent,
    SurfaceSession,
)

MIGRATIONS_DIR = (
    pathlib.Path(__file__).parent.parent.parent.parent / "infra" / "migrations"
)
MIGRATION_0016 = MIGRATIONS_DIR / "0016_surface_sessions.sql"


# ---------------------------------------------------------------------------
# SurfaceSession frozen model
# ---------------------------------------------------------------------------


def _session(**overrides) -> SurfaceSession:
    defaults = dict(
        surface=SurfaceIdentity(kind="cli", session_id="surf-1"),
        workspace=WorkspaceIdentity(kind="global", root="/tmp/atlas"),
        agent="atlas",
        model=ModelIdentity(provider="anthropic", model_id="claude-opus-4"),
        permission_mode="ask",
        prompt_version="1.0.0",
        tool_catalog_version="1.0.0",
        context_policy_version="1.0.0",
    )
    defaults.update(overrides)
    return SurfaceSession(**defaults)


def test_surface_session_constructs_and_roundtrips() -> None:
    """Constructs from valid identities and round-trips through model_dump."""
    s = _session()
    dumped = s.model_dump()
    assert dumped["agent"] == "atlas"
    assert dumped["surface"]["kind"] == "cli"
    assert dumped["workspace"]["kind"] == "global"
    assert dumped["model"]["provider"] == "anthropic"
    # round-trip
    s2 = SurfaceSession(**dumped)
    assert s2 == s


def test_surface_session_default_state_is_starting() -> None:
    assert _session().state == "starting"


def test_surface_session_id_auto_generates_uuid4() -> None:
    s1 = _session()
    s2 = _session()
    assert s1.id != s2.id
    # uuid4 string is 36 chars with 4 dashes
    assert len(s1.id) == 36 and s1.id.count("-") == 4


def test_surface_session_datetimes_serialize_to_iso() -> None:
    dumped = _session().model_dump()
    for field in ("created_at", "updated_at", "heartbeat_at"):
        assert isinstance(dumped[field], str)
        # ISO 8601 strings contain a 'T' separator
        assert "T" in dumped[field]


def test_surface_session_is_frozen() -> None:
    s = _session()
    with pytest.raises(ValidationError):
        s.state = "active"  # type: ignore[misc]


def test_surface_session_rejects_unknown_surface_kind() -> None:
    with pytest.raises(ValidationError):
        _session(surface=SurfaceIdentity(kind="bogus", session_id="x"))  # type: ignore[arg-type]


def test_surface_session_rejects_unknown_workspace_kind() -> None:
    with pytest.raises(ValidationError):
        _session(workspace=WorkspaceIdentity(kind="bogus", root="/x"))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# SurfaceEvent frozen model (D-013)
# ---------------------------------------------------------------------------


def test_surface_event_constructs_with_json_string_payload() -> None:
    e = SurfaceEvent(
        session_id="sess-1",
        seq=1,
        kind="text",
        occurred_at="2026-06-25T00:00:00+00:00",
        payload_json='{"text": "hi"}',
    )
    assert e.payload_json == '{"text": "hi"}'
    assert e.run_id is None


def test_surface_event_default_payload_is_empty_json_string() -> None:
    e = SurfaceEvent(
        session_id="sess-1", seq=0, kind="completion", occurred_at="2026-06-25T00:00:00+00:00"
    )
    assert e.payload_json == "{}"


def test_surface_event_rejects_dict_payload() -> None:
    """payload_json must be a str (D-013) — a dict must be rejected."""
    with pytest.raises(ValidationError):
        SurfaceEvent(
            session_id="sess-1",
            seq=1,
            kind="text",
            occurred_at="2026-06-25T00:00:00+00:00",
            payload_json={"text": "hi"},  # type: ignore[arg-type]
        )


def test_surface_event_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        SurfaceEvent(
            session_id="s", seq=1, kind="bogus", occurred_at="2026-06-25T00:00:00+00:00"  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# Audit event_type literals appended (AUD-01, Pattern 8 — no migration)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "event_type",
    [
        "surface_session_started",
        "surface_session_suspended",
        "surface_session_resumed",
        "surface_session_reclaimed",
        "run_cancelled",
        "permission_transition",
    ],
)
def test_audit_event_accepts_new_surface_literals(event_type: str) -> None:
    ev = AuditEvent(run_id="r-1", event_type=event_type)
    assert ev.event_type == event_type


def test_audit_event_still_accepts_existing_literal() -> None:
    assert AuditEvent(run_id="r-1", event_type="tool_call").event_type == "tool_call"


# ---------------------------------------------------------------------------
# Migration 0016 — table mirrors fields 1:1, soft run link, terminal trigger
# ---------------------------------------------------------------------------


def test_migration_0016_exists() -> None:
    assert MIGRATION_0016.exists(), f"Migration not found at {MIGRATION_0016}"


def test_migration_0016_creates_table_with_trigger() -> None:
    sql = MIGRATION_0016.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS surface_sessions" in sql
    assert "BEFORE UPDATE" in sql
    # soft run link: no FK on runs.session_id introduced here
    assert "REFERENCES runs(session_id)" not in sql


def test_migration_0016_applies_and_mirrors_fields() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(MIGRATION_0016.read_text(encoding="utf-8"))
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(surface_sessions)").fetchall()
        }
        expected = {
            "id",
            "surface_kind",
            "surface_session_id",
            "workspace_kind",
            "workspace_root",
            "project_id",
            "mission_id",
            "run_id",
            "agent",
            "model_provider",
            "model_id",
            "permission_mode",
            "prompt_version",
            "tool_catalog_version",
            "context_policy_version",
            "state",
            "owner_token",
            "owner_pid",
            "heartbeat_at",
            "created_at",
            "updated_at",
        }
        assert expected.issubset(cols), f"Missing columns: {expected - cols}"
    finally:
        conn.close()


def test_migration_0016_terminal_rows_are_immutable() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(MIGRATION_0016.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO surface_sessions"
            "(id, surface_kind, surface_session_id, workspace_kind, workspace_root, "
            "agent, model_provider, model_id, permission_mode, prompt_version, "
            "tool_catalog_version, context_policy_version, state, heartbeat_at, "
            "created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "sid-1", "cli", "surf-1", "global", "/tmp",
                "atlas", "anthropic", "m", "ask", "1.0.0",
                "1.0.0", "1.0.0", "completed", "t", "t", "t",
            ),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE surface_sessions SET state='active' WHERE id=?", ("sid-1",)
            )
    finally:
        conn.close()


def test_session_state_and_event_kind_literals_exposed() -> None:
    # SessionState / EventKind are importable Literal aliases (used by plan 03).
    assert SessionState is not None
    assert EventKind is not None
