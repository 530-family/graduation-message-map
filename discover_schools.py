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
import csv

# Gmail API setup
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# This pattern tries to find a school name with 1 to 3 parts, avoiding overly greedy matches.
# It does not use capturing groups; the whole match is the school name.
SCHOOL_PATTERN = re.compile(r'[a-zA-Z0-9가-힣]{2,10}(?:\s[a-zA-Z0-9가-힣]{1,10}){0,2}\s*(?:중학교|고등학교|대학교|아카데미|스쿨|유치원|초등학교|영재학교|국제학교)')
PRIMARY_SCHOOL_PATTERN = re.compile(r'\[학교명 / 소재지\]:\s*(.+?학교)')


def get_school_info_from_csv(school_name, csv_path='public/data/schoolInfo.csv'):
    """
    Searches for a school in the local CSV file and returns its information.
    """
    try:
        # Try cp949 first, as it's a common Korean Windows encoding
        try:
            infile = open(csv_path, mode='r', encoding='cp949')
        except UnicodeDecodeError:
            print(f"  ! cp949 decoding failed for '{csv_path}', trying euc-kr with error replacement.")
            infile = open(csv_path, mode='r', encoding='euc-kr', errors='replace')
        
        with infile: # Use the opened file object
            reader = csv.reader(infile)
            try:
                header = next(reader) # Skip header row
            except StopIteration:
                print(f"  ! CSV file '{csv_path}' is empty.")
                return None
            
            school_name_index = 3
            address_index = 10

            for row in reader:
                try:
                    if len(row) > max(school_name_index, address_index):
                        csv_school_name = row[school_name_index]
                        if school_name == csv_school_name:
                            print(f"  ✓ Found '{school_name}' in {csv_path}")
                            return {
                                "SCHUL_NM": row[school_name_index],
                                "ORG_RDNMA": row[address_index]
                            }
                except IndexError:
                    # Skip malformed rows
                    continue
            
            print(f"  ! '{school_name}' not found in {csv_path}.")
            return None

    except FileNotFoundError:
        print(f"  ✗ Error: CSV file not found at '{csv_path}'.")
        return None
    except Exception as e:
        print(f"  ✗ An error occurred while reading CSV: {e}")
        return None


def extract_email_text(payload):
    """
    Recursively extracts text from an email payload.
    For multipart/alternative, it prioritizes text/html over text/plain.
    """
    if payload.get('mimeType') == 'text/plain' and payload.get('body') and payload.get('body').get('data'):
        return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')

    if payload.get('mimeType') == 'text/html' and payload.get('body') and payload.get('body').get('data'):
        soup = BeautifulSoup(base64.urlsafe_b64decode(payload['body']['data']), 'html.parser')
        return soup.get_text(separator='\n')

    if 'parts' in payload:
        if payload.get('mimeType') == 'multipart/alternative':
            # In alternative, parts are in order of increasing preference. Last part is best.
            html_part = None
            text_part = None
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain':
                    text_part = extract_email_text(part)
                elif part.get('mimeType') == 'text/html':
                    html_part = extract_email_text(part)
            return html_part or text_part or ''
        else:
            # For other multipart types (mixed, related, etc.), concatenate all parts.
            return "".join([extract_email_text(part) for part in payload['parts']])
    
    # Fallback for non-multipart message with data directly in payload body
    if payload.get('body') and payload.get('body').get('data'):
         return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')

    return ""

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
    """Reads the ndjson file and returns a set of unique school identifiers.
    An identifier is a tuple of (schoolName, address_prefix).
    """
    schools = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    school_name = data.get('schoolName')
                    address = data.get('address')
                    if school_name and address:
                        address_prefix = ' '.join(address.split()[:2])
                        schools.add((school_name, address_prefix))
                    elif school_name:
                        # For entries with no address yet, use an empty prefix
                        schools.add((school_name, ''))
                except json.JSONDecodeError as e:
                    print(f"Warning: Skipping malformed JSON on line {i+1} in '{file_path}': {e}")
                    print(f"         > Content: {line.strip()}")
                    continue
    except FileNotFoundError:
        print(f"Info: '{file_path}' not found. Assuming no existing schools.")
    return schools

