import json
import os
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_IDS
from utils.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = "data"
REPLIES_FILE = os.path.join(DATA_DIR, "autoreplies.json")


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _load_all() -> dict:
    """Load the full autoreplies file (dict keyed by str(admin_id))."""
    try:
        with open(REPLIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        logger.error("autoreplies.json is malformed, resetting.")
        return {}

    # ── Auto-migration: old flat format {"keyword": "reply"} ──────────────
    # Detect by checking whether any top-level value is a string instead of dict.
    if data and any(isinstance(v, str) for v in data.values()):
        logger.warning(
            "Old flat autoreplies.json detected — migrating to per-admin format."
        )
        first_admin = str(ADMIN_IDS[0]) if ADMIN_IDS else "unknown"
        migrated = {first_admin: data}
        _save_all(migrated)
        return migrated

    return data


def _save_all(data: dict) -> None:
    """Persist the full autoreplies dict to disk."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(REPLIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_replies(admin_id: int) -> dict:
    """Return the keyword→response map for a specific admin."""
    return _load_all().get(str(admin_id), {})


def save_replies(admin_id: int, replies: dict) -> None:
    """Save the keyword→response map for a specific admin."""
    data = _load_all()
    data[str(admin_id)] = replies
    _save_all(data)


# ---------------------------------------------------------------------------
# Auto-reply message handler (normal chat messages)
# ---------------------------------------------------------------------------

async def handle_autoreply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check if the incoming text matches any keyword and reply accordingly.

    Checks against the replies of every admin and responds on the first match.
    Falls back to echoing the original message if no keyword matches
    (preserves the previous echo_text behaviour).
    """
    if not update.message or not update.message.text:
        return
    text = update.message.text
    text_lower = text.lower()

    all_data = _load_all()

    for admin_id_str, replies in all_data.items():
        for keyword, response in replies.items():
            if keyword.lower() in text_lower:
                logger.info(
                    "Auto-reply triggered: keyword=%r (admin=%s) for user=%s",
                    keyword,
                    admin_id_str,
                    update.effective_user.id,
                )
                await update.message.reply_text(response)
                return

    # No keyword matched — echo the message (original behaviour)
    await update.message.reply_text(f"You said: {text}")


# ---------------------------------------------------------------------------
# Admin commands
# ---------------------------------------------------------------------------

async def setreply_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/setreply <keyword> # <response> — add or update an auto-reply rule."""
    admin_id = update.effective_user.id
    if admin_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Not authorized.")
        return

    full_args = " ".join(context.args)
    if "#" not in full_args:
        await update.message.reply_text(
            "Usage: /setreply <keyword or phrase> # <response>\n"
            "Example: /setreply Hi, how are you? # Hi! All good! 😊"
        )
        return

    keyword, response = full_args.split("#", 1)
    keyword = keyword.strip().lower()
    response = response.strip()

    if not keyword or not response:
        await update.message.reply_text("❌ You must specify both a keyword and a valid response.")
        return

    replies = load_replies(admin_id)
    action = "updated" if keyword in replies else "added"
    replies[keyword] = response
    save_replies(admin_id, replies)

    logger.info("Auto-reply %s by admin %s: %r → %r", action, admin_id, keyword, response)
    await update.message.reply_text(
        f"✅ Response {action}:\n🔑 `{keyword}` → {response}", parse_mode="Markdown"
    )


async def delreply_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/delreply <keyword> — remove an auto-reply rule."""
    admin_id = update.effective_user.id
    if admin_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Not authorized.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /delreply <keyword or phrase>")
        return

    keyword = " ".join(context.args).lower()
    replies = load_replies(admin_id)

    if keyword not in replies:
        await update.message.reply_text(f"❌ Keyword `{keyword}` not found.", parse_mode="Markdown")
        return

    del replies[keyword]
    save_replies(admin_id, replies)

    logger.info("Auto-reply deleted by admin %s: %r", admin_id, keyword)
    await update.message.reply_text(f"🗑️ Response for `{keyword}` deleted.", parse_mode="Markdown")


async def listreplies_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/listreplies — show your own configured auto-reply rules."""
    admin_id = update.effective_user.id
    if admin_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Not authorized.")
        return

    replies = load_replies(admin_id)

    if not replies:
        await update.message.reply_text("📭 No auto-replies configured.\nUse /setreply to add one.")
        return

    lines = ["📋 *Auto-replies configured:*\n"]
    for keyword, response in replies.items():
        lines.append(f"🔑 `{keyword}`\n↩️ {response}\n")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
