from __future__ import annotations

import dataclasses
import json
import pathlib
import stat
import time

import pytest

from atlas_runtime import service_supervision as supervision


def _record(**changes: object) -> supervision.ServiceLaunchRecord:
    values: dict[str, object] = {
        "service": "gateway",
        "pid": 4321,
        "executable_path": r"C:\Atlas\atlas-gateway.exe",
        "process_creation_time": 987654321,
        "argv_fingerprint": supervision.argv_fingerprint(
            ["atlas-gateway", "--token", "do-not-store-me"]
        ),
        "host": "127.0.0.1",
        "port": 8484,
        "launched_at": "2026-08-05T12:00:00Z",
        "log_path": r"C:\Atlas\logs\gateway.log",
    }
    values.update(changes)
    return supervision.ServiceLaunchRecord(**values)  # type: ignore[arg-type]


def _no_port(host: str, port: int, *, timeout: float) -> supervision.PortObservation:
    del timeout
    return supervision.PortObservation(host, port, False, "ConnectionRefusedError")


def test_launch_record_round_trip_is_frozen_json_stable_and_secret_free(
    tmp_path: pathlib.Path,
) -> None:
    path = tmp_path / "gateway.service.json"
    record = _record()

    supervision.write_launch_record(record, path)

    assert supervision.load_launch_record(path) == record
    assert json.dumps(record.to_dict(), sort_keys=True)
    assert "do-not-store-me" not in path.read_text(encoding="utf-8")
    if supervision.os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) & 0o077 == 0
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.pid = 9  # type: ignore[misc]


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "[]",
        '{"schema_version":1}',
        json.dumps({**_record().to_dict(), "pid": True}),
        json.dumps({**_record().to_dict(), "schema_version": 999}),
        json.dumps({**_record().to_dict(), "surprise": "field"}),
    ],
)
def test_malformed_or_unsupported_records_fail_explicitly(
    tmp_path: pathlib.Path, payload: str
) -> None:
    path = tmp_path / "bad.service.json"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(supervision.ServiceStateError):
        supervision.load_launch_record(path)


