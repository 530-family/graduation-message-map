import { NextRequest, NextResponse } from "next/server";
import { google } from "googleapis";
import { randomBytes } from "crypto";
import { readFile, writeFile } from "fs/promises";
import { join } from "path";

// Vercel 서버리스 함수에서 Node.js runtime 사용 (Edge Runtime 대신)
export const runtime = 'nodejs';

// Google Sheets 설정
const SPREADSHEET_ID = process.env.GOOGLE_SPREADSHEET_ID || "";
const SHEET_NAME = "requests";
const KAKAO_REST_API_KEY = process.env.KAKAO_REST_API_KEY || "";

interface RequestData {
  email: string;
  schoolName: string;
  address: string;
  graduationDate: string;
  requestDetails: string;
  season?: string;
  type?: string;
}

interface Coordinates {
  longitude: number;
  latitude: number;
}

interface CoordinateEntry {
  id: number;
  schoolName: string;
  address: string;
  coordinates: Coordinates;
  videoStatus: string;
  videoUrl: string;
}

// Google JWT 인증 설정
function getGoogleAuth() {
  // 환경 변수에서 읽기 (함수 내부에서 처리)
  const clientEmail = process.env.GOOGLE_CLIENT_EMAIL || "";
  let privateKey = process.env.GOOGLE_PRIVATE_KEY || "";

  // 따옴표 제거 (처음과 끝의 따옴표만)
  if (privateKey.startsWith('"') && privateKey.endsWith('"')) {
    privateKey = privateKey.slice(1, -1);
  }

  // \\n을 실제 줄바꿈으로 변환
  privateKey = privateKey.replace(/\\n/g, '\n');

  // options 객체 형태로 JWT 생성 (google-auth-library 올바른 사용법)
  return new google.auth.JWT({
    email: clientEmail,
    key: privateKey,
    scopes: ["https://www.googleapis.com/auth/spreadsheets"],
  });
}

// 카카오 지오코딩 API
async function geocodeAddress(address: string): Promise<{ coordinates: Coordinates; debugInfo: any } | null> {
  const debugInfo: any = { address, apiKeyExists: !!KAKAO_REST_API_KEY };

  if (!KAKAO_REST_API_KEY) {
    debugInfo.error = "KAKAO_REST_API_KEY_MISSING";
    return null;
  }

  try {
    const apiUrl = `https://dapi.kakao.com/v2/local/search/address.json?query=${encodeURIComponent(address)}`;

    const response = await fetch(apiUrl, {
      headers: {
        'Authorization': `KakaoAK ${KAKAO_REST_API_KEY}`,
      },
    });

    const data = await response.json();

    if (data.documents && data.documents.length > 0) {
      const doc = data.documents[0];
      if (doc.x && doc.y) {
        return {
          coordinates: {
            longitude: parseFloat(doc.x),
            latitude: parseFloat(doc.y),
          },
          debugInfo,
        };
      }
    }

    debugInfo.error = "NO_RESULTS";
    return null;
  } catch (error) {
    console.error("카카오 API 요청 실패:", error);
    debugInfo.error = String(error);
    return null;
  }
}

// coordinates.ndjson 파일 읽기
async function readCoordinatesFile(): Promise<CoordinateEntry[]> {
  try {
    const filePath = join(process.cwd(), "public", "data", "coordinates.ndjson");
    const content = await readFile(filePath, "utf-8");
    const lines = content.trim().split("\n");

    const entries: CoordinateEntry[] = [];
    for (const line of lines) {
      if (line.trim()) {
        try {
          entries.push(JSON.parse(line));
        } catch (e) {
          console.error("JSON 파싱 오류:", line);
        }
      }
    }

    return entries;
  } catch (error) {
    console.error("coordinates.ndjson 파일 읽기 오류:", error);
    return [];
  }
}

// coordinates.ndjson 파일에 쓰기
async function writeCoordinatesFile(entries: CoordinateEntry[]): Promise<void> {
  try {
    const filePath = join(process.cwd(), "public", "data", "coordinates.ndjson");
    const content = entries.map((entry) => JSON.stringify(entry)).join("\n") + "\n";
    await writeFile(filePath, content, "utf-8");
  } catch (error) {
    console.error("coordinates.ndjson 파일 쓰기 오류:", error);
    throw error;
  }
}

