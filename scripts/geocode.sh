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
    echo "사용법: $0 <주소> [주소타입]"
    echo ""
    echo "파라미터:"
    echo "  주소      : 검색할 주소 (필수)"
    echo "  주소타입  : PARCEL (지번주소) 또는 ROAD (도로명주소, 기본값)"
    echo ""
    echo "예시:"
    echo "  $0 \"효령로72길 60\""
    echo "  $0 \"효령로72길 60\" ROAD"
    echo "  $0 \"관양동 1588-8\" PARCEL"
    echo ""
    echo "참고: API 키는 .env.local 파일의 VWORLD_API_KEY에서 자동으로 로드됩니다."
    exit 1
}

# 파라미터 체크
if [ $# -lt 1 ]; then
    echo -e "${RED}오류: 주소를 입력해주세요.${NC}"
    usage
fi

ADDRESS="$1"
TYPE="${2:-ROAD}"  # 기본값은 ROAD

# 주소 정제: 앞뒤 공백과 줄바꿈 제거
ADDRESS=$(echo "$ADDRESS" | tr -d '\n\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

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

exit 0
