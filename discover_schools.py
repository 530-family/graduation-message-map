#!/usr/bin/env python3
import base64
import email
import json
import os
import re
import argparse
import subprocess
from datetime import date, timedelta, datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from bs4 import BeautifulSoup

# Gmail API setup
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
# 1. A non-greedy name part that must start with a word character.
# 2. The school type suffix. This is now a single-group pattern.
SCHOOL_PATTERN = re.compile(r'(\w[\w\s]*?(?:중학교|고등학교|대학교|아카데미|스쿨|유치원|초등학교))')
PRIMARY_SCHOOL_PATTERN = re.compile(r'\[학교명 / 소재지\]:\s*(.+?학교)')

def get_gmail_service():
    """Authenticates with Gmail API and returns a service object."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def get_existing_schools(file_path):
    """Reads the ndjson file and returns a set of existing school names."""
    schools = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if not line.strip():
                    continue
                try:
                    schools.add(json.loads(line).get('schoolName'))
                except json.JSONDecodeError as e:
                    print(f"Warning: Skipping malformed JSON on line {i+1} in '{file_path}': {e}")
                    print(f"         > Content: {line.strip()}")
                    continue
    except FileNotFoundError:
        print(f"Info: '{file_path}' not found. Assuming no existing schools.")
    return schools

def find_new_schools(service, start_dt_obj, start_date_str):
    """
    Searches Gmail across all pages, sorts messages chronologically, extracts
    potential school names, and returns a new, unique, and ordered list.
    """
    query = f'label:졸업식 to:me after:{start_date_str}'
    print(f"Searching Gmail with query: '{query}'")
    
    # --- Handle Pagination: Fetch all message summaries from all pages ---
    messages_summary = []
    request = service.users().messages().list(userId='me', q=query)
    while request is not None:
        response = request.execute()
        messages_summary.extend(response.get('messages', []))
        request = service.users().messages().list_next(previous_request=request, previous_response=response)
    
    if not messages_summary:
        print("No messages found matching the criteria.")
        return []

    print(f"Found a total of {len(messages_summary)} messages. Fetching details for sorting...")
    
    # Fetch internalDate for all messages to sort them
    dated_messages = []
    for msg_summary in messages_summary:
        msg_meta = service.users().messages().get(userId='me', id=msg_summary['id'], format='metadata', fields='id,internalDate').execute()
        msg_internal_dt = datetime.fromtimestamp(int(msg_meta['internalDate']) / 1000)
        if msg_internal_dt >= start_dt_obj:
            dated_messages.append(msg_meta)

    # Sort messages by internalDate, oldest first
    dated_messages.sort(key=lambda x: int(x['internalDate']))
    
    print(f"Processing {len(dated_messages)} messages in chronological order...")
    
    found_schools_list = []
    seen_schools_set = set()

    for msg_meta in dated_messages:
        print(f"\n--- Checking Email ID: {msg_meta['id']} ---")
        message_data = service.users().messages().get(userId='me', id=msg_meta['id']).execute()
        
        subject = ''
        for header in message_data['payload']['headers']:
            if header['name'].lower() == 'subject':
                subject = header['value']
                break
        
        body = ''
        if 'parts' in message_data['payload']:
            for part in message_data['payload']['parts']:
                if part.get('body') and part.get('body').get('data'):
                    if part['mimeType'] == 'text/plain':
                        body += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                    elif part['mimeType'] == 'text/html':
                        soup = BeautifulSoup(base64.urlsafe_b64decode(part['body']['data']), 'html.parser')
                        body += soup.get_text()
        elif message_data['payload'].get('body') and message_data['payload'].get('body').get('data'):
            body_data = message_data['payload']['body']['data']
            body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')

        full_text = f"{subject} {body}"
        
        def add_school(school_name):
            cleaned_school = school_name.strip()
            if cleaned_school and cleaned_school not in seen_schools_set:
                seen_schools_set.add(cleaned_school)
                found_schools_list.append(cleaned_school)

        # 1. Primary Strategy: Look for '[학교명 / 소재지]:'
        primary_match = PRIMARY_SCHOOL_PATTERN.search(full_text)
        if primary_match:
            school_name = primary_match.group(1).strip()
            print(f"  > Primary pattern matched: '{school_name}'")
            add_school(school_name)
            continue # Skip to the next email

        # 2. Fallback Strategy: Find the *first* match of the general pattern
        fallback_match = SCHOOL_PATTERN.search(full_text)
        if fallback_match:
            school_name = fallback_match.group(1).strip()
            print(f"  > Fallback pattern matched: '{school_name}'")
            add_school(school_name)
            continue # Skip to the next email
            
        print("  > No school name patterns matched in this email.")
            
    return found_schools_list

def append_to_ndjson(file_path, data_item):
    """Appends a JSON object to the ndjson file."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True) # Ensure directory exists
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(data_item, ensure_ascii=False) + '\n')

