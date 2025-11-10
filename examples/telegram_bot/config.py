from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class BotSettings:
    bot_token: str
    database_url: str
    log_level: str = "INFO"
    json_logs: bool = False


def load_settings() -> BotSettings:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN not set")
    db_url = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./bot.db")
    return BotSettings(
        bot_token=token,
        database_url=db_url,
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        json_logs=os.getenv("JSON_LOGS", "false").lower() == "true",
    )

