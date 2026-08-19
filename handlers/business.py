import json
import os
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_IDS
from utils.logger import get_logger
from handlers.autoreply import load_replies

logger = get_logger(__name__)

async def business_connection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle business connections (when the bot is added or removed from a business account)."""
    connection = update.business_connection
    if not connection:
        return

    if connection.is_enabled:
        logger.info(
            "Bot CONNECTED to secretary account %s (connection ID: %s) | can_reply=%s",
            connection.user_chat_id,
            connection.id,
            getattr(connection, 'can_reply', 'N/A')
        )
    else:
        logger.info(f"Bot DISCONNECTED from secretary account {connection.user_chat_id} (connection ID: {connection.id})")




async def business_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages sent to the connected business account."""
    message = update.business_message
    if not message or not message.text:
        return

    # To avoid answering our own replies or loops
    if message.from_user.is_bot:
        return

    text = message.text
    text_lower = text.lower()
    
    replies = load_replies()

    for keyword, response in replies.items():
        if keyword.lower() in text_lower:
            logger.info(
                "Business auto-reply triggered: keyword=%r for user=%s chat_id=%s connection=%s",
                keyword,
                message.from_user.id,
                message.chat_id,
                message.business_connection_id,
            )
            try:
                # Use from_user.id as chat_id — in private chats they coincide.
                # Explicitly pass business_connection_id so PTB signs the request correctly.
                await context.bot.send_message(
                    chat_id=message.from_user.id,
                    text=response,
                    business_connection_id=message.business_connection_id,
                )
                logger.info("Business reply sent successfully.")
            except Exception as e:
                logger.error(
                    "Failed to send business reply (chat_id=%s, conn=%s): %s",
                    message.from_user.id,
                    message.business_connection_id,
                    e,
                )
            return

    # If no keyword matched, we could just ignore it or echo.
    # In secretary mode, it's usually better to ignore unless there is a match,
    # otherwise it echoes all normal user conversations.
    logger.debug(f"Ignored business message without matching keywords: {text}")
