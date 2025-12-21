#!/usr/bin/env python3
import base64
import email
import json
import os
import re
import argparse
import subprocess
import time
from datetime import date, timedelta, datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from bs4 import BeautifulSoup
import csv

# Gmail API setup
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Define Suffixes globally
K12_SUFFIXES = ['초등학교', '중학교', '고등학교']
SUFFIX_LIST = K12_SUFFIXES + ['대학교', '영재학교', '국제학교', '아카데미', '스쿨', '유치원']
SUFFIX_REGEX = '|'.join(SUFFIX_LIST)

# Regex patterns
SCHOOL_PATTERN = re.compile(r'[a-zA-Z0-9가-힣]{2,20}(?:\s[a-zA-Z0-9가-힣]{1,20}){0,4}\s*(?:' + SUFFIX_REGEX + r')')
PRIMARY_SCHOOL_PATTERN = re.compile(r'\[학교명 / 소재지\]:\s*(.+?학교)')


def _search_csv(csv_path, school_name, location_hint, school_name_col, address_col):
    """
    A helper function to search a given CSV file for a school.
    It now uses exact matching.
    """
    if not school_name:
        return None
    try:
        try:
            infile = open(csv_path, mode='r', encoding='cp949')
        except UnicodeDecodeError:
            infile = open(csv_path, mode='r', encoding='euc-kr', errors='replace')
        
        with infile:
            reader = csv.reader(infile)
            try:
                header = next(reader)
                all_rows = list(reader)
            except StopIteration:
                return None
            
            exact_matches = []
            for row in all_rows:
                try:
                    if len(row) > max(school_name_col, address_col) and school_name == row[school_name_col]:
                        exact_matches.append(row)
                except IndexError:
                    continue
            
            if not exact_matches:
                return None

            if location_hint:
                hint_matches = [row for row in exact_matches if len(row) > address_col and location_hint in row[address_col]]
                if hint_matches:
                    print(f"  ✓ Found exact match for '{school_name}' with hint '{location_hint}' in {csv_path}")
                    return {"schoolName": hint_matches[0][school_name_col], "address": hint_matches[0][address_col]}
            
            print(f"  ✓ Found exact match for '{school_name}' (no location hint match) in {csv_path}")
            return {"schoolName": exact_matches[0][school_name_col], "address": exact_matches[0][address_col]}
            
    except FileNotFoundError:
        print(f"  ! CSV file not found at '{csv_path}'.")
        return None
    except Exception as e:
        print(f"  ✗ An error occurred while reading {csv_path}: {e}")
        return None


def get_school_info(school_name, location_hint=None):
    """
    Gets school information by searching the appropriate CSV file based on the school name's content.
    """
    if not school_name:
        return None

    if any(suffix in school_name for suffix in K12_SUFFIXES):
        print(f"  > '{school_name}' identified as K-12, checking schoolInfo.csv...")
        school_info = _search_csv('public/data/schoolInfo.csv', school_name, location_hint, school_name_col=3, address_col=10)
        if school_info:
            return school_info
        print(f"  > Not found in schoolInfo.csv, falling back to universityInfo.csv...")
        return _search_csv('public/data/universityInfo.csv', school_name, location_hint, school_name_col=0, address_col=8)
    else:
        print(f"  > '{school_name}' not identified as K-12, checking universityInfo.csv...")
        uni_info = _search_csv('public/data/universityInfo.csv', school_name, location_hint, school_name_col=0, address_col=8)
        
        if uni_info and "대학원" not in uni_info['schoolName']:
            return uni_info
        elif uni_info:
            print(f"  > Rejecting match '{uni_info['schoolName']}' because it is a graduate school.")

        print(f"  > Not found in universityInfo.csv or was a grad school, falling back to schoolInfo.csv...")
        return _search_csv('public/data/schoolInfo.csv', school_name, location_hint, school_name_col=3, address_col=10)


