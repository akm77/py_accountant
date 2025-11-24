from __future__ import annotations

import json
import logging
import re
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest
import structlog

from py_accountant.infrastructure.config.settings import get_settings
from py_accountant.infrastructure.logging.config import configure_logging, get_logger

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _reset_structlog_cache() -> None:
    # Clear handlers to force reconfiguration between tests
    root = __import__("logging").getLogger()
    root.handlers.clear()


@pytest.fixture(autouse=True)
def reset(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_structlog_cache()

    with suppress(AttributeError):  # type: ignore[attr-defined]
        get_settings.cache_clear()  # type: ignore[attr-defined]


def test_structlog_init_console(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("JSON_LOGS", "false")

    configure_logging()
    logger = get_logger("test")
    logger.debug("hello", foo=1)

    captured = capsys.readouterr().out
    plain = ANSI_RE.sub("", captured)
    assert "hello" in plain
    assert "foo=1" in plain  # console renderer pretty prints key=value
    assert "test" in plain  # logger name


def test_structlog_init_json(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("JSON_LOGS", "true")

    configure_logging()
    logger = get_logger("audit")
    logger.info("event", value=42)

    out = capsys.readouterr().out.strip().splitlines()[-1]
    log_obj = json.loads(out)
    # Basic fields
    assert log_obj["event"] == "event"
    assert log_obj["value"] == 42
    assert log_obj["level"] == "info"
    assert log_obj["logger"] == "audit"
    assert re.match(r"\d{4}-\d{2}-\d{2}T", log_obj["timestamp"]) is not None

    # structlog config processors list exists
    assert isinstance(structlog.get_config()["processors"], list)


def test_structlog_json_file_rotation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log_file = tmp_path / "app.log"
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/db")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("JSON_LOGS", "true")
    monkeypatch.setenv("LOG_FILE", str(log_file))
    monkeypatch.setenv("LOG_ROTATION", "size")
    monkeypatch.setenv("LOG_MAX_BYTES", "1024")  # 1 KiB to force rotation sooner
    monkeypatch.setenv("LOG_BACKUP_COUNT", "2")

    configure_logging()
    logger = get_logger("rotate")

    # Write enough lines to exceed 1 KiB
    for i in range(200):
        logger.info("event", seq=i, payload="x" * 20)

    # Ensure at least base file exists
    assert log_file.exists()
    contents = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert contents, "Log file should have content"
    sample = json.loads(contents[0])
    assert sample["event"] == "event"
    assert sample["logger"] == "rotate"
    # Rotation may have produced .1 file
    rotated_files = list(tmp_path.glob("app.log*"))
    assert rotated_files, "Rotation files expected"


def test_logging_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGGING_ENABLED", "false")
    _reset_structlog_cache()
    get_logger("disabled").info("no-op")
    assert not logging.getLogger().handlers
