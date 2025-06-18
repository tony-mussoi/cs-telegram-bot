# Tutorial python-telegram-bot:
# https://github.com/python-telegram-bot/python-telegram-bot/wiki/Extensions---Your-first-Bot
# https://core.telegram.org/bots/tutorial
import logging
from telegram import Update
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "7448557069:AAE5OVaRuGOgT8qad7Vq-0y15uc2E2I01WQ"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm Cubo bot, please talk to me!")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=update.message.text)


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I didn't understand that command.")

### MAIN ###
if __name__ == '__main__':
    print("INSIDE MAIN")
    application = ApplicationBuilder().token(TOKEN).build()
    echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), echo)
    #caps_handler = CommandHandler('caps', caps)
    unknown_handler = MessageHandler(filters.COMMAND, unknown)

    start_handler = CommandHandler('start', start)
    print("BOT STARTED")

    application.add_handler(start_handler)
    application.add_handler(echo_handler)
    application.add_handler(unknown_handler)

    application.run_polling()