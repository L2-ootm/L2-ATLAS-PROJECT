"""Tests for atlas_runtime.rtk — tool-output compression (Phase 3 Track A, F6).

Covers TerminalAdapter/ReadFileAdapter compression directly (exit codes,
error lines, file paths preserved; small outputs passed through unchanged),
the registry (register/get, workspace op="read" resolution), and the
`compress_tool_output` top-level helper's no-op-on-unknown-tool and
never-raises guarantees.
"""
from __future__ import annotations

import json

from atlas_runtime import rtk


# ---------------------------------------------------------------------------
# TerminalAdapter
# ---------------------------------------------------------------------------


def test_terminal_adapter_passes_through_small_output():
    adapter = rtk.TerminalAdapter()
    raw = "hello world"
    result = adapter.compress(raw, {})
    assert result.compressed == raw
    assert result.display_hint == "full"
    assert result.original_size == result.compressed_size == len(raw)


def test_terminal_adapter_compresses_large_plain_text_and_keeps_tail():
    adapter = rtk.TerminalAdapter()
    lines = [f"ok line {i}" for i in range(500)]
    raw = "\n".join(lines)
    assert len(raw) > adapter.PASSTHROUGH_CHARS
    result = adapter.compress(raw, {"exit_code": 0})
    assert result.display_hint == "reduced"
    assert result.compressed_size < result.original_size
    assert "exit_code=0" in result.compressed
    # Tail lines survive.
    assert "ok line 499" in result.compressed
    assert "ok line 498" in result.compressed
    # Far-earlier lines do not.
    assert "ok line 0" not in result.compressed


def test_terminal_adapter_keeps_error_lines_and_exit_code_from_json_payload():
    adapter = rtk.TerminalAdapter()
    output_lines = ["step %d ok" % i for i in range(300)]
    output_lines.insert(150, "Traceback (most recent call last):")
    output_lines.insert(151, "RuntimeError: something broke")
    raw = json.dumps(
        {"output": "\n".join(output_lines), "exit_code": 1, "error": "process exited 1"}
    )
    assert len(raw) > adapter.PASSTHROUGH_CHARS
    result = adapter.compress(raw, {})
    assert result.display_hint == "reduced"
    assert result.metadata["exit_code"] == 1
    assert "exit_code=1" in result.compressed
    assert "error: process exited 1" in result.compressed
    assert "RuntimeError: something broke" in result.compressed


def test_terminal_adapter_handles_empty_output():
    adapter = rtk.TerminalAdapter()
    result = adapter.compress("", {})
    assert result.compressed == ""
    assert result.original_size == 0
    assert result.display_hint == "full"


def test_terminal_adapter_never_raises_on_malformed_json():
    adapter = rtk.TerminalAdapter()
    raw = "{not valid json" * 200  # large enough to skip passthrough
    result = adapter.compress(raw, {})
    assert isinstance(result.compressed, str)
    assert result.display_hint == "reduced"


# ---------------------------------------------------------------------------
# ReadFileAdapter
# ---------------------------------------------------------------------------


def test_read_file_adapter_passes_through_small_output():
    adapter = rtk.ReadFileAdapter()
    raw = "1|import os\n2|print('hi')\n"
    result = adapter.compress(raw, {"path": "a.py"})
    assert result.compressed == raw
    assert result.display_hint == "full"


def test_read_file_adapter_compresses_large_plain_text_and_preserves_path():
    adapter = rtk.ReadFileAdapter()
    body = "\n".join(f"{i}|line {i}" for i in range(1, 400))
    result = adapter.compress(body, {"path": "src/big.py", "offset": 1})
    assert result.display_hint == "summary"
    assert result.compressed_size < result.original_size
    assert "src/big.py" in result.compressed
    assert result.metadata["path"] == "src/big.py"
    assert result.metadata["offset"] == 1
    # Reversible: the hash is recoverable from the same content again.
    assert result.original_hash == rtk._hash(body)


def test_read_file_adapter_prefers_json_payload_fields_over_tool_args():
    adapter = rtk.ReadFileAdapter()
    content = "\n".join(f"{i}|x" for i in range(1, 400))
    raw = json.dumps({"content": content, "path": "resolved/path.py", "total_lines": 5000})
    result = adapter.compress(raw, {"path": "requested/path.py", "offset": 1})
    assert result.display_hint == "summary"
    # The JSON payload's own path (post-resolution) wins over the raw args.
    assert "resolved/path.py" in result.compressed
    assert "of 5000" in result.compressed


def test_read_file_adapter_never_raises_on_malformed_json():
    adapter = rtk.ReadFileAdapter()
    raw = "{not valid json" * 200
    result = adapter.compress(raw, {"path": "x.py"})
    assert isinstance(result.compressed, str)
    assert result.display_hint == "summary"


# ---------------------------------------------------------------------------
# Registry + compress_tool_output
# ---------------------------------------------------------------------------


def test_registry_has_default_adapters():
    assert isinstance(rtk.get_adapter("terminal"), rtk.TerminalAdapter)
    assert isinstance(rtk.get_adapter("read_file"), rtk.ReadFileAdapter)
    assert rtk.get_adapter("no_such_tool") is None


def test_register_adapter_overrides():
    class _Stub:
        def compress(self, raw_output, tool_args):
            return rtk.CompressedOutput(
                tool_name="stub_tool", compressed="STUB", original_hash="h",
                original_size=len(raw_output), compressed_size=4, metadata={},
                display_hint="summary",
            )

    rtk.register_adapter("stub_tool", _Stub())
    try:
        assert rtk.compress_tool_output("stub_tool", {}, "anything") == "STUB"
    finally:
        del rtk._REGISTRY["stub_tool"]  # test isolation — don't leak into other tests


def test_compress_tool_output_noop_for_unknown_tool():
    raw = "x" * 5000
    assert rtk.compress_tool_output("web_fetch", {"url": "https://example.com"}, raw) == raw


def test_compress_tool_output_workspace_read_op_uses_read_file_adapter():
    body = "\n".join(f"{i}|x" for i in range(1, 400))
    compressed = rtk.compress_tool_output("workspace", {"op": "read", "path": "a.py"}, body)
    assert compressed != body
    assert "a.py" in compressed


def test_compress_tool_output_workspace_non_read_op_is_noop():
    raw = "y" * 5000
    compressed = rtk.compress_tool_output("workspace", {"op": "list", "path": "."}, raw)
    assert compressed == raw


def test_compress_tool_output_never_raises_on_adapter_exception():
    class _Boom:
        def compress(self, raw_output, tool_args):
            raise RuntimeError("boom")

    rtk.register_adapter("boom_tool", _Boom())
    try:
        raw = "unchanged"
        assert rtk.compress_tool_output("boom_tool", {}, raw) == raw
    finally:
        del rtk._REGISTRY["boom_tool"]
