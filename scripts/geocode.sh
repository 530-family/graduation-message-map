#!/bin/bash

# VWorld API를 사용하여 주소를 좌표로 변환하는 스크립트
# 사용법: ./geocode.sh "주소" [주소타입]

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 프로젝트 루트 디렉토리 찾기
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env.local"

# 사용법 출력 함수
usage() {
    echo "사용법: $0 [OPTIONS] <학교명> <주소> [주소타입]"
    echo ""
    echo "파라미터:"
    echo "  학교명    : 학교 이름 (필수)"
    echo "  주소      : 검색할 주소 (필수)"
    echo "  주소타입  : PARCEL (지번주소) 또는 ROAD (도로명주소, 기본값)"
    echo ""
    echo "옵션:"
    echo "  --on-duplicate <action> : 중복 발견 시 수행할 동작."
    echo "                            - prompt: 사용자에게 묻기 (기본값)"
    echo "                            - skip: 작업을 건너뛰기"
    echo "                            - overwrite: 기존 항목 덮어쓰기"
    echo "                            - add-new: 새 항목으로 추가하기"
    echo ""
    echo "예시:"
    echo "  $0 \"천곡중학교\" \"광주광역시 광산구 월계로16번길 78 (월계동)\""
    echo "  $0 --on-duplicate skip \"한국외국어대학교\" \"서울특별시 동대문구 이문로 107 (이문동)\""
    echo ""
    echo "참고: API 키는 .env.local 파일의 VWORLD_API_KEY에서 자동으로 로드됩니다."
    echo "      결과는 public/data/coordinates.ndjson 파일에 자동으로 추가됩니다."
    exit 1
}

# 기본값 설정
ON_DUPLICATE_ACTION="prompt"

# 옵션 파싱
# 루프를 돌면서 옵션을 먼저 처리하고, 남은 것을 위치 인자로 사용
declare -a POSITIONAL_ARGS=()
while [[ $# -gt 0 ]]; do
    case $1 in
        --on-duplicate)
        if [[ -n "$2" && "$2" != -* ]]; then
            ON_DUPLICATE_ACTION="$2"
            shift # past argument
            shift # past value
        else
            echo "오류: --on-duplicate 옵션에는 값이 필요합니다." >&2
            exit 1
        fi
        ;;
        *)
        POSITIONAL_ARGS+=("$1") # 위치 인자 저장
        shift # past argument
        ;;
    esac
done
set -- "${POSITIONAL_ARGS[@]}" # 위치 인자 복원

