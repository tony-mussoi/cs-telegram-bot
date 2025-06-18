import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from whatsapp_lib import *
#import telegram
#print(telegram.__version__)
#help(Application.run_webhook)

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Load Telegram app Token, Webhook URL, and Airtable Base ID
TELEGRAM_APP_TOKEN = os.environ["TELEGRAM_APP_TOKEN"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]  # e.g., https://abc123.ngrok-free.app
PORT = int(os.environ.get("PORT", 5000))
BASE_ID = os.environ.get('AIRTABLE_CRM_OPS_BASE_ID')

# ✅ Setup variables for Webhook flow control
# User selection lists
theme_options = ['Corporate', 'Tax']
corp_data_fields = ['Company type','Company Legal Name', 'Incorporation Country']
tax_data_fields = ['EIN','Tax Country', 'Tax forms']

# Lists for display
theme_options_list = "\n".join(f"{i + 1}. {company}" for i, company in enumerate(theme_options))
corp_data_fields_list = "\n".join(f"{i + 1}. {company}" for i, company in enumerate(corp_data_fields))
tax_data_fields_list = "\n".join(f"{i + 1}. {company}" for i, company in enumerate(tax_data_fields))

# Standard message strings
noloco_link = "\n\nFor full access, login to:\n https://cubostart-crm-portal.noloco.co/"
hello_string = "Hello \'{}\'! Please, select the company:\n{}" + noloco_link
invalid_string = "Sorry, invalid selection."

# Initiate User sessions
# States: 'awaiting_client_name', 'awaiting_company_name', 'awaiting_theme_selection', 'awaiting_data_request'
user_sessions = fetch_client_bots(BASE_ID, 'Bots')
telegram_sessions = {}  # memory session: telegram_id -> session


# Get Client´s session from phone number originating the Whatsapp message
def get_session_from_phone(client_number):
    for session in user_sessions.values():
        if session.get('client_phone') == client_number:
            return session
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in telegram_sessions:
        del telegram_sessions[user_id]
    await update.message.reply_text("Session reset. Please type anything to begin again.")


# Parse message when a selection list is presented for the user
def parse_option_selection(s):
    s = s.strip()
    return int(s) if s in {str(i) for i in range(10)} else 0


# ✅ Setup general Telegram Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in telegram_sessions:
        del telegram_sessions[user_id]
    await update.message.reply_text("Session reset. Please type anything to begin again.")


# ✅ Setup Telegram main Message Handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    incoming_msg = update.message.text.strip()
    session = telegram_sessions.get(user_id)

    if not session:
        for s in user_sessions.values():
            if s.get("telegram_user_id") == user_id:
                session = s.copy()
                break
        if not session:
            await update.message.reply_text("Sorry, we couldn't find your user in our system.")
            return
        session['stage'] = 'initial_stage'
        telegram_sessions[user_id] = session

    company_list = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(session['companies']))
    string = ""
    file_url = None

    stage = session['stage']
    msg = incoming_msg.lower()

    if stage == 'initial_stage':
        session['stage'] = 'awaiting_company_selection'
        string = f"Hello {session['client_name']}! Please, select the company:\n{company_list}" + noloco_link

    elif stage == 'awaiting_company_selection':
        sel = parse_option_selection(msg)
        if sel == 0:
            string = f"Please, select the company:\n{company_list}" + noloco_link
        elif sel <= len(session['companies']):
            session['selected_company'] = session['companies'][sel - 1]
            session['stage'] = 'awaiting_theme_selection'
            string = f"Which data segment are you looking for in {session['selected_company']}?\n{theme_options_list}\n0. to select another Company"
        else:
            string = invalid_string

    elif stage == 'awaiting_theme_selection':
        sel = parse_option_selection(msg)
        if sel == 0:
            session['stage'] = 'awaiting_company_selection'
            string = f"Please, select the company:\n{company_list}" + noloco_link
        elif sel <= len(theme_options):
            session['selected_theme'] = theme_options[sel - 1]
            session['stage'] = 'awaiting_data_request'
            field_list = corp_data_fields_list if session['selected_theme'] == 'Corporate' else tax_data_fields_list
            string = f"Which {session['selected_theme']} data are you looking for '{session['selected_company']}'?\n{field_list}\n0. to select another Company"
        else:
            string = invalid_string

    elif stage == 'awaiting_data_request':
        sel = parse_option_selection(msg)
        company_name = session['selected_company']
        theme = session['selected_theme']
        company_id = find_record_id_by_value(BASE_ID, 'Companies', 'Company', company_name)
        company_dict = get_airtable_record(BASE_ID, 'Companies', company_id)
        fields = {k.lower(): v for k, v in company_dict.get('fields', {}).items()}

        if sel == 0:
            session['stage'] = 'awaiting_company_selection'
            string = f"Please, select the company:\n{company_list}" + noloco_link
        elif theme == 'Corporate' and sel <= len(corp_data_fields):
            field = corp_data_fields[sel - 1].lower()
            value = fields.get(field, 'Not available')
            string = f"{corp_data_fields[sel - 1]}: {value}"
        elif theme == 'Tax' and sel <= len(tax_data_fields):
            if sel == 1:
                t1 = fields.get('tax id type', 'N/A')
                t2 = fields.get('tax id number', 'N/A')
                string = f"Tax ID type: {t1}  -  Number: {t2}"
                file_url = get_file_url_from_airtable(BASE_ID, 'Companies', company_name + ' - EIN.pdf')
            else:
                field = tax_data_fields[sel - 1].lower()
                value = fields.get(field, 'Not available')
                string = f"{tax_data_fields[sel - 1]}: {value}"
        else:
            string = invalid_string

    else:
        string = "Sorry, I’m not sure what to do. Type /start to reset."

    await update.message.reply_text(string)
    if file_url:
        await update.message.reply_document(document=file_url)
    return


# ✅ Application setup
def main():
    application = Application.builder().token(TELEGRAM_APP_TOKEN).build()
    # Application Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print(f">> Starting webhook at: {WEBHOOK_URL}/webhook")
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=f"{WEBHOOK_URL}/webhook"
    )


if __name__ == "__main__":
    main()