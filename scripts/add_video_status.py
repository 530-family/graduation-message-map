import json
import csv

# Read CSV to get schools that received videos
schools_sent = {}
with open('../graduation_sent_emails.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        school_name = row['학교명'].strip()
        youtube_url = row['YouTube URL'].strip()
        recipient = row['받는 사람'].strip()
        schools_sent[school_name] = {
            'youtube_url': youtube_url,
            'recipient': recipient
        }

print(f"CSV에서 {len(schools_sent)}개 학교의 영상 전송 정보를 읽었습니다.")

# Process coordinates.ndjson (public version - without sender/requestContent)
print("\n=== coordinates.ndjson 처리 ===")
output_data = []
matched_count = 0
already_exists = 0

with open('../public/data/coordinates.ndjson', 'r', encoding='utf-8') as f:
    for line in f:
        if not line.strip():
            continue
        item = json.loads(line)
        school_name = item.get('schoolName', '').strip()

        # Check if this school received a video
        if school_name in schools_sent:
            if 'videoStatus' not in item:
                item['videoStatus'] = 'Sent'
                item['videoUrl'] = schools_sent[school_name]['youtube_url']
                matched_count += 1
            else:
                already_exists += 1
        elif 'videoStatus' not in item:
            item['videoStatus'] = 'Pending'

        output_data.append(item)

# Write back to coordinates.ndjson
output_file = '../public/data/coordinates.ndjson'
with open(output_file, 'w', encoding='utf-8') as f:
    for item in output_data:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')

print(f'일치하여 추가: {matched_count}개')
print(f'이미 존재: {already_exists}개')
print(f'전체 처리: {len(output_data)}개')

# Process coordinates.internal.ndjson (internal version - with sender/requestContent)
print("\n=== coordinates.internal.ndjson 처리 ===")
output_data2 = []
matched_count2 = 0
already_exists2 = 0

with open('../public/data/coordinates.internal.ndjson', 'r', encoding='utf-8') as f:
    for line in f:
        if not line.strip():
            continue
        item = json.loads(line)
        school_name = item.get('schoolName', '').strip()

        # Check if this school received a video
        if school_name in schools_sent:
            if 'videoStatus' not in item:
                item['videoStatus'] = 'Sent'
                item['videoUrl'] = schools_sent[school_name]['youtube_url']
                matched_count2 += 1
            else:
                already_exists2 += 1
        elif 'videoStatus' not in item:
            item['videoStatus'] = 'Pending'

        output_data2.append(item)

# Write back to coordinates.internal.ndjson
output_file2 = '../public/data/coordinates.internal.ndjson'
with open(output_file2, 'w', encoding='utf-8') as f:
    for item in output_data2:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')

print(f'일치하여 추가: {matched_count2}개')
print(f'이미 존재: {already_exists2}개')
print(f'전체 처리: {len(output_data2)}개')

# Summary
sent = [x for x in output_data if x.get('videoStatus') == 'Sent' and x.get('videoUrl')]
pending = [x for x in output_data if x.get('videoStatus') == 'Pending']

print(f'\n=== 최종 요약 ===')
print(f'영상 전송됨 (URL 있음): {len(sent)}개')
print(f'대기 중: {len(pending)}개')
print(f'\n영상 전송된 학교 예시:')
for item in sent[:10]:
    print(f'  - {item["schoolName"]}: {item["videoUrl"]}')
