"""Machine-readable shared surface-session lifecycle commands.

Handlers are thin adapters over ``surface_session_service``,
``workspace_service``, and ``permission_broker``. The Rust gateway dispatches
these commands; lifecycle and authority never live in Typer.
"""

from __future__ import annotations

import json
import os
import pathlib
import sqlite3
import threading
import uuid
from typing import Optional

import typer
from atlas_core.schemas.agent_contract import (
    ModelIdentity,
    SurfaceIdentity,
    WorkspaceIdentity,
)
from pydantic import ValidationError

from atlas_runtime import (
    agent_contract_service,
    audit_service,
    config_service,
    permission_broker,
    run_service,
    surface_events,
    surface_session_service,
    tool_catalog,
    workspace_service,
)

surface_app = typer.Typer(
    name="surface",
    help="Shared surface-session lifecycle and ownership contracts.",
)

_LOCK = threading.Lock()


def _get_connection() -> sqlite3.Connection:
    from atlas_runtime.cli import main

    return main._get_connection()


def _get_lock() -> threading.Lock:
    return _LOCK


def _echo(value: object) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    typer.echo(json.dumps(value, separators=(",", ":"), ensure_ascii=False))


def _echo_session(session, *, include_owner_token: bool = False) -> None:
    payload = session.model_dump(mode="json")
    if not include_owner_token:
        payload["owner_token"] = ""
    _echo(payload)


def _fail(
    code: str,
    message: str,
    remediation: str,
    *,
    field: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "error": {
            "code": code,
            "message": message,
            "remediation": remediation,
        }
    }
    if field is not None:
        payload["error"]["field"] = field  # type: ignore[index]
    _echo(payload)
    raise typer.Exit(1)


def _session_or_fail(conn: sqlite3.Connection, session_id: str):
    session = surface_session_service.get_session(conn, session_id)
    if session is None:
        _fail(
            "surface_not_found",
            f"no surface session {session_id!r}",
            "create a new surface session or reload the current session id",
            field="session_id",
        )
    return session


def _owned_session_or_fail(
    conn: sqlite3.Connection,
    session_id: str,
    owner_token: str,
):
    session = _session_or_fail(conn, session_id)
    if not owner_token or session.owner_token != owner_token:
        _fail(
            "surface_owner_mismatch",
            "surface owner token is missing or stale",
            "use the token returned by create/resume or create a new session",
            field="owner_token",
        )
    return session


