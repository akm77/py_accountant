"""Telegram bot entry point with py_accountant integration.

This is a minimal working example of integrating py_accountant into an aiogram bot.
For full production-ready implementation, see docs/INTEGRATION_GUIDE_AIOGRAM.md
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from config import settings
from clock import create_clock
from uow import create_uow_factory

# Configure logging
logging.basicConfig(
    level=settings.bot_log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def start_handler(message: Message) -> None:
    """Handle /start command."""
    await message.reply(
        "👋 Welcome to Finance Bot!\n\n"
        "Available commands:\n"
        "/currencies - List currencies\n"
        "/accounts - List your accounts\n"
        "/balance - Check balance\n"
        "/deposit - Record income\n"
        "/expense - Record expense\n"
        "/history - View transaction history\n\n"
        "Example:\n"
        "/deposit 1000 USD Salary"
    )


async def ping_handler(message: Message) -> None:
    """Handle /ping command."""
    await message.reply("🏓 Pong! Bot is running.")


async def on_startup(bot: Bot, uow_factory) -> None:
    """Initialize resources on bot startup."""
    logger.info("Bot starting up...")

    # Verify database connection
    try:
        async with uow_factory() as uow:
            currencies = await uow.currencies.list_all()
            logger.info(f"Database connection verified. Found {len(currencies)} currencies.")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

    logger.info("Bot startup complete")


async def on_shutdown(bot: Bot, uow_factory) -> None:
    """Cleanup resources on bot shutdown."""
    logger.info("Bot shutting down...")

    # Close database connections
    try:
        uow = uow_factory()
        await uow.engine.dispose()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

    await bot.session.close()
    logger.info("Bot shutdown complete")


async def main() -> None:
    """Start bot."""
    # Initialize bot and dispatcher
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Create dependencies
    uow_factory = create_uow_factory()
    clock = create_clock()

    # Store dependencies in bot data for access in handlers
    bot["uow_factory"] = uow_factory
    bot["clock"] = clock

    # Register basic handlers
    dp.message.register(start_handler, Command("start"))
    dp.message.register(ping_handler, Command("ping"))

    # TODO: Register additional handlers from handlers/ modules
    # from handlers import transaction, account, currency, history
    # dp.include_router(transaction.router)
    # dp.include_router(account.router)
    # dp.include_router(currency.router)
    # dp.include_router(history.router)

    # Start polling
    logger.info("Starting bot polling...")
    try:
        await on_startup(bot, uow_factory)
        await dp.start_polling(bot)
    finally:
        await on_shutdown(bot, uow_factory)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception(f"Bot crashed: {e}")