def test_missing_record_and_legacy_pid_compatibility(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "legacy.pid"
    assert supervision.load_launch_record(tmp_path / "missing.json") is None
    assert supervision.read_legacy_pid(path) is None

    path.write_text(" 31415\n", encoding="utf-8")
    assert supervision.read_legacy_pid(path) == 31415
    for malformed in ("", "0", "-1", "12x", "{}"):
        path.write_text(malformed, encoding="utf-8")
        assert supervision.read_legacy_pid(path) is None


def test_atomic_write_retries_then_succeeds(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "gateway.service.json"
    real_replace = supervision.os.replace
    attempts = 0

    def flaky_replace(source: object, destination: object) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("temporarily held")
        real_replace(source, destination)

    monkeypatch.setattr(supervision.os, "replace", flaky_replace)
    supervision.write_launch_record(_record(), path, retries=2, retry_delay=0)

    assert attempts == 3
    assert supervision.load_launch_record(path) == _record()


def test_atomic_write_failure_preserves_previous_valid_record(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "gateway.service.json"
    original = _record(pid=111)
    supervision.write_launch_record(original, path)
    before = path.read_bytes()

    def denied(source: object, destination: object) -> None:
        del source, destination
        raise PermissionError("held by scanner")

    monkeypatch.setattr(supervision.os, "replace", denied)
    with pytest.raises(PermissionError):
        supervision.write_launch_record(
            _record(pid=222), path, retries=2, retry_delay=0
        )

    assert path.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize(
    ("observation", "state", "reason"),
    [
        (
            supervision.ProcessObservation(4321, False, False),
            "stopped",
            "process_dead",
        ),
        (
            supervision.ProcessObservation(
                4321, True, True, r"C:\Other\atlas-gateway.exe", 987654321
            ),
            "identity_mismatch",
            "executable_mismatch",
        ),
        (
            supervision.ProcessObservation(
                4321, True, True, r"c:\atlas\ATLAS-GATEWAY.EXE", 12
            ),
            "identity_mismatch",
            "creation_time_mismatch",
        ),
        (
            supervision.ProcessObservation(4321, True, False, error="access_denied"),
            "unverifiable",
            "identity_unavailable",
        ),
        (
            supervision.ProcessObservation(
                4321,
                True,
                True,
                r"c:\atlas\ATLAS-GATEWAY.EXE",
                987654321,
            ),
            "running",
            "exact_match",
        ),
    ],
)
def test_observed_status_fails_closed_for_dead_reused_wrong_or_unavailable_process(
    observation: supervision.ProcessObservation, state: str, reason: str
) -> None:
    status = supervision.observe_service(
        _record(), process_observer=lambda pid: observation, port_observer=_no_port
    )

    assert status.state == state
    assert status.identity is not None
    assert status.identity.reason == reason
    assert json.loads(json.dumps(status.to_dict()))["state"] == state
    with pytest.raises(dataclasses.FrozenInstanceError):
        status.state = "anything"  # type: ignore[misc]


def test_port_observation_is_diagnostic_not_identity_authority() -> None:
    wrong_listener = lambda host, port, timeout: supervision.PortObservation(  # noqa: E731
        host, port, True
    )
    dead = supervision.ProcessObservation(4321, False, False)

    status = supervision.observe_service(
        _record(), process_observer=lambda pid: dead, port_observer=wrong_listener
    )

    assert status.port is not None and status.port.listening is True
    assert status.state == "stopped"


def test_late_atlas_home_controls_all_owner_local_paths(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    monkeypatch.setenv("ATLAS_HOME", str(first))
    assert supervision.state_path("gateway").parent == first
    assert supervision.legacy_pid_path("gateway").parent == first

    monkeypatch.setenv("ATLAS_HOME", str(second))
    assert supervision.state_path("gateway").parent == second
    assert supervision.log_path("gateway").parent == second / "logs"
    assert supervision.lock_path("gateway").parent == second / "locks"


def test_sensitive_log_rotates_is_owner_only_and_tail_is_bounded_redacted(
    tmp_path: pathlib.Path,
) -> None:
    path = tmp_path / "service.log"
    canary = "CANARY-ultra-secret"
    path.write_bytes(b"old-log-that-is-over-limit")

    with supervision.open_sensitive_log(path, max_bytes=8, backups=2) as handle:
        handle.write(
            (
                "discarded line\n"
                "\x1b[31mboom\x1b[0m\x00\n"
                f"Authorization: Bearer header-token token={canary}\n"
                "password=hunter2 https://alice:pass@example.test\n"
            ).encode("utf-8")
            + b"broken:\xff\n"
        )

    assert (tmp_path / "service.log.1").read_bytes() == b"old-log-that-is-over-limit"
    if supervision.os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) & 0o077 == 0
    tail = supervision.sanitized_log_tail(
        path, max_bytes=512, max_lines=4, redact_values=[canary]
    )
    assert tail.truncated is True
    assert "discarded line" not in tail.text
    assert "\x1b" not in tail.text and "\x00" not in tail.text
    assert "header-token" not in tail.text
    assert canary not in tail.text
    assert "hunter2" not in tail.text and "pass@example" not in tail.text
    assert "[REDACTED]" in tail.text
    assert "�" in tail.text


def test_sensitive_log_directory_stays_traversable_after_hardening(
    tmp_path: pathlib.Path,
) -> None:
    """Hardening the log directory must not lock its owner out.

    POSIX needs the owner execute bit to traverse a directory at all, so an
    rw-only log directory makes every open inside it fail with EACCES — the
    first one included, since the directory is hardened before the file.
    """
    path = tmp_path / "logs" / "service.log"

    with supervision.open_sensitive_log(path) as handle:
        handle.write(b"first\n")
    with supervision.open_sensitive_log(path) as handle:
        handle.write(b"second\n")

    assert path.read_bytes() == b"first\nsecond\n"
    if supervision.os.name != "nt":
        mode = stat.S_IMODE(path.parent.stat().st_mode)
        assert mode & 0o077 == 0
        assert mode & stat.S_IXUSR


def test_tail_byte_truncation_handles_split_utf8_and_missing_file(
    tmp_path: pathlib.Path,
) -> None:
    path = tmp_path / "unicode.log"
    path.write_bytes(("first\n" + "🙂" * 20 + "\nlast\n").encode("utf-8"))

    result = supervision.sanitized_log_tail(path, max_bytes=20, max_lines=10)

    assert result.truncated is True
    assert result.text.endswith("last")
    assert supervision.sanitized_log_tail(tmp_path / "missing.log").to_dict() == {
        "text": "",
        "truncated": False,
    }


def test_service_lock_is_per_service_bounded_and_released(
    tmp_path: pathlib.Path,
) -> None:
    path = tmp_path / "gateway.lock"
    with supervision.service_lock("gateway", path=path, timeout=0):
        started = time.monotonic()
        with pytest.raises(supervision.ServiceLockBusy):
            with supervision.service_lock(
                "gateway", path=path, timeout=0.03, poll_interval=0.005
            ):
                pytest.fail("contended lock must not be acquired")
        assert time.monotonic() - started < 0.25
        assert path.exists()

    assert not path.exists()
    with supervision.service_lock("gateway", path=path, timeout=0):
        assert path.exists()


@pytest.mark.parametrize("service", ["../gateway", "Gateway", "", "x" * 65])
def test_service_keys_cannot_escape_owner_root(service: str) -> None:
    with pytest.raises(ValueError):
        supervision.state_path(service)
