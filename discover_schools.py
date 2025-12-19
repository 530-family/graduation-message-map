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
# This pattern matches words ending with '학교' or '아카데미', capturing the full name.
# It's designed to avoid splitting names and is not perfect, but covers many cases.
SCHOOL_PATTERN = re.compile(r'([\w\s]+(?:중학교|고등학교|대학교|아카데미|스쿨|유치원|초등학교))')

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
            for line in f:
                if line.strip():
                    schools.add(json.loads(line).get('schoolName'))
    except FileNotFoundError:
        print(f"Info: '{file_path}' not found. Assuming no existing schools.")
    return schools

def find_new_schools(service, start_dt_obj, start_date_str):
    """Searches Gmail, extracts potential school names, and returns new, unique ones, filtering by exact datetime."""
    # Use only date for the initial Gmail API query to limit results efficiently
    query = f'label:졸업식 to:me after:{start_date_str}' # start_date_str is 'YYYY/MM/DD'
    print(f"Searching Gmail with query: '{query}'")
    
    response = service.users().messages().list(userId='me', q=query).execute()
    messages = response.get('messages', [])
    
    if not messages:
        print("No messages found matching the criteria.")
        return set()

    print(f"Found {len(messages)} messages. Processing and filtering by exact time...")
    
    found_schools = set()
    for msg in messages:
        message_data = service.users().messages().get(userId='me', id=msg['id']).execute()
        
        # Convert internalDate to datetime object for comparison
        # internalDate is in milliseconds since epoch
        # The internalDate is UTC, so ensure comparison is also UTC-aware or naive but consistent.
        # For simplicity, we'll assume naive datetimes are in the same timezone for comparison.
        msg_internal_dt = datetime.fromtimestamp(int(message_data['internalDate']) / 1000)

        # Filter by exact start_dt_obj
        if msg_internal_dt < start_dt_obj:
            print(f"  Skipping message (ID: {msg['id']}) older than {start_dt_obj}.")
            continue # Skip messages older than the specified start_dt

        # Extract subject
        subject = ''
        for header in message_data['payload']['headers']:
            if header['name'].lower() == 'subject':
                subject = header['value']
                break
        
        # Extract body
        body = ''
        if 'parts' in message_data['payload']:
            for part in message_data['payload']['parts']:
                if part.get('body') and part.get('body').get('data'):
                    if part['mimeType'] == 'text/plain':
                        body += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    elif part['mimeType'] == 'text/html':
                        soup = BeautifulSoup(base64.urlsafe_b64decode(part['body']['data']), 'html.parser')
                        body += soup.get_text()
        else:
             if message_data['payload'].get('body') and message_data['payload'].get('body').get('data'):
                body_data = message_data['payload']['body']['data']
                body = base64.urlsafe_b64decode(body_data).decode('utf-8')


        full_text = f"{subject} {body}"
        
        # Find all matches in the text
        potential_schools = SCHOOL_PATTERN.findall(full_text)
        for school in potential_schools:
            # Basic cleaning
            cleaned_school = school.strip()
            # Add to our set of found schools
            found_schools.add(cleaned_school)
            
    return found_schools

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
    schools_to_add = newly_found_schools - existing_schools
    
    if not schools_to_add:
        print("\nAll found schools already exist in the coordinates file. Nothing to add.")
        return
        
    print(f"\nAttempting to add {len(schools_to_add)} new schools:")
    for school in sorted(list(schools_to_add)):
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
    fail_count = 0

    for school_name in sorted(list(schools_to_add)):
        print(f"\n--- Geocoding '{school_name}' ---")
        try:
            # We use the school name as the address as requested.
            command = [
                'bash',
                geocode_script,
                '--on-duplicate',
                'skip',
                school_name,
                school_name 
            ]
            
            # The script will print its own output, so we don't need to capture it unless for debugging.
            # We check the return code to see if it succeeded.
            result = subprocess.run(command, check=False, text=True) # check=False to handle non-zero exit codes manually
            
            if result.returncode == 0:
                print(f"✓ Successfully processed '{school_name}'.")
                success_count += 1
            else:
                print(f"✗ Failed to process '{school_name}' (geocode.sh exit code: {result.returncode}). Check output above for details.")
                fail_count += 1

        except Exception as e:
            print(f"✗ An unexpected error occurred while running geocode.sh for '{school_name}': {e}")
            fail_count += 1
    
    print("\n" + "="*80)
    print("Geocoding Summary")
    print("="*80)
    print(f"Successfully added: {success_count}")
    print(f"Failed or skipped: {fail_count}")
    print("="*80)

if __name__ == '__main__':
    main()
