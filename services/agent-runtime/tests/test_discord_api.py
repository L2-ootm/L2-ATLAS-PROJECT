"""Tests for the discord_api write client (Phase C, C-WP2).

urllib.request.urlopen is monkeypatched to capture the method, URL, and JSON body
of each write wrapper so nothing is networked. Error mapping (HTTP / unreachable /
bad JSON -> DiscordSidecarError) is also covered.
"""
from __future__ import annotations

import io
import json
import urllib.error

import pytest

from atlas_runtime import discord_api


class _FakeResp:
    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture()
def captured(monkeypatch):
    """Capture the outgoing Request; return a canned success payload."""
    seen = {}

    def _fake_urlopen(req, timeout=None):
        seen["method"] = req.get_method()
        seen["url"] = req.full_url
        seen["body"] = json.loads(req.data.decode("utf-8")) if req.data else None
        return _FakeResp({"id": "999", "name": "ok", "success": True})

    monkeypatch.setattr(discord_api.urllib.request, "urlopen", _fake_urlopen)
    return seen


def test_create_channel_posts_body(captured):
    out = discord_api.create_channel(
        "g1", name="general", type="text", category_id="cat1", topic="hi", reason="ATLAS test"
    )
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/guilds/g1/channels")
    assert captured["body"] == {
        "name": "general",
        "type": "text",
        "category_id": "cat1",
        "topic": "hi",
        "reason": "ATLAS test",
    }
    assert out["id"] == "999"


def test_edit_channel_patches_only_supplied_fields(captured):
    discord_api.edit_channel("g1", "c1", name="renamed", reason="r")
    assert captured["method"] == "PATCH"
    assert captured["url"].endswith("/guilds/g1/channels/c1")
    assert captured["body"] == {"reason": "r", "name": "renamed"}
    assert "topic" not in captured["body"]


def test_delete_channel(captured):
    discord_api.delete_channel("g1", "c1", reason="cleanup")
    assert captured["method"] == "DELETE"
    assert captured["url"].endswith("/guilds/g1/channels/c1")
    assert captured["body"] == {"reason": "cleanup"}


def test_create_role_posts_permissions(captured):
    discord_api.create_role(
        "g1", name="mod", color_hex="#ff0000", hoist=True, permissions={"kick_members": True}, reason="r"
    )
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/guilds/g1/roles")
    assert captured["body"]["permissions"] == {"kick_members": True}
    assert captured["body"]["hoist"] is True


def test_set_permissions_posts_allow_deny(captured):
    discord_api.set_permissions(
        "g1", "c1", role_id="r1", allow=["view_channel"], deny=["send_messages"], reason="r"
    )
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/guilds/g1/channels/c1/permissions")
    assert captured["body"] == {
        "role_id": "r1",
        "allow": ["view_channel"],
        "deny": ["send_messages"],
        "reason": "r",
    }


def test_send_message_posts_embed(captured):
    discord_api.send_message("c1", embed={"title": "hello"}, reason="r")
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/channels/c1/messages")
    assert captured["body"] == {"embed": {"title": "hello"}, "reason": "r"}


def test_http_error_surfaces_detail(monkeypatch):
    def _raise(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url, 403, "Forbidden", {}, io.BytesIO(b'{"error": "Forbidden"}')
        )

    monkeypatch.setattr(discord_api.urllib.request, "urlopen", _raise)
    with pytest.raises(discord_api.DiscordSidecarError) as exc:
        discord_api.delete_channel("g1", "c1")
    assert "403" in str(exc.value) and "Forbidden" in str(exc.value)


def test_unreachable_maps_to_sidecar_error(monkeypatch):
    def _raise(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(discord_api.urllib.request, "urlopen", _raise)
    with pytest.raises(discord_api.DiscordSidecarError) as exc:
        discord_api.create_channel("g1", name="x")
    assert "unreachable" in str(exc.value)
