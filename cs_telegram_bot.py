from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters)
from cs_chatbot_lib import *

# Setup Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- Environment Variables ---
TELEGRAM_APP_TOKEN = os.environ.get("TELEGRAM_APP_TOKEN")
WEBHOOK_URL = os.environ["WEBHOOK_URL"]  # e.g., https://abc123.ngrok-free.app
PORT = int(os.environ.get("PORT", 5000))
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
MONITORING_CHAT_ID = int(os.environ.get("MONITORING_CHAT_ID"))
AIRTABLE_CRM_OPS_BASE_ID = os.environ.get('AIRTABLE_CRM_OPS_BASE_ID')

# --- Load User Sessions ---
user_sessions = fetch_client_bots(AIRTABLE_CRM_OPS_BASE_ID, 'Bots')

# --- Shared Options ---
theme_options = ['Corporate', 'Tax']
corp_data_fields = ['Company type', 'Company Legal Name', 'Incorporation Country']
tax_data_fields = ['EIN', 'Tax Country', 'Tax forms']

# Parse bot user selected options
def parse_option_selection(s):
    s = s.strip()
    return int(s) if s.isdigit() and 0 <= int(s) <= 9 else 0

# Control Bot workflow, and handle data requests
def run_flow_control(session, incoming_msg):
    base_id = AIRTABLE_CRM_OPS_BASE_ID
    string, file_url = None, None

    if not session.get('authorized'):
        string = "You're not authorized yet. Please wait for approval."
        return string, None

    if session['stage'] == 'initial_stage':
        company_list = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(session["companies"]))
        session['stage'] = 'awaiting_company_selection'
        string = f"Hello {session['clients']}! Please select the company:\n{company_list}".\
            replace('[', '').replace(']', '')

    elif session['stage'] == 'awaiting_company_selection':
        sel = parse_option_selection(incoming_msg)
        if sel == 0:
            session['stage'] = 'awaiting_company_selection'
        elif sel <= len(session['companies']):
            session['selected_company'] = session['companies'][sel - 1]
            session['stage'] = 'awaiting_theme_selection'
            string = f"Which data segment are you looking for {session['selected_company']}?\n" + \
                     "\n".join(f"{i + 1}. {t}" for i, t in enumerate(theme_options)) + "\n0. to select another Company"
        else:
            string = "Invalid selection."

    elif session['stage'] == 'awaiting_theme_selection':
        sel = parse_option_selection(incoming_msg)
        if sel == 0:
            session['stage'] = 'awaiting_company_selection'
        elif sel <= len(theme_options):
            session['selected_theme'] = theme_options[sel - 1]
            session['stage'] = 'awaiting_data_request'
            if session['selected_theme'] == 'Corporate':
                string = f"Which Corporate data are you looking for '{session['selected_company']}'?\n" + \
                    "\n".join(f"{i+1}. {f}" for i, f in enumerate(corp_data_fields)) + "\n0. to select another Company"
            else:
                string = f"Which Tax data are you looking for '{session['selected_company']}'?\n" + \
                    "\n".join(f"{i+1}. {f}" for i, f in enumerate(tax_data_fields)) + "\n0. to select another Company"
        else:
            string = "Invalid selection."

    elif session['stage'] == 'awaiting_data_request':
        sel = parse_option_selection(incoming_msg)
        company_name = session['selected_company']
        theme = session['selected_theme']
        company_id = find_record_id_by_value(base_id, 'Companies', 'Company', company_name)
        company_dict = get_airtable_record(base_id, 'Companies', company_id)
        fields = {k.lower(): v for k, v in company_dict.get('fields', {}).items()}

        if sel == 0:
            session['stage'] = 'awaiting_company_selection'
            company_list = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(session['companies']))
            string = f"Hello {session['client_name']}! Please select the company:\n{company_list}"

        elif theme == 'Corporate' and sel <= len(corp_data_fields):
            lookup = corp_data_fields[sel - 1].lower()
            value = fields.get(lookup)
            string = f"{corp_data_fields[sel - 1]}: {value}"

        elif theme == 'Tax':
            if sel == 1:
                value_1 = fields.get('tax id type')
                value_2 = fields.get('tax id number')
                string = f"Tax ID type: {value_1}  -  Number: {value_2}"
                file_url = get_file_url_from_airtable(base_id, 'Companies', company_name + ' - EIN.pdf')
            elif sel <= len(tax_data_fields):
                lookup = tax_data_fields[sel - 1].lower()
                value = fields.get(lookup)
                string = f"{tax_data_fields[sel - 1]}: {value}"
            else:
                string = "Invalid selection."

    return string, file_url

