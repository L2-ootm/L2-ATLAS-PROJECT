"""Centralized logging configuration tests (F13)."""
from __future__ import annotations

import logging

import pytest

from atlas_runtime import logging_config


@pytest.fixture(autouse=True)
def _isolated_logging():
    logging_config.reset_for_tests()
    yield
    logging_config.reset_for_tests()


def test_configure_creates_rotating_file_and_logs(tmp_path) -> None:
    handler = logging_config.configure_logging(level="DEBUG", log_dir=tmp_path)
    assert handler is not None

    logging.getLogger("atlas_runtime.test").debug("hello from the audit trail")
    handler.flush()

    log_file = tmp_path / "atlas.log"
    assert log_file.is_file()
    content = log_file.read_text(encoding="utf-8")
    assert "hello from the audit trail" in content
    assert "DEBUG" in content


def test_configure_is_idempotent(tmp_path) -> None:
    first = logging_config.configure_logging(log_dir=tmp_path)
    second = logging_config.configure_logging(log_dir=tmp_path)
    assert first is not None
    assert second is None
    assert len(logging.getLogger("atlas_runtime").handlers) == 1


def test_configure_fails_open_on_unwritable_dir(tmp_path) -> None:
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("file, not dir", encoding="utf-8")
    handler = logging_config.configure_logging(log_dir=blocker / "logs")
    assert handler is None  # no raise — startup must survive


def test_env_level_respected(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ATLAS_LOG_LEVEL", "ERROR")
    handler = logging_config.configure_logging(log_dir=tmp_path)
    assert handler is not None
    assert logging.getLogger("atlas_runtime").level == logging.ERROR
