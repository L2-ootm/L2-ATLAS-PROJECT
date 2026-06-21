"""Tests for atlas_core.schemas.discord (Phase C) and the discord_action audit type."""

import datetime
import json

import pytest
from pydantic import ValidationError


def test_discord_approval_importable_from_package() -> None:
    from atlas_core.schemas import (  # noqa: F401
        DiscordAction,
        DiscordApproval,
        DiscordApprovalStatus,
    )


def test_discord_approval_defaults() -> None:
    from atlas_core.schemas.discord import DiscordApproval

    a = DiscordApproval(action="create_channel", guild_id="g1")
    assert a.id != ""
    assert a.status == "pending"
    assert a.params == "{}"
    assert a.target_id is None
    assert a.run_id == "operator"
    assert a.decided_at is None
    assert isinstance(a.requested_at, datetime.datetime)


def test_discord_approval_is_frozen() -> None:
    from atlas_core.schemas.discord import DiscordApproval

    a = DiscordApproval(action="delete_role", guild_id="g1", target_id="r9")
    with pytest.raises(ValidationError):
        a.status = "executed"  # type: ignore[misc]


def test_discord_approval_rejects_unknown_action() -> None:
    from atlas_core.schemas.discord import DiscordApproval

    with pytest.raises(ValidationError):
        DiscordApproval(action="nuke_guild", guild_id="g1")  # type: ignore[arg-type]


def test_discord_approval_rejects_unknown_status() -> None:
    from atlas_core.schemas.discord import DiscordApproval

    with pytest.raises(ValidationError):
        DiscordApproval(action="create_channel", guild_id="g1", status="approved")  # type: ignore[arg-type]


def test_discord_approval_serializes_json_safe() -> None:
    from atlas_core.schemas.discord import DiscordApproval

    a = DiscordApproval(
        action="edit_channel",
        guild_id="g1",
        target_id="c1",
        params=json.dumps({"name": "general"}),
        decided_at=datetime.datetime.now(datetime.timezone.utc),
    )
    dumped = a.model_dump()
    # round-trips through json (datetimes are ISO strings, params is a str)
    json.dumps(dumped)
    assert isinstance(dumped["requested_at"], str)
    assert isinstance(dumped["decided_at"], str)
    assert isinstance(dumped["params"], str)


def test_audit_event_accepts_discord_action() -> None:
    from atlas_core.schemas.core import AuditEvent

    ae = AuditEvent(run_id="operator", event_type="discord_action")
    assert ae.event_type == "discord_action"
