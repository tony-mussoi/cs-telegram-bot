import os
import requests
import json
from pyairtable import Table

AIRTABLE_ACCESS_TOKEN = os.environ.get('AIRTABLE_ACCESS_TOKEN')
AIRTABLE_ENDPOINT = 'https://api.airtable.com/v0/'
headers = {'Authorization': f'Bearer {AIRTABLE_ACCESS_TOKEN}', 'Content-Type': 'application/json'}


# Retrieve WhatsApp Bots configurations, grouped by phone number
def fetch_client_bots(base_id, table_name):
    url = f'{AIRTABLE_ENDPOINT}{base_id}/{table_name}'
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Error fetching data:", response.status_code)
        return {}
    records = response.json().get('records', [])
    user_sessions = {}
    for record in records:
        fields = record.get('fields', {})
        client_phone = fields.get('From number', '').strip()
        client_name = fields.get('Client name', '')[0].strip()
        company_name = fields.get('Company name', '')[0].strip()
        if not client_phone or not client_name or not company_name:
            continue
        if client_phone not in user_sessions:
            user_sessions[client_phone] = {
                'client_phone': client_phone,
                'client_name': client_name,
                'companies': [],
                'stage': 'initial_stage',
                'selected_company': None,
                'selected_theme': None,
            }
        user_sessions[client_phone]['companies'].append(company_name)
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




