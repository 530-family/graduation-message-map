import { NextResponse } from "next/server";
import { google } from "googleapis";

// Vercel 서버리스 함수에서 Node.js runtime 사용
export const runtime = 'nodejs';

// 캐싱 비활성화: 매번 시트에서 데이터를 가져옴
export const dynamic = 'force-dynamic';

// Google Sheets 설정
const SPREADSHEET_ID = process.env.GOOGLE_SPREADSHEET_ID || "";
const SHEET_NAME = "requests";

// 비디오 상태 enum
enum VideoStatus {
  PENDING = "대기중",          // 최초 신청한 상태
  UPLOADED = "업로드완료",     // 유튜브 업로드 완료
  EMAIL_DRAFT = "메일작성완료", // 이메일 임시 보관함 생성 완료
  SENT = "전송완료"            // 이메일 전송 완료
}

interface SchoolData {
  id: string;  // 시트의 고유 ID 사용
  schoolName: string;
  address: string;
  coordinates: {
    longitude: number;
    latitude: number;
  };
  videoStatus: VideoStatus;  // enum 타입 사용
  videoUrl: string;
  // email, requestContent는 브라우저로 전송하지 않음 (개인정보 보호)
}

interface UpdateStatusRequest {
  id: string;
  videoStatus: VideoStatus;
  videoUrl?: string;
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
      range: `${SHEET_NAME}!A:M`,  // M열까지 (videoUrl 컬럼 추가)
    });

    const rows = response.data.values || [];
    // 헤더 행 제외
    const dataRows = rows.slice(1);

    // SchoolData 배열로 변환
    const schools: SchoolData[] = dataRows
      .filter((row) => row.length >= 11) // 최소 필드 확인 (이메일, 요청사항 포함)
      .map((row) => {
        // A열: ID, B열: 타입, C열: 시즌, D열: 상태, E열: 이메일
        // F열: 학교명, G열: 주소, H열: 경도, I열: 위도
        // J열: 졸업식 날짜, K열: 요청 사항, L열: 제출 시간, M열: videoUrl
        const sheetId = row[0] || `row-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;  // 시트의 고유 ID 사용
        const schoolName = row[5] || "";
        const address = row[6] || "";
        const email = row[4] || "";
        const requestContent = row[10] || "";
        const longitude = parseFloat(row[7]) || 0;
        const latitude = parseFloat(row[8]) || 0;

        // videoStatus는 시트의 상태 컬럼 (D열) 사용
        // 새로운 상태 시스템으로 매핑
        const status = row[3] || "대기중";
        let videoStatus = VideoStatus.PENDING;

        if (status === "전송완료" || status === "완료") {
          videoStatus = VideoStatus.SENT;
        } else if (status === "메일작성완료") {
          videoStatus = VideoStatus.EMAIL_DRAFT;
        } else if (status === "업로드완료") {
          videoStatus = VideoStatus.UPLOADED;
        }

        // M열에서 videoUrl 가져오기
        const videoUrl = row[12] || "";

        return {
          id: String(sheetId),
          schoolName,
          address,
          // email, requestContent는 브라우저로 전송하지 않음 (개인정보 보호)
          coordinates: {
            longitude,
            latitude,
          },
          videoStatus,
          videoUrl,
        };
      })
      .filter((school): school is SchoolData => school !== null);

    return NextResponse.json(schools, {
      headers: {
        'Cache-Control': 'no-store, no-cache, must-revalidate',
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
