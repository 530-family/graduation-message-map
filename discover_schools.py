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
import uuid
import collections

# Gmail API setup
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Define Suffixes globally
K12_SUFFIXES = ['초등학교', '중학교', '고등학교']
SUFFIX_LIST = K12_SUFFIXES + ['대학교', '영재학교', '국제학교', '아카데미', '스쿨', '유치원']
SUFFIX_REGEX = '|'.join(SUFFIX_LIST)

# Regex patterns
SCHOOL_PATTERN = re.compile(r'[a-zA-Z0-9가-힣]{2,20}(?:\s[a-zA-Z0-9가-힣]{1,20}){0,4}\s*(?:' + SUFFIX_REGEX + r')')
PRIMARY_SCHOOL_PATTERN = re.compile(r'\[학교명 / 소재지\]:\s*(.+?학교)')


def _search_csv(csv_path, school_name, location_hint, school_name_col, address_col, id_col=None, detail_address_col=None, email_subject=None, email_body=None):
    """
    A helper function to search a given CSV file for a school.
    It now uses exact matching and handles ambiguous matches.
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
                    if len(row) > max(school_name_col, address_col, id_col or 0, detail_address_col or 0) and school_name == row[school_name_col]:
                        exact_matches.append(row)
                except IndexError:
                    continue
            
            if not exact_matches:
                return None

            if location_hint:
                hint_matches = [row for row in exact_matches if len(row) > address_col and location_hint in row[address_col]]
                if hint_matches:
                    print(f"  ✓ Found exact match for '{school_name}' with hint '{location_hint}' in {csv_path}")
                    row = hint_matches[0]
                    school_id = row[id_col] if id_col is not None and len(row) > id_col else None
                    detail_address = row[detail_address_col] if detail_address_col is not None and len(row) > detail_address_col else None
                    return {"schoolName": row[school_name_col], "address": format_address(row[address_col]), "id": school_id, "detailAddress": detail_address}

            if len(exact_matches) > 1:
                print(f"\n  ! Ambiguous school name: Found {len(exact_matches)} matches for '{school_name}'.")
                print("  Please review the email content below to make the correct choice.")
                print("-" * 70)
                print(f"  Subject: {email_subject}")
                print(f"  Body (first 200 chars): {email_body[:200].strip()}...")
                print("-" * 70)
                for i, row in enumerate(exact_matches):
                    print(f"    {i+1}: {row[school_name_col]} ({row[address_col]})")
                
                while True:
                    try:
                        choice = input(f">>> Please select the correct school (1-{len(exact_matches)}) or press Enter to skip: ")
                        if not choice:
                            return None
                        choice_idx = int(choice) - 1
                        if 0 <= choice_idx < len(exact_matches):
                            chosen_row = exact_matches[choice_idx]
                            school_id = chosen_row[id_col] if id_col is not None and len(chosen_row) > id_col else None
                            detail_address = chosen_row[detail_address_col] if detail_address_col is not None and len(chosen_row) > detail_address_col else None
                            return {"schoolName": chosen_row[school_name_col], "address": format_address(chosen_row[address_col]), "id": school_id, "detailAddress": detail_address}
                        else:
                            print("  ! Invalid selection. Please try again.")
                    except ValueError:
                        print("  ! Invalid input. Please enter a number.")
            
            # If only one match
            if exact_matches:
                row = exact_matches[0]
                school_id = row[id_col] if id_col is not None and len(row) > id_col else None
                detail_address = row[detail_address_col] if detail_address_col is not None and len(row) > detail_address_col else None
                return {"schoolName": row[school_name_col], "address": format_address(row[address_col]), "id": school_id, "detailAddress": detail_address}
            
            return None
    except FileNotFoundError:
        print(f"  ! CSV file not found at '{csv_path}'.")
        return None
    except Exception as e:
        print(f"  ✗ An error occurred while reading {csv_path}: {e}")
        return None


def get_school_info(school_name, location_hint=None, email_subject=None, email_body=None):
    """
    Gets school information by searching the appropriate CSV file based on the school name's content.
    """
    if not school_name:
        return None

    if any(suffix in school_name for suffix in K12_SUFFIXES):
        print(f"  > '{school_name}' identified as K-12, checking schoolInfo.csv...")
        school_info = _search_csv('public/data/schoolInfo.csv', school_name, location_hint, 3, 10, 2, 11, email_subject, email_body)
        if school_info:
            return school_info
        print(f"  > Not found in schoolInfo.csv, falling back to universityInfo.csv...")
        return _search_csv('public/data/universityInfo.csv', school_name, location_hint, 0, 8, 19, 9, email_subject, email_body)
    else:
        print(f"  > '{school_name}' not identified as K-12, checking universityInfo.csv...")
        uni_info = _search_csv('public/data/universityInfo.csv', school_name, location_hint, 0, 8, 19, 9, email_subject, email_body)
        
        if uni_info and "대학원" not in uni_info['schoolName']:
            return uni_info
        elif uni_info:
            print(f"  > Rejecting match '{uni_info['schoolName']}' because it is a graduate school.")

        print(f"  > Not found in universityInfo.csv or was a grad school, falling back to schoolInfo.csv...")
        return _search_csv('public/data/schoolInfo.csv', school_name, location_hint, 3, 10, 2, 11, email_subject, email_body)


def format_address(address_str):
    """
    This function's only job is to return the clean base address.
    The parenthesized detail is added back in the main function.
    """
    return strip_parentheses_for_comparison(address_str)


def strip_parentheses_for_comparison(address_str):
    """
    Takes a raw address string and returns a clean "base" address 
    by removing postcodes, parenthesized details, and other junk.
    Also normalizes province names.
    """
    if not address_str:
        return ""
    
    # Remove leading postcode
    base_address = re.sub(r'^\d+\s*,\s*', '', address_str).strip()
    
    # Remove any existing parenthesized part and preceding junk
    base_address = re.sub(r'(?:[\",]?\s*,\s*|[\",]?\s*)?\(.*?\),?$', '', base_address).strip()

    # Remove any leftover quotes
    base_address = base_address.replace('"', '').strip()
    
    # Normalize province names to handle administrative changes
    base_address = re.sub(r'강원특별자치도', '강원도', base_address)
    base_address = re.sub(r'전북특별자치도', '전라북도', base_address)

    # Consolidate multiple spaces into a single space
    base_address = re.sub(r'\s+', ' ', base_address).strip()

    return base_address


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
    """Reads the ndjson file and returns a set of unique school names."""
    schools = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if not line.strip(): continue
                try:
                    data = json.loads(line)
                    school_name = data.get('schoolName')
                    if school_name:
                        schools.add(school_name)
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


def get_max_id(file_path):
    """Reads the ndjson file and returns the maximum 'id' found."""
    max_id = 0
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                try:
                    data = json.loads(line)
                    if 'id' in data and isinstance(data['id'], int):
                        max_id = max(max_id, data['id'])
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return max_id


def upsert_ndjson_with_submissions(file_path, new_entry, lookup_key='schoolName'):
    key_to_find = new_entry.get(lookup_key)
    if not key_to_find:
        append_to_ndjson(file_path, new_entry)
        return

    temp_file = file_path + ".tmp"
    found = False
    
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        existing_entries_buffer = [] # Buffer to hold all lines

        try:
            with open(file_path, 'r', encoding='utf-8') as f_in:
                for line in f_in:
                    if not line.strip():
                        existing_entries_buffer.append(line)
                        continue
                    try:
                        data = json.loads(line)
                        if data.get(lookup_key) == key_to_find:
                            # Merge submissions if both existing and new entries have them
                            if 'submissions' in data and 'submissions' in new_entry:
                                data['submissions'].extend(new_entry['submissions'])
                                # Update other top-level fields with new_entry's data (except submissions)
                                for k, v in new_entry.items():
                                    if k != 'submissions':
                                        data[k] = v
                            elif 'submissions' in new_entry: # Existing entry had no submissions, but new one does
                                data['submissions'] = new_entry['submissions']
                            # If new_entry has no submissions, just update other fields; no change to existing 'submissions'
                            else: # If new_entry has no submissions, but other fields updated
                                for k, v in new_entry.items():
                                    if k != 'submissions':
                                        data[k] = v


                            existing_entries_buffer.append(json.dumps(data, ensure_ascii=False) + '\n')
                            found = True
                        else:
                            existing_entries_buffer.append(line)
                    except json.JSONDecodeError:
                        existing_entries_buffer.append(line) # Keep invalid JSON lines as is
        except FileNotFoundError:
            pass # File doesn't exist yet, will be created below

        with open(temp_file, 'w', encoding='utf-8') as f_out:
            for line in existing_entries_buffer:
                f_out.write(line)
            if not found: # If key was not found, append the new entry
                f_out.write(json.dumps(new_entry, ensure_ascii=False) + '\n')
        
        os.replace(temp_file, file_path)

    except Exception as e:
        print(f"  ✗ An error occurred during upsert to {file_path}: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)

def upsert_ndjson(file_path, data_item, lookup_key='schoolName'):
    """
    Updates an entry in an ndjson file if it exists, otherwise appends it.
    The check is based on the lookup_key.
    """
    key_to_find = data_item.get(lookup_key)
    if not key_to_find:
        append_to_ndjson(file_path, data_item)
        return

    temp_file = file_path + ".tmp"
    found = False
    
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        try:
            with open(file_path, 'r', encoding='utf-8') as f_in, open(temp_file, 'w', encoding='utf-8') as f_out:
                for line in f_in:
                    if not line.strip():
                        f_out.write(line)
                        continue
                    try:
                        data = json.loads(line)
                        if data.get(lookup_key) == key_to_find:
                            f_out.write(json.dumps(data_item, ensure_ascii=False) + '\n')
                            found = True
                        else:
                            f_out.write(line)
                    except json.JSONDecodeError:
                        f_out.write(line)
        except FileNotFoundError:
            pass

        if not found:
            with open(temp_file, 'a', encoding='utf-8') as f_out:
                f_out.write(json.dumps(data_item, ensure_ascii=False) + '\n')
        
        os.replace(temp_file, file_path)
    except Exception as e:
        print(f"  ✗ An error occurred during upsert to {file_path}: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)

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


def find_entries_in_ndjson(file_path, school_name):
    """Finds all entries in an ndjson file matching a school name."""
    entries = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                try:
                    data = json.loads(line)
                    if data.get('schoolName') == school_name:
                        entries.append(data)
                except (json.JSONDecodeError, AttributeError):
                    continue
    except FileNotFoundError:
        pass
    return entries


def find_entry_in_ndjson_by_id(file_path, entry_id):
    """Finds a specific entry in an ndjson file by its id."""
    if entry_id is None: return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                try:
                    data = json.loads(line)
                    if data.get('id') == entry_id:
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

    query = f'label:졸업식 to:me after:{int(start_dt_obj.timestamp())}'
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
            school_info = get_school_info(school_name_to_search, location_hint, email_subject=subject, email_body=body)

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
            school_info = get_school_info(school_name_to_search, location_hint, email_subject=subject, email_body=body)

        if not school_info:
            if candidate_name:
                print(f"  > Could not validate '{candidate_name}'. Adding with empty address as requested.")
                school_info = {'schoolName': candidate_name.strip(), 'address': '', 'id': None, 'detailAddress': None}
            else:
                continue

        final_name, final_address = school_info['schoolName'], school_info['address']
        should_overwrite = False # Default to append for new schools
        matching_entry = None

        if final_name in existing_schools:
            all_entries_with_name = find_entries_in_ndjson(coords_file, final_name)
            
            for entry in all_entries_with_name:
                existing_address_base = strip_parentheses_for_comparison(entry.get('address', ''))
                new_address_base = strip_parentheses_for_comparison(final_address)
                print(f"  > Comparing base address for '{final_name}': new='{new_address_base}', old='{existing_address_base}'")
                if existing_address_base and new_address_base and existing_address_base == new_address_base:
                    matching_entry = entry
                    break
        
        if matching_entry: # Found a school with same name and full address
            should_overwrite = True # This will be an update/overwrite
            
            # Check for duplicate submission (same schoolName, same full address, same sender)
            existing_internal_entry = find_entry_in_ndjson_by_id(internal_coords_file, matching_entry.get('id'))
            if existing_internal_entry:
                senders_in_submissions = [sub.get('sender') for sub in existing_internal_entry.get('submissions', [])]
                if sender in senders_in_submissions:
                     print(f"  ✓ School '{final_name}' with same address and submission from sender '{sender}' already exists. Skipping.")
                     continue # Skip this email completely
            
            # If we are here, it's an existing school with same name & full address, but a new submission.
            # It should proceed to geocode and update.
            print(f"  ✓ School '{final_name}' with same address found. Proceeding to update with new submission.")
        else: # No school found with this name and full address
            if final_name in existing_schools:
                # This implies a school with same name exists, but with a different full address.
                # So it's a new entry, not an update.
                print(f"  > School '{final_name}' found, but with different full address. Creating new entry.")
            else:
                 print(f"  > New school '{final_name}'. Creating new entry.")
            should_overwrite = False # This will be a new entry (append)

        print(f"  ✓ Valid school found: '{final_name}' at '{final_address}'.")
        print("  Calling geocode.sh to add and geocode...")
        
        try:
            command = ['bash', geocode_script, final_name, final_address]
            result = subprocess.run(command, check=True, text=True, capture_output=True)
            print(f"  ✓ Geocode script finished for '{final_name}'.")

            try:
                newly_added_entry = json.loads(result.stdout)
            except json.JSONDecodeError:
                print(f"  ✗ Failed to parse JSON from geocode.sh output: {result.stdout}")
                continue
            
            geocoding_successful = False
            if newly_added_entry:
                new_coords = newly_added_entry.get("coordinates", {})
                new_lng = new_coords.get("longitude")
                new_lat = new_coords.get("latitude")
                geocoding_successful = (new_lng is not None and new_lng != 0) and (new_lat is not None and new_lat != 0)

            # Preserve old coordinates if geocoding failed on an update
            if not geocoding_successful and should_overwrite and matching_entry:
                old_coords = matching_entry.get("coordinates", {})
                old_lng = old_coords.get("longitude")
                old_lat = old_coords.get("latitude")
                if (old_lng is not None and old_lng != 0) and (old_lat is not None and old_lat != 0):
                    print("  ! Geocoding API failed on update. Preserving old valid coordinates.")
                    newly_added_entry["coordinates"] = old_coords

            school_id_from_csv = school_info.get('id')
            newly_added_entry_id = None

            if should_overwrite: # It's an update
                existing_entry_in_coords = find_entry_in_ndjson(coords_file, final_name)
                if existing_entry_in_coords and 'id' in existing_entry_in_coords:
                    newly_added_entry_id = existing_entry_in_coords['id']
                else:
                    # Fallback if somehow existing entry doesn't have an ID or find_entry_in_ndjson fails
                    newly_added_entry_id = get_max_id(coords_file) + 1
                    print(f"  ! Fallback auto-incremental ID generated for update: {newly_added_entry_id}")
            else: # It's a new entry (append)
                newly_added_entry_id = get_max_id(coords_file) + 1
            
            # Reconstruct final address by appending the detail address part
            final_address_complete = newly_added_entry.get('address')
            detail_address = school_info.get('detailAddress')
            if detail_address:
                # Clean the detail address itself: e.g., "(달동/동평중학교)" -> "달동"
                cleaned_detail = re.sub(r'[\(\)]', '', detail_address)
                first_part = re.split(r'[,\/]', cleaned_detail)[0].strip()
                if first_part:
                     final_address_complete += f" ({first_part})"

            # Reconstruct newly_added_entry to ensure order and assign the determined ID
            ordered_entry = collections.OrderedDict()
            ordered_entry['id'] = newly_added_entry_id
            ordered_entry['schoolName'] = newly_added_entry.get('schoolName')
            ordered_entry['address'] = final_address_complete
            ordered_entry['coordinates'] = newly_added_entry.get('coordinates')
            newly_added_entry = ordered_entry

            if should_overwrite:
                upsert_ndjson(coords_file, newly_added_entry)
            else:
                append_to_ndjson(coords_file, newly_added_entry)
            existing_schools.add(final_name)

            coords = newly_added_entry.get("coordinates", {})
            lng = coords.get("longitude")
            lat = coords.get("latitude")

            error_status = newly_added_entry.get('errorStatus', 'N/A')
            if (lng is None or lng == 0) or (lat is None or lat == 0):
                print(f"  ✗ Geocoding failed for '{newly_added_entry.get('address', final_address)}' (Status: {error_status}). Adding to manual lookup file.")
                with open("manual_address_lookup.txt", "a", encoding="utf-8") as f:
                    f.write(f"{newly_added_entry.get('address', final_address)}\n")
            
            internal_entry = newly_added_entry.copy() # This already has id, schoolName, address, coordinates

            current_submission = {
                "sender": sender,
                "subject": subject,
                "body": body
            }
            internal_entry['submissions'] = [current_submission]
            
            if should_overwrite:
                upsert_ndjson_with_submissions(internal_coords_file, internal_entry)
            else:
                append_to_ndjson(internal_coords_file, internal_entry)
            print(f"  ✓ Successfully synced to {internal_coords_file}.")

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
