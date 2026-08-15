"""Continuity is a property of a session, not of the runtime that served it.

`claude_code` and `codex` were written after `native` and never got the
conversation replay that lived inside it, so the same operator in the same
cockpit session got a coherent thread or a cold start depending on which
runtime the run happened to use. These tests hold every runtime to the same
contract.
"""
from __future__ import annotations

import datetime
import sqlite3
import threading
import uuid

import pytest

from atlas_runtime import session_continuity
from atlas_runtime.agents.claude_code import ClaudeCodeAgent
from atlas_runtime.agents.codex import CodexAgent
from atlas_runtime.agents.native import NativeAtlasAgent


# --- fixtures ---------------------------------------------------------------


def _mission(db: sqlite3.Connection, intent: str) -> str:
    mid = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT INTO missions(id, title, intent, status, project, created_at, updated_at) "
        "VALUES (?, ?, ?, 'pending', '', ?, ?)",
        (mid, "t", intent, now, now),
    )
    db.commit()
    return mid


def _run(db: sqlite3.Connection, mission_id: str, session_id: str) -> str:
    rid = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT INTO runs(id, mission_id, session_id, status, started_at, finished_at, summary) "
        "VALUES (?, ?, ?, 'running', ?, NULL, '')",
        (rid, mission_id, session_id, now),
    )
    db.commit()
    return rid


# Both runtimes map by class name / event type, so these fakes must carry the
# SDK's names exactly.
class TextBlock:
    def __init__(self, text: str) -> None:
        self.text = text


class AssistantMessage:
    def __init__(self, content: list) -> None:
        self.content = content


class ResultMessage:
    def __init__(self, is_error: bool = False) -> None:
        self.is_error = is_error
        self.subtype = "success"


def _claude_runtime(answer: str, seen: list[str]):
    async def _query(*, prompt, options):  # noqa: ANN001
        seen.append(prompt)
        yield AssistantMessage([TextBlock(answer)])
        yield ResultMessage()

    return ClaudeCodeAgent(query_fn=_query)


def _codex_runtime(answer: str, seen: list[str]):
    def _runner(prompt: str, cancel_token):  # noqa: ANN001
        seen.append(prompt)
        yield {
            "type": "item.completed",
            "item": {"id": "item_0", "item_type": "agent_message", "text": answer},
        }
        yield {"type": "turn.completed"}

    return CodexAgent(runner_fn=_runner)


class _FakeHarness:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.histories: list = []

    def run_conversation(
        self,
        user_message: str,
        system_message=None,  # noqa: ANN001
        task_id=None,  # noqa: ANN001
        conversation_history=None,  # noqa: ANN001
        persist_user_message=None,  # noqa: ANN001
    ):
        self.histories.append(conversation_history)
        return {
            "final_response": self.answer,
            "api_calls": 1,
            "completed": True,
            "failed": False,
            "error": None,
        }


# --- the contract, per runtime ---------------------------------------------


@pytest.mark.parametrize("runtime", ["claude_code", "codex"])
def test_a_second_turn_can_see_the_first(
    db: sqlite3.Connection, lock: threading.Lock, surface_session: str, runtime: str
) -> None:
    seen: list[str] = []
    build = _claude_runtime if runtime == "claude_code" else _codex_runtime

    first_mission = _mission(db, "what does the installer verify?")
    first_run = _run(db, first_mission, surface_session)
    build("it verifies the payload manifest", seen).execute(
        db, lock,
        mission_id=first_mission,
        run_id=first_run,
        prompt="# ATLAS Operator Context\n\n---\n\nwhat does the installer verify?",
    )

    second_mission = _mission(db, "and if that check fails?")
    second_run = _run(db, second_mission, surface_session)
    build("it aborts the install", seen).execute(
        db, lock,
        mission_id=second_mission,
        run_id=second_run,
        prompt="and if that check fails?",
    )

    first_prompt, second_prompt = seen
    assert "Conversation so far" not in first_prompt
    assert "what does the installer verify?" in second_prompt
    assert "it verifies the payload manifest" in second_prompt
    # The recalled thread is labelled, so the model can tell it apart from the
    # message it is being asked to answer.
    assert "Conversation so far" in second_prompt
    assert second_prompt.endswith("and if that check fails?")


@pytest.mark.parametrize("runtime", ["claude_code", "codex"])
def test_the_operator_ask_is_recorded_without_the_compiled_brief(
    db: sqlite3.Connection, lock: threading.Lock, surface_session: str, runtime: str
) -> None:
    build = _claude_runtime if runtime == "claude_code" else _codex_runtime
    mission = _mission(db, "remember COBALT-MERIDIAN-731")
    run_id = _run(db, mission, surface_session)

    build("noted", []).execute(
        db, lock,
        mission_id=mission,
        run_id=run_id,
        prompt="# ATLAS Operator Context\n\n## Goals\n- stale brief\n\n---\n\n"
               "remember COBALT-MERIDIAN-731",
    )

    rows = db.execute(
        "SELECT role, content FROM session_messages WHERE surface_session_id=? "
        "AND run_id=? ORDER BY seq",
        (surface_session, run_id),
    ).fetchall()
    assert [row[0] for row in rows] == ["user", "assistant"]
    assert rows[0][1] == "remember COBALT-MERIDIAN-731"
    assert rows[1][1] == "noted"


def test_every_runtime_persists_the_thread_the_others_can_read(
    db: sqlite3.Connection, lock: threading.Lock, surface_session: str
) -> None:
    """Switching runtimes mid-session must not restart the conversation: the
    record is `session_messages`, not anything a runtime keeps to itself."""
    seen: list[str] = []
    claude_mission = _mission(db, "start the audit")
    _claude_runtime("audit started", seen).execute(
        db, lock,
        mission_id=claude_mission,
        run_id=_run(db, claude_mission, surface_session),
        prompt="start the audit",
    )

    codex_mission = _mission(db, "what did you find?")
    _codex_runtime("three findings", seen).execute(
        db, lock,
        mission_id=codex_mission,
        run_id=_run(db, codex_mission, surface_session),
        prompt="what did you find?",
    )

    native_mission = _mission(db, "fix the first one")
    harness = _FakeHarness("fixed")
    NativeAtlasAgent(agent_factory=lambda session_id: harness).execute(
        db, lock,
        mission_id=native_mission,
        run_id=_run(db, native_mission, surface_session),
        prompt="fix the first one",
    )

    replayed = [item["content"] for item in (harness.histories[-1] or [])]
    joined = "\n".join(replayed)
    assert "start the audit" in joined
    assert "audit started" in joined
    assert "what did you find?" in joined
    assert "three findings" in joined
    assert "fix the first one" not in joined


# --- rendering --------------------------------------------------------------


def test_a_session_less_run_has_no_history_and_no_crash(db: sqlite3.Connection) -> None:
    assert session_continuity.load(db, None) == []
    assert session_continuity.transcript([]) == ""
    assert session_continuity.with_history("just the prompt", "") == "just the prompt"
