from telegram import Update, LabeledPrice
from telegram.ext import ContextTypes
from config import PAYMENT_PROVIDER_TOKEN

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send an invoice for a test payment."""
    if not PAYMENT_PROVIDER_TOKEN or PAYMENT_PROVIDER_TOKEN == "your_smart_glocal_token_here":
        await update.message.reply_text(
            "Smart Glocal payment not configured. "
            "Add PAYMENT_PROVIDER_TOKEN to the .env file to test this feature."
        )
        return
        
    chat_id = update.message.chat_id
    title = "Support Donation"
    description = "Buy us a coffee to support the bot development!"
    # Select a payload just for you to recognize its the donation from your bot
    payload = "Custom-Payload-Donation"
    currency = "EUR"
    # price in cents
    price = 150
    prices = [LabeledPrice("Coffee", price * 100)]

    # optionally pass need_name=True, need_phone_number=True,
    # need_email=True, need_shipping_address=True, is_flexible=True
    await context.bot.send_invoice(
        chat_id,
        title,
        description,
        payload,
        PAYMENT_PROVIDER_TOKEN,
        currency,
        prices,
    )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Answers the PreQecheckoutQuery"""
    query = update.pre_checkout_query
    # check the payload, is this from your bot?
    if query.invoice_payload != "Custom-Payload-Donation":
        # answer False pre_checkout_query
        await query.answer(ok=False, error_message="Something went wrong...")
    else:
        await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirms the successful payment."""
    # do something after successfully receiving payment
    await update.message.reply_text("Thank you for your support! We received your coffee. ☕")

