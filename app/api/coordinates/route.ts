import { NextResponse } from "next/server";
import { google } from "googleapis";

// Vercel 서버리스 함수에서 Node.js runtime 사용
export const runtime = 'nodejs';

// 캐싱: 5분
export const dynamic = 'force-dynamic';
export const revalidate = 300;

// Google Sheets 설정
const SPREADSHEET_ID = process.env.GOOGLE_SPREADSHEET_ID || "";
const SHEET_NAME = "requests";

interface SchoolData {
  id: number;
  schoolName: string;
  address: string;
  email: string;
  requestContent: string;
  coordinates: {
    longitude: number;
    latitude: number;
  };
  videoStatus: string;
  videoUrl: string;
}

// Google JWT 인증 설정
function getGoogleAuth() {
  const clientEmail = process.env.GOOGLE_CLIENT_EMAIL || "";
  let privateKey = process.env.GOOGLE_PRIVATE_KEY || "";

  // 따옴표 제거
  if (privateKey.startsWith('"') && privateKey.endsWith('"')) {
    privateKey = privateKey.slice(1, -1);
  }

  // \\n을 실제 줄바꿈으로 변환
  privateKey = privateKey.replace(/\\n/g, '\n');

  return new google.auth.JWT({
    email: clientEmail,
    key: privateKey,
    scopes: ["https://www.googleapis.com/auth/spreadsheets"],
  });
}

export async function GET() {
  try {
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
    await auth.authorize();
    const sheets = google.sheets({ version: "v4", auth });

    // 시트 데이터 조회
    const response = await sheets.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `${SHEET_NAME}!A:L`,
    });

    const rows = response.data.values || [];
    // 헤더 행 제외
    const dataRows = rows.slice(1);

    // SchoolData 배열로 변환
    const schools: SchoolData[] = dataRows
      .filter((row) => row.length >= 11) // 최소 필드 확인 (이메일, 요청사항 포함)
      .map((row, index) => {
        // A열: ID, B열: 타입, C열: 시즌, D열: 상태, E열: 이메일
        // F열: 학교명, G열: 주소, H열: 경도, I열: 위도
        // J열: 졸업식 날짜, K열: 요청 사항, L열: 제출 시간
        const schoolName = row[5] || "";
        const address = row[6] || "";
        const email = row[4] || "";
        const requestContent = row[10] || "";
        const longitude = parseFloat(row[7]) || 0;
        const latitude = parseFloat(row[8]) || 0;

        // videoStatus는 시트의 상태 컬럼 (D열) 사용
        // "완료" 또는 "전송완료"면 "Sent", 그 외 "Pending"
        const status = row[3] || "";
        const videoStatus = (status === "완료" || status === "전송완료") ? "Sent" : "Pending";

        return {
          id: index + 1,
          schoolName,
          address,
          email,
          requestContent,
          coordinates: {
            longitude,
            latitude,
          },
          videoStatus,
          videoUrl: "",
        };
      })
      .filter((school): school is SchoolData => school !== null);

    return NextResponse.json(schools, {
      headers: {
        'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600',
      },
    });
  } catch (error) {
    console.error("Coordinates API Error:", error);

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
