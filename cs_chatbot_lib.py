import os
import logging
import requests
import json
from pyairtable import Table

AIRTABLE_ACCESS_TOKEN = os.environ.get('AIRTABLE_ACCESS_TOKEN')
AIRTABLE_ENDPOINT = 'https://api.airtable.com/v0/'
headers = {'Authorization': f'Bearer {AIRTABLE_ACCESS_TOKEN}', 'Content-Type': 'application/json'}

# Retrieve Bots configurations, grouped by phone number
def fetch_client_bots(base_id, table_name):
    url = f'{AIRTABLE_ENDPOINT}{base_id}/{table_name}'
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Error fetching data:", response.status_code)
        return {}
    records = response.json().get('records', [])
    user_sessions = {}
    # Set in-memory User Sessions
    for record in records:
        fields = record.get('fields', {})
        client_phone = fields.get('From number', '').strip()
        chat_id = fields.get('Chat ID', '').strip()
        clients = fields.get('Clients', '')
        companies = fields.get('Companies', '')
        authorized = fields.get('Authorized', '')
        if authorized:
            stage = 'initial_stage'
        elif not client_phone:
            stage = 'auth_awaiting_start'
        else:
            stage = 'auth_awaiting_authorization'
        # Add individual session to sessions dictionary
        if client_phone not in user_sessions:
            user_sessions[chat_id] = {
                'chat_id': chat_id,
                'client_phone': client_phone,
                'authorized': authorized,
                'clients': clients,
                'companies': [],
                'stage': stage,
                'selected_company': None,
                'selected_group': None,
            }
        user_sessions[chat_id]['companies'].append(companies)
    return user_sessions

# Find a record in an Airtable table by field value and return its ID.
def find_record_id_by_value(base_id, table_name, field_name, field_value):
    # Initialize the Airtable client with the base ID and table name
    airtable = Table(AIRTABLE_ACCESS_TOKEN, base_id, table_name)
    try:
        # Fetch all records from the table
        records = airtable.all()
        # Loop through the records to find the one that matches the field value
        for record in records:
            # Check if the field value matches the value you are searching for
            if record['fields'].get(field_name) == field_value:
                # Return the record ID if a match is found
                return record['id']
        # Return None if no record is found
        return None
    except Exception as e:
        print(f"An error occurred while searching for the record: {e}")
    return None

# Get individual Airtable record
def get_airtable_record(base_id, table_name, record_id):
    url = f'{AIRTABLE_ENDPOINT}{base_id}/{table_name}/{record_id}'
    # Send your request and parse the response
    response = requests.get(url, headers=headers)
    data = json.loads(response.text)
    # Print the field values for the record
    print(data['fields'])
    return data

""" Create new record in Airtable
def create_airtable_record(base_id, table_name, data):
    url = f'{AIRTABLE_ENDPOINT}{base_id}/{table_name}'
    # Send a POST request to create the record and parse response
    # print("Data being sent to Airtable:")
    # print(json.dumps(data, indent=4))  # This will help you inspect the data structure
    response = requests.post(url, headers=headers, json=data)
    # Check if the request was successful
    if response.status_code == 200:
        print("Record created successfully:", response.json())
    else:
        print("Failed to create record:", response.json())
    return response.status_code
"""

# Get file URL from Airtable
def get_file_url_from_airtable(base_id, table_name, filename):
    url = f'{AIRTABLE_ENDPOINT}{base_id}/{table_name}'
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None
    for record in response.json().get("records", []):
        company_name = record.get("fields", {}).get("Company", [])
        attachments = record.get("fields", {}).get("Tax ID file", [])
        for file in attachments:
            #if file.get("filename", "").lower() == filename.lower():
            if file.get("filename", "") == filename:
                return file.get("url")
    return None

# Add Chatbot user to Airtable
def add_bot_user(base_id, table_name, phone, user_id, request_name, request_client):
    url = f'{AIRTABLE_ENDPOINT}{base_id}/{table_name}'
    # Check if the phone already exists
    filter_formula = f"{{From number}} = '{phone}'"
    check_url = f"{url}?filterByFormula={requests.utils.quote(filter_formula)}"
    check_response = requests.get(check_url, headers=headers)
    check_response.raise_for_status()
    records = check_response.json().get("records", [])
    # Setup user data
    data_fields = {
            "From number": phone,
            "Chat ID": str(user_id),
            "Request Name": request_name,
            "Request Client": request_client,
    }
    # Update the existing record in Airtable
    if records: # If User already exists
        record_id = records[0]["id"]
        patch_url = f"{url}/{record_id}"
        patch_response = requests.patch(patch_url, headers=headers, json={"fields": data_fields})
        patch_response.raise_for_status()
        return patch_response.status_code

    # Create a new record, in Airtable, if not found
    post_response = requests.post(url, headers=headers, json={"fields": data_fields})
    post_response.raise_for_status()
    return post_response.status_code

# Add in-memory Chatbot user Session
def add_new_session(user_sessions, chat_id):
    user_sessions[chat_id] = {
        'chat_id': chat_id,
        'client_phone': '',
        'authorized': '',
        'clients': '',
        'companies': [],
        'stage': 'auth_awaiting_start',
        'selected_company': None,
        'selected_group': None,
    }
    return user_sessions

# Check User bot authorization
def is_user_authorized(base_id, table_name, user_id, session):
    url = f'{AIRTABLE_ENDPOINT}{base_id}/{table_name}'
    params = {
        "filterByFormula": f"{{Chat ID}} = '{user_id}'"
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        records = response.json().get("records", [])
        if not records:
            session['authorized'] = False
            return session
        fields = records[0].get("fields", {})
        authorized = fields.get("Authorized", False)
        session['authorized'] = authorized
        # If authorized, retrieve Clients and Companies
        if authorized:
            clients_str = fields.get("Clients", "")[0]
            session['clients'] = [client.strip() for client in clients_str.split(",")] if clients_str else []
            companies_str = fields.get("Companies", "")[0]
            session['companies'] = [company.strip() for company in companies_str.split(",")] if companies_str else []
            # Update session stage, if still within Authorization process
            if session['stage'] in ['auth_awaiting_start', 'auth_awaiting_name', 'auth_awaiting_phone',
                                    'auth_awaiting_authorization']:
                session['stage'] = 'initial_stage'

    except requests.RequestException as e:
        logging.error(f"Error checking user authorization: {e}")
        session['authorized'] = False
    return session

# Retrieve Action Items, filtered by Company name
def fetch_action_items(base_id, table_name, company_name):
    url = f"{AIRTABLE_ENDPOINT}{base_id}/{table_name}"
    filter_formula = f"{{Company}} = '{company_name}'"
    params = {
        "filterByFormula": filter_formula
    }
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    records = response.json().get("records", [])
    action_items = [f"✅  \"{rec['fields'].get('Action Item')}\"\n" for rec in records if
                    rec.get("fields", {}).get("Action Item")]
    return "".join(action_items)
