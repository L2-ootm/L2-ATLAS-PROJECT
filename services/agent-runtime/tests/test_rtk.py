"""Tests for atlas_runtime.rtk_bridge."""
from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from atlas_runtime.rtk_bridge import available, compress_output, rewrite_command


def test_available_when_rtk_on_path(monkeypatch):
    monkeypatch.setattr("atlas_runtime.rtk_bridge.shutil.which", lambda _: "/usr/bin/rtk")
    assert available() is True


def test_available_when_rtk_missing(monkeypatch):
    monkeypatch.setattr("atlas_runtime.rtk_bridge.shutil.which", lambda _: None)
    assert available() is False


def test_rewrite_command_returns_original_when_disabled(monkeypatch):
    monkeypatch.setenv("ATLAS_RTK_DISABLED", "1")
    assert rewrite_command("git status") == "git status"


def test_rewrite_command_returns_original_when_unavailable(monkeypatch):
    monkeypatch.delenv("ATLAS_RTK_DISABLED", raising=False)
    monkeypatch.setattr("atlas_runtime.rtk_bridge.available", lambda: False)
    assert rewrite_command("git status") == "git status"


def test_rewrite_command_returns_rewritten_on_success(monkeypatch):
    monkeypatch.delenv("ATLAS_RTK_DISABLED", raising=False)
    monkeypatch.setattr("atlas_runtime.rtk_bridge.available", lambda: True)

    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, stdout="rtk git status\n", stderr="")
    monkeypatch.setattr("atlas_runtime.rtk_bridge.subprocess.run", fake_run)
    assert rewrite_command("git status") == "rtk git status"


def test_rewrite_command_returns_original_on_exit_1(monkeypatch):
    monkeypatch.delenv("ATLAS_RTK_DISABLED", raising=False)
    monkeypatch.setattr("atlas_runtime.rtk_bridge.available", lambda: True)

    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")
    monkeypatch.setattr("atlas_runtime.rtk_bridge.subprocess.run", fake_run)
    assert rewrite_command("some_cmd") == "some_cmd"


def test_compress_output_returns_original_when_disabled(monkeypatch):
    monkeypatch.setenv("ATLAS_RTK_DISABLED", "1")
    assert compress_output("hello") == "hello"


def test_compress_output_returns_original_when_not_smaller(monkeypatch):
    monkeypatch.delenv("ATLAS_RTK_DISABLED", raising=False)
    monkeypatch.setattr("atlas_runtime.rtk_bridge.available", lambda: True)

    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, stdout="same length output", stderr="")
    monkeypatch.setattr("atlas_runtime.rtk_bridge.subprocess.run", fake_run)
    assert compress_output("same length output") == "same length output"


def test_compress_output_returns_compressed_when_smaller(monkeypatch):
    monkeypatch.delenv("ATLAS_RTK_DISABLED", raising=False)
    monkeypatch.setattr("atlas_runtime.rtk_bridge.available", lambda: True)

    long_output = "line\n" * 100
    short_output = "3 lines\n"

    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, stdout=short_output, stderr="")
    monkeypatch.setattr("atlas_runtime.rtk_bridge.subprocess.run", fake_run)
    assert compress_output(long_output) == short_output


def test_compress_output_returns_original_on_timeout(monkeypatch):
    monkeypatch.delenv("ATLAS_RTK_DISABLED", raising=False)
    monkeypatch.setattr("atlas_runtime.rtk_bridge.available", lambda: True)

    def fake_run(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 5)
    monkeypatch.setattr("atlas_runtime.rtk_bridge.subprocess.run", fake_run)
    assert compress_output("hello") == "hello"
