import uuid
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes

async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline queries."""
    query = update.inline_query.query

    if not query:
        return

    # Create a couple of example results based on the query
    results = [
        InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title="Uppercase",
            description=f"Send the text in uppercase",
            input_message_content=InputTextMessageContent(
                message_text=query.upper()
            ),
        ),
        InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title="Bold",
            description=f"Send the text in bold",
            input_message_content=InputTextMessageContent(
                message_text=f"*{query}*",
                parse_mode="MarkdownV2"
            ),
        ),
        InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title="Length",
            description=f"Show the length of the text",
            input_message_content=InputTextMessageContent(
                message_text=f"The text '{query}' is {len(query)} characters long."
            ),
        )
    ]

    await update.inline_query.answer(results)
