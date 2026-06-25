"""Behavioral tests for the shared zero-dependency secure file primitive."""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import pytest

from atlas_runtime import secure_store


def test_file_lock_serializes_contenders_and_times_out(tmp_path: Path) -> None:
    lock_path = tmp_path / "config.lock"
    contender_started = threading.Event()
    result: list[str] = []

    def contend() -> None:
        contender_started.set()
        try:
            with secure_store.file_lock(lock_path, timeout_seconds=0.05):
                result.append("acquired")
        except secure_store.SecureStoreError as exc:
            result.append(exc.code)

    with secure_store.file_lock(lock_path):
        thread = threading.Thread(target=contend)
        thread.start()
        contender_started.wait(timeout=1)
        thread.join(timeout=1)

    assert result == ["store_lock_timeout"]
    assert lock_path.stat().st_size >= 1


def test_durable_replace_uses_exclusive_owner_only_temp_and_cleans_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "atlas" / "config.yaml"
    real_open = os.open
    calls: list[tuple[str, int, int]] = []

    def capture_open(name: str, flags: int, mode: int = 0o777) -> int:
        calls.append((name, flags, mode))
        return real_open(name, flags, mode)

    monkeypatch.setattr(secure_store.os, "open", capture_open)
    secure_store.durable_replace_text(path, "revision: 1\n")

    assert path.read_text(encoding="utf-8") == "revision: 1\n"
    temp_calls = [call for call in calls if call[0].endswith(".tmp")]
    assert len(temp_calls) == 1
    _, flags, mode = temp_calls[0]
    assert flags & os.O_EXCL
    assert mode == 0o600
    assert list(path.parent.glob("*.tmp")) == []


def test_posix_permission_hardening_uses_owner_only_modes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_path = tmp_path / "config.yaml"
    file_path.write_text("x", encoding="utf-8")
    calls: list[tuple[Path, int]] = []

    monkeypatch.setattr(secure_store, "_is_windows", lambda: False)
    monkeypatch.setattr(
        secure_store.os,
        "chmod",
        lambda path, mode: calls.append((Path(path), mode)),
    )

    secure_store.harden_owner_directory(tmp_path)
    secure_store.harden_owner_permissions(file_path)

    assert calls == [(tmp_path, 0o700), (file_path, 0o600)]


def test_windows_permission_hardening_uses_explicit_icacls_argv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "auth.json"
    calls: list[tuple[list[str], dict[str, object]]] = []

    monkeypatch.setattr(secure_store, "_is_windows", lambda: True)
    monkeypatch.setattr(secure_store, "_windows_identity", lambda: "DESKTOP\\operator")
    monkeypatch.setattr(
        secure_store.subprocess,
        "run",
        lambda argv, **kwargs: calls.append((argv, kwargs)),
    )

    secure_store.harden_owner_permissions(target)

    argv, kwargs = calls[0]
    assert argv[0] == "icacls"
    assert str(target) in argv
    assert "/inheritance:r" in argv
    assert "DESKTOP\\operator:(F)" in argv
    assert kwargs["shell"] is False
    assert kwargs["check"] is True


def test_preserve_corrupt_copies_to_deterministic_sibling(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("not: [yaml", encoding="utf-8")

    preserved = secure_store.preserve_corrupt(path)

    assert preserved == tmp_path / "config.yaml.corrupt"
    assert preserved.read_bytes() == path.read_bytes()


def test_file_lock_releases_after_context_exit(tmp_path: Path) -> None:
    lock_path = tmp_path / "store.lock"

    with secure_store.file_lock(lock_path):
        pass
    time.sleep(0.01)
    with secure_store.file_lock(lock_path, timeout_seconds=0.1):
        pass
