import html
import json
import os
import time
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_IDS
from utils.logger import get_logger
from utils.variables import resolve_variables, get_vars, set_var, delete_var

logger = get_logger(__name__)

DATA_DIR = "data"
REPLIES_FILE = os.path.join(DATA_DIR, "autoreplies.json")

# Valid reply modes  (``exact`` was renamed to ``match`` — old data still reads as ``exact`` on disk)
MODES = ("contains", "match", "first")
# Alias: "exact" on disk is treated as "match" internally
_ALIAS = {"exact": "match"}


# ---------------------------------------------------------------------------
# Persistence helpers — autoreplies
# ---------------------------------------------------------------------------

def _load_all() -> dict:
    """Load the autoreplies file into the internal format:
        { "admin_id": { "keyword": {"response": "...", "mode": "..."} } }

    Auto-migrates from previous JSON structures on disk.
    """
    try:
        with open(REPLIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

    needs_save = False
    internal_data = {}

    # Auto-migration: very old flat format {keyword: "reply_str"}
    if data and any(isinstance(v, str) for v in data.values()):
        logger.warning("Old flat autoreplies.json detected — migrating to per-admin format.")
        first_admin = str(ADMIN_IDS[0]) if ADMIN_IDS else "unknown"
        migrated_rules = {k: {"response": v, "mode": "contains"} for k, v in data.items()}
        internal_data = {first_admin: migrated_rules}
        _save_all(internal_data)
        return internal_data

    # Parse JSON which could be Format 2, Format 3, or Format 4 (newest)
    for admin_id_str, rules_or_modes in data.items():
        internal_data[admin_id_str] = {}
        for key, value in rules_or_modes.items():
            if isinstance(value, str):
                # Format 2: {admin: {keyword: "reply"}}
                internal_data[admin_id_str][key] = {"response": value, "mode": "contains"}
                needs_save = True
            elif isinstance(value, dict):
                if "response" in value and "mode" in value:
                    # Format 3: {admin: {keyword: {"response": "...", "mode": "..."}}}
                    mode = _ALIAS.get(value["mode"], value["mode"])
                    internal_data[admin_id_str][key] = {"response": value["response"], "mode": mode}
                    needs_save = True
                elif key in MODES or key in _ALIAS:
                    # Format 4 (New): {admin: {mode: {keyword: "response"}}}
                    mode = _ALIAS.get(key, key)
                    for keyword, response in value.items():
                        internal_data[admin_id_str][keyword] = {"response": response, "mode": mode}

    if needs_save:
        _save_all(internal_data)

    return internal_data


def _save_all(internal_data: dict) -> None:
    """Persist the autoreplies dict to disk in the grouped format:
       { "admin_id": { "mode": { "keyword": "response" } } }
    """
    os.makedirs(DATA_DIR, exist_ok=True)

    out_data = {}
    for admin_id_str, rules in internal_data.items():
        out_data[admin_id_str] = {"contains": {}, "match": {}, "first": {}}
        for keyword, rule in rules.items():
            mode = rule.get("mode", "contains")
            # Normalise legacy "exact" to "match" on write
            mode = _ALIAS.get(mode, mode)
            response = rule.get("response", "")
            if mode not in out_data[admin_id_str]:
                out_data[admin_id_str][mode] = {}
            out_data[admin_id_str][mode][keyword] = response

        # Remove empty modes for a cleaner JSON file
        for mode in list(out_data[admin_id_str].keys()):
            if not out_data[admin_id_str][mode]:
                del out_data[admin_id_str][mode]

    with open(REPLIES_FILE, "w", encoding="utf-8") as f:
        json.dump(out_data, f, ensure_ascii=False, indent=2)


def load_replies(admin_id: int) -> dict:
    """Return the keyword->rule map for a specific admin."""
    return _load_all().get(str(admin_id), {})


def save_replies(admin_id: int, replies: dict) -> None:
    """Save the keyword->rule map for a specific admin."""
    data = _load_all()
    data[str(admin_id)] = replies
    _save_all(data)


# ---------------------------------------------------------------------------
# Auto-reply message handler (normal chat messages)
# ---------------------------------------------------------------------------

async def handle_autoreply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check if the incoming text matches any rule and reply accordingly.

    Modes:
      - "first"    -> reply only to the very first message ever from this user (works on text and media)
      - "match"    -> reply only if the message matches the keyword exactly (requires text)
      - "contains" -> reply if the keyword is found anywhere in the message (default, requires text)

    Responses support $variable placeholders:
      Built-in: $first_name, $last_name, $username, $full_name, $id, $language
      Custom:   any variable set by the admin via /setvar
      Missing fields resolve to empty string (no errors).
    """
    if not update.message:
        return

    # Text can be empty for media/stickers.
    text = update.message.text or update.message.caption or ""
    text_lower = text.lower().strip()
    user = update.effective_user
    user_id = user.id

    # is_media = True for stickers, photos without caption, etc. (no usable text)
    is_media = not (update.message.text or update.message.caption)

    all_data = _load_all()

    # -- 24h inactivity timeout for "first" rule --
    now = time.time()
    last_interaction = context.user_data.get("last_interaction_time", 0)
    if now - last_interaction > 86400:  # 24 hours
        context.user_data["first_reply_seen"] = set()
    context.user_data["last_interaction_time"] = now

    first_seen_set: set = context.user_data.setdefault("first_reply_seen", set())
    rule_matched = False

    for admin_id_str, rules in all_data.items():
        try:
            admin_id_int = int(admin_id_str)
        except ValueError:
            admin_id_int = 0

        for keyword, rule in rules.items():
            response = rule.get("response", "")
            mode = rule.get("mode", "contains")

            matched = False

            if mode == "first":
                # Trigger on ANY message (including stickers) if this specific rule
                # has not fired yet for this user. Key = (admin_id, keyword) so that
                # multiple "first" rules per admin are each tracked independently.
                first_key = (admin_id_str, keyword)
                if first_key not in first_seen_set:
                    matched = True
            elif not is_media:  # match and contains modes require text
                if mode == "match":
                    matched = (text_lower == keyword.lower())
                else:  # "contains"
                    matched = (keyword.lower() in text_lower)

            if matched:
                logger.info(
                    "Auto-reply triggered: mode=%r keyword=%r (admin=%s) for user=%s",
                    mode, keyword, admin_id_str, user_id,
                )
                if mode == "first":
                    first_seen_set.add((admin_id_str, keyword))

                # Resolve $variables in the response template
                resolved = resolve_variables(response, admin_id_int, user)

                await update.message.reply_text(resolved)
                rule_matched = True
                break

        if rule_matched:
            break

    if not rule_matched and not is_media:
        # Fallback to echoing if it is a text message and no rule matched
        await update.message.reply_text(f"You said: {text}")


# ---------------------------------------------------------------------------
# Admin commands — auto-replies
# ---------------------------------------------------------------------------

async def setreply_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/setreply <keyword> # <response> [# <mode>] — add or update an auto-reply rule.

    Responses may contain $variables:
      Built-in: $first_name, $last_name, $username, $full_name, $id, $language
      Custom:   anything set via /setvar
    """
    admin_id = update.effective_user.id
    if admin_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Not authorized.")
        return

    full_args = " ".join(context.args)
    if "#" not in full_args:
        await update.message.reply_text(
            "Usage: /setreply <keyword> # <response> [# <mode>]\n\n"
            "*Modes:*\n"
            "  • `contains` — reply if keyword is in message _(default)_\n"
            "  • `match`    — reply only on exact match\n"
            "  • `first`    — reply only to the user's first message ever\n\n"
            "*Variable placeholders in response:*\n"
            "  `$first_name`, `$last_name`, `$username`, `$full_name`, `$id`, `$language`\n"
            "  + any variable defined with /setvar\n"
            "  Empty fields silently become empty strings.\n\n"
            "*Examples:*\n"
            "  /setreply hi # Hi $first_name! 👋\n"
            "  /setreply hi # Hi $username! 👋 # contains\n"
            "  /setreply hi # Hi $username! 👋 # match\n"
            "  /setreply ignored # Welcome $full_name! 🎉 # first",
            parse_mode="Markdown",
        )
        return

    parts = [p.strip() for p in full_args.split("#")]
    keyword = parts[0].strip().lower()
    response = parts[1].strip() if len(parts) > 1 else ""
    mode_raw = parts[2].strip().lower() if len(parts) > 2 else "contains"

    # Accept "exact" as legacy alias for "match"
    mode_raw = _ALIAS.get(mode_raw, mode_raw)

    if mode_raw not in MODES:
        await update.message.reply_text(
            f"❌ Unknown mode `{mode_raw}`. Valid modes: `contains`, `match`, `first`.",
            parse_mode="Markdown",
        )
        return

    if not keyword or not response:
        await update.message.reply_text("❌ You must specify both a keyword and a valid response.")
        return

    replies = load_replies(admin_id)
    action = "updated" if keyword in replies else "added"
    replies[keyword] = {"response": response, "mode": mode_raw}
    save_replies(admin_id, replies)

    mode_emoji = {"contains": "🔍", "match": "🎯", "first": "👋"}.get(mode_raw, "")
    logger.info("Auto-reply %s by admin %s: %r -> %r (mode=%s)", action, admin_id, keyword, response, mode_raw)
    await update.message.reply_text(
        f"✅ Response {action}:\n"
        f"🔑 <code>{html.escape(keyword)}</code>\n"
        f"↩️ {html.escape(response)}\n"
        f"{mode_emoji} Mode: <code>{mode_raw}</code>",
        parse_mode="HTML",
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

    mode_titles = {
        "first":    "👋 First messages (First)",
        "match":    "🎯 Exact match (Match)",
        "contains": "🔍 Keyword contained (Contains)",
    }

    grouped = {"first": [], "match": [], "contains": [], "other": []}
    for keyword, rule in replies.items():
        mode = rule.get("mode", "contains")
        response = rule.get("response", "?")
        if mode in grouped:
            grouped[mode].append((keyword, response))
        else:
            grouped["other"].append((keyword, response, mode))

    lines = ["📋 <b>Auto-replies configured:</b>"]

    for mode in ["first", "match", "contains"]:
        if grouped[mode]:
            lines.append(f"\n<b>{mode_titles[mode]}</b>")
            for keyword, response in grouped[mode]:
                lines.append(f"  🔑 <code>{html.escape(keyword)}</code>")
                lines.append(f"  ↩️ {html.escape(response)}")

    if grouped["other"]:
        lines.append("\n❓ <b>Other modes</b>")
        for keyword, response, mode in grouped["other"]:
            lines.append(
                f"  🔑 <code>{html.escape(keyword)}</code>\n"
                f"  ↩️ {html.escape(response)}\n"
                f"  Mode: <code>{mode}</code>"
            )

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


# ---------------------------------------------------------------------------
# Admin commands — custom variables
# ---------------------------------------------------------------------------

async def setvar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/setvar <name> <value> — define a custom variable usable in auto-reply templates."""
    admin_id = update.effective_user.id
    if admin_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Not authorized.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /setvar <name> <value>\n\n"
            "Example: /setvar shop_name My Store\n"
            "Then use `$shop_name` in any auto-reply response.",
            parse_mode="Markdown",
        )
        return

    name = context.args[0].lower()
    value = " ".join(context.args[1:])

    # Disallow names that clash with built-in variables
    _BUILTIN = {"first_name", "last_name", "username", "full_name", "id", "language"}
    if name in _BUILTIN:
        await update.message.reply_text(
            f"❌ `${name}` is a built-in variable and cannot be overridden.\n"
            f"Built-in variables: {', '.join(f'`${v}`' for v in sorted(_BUILTIN))}",
            parse_mode="Markdown",
        )
        return

    existing = get_vars(admin_id)
    action = "updated" if name in existing else "created"
    set_var(admin_id, name, value)

    await update.message.reply_text(
        f"✅ Variable {action}:\n`${name}` = `{value}`",
        parse_mode="Markdown",
    )


async def listvar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/listvar — list all custom variables defined by this admin."""
    admin_id = update.effective_user.id
    if admin_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Not authorized.")
        return

    custom_vars = get_vars(admin_id)

    lines = ["📦 *Custom variables:*\n"]
    if custom_vars:
        for name, value in sorted(custom_vars.items()):
            lines.append(f"  `${name}` = `{value}`")
    else:
        lines.append("  _(no variables defined)_")

    lines.append(
        "\n📌 *Built-in variables (always available):*\n"
        "  `$first_name`, `$last_name`, `$username`\n"
        "  `$full_name`, `$id`, `$language`"
    )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def deletevar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/deletevar <name> — remove a custom variable."""
    admin_id = update.effective_user.id
    if admin_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Not authorized.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /deletevar <name>")
        return

    name = context.args[0].lower()
    deleted = delete_var(admin_id, name)

    if deleted:
        await update.message.reply_text(f"🗑️ Variable `${name}` deleted.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Variable `${name}` not found.", parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Admin commands — first-reply state management
# ---------------------------------------------------------------------------

async def resetfirst_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/resetfirst — reset the 'first message seen' state for a user so 'first' rules fire again.

    Resets both the normal bot chat state and the business/secretary chat state.

    Usage:
      /resetfirst              — reset YOUR OWN first-seen state (for testing)
      /resetfirst <user_id>    — reset a specific user's first-seen state
    """
    caller_id = update.effective_user.id
    if caller_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Not authorized.")
        return

    def _reset(user_data: dict) -> list:
        """Clear both first-seen keys and return which ones were cleared."""
        cleared = []
        for key in ("first_reply_seen", "business_first_reply_seen"):
            if key in user_data:
                user_data[key] = set()
                cleared.append(key)
            else:
                user_data[key] = set()  # create it so next message works
                cleared.append(key)
        return cleared

    if context.args:
        try:
            target_user_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID. Usage: /resetfirst [user_id]")
            return

        app = context.application
        target_data = app.user_data.get(target_user_id, {})
        if not target_data:
            # initialise empty entry
            app.user_data[target_user_id] = {}
            target_data = app.user_data[target_user_id]
        _reset(target_data)
        await update.message.reply_text(
            f"✅ First-seen state reset for user `{target_user_id}`.\n"
            "Both bot-chat and business-chat states cleared.",
            parse_mode="Markdown",
        )
    else:
        _reset(context.user_data)
        await update.message.reply_text(
            "✅ Your first-seen state has been reset (bot chat + business chat).\n"
            "The next message you send will trigger 'first' rules again."
        )
