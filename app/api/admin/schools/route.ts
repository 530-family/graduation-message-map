import { NextResponse } from "next/server";
import { google } from "googleapis";

// Vercel 서버리스 함수에서 Node.js runtime 사용
export const runtime = 'nodejs';

// 캐싱 비활성화: 매번 시트에서 데이터를 가져옴
export const dynamic = 'force-dynamic';

// Google Sheets 설정
const SPREADSHEET_ID = process.env.GOOGLE_SPREADSHEET_ID || "";
const SHEET_NAME = "requests";

// 관리자용 API 키 (VideoEditor에서 사용)
const ADMIN_API_KEY = process.env.ADMIN_API_KEY || "";

// 비디오 상태 enum
enum VideoStatus {
  PENDING = "대기중",
  UPLOADED = "업로드완료",
  EMAIL_DRAFT = "메일작성완료",
  SENT = "전송완료"
}

interface AdminSchoolData {
  id: string;
  type: string;
  season: string;
  status: string;
  email: string;
  schoolName: string;
  address: string;
  coordinates: {
    longitude: number;
    latitude: number;
  };
  graduationDate: string;
  requestContent: string;
  submittedAt: string;
  videoUrl: string;
}

interface UpdateStatusRequest {
  id: string;
  status: VideoStatus;
  videoUrl?: string;
}

// Google JWT 인증 설정
function getGoogleAuth() {
  const clientEmail = process.env.GOOGLE_CLIENT_EMAIL || "";
  let privateKey = process.env.GOOGLE_PRIVATE_KEY || "";

  if (privateKey.startsWith('"') && privateKey.endsWith('"')) {
    privateKey = privateKey.slice(1, -1);
  }

  privateKey = privateKey.replace(/\\n/g, '\n');

  return new google.auth.JWT({
    email: clientEmail,
    key: privateKey,
    scopes: ["https://www.googleapis.com/auth/spreadsheets"],
  });
}

// API 키 인증 미들웨어
function authenticate(request: Request): boolean {
  const authHeader = request.headers.get('authorization');
  const apiKey = authHeader?.replace('Bearer ', '');

  // ADMIN_API_KEY가 설정되지 않은 경우 로컬 개발 환경으로 간주하여 통과
  if (!ADMIN_API_KEY) {
    console.warn('ADMIN_API_KEY not set, allowing all requests (development mode)');
    return true;
  }

  return apiKey === ADMIN_API_KEY;
}

