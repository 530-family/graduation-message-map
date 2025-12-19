#!/usr/bin/env python3
import base64
import email
import json
import os
import re
import argparse
import subprocess
from datetime import date, timedelta, datetime
import urllib.parse
import urllib.request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from bs4 import BeautifulSoup

# Gmail API setup
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
# This pattern uses two groups to ensure a name part exists before the suffix.
# 1. A non-greedy name part that must start with a non-whitespace character.
# 2. The school type suffix.
SCHOOL_PATTERN = re.compile(r'(\S[\w\s]*?)(중학교|고등학교|대학교|아카데미|스쿨|유치원|초등학교)')

def get_google_search_credentials():
    """Reads Google API Key and CSE ID from .env.local file."""
    creds = {}
    try:
        with open('.env.local', 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"\'') # Remove quotes
                    if key in ['GOOGLE_API_KEY', 'GOOGLE_CSE_ID']:
                        creds[key] = value
    except FileNotFoundError:
        return None # .env.local not found
    
    if 'GOOGLE_API_KEY' in creds and 'GOOGLE_CSE_ID' in creds:
        return creds
    return None # Keys not found

def search_address_web(school_name, api_key, cse_id):
    """Searches for a school's address using Google Custom Search API."""
    print(f"  -> Performing web search for '{school_name}' address...")
    try:
        query = f'"{school_name}" 도로명 주소'
        encoded_query = urllib.parse.quote(query)
        url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={cse_id}&q={encoded_query}"
        
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            
            if 'items' in data and data['items']:
                # Return the snippet of the first result
                snippet = data['items'][0].get('snippet', '').strip()
                # Clean the snippet
                cleaned_snippet = snippet.replace('\n', ' ').replace('...', ' ').strip()
                if cleaned_snippet:
                    print(f"  -> Found potential address: {cleaned_snippet}")
                    return cleaned_snippet
    except Exception as e:
        print(f"  -> Web search failed: {e}")
    
    print("  -> Web search did not find a usable address.")
    return None

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
        
        # Find all matches using the new two-group pattern
        for match in SCHOOL_PATTERN.finditer(full_text):
            # Combine group 1 (name) and group 2 (suffix)
            full_school_name = match.group(1).strip() + match.group(2)
            
            # Basic cleaning
            cleaned_school = full_school_name.strip()
            # Add to our set of found schools
            found_schools.add(cleaned_school)
            
    return found_schools

def append_to_ndjson(file_path, data_item):
    """Appends a JSON object to the ndjson file."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True) # Ensure directory exists
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(data_item, ensure_ascii=False) + '\n')

# Helper functions for ndjson operations
def get_next_id_from_ndjson(file_path):
    """Reads the ndjson file and returns the next available ID."""
    max_id = 0
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    if 'id' in data and isinstance(data['id'], int):
                        max_id = max(max_id, data['id'])
    except FileNotFoundError:
        pass # File does not exist, max_id remains 0
    except json.JSONDecodeError as e:
        print(f"Warning: Error decoding JSON from '{file_path}': {e}. IDs might be inconsistent.")
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
    added_empty_address_count = 0
    search_creds = get_google_search_credentials()

    if not search_creds:
        print("NOTE: Google Search credentials not found in .env.local. Web search fallback will be skipped.")

    for school_name in sorted(list(schools_to_add)):
        print(f"\n--- Processing '{school_name}' ---")
        geocoded_successfully = False

        # --- Attempt 1: Use school name as address ---
        try:
            print("  Attempt 1: Geocoding with school name as address.")
            command1 = [
                'bash', geocode_script,
                '--on-duplicate', 'skip',
                school_name, school_name 
            ]
            result1 = subprocess.run(command1, check=False, text=True, capture_output=True)
            
            if result1.returncode == 0:
                print(f"  ✓ Success with Attempt 1.")
                print(result1.stdout)
                success_count += 1
                geocoded_successfully = True
            else:
                print(f"  ✗ Attempt 1 failed.")

            # --- Attempt 2: Web search for address if first attempt failed ---
            if not geocoded_successfully and search_creds:
                found_address = search_address_web(school_name, search_creds['GOOGLE_API_KEY'], search_creds['GOOGLE_CSE_ID'])
                
                if found_address:
                    print("  Attempt 2: Geocoding with address found from web search.")
                    command2 = [
                        'bash', geocode_script,
                        '--on-duplicate', 'skip',
                        school_name, found_address
                    ]
                    result2 = subprocess.run(command2, check=False, text=True, capture_output=True)

                    if result2.returncode == 0:
                        print(f"  ✓ Success with Attempt 2.")
                        print(result2.stdout)
                        success_count += 1
                        geocoded_successfully = True
                    else:
                        print(f"  ✗ Attempt 2 failed.")

        except Exception as e:
            print(f"  ✗ An unexpected error occurred while processing '{school_name}': {e}")
        
        # --- Fallback: Add with empty address if all attempts failed ---
        if not geocoded_successfully:
            print(f"  -> All attempts failed. Adding '{school_name}' with an empty address.")
            next_id = get_next_id_from_ndjson(coords_file)
            empty_address_entry = {
                "id": next_id,
                "schoolName": school_name,
                "address": "",
                "coordinates": {"longitude": 0, "latitude": 0}
            }
            append_to_ndjson(coords_file, empty_address_entry)
            added_empty_address_count += 1

    print("\n" + "="*80)
    print("Geocoding Summary")
    print("="*80)
    print(f"Successfully geocoded and added: {success_count}")
    print(f"Added with empty address (requires manual update): {added_empty_address_count}")
    print("="*80)

if __name__ == '__main__':
    main()