# --- Telegram Handlers ---
# Handle general messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    session = user_sessions.get(user_id)
    incoming_msg = update.message.text.strip()

    if not user_sessions or session['stage'] == 'auth_awaiting_start':
        await update.message.reply_text("You're not authorized yet. Please type command '/start'.")
        return

    if session['stage'] == 'auth_awaiting_name':
        session['client_name'] = incoming_msg
        session['stage'] = 'auth_awaiting_phone'
        button = KeyboardButton("\ud83d\udcf1 Share my phone number", request_contact=True)
        keyboard = ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Thank you, now tap the keyboard icon at the bottom right "
                                        "to share your phone number.", reply_markup=keyboard)
        return

    if session['stage'] == 'auth_awaiting_phone':
        await update.message.reply_text("Please tap the keyboard icon at the bottom right to send your phone number.")
        return

    session = is_user_authorized(AIRTABLE_CRM_OPS_BASE_ID, "Bots", user_id, session)
    if not session.get('authorized'):
        await update.message.reply_text("You're not authorized yet. Please wait while we review your access.")
        return

    # Handle message, retrieving required data, and manage current workflow
    string, file_url = run_flow_control(session, incoming_msg)
    if string:
        await update.message.reply_text(string)
    if file_url:
        await update.message.reply_document(file_url)

    # Log messages to monitoring Chat
    if MONITORING_CHAT_ID:
        await context.bot.send_message(chat_id=MONITORING_CHAT_ID,
                                text=f"From: {user_id}\n" f"Msg: '{incoming_msg}'\n" f"Stage: {session.get('stage')}")
        await context.bot.send_message(chat_id=MONITORING_CHAT_ID, text=f"Bot replied to `{user_id}`:\n{string}",)
    return

# Handle phone number, from contact message
async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    session = user_sessions.get(user_id)
    if session['stage'] == 'auth_awaiting_start':
        await update.message.reply_text("You're not authorized yet. Please type command '/start'.")
        return
    # Initialize Chatbot user session
    phone = update.message.contact.phone_number
    request_name = update.effective_user.first_name + " " + update.effective_user.last_name
    session['phone'] = phone
    session['authorized'] = False
    session['stage'] = 'auth_awaiting_authorization'
    request_client = session.get('client_name', '')

    # Add user to table Bots @ Airtable, if it does not exist, and wait for manual authorization
    add_bot_user(AIRTABLE_CRM_OPS_BASE_ID, "Bots", phone, user_id, request_name, request_client)
    await update.message.reply_text("Thank you! Please wait while we review your access request.")
    if ADMIN_CHAT_ID:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID,
            text=f"*New user waiting authorization:*\n👤 {request_name} @ {request_client}\n📞 {phone}\n🆔 {user_id}",
                                       parse_mode="Markdown")
    return

# Handle '/start' command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global user_sessions
    user_id = str(update.effective_user.id)
    # Check for existing Chatbot user session
    if (not user_sessions) or (not user_sessions.get(user_id)):
        # Add user session; stage = 'auth_awaiting_start'
        user_sessions = add_new_session(user_sessions, user_id)

    # Initialize in-memory Session
    session = user_sessions.get(user_id)
    session = is_user_authorized(AIRTABLE_CRM_OPS_BASE_ID, "Bots", user_id, session)
    if session['stage'] == 'auth_awaiting_authorization':
        await update.message.reply_text("Your request is already under review. You´ll be notified when completed.")
    else:
        await update.message.reply_text("Welcome to Cubo Bot! Please type your Client or Company name:")
        session['stage'] = 'auth_awaiting_name'
    return

# Handle '/reset_bot' command
async def reset_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global user_sessions
    user_id = str(update.effective_user.id)
    if user_id == ADMIN_CHAT_ID:
        user_sessions = fetch_client_bots(AIRTABLE_CRM_OPS_BASE_ID, 'Bots')
    return

######## MAIN ########
if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_APP_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('reset_bot', reset_bot))
    application.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.run_webhook(listen='0.0.0.0', port=PORT, url_path='webhook', webhook_url=f'{WEBHOOK_URL}/webhook')
###### END MAIN ######

### Auxiliary Handlers
#import telegram
#print(telegram.__version__)
#help(Application.run_webhook)

#async def debug_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
#    await update.message.reply_text(f"Chat ID: {update.effective_chat.id}")

#async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
#    await update.message.reply_text(f"Your Telegram user ID is: {update.effective_user.id}")

# application.add_handler(CommandHandler("chatid", debug_chat_id))
# application.add_error_handler(error_handler)


"""
#from telegram.error import TelegramError
# Handle bot errors
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.error(msg="Exception while handling an update:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ An internal error occurred. The admins have been notified.",
            )
        except TelegramError as e:
            logging.error(f"Failed to send error message to user: {e}")
"""