def extract_email_text(payload):
    """
    Recursively extracts text from an email payload.
    """
    if payload.get('mimeType') == 'text/plain' and payload.get('body') and payload.get('body').get('data'):
        return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')

    if payload.get('mimeType') == 'text/html' and payload.get('body') and payload.get('body').get('data'):
        soup = BeautifulSoup(base64.urlsafe_b64decode(payload['body']['data']), 'html.parser')
        return soup.get_text(separator='\n')

    if 'parts' in payload:
        if payload.get('mimeType') == 'multipart/alternative':
            html_part, text_part = None, None
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain':
                    text_part = extract_email_text(part)
                elif part.get('mimeType') == 'text/html':
                    html_part = extract_email_text(part)
            return html_part or text_part or ''
        else:
            return "".join([extract_email_text(part) for part in payload['parts']])
    
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
            if not os.path.exists('credentials.json'):
                print("Error: credentials.json not found.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def get_existing_schools(file_path):
    """Reads the ndjson file and returns a set of unique school identifiers."""
    schools = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if not line.strip(): continue
                try:
                    data = json.loads(line)
                    school_name = data.get('schoolName')
                    address = data.get('address')
                    if school_name and address:
                        schools.add((school_name, address))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return schools

def append_to_ndjson(file_path, data_item):
    """Appends a JSON object to the ndjson file."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(data_item, ensure_ascii=False) + '\n')

def find_entry_in_ndjson(file_path, school_name):
    """Finds a specific entry in an ndjson file by school name."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Search from the end of the file, because we are looking for the most recent entry
            for line in reversed(lines):
                if not line.strip(): continue
                try:
                    data = json.loads(line)
                    if data.get('schoolName') == school_name:
                        return data
                except (json.JSONDecodeError, AttributeError):
                    continue
    except FileNotFoundError:
        return None
    return None

def main():
    """Main function to run the school discovery and geocoding process."""
    parser = argparse.ArgumentParser(description='Discover new schools from Gmail and add them to the coordinates file.')
    parser.add_argument(
        '--start-datetime', type=str, required=True,
        help='The start date and optionally time for the email search in YYYY-MM-DD or "YYYY-MM-DD HH:MM:SS" format.'
    )
    args = parser.parse_args()

    start_dt_obj = None
    try:
        start_dt_obj = datetime.strptime(args.start_datetime, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        try:
            start_dt_obj = datetime.strptime(args.start_datetime, '%Y-%m-%d')
        except ValueError:
            print("Error: --start-datetime must be in YYYY-MM-DD or 'YYYY-MM-DD HH:MM:SS' format.")
            return

    coords_file = 'public/data/coordinates.ndjson'
    internal_coords_file = 'public/data/coordinates.internal.ndjson'
    geocode_script = 'scripts/geocode.sh'

    if not os.path.exists(geocode_script):
        print(f"\nError: Geocoding script not found at '{geocode_script}'.")
        return

    service = get_gmail_service()
    if not service: return

    query = f'label:졸업식 to:me after:{start_dt_obj.strftime("%Y/%m/%d")}'
    print(f"Searching Gmail with query: '{query}'")
    
    messages_summary = []
    request = service.users().messages().list(userId='me', q=query)
    while request is not None:
        response = request.execute()
        messages_summary.extend(response.get('messages', []))
        request = service.users().messages().list_next(previous_request=request, previous_response=response)
    
    if not messages_summary:
        print("No new messages found.")
        return

    print(f"Found {len(messages_summary)} messages. Processing in chronological order...")
    messages_summary.reverse()

    emails_for_manual_review = []
    processed_thread_ids = set()
    
    for msg_summary in messages_summary:
        msg_id = msg_summary['id']
        thread_id = msg_summary['threadId']

        if thread_id in processed_thread_ids:
            print(f"\n--- Skipping Email ID: {msg_id} (already processed thread {thread_id}) ---")
            continue
        
        print(f"\n--- Checking Email ID: {msg_id} (Thread: {thread_id}) ---")
        
        existing_schools = get_existing_schools(coords_file)

        message_data = service.users().messages().get(userId='me', id=msg_id).execute()
        processed_thread_ids.add(thread_id)

        subject = next((h['value'] for h in message_data['payload']['headers'] if h['name'].lower() == 'subject'), '')
        sender = next((h['value'] for h in message_data['payload']['headers'] if h['name'].lower() == 'from'), '')
        body = extract_email_text(message_data['payload'])
        full_text = f"{subject}\n\n{body}"

        candidate_name = None
        primary_match = PRIMARY_SCHOOL_PATTERN.search(full_text)
        if primary_match:
            candidate_name = primary_match.group(1).strip()
            print(f"  > Primary pattern matched: '{candidate_name}'")
        else:
            all_fallback_matches = SCHOOL_PATTERN.findall(full_text)
            if all_fallback_matches:
                print(f"  > Fallback pattern matched: {all_fallback_matches}")
                candidate_name = all_fallback_matches[0]

        school_info = None
        if candidate_name is None:
            print("  > No school name pattern matched automatically.")
        else:
            location_hint, school_name_to_search = None, candidate_name
            if ' ' in candidate_name.strip():
                parts = candidate_name.strip().split(' ')
                if len(parts) > 1:
                    location_hint, school_name_to_search = parts[0], parts[-1]
                print(f"  > Derived: School Name='{school_name_to_search}', Location Hint='{location_hint}'")
            school_info = get_school_info(school_name_to_search, location_hint)

        while not school_info:
            print(f"\n  ! Could not validate school: '{candidate_name}'")
            print("  Please review the email content and provide the correct name.")
            print("-" * 50)
            print(f"Subject: {subject}\nBody:\n{body.strip()}")
            print("-" * 50)
            
            user_input = input(">>> Enter correct school name (or press Enter to skip): ").strip()
            if not user_input:
                print("  > Skipped. Adding to manual review list.")
                emails_for_manual_review.append({'id': msg_id, 'subject': subject, 'body': body})
                school_info = None
                break
            
            candidate_name = user_input
            location_hint, school_name_to_search = None, candidate_name
            if ' ' in candidate_name.strip():
                parts = candidate_name.strip().split(' ')
                if len(parts) > 1:
                    location_hint, school_name_to_search = parts[0], parts[-1]
                print(f"  > Derived from user input: School Name='{school_name_to_search}', Location Hint='{location_hint}'")
            school_info = get_school_info(school_name_to_search, location_hint)

        if not school_info: continue

        final_name, final_address = school_info['schoolName'], school_info['address']

        if (final_name, final_address) in existing_schools:
            print(f"  ✓ School '{final_name}' with address '{final_address}' already exists. Skipping.")
            continue

        print(f"  ✓ Valid school found: '{final_name}' at '{final_address}'.")
        print("  Calling geocode.sh to add and geocode...")
        
        try:
            # Let geocode.sh handle the addition to coordinates.ndjson
            command = ['bash', geocode_script, '--on-duplicate', 'overwrite', final_name, final_address]
            result = subprocess.run(command, check=True, text=True, capture_output=True)
            print(f"  ✓ Geocode script finished for '{final_name}'.")

            # Now, find the entry geocode.sh just created
            newly_added_entry = None
            for i in range(5): # Retry for 0.5 seconds
                newly_added_entry = find_entry_in_ndjson(coords_file, final_name)
                if newly_added_entry:
                    break
                time.sleep(0.1)

            if newly_added_entry:
                coords = newly_added_entry.get("coordinates", {})
                lng = coords.get("longitude")
                lat = coords.get("latitude")

                if (lng is None or lng == 0) or (lat is None or lat == 0):
                    print(f"  ✗ Geocoding failed for '{final_address}'. Adding to manual lookup file.")
                    with open("manual_address_lookup.txt", "a", encoding="utf-8") as f:
                        f.write(f"{final_address}\n")
                
                internal_entry = newly_added_entry.copy()
                internal_entry['requestContent'] = body
                internal_entry['sender'] = sender
                internal_entry['subject'] = subject
                append_to_ndjson(internal_coords_file, internal_entry)
                print(f"  ✓ Successfully synced to {internal_coords_file}.")
            else:
                print(f"  ✗ ERROR: Could not find '{final_name}' in {coords_file} after geocoding to sync internal file.")

        except subprocess.CalledProcessError as e:
            print(f"  ✗ Geocoding script failed for '{final_name}'. STDERR: {e.stderr.strip()}")
        except Exception as e:
            print(f"  ✗ An unexpected error occurred during geocoding: {e}")

    if emails_for_manual_review:
        manual_file = 'manual_school_entry.json'
        print(f"\n{'='*80}\nManual Review Needed\n{'='*80}")
        print(f"{len(emails_for_manual_review)} emails could not be processed automatically and were saved to '{manual_file}'.")
        with open(manual_file, 'w', encoding='utf-8') as f:
            json.dump(emails_for_manual_review, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*80}\nScript Finished\n{'='*80}")

if __name__ == '__main__':
    main()
