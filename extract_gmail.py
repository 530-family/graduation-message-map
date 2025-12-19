import base64
import email
import json
import os
import argparse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from bs4 import BeautifulSoup

# Gmail API setup
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
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

def get_school_search_queries(school_name):
    """
    Generate search queries in priority order:
    1. Quoted full form (e.g., "신한고등학교") 
    2. Quoted short form (e.g., "신한고") 
    3. Quoted shorter form (e.g., "신한")
    4. Unquoted shorter form (e.g., 신한)
    5. Unquoted short form (e.g., 신한고)
    """
    queries = []
    if school_name.endswith("중학교"):
        short_form = school_name[:-2]  # e.g., "신한중"
        shorter_form = school_name[:-3]  # e.g., "신한"
        queries.append(f'label:졸업식 to:me "{short_form}"')
        queries.append(f'label:졸업식 to:me "{school_name}"')
        queries.append(f'label:졸업식 to:me "{shorter_form}"')
        queries.append(f'label:졸업식 to:me {shorter_form}')
        queries.append(f'label:졸업식 to:me {short_form}')
    elif school_name.endswith("고등학교"):
        short_form = school_name[:-3]  # e.g., "신한고"
        shorter_form = school_name[:-4]  # e.g., "신한"
        queries.append(f'label:졸업식 to:me "{short_form}"')
        queries.append(f'label:졸업식 to:me "{school_name}"')
        queries.append(f'label:졸업식 to:me "{shorter_form}"')
        queries.append(f'label:졸업식 to:me {shorter_form}')
        queries.append(f'label:졸업식 to:me {short_form}')
    else:
        queries.append(f'label:졸업식 to:me "{school_name}"')
        queries.append(f'label:졸업식 to:me {school_name}')
    return queries