# 파라미터 체크
if [ ${#POSITIONAL_ARGS[@]} -lt 2 ]; then
    echo -e "${RED}오류: 학교명과 주소를 입력해주세요.${NC}"
    usage
fi

SCHOOL_NAME="${POSITIONAL_ARGS[0]}"
ADDRESS="${POSITIONAL_ARGS[1]}"
TYPE="${POSITIONAL_ARGS[2]:-ROAD}"  # 기본값은 ROAD

# 입력값 정제: 앞뒤 공백과 줄바꿈 제거
SCHOOL_NAME=$(echo "$SCHOOL_NAME" | tr -d '\n\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
ADDRESS=$(echo "$ADDRESS" | tr -d '\n\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

# --- CSV에서 주소 우선 검색 (주소가 제공되지 않았을 경우에만) ---
if [ -z "$ADDRESS" ]; then
    echo -e "${YELLOW}주소가 제공되지 않았습니다. CSV에서 주소를 검색합니다...${NC}"
    CSV_SCHOOL="$PROJECT_ROOT/public/data/schoolInfo.csv"
    CSV_UNIV="$PROJECT_ROOT/public/data/universityInfo.csv"
    CSV_TO_USE=""

    # 학교명 접미사에 따라 사용할 CSV 파일 결정
    if [[ "$SCHOOL_NAME" == *"초등학교" || "$SCHOOL_NAME" == *"중학교" || "$SCHOOL_NAME" == *"고등학교" ]]; then
        CSV_TO_USE="$CSV_SCHOOL"
    else
        CSV_TO_USE="$CSV_UNIV"
    fi

    FOUND_ADDRESS=""
    if [ -f "$CSV_TO_USE" ]; then
        # iconv로 인코딩 처리, awk로 CSV 파싱
        # 학교명: 4번째 열, 도로명주소: 11번째 열
        FOUND_ADDRESS=$(iconv -f cp949 -t utf-8 "$CSV_TO_USE" 2>/dev/null | awk -F, -v name="$SCHOOL_NAME" 'BEGIN{OFS=FS} $4 == name {print $11}' | head -n 1)
        
        # 정확히 일치하는 것이 없으면, 이름으로 끝나는 경우(endswith)를 검색
        if [ -z "$FOUND_ADDRESS" ]; then
            FOUND_ADDRESS=$(iconv -f cp949 -t utf-8 "$CSV_TO_USE" 2>/dev/null | awk -F, -v name="$SCHOOL_NAME" 'BEGIN{OFS=FS} ($4 ~ name"$") {print $11}' | head -n 1)
        fi
    fi

    if [ -n "$FOUND_ADDRESS" ]; then
        # CSV에서 찾은 주소의 큰따옴표 제거
        CLEANED_ADDRESS=$(echo "$FOUND_ADDRESS" | tr -d '"')
        echo -e "${GREEN}✓ CSV에서 주소 찾음. 이 주소를 사용합니다:${NC} $CLEANED_ADDRESS"
        ADDRESS="$CLEANED_ADDRESS" # ADDRESS 변수를 덮어씀
    else
        echo -e "${YELLOW}! CSV에서 주소를 찾지 못함. 입력된 주소로 검색을 계속합니다.${NC}"
    fi
fi
# --- CSV 검색 로직 끝 ---

# .env.local 파일에서 API 키 로드
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}오류: .env.local 파일을 찾을 수 없습니다.${NC}"
    echo "경로: $ENV_FILE"
    exit 1
fi

# VWORLD_API_KEY 추출
API_KEY=$(grep "^VWORLD_API_KEY=" "$ENV_FILE" | cut -d '=' -f2- | tr -d '"' | tr -d "'")

if [ -z "$API_KEY" ]; then
    echo -e "${RED}오류: .env.local 파일에서 VWORLD_API_KEY를 찾을 수 없습니다.${NC}"
    exit 1
fi

# 주소 타입 검증
if [ "$TYPE" != "PARCEL" ] && [ "$TYPE" != "ROAD" ]; then
    echo -e "${RED}오류: 주소타입은 PARCEL 또는 ROAD 여야 합니다.${NC}"
    usage
fi

# URL 인코딩
ENCODED_ADDRESS=$(echo "$ADDRESS" | jq -sRr @uri)

# API 요청 URL 구성
API_URL="https://api.vworld.kr/req/address"
PARAMS="service=address&request=getcoord&version=2.0&crs=epsg:4326"
PARAMS="${PARAMS}&address=${ENCODED_ADDRESS}&refine=true&simple=false&format=json&type=${TYPE}&key=${API_KEY}"

FULL_URL="${API_URL}?${PARAMS}"

echo -e "${YELLOW}주소 검색 중...${NC}"
echo "학교명: $SCHOOL_NAME"
echo "주소: $ADDRESS"
echo "타입: $TYPE"
echo ""

# API 호출
RESPONSE=$(curl -s "$FULL_URL")

# 응답 확인
if [ -z "$RESPONSE" ]; then
    echo -e "${RED}오류: API 응답이 없습니다.${NC}"
    exit 1
fi

# JSON 응답에서 제어 문자 제거 (줄바꿈, 탭, 캐리지 리턴 등을 공백으로 대체)
RESPONSE=$(echo "$RESPONSE" | tr '\n\r\t' ' ')

# JSON 유효성 검사
if ! echo "$RESPONSE" | jq empty 2>/dev/null; then
    echo -e "${RED}오류: 잘못된 JSON 응답을 받았습니다.${NC}"
    echo -e "${YELLOW}API 원본 응답:${NC}"
    echo "$RESPONSE"
    exit 1
fi

# 에러 체크
ERROR=$(echo "$RESPONSE" | jq -r '.response.status' 2>/dev/null)
if [ "$ERROR" != "OK" ]; then
    echo -e "${RED}오류: API 요청 실패${NC}"
    echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"
    exit 1
fi

# 결과 파싱
RESULT=$(echo "$RESPONSE" | jq -r '.response.result')
if [ "$RESULT" == "null" ] || [ -z "$RESULT" ]; then
    echo -e "${RED}오류: 검색 결과가 없습니다.${NC}"
    exit 1
fi

# 좌표 추출 (Leaflet은 [latitude, longitude] 순서 사용)
X=$(echo "$RESPONSE" | jq -r '.response.result.point.x')  # 경도 (Longitude)
Y=$(echo "$RESPONSE" | jq -r '.response.result.point.y')  # 위도 (Latitude)

# 상세 주소 정보 추출
LEVEL0=$(echo "$RESPONSE" | jq -r '.response.refined.structure.level0 // "N/A"')
LEVEL1=$(echo "$RESPONSE" | jq -r '.response.refined.structure.level1 // "N/A"')
LEVEL2=$(echo "$RESPONSE" | jq -r '.response.refined.structure.level2 // "N/A"')
LEVEL3=$(echo "$RESPONSE" | jq -r '.response.refined.structure.level3 // "N/A"')
LEVEL4L=$(echo "$RESPONSE" | jq -r '.response.refined.structure.level4L // "N/A"')
LEVEL5=$(echo "$RESPONSE" | jq -r '.response.refined.structure.level5 // "N/A"')
REFINED_TEXT=$(echo "$RESPONSE" | jq -r '.response.refined.text // "N/A"')

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}검색 결과${NC}"
echo -e "${GREEN}========================================${NC}"
echo "학교명: $SCHOOL_NAME"
echo "입력 주소: $ADDRESS"
echo "정제된 주소: $REFINED_TEXT"
echo ""
echo -e "${GREEN}좌표 (EPSG:4326 / WGS84)${NC}"
echo "경도 (Longitude): $X"
echo "위도 (Latitude): $Y"
echo ""
echo -e "${YELLOW}Leaflet에서 사용할 좌표:${NC}"
echo "[$Y, $X]"
echo ""
echo -e "${GREEN}주소 구조${NC}"
echo "국가: $LEVEL0"
echo "시도: $LEVEL1"
echo "시군구: $LEVEL2"
echo "읍면동: $LEVEL3"
echo "도로명: $LEVEL4L"
echo "건물번호: $LEVEL5"
echo -e "${GREEN}========================================${NC}"

# JSON 형식으로도 출력
echo ""
echo -e "${YELLOW}JSON 출력 (전체):${NC}"
echo "{
  \"address\": \"$ADDRESS\",
  \"refined\": \"$REFINED_TEXT\",
  \"type\": \"$TYPE\",
  \"coordinates\": {
    \"longitude\": $X,
    \"latitude\": $Y
  },
  \"leaflet\": [$Y, $X],
  \"structure\": {
    \"level0\": \"$LEVEL0\",
    \"level1\": \"$LEVEL1\",
    \"level2\": \"$LEVEL2\",
    \"level3\": \"$LEVEL3\",
    \"level4L\": \"$LEVEL4L\",
    \"level5\": \"$LEVEL5\"
  }
}" | jq '.'