export async function GET(request: Request) {
  try {
    // API 키 인증
    if (!authenticate(request)) {
      return NextResponse.json(
        { error: "인증 실패: 유효한 API 키가 필요합니다." },
        { status: 401 }
      );
    }

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
    await auth.authorize();
    const sheets = google.sheets({ version: "v4", auth });

    // 시트 데이터 조회
    const response = await sheets.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `${SHEET_NAME}!A:M`,
    });

    const rows = response.data.values || [];
    const dataRows = rows.slice(1);

    // AdminSchoolData 배열로 변환 (모든 데이터 포함)
    const schools: AdminSchoolData[] = dataRows
      .filter((row) => row.length >= 11)
      .map((row) => {
        const id = row[0] || `row-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        const type = row[1] || "";
        const season = row[2] || "";
        const status = row[3] || "대기중";
        const email = row[4] || "";
        const schoolName = row[5] || "";
        const address = row[6] || "";
        const longitude = parseFloat(row[7]) || 0;
        const latitude = parseFloat(row[8]) || 0;
        const graduationDate = row[9] || "";
        const requestContent = row[10] || "";
        const submittedAt = row[11] || "";
        const videoUrl = row[12] || "";

        return {
          id: String(id),
          type,
          season,
          status,
          email,
          schoolName,
          address,
          coordinates: {
            longitude,
            latitude,
          },
          graduationDate,
          requestContent,
          submittedAt,
          videoUrl,
        };
      })
      .filter((school): school is AdminSchoolData => school !== null);

    return NextResponse.json(schools, {
      headers: {
        'Cache-Control': 'no-store, no-cache, must-revalidate',
      },
    });
  } catch (error) {
    console.error("Admin Schools API Error:", error);

    if (error instanceof Error) {
      return NextResponse.json(
        { error: `데이터 조회 중 오류가 발생했습니다: ${error.message}` },
        { status: 500 }
      );
    }

    return NextResponse.json(
      { error: "데이터 조회 중 알 수 없는 오류가 발생했습니다." },
      { status: 500 }
    );
  }
}

// PATCH: 상태 업데이트 (VideoEditor에서 사용)
export async function PATCH(request: Request) {
  try {
    // API 키 인증
    if (!authenticate(request)) {
      return NextResponse.json(
        { error: "인증 실패: 유효한 API 키가 필요합니다." },
        { status: 401 }
      );
    }

    const body: UpdateStatusRequest = await request.json();

    if (!body.id || !body.status) {
      return NextResponse.json(
        { error: "필수 파라미터가 누락되었습니다: id, status" },
        { status: 400 }
      );
    }

    if (!SPREADSHEET_ID) {
      return NextResponse.json(
        { error: "서버 설정 오류: SPREADSHEET_ID가 설정되지 않았습니다." },
        { status: 500 }
      );
    }

    // Google Sheets API 연결
    const auth = getGoogleAuth();
    await auth.authorize();
    const sheets = google.sheets({ version: "v4", auth });

    // 먼저 전체 데이터를 가져와서 해당 ID의 행을 찾음
    const getResponse = await sheets.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `${SHEET_NAME}!A:M`,
    });

    const rows = getResponse.data.values || [];
    const dataRows = rows.slice(1);

    // ID로 행 찾기 (A열)
    let targetRowIndex = -1;
    for (let i = 0; i < dataRows.length; i++) {
      if (String(dataRows[i][0]) === String(body.id)) {
        targetRowIndex = i + 2; // +2: 헤더 행(1) + 인덱스 보정
        break;
      }
    }

    if (targetRowIndex === -1) {
      return NextResponse.json(
        { error: `ID를 찾을 수 없습니다: ${body.id}` },
        { status: 404 }
      );
    }

    // D열(상태)과 M열(videoUrl)만 업데이트하여 중간 데이터 보존
    // 먼저 현재 행 데이터를 가져옴
    const currentRow = await sheets.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `${SHEET_NAME}!A${targetRowIndex}:M${targetRowIndex}`,
    });

    const rowValues = currentRow.data.values?.[0] || [];
    if (rowValues.length < 13) {
      // 행이 충분히 길지 않으면 빈 값으로 채움
      while (rowValues.length < 13) rowValues.push("");
    }

    // D열(인덱스 3)과 M열(인덱스 12)만 업데이트
    rowValues[3] = body.status;  // D열: 상태
    rowValues[12] = body.videoUrl || "";  // M열: videoUrl

    // 전체 행 업데이트
    await sheets.spreadsheets.values.update({
      spreadsheetId: SPREADSHEET_ID,
      range: `${SHEET_NAME}!A${targetRowIndex}:M${targetRowIndex}`,
      valueInputOption: "USER_ENTERED",
      requestBody: {
        values: [rowValues],
      },
    });

    return NextResponse.json({
      success: true,
      id: body.id,
      status: body.status,
      videoUrl: body.videoUrl || "",
    });
  } catch (error) {
    console.error("Update Status API Error:", error);

    if (error instanceof Error) {
      return NextResponse.json(
        { error: `상태 업데이트 중 오류가 발생했습니다: ${error.message}` },
        { status: 500 }
      );
    }

    return NextResponse.json(
      { error: "상태 업데이트 중 알 수 없는 오류가 발생했습니다." },
      { status: 500 }
    );
  }
}
