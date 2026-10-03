import json
import os
import time
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_IDS
from utils.logger import get_logger
from handlers.autoreply import load_replies

logger = get_logger(__name__)

DATA_DIR = "data"
# Key used in bot_data to persist the connection_id → admin_id mapping (in-memory)
_CONN_MAP_KEY = "business_connections"
# Backup file for conn_map — survives bot restarts reliably
_CONN_FILE = os.path.join(DATA_DIR, "business_connections.json")


# ---------------------------------------------------------------------------
# Persistent connection map helpers
# ---------------------------------------------------------------------------

def _load_conn_map() -> dict:
    """Load the connection_id → admin_id map from disk (fallback for restarts)."""
    try:
        with open(_CONN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_conn_map(conn_map: dict) -> None:
    """Persist the connection_id → admin_id map to disk."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_CONN_FILE, "w", encoding="utf-8") as f:
        json.dump(conn_map, f, ensure_ascii=False, indent=2)


async def business_connection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle business connections (when the bot is added or removed from a business account)."""
    connection = update.business_connection
    if not connection:
        return

    # Initialise the in-memory mapping dict if not present
    if _CONN_MAP_KEY not in context.bot_data:
        context.bot_data[_CONN_MAP_KEY] = _load_conn_map()  # seed from file

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

    # Persist to file so it survives bot restarts
    _save_conn_map(context.bot_data[_CONN_MAP_KEY])
    logger.info("Connection map saved: %s", context.bot_data[_CONN_MAP_KEY])


async def business_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages sent to the connected business account."""
    message = update.business_message
    if not message:
        return

    # Avoid answering our own replies or loops
    if message.from_user and message.from_user.is_bot:
        return

    text = message.text or message.caption or ""
    text_lower = text.lower().strip()
    # is_media = True for stickers, photos without text/caption, etc.
    is_media = not (message.text or message.caption)

    # ── Resolve which admin owns this connection ─────────────────────────────
    # 1. Try in-memory map (fastest, populated when connection event fires)
    conn_map: dict = context.bot_data.get(_CONN_MAP_KEY, {})
    # 2. Fallback to file-persisted map (survives bot restarts)
    if not conn_map:
        conn_map = _load_conn_map()
        if conn_map:
            context.bot_data[_CONN_MAP_KEY] = conn_map  # restore in-memory cache
            logger.info("Connection map restored from file: %s", conn_map)

    admin_id: int | None = conn_map.get(message.business_connection_id)

    admin_id_str = str(admin_id) if admin_id else "unknown"

    if admin_id is None:
        # Connection not in memory (e.g. bot restarted) — fall back to ADMIN_IDS order
        logger.warning(
            "Unknown business_connection_id %s — connection map: %s. "
            "Falling back to first admin.",
            message.business_connection_id,
            list(conn_map.keys()),
        )
        admin_id = ADMIN_IDS[0] if ADMIN_IDS else None
        admin_id_str = str(admin_id)

    if admin_id is None:
        logger.error("No admin_id available to handle business message.")
        return

    replies = load_replies(admin_id)

    # -- 24h inactivity timeout for "first" rule --
    now = time.time()
    last_interaction = context.user_data.get("last_business_interaction_time", 0)
    if now - last_interaction > 86400:  # 24 hours
        context.user_data["business_first_reply_seen"] = set()
    context.user_data["last_business_interaction_time"] = now

    # Separate key for business first-seen to avoid mixing with normal bot chats.
    # Key = (admin_id_str, keyword) so each "first" rule is tracked independently.
    first_seen_set: set = context.user_data.setdefault("business_first_reply_seen", set())

    for keyword, rule in replies.items():
        response = rule.get("response", "")
        mode = rule.get("mode", "contains")

        matched = False

        if mode == "first":
            # Trigger on ANY message type (including stickers) if this rule
            # has not yet fired for this user.
            first_key = (admin_id_str, keyword)
            if first_key not in first_seen_set:
                matched = True
        elif not is_media:
            if mode == "match":
                matched = (text_lower == keyword.lower())
            else:  # "contains"
                matched = (keyword.lower() in text_lower)

        if matched:
            logger.info(
                "Business auto-reply triggered: mode=%r keyword=%r (admin=%s) for user=%s chat_id=%s connection=%s",
                mode,
                keyword,
                admin_id,
                message.from_user.id if message.from_user else "?",
                message.chat_id,
                message.business_connection_id,
            )
            try:
                # Resolve $variables in the response template
                from utils.variables import resolve_variables
                resolved = resolve_variables(response, admin_id, message.from_user)

                await context.bot.send_message(
                    chat_id=message.from_user.id,
                    text=resolved,
                    business_connection_id=message.business_connection_id,
                )
                if mode == "first":
                    first_seen_set.add((admin_id_str, keyword))
                logger.info("Business reply sent successfully.")
            except Exception as e:
                logger.error(
                    "Failed to send business reply (chat_id=%s, conn=%s): %s",
                    message.from_user.id if message.from_user else "?",
                    message.business_connection_id,
                    e,
                )
            return

    # No keyword matched — ignore silently in secretary mode
    logger.debug("Ignored business message without matching keywords: %s", text)

