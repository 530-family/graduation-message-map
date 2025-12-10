"use client";

import dynamic from "next/dynamic";
import LEDDisplayBoard from "./components/LEDDisplayBoard";
import QuickLinks from "./components/QuickLinks";

// Leaflet은 서버 사이드 렌더링을 지원하지 않으므로 dynamic import 사용
const KoreaMap = dynamic(() => import("./components/KoreaMap"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-screen flex items-center justify-center">
      지도 로딩 중...
    </div>
  ),
});

export default function Home() {
  return (
    <main className="relative">
      <LEDDisplayBoard />
      <KoreaMap />
      <QuickLinks />
    </main>
  );
}