def find_new_schools(service, start_dt_obj, start_date_str):
    """
    Searches Gmail, extracts school names using regex, and asks for manual input
    if extraction fails.
    Returns:
        A tuple containing:
        - A list of unique, chronologically ordered school names.
        - A list of emails (dict with id, subject, body) for manual review.
    """
    query = f'label:졸업식 to:me after:{start_date_str}'
    print(f"Searching Gmail with query: '{query}'")
    
    messages_summary = []
    request = service.users().messages().list(userId='me', q=query)
    while request is not None:
        response = request.execute()
        messages_summary.extend(response.get('messages', []))
        request = service.users().messages().list_next(previous_request=request, previous_response=response)
    
    if not messages_summary:
        print("No messages found matching the criteria.")
        return [], []

    print(f"Found a total of {len(messages_summary)} messages. Fetching details for sorting...")
    
    dated_messages = []
    for msg_summary in messages_summary:
        msg_meta = service.users().messages().get(userId='me', id=msg_summary['id'], format='metadata', fields='id,internalDate').execute()
        msg_internal_dt = datetime.fromtimestamp(int(msg_meta['internalDate']) / 1000)
        if msg_internal_dt >= start_dt_obj:
            dated_messages.append(msg_meta)

    dated_messages.sort(key=lambda x: int(x['internalDate']))
    
    print(f"Processing {len(dated_messages)} messages in chronological order...")
    
    found_schools_list = []
    seen_schools_set = set()
    emails_for_manual_review = []

    for msg_meta in dated_messages:
        print(f"\n--- Checking Email ID: {msg_meta['id']} ---")
        message_data = service.users().messages().get(userId='me', id=msg_meta['id']).execute()
        
        subject = ''
        for header in message_data['payload']['headers']:
            if header['name'].lower() == 'subject':
                subject = header['value']
                break
        
        body = extract_email_text(message_data['payload'])

        full_text = f"{subject}\n\n{body}"
        
        def add_school(school_name):
            cleaned_school = school_name.strip()
            if cleaned_school and cleaned_school not in seen_schools_set:
                seen_schools_set.add(cleaned_school)
                found_schools_list.append(cleaned_school)
        
        school_found = False
        primary_match = PRIMARY_SCHOOL_PATTERN.search(full_text)
        if primary_match:
            school_name = primary_match.group(1).strip()
            print(f"  > Primary pattern matched: '{school_name}'")
            add_school(school_name)
            school_found = True

        if not school_found:
            fallback_match = SCHOOL_PATTERN.search(full_text)
            if fallback_match:
                full_school_name = fallback_match.group(0).strip()
                print(f"  > Fallback pattern matched: '{full_school_name}'")
                add_school(full_school_name)
                school_found = True
        
        if not school_found:
            print("\n" + "-"*50)
            print("  ! 자동 추출 실패: 수동 입력이 필요합니다.")
            print("  ! Automatic extraction failed: Manual input required.")
            print("-"*50)
            print(f"이메일 제목 (Subject): {subject}")
            print("\n--- 이메일 본문 (Body) ---")
            print(body.strip())
            print("-------------------------\n")
            
            manual_school_name = input(">>> 학교 이름을 직접 입력하세요 (건너뛰려면 Enter 키): ").strip()
            
            if manual_school_name:
                print(f"  > 사용자가 입력한 학교 이름: '{manual_school_name}'")
                add_school(manual_school_name)
            else:
                print("  > 건너뛰었습니다. 수동 검토 목록에 추가합니다.")
                emails_for_manual_review.append({
                    'id': msg_meta['id'],
                    'subject': subject,
                    'body': body
                })
            
    return found_schools_list, emails_for_manual_review

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

    # --- Step 2: Find new schools and emails for manual review ---
    service = get_gmail_service()
    newly_found_schools, emails_for_manual_review = find_new_schools(service, start_dt_obj, start_dt_obj.strftime('%Y/%m/%d'))
    
    if newly_found_schools:
        print(f"\nFound {len(newly_found_schools)} total potential schools from Gmail.")
    else:
        print("\nNo new potential schools found in Gmail.")

    # --- Step 3: Filter out existing schools ---
    print("\nFiltering against existing schools...")
    schools_to_add = []
    # Create a simple set of names for logging and basic checking
    existing_school_names = {s[0] for s in existing_schools if s[0]}
    for school in newly_found_schools:
        if school not in existing_school_names:
            schools_to_add.append(school)
        else:
            # Even if the name exists, it might be a different school in another location.
            # We will let the more robust geocoding step handle the final duplicate check.
            print(f"  - Name '{school}' already exists, but adding for geocoding to verify location.")
            schools_to_add.append(school)
    
    if not schools_to_add:
        print("\nAll auto-detected schools already exist. No new schools to add automatically.")
    else:
        print(f"\nAttempting to add {len(schools_to_add)} new schools in chronological order:")
        for school in schools_to_add:
            print(f"  - {school}")

        # --- Step 4: Find school addresses and add new schools ---
        geocode_script = 'scripts/geocode.sh'
        if not os.path.exists(geocode_script):
            print(f"\nError: Geocoding script not found at '{geocode_script}'. Cannot get coordinates.")
            # To prevent adding entries without trying to geocode, we stop here.
            return

        print("\n" + "="*80)
        print("Starting School Info Search & Geocoding Process")
        print("="*80)

        success_count = 0
        added_empty_address_count = 0

        for school_name in schools_to_add:
            print(f"\n--- Processing '{school_name}' ---")
            
            school_info = get_school_info_from_csv(school_name)
            
            geocoded_successfully = False
            if school_info and school_info.get("ORG_RDNMA"):
                precise_name = school_info.get("SCHUL_NM", school_name)
                precise_address = school_info.get("ORG_RDNMA")
                print(f"  ✓ Found via CSV: '{precise_name}' at '{precise_address}'")

                try:
                    command = [
                        'bash', geocode_script,
                        '--on-duplicate', 'skip',
                        precise_name, precise_address
                    ]
                    result = subprocess.run(command, check=False, text=True, capture_output=True)
                
                    if result.returncode == 0:
                        print(f"  ✓ Successfully geocoded '{precise_name}' using CSV address.")
                        print(result.stdout)
                        success_count += 1
                        geocoded_successfully = True
                    else:
                        print(f"  ✗ Geocoding with CSV address failed (Code: {result.returncode}). Stderr: {result.stderr.strip()}")
                except Exception as e:
                    print(f"  ✗ An unexpected error occurred during geocoding: {e}")

                # If geocoding fails after finding address, add with the address info we found
                if not geocoded_successfully:
                    print("  -> Adding entry with CSV address but without coordinates.")
                    next_id = get_next_id_from_ndjson(coords_file)
                    entry = {
                        "id": next_id,
                        "schoolName": precise_name,
                        "address": precise_address,
                        "coordinates": {"longitude": 0, "latitude": 0}
                    }
                    append_to_ndjson(coords_file, entry)
                    added_empty_address_count += 1
            else:
                # CSV lookup failed. Try geocoding with the original name as a fallback.
                print(f"  ! CSV lookup failed for '{school_name}'. Falling back to geocoding with original name.")
                try:
                    command = [
                        'bash', geocode_script,
                        '--on-duplicate', 'skip',
                        school_name, school_name
                    ]
                    result = subprocess.run(command, check=False, text=True, capture_output=True)
                    if result.returncode == 0:
                        print(f"  ✓ Successfully geocoded '{school_name}' using its name as fallback.")
                        print(result.stdout)
                        success_count += 1
                        geocoded_successfully = True
                except Exception as e:
                     print(f"  ✗ An unexpected error occurred during fallback geocoding: {e}")

                if not geocoded_successfully:
                    print("  -> Fallback geocoding failed. Adding as entry with empty address.")
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
        print("Automatic Geocoding Summary")
        print("="*80)
        print(f"Successfully geocoded and added: {success_count}")
        print(f"Added with empty address (requires manual update): {added_empty_address_count}")

    # --- Step 5: Handle emails needing manual review ---
    if emails_for_manual_review:
        manual_file = 'manual_school_entry.json'
        print(f"\n" + "="*80)
        print(f"Manual Review Needed")
        print("="*80)
        print(f"{len(emails_for_manual_review)} emails could not be parsed automatically.")
        print(f"Their content has been saved to '{manual_file}' for manual review.")
        with open(manual_file, 'w', encoding='utf-8') as f:
            json.dump(emails_for_manual_review, f, ensure_ascii=False, indent=2)
    
    print("\n" + "="*80)
    print("Script Finished")
    print("="*80)

if __name__ == '__main__':
    main()
