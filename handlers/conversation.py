from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes
)

# States for the conversation
RATING, FEEDBACK = range(2)

async def feedback_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the feedback conversation."""
    reply_keyboard = [['1', '2', '3', '4', '5']]
    
    await update.message.reply_text(
        "Hello! Would you like to leave some feedback about the bot?\n"
        "You can cancel at any time by typing /cancel.\n\n"
        "From 1 to 5, how do you rate your experience?",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
    )
    return RATING

async def feedback_rating(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the rating and asks for text feedback."""
    user = update.effective_user
    context.user_data['rating'] = update.message.text
    
    await update.message.reply_text(
        f"Thank you {user.first_name}! You selected {update.message.text}.\n"
        "Now, please write a short free-text comment about your experience:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return FEEDBACK

async def feedback_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the text feedback and ends the conversation."""
    user = update.effective_user
    feedback_text = update.message.text
    rating = context.user_data.get('rating')
    
    # In a real app, you would save this to a database
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Feedback from {user.id} ({user.first_name}): Rating={rating}, Comment={feedback_text}")
    
    await update.message.reply_text(
        "Thank you for your valuable feedback! We have recorded it successfully."
    )
    
    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END

async def feedback_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text(
        "You cancelled the feedback submission. See you next time!",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

# Export the ConversationHandler
feedback_conv_handler = ConversationHandler(
    entry_points=[CommandHandler('feedback', feedback_start)],
    states={
        RATING: [MessageHandler(filters.Regex('^(1|2|3|4|5)$'), feedback_rating)],
        FEEDBACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, feedback_text)],
    },
    fallbacks=[CommandHandler('cancel', feedback_cancel)],
)
