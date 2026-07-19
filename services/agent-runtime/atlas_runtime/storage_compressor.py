"""RTK — ATLAS-owned tool-output compression (Phase 3 Track A, F6).

Compresses tool output at the point ATLAS stores/observes it — `tool_calls`
rows and `audit_events.data` — so what persists (and what a future context
read pulls back in) is a compact, information-dense summary instead of a raw
dump, while exit codes / error lines / file paths / content hashes survive so
the compression is honest about what it dropped.

Per F6.md section 6.4 (Integration Point 3), this is deliberately an
ATLAS-owned layer, NOT a Hermes plugin hook — it does not edit
`foundation/atlas-hermes/` at all. It reaches Hermes-executed tool output
(`terminal`, `read_file`) through the `tool_complete_callback` ATLAS already
registers in `agents/native.py` (D-001: observe via hook, never edit the
vendored harness), and reaches ATLAS's own explicit-invoke tools
(`workspace` read/read_file) through `tool_service.py`'s single chokepoint.

Scope note: this compresses what ATLAS PERSISTS and re-injects into its own
context assembly, not the live in-run message list Hermes feeds its model —
that stream is entirely internal to the vendored harness and out of reach
without editing it (out of scope here; Hermes's own ContextCompressor already
prunes that lazily). See F6.md section 11, open question 5.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class CompressedOutput:
    """Result of compressing one tool's raw output."""

    tool_name: str
    compressed: str
    original_hash: str
    original_size: int
    compressed_size: int
    metadata: dict[str, Any]
    display_hint: str  # "full" | "reduced" | "summary"


class ToolOutputAdapter(Protocol):
    """A tool-specific compression strategy."""

    def compress(self, raw_output: str, tool_args: dict[str, Any]) -> CompressedOutput: ...


def _hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()[:12]


def _parse_json_dict(text: str) -> dict[str, Any] | None:
    """Best-effort JSON-object parse — several Hermes tools (terminal,
    read_file, search_files) return a JSON string, not plain text. Returns
    None for plain text or malformed JSON, never raises."""
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


# ---------------------------------------------------------------------------
# TerminalAdapter
# ---------------------------------------------------------------------------

_ERROR_LINE_RE = re.compile(r"error|exception|traceback|fail", re.IGNORECASE)


class TerminalAdapter:
    """Terminal/shell output: keep the exit code, error-looking lines, and
    the tail; drop repetitive passing output (a clean 40K-char test run
    contributes nothing further once its exit code and last few lines are
    known). `foundation/atlas-hermes/tools/terminal_tool.py` returns a JSON
    string with `output`/`exit_code`/`error` keys — parsed when present;
    plain text (or an unparseable payload) falls back to line-based
    heuristics so this never raises on an unexpected shape."""

    tool_name = "terminal"
    TAIL_LINES = 20
    MAX_ERROR_LINES = 20
    # Below this size, compressing would not meaningfully shrink the
    # payload — pass the original through unchanged (display_hint="full").
    PASSTHROUGH_CHARS = 800

    def compress(self, raw_output: str, tool_args: dict[str, Any]) -> CompressedOutput:
        raw_output = raw_output or ""
        original_size = len(raw_output)

        exit_code: Any = tool_args.get("exit_code") if tool_args else None
        error_text = ""
        output_text = raw_output
        parsed = _parse_json_dict(raw_output)
        if parsed is not None and ("output" in parsed or "exit_code" in parsed):
            exit_code = parsed.get("exit_code", exit_code)
            output_text = parsed.get("output") or ""
            error_text = parsed.get("error") or ""

        if original_size <= self.PASSTHROUGH_CHARS:
            return CompressedOutput(
                tool_name=self.tool_name,
                compressed=raw_output,
                original_hash=_hash(raw_output),
                original_size=original_size,
                compressed_size=original_size,
                metadata={"exit_code": exit_code},
                display_hint="full",
            )

        lines = output_text.splitlines()
        error_lines = [ln for ln in lines if _ERROR_LINE_RE.search(ln)][: self.MAX_ERROR_LINES]
        tail = lines[-self.TAIL_LINES :]

        parts: list[str] = []
        if exit_code is not None:
            parts.append(f"exit_code={exit_code}")
        if error_text:
            parts.append(f"error: {error_text}")
        if error_lines:
            parts.append("error lines:\n" + "\n".join(error_lines))
        parts.append(f"last {len(tail)} of {len(lines)} lines:\n" + "\n".join(tail))
        compressed = "\n".join(parts)

        return CompressedOutput(
            tool_name=self.tool_name,
            compressed=compressed,
            original_hash=_hash(raw_output),
            original_size=original_size,
            compressed_size=len(compressed),
            metadata={
                "exit_code": exit_code,
                "line_count": len(lines),
                "error_line_count": len(error_lines),
            },
            display_hint="reduced",
        )


