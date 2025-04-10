import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from whatsapp_lib import *

# NGROK setup:
# start NGROK: ngrok http http://localhost:8080
# forwarding Twilio: https://<check URL after launching NGROK and setting up Webhook @ Twilio>

app = Flask(__name__)
base_id = os.environ.get('AIRTABLE_CRM_OPS_BASE_ID')
# User selection lists
selection_options = {'1', '2', '3', '4', '5', '6', '7', '8', '9'}
theme_options = ['Corporate', 'Tax']
theme_options_list = "\n".join(f"{i + 1}. {company}" for i, company in enumerate(theme_options))
corp_data_fields = ['Company type','Company Legal Name', 'Incorporation Country']
corp_data_fields_list = "\n".join(f"{i + 1}. {company}" for i, company in enumerate(corp_data_fields))
tax_data_fields = ['EIN','Tax Country', 'Tax forms']
tax_data_fields_list = "\n".join(f"{i + 1}. {company}" for i, company in enumerate(tax_data_fields))
# Standard message strings
noloco_link = "\n\nFor full access, login to:\n https://cubostart-crm-portal.noloco.co/"
hello_string = "Hello \'{}\'! Please, select the company:\n{}" + noloco_link
invalid_string = "Sorry, invalid selection."

# Initiate User sessions
# States: 'awaiting_client_name', 'awaiting_company_name', 'awaiting_theme_selection', 'awaiting_data_request'
user_sessions = fetch_client_bots(base_id, 'Bots')


# Get Client´s session from phone number originating the Whatsapp message
def get_session_from_phone(client_number):
    for session in user_sessions.values():
        if session.get('client_phone') == client_number:
            return session
    return None


# Parse Whatsapp message when a selection list is presented for the user
def parse_option_selection(s):
    s = s.strip()
    return int(s) if s in {'1', '2', '3', '4', '5', '6', '7', '8', '9'} else 0


# Webhook to reply Whatsapp incoming message
@app.route("/", methods=['GET', 'POST'])
def whatsapp_reply():
    incoming_msg = request.form.get('Body', '').strip().lower()
    print(f"Incoming message: {incoming_msg}")
    client_phone = request.form.get('From', '').replace('whatsapp:', '')
    session = get_session_from_phone(client_phone)
    company_list = "\n".join(f"{i + 1}. {company}" for i, company in enumerate(session['companies']))
    print(f"Session: {session}")
    response = MessagingResponse()
    msg = response.message()
    string, file_url = None, None

    # Whatsapp request parsing, based on session current configuration
    if session is None:
        string = f"Sorry, we couldn't find your Whatsapp number in our database."
    # Handle Initial stage
    elif session['stage'] == 'initial_stage':
        session['stage'] = 'awaiting_company_selection'
        string = hello_string.format(session['client_name'], company_list)
    # Handle Company selection
    elif session['stage'] == 'awaiting_company_selection':
        user_selection = parse_option_selection(incoming_msg)
        if user_selection == 0:  # Select a different Company
            session['stage'] = 'awaiting_company_selection'
            string = hello_string.format(session['client_name'], company_list)
        elif user_selection <= len(session['companies']):
            session['selected_company'] = session['companies'][user_selection - 1]
            session['stage'] = 'awaiting_theme_selection'
            string = f"Which data segment are you looking for {session['selected_company']}?\n" \
                     + theme_options_list + "\n0. to select another Company"
        else:
            string = invalid_string
    # Handle Theme selection
    elif session['stage'] == 'awaiting_theme_selection':
        user_selection = parse_option_selection(incoming_msg)
        if user_selection == 0:  # Select a different Company
            session['stage'] = 'awaiting_company_selection'
            string = hello_string.format(session['client_name'], company_list)
        elif user_selection <= len(theme_options):
            session['stage'] = 'awaiting_data_request'
            session['selected_theme'] = theme_options[user_selection - 1]
            string = "Which ** {} data are you looking for \'{}\'?\n{}\n0. to select another Company"
            if session['selected_theme'] == 'Corporate':
                string = string.format(session['selected_theme'], session['selected_company'], corp_data_fields_list)
            elif session['selected_theme'] == 'Tax':
                string = string.format(session['selected_theme'], session['selected_company'], tax_data_fields_list)
        else:
            string = invalid_string
    # Handle Data selection
    elif session['stage'] == 'awaiting_data_request':
        user_selection = parse_option_selection(incoming_msg)
        company_name = session['selected_company']
        theme = session['selected_theme']
        company_id = find_record_id_by_value(base_id, 'Companies', 'Company', company_name)
        company_dict = get_airtable_record(base_id, 'Companies', company_id)
        company_fields_dict = company_dict.get('fields', {})
        # Normalize keys (all lowercase)
        lookup_dict = {k.lower(): v for k, v in company_fields_dict.items()}
        if user_selection == 0:  # Select a different Company
            session['stage'] = 'awaiting_company_selection'
            string = hello_string.format(session['client_name'], company_list)
        elif user_selection > len(corp_data_fields):
            string = invalid_string
        elif theme == 'Corporate':
            lookup_field = corp_data_fields[user_selection - 1].strip().lower()
            value = lookup_dict.get(lookup_field)
            string = f"{corp_data_fields[user_selection - 1]}: {value}"
        elif theme == 'Tax':
            if user_selection == 1:  # EIN
                value_1 = lookup_dict.get('tax id type')
                value_2 = lookup_dict.get('tax id number')
                string = f"Tax ID type: {value_1}  -  Number: {value_2}"
                file_url = get_file_url_from_airtable(base_id, 'Companies', company_name + ' - EIN.pdf')
            else:
                lookup_field = tax_data_fields[user_selection - 1].strip().lower()
                value = lookup_dict.get(lookup_field)
                string = f"{tax_data_fields[user_selection - 1]}: {value}"

    # Return reply message to Twilio Whatsapp service
    print(string)
    msg.body(string)
    if file_url:
        msg.media(file_url)
    return str(response)


if __name__ == "__main__":
    app.run(port=8080)