echo ""
echo -e "${YELLOW}JSON 출력 (간단):${NC}"
echo "{
  \"address\": \"$REFINED_TEXT\",
  \"coordinates\": {
    \"longitude\": $X,
    \"latitude\": $Y
  }
}" | jq '.'

# coordinates.ndjson 파일에 추가
NDJSON_FILE="$PROJECT_ROOT/public/data/coordinates.ndjson"

# 디렉토리가 없으면 생성
mkdir -p "$(dirname "$NDJSON_FILE")"

# ID 생성 (기존 파일에서 최대 ID를 찾아서 +1)
if [ -f "$NDJSON_FILE" ] && [ -s "$NDJSON_FILE" ]; then
    MAX_ID=$(jq -r '.id' "$NDJSON_FILE" 2>/dev/null | sort -n | tail -1)
    if [ -z "$MAX_ID" ] || [ "$MAX_ID" = "null" ]; then
        NEXT_ID=1
    else
        NEXT_ID=$((MAX_ID + 1))
    fi
else
    NEXT_ID=1
fi

# 새 데이터를 NDJSON 형식으로 준비 (한 줄로)
NEW_ENTRY="{\"id\":$NEXT_ID,\"schoolName\":\"$SCHOOL_NAME\",\"address\":\"$REFINED_TEXT\",\"coordinates\":{\"longitude\":$X,\"latitude\":$Y}}"

# 중복 체크 (학교명 기준)
REPLACE_MODE=false
INSERT_LINE=0

