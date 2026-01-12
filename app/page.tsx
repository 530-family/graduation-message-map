"use client";

import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import LEDDisplayBoard from "./components/LEDDisplayBoard";
import SchoolSearch from "./components/SchoolSearch";
import QuickLinks from "./components/QuickLinks";
import RequestFormWrapper from "./components/RequestFormWrapper";
import type { SchoolData } from "./components/KoreaMap";

// Leaflet은 서버 사이드 렌더링을 지원하지 않으므로 dynamic import 사용
const KoreaMap = dynamic(() => import("./components/KoreaMap"), {
  ssr: false,
  loading: () => {
    return (
      <div className="w-full h-screen flex items-center justify-center">
        지도 로딩 중...
      </div>
    );
  },
});

export default function Home() {
  const [schools, setSchools] = useState<SchoolData[]>([]);
  const [selectedSchool, setSelectedSchool] = useState<SchoolData | null>(null);

  useEffect(() => {
    // Google Sheets API에서 데이터 로드
    fetch("/api/coordinates")
      .then((response) => response.json())
      .then((data) => {
        setSchools(data);
      })
      .catch((error) => {
        console.error("Failed to load coordinates data:", error);
      });
  }, []);

  return (
    <main className="relative">
      <LEDDisplayBoard />
      <SchoolSearch
        schools={schools}
        selectedSchool={selectedSchool}
        onSchoolSelect={setSelectedSchool}
        onClearSelection={() => setSelectedSchool(null)}
      />
      <KoreaMap selectedSchool={selectedSchool} />
      <QuickLinks />
      <RequestFormWrapper />
    </main>
  );
}