@surface_app.command("create")
def create(
    surface_kind: str = typer.Option(..., "--surface-kind"),
    surface_id: Optional[str] = typer.Option(None, "--surface-id"),
    global_: bool = typer.Option(False, "--global"),
    project_id: Optional[str] = typer.Option(None, "--project"),
    agent: Optional[str] = typer.Option(None, "--agent"),
    provider: Optional[str] = typer.Option(None, "--provider"),
    model: Optional[str] = typer.Option(None, "--model"),
    permission_mode: Optional[str] = typer.Option(None, "--permission-mode"),
    approval_channel: bool = typer.Option(
        True,
        "--approval-channel/--no-approval-channel",
    ),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Create and activate one global or registered-project surface session."""
    if global_ == bool(project_id):
        _fail(
            "workspace_invalid",
            "choose exactly one of --global or --project",
            "pass --global or --project <registered-id>",
            field="workspace",
        )
    conn = _get_connection()
    lock = _get_lock()
    kind = "global" if global_ else "project"
    try:
        root = workspace_service.resolve_workspace(
            conn,
            kind=kind,
            project_id=project_id,
            use_global=global_,
        )
    except workspace_service.WorkspaceError as exc:
        _fail(
            f"workspace_{exc.reason}",
            str(exc),
            "register the project and verify its root before creating a session",
            field="project_id",
        )
    if kind == "project" and not pathlib.Path(root).is_dir():
        _fail(
            "workspace_root_invalid",
            f"registered project root is unavailable: {root}",
            "restore the directory or update the registered project root",
            field="project_id",
        )

    config = config_service.load_config()
    resolved = config_service.resolve_provider(config)
    try:
        session = surface_session_service.create_session(
            conn,
            lock,
            surface=SurfaceIdentity(
                kind=surface_kind,
                session_id=surface_id or str(uuid.uuid4()),
            ),
            workspace=WorkspaceIdentity(
                kind=kind,
                root=root,
                project_id=project_id,
            ),
            agent=agent or config.runtime.default_agent,
            model=ModelIdentity(
                provider=provider or resolved["provider"],
                model_id=model or resolved["model"],
            ),
            permission_mode=permission_mode or config.permission.mode,
            prompt_version=agent_contract_service.PROMPT_VERSION,
            tool_catalog_version=tool_catalog.build_shipped_catalog().catalog_version,
            context_policy_version=agent_contract_service.CONTEXT_POLICY_VERSION,
            owner_token=str(uuid.uuid4()),
            owner_pid=os.getpid(),
        )
        surface_session_service.transition_session(
            conn,
            lock,
            session.id,
            "active",
        )
        if approval_channel:
            permission_broker.register_channel(
                conn,
                lock,
                surface_session_id=session.id,
                surface_kind=surface_kind,
            )
        session = surface_session_service.get_session(conn, session.id)
    except (ValidationError, ValueError) as exc:
        _fail(
            "surface_invalid",
            str(exc),
            "correct the surface, model, permission, or workspace fields and retry",
        )
    if json_out:
        _echo_session(session, include_owner_token=True)
        return
    typer.echo(session.id)


@surface_app.command("get")
def get(
    session_id: str,
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    session = _session_or_fail(_get_connection(), session_id)
    if json_out:
        _echo_session(session)
        return
    typer.echo(f"{session.id}\t{session.state}\t{session.surface.kind}")


@surface_app.command("list")
def list_sessions(
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    sessions = surface_session_service.list_sessions(_get_connection())
    if json_out:
        _echo({"sessions": [item.model_dump(mode="json") for item in sessions]})
        return
    for session in sessions:
        typer.echo(f"{session.id}\t{session.state}\t{session.surface.kind}")


@surface_app.command("events")
def events(
    session_id: str,
    after_seq: int = typer.Option(-1, "--after-seq", min=-1),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Replay normalized events strictly after one per-session sequence."""
    conn = _get_connection()
    _session_or_fail(conn, session_id)
    audit_events = audit_service.get_events_for_session(conn, session_id)
    normalized = surface_events.normalize_surface_events(
        audit_events,
        session_id=session_id,
    )
    replay = surface_events.replay_since(normalized, after_seq)
    payload = {
        "session_id": session_id,
        "after_seq": after_seq,
        "events": [event.model_dump(mode="json") for event in replay],
    }
    if json_out:
        _echo(payload)
        return
    for event in replay:
        typer.echo(f"{event.seq}\t{event.kind}\t{event.run_id or ''}")


@surface_app.command("heartbeat")
def heartbeat(
    session_id: str,
    owner_token: str = typer.Option(..., "--owner-token"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    conn = _get_connection()
    lock = _get_lock()
    _owned_session_or_fail(conn, session_id, owner_token)
    surface_session_service.heartbeat(conn, lock, session_id)
    session = _session_or_fail(conn, session_id)
    if json_out:
        _echo_session(session)
        return
    typer.echo(f"{session.id}\t{session.state}")


@surface_app.command("suspend")
def suspend(
    session_id: str,
    owner_token: str = typer.Option(..., "--owner-token"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    conn = _get_connection()
    lock = _get_lock()
    session = _owned_session_or_fail(conn, session_id, owner_token)
    try:
        surface_session_service.transition_session(conn, lock, session_id, "suspended")
    except ValueError as exc:
        _fail(
            "surface_transition_conflict",
            str(exc),
            "reload the session and retry only from an active state",
        )
    permission_broker.revoke_channel(
        conn,
        lock,
        surface_session_id=session_id,
    )
    session = _session_or_fail(conn, session_id)
    if json_out:
        _echo_session(session)
        return
    typer.echo(f"{session.id}\t{session.state}")


@surface_app.command("resume")
def resume(
    session_id: str,
    owner_token: str = typer.Option(..., "--owner-token"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    conn = _get_connection()
    prior = _owned_session_or_fail(conn, session_id, owner_token)
    next_owner_token = str(uuid.uuid4())
    try:
        session = surface_session_service.resume_session(
            conn,
            _get_lock(),
            session_id,
            owner_token=next_owner_token,
            owner_pid=os.getpid(),
        )
        permission_broker.register_channel(
            conn,
            _get_lock(),
            surface_session_id=session_id,
            surface_kind=prior.surface.kind,
        )
    except (
        ValueError,
        LookupError,
        agent_contract_service.ContractCompatibilityError,
    ) as exc:
        _fail(
            "surface_resume_conflict",
            str(exc),
            "reload the session contract or create a new session",
        )
    if json_out:
        _echo_session(session, include_owner_token=True)
        return
    typer.echo(f"{session.id}\t{session.state}")


def _finish(
    session_id: str,
    *,
    owner_token: str,
    cancelled: bool,
    json_out: bool,
) -> None:
    conn = _get_connection()
    lock = _get_lock()
    session = _owned_session_or_fail(conn, session_id, owner_token)
    try:
        if session.state == "starting":
            surface_session_service.transition_session(conn, lock, session_id, "failed")
        elif session.state == "active" and not cancelled:
            surface_session_service.transition_session(
                conn, lock, session_id, "completed"
            )
        elif session.state in {"active", "suspended"}:
            surface_session_service.transition_session(
                conn, lock, session_id, "cancelling"
            )
            if session.run_id and session.mission_id:
                try:
                    run_service.cancel_run(
                        conn,
                        lock,
                        run_id=session.run_id,
                        mission_id=session.mission_id,
                    )
                except ValueError:
                    pass
            surface_session_service.transition_session(
                conn, lock, session_id, "completed"
            )
        elif session.state == "cancelling":
            surface_session_service.transition_session(
                conn, lock, session_id, "completed"
            )
        elif session.state not in {"completed", "failed", "reclaimed"}:
            raise ValueError(f"cannot close surface session from {session.state}")
    except ValueError as exc:
        _fail(
            "surface_transition_conflict",
            str(exc),
            "reload the session and retry from a live lifecycle state",
        )
    permission_broker.revoke_channel(
        conn,
        lock,
        surface_session_id=session_id,
    )
    terminal = _session_or_fail(conn, session_id)
    if json_out:
        _echo_session(terminal)
        return
    typer.echo(f"{terminal.id}\t{terminal.state}")


@surface_app.command("cancel")
def cancel(
    session_id: str,
    owner_token: str = typer.Option(..., "--owner-token"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    _finish(
        session_id,
        owner_token=owner_token,
        cancelled=True,
        json_out=json_out,
    )


@surface_app.command("close")
def close(
    session_id: str,
    owner_token: str = typer.Option(..., "--owner-token"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    _finish(
        session_id,
        owner_token=owner_token,
        cancelled=False,
        json_out=json_out,
    )


__all__ = ["surface_app"]
