import base64
import email
import json
import os
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

def get_school_search_names(school_name):
    search_names = []
    if school_name.endswith("중학교"):
        # For "OO중학교", add "OO중" and "OO"
        search_names.append(school_name[:-2])
        search_names.append(school_name[:-3])
    elif school_name.endswith("고등학교"):
        # For "XX고등학교", add "XX고" and "XX"
        search_names.append(school_name[:-3])
        search_names.append(school_name[:-4])
    else:
        search_names.append(school_name)
    return search_names

def main():
    service = get_gmail_service()
    updated_data = []

    try:
        with open('public/data/coordinates.ndjson', 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print("Error: public/data/coordinates.ndjson not found.")
        return

    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        try:
            data = json.loads(line)
            school_name = data.get('schoolName')
            
            content = ""
            if school_name:
                search_names = get_school_search_names(school_name)
                messages = []
                queries_tried = []
                for search_name in search_names:
                    query = f'label:졸업식 {search_name}'
                    queries_tried.append(query)
                    response = service.users().messages().list(userId='me', q=query).execute()
                    messages = response.get('messages', [])
                    if messages:
                        break

                if messages:
                    message_id = messages[0]['id']
                    message_data = service.users().messages().get(userId='me', id=message_id, format='raw').execute()
                    
                    raw_email = base64.urlsafe_b64decode(message_data['raw'].encode('ASCII'))
                    email_message = email.message_from_bytes(raw_email)
                    
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
                    
                    
                    drive_link_found = False
                    if content:
                        soup_for_links = BeautifulSoup(payload, 'html.parser')
                        for link in soup_for_links.find_all('a'):
                            href = link.get('href')
                            if href and 'drive.google.com' in href:
                                drive_link_found = True
                                break
                    
                    if drive_link_found:
                        data['done'] = True
                    
                    
                    print(f"Successfully extracted message for {school_name}")
                else:
                    print(f"No message found for {school_name} (queries: {queries_tried})")

            data['requestContent'] = content.strip()
            updated_data.append(data)

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            print(f"Problematic JSON string: {line}")

    with open('public/data/coordinates.ndjson', 'w', encoding='utf-8') as f:
        for item in updated_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    
    print("Finished updating public/data/coordinates.ndjson")

if __name__ == '__main__':
    main()
