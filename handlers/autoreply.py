import json
import os
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_IDS
from utils.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = "data"
REPLIES_FILE = os.path.join(DATA_DIR, "autoreplies.json")


def load_replies() -> dict:
    """Load keyword→response map from disk."""
    try:
        with open(REPLIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        logger.error("autoreplies.json is malformed, resetting.")
        return {}


def save_replies(replies: dict) -> None:
    """Persist keyword→response map to disk."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(REPLIES_FILE, "w", encoding="utf-8") as f:
        json.dump(replies, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Auto-reply message handler
# ---------------------------------------------------------------------------

async def handle_autoreply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check if the incoming text matches any keyword and reply accordingly.

    Falls back to echoing the original message if no keyword matches
    (preserves the previous echo_text behaviour).
    """
    text = update.message.text
    if not text:
        return

    replies = load_replies()
    text_lower = text.lower()

    for keyword, response in replies.items():
        if keyword.lower() in text_lower:
            logger.info(
                "Auto-reply triggered: keyword=%r for user=%s",
                keyword,
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
    """/setreply <keyword> <response> — add or update an auto-reply rule."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Non autorizzato.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Uso: /setreply <keyword> <risposta>\n"
            "Esempio: /setreply ciao Ciao! Come posso aiutarti? 😊"
        )
        return

    keyword = context.args[0].lower()
    response = " ".join(context.args[1:])

    replies = load_replies()
    action = "aggiornata" if keyword in replies else "aggiunta"
    replies[keyword] = response
    save_replies(replies)

    logger.info("Auto-reply %s by admin %s: %r → %r", action, update.effective_user.id, keyword, response)
    await update.message.reply_text(f"✅ Risposta {action}:\n🔑 `{keyword}` → {response}", parse_mode="Markdown")


async def delreply_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/delreply <keyword> — remove an auto-reply rule."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Non autorizzato.")
        return

    if not context.args:
        await update.message.reply_text("Uso: /delreply <keyword>")
        return

    keyword = context.args[0].lower()
    replies = load_replies()

    if keyword not in replies:
        await update.message.reply_text(f"❌ Keyword `{keyword}` non trovata.", parse_mode="Markdown")
        return

    del replies[keyword]
    save_replies(replies)

    logger.info("Auto-reply deleted by admin %s: %r", update.effective_user.id, keyword)
    await update.message.reply_text(f"🗑️ Risposta per `{keyword}` eliminata.", parse_mode="Markdown")


async def listreplies_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/listreplies — show all configured auto-reply rules."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Non autorizzato.")
        return

    replies = load_replies()

    if not replies:
        await update.message.reply_text("📭 Nessuna risposta automatica configurata.\nUsa /setreply per aggiungerne una.")
        return

    lines = ["📋 *Risposte automatiche configurate:*\n"]
    for keyword, response in replies.items():
        lines.append(f"🔑 `{keyword}`\n↩️ {response}\n")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