export async function POST(request: NextRequest) {
  try {
    const body: RequestData = await request.json();

    // 필드 유효성 검사
    const { email, schoolName, address, graduationDate, requestDetails } = body;

    if (!email || !schoolName || !address || !graduationDate || !requestDetails) {
      return NextResponse.json(
        { error: "모든 필드를 입력해주세요." },
        { status: 400 }
      );
    }

    // 이메일 형식 검사
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      return NextResponse.json(
        { error: "유효한 이메일 주소를 입력해주세요." },
        { status: 400 }
      );
    }

    // 환경 변수 검사
    if (!SPREADSHEET_ID) {
      return NextResponse.json(
        { error: "서버 설정 오류: SPREADSHEET_ID가 설정되지 않았습니다." },
        { status: 500 }
      );
    }

    if (!process.env.GOOGLE_PRIVATE_KEY || !process.env.GOOGLE_CLIENT_EMAIL) {
      return NextResponse.json(
        { error: "서버 설정 오류: Google 인증 정보가 설정되지 않았습니다." },
        { status: 500 }
      );
    }

    // Google Sheets API 연결
    const auth = getGoogleAuth();
    await auth.authorize(); // JWT 인증 토큰 획득
    const sheets = google.sheets({ version: "v4", auth });

    // 중복 체크: 기존 데이터 조회
    const existingData = await sheets.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `${SHEET_NAME}!A:L`, // 좌표 포함 전체 범위
    });

    const rows = existingData.data.values || [];
    // 헤더 행 제외 (첫 번째 행은 제목)
    const dataRows = rows.slice(1);

    // 중복 체크
    for (const row of dataRows) {
      const existingEmail = row[4]; // F열: 이메일
      const existingAddress = row[6]; // G열: 주소

      // 이메일 중복 체크
      if (existingEmail === email) {
        return NextResponse.json(
          { error: "이미 접수된 이메일이에요. 한 번의 신청으로 충분해요! ✨" },
          { status: 409 }
        );
      }

      // 주소 정규화 함수 (첫 "(" 또는 "/"부터 뒤를 제거)
      const normalizeAddress = (addr: string) => {
        const cleaned = addr || "";
        // "(" 또는 "/" 중 먼저 나오는 것 찾아서 그 앞부분만 사용
        const parenIndex = cleaned.indexOf("(");
        const slashIndex = cleaned.indexOf("/");

        let cutIndex = -1;
        if (parenIndex !== -1 && slashIndex !== -1) {
          cutIndex = Math.min(parenIndex, slashIndex);
        } else if (parenIndex !== -1) {
          cutIndex = parenIndex;
        } else if (slashIndex !== -1) {
          cutIndex = slashIndex;
        }

        if (cutIndex !== -1) {
          return cleaned.substring(0, cutIndex).trim();
        }
        return cleaned.trim();
      };

      // 주소 중복 체크 (정규화된 주소로 비교)
      const existingAddressClean = normalizeAddress(existingAddress || "");
      const currentAddressClean = normalizeAddress(address);

      if (existingAddressClean === currentAddressClean) {
        return NextResponse.json(
          { error: "이미 같은 학교가 신청되었어요! 졸업식 날 축사 영상을 기대해 주세요 🎉" },
          { status: 409 }
        );
      }
    }

    // 주소를 좌표로 변환
    const geocodeResult = await geocodeAddress(address);

    // 좌표 변환 실패 시 기본값 (0, 0) 사용
    const coordinates = geocodeResult?.coordinates || { longitude: 0, latitude: 0 };
    const debugInfo = geocodeResult?.debugInfo;

    // 현재 시간 (한국 시간)
    const now = new Date();
    const timestamp = now.toLocaleString("ko-KR", {
      timeZone: "Asia/Seoul",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });

    // 시트에 추가할 데이터 행
    const uniqueId = randomBytes(8).toString('base64url'); // 11자리 고유 ID
    const rowData = [
      uniqueId,            // ID (11자리 랜덤 코드)
      "졸업식",             // 타입 (고정)
      "2026-1",            // 시즌 (고정)
      "대기중",             // 상태
      email,               // 이메일
      schoolName,          // 학교명
      address,             // 주소
      coordinates.longitude, // 경도
      coordinates.latitude,  // 위도
      graduationDate,      // 졸업식 날짜
      requestDetails,      // 요청 사항
      timestamp,           // 제출 시간
    ];

    // 시트에 데이터 추가
    await sheets.spreadsheets.values.append({
      spreadsheetId: SPREADSHEET_ID,
      range: `${SHEET_NAME}!A:L`, // 좌표 컬럼 추가로 범위 확장
      valueInputOption: "USER_ENTERED",
      requestBody: {
        values: [rowData],
      },
    });

    // coordinates.ndjson에 새 row 추가
    try {
      const coordinateEntries = await readCoordinatesFile();

      // 새 ID 계산 (기존 최대 ID + 1)
      const maxId = coordinateEntries.length > 0
        ? Math.max(...coordinateEntries.map((e) => e.id))
        : 0;

      const newEntry: CoordinateEntry = {
        id: maxId + 1,
        schoolName,
        address,
        coordinates,
        videoStatus: "Pending",
        videoUrl: "",
      };

      coordinateEntries.push(newEntry);
      await writeCoordinatesFile(coordinateEntries);
    } catch (error) {
      console.error("coordinates.ndjson 업데이트 오류:", error);
      // coordinates.ndjson 업데이트 실패 시에도 Google Sheets 저장은 성공했으므로 계속 진행
    }

    return NextResponse.json(
      { success: true, message: "요청이 성공적으로 제출되었습니다." },
      { status: 200 }
    );
  } catch (error) {
    console.error("API Error:", error);

    // Google API 오류 상세 메시지
    if (error instanceof Error) {
      return NextResponse.json(
        { error: `제출 중 오류가 발생했습니다: ${error.message}` },
        { status: 500 }
      );
    }

    return NextResponse.json(
      { error: "제출 중 알 수 없는 오류가 발생했습니다." },
      { status: 500 }
    );
  }
}

export async function GET() {
  return NextResponse.json(
    { error: "GET 요청은 지원되지 않습니다." },
    { status: 405 }
  );
}
