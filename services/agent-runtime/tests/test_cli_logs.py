"""Tests for `atlas logs` — tails <ATLAS home>/logs/atlas.log.

--follow is an infinite polling loop (only exits on Ctrl-C) and isn't covered
here; the tail-reading and --path/missing-file paths are pure and fast.
"""
from __future__ import annotations

from typer.testing import CliRunner

from atlas_runtime import logging_config
from atlas_runtime.cli.main import app

runner = CliRunner()


def test_logs_path_flag_prints_resolved_path(tmp_path, monkeypatch) -> None:
    target = tmp_path / "atlas.log"
    monkeypatch.setattr(logging_config, "log_file_path", lambda: target)
    result = runner.invoke(app, ["logs", "--path"])
    assert result.exit_code == 0
    assert result.output.strip() == str(target)


def test_logs_missing_file_exits_nonzero(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(logging_config, "log_file_path", lambda: tmp_path / "missing.log")
    result = runner.invoke(app, ["logs"])
    assert result.exit_code == 1
    assert "no log file yet" in result.output


def test_logs_default_tail(tmp_path, monkeypatch) -> None:
    target = tmp_path / "atlas.log"
    target.write_text("\n".join(f"line{i}" for i in range(1, 101)) + "\n", encoding="utf-8")
    monkeypatch.setattr(logging_config, "log_file_path", lambda: target)
    result = runner.invoke(app, ["logs"])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert len(lines) == 50
    assert lines[0] == "line51"
    assert lines[-1] == "line100"


def test_logs_custom_tail_count(tmp_path, monkeypatch) -> None:
    target = tmp_path / "atlas.log"
    target.write_text("\n".join(f"line{i}" for i in range(1, 11)) + "\n", encoding="utf-8")
    monkeypatch.setattr(logging_config, "log_file_path", lambda: target)
    result = runner.invoke(app, ["logs", "--tail", "3"])
    assert result.exit_code == 0
    assert result.output.strip().splitlines() == ["line8", "line9", "line10"]


def test_logs_tail_zero_prints_whole_file(tmp_path, monkeypatch) -> None:
    target = tmp_path / "atlas.log"
    target.write_text("only-line\n", encoding="utf-8")
    monkeypatch.setattr(logging_config, "log_file_path", lambda: target)
    result = runner.invoke(app, ["logs", "--tail", "0"])
    assert result.exit_code == 0
    assert result.output.strip() == "only-line"


def test_log_file_path_helper_honors_atlas_home(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.delenv("ATLAS_LOG_DIR", raising=False)
    assert logging_config.log_file_path() == tmp_path / "logs" / "atlas.log"
