"""Typed Python client for the Rust ``atlas-evidence`` NDJSON authority.

This module owns process/protocol validation only. It deliberately contains no
diff, hashing, redaction, or SQLite persistence fallback.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import shutil
import subprocess
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "atlas-evidence/v1"
DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_CAPTURE_PAYLOAD_BYTES = 64 * 1024 * 1024


class CaptureReceipt(BaseModel):
    """Bounded receipt returned for one atomic Rust change-set transaction."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    change_set_id: str | None = None
    coverage: Literal["complete", "tool_only", "partial", "unavailable"]
    status: Literal["captured", "partial", "unavailable", "too_large"]
    file_count: int = Field(default=0, ge=0)
    additions: int = Field(default=0, ge=0)
    deletions: int = Field(default=0, ge=0)
    redaction_count: int = Field(default=0, ge=0)
    error_code: str | None = None


def unavailable_receipt(error_code: str) -> CaptureReceipt:
    return CaptureReceipt(
        coverage="unavailable",
        status="unavailable",
        error_code=error_code,
    )


def find_evidence_binary() -> str | None:
    configured = os.environ.get("ATLAS_EVIDENCE_BIN", "").strip()
    if configured:
        return configured
    installed = shutil.which("atlas-evidence")
    if installed:
        return installed
    suffix = ".exe" if os.name == "nt" else ""
    root = pathlib.Path(__file__).resolve().parents[3]
    for profile in ("release", "debug"):
        candidate = (
            root
            / "native"
            / "atlas-core-rs"
            / "target"
            / profile
            / f"atlas-evidence{suffix}"
        )
        if candidate.is_file():
            return str(candidate)
    return None


def _protocol_request(
    db_path: pathlib.Path,
    capture: dict[str, object],
) -> dict[str, object]:
    return {
        "protocol": PROTOCOL_VERSION,
        "kind": "change_set",
        "db_path": str(db_path),
        "provenance": {
            "run_id": capture.get("run_id"),
            "session_id": capture.get("session_id"),
            "team_run_id": capture.get("team_run_id"),
            "turn_id": capture.get("turn_id"),
            "actor_id": capture.get("actor_id"),
            "parent_actor_id": capture.get("parent_actor_id"),
            "tool_call_id": capture.get("tool_call_id"),
        },
        "coverage": capture.get("coverage", "partial"),
        "status": capture.get("status", "partial"),
        "files": capture.get("files", []),
    }


def persist_change_capture(
    *,
    db_path: pathlib.Path | None,
    capture: dict[str, object],
    evidence_bin: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> CaptureReceipt:
    """Persist one capture envelope or return a typed unavailable receipt."""

    if db_path is None:
        return unavailable_receipt("database_unavailable")
    executable = evidence_bin or find_evidence_binary()
    if not executable:
        return unavailable_receipt("binary_unavailable")
    files = capture.get("files")
    if not isinstance(files, list):
        return unavailable_receipt("invalid_capture")
    payload_bytes = 0
    for file in files:
        if not isinstance(file, dict):
            return unavailable_receipt("invalid_capture")
        payload_bytes += len(str(file.get("before", "")).encode("utf-8"))
        payload_bytes += len(str(file.get("after", "")).encode("utf-8"))
    if payload_bytes > MAX_CAPTURE_PAYLOAD_BYTES:
        return CaptureReceipt(
            coverage="partial",
            status="too_large",
            error_code="capture_too_large",
        )

    request = _protocol_request(db_path, capture)
    try:
        result = subprocess.run(  # noqa: S603
            [executable],
            input=json.dumps(request, ensure_ascii=False) + "\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.error("Rust evidence capture timed out after %.3fs", timeout_seconds)
        return unavailable_receipt("timeout")
    except (OSError, subprocess.SubprocessError) as exc:
        logger.error("Rust evidence capture process unavailable: %s", exc)
        return unavailable_receipt("process_unavailable")

    try:
        lines = result.stdout.splitlines()
        response = json.loads(lines[-1]) if lines else None
        if not isinstance(response, dict):
            raise ValueError("response is not an object")
    except (ValueError, json.JSONDecodeError):
        logger.error("Rust evidence capture returned malformed JSON")
        return unavailable_receipt("malformed_response")

    if response.get("protocol") != PROTOCOL_VERSION:
        logger.error("Rust evidence capture protocol mismatch")
        return unavailable_receipt("protocol_mismatch")
    if result.returncode != 0 or response.get("ok") is not True:
        error = response.get("error")
        code = error.get("code") if isinstance(error, dict) else None
        logger.error(
            "Rust evidence capture failed rc=%s error=%s",
            result.returncode,
            error or result.stderr[-500:],
        )
        return unavailable_receipt(str(code or "persistence_failed"))

    try:
        return CaptureReceipt.model_validate(response.get("change_set"))
    except ValidationError:
        logger.error("Rust evidence capture returned an invalid typed receipt")
        return unavailable_receipt("malformed_response")
