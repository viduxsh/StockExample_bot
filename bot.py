import os
import json
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, Application, TypeHandler
from config import BOT_TOKEN, ADMIN_IDS

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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
    
    # Determine the type of operation
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
            await application.bot.send_message(chat_id=admin_id, text="🚀 Il bot si è avviato.")
        except Exception as e:
            logger.error(f"Errore nell'invio del messaggio di avvio a {admin_id}: {e}")

async def post_stop(application: Application):
    """Send a shutdown message to all admins."""
    for admin_id in ADMIN_IDS:
        try:
            await application.bot.send_message(chat_id=admin_id, text="🛑 Il bot si è spento.")
        except Exception as e:
            logger.error(f"Errore nell'invio del messaggio di spegnimento a {admin_id}: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! I'm an example bot showcasing the python-telegram-bot features. "
        "Try /help to see what I can do.",
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = (
        "/start - Welcome message\n"
        "/keyboard - Show a custom reply keyboard\n"
        "/inline - Show an inline keyboard\n"
        "Send any text - Echo the text\n"
        "Send a photo, document, location - React to media"
    )
    await update.message.reply_text(help_text)

async def keyboard_example(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show a custom reply keyboard."""
    reply_keyboard = [['Option 1', 'Option 2'], ['Remove Keyboard']]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text('Please choose an option:', reply_markup=markup)

async def inline_example(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show an inline keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("Option A", callback_data='A'),
            InlineKeyboardButton("Option B", callback_data='B'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Please choose:', reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    await query.answer() # Required to stop the loading animation on the button
    await query.edit_message_text(text=f"Selected option: {query.data}")

async def echo_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Echo the user message (only text) and save it."""
    text = update.message.text
    user = update.effective_user
    
    # Save message to file
    with open(os.path.join(DATA_DIR, "messages.txt"), "a", encoding="utf-8") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] {user.username or user.first_name}: {text}\n")

    if text == 'Remove Keyboard':
        await update.message.reply_text('Keyboard removed.', reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text(f"You said: {text}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Echo when a photo is received."""
    await update.message.reply_text("Nice photo! I received it.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Echo when a document is received."""
    await update.message.reply_text(f"Document received: {update.message.document.file_name}")

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Echo when location is received."""
    await update.message.reply_text("Location received!")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log the error."""
    logger.error("Exception while handling an update:", exc_info=context.error)

if __name__ == '__main__':
    # Initialize the application
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_stop(post_stop)
        .build()
    )

    # Register the logging handler first (Group -1 to catch everything before other handlers)
    application.add_handler(TypeHandler(Update, log_update), group=-1)

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("keyboard", keyboard_example))
    application.add_handler(CommandHandler("inline", inline_example))

    # Callback Query handler (for inline buttons)
    application.add_handler(CallbackQueryHandler(button_callback))

    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))

    # Error handler
    application.add_error_handler(error_handler)

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)