if [ -f "$NDJSON_FILE" ]; then
    # 학교명이 포함된 줄 번호 찾기 (Regex search with optional space)
    LINE_NUM=$(grep -n -E "\"schoolName\":\s*\"$SCHOOL_NAME\"" "$NDJSON_FILE" 2>/dev/null | cut -d: -f1)

    if [ -n "$LINE_NUM" ]; then
        # 기존 데이터 추출 (한 줄)
        EXISTING=$(sed -n "${LINE_NUM}p" "$NDJSON_FILE")
        EXISTING_ID=$(echo "$EXISTING" | jq -r '.id')

        # --on-duplicate 값에 따라 분기 처리
        case "$ON_DUPLICATE_ACTION" in
            skip)
                echo -e "${YELLOW}경고: '$SCHOOL_NAME'가 이미 존재합니다. --on-duplicate=skip 설정에 따라 건너뜁니다.${NC}"
                exit 0
                ;;
            overwrite)
                echo -e "${YELLOW}경고: '$SCHOOL_NAME'가 이미 존재합니다. --on-duplicate=overwrite 설정에 따라 덮어씁니다.${NC}"
                NEW_ENTRY="{\"id\":$EXISTING_ID,\"schoolName\":\"$SCHOOL_NAME\",\"address\":\"$REFINED_TEXT\",\"coordinates\":{\"longitude\":$X,\"latitude\":$Y}}"
                
                # sed의 치환(substitute) 기능을 사용하여 해당 라인을 직접 교체
                # BSD/macOS sed와 호환되도록 -i 뒤에 '' 확장자 제공
                sed -i.bak "${LINE_NUM}s/.*/$NEW_ENTRY/" "$NDJSON_FILE"
                rm -f "$NDJSON_FILE.bak"

                echo -e "${GREEN}기존 데이터를 덮어썼습니다.${NC}"
                echo -e "${YELLOW}새 데이터:${NC}"
                echo "$NEW_ENTRY" | jq '.'
                exit 0
                ;;
            add-new)
                echo -e "${YELLOW}경고: '$SCHOOL_NAME'가 이미 존재합니다. --on-duplicate=add-new 설정에 따라 새로 추가합니다.${NC}"
                # Fall through to the default append logic
                ;;
            *) # prompt 또는 잘못된 값일 경우
                echo ""
                echo -e "${YELLOW}⚠️  경고: '$SCHOOL_NAME'는 이미 coordinates.ndjson에 존재합니다.${NC}"
                echo -e "${YELLOW}기존 데이터:${NC}"
                echo "$EXISTING" | jq '.'
                echo ""
                echo "선택하세요:"
                echo "  1) 덮어쓰기 (기존 데이터를 새 데이터로 교체)"
                echo "  2) 새로 추가 (같은 이름의 다른 학교로 추가)"
                echo "  3) 취소"
                read -p "선택 (1/2/3): " -n 1 -r
                echo

                if [[ $REPLY == "1" ]]; then
                    NEW_ENTRY="{\"id\":$EXISTING_ID,\"schoolName\":\"$SCHOOL_NAME\",\"address\":\"$REFINED_TEXT\",\"coordinates\":{\"longitude\":$X,\"latitude\":$Y}}"
                    sed -i.bak "${LINE_NUM}s/.*/$NEW_ENTRY/" "$NDJSON_FILE"
                    rm -f "$NDJSON_FILE.bak"
                    echo -e "${GREEN}기존 데이터를 덮어썼습니다.${NC}"
                    echo -e "${YELLOW}새 데이터:${NC}"
                    echo "$NEW_ENTRY" | jq '.'
                    exit 0
                elif [[ $REPLY == "2" ]]; then
                    echo -e "${GREEN}새로운 항목으로 추가합니다.${NC}"
                    # Fall through to the default append logic
                else
                    echo -e "${RED}취소되었습니다.${NC}"
                    exit 0
                fi
                ;;
        esac
    fi
fi

# ID 생성 (기존 파일에서 최대 ID를 찾아서 +1)
if [ -f "$NDJSON_FILE" ] && [ -s "$NDJSON_FILE" ]; then
    MAX_ID=$(jq -r '.id' "$NDJSON_FILE" 2>/dev/null | sort -n | tail -1)
    if [ -z "$MAX_ID" ] || [ "$MAX_ID" = "null" ]; then
        NEXT_ID=1
    else
        NEXT_ID=$((MAX_ID + 1))
    fi
else
    NEXT_ID=1
fi

# 새 데이터를 NDJSON 형식으로 준비 (한 줄로)
NEW_ENTRY="{\"id\":$NEXT_ID,\"schoolName\":\"$SCHOOL_NAME\",\"address\":\"$REFINED_TEXT\",\"coordinates\":{\"longitude\":$X,\"latitude\":$Y}}"

# 파일 끝에 추가
echo "$NEW_ENTRY" >> "$NDJSON_FILE"

echo ""
echo -e "${GREEN}✓ coordinates.ndjson에 데이터가 추가되었습니다!${NC}"
echo -e "${GREEN}파일 위치: $NDJSON_FILE${NC}"
echo ""
echo -e "${YELLOW}추가된 데이터:${NC}"
echo "$NEW_ENTRY" | jq '.'

exit 0
