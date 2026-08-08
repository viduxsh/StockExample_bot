import os
import json
import httpx
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_IDS
from utils.logger import get_logger

logger = get_logger(__name__)
DATA_DIR = "data"

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot stats to admins."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("You are not authorized to use this command.")
        return

    def _file_info(filename: str) -> str:
        path = os.path.join(DATA_DIR, filename)
        if not os.path.exists(path):
            return f"{filename}: not found"
        size_kb = os.path.getsize(path) / 1024
        lines = sum(1 for _ in open(path, encoding="utf-8", errors="ignore"))
        return f"{filename}: {lines} lines ({size_kb:.1f} KB)"

    try:
        op_log = _file_info("operations_log.jsonl")
        bot_log = _file_info("bot.log")
        err_log = _file_info("errors.log")

        text = (
            "📊 *Bot Statistics*\n\n"
            "*Log files:*\n"
            f"• `{op_log}`\n"
            f"• `{bot_log}`\n"
            f"• `{err_log}`"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error reading statistics: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log the error and send a message to notify the developer."""

    # httpx.ReadError is a transient network issue, not a bot bug — log as warning only
    if isinstance(context.error, httpx.ReadError):
        logger.warning("httpx.ReadError (transient network issue): %s", context.error)
        return

    logger.error("Exception while handling an update:", exc_info=context.error)

    # Send a message to the admins
    for admin_id in ADMIN_IDS:
        try:
            error_message = f"⚠️ Bot Error:\n<pre>{context.error}</pre>"
            # Avoid sending messages that are too long
            if len(error_message) > 4000:
                error_message = error_message[:4000] + "...</pre>"
            
            await context.bot.send_message(
                chat_id=admin_id, text=error_message, parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Unable to send error message to admin {admin_id}: {e}")
