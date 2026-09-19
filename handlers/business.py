import json
import os
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_IDS
from utils.logger import get_logger
from handlers.autoreply import load_replies

logger = get_logger(__name__)

# Key used in bot_data to persist the connection_id → admin_id mapping
_CONN_MAP_KEY = "business_connections"


async def business_connection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle business connections (when the bot is added or removed from a business account)."""
    connection = update.business_connection
    if not connection:
        return

    # Initialise the mapping dict if not present
    if _CONN_MAP_KEY not in context.bot_data:
        context.bot_data[_CONN_MAP_KEY] = {}

    if connection.is_enabled:
        # Map this opaque connection ID to the admin's Telegram user ID
        context.bot_data[_CONN_MAP_KEY][connection.id] = connection.user_id

        logger.info(
            "Bot CONNECTED to secretary account %s (connection ID: %s) | can_reply=%s",
            connection.user_id,
            connection.id,
            getattr(connection, "can_reply", "N/A"),
        )
    else:
        # Remove the mapping when disconnected
        context.bot_data[_CONN_MAP_KEY].pop(connection.id, None)
        logger.info(
            "Bot DISCONNECTED from secretary account %s (connection ID: %s)",
            connection.user_id,
            connection.id,
        )


async def business_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages sent to the connected business account."""
    message = update.business_message
    if not message or not message.text:
        return

    # Avoid answering our own replies or loops
    if message.from_user.is_bot:
        return

    text = message.text
    text_lower = text.lower()

    # ── Resolve which admin owns this connection ─────────────────────────────
    conn_map: dict = context.bot_data.get(_CONN_MAP_KEY, {})
    admin_id: int | None = conn_map.get(message.business_connection_id)

    if admin_id is None:
        # Connection not in memory (e.g. bot restarted) — fall back to ADMIN_IDS order
        logger.warning(
            "Unknown business_connection_id %s — connection map: %s. "
            "Falling back to first admin.",
            message.business_connection_id,
            list(conn_map.keys()),
        )
        admin_id = ADMIN_IDS[0] if ADMIN_IDS else None

    if admin_id is None:
        logger.error("No admin_id available to handle business message.")
        return

    replies = load_replies(admin_id)

    for keyword, response in replies.items():
        if keyword.lower() in text_lower:
            logger.info(
                "Business auto-reply triggered: keyword=%r (admin=%s) for user=%s chat_id=%s connection=%s",
                keyword,
                admin_id,
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

    # No keyword matched — ignore silently in secretary mode
    logger.debug("Ignored business message without matching keywords: %s", text)
