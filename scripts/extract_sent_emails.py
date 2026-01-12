"""
Extract emails with '졸업식 전송완료' label and save school names with YouTube URLs to CSV.
"""
import base64
import email
import csv
import re
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from bs4 import BeautifulSoup

# Gmail API setup
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def get_gmail_service():
    """Authenticate and return Gmail service."""
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


def extract_youtube_urls(text):
    """Extract YouTube URLs from text (both youtu.be and youtube.com formats)."""
    # Pattern for youtu.be URLs like https://youtu.be/MPglgYJXiSQ
    youtu_be_pattern = r'https://youtu\.be/([a-zA-Z0-9_-]+)'
    # Pattern for youtube.com URLs
    youtube_com_pattern = r'https://www\.youtube\.com/watch\?v=([a-zA-Z0-9_-]+)'
    # Pattern for youtube.com/short URLs
    youtube_short_pattern = r'https://www\.youtube\.com/shorts/([a-zA-Z0-9_-]+)'

    urls = []
    urls.extend(re.findall(youtu_be_pattern, text))
    urls.extend(re.findall(youtube_com_pattern, text))
    urls.extend(re.findall(youtube_short_pattern, text))

    # Convert video IDs to full URLs
    full_urls = []
    for video_id in urls:
        full_urls.append(f'https://youtu.be/{video_id}')

    return full_urls


def extract_school_name_from_subject(subject):
    """
    Extract school name from email subject.
    Common patterns:
    - [학교명] 졸업식 전송완료
    - 학교명 졸업식 축하 영상 전송완료
    - Re: 학교명 졸업식
    """
    # Remove common prefixes
    subject = subject.strip()
    for prefix in ['Re:', 'Fw:', 'FW:', 'RE:', 'FW']:
        if subject.startswith(prefix):
            subject = subject[len(prefix):].strip()

    # Pattern 1: [학교명] format
    bracket_match = re.search(r'\[([^\]]+(?:학교|대학교))\]', subject)
    if bracket_match:
        return bracket_match.group(1)

    # Pattern 2: Extract school name ending with school suffix
    # Match patterns like "신한고등학교", "서울중학교", "한국대학교"
    school_suffix_pattern = r'([가-힣]+(?:초등학교|중학교|고등학교|대학교|대))'
    school_match = re.search(school_suffix_pattern, subject)
    if school_match:
        return school_match.group(1)

    return None


def extract_school_name_from_body(body_text):
    """
    Extract school name from email body.
    Looks for patterns like:
    - "신한고등학교 졸업식 축하 영상입니다."
    - "보내는 학교: 신한고등학교"
    - "학교명: 신한고"
    """
    # Remove extra whitespace
    body_text = ' '.join(body_text.split())

    # Pattern 1: "학교명: 신한고등학교" format
    school_name_pattern = r'학교명\s*[:]\s*([가-힣]+(?:초등학교|중학교|고등학교|대학교|대|고|중))'
    match = re.search(school_name_pattern, body_text)
    if match:
        return match.group(1)

    # Pattern 2: School name at the beginning followed by 졸업식
    school_prefix_pattern = r'^([가-힣]+(?:초등학교|중학교|고등학교|대학교|대))\s*졸업식'
    match = re.search(school_prefix_pattern, body_text)
    if match:
        return match.group(1)

    # Pattern 3: First occurrence of full school name
    full_school_pattern = r'([가-힣]{2,}(?:초등학교|중학교|고등학교|대학교))'
    matches = re.findall(full_school_pattern, body_text)
    if matches:
        # Return the first match
        return matches[0]

    return None


