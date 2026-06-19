from __future__ import annotations

import pytest

from atlas_runtime import console_service


class TextBlock:
    def __init__(self, text: str) -> None:
        self.text = text


class ToolUseBlock:
    def __init__(self, name: str, id: str, input: dict) -> None:
        self.name = name
        self.id = id
        self.input = input


class ToolResultBlock:
    def __init__(self, tool_use_id: str, content) -> None:  # noqa: ANN001
        self.tool_use_id = tool_use_id
        self.content = content


class AssistantMessage:
    def __init__(self, content: list) -> None:
        self.content = content


class UserMessage:
    def __init__(self, content) -> None:  # noqa: ANN001
        self.content = content


class ResultMessage:
    def __init__(self, is_error: bool = False) -> None:
        self.is_error = is_error
        self.subtype = "error" if is_error else "success"
        self.num_turns = 1
        self.total_cost_usd = 0.0
        self.usage = {"input_tokens": 1}


def _make_query(messages: list):
    async def _q(*, prompt, options):  # noqa: ANN001
        assert prompt
        for msg in messages:
            yield msg

    return _q


def test_native_console_chat_returns_receipt(tmp_path):
    result = console_service.run_chat(
        prompt="summarize this project",
        agent="native",
        cwd=str(tmp_path),
    )

    assert result["status"] == "succeeded"
    assert result["agent"] == "native"
    assert result["cwd"] == str(tmp_path.resolve())
    assert "Native console mode" in result["text"]


def test_console_chat_rejects_invalid_cwd(tmp_path):
    with pytest.raises(ValueError, match="folder does not exist"):
        console_service.run_chat(
            prompt="x",
            agent="native",
            cwd=str(tmp_path / "missing"),
        )


def test_claude_code_console_maps_sdk_stream(tmp_path):
    messages = [
        AssistantMessage(
            [
                TextBlock("hello "),
                ToolUseBlock("Read", "tool-1", {"file_path": "README.md"}),
                TextBlock("ATLAS"),
            ]
        ),
        ResultMessage(),
    ]

    result = console_service.run_chat(
        prompt="inspect",
        agent="claude_code",
        cwd=str(tmp_path),
        query_fn=_make_query(messages),
    )

    assert result["status"] == "succeeded"
    assert result["text"] == "hello ATLAS"
    assert any(e["type"] == "tool_call" and e["tool_name"] == "Read" for e in result["events"])


def test_claude_code_console_captures_tool_results(tmp_path):
    # Tool results arrive in a UserMessage that follows the assistant's tool use.
    messages = [
        AssistantMessage([ToolUseBlock("Read", "tool-1", {"file_path": "README.md"})]),
        UserMessage([ToolResultBlock("tool-1", "file contents here")]),
        AssistantMessage([TextBlock("done")]),
        ResultMessage(),
    ]

    result = console_service.run_chat(
        prompt="inspect",
        agent="claude_code",
        cwd=str(tmp_path),
        query_fn=_make_query(messages),
    )

    results = [e for e in result["events"] if e["type"] == "tool_result"]
    assert len(results) == 1
    assert results[0]["tool_call_id"] == "tool-1"
    assert results[0]["content"] == "file contents here"
