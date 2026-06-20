"""Tests for atlas_core.schemas.core — SCHEMA-01 (import, instantiation, serialization) and SCHEMA-03 (model_json_schema)."""

import json

import pytest


# --- Import tests ---


def test_import() -> None:
    """SCHEMA-01: importing Mission from atlas_core.schemas.core must not raise."""
    from atlas_core.schemas.core import Mission  # noqa: F401


def test_all_models_importable() -> None:
    """SCHEMA-01: all 7 model names and SECRET_PATTERNS must be importable."""
    from atlas_core.schemas.core import (  # noqa: F401
        Artifact,
        AuditEvent,
        Mission,
        Run,
        SECRET_PATTERNS,
        Source,
        ToolCall,
        WikiPage,
    )


# --- Instantiation tests ---


def test_model_instantiation_mission() -> None:
    """SCHEMA-01: Mission with only title produces correct defaults."""
    from atlas_core.schemas.core import Mission

    m = Mission(title="hello")
    assert m.id != ""
    assert m.status == "pending"
    assert m.intent == ""


def test_model_instantiation_audit_event() -> None:
    """SCHEMA-01: AuditEvent with required fields has correct defaults."""
    import datetime

    from atlas_core.schemas.core import AuditEvent

    ae = AuditEvent(run_id="r1", event_type="llm_call")
    assert ae.data == "{}"
    assert isinstance(ae.timestamp, datetime.datetime)


# --- Serialization tests ---


def test_serialization_no_datetime_objects() -> None:
    """SCHEMA-01: model_dump() must not contain datetime objects — created_at must be str."""
    from atlas_core.schemas.core import Mission

    dumped = Mission(title="t").model_dump()
    assert isinstance(dumped["created_at"], str), (
        f"created_at should be str, got {type(dumped['created_at'])}"
    )


def test_serialization_json_safe() -> None:
    """SCHEMA-01: model_dump() output must be passable to json.dumps without TypeError."""
    from atlas_core.schemas.core import Mission

    dumped = Mission(title="t").model_dump()
    # Must not raise TypeError
    json.dumps(dumped)


def test_serialization_no_dict_types() -> None:
    """SCHEMA-01: AuditEvent.data in model_dump() must be str, not dict."""
    from atlas_core.schemas.core import AuditEvent

    dumped = AuditEvent(run_id="r", event_type="llm_call").model_dump()
    assert isinstance(dumped["data"], str)


def test_path_is_str() -> None:
    """SCHEMA-01: Artifact.path in model_dump() must be str, not pathlib.Path."""
    from atlas_core.schemas.core import Artifact

    dumped = Artifact(run_id="r", path="/tmp/f", artifact_type="file_write").model_dump()
    assert isinstance(dumped["path"], str)


# --- JSON Schema tests ---


def test_json_schema_valid_mission() -> None:
    """SCHEMA-03: Mission.model_json_schema() returns a dict with a 'properties' key."""
    from atlas_core.schemas.core import Mission

    schema = Mission.model_json_schema()
    assert isinstance(schema, dict)
    assert "properties" in schema


def test_json_schema_all_fields_present() -> None:
    """SCHEMA-03: Mission JSON Schema must contain exactly its canonical fields.

    project_id is the folder-backed project link added in 0005_projects.sql (P3).
    """
    from atlas_core.schemas.core import Mission

    props = set(Mission.model_json_schema()["properties"].keys())
    expected = {
        "id", "title", "intent", "status", "project", "project_id",
        "created_at", "updated_at",
    }
    assert props == expected, f"Unexpected field set: {props}"


def test_json_schema_status_enum() -> None:
    """SCHEMA-03: Mission.status JSON Schema must expose lifecycle values."""
    from atlas_core.schemas.core import Mission

    status_schema = Mission.model_json_schema()["properties"]["status"]
    # Pydantic may inline enum or use $ref; resolve either case
    if "enum" in status_schema:
        enum_values = status_schema["enum"]
    elif "anyOf" in status_schema:
        enum_values = []
        for item in status_schema["anyOf"]:
            enum_values.extend(item.get("enum", []))
    else:
        # Fallback: check allOf/const patterns
        enum_values = status_schema.get("enum", [])
    assert "pending" in enum_values, f"'pending' not found in status schema: {status_schema}"
    assert "archived" in enum_values, f"'archived' not found in status schema: {status_schema}"