def get_email_body(message):
    """Extract email body text from message."""
    payload = message.get('payload', {})
    body_text = ""

    if 'parts' in payload:
        for part in payload['parts']:
            if part.get('mimeType') == 'text/html':
                data = part.get('body', {}).get('data', '')
                if data:
                    decoded = base64.urlsafe_b64decode(data.encode('ASCII'))
                    soup = BeautifulSoup(decoded, 'html.parser')
                    body_text += soup.get_text() + ' '
            elif part.get('mimeType') == 'text/plain':
                data = part.get('body', {}).get('data', '')
                if data:
                    decoded = base64.urlsafe_b64decode(data.encode('ASCII'))
                    body_text += decoded.decode('utf-8', errors='ignore') + ' '
    else:
        # Single part message
        data = payload.get('body', {}).get('data', '')
        if data:
            decoded = base64.urlsafe_b64decode(data.encode('ASCII'))
            body_text = decoded.decode('utf-8', errors='ignore')

    return body_text


def main():
    """Main function to extract and save data."""
    print("Authenticating with Gmail API...")
    service = get_gmail_service()
    print("Authentication successful!")

    # Search for emails with '졸업식 전송완료' label from j7840790@gmail.com
    query = 'from:j7840790@gmail.com label:졸업식 전송완료'
    print(f"\nSearching for emails with query: {query}")

    results = []
    page_token = None

    while True:
        response = service.users().messages().list(
            userId='me',
            q=query,
            pageToken=page_token,
            maxResults=100
        ).execute()

        messages = response.get('messages', [])
        print(f"Found {len(messages)} emails on this page...")

        for msg in messages:
            msg_id = msg['id']
            message = service.users().messages().get(
                userId='me',
                id=msg_id,
                format='metadata',
                metadataHeaders=['Subject', 'To', 'Date']
            ).execute()

            # Get headers
            headers = message.get('payload', {}).get('headers', [])
            subject = ""
            to_addr = ""
            date = ""

            for header in headers:
                if header['name'] == 'Subject':
                    subject = header['value']
                elif header['name'] == 'To':
                    to_addr = header['value']
                elif header['name'] == 'Date':
                    date = header['value']

            # Get full message with body
            full_message = service.users().messages().get(
                userId='me',
                id=msg_id,
                format='full'
            ).execute()

            body_text = get_email_body(full_message)

            # Extract school name
            school_name = extract_school_name_from_subject(subject)
            if not school_name:
                school_name = extract_school_name_from_body(body_text)

            # Extract YouTube URLs
            youtube_urls = extract_youtube_urls(body_text)
            youtube_url = youtube_urls[0] if youtube_urls else ""

            results.append({
                '학교명': school_name or '(추출 실패)',
                '받는 사람': to_addr,
                '날짜': date,
                '제목': subject,
                'YouTube URL': youtube_url,
                '이메일 ID': msg_id
            })

            print(f"  - {school_name or '(미확인)'}: {youtube_url if youtube_url else '(URL 없음)'}")

        page_token = response.get('nextPageToken')
        if not page_token:
            break

    print(f"\n총 {len(results)}개의 이메일을 찾았습니다.")

    # Save to CSV
    output_file = '../graduation_sent_emails.csv'
    with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
        fieldnames = ['학교명', 'YouTube URL', '받는 사람', '날짜', '제목', '이메일 ID']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for result in results:
            writer.writerow({
                '학교명': result['학교명'],
                'YouTube URL': result['YouTube URL'],
                '받는 사람': result['받는 사람'],
                '날짜': result['날짜'],
                '제목': result['제목'],
                '이메일 ID': result['이메일 ID']
            })

    print(f"\nCSV 파일 저장 완료: {output_file}")

    # Print summary
    schools_with_url = [r for r in results if r['YouTube URL']]
    schools_without_url = [r for r in results if not r['YouTube URL']]
    school_extraction_failed = [r for r in results if r['학교명'] == '(추출 실패)']

    print(f"\n=== 요약 ===")
    print(f"전체 이메일: {len(results)}개")
    print(f"학교명 추출 성공: {len(results) - len(school_extraction_failed)}개")
    print(f"학교명 추출 실패: {len(school_extraction_failed)}개")
    print(f"YouTube URL 발견: {len(schools_with_url)}개")
    print(f"URL 미발견: {len(schools_without_url)}개")

    if school_extraction_failed:
        print(f"\n학교명 추출 실패 목록:")
        for r in school_extraction_failed:
            print(f"  - 제목: {r['제목']}")


if __name__ == '__main__':
    main()
