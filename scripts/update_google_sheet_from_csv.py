"""
Update Google Sheet from CSV file.
Matches by School Name (F column) + Address (G column) and updates Status (D column) and URL (M column).
"""

import csv
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

# Configuration
SPREADSHEET_ID = "1_6d7WlgCPJFVF3E6uiRWQyhc_M-vCwwL_-HBlXcRvPI"  # Google Sheet ID
SHEET_NAME = "requests"  # Use this specific sheet name
CSV_PATH = r"C:\Users\wjsdj\Downloads\Telegram Desktop\0114results.csv"

# Column indices (0-based)
# Based on: F=School(5), G=Address(6), D=Status(3), M=URL(12)
COL_SCHOOL = 5      # F column
COL_ADDRESS = 6     # G column
COL_STATUS = 3      # D column
COL_URL = 12        # M column

# OAuth2 scopes
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


def authenticate():
    """Authenticate using OAuth2 credentials.json"""
    creds = None
    token_path = 'token.pickle'

    # Load existing token if available
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    # If no valid credentials, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Use credentials.json from parent directory
            cred_path = os.path.join(os.path.dirname(__file__), '..', 'credentials.json')
            flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials for future use
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

    return creds


def read_csv_data(csv_path):
    """Read CSV and return dict mapping (school_name, address) -> (status, url)"""
    data = {}

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            school = row.get('School', '').strip()
            status = row.get('Status', '').strip()
            url = row.get('URL', '').strip()
            address = row.get('Address', '').strip()

            if school and address:
                key = (school, address)
                # Convert "Sent" to "전송완료"
                display_status = "전송완료" if status == "Sent" else status
                data[key] = (display_status, url)

    print(f"CSV에서 {len(data)}개 학교 데이터를 읽었습니다.")
    return data


def update_sheet(service, spreadsheet_id, sheet_name, csv_data):
    """Update Google Sheet with CSV data"""
    from googleapiclient.discovery import build

    sheets = build('sheets', 'v4', credentials=service)

    # Get sheet metadata to find the actual sheet name
    spreadsheet = sheets.spreadsheets().get(
        spreadsheetId=spreadsheet_id
    ).execute()

    # List all sheets
    sheet_list = spreadsheet.get('sheets', [])
    print(f"\n발견된 시트 목록:")
    for i, s in enumerate(sheet_list):
        title = s.get('properties', {}).get('title', 'Unknown')
        print(f"  {i+1}. {title}")

    # Use first sheet if sheet_name not found
    actual_sheet_name = sheet_name
    sheet_titles = [s.get('properties', {}).get('title') for s in sheet_list]

    if sheet_name not in sheet_titles and sheet_list:
        actual_sheet_name = sheet_list[0].get('properties', {}).get('title')
        print(f"\n'{sheet_name}' 시트를 찾을 수 없어 '{actual_sheet_name}'을 사용합니다.")

    print(f"\n사용할 시트: {actual_sheet_name}")

    # Get all data from the sheet
    result = sheets.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f'{actual_sheet_name}!A:Z',
        valueRenderOption='UNFORMATTED_VALUE'
    ).execute()

    rows = result.get('values', [])

    if not rows:
        print("시트에 데이터가 없습니다.")
        return

    # Find rows that need updates
    updates = []
    matched_count = 0

    # Skip header row (start from index 1)
    for row_idx in range(1, len(rows)):
        row = rows[row_idx]

        # Ensure row has enough columns
        while len(row) <= max(COL_SCHOOL, COL_ADDRESS, COL_STATUS, COL_URL):
            row.append('')

        school = row[COL_SCHOOL].strip() if COL_SCHOOL < len(row) else ''
        address = row[COL_ADDRESS].strip() if COL_ADDRESS < len(row) else ''

        if not school or not address:
            continue

        key = (school, address)

        if key in csv_data:
            status, url = csv_data[key]

            # Only add if values are different
            current_status = row[COL_STATUS].strip() if COL_STATUS < len(row) else ''
            current_url = row[COL_URL].strip() if COL_URL < len(row) else ''

            if current_status != status or current_url != url:
                updates.append({
                    'row': row_idx + 1,  # 1-indexed for API
                    'status': status,
                    'url': url,
                    'school': school
                })
                matched_count += 1

    # Apply updates in batch
    if updates:
        # Build update data
        update_data = []

        for update in updates:
            row_num = update['row']
            # Update status (D column)
            update_data.append({
                'range': f'{actual_sheet_name}!D{row_num}',
                'values': [[update['status']]]
            })
            # Update URL (M column)
            update_data.append({
                'range': f'{actual_sheet_name}!M{row_num}',
                'values': [[update['url']]]
            })

        # Batch update
        body = {
            'valueInputOption': 'USER_ENTERED',
            'data': update_data
        }

        sheets.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body
        ).execute()

        print(f"\n{len(updates)}개 행을 업데이트했습니다:")
        for u in updates[:10]:
            print(f"  - {u['school']}: {u['status']}")
        if len(updates) > 10:
            print(f"  ... 외 {len(updates) - 10}개")
    else:
        print("\n업데이트할 데이터가 없습니다. 모든 행이 이미 최신 상태입니다.")

    # Summary
    total_with_data = sum(1 for r in rows[1:] if len(r) > COL_SCHOOL and r[COL_SCHOOL].strip())
    print(f"\n요약:")
    print(f"  - 전체 학교: {total_with_data}개")
    print(f"  - 매칭됨: {matched_count}개")
    print(f"  - 업데이트됨: {len(updates)}개")

    # Find unmatched schools
    csv_schools = set(csv_data.keys())
    sheet_schools = set()
    for row_idx in range(1, len(rows)):
        row = rows[row_idx]
        while len(row) <= max(COL_SCHOOL, COL_ADDRESS):
            row.append('')
        school = row[COL_SCHOOL].strip() if COL_SCHOOL < len(row) else ''
        address = row[COL_ADDRESS].strip() if COL_ADDRESS < len(row) else ''
        if school and address:
            sheet_schools.add((school, address))

    unmatched = csv_schools - sheet_schools
    if unmatched:
        print(f"\n=== 매칭 안 된 학교 ({len(unmatched)}개) ===")
        for school, address in sorted(unmatched):
            print(f"  - {school}")
            print(f"    주소: {address}")


def main():
    """Main entry point"""
    print("=" * 50)
    print("구글 시트 CSV 업데이트 도구")
    print("=" * 50)

    # Check configuration
    if SPREADSHEET_ID == "YOUR_SPREADSHEET_ID_HERE":
        print("\n오류: SPREADSHEET_ID를 설정해주세요.")
        print("스크립트 상단의 SPREADSHEET_ID 변수를 수정하세요.")
        print("URL: https://docs.google.com/spreadsheets/d/[SPREADSHEET_ID]/edit")
        return

    # Check CSV file exists
    if not os.path.exists(CSV_PATH):
        print(f"\n오류: CSV 파일을 찾을 수 없습니다: {CSV_PATH}")
        return

    # Authenticate
    print("\n구글 인증 중...")
    creds = authenticate()
    print("인증 완료!")

    # Read CSV
    print(f"\nCSV 파일 읽는 중: {CSV_PATH}")
    csv_data = read_csv_data(CSV_PATH)

    # Update sheet
    print(f"\n구글 시트 업데이트 중...")
    print(f"Spreadsheet ID: {SPREADSHEET_ID}")
    print(f"Sheet Name: {SHEET_NAME}")
    update_sheet(creds, SPREADSHEET_ID, SHEET_NAME, csv_data)

    print("\n완료!")


if __name__ == '__main__':
    main()
