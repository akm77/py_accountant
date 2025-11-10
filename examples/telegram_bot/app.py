from __future__ import annotations

import asyncio
from typing import Final

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from examples.telegram_bot.config import load_settings
from examples.telegram_bot.handlers import (
    handle_audit,
    handle_balance,
    handle_rates,
    handle_start,
    handle_tx,
)
from infrastructure.logging.config import configure_logging, get_logger

configure_logging()
log = get_logger("bot")

SETTINGS = load_settings()
DB_URL: Final[str] = SETTINGS.database_url


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:  # noqa: D401
    text = handle_start(DB_URL)
    await update.message.reply_text(text)
    log.info("cmd_start", user_id=update.effective_user.id if update.effective_user else None)


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:  # noqa: D401
    if not context.args:
        await update.message.reply_text("Usage: /balance <AccountFullName>")
        return
    account = context.args[0]
    text = handle_balance(DB_URL, account)
    await update.message.reply_text(text)
    log.info("cmd_balance", account=account)


async def tx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:  # noqa: D401
    if not context.args:
        await update.message.reply_text("Usage: /tx <LINE1;LINE2;...> (SIDE:Account:Amount:Currency:Rate|NONE)")
        return
    raw = " ".join(context.args)
    text = handle_tx(DB_URL, raw)
    await update.message.reply_text(text)
    log.info("cmd_tx", raw=raw)


async def rates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:  # noqa: D401
    text = handle_rates(DB_URL)
    await update.message.reply_text(text)
    log.info("cmd_rates")


async def audit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:  # noqa: D401
    text = handle_audit(DB_URL)
    await update.message.reply_text(text)
    log.info("cmd_audit")


async def main() -> None:
    app = ApplicationBuilder().token(SETTINGS.bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("tx", tx))
    app.add_handler(CommandHandler("rates", rates))
    app.add_handler(CommandHandler("audit", audit))

    log.info("bot_starting")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    # Run until Ctrl+C
    try:
        await asyncio.Event().wait()
    finally:
        log.info("bot_stopping")
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