def test_json_schema_all_models() -> None:
    """SCHEMA-03: model_json_schema() on each of the 7 models must return a dict with 'properties'."""
    from atlas_core.schemas.core import (
        Artifact,
        AuditEvent,
        Mission,
        Run,
        Source,
        ToolCall,
        WikiPage,
    )

    for model in (Mission, Run, AuditEvent, ToolCall, Artifact, Source, WikiPage):
        schema = model.model_json_schema()
        assert isinstance(schema, dict), f"{model.__name__} did not return a dict"
        assert "properties" in schema, f"{model.__name__} schema missing 'properties'"


def test_secret_patterns() -> None:
    """SECRET_PATTERNS must catch URL querystring, JSON key-value, and Bearer notation."""
    import re
    from atlas_core.schemas.core import SECRET_PATTERNS

    assert isinstance(SECRET_PATTERNS, tuple)
    assert len(SECRET_PATTERNS) >= 3
    for pattern in SECRET_PATTERNS:
        assert hasattr(pattern, "match"), f"Pattern {pattern!r} has no .match method"

    def matches_any(text: str) -> bool:
        return any(p.search(text) for p in SECRET_PATTERNS)

    # URL querystring style
    assert matches_any("token=abc123")
    assert matches_any("api_key=xyz")
    assert matches_any("password=p@ss")
    # JSON key-value style (the previously uncovered case)
    assert matches_any('{"token": "sk-abc123"}')
    assert matches_any('{"api_key": "xyz"}')
    assert matches_any('{"password": "p@ss"}')
    # Bearer token
    assert matches_any("Bearer eyJhbGci.abc.def")
    # Non-secret strings must not match
    assert not matches_any("user=alice")
    assert not matches_any('{"username": "alice"}')


def test_frozen_model() -> None:
    """SCHEMA-01: assigning to a frozen Mission field must raise an exception."""
    from atlas_core.schemas.core import Mission

    m = Mission(title="t")
    with pytest.raises(Exception):
        m.title = "mutated"  # type: ignore[misc]


# --- Goal model slice (loop-engineering: Goal / Task / Observation) ---


def test_goal_model_importable_and_json_safe() -> None:
    """Goal/Task/Observation import, instantiate, and serialize JSON-safe."""
    from atlas_core.schemas.core import Goal, Observation, Task

    g = Goal(title="Ship the loop", description="full slice", focus_id="f1")
    t = Task(goal_id=g.id, title="write the migration")
    o = Observation(goal_id=g.id, run_id="r1", body="tests green", source="run:r1")

    for model in (g, t, o):
        dumped = model.model_dump()
        json.dumps(dumped)  # must not raise
        assert isinstance(dumped["created_at"], str)


def test_goal_defaults_and_nesting() -> None:
    """Goal defaults: open status, nullable parent/focus; sub-goal via parent_goal_id."""
    from atlas_core.schemas.core import Goal

    root = Goal(title="root")
    assert root.status == "open"
    assert root.parent_goal_id is None and root.focus_id is None
    child = Goal(title="sub", parent_goal_id=root.id)
    assert child.parent_goal_id == root.id


def test_goal_model_status_enums() -> None:
    """Status literals are enforced by Pydantic."""
    from pydantic import ValidationError

    from atlas_core.schemas.core import Goal, Task

    with pytest.raises(ValidationError):
        Goal(title="x", status="bogus")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        Task(goal_id="g", title="x", status="bogus")  # type: ignore[arg-type]


def test_goal_model_json_schema() -> None:
    """model_json_schema() returns a dict with 'properties' for each new model."""
    from atlas_core.schemas.core import Goal, Observation, Task

    for model in (Goal, Task, Observation):
        schema = model.model_json_schema()
        assert isinstance(schema, dict) and "properties" in schema
