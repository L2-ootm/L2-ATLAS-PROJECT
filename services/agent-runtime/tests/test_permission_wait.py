"""Bounded blocking/heartbeat semantics for surface approval adapters."""

from __future__ import annotations

import threading

from atlas_core.schemas.control_plane import PermissionConfig
from atlas_core.schemas.tool import ToolManifest, ToolResult
from atlas_runtime import permission_broker, tool_service


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


def _pending(db, lock, monkeypatch, session_id: str):
    from atlas_runtime.tools import registry

    manifest = ToolManifest(name="writer", risk_level="write")

    def adapter(args, ctx):  # noqa: ANN001
        return ToolResult(ok=True, tool_name="writer", output="done")

    class _Registry:
        def resolve(self, name):  # noqa: ANN001
            return manifest, adapter

    monkeypatch.setattr(registry, "get_registry", lambda: _Registry())
    return tool_service.invoke(
        db,
        lock,
        tool_name="writer",
        args={"path": "note.md"},
        ctx={
            "permission_config": PermissionConfig(preset="manual"),
            "workspace_root": "/tmp/atlas",
        },
        surface_session_id=session_id,
        surface_kind="cli",
    )


def test_wait_heartbeats_in_bounded_intervals_then_timeout_denies(
    db,
    lock,
    monkeypatch,
    make_active_session,
) -> None:
    session_id = make_active_session()
    permission_broker.register_channel(
        db,
        lock,
        surface_session_id=session_id,
        surface_kind="cli",
    )
    approval = _pending(db, lock, monkeypatch, session_id)
    clock = _Clock()
    heartbeats: list[float] = []

    terminal = permission_broker.wait_for_terminal(
        db,
        lock,
        approval_id=approval.id,
        surface_session_id=session_id,
        timeout_seconds=2.5,
        heartbeat=lambda: heartbeats.append(clock.value),
        poll_interval=1.0,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        require_open_channel=True,
    )

    assert terminal.status == "rejected"
    assert terminal.decision == "reject"
    assert terminal.reason == "timeout"
    assert clock.sleeps == [1.0, 1.0, 0.5]
    assert heartbeats == [0.0, 1.0, 2.0, 2.5]


def test_wait_cancellation_denies_without_sleep(
    db,
    lock,
    monkeypatch,
    make_active_session,
) -> None:
    session_id = make_active_session()
    approval = _pending(db, lock, monkeypatch, session_id)
    cancelled = threading.Event()
    cancelled.set()
    clock = _Clock()

    terminal = permission_broker.wait_for_terminal(
        db,
        lock,
        approval_id=approval.id,
        surface_session_id=session_id,
        timeout_seconds=30,
        cancel_event=cancelled,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )

    assert terminal.status == "rejected"
    assert terminal.decision == "reject"
    assert terminal.reason == "cancelled"
    assert clock.sleeps == []


def test_wait_disconnected_required_channel_denies(
    db,
    lock,
    monkeypatch,
    make_active_session,
) -> None:
    session_id = make_active_session()
    approval = _pending(db, lock, monkeypatch, session_id)

    terminal = permission_broker.wait_for_terminal(
        db,
        lock,
        approval_id=approval.id,
        surface_session_id=session_id,
        timeout_seconds=30,
        require_open_channel=True,
    )

    assert terminal.status == "rejected"
    assert terminal.decision == "reject"
    assert terminal.reason == "channel_disconnected"


def test_wait_returns_concurrent_operator_outcome(
    db,
    lock,
    monkeypatch,
    make_active_session,
) -> None:
    session_id = make_active_session()
    approval = _pending(db, lock, monkeypatch, session_id)
    decided = False

    def heartbeat() -> None:
        nonlocal decided
        if decided:
            return
        decided = True
        permission_broker.claim(
            db,
            lock,
            approval_id=approval.id,
            surface_session_id=session_id,
            decision="approve",
            nonce=approval.nonce,
        )

    terminal = permission_broker.wait_for_terminal(
        db,
        lock,
        approval_id=approval.id,
        surface_session_id=session_id,
        timeout_seconds=30,
        heartbeat=heartbeat,
        poll_interval=0.01,
    )

    assert terminal.status == "executed"
    assert terminal.decision == "approve"
