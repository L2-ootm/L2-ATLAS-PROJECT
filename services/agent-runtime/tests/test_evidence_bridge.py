from __future__ import annotations

import json
import subprocess

from atlas_runtime import evidence_bridge


def _capture_request(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return {
        "run_id": "run-1",
        "session_id": "session-1",
        "tool_call_id": "call-1",
        "coverage": "complete",
        "status": "captured",
        "files": [
            {
                "path": "src/example.txt",
                "operation": "edit",
                "before": "token=before-secret\nold\n",
                "after": "token=after-secret\nnew\n",
                "generated": False,
            }
        ],
    }


def test_bridge_sends_one_versioned_capture_envelope_and_validates_receipt(
    monkeypatch, tmp_path
):
    observed = {}

    def run(command, **kwargs):
        observed["command"] = command
        observed["request"] = json.loads(kwargs["input"])
        observed["timeout"] = kwargs["timeout"]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "protocol": evidence_bridge.PROTOCOL_VERSION,
                    "ok": True,
                    "change_set": {
                        "change_set_id": "change-1",
                        "coverage": "complete",
                        "status": "captured",
                        "file_count": 1,
                        "additions": 1,
                        "deletions": 1,
                        "redaction_count": 2,
                    },
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(evidence_bridge.subprocess, "run", run)
    receipt = evidence_bridge.persist_change_capture(
        db_path=tmp_path / "atlas.db",
        evidence_bin="atlas-evidence-test",
        capture=_capture_request(tmp_path),
        timeout_seconds=2.5,
    )

    assert receipt.status == "captured"
    assert receipt.change_set_id == "change-1"
    assert receipt.file_count == 1
    assert observed["command"] == ["atlas-evidence-test"]
    assert observed["request"]["protocol"] == evidence_bridge.PROTOCOL_VERSION
    assert observed["request"]["kind"] == "change_set"
    assert observed["request"]["db_path"] == str(tmp_path / "atlas.db")
    assert observed["timeout"] == 2.5


def test_bridge_timeout_is_explicit_and_has_no_python_persistence_fallback(
    monkeypatch, tmp_path
):
    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("atlas-evidence", 0.01)

    monkeypatch.setattr(evidence_bridge.subprocess, "run", timeout)
    receipt = evidence_bridge.persist_change_capture(
        db_path=tmp_path / "atlas.db",
        evidence_bin="atlas-evidence-test",
        capture=_capture_request(tmp_path),
        timeout_seconds=0.01,
    )

    assert receipt.status == "unavailable"
    assert receipt.coverage == "unavailable"
    assert receipt.change_set_id is None
    assert receipt.error_code == "timeout"


def test_bridge_rejects_malformed_or_wrong_version_response(monkeypatch, tmp_path):
    responses = [
        subprocess.CompletedProcess(["e"], 0, stdout="not-json\n", stderr=""),
        subprocess.CompletedProcess(
            ["e"],
            0,
            stdout=json.dumps(
                {
                    "protocol": "atlas-evidence/v0",
                    "ok": True,
                    "change_set": {},
                }
            ),
            stderr="",
        ),
    ]

    for completed in responses:
        monkeypatch.setattr(
            evidence_bridge.subprocess,
            "run",
            lambda *_args, _completed=completed, **_kwargs: _completed,
        )
        receipt = evidence_bridge.persist_change_capture(
            db_path=tmp_path / "atlas.db",
            evidence_bin="atlas-evidence-test",
            capture=_capture_request(tmp_path),
        )
        assert receipt.status == "unavailable"
        assert receipt.change_set_id is None
        assert receipt.error_code in {"malformed_response", "protocol_mismatch"}