def main():
    parser = argparse.ArgumentParser(description='Extract Gmail messages and update coordinates data.')
    parser.add_argument('--skip-gmail', action='store_true', help='Skip Gmail API calls and use existing internal data.')
    parser.add_argument('--skip-existing', action='store_true', help='Skip Gmail API calls if requestContent already exists.')
    args = parser.parse_args()

    service = None
    if not args.skip_gmail:
        service = get_gmail_service()

    original_data = []
    try:
        with open('public/data/coordinates.ndjson', 'r', encoding='utf-8') as f:
            original_data = [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        print("Error: public/data/coordinates.ndjson not found.")
        return
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from coordinates.ndjson: {e}")
        return

    # Load existing internal data if it exists and create backup
    existing_internal_data = {}
    try:
        import shutil
        from datetime import datetime

        # Create backup before processing
        if os.path.exists('public/data/coordinates.internal.ndjson'):
            backup_name = f'public/data/coordinates.internal.ndjson.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            shutil.copy2('public/data/coordinates.internal.ndjson', backup_name)
            print(f"Created backup: {backup_name}")

        with open('public/data/coordinates.internal.ndjson', 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    # Use id as key to map existing internal data
                    existing_internal_data[item.get('id')] = item
        print(f"Loaded {len(existing_internal_data)} existing internal records.")
    except FileNotFoundError:
        print("No existing internal data found, will create new file.")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from coordinates.internal.ndjson: {e}")

    internal_data = []
    schools_needing_manual_input = []  # Track schools that need manual data entry

    for i, data in enumerate(original_data):
        school_id = data.get('id')
        school_name = data.get('schoolName')

        # When skipping Gmail, preserve existing internal data
        if args.skip_gmail:
            # Check if we have existing internal data for this school
            if school_id in existing_internal_data:
                internal_item = existing_internal_data[school_id].copy()
                print(f"Skipping Gmail lookup for {school_name}, using existing internal data.")

                # Check if there's a Drive link in existing content and update status
                if internal_item.get('requestContent') and 'drive.google.com' in internal_item['requestContent']:
                    if not internal_item.get('status'):
                        internal_item['status'] = 'sent'
                        original_data[i]['status'] = 'sent'
                        print(f"  -> Drive link found, marked as 'sent'.")
            else:
                # No existing internal data, just copy from original
                internal_item = data.copy()
                print(f"Skipping Gmail lookup for {school_name}, no existing internal data found.")

            internal_data.append(internal_item)
            continue

        # Not skipping Gmail - create new internal_item from original data
        internal_item = data.copy()

        # Check if we should skip this school because it already has requestContent
        # IMPORTANT: Check BEFORE making any Gmail API calls
        if args.skip_existing and school_id in existing_internal_data:
            existing_content = existing_internal_data[school_id].get('requestContent', '').strip()
            if existing_content:  # Only skip if there's actual content (not empty string)
                print(f"Skipping {school_name} - requestContent already exists (length: {len(existing_content)} chars).")
                internal_item = existing_internal_data[school_id].copy()

                # Still check for Drive link and update status if needed
                if 'drive.google.com' in existing_content:
                    if not internal_item.get('status'):
                        internal_item['status'] = 'sent'
                        original_data[i]['status'] = 'sent'
                        print(f"  -> Drive link found, marked as 'sent'.")

                internal_data.append(internal_item)
                continue
            else:
                print(f"Processing {school_name} - requestContent is empty, will fetch from Gmail.")

        # Only proceed with Gmail API calls if we haven't skipped above
        content = ""
        if school_name and service:
            queries = get_school_search_queries(school_name)
            messages = []
            for query in queries:
                response = service.users().messages().list(userId='me', q=query).execute()
                messages = response.get('messages', [])
                if messages:
                    print(f"Found messages for {school_name} using query: {query}")
                    break

            if messages:
                # 1. Process oldest email for requestContent
                oldest_message_id = messages[-1]['id']
                message_data = service.users().messages().get(userId='me', id=oldest_message_id, format='raw').execute()
                raw_email = base64.urlsafe_b64decode(message_data['raw'].encode('ASCII'))
                email_message = email.message_from_bytes(raw_email)
                
                body_html = None
                body_plain = None

                if email_message.is_multipart():
                    for part in email_message.walk():
                        content_type = part.get_content_type()
                        # Prefer HTML part, but only if we haven't found one yet
                        if content_type == "text/html" and not body_html:
                            payload = part.get_payload(decode=True)
                            if payload and payload.strip():
                                body_html = payload
                        # Also look for plain text part
                        elif content_type == "text/plain" and not body_plain:
                            payload = part.get_payload(decode=True)
                            if payload and payload.strip():
                                body_plain = payload
                else: # Not multipart
                    content_type = email_message.get_content_type()
                    if content_type == "text/html":
                        payload = email_message.get_payload(decode=True)
                        if payload and payload.strip():
                            body_html = payload
                    elif content_type == "text/plain":
                        payload = email_message.get_payload(decode=True)
                        if payload and payload.strip():
                            body_plain = payload

                # Prioritize HTML content, but fallback to plain text
                if body_html:
                    soup = BeautifulSoup(body_html, 'html.parser')
                    content = soup.get_text()
                    print(f"  -> Successfully extracted content from HTML part.")
                elif body_plain:
                    content = body_plain.decode('utf-8', errors='ignore')
                    print(f"  -> Successfully extracted content from plain text part.")
                else:
                    print(f"  -> WARNING: Could not extract readable content for {school_name}.")

                # 2. Process newest email to check for Google Drive link
                newest_message_id = messages[0]['id']
                message_data = service.users().messages().get(userId='me', id=newest_message_id, format='raw').execute()
                raw_email = base64.urlsafe_b64decode(message_data['raw'].encode('ASCII'))
                email_message = email.message_from_bytes(raw_email)

                drive_link_found = False
                payload_for_links = None
                if email_message.is_multipart():
                    for part in email_message.walk():
                        if part.get_content_type() == "text/html":
                            payload_for_links = part.get_payload(decode=True)
                            break
                else:
                    if email_message.get_content_type() == "text/html":
                        payload_for_links = email_message.get_payload(decode=True)
                
                if payload_for_links:
                    soup_for_links = BeautifulSoup(payload_for_links, 'html.parser')
                    for link in soup_for_links.find_all('a'):
                        href = link.get('href')
                        if href and 'drive.google.com' in href:
                            drive_link_found = True
                            break
                
                if drive_link_found:
                    print(f"Google Drive link found in newest email for {school_name}. Marking as 'sent'.")
                    internal_item['status'] = 'sent'
                    original_data[i]['status'] = 'sent'
            else:
                print(f"No message found for {school_name} (tried {len(queries)} queries)")
                schools_needing_manual_input.append({
                    'id': school_id,
                    'schoolName': school_name,
                    'address': data.get('address', '')
                })

        internal_item['requestContent'] = content.strip()
        internal_data.append(internal_item)

    # Write to the internal data file
    with open('public/data/coordinates.internal.ndjson', 'w', encoding='utf-8') as f:
        for item in internal_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    print("Finished writing to public/data/coordinates.internal.ndjson")

    # Write updates (specifically the 'status' field) back to the main coordinates file
    with open('public/data/coordinates.ndjson', 'w', encoding='utf-8') as f:
        for item in original_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    print("Finished updating public/data/coordinates.ndjson with status.")

    # Print summary of schools needing manual input
    if schools_needing_manual_input:
        print("\n" + "="*80)
        print("SCHOOLS REQUIRING MANUAL DATA ENTRY (Email not found)")
        print("="*80)
        for school in schools_needing_manual_input:
            print(f"\nID: {school['id']}")
            print(f"School Name: {school['schoolName']}")
            print(f"Address: {school['address']}")
            print("-" * 80)

        print(f"\nTotal schools needing manual input: {len(schools_needing_manual_input)}")

        # Save to a separate file for easy reference
        with open('public/data/manual_input_needed.json', 'w', encoding='utf-8') as f:
            json.dump(schools_needing_manual_input, f, ensure_ascii=False, indent=2)
        print("List saved to: public/data/manual_input_needed.json")
    else:
        print("\n✓ All schools have email data - no manual input required!")

if __name__ == '__main__':
    main()