# ---------------------------------------------------------------------------
# ReadFileAdapter
# ---------------------------------------------------------------------------


class ReadFileAdapter:
    """File-read output: store path + line range + content hash, drop the
    body. Fully reversible — the file still exists on disk, so a caller that
    genuinely needs the content again just re-reads it; there is no
    information here that a `read_file(path, offset, limit)` cannot recover.
    `foundation/atlas-hermes/tools/file_tools.py` returns a JSON string with
    a `content` key (plus `path`/`total_lines`); ATLAS's own `workspace`
    adapter (`tools/adapters/workspace.py`, op="read") returns plain text —
    both are handled, JSON preferred when present."""

    tool_name = "read_file"
    PASSTHROUGH_CHARS = 300

    def compress(self, raw_output: str, tool_args: dict[str, Any]) -> CompressedOutput:
        raw_output = raw_output or ""
        original_size = len(raw_output)
        tool_args = tool_args or {}
        path = str(tool_args.get("path") or tool_args.get("file_path") or "")
        offset = tool_args.get("offset") or 1
        try:
            offset = int(offset)
        except (TypeError, ValueError):
            offset = 1

        content = raw_output
        total_lines: Any = None
        parsed = _parse_json_dict(raw_output)
        if parsed is not None and "content" in parsed:
            content = parsed.get("content") or ""
            total_lines = parsed.get("total_lines")
            path = str(parsed.get("path") or path)

        if original_size <= self.PASSTHROUGH_CHARS:
            return CompressedOutput(
                tool_name=self.tool_name,
                compressed=raw_output,
                original_hash=_hash(raw_output),
                original_size=original_size,
                compressed_size=original_size,
                metadata={"path": path, "offset": offset},
                display_hint="full",
            )

        line_count = content.count("\n") + (1 if content else 0)
        end_line = offset + max(line_count - 1, 0)
        content_hash = _hash(content)
        suffix = f" of {total_lines}" if total_lines else ""
        compressed = (
            f"[read_file] {path} lines {offset}-{end_line}{suffix} "
            f"({len(content):,} chars, hash:{content_hash})"
        )

        return CompressedOutput(
            tool_name=self.tool_name,
            compressed=compressed,
            original_hash=content_hash,
            original_size=original_size,
            compressed_size=len(compressed),
            metadata={
                "path": path,
                "offset": offset,
                "line_count": line_count,
                "total_lines": total_lines,
            },
            display_hint="summary",
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, ToolOutputAdapter] = {}


def register_adapter(tool_name: str, adapter: ToolOutputAdapter) -> None:
    """Bind an adapter to a tool name. Re-registering a name overwrites it
    (last write wins) — used by callers that want to override a default."""
    _REGISTRY[tool_name] = adapter


def get_adapter(tool_name: str) -> ToolOutputAdapter | None:
    return _REGISTRY.get(tool_name)


register_adapter("terminal", TerminalAdapter())
register_adapter("read_file", ReadFileAdapter())


def _resolve_adapter(tool_name: str, args: dict[str, Any]) -> ToolOutputAdapter | None:
    """`tool_name` -> adapter, including the ATLAS `workspace` tool's
    read/read_file op (`tools/adapters/workspace.py`), which is a
    ReadFileAdapter under a different top-level tool name."""
    adapter = get_adapter(tool_name)
    if adapter is not None:
        return adapter
    if tool_name == "workspace" and (args or {}).get("op") in ("read", "read_file"):
        return get_adapter("read_file")
    return None


def compress_tool_output(tool_name: str, args: dict[str, Any] | None, raw_output: str) -> str:
    """Best-effort RTK compression: the compressed text for a tool with a
    registered adapter, else `raw_output` unchanged. Never raises — a
    compression bug must never break tool result storage; the raw output is
    always a safe fallback."""
    adapter = _resolve_adapter(tool_name, args or {})
    if adapter is None:
        return raw_output
    try:
        return adapter.compress(raw_output or "", args or {}).compressed
    except Exception:  # noqa: BLE001 — compression is a storage optimization, not a gate
        return raw_output
