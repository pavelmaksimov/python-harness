"""Order commands for the Telegram bot, with inline error handling."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import ContextTypes

from project.components.orders.use_cases import OrderStatusUseCase

logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await update.effective_message.reply_text("Hello!")
    except Exception as exc:  # noqa: BLE001
        logger.warning("start failed: %s", exc)


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session: AsyncSession = context.bot_data["session"]
    try:
        status = await OrderStatusUseCase(session).run(update.effective_user.id)
        await update.effective_message.reply_text(status)
    except TimeoutError:
        await update.effective_message.reply_text("Timed out, please try again")
    except Exception:  # noqa: BLE001
        await update.effective_message.reply_text("Something went wrong")