# Helper functions for ndjson operations
# Helper functions for ndjson operations
def get_next_id_from_ndjson(file_path):
    """Reads the ndjson file robustly and returns the next available ID."""
    max_id = 0
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if 'id' in data and isinstance(data['id'], int):
                        max_id = max(max_id, data['id'])
                except json.JSONDecodeError:
                    # This will skip malformed lines, preventing the ID bug
                    print(f"Warning: Skipping malformed line {i+1} in '{file_path}' when determining next ID.")
                    continue
    except FileNotFoundError:
        pass # File does not exist, max_id remains 0
    return max_id + 1

def main():
    """Main function to run the school discovery and geocoding process."""
    parser = argparse.ArgumentParser(description='Discover new schools from Gmail and add them to the coordinates file.')
    parser.add_argument(
        '--start-datetime',
        type=str,
        required=True,
        help='The start date and optionally time for the email search in YYYY-MM-DD or "YYYY-MM-DD HH:MM:SS" format.'
    )
    args = parser.parse_args()

    # Validate datetime format and convert to datetime object
    start_dt_obj = None
    try:
        # Try parsing with time first
        start_dt_obj = datetime.strptime(args.start_datetime, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        try:
            # Fallback to date only, set time to 00:00:00
            start_dt_obj = datetime.strptime(args.start_datetime, '%Y-%m-%d')
        except ValueError:
            print("Error: --start-datetime must be in YYYY-MM-DD or 'YYYY-MM-DD HH:MM:SS' format.")
            return

    # --- Step 1: Get existing schools from coordinates file ---
    coords_file = 'public/data/coordinates.ndjson'
    existing_schools = get_existing_schools(coords_file)
    print(f"Found {len(existing_schools)} existing schools in '{coords_file}'.")

    # --- Step 2: Find new schools from Gmail ---
    service = get_gmail_service()
    # Pass the datetime object for precise filtering and the date part for the initial Gmail query
    newly_found_schools = find_new_schools(service, start_dt_obj, start_dt_obj.strftime('%Y/%m/%d'))
    
    if not newly_found_schools:
        print("\nNo new potential schools found in Gmail.")
        return

    print(f"\nFound {len(newly_found_schools)} total potential schools from Gmail.")

    # --- Step 3: Filter out existing schools ---
    print("\nFiltering against existing schools...")
    schools_to_add = []
    for school in newly_found_schools:
        if school not in existing_schools:
            schools_to_add.append(school)
        else:
            print(f"  - Skipping '{school}' (already exists in coordinates.ndjson)")
    
    if not schools_to_add:
        print("\nAll found schools already exist in the coordinates file. Nothing to add.")
        return
        
    print(f"\nAttempting to add {len(schools_to_add)} new schools in chronological order:")
    for school in schools_to_add:
        print(f"  - {school}")

    # --- Step 4: Run geocode.sh for each new school ---
    geocode_script = 'scripts/geocode.sh'
    if not os.path.exists(geocode_script):
        print(f"\nError: Geocoding script not found at '{geocode_script}'.")
        return

    print("\n" + "="*80)
    print("Starting Geocoding Process")
    print("="*80)

    success_count = 0
    added_empty_address_count = 0

    for school_name in schools_to_add:
        print(f"\n--- Processing '{school_name}' ---")
        geocoded_successfully = False
        try:
            # Attempt to geocode using school name as address
            command = [
                'bash', geocode_script,
                '--on-duplicate', 'skip',
                school_name, school_name 
            ]
            result = subprocess.run(command, check=False, text=True, capture_output=True)
            
            if result.returncode == 0:
                print(f"  ✓ Successfully geocoded '{school_name}' using its name.")
                print(result.stdout)
                success_count += 1
                geocoded_successfully = True
            else:
                print(f"  ✗ Geocoding with name failed. Adding as entry with empty address.")

        except Exception as e:
            print(f"  ✗ An unexpected error occurred during geocoding: {e}")
        
        # Fallback: Add with empty address if geocoding failed
        if not geocoded_successfully:
            next_id = get_next_id_from_ndjson(coords_file)
            empty_address_entry = {
                "id": next_id,
                "schoolName": school_name,
                "address": "",
                "coordinates": {"longitude": 0, "latitude": 0}
            }
            append_to_ndjson(coords_file, empty_address_entry)
            print(f"  -> Added '{school_name}' to '{coords_file}' with an empty address (ID: {next_id}).")
            added_empty_address_count += 1

    print("\n" + "="*80)
    print("Geocoding Summary")
    print("="*80)
    print(f"Successfully geocoded and added: {success_count}")
    print(f"Added with empty address (requires manual update): {added_empty_address_count}")
    print("="*80)

if __name__ == '__main__':
    main()
