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
    parser.add_argument('--skip-gmail', action='store_true', help='Skip Gmail API calls if requestContent exists.')
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

    internal_data = []

    for i, data in enumerate(original_data):
        internal_item = data.copy()
        school_name = internal_item.get('schoolName')

        # When skipping Gmail, we check existing content for the link
        if args.skip_gmail:
            if internal_item.get('requestContent') and 'drive.google.com' in internal_item['requestContent']:
                print(f"Skipping Gmail lookup for {school_name}, Drive link found in existing content.")
                internal_item['done'] = True
                original_data[i]['done'] = True
            else:
                 print(f"Skipping Gmail lookup for {school_name} (content exists or flag set).")
            internal_data.append(internal_item)
            continue
        
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
                
                payload = None
                if email_message.is_multipart():
                    for part in email_message.walk():
                        if part.get_content_type() == "text/html":
                            payload = part.get_payload(decode=True)
                            soup = BeautifulSoup(payload, 'html.parser')
                            content = soup.get_text()
                            break
                else:
                    if email_message.get_content_type() == "text/html":
                        payload = email_message.get_payload(decode=True)
                        soup = BeautifulSoup(payload, 'html.parser')
                        content = soup.get_text()
                
                print(f"Successfully extracted content from oldest email for {school_name}")

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
                    print(f"Google Drive link found in newest email for {school_name}. Marking as 'done'.")
                    internal_item['done'] = True
                    original_data[i]['done'] = True
            else:
                print(f"No message found for {school_name} (tried {len(queries)} queries)")

        internal_item['requestContent'] = content.strip()
        internal_data.append(internal_item)

    # Write to the internal data file
    with open('public/data/coordinates.internal.ndjson', 'w', encoding='utf-8') as f:
        for item in internal_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    print("Finished writing to public/data/coordinates.internal.ndjson")

    # Write updates (specifically the 'done' flag) back to the main coordinates file
    with open('public/data/coordinates.ndjson', 'w', encoding='utf-8') as f:
        for item in original_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    
    print("Finished updating public/data/coordinates.ndjson with 'done' status.")

if __name__ == '__main__':
    main()