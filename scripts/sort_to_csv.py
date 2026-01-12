import json
import re
import csv
from datetime import datetime
import sys

# UTF-8 출력 설정
sys.stdout.reconfigure(encoding='utf-8')

# 파일 읽기
with open('../public/data/coordinates.ndjson', 'r', encoding='utf-8') as f:
    data = [json.loads(line.strip()) for line in f if line.strip()]

def extract_graduation_date(content):
    if not content:
        return None

    # 명시적인 연도가 있는 패턴
    patterns_with_year = [
        r'(\d{4})[년\.\-](\d{1,2})[월\.\-](\d{1,2})',
        r'(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})',
    ]

    for pattern in patterns_with_year:
        match = re.search(pattern, content)
        if match:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            # 2025년 1-2월은 2026년으로 보정
            if year == 2025 and month in [1, 2]:
                year = 2026
            try:
                return datetime(year, month, day)
            except ValueError:
                continue

    # 연도가 없는 패턴 - 더 단순하게
    patterns_without_year = [
        r'(\d{1,2})월\s*(\d{1,2})일',
        r'(\d{1,2})\s*월\s*(\d{1,2})\s*일',
        r'12월\s*(3[01]|[12]\d)',
    ]

    for pattern in patterns_without_year:
        match = re.search(pattern, content)
        if match:
            month, day = int(match.group(1)), int(match.group(2))
            # 11월, 12월은 2025년, 그 외는 2026년
            if month in [11, 12]:
                year = 2025
            else:
                year = 2026
            try:
                return datetime(year, month, day)
            except ValueError:
                continue

    return None

# 날짜 추출 및 분류
with_dates = []
without_dates = []

for item in data:
    content = item.get('requestContent', '')
    id_val = item.get('id', 0)

    grad_date = extract_graduation_date(content)

    if grad_date:
        with_dates.append({'item': item, 'id': id_val, 'graduationDate': grad_date})
    else:
        without_dates.append(item)

# 정렬
with_dates_sorted = sorted(with_dates, key=lambda x: x['graduationDate'])
without_dates_sorted = sorted(without_dates, key=lambda x: x['id'])

# CSV 파일 생성 (날짜순)
csv_file = '../public/data/graduation_sorted_by_date.csv'
with open(csv_file, 'w', encoding='utf-8-sig', newline='') as f:
    fieldnames = ['ID', '학교명', '졸업식 날짜', '주소', '영상 전송 여부', 'YouTube URL', '신청자 이메일']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()

    # 날짜 있는 항목
    for x in with_dates_sorted:
        item = x['item']
        video_status = item.get('videoStatus', 'pending')
        video_url = item.get('videoUrl', '')
        # 이메일 추출 (sender 필드에서)
        sender = item.get('sender', '')
        email_match = re.search(r'<([^>]+)>', sender)
        email = email_match.group(1) if email_match else sender

        writer.writerow({
            'ID': item.get('id', ''),
            '학교명': item.get('schoolName', ''),
            '졸업식 날짜': x['graduationDate'].strftime('%Y-%m-%d'),
            '주소': item.get('address', ''),
            '영상 전송 여부': 'O' if video_status in ['Sent', 'sent'] else '',
            'YouTube URL': video_url,
            '신청자 이메일': email
        })

    # 날짜 없는 항목
    for item in without_dates_sorted:
        video_status = item.get('videoStatus', 'pending')
        video_url = item.get('videoUrl', '')
        sender = item.get('sender', '')
        email_match = re.search(r'<([^>]+)>', sender)
        email = email_match.group(1) if email_match else sender

        writer.writerow({
            'ID': item.get('id', ''),
            '학교명': item.get('schoolName', ''),
            '졸업식 날짜': '',
            '주소': item.get('address', ''),
            '영상 전송 여부': 'O' if video_status in ['Sent', 'sent'] else '',
            'YouTube URL': video_url,
            '신청자 이메일': email
        })

# 통계
sent_count = sum(1 for x in with_dates_sorted + without_dates_sorted if x.get('item', x).get('videoStatus') in ['Sent', 'sent'])
sent_with_url = sum(1 for x in with_dates_sorted + without_dates_sorted if x.get('item', x).get('videoStatus') in ['Sent', 'sent'] and x.get('item', x).get('videoUrl'))
pending_count = len(data) - sent_count

print('CSV 생성 완료!')
print(f'파일: {csv_file}')
print(f'\n통계:')
print(f'  날짜 있음: {len(with_dates_sorted)}건')
print(f'  날짜 없음: {len(without_dates_sorted)}건')
print(f'  영상 전송(Sent): {sent_count}건')
print(f'    - URL 있음: {sent_with_url}건')
print(f'    - URL 없음: {sent_count - sent_with_url}건')
print(f'  대기 중(Pending): {pending_count}건')

print(f'\n날짜순 상위 20개:')
for x in with_dates_sorted[:20]:
    item = x['item']
    video_status = item.get('videoStatus', 'pending')
    status_mark = '✓' if video_status in ['Sent', 'sent'] else ' '
    print(f"  {status_mark} {x['graduationDate'].strftime('%Y-%m-%d')} | ID:{x['id']:4d} | {item.get('schoolName', '')}")
