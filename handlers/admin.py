import os
import json
import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_IDS

logger = logging.getLogger(__name__)
DATA_DIR = "data"

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot stats to admins."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("You are not authorized to use this command.")
        return
        
    try:
        # Count the lines in operations_log.jsonl
        log_path = os.path.join(DATA_DIR, "operations_log.jsonl")
        count = 0
        if os.path.exists(log_path):
            with open(log_path, 'r', encoding='utf-8') as f:
                count = sum(1 for _ in f)
                
        await update.message.reply_text(f"📊 Bot Statistics:\n- Total recorded operations: {count}")
    except Exception as e:
        await update.message.reply_text(f"Error reading statistics: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log the error and send a message to notify the developer."""
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
