# Tutorial python-telegram-bot:
# https://github.com/python-telegram-bot/python-telegram-bot/wiki/Extensions---Your-first-Bot
# https://core.telegram.org/bots/tutorial
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import telegram
print(telegram.__version__)
#help(Application.run_webhook)


# Load your bot token and webhook URL (set by ngrok)
TELEGRAM_APP_TOKEN = os.environ["TELEGRAM_APP_TOKEN"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]  # e.g., https://abc123.ngrok-free.app
PORT = int(os.environ.get("PORT", 5000))


# --- Telegram Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(">>> HANDLER: /start")
    await update.message.reply_text("Hi, I'm Cubo bot!")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(">>> HANDLER: echo")
    await update.message.reply_text(f"You said: {update.message.text}")


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(">>> HANDLER: unknown")
    await update.message.reply_text("Sorry, I didn't understand that command.")


# ✅ 1. Application setup
# --- App setup ---
def main():
    application = Application.builder().token(TELEGRAM_APP_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))

    print(f">> Starting webhook at: {WEBHOOK_URL}/webhook")

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=f"{WEBHOOK_URL}/webhook"
    )

if __name__ == "__main__":
    main()