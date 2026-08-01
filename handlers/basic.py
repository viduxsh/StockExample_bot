import os
import io
from datetime import datetime
from telegram import Update, InputMediaPhoto, ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

DATA_DIR = "data"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hello {user.mention_html()}! I am an example bot showcasing python-telegram-bot features."
        "\nUse /help to see what I can do.",
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = (
        "<b>Basic Commands:</b>\n"
        "/start - Welcome message\n"
        "/help - Show this message\n"
        "/format - Formatted text example (MarkdownV2)\n"
        "/album - Photo group example (MediaGroup)\n"
        "/dynamic - Generate and send a file on the fly\n"
        "\n<b>Advanced Features:</b>\n"
        "/feedback - Start a multi-step survey\n"
        "/timer &lt;seconds&gt; - Set a timer\n"
        "/buy - Payment example (Stripe Test)\n"
        "\n<b>Other:</b>\n"
        "Try typing @{} in another chat to test Inline Queries!".format(context.bot.username)
    )
    await update.message.reply_html(help_text)

async def format_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show advanced formatting using MarkdownV2."""
    text = (
        "*Bold*\n"
        "_Italic_\n"
        "__Underline__\n"
        "~Strikethrough~\n"
        "||Spoiler|| - Click to read\n"
        "[Inline link](http://www.example.com/)\n"
        "`Inline code`\n"
        "```python\n"
        "print('Python formatted code')\n"
        "```"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)

async def album_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a media group (album of photos)."""
    # Using placeholder images for demonstration
    media = [
        InputMediaPhoto("https://picsum.photos/400/300?random=1", caption="Photo 1"),
        InputMediaPhoto("https://picsum.photos/400/300?random=2"),
        InputMediaPhoto("https://picsum.photos/400/300?random=3"),
    ]
    await update.message.reply_media_group(media=media)

async def dynamic_file_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a file in memory and send it."""
    user = update.effective_user
    content = f"This file was dynamically generated for {user.first_name} at {datetime.now()}."
    
    # Create file in memory
    file_bytes = io.BytesIO(content.encode('utf-8'))
    file_bytes.name = f"report_{user.id}.txt"
    
    await update.message.reply_document(document=file_bytes, caption="Here is your dynamically generated file!")

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

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Echo when media is received."""
    if update.message.photo:
        await update.message.reply_text("Nice photo! I received it.")
    elif update.message.document:
        await update.message.reply_text(f"Document received: {update.message.document.file_name}")
    elif update.message.location:
        await update.message.reply_text("Location received!")
