import os
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    InlineQueryHandler,
    PreCheckoutQueryHandler,
    filters, 
    ContextTypes, 
    Application, 
    TypeHandler
)

from config import BOT_TOKEN, ADMIN_IDS
from handlers.basic import (
    start_command, help_command, format_command, album_command, 
    dynamic_file_command, echo_text, handle_media
)
from handlers.conversation import feedback_conv_handler
from handlers.inline import inline_query_handler
from handlers.payment import buy_command, precheckout_callback, successful_payment_callback
from handlers.admin import stats_command, error_handler
from handlers.autoreply import (
    handle_autoreply, setreply_command, delreply_command, listreplies_command
)

from utils.logger import setup_logging, get_logger

# Initialise file + console logging (must happen before any handler imports log)
setup_logging()
logger = get_logger(__name__)

# Ensure data directory exists for saving files
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

async def log_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log every update received from users."""
    if not update:
        return
    
    user = update.effective_user
    if not user:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    operation = "UNKNOWN"
    details = ""
    if update.message:
        if update.message.text:
            operation = "COMMAND" if update.message.text.startswith('/') else "TEXT_MESSAGE"
            details = update.message.text
        elif update.message.photo:
            operation = "PHOTO"
        elif update.message.document:
            operation = "DOCUMENT"
            details = update.message.document.file_name
        elif update.message.location:
            operation = "LOCATION"
        else:
            operation = "MESSAGE"
    elif update.callback_query:
        operation = "CALLBACK_QUERY"
        details = update.callback_query.data
    elif update.inline_query:
        operation = "INLINE_QUERY"
        details = update.inline_query.query
        
    user_info = {
        "id": user.id,
        "is_bot": user.is_bot,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
        "language_code": user.language_code
    }
    
    log_entry = {
        "time": timestamp,
        "operation": operation,
        "details": details,
        "user": user_info
    }
    
    with open(os.path.join(DATA_DIR, "operations_log.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

async def post_init(application: Application):
    """Send a startup message to all admins."""
    for admin_id in ADMIN_IDS:
        try:
            await application.bot.send_message(chat_id=admin_id, text="🚀 Bot started.")
        except Exception as e:
            logger.error(f"Error sending message to {admin_id}: {e}")

async def post_stop(application: Application):
    """Send a shutdown message to all admins."""
    for admin_id in ADMIN_IDS:
        try:
            await application.bot.send_message(chat_id=admin_id, text="🛑 Bot stopped.")
        except Exception as e:
            logger.error(f"Error sending message to {admin_id}: {e}")

# --- JOB QUEUE EXAMPLES ---
async def set_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a job to the queue."""
    chat_id = update.effective_message.chat_id
    try:
        # args[0] should contain the time for the timer in seconds
        due = float(context.args[0])
        if due < 0:
            await update.effective_message.reply_text("You can't go back in time!")
            return

        context.job_queue.run_once(alarm, due, chat_id=chat_id, name=str(chat_id), data=due)
        await update.effective_message.reply_text(f"Timer set! It will ring in {due} seconds.")
    except (IndexError, ValueError):
        await update.effective_message.reply_text("Usage: /timer <seconds>")

async def alarm(context: ContextTypes.DEFAULT_TYPE):
    """Send the alarm message."""
    job = context.job
    await context.bot.send_message(job.chat_id, text=f"Beep! {job.data} seconds have passed!")

# --------------------------

if __name__ == '__main__':
    # Initialize the application
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .post_init(post_init)
        .post_stop(post_stop)
        .build()
    )

    # Register the logging handler first (Group -1 to catch everything before other handlers)
    application.add_handler(TypeHandler(Update, log_update), group=-1)

    # Basic Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("format", format_command))
    application.add_handler(CommandHandler("album", album_command))
    application.add_handler(CommandHandler("dynamic", dynamic_file_command))
    
    # Timer / Job Queue Command
    application.add_handler(CommandHandler("timer", set_timer))
    
    # Admin Commands
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("setreply", setreply_command))
    application.add_handler(CommandHandler("delreply", delreply_command))
    application.add_handler(CommandHandler("listreplies", listreplies_command))

    # Conversation handler (Feedback)
    application.add_handler(feedback_conv_handler)
    
    # Inline Query Handler
    application.add_handler(InlineQueryHandler(inline_query_handler))
    
    # Payment Handlers
    application.add_handler(CommandHandler("buy", buy_command))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    # Media & Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_autoreply))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL | filters.LOCATION, handle_media))

    # Error handler
    application.add_error_handler(error_handler)

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)
