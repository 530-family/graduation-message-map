"use client";

import { useEffect, useState } from "react";

export default function LEDDisplayBoard() {
  const [isVisible, setIsVisible] = useState(true);
  const [isMounted, setIsMounted] = useState(false);
  const [schoolCount, setSchoolCount] = useState(0);

  useEffect(() => {
    setIsMounted(true);

    // Load school count from ndjson file
    fetch("/data/coordinates.ndjson")
      .then((res) => res.text())
      .then((text) => {
        // Remove all whitespace and newlines, then split by }{
        const cleaned = text.replace(/\s+/g, "");
        const objects = cleaned.split("}{");
        setSchoolCount(objects.length);
      })
      .catch((err) => console.error("Failed to load school data:", err));

    const interval = setInterval(() => {
      setIsVisible((prev) => !prev);
    }, 800);

    return () => clearInterval(interval);
  }, []);

  // 마운트 전까지 간단한 버전만 렌더링
  if (!isMounted) {
    return (
      <div className="fixed top-0 left-0 right-0 z-50 bg-gray-600 py-6 border-b-4">
        <div className="container mx-auto px-4">
          <h1 className="text-center text-4xl md:text-6xl font-bold tracking-wider font-[PfStardust30]">
            졸업을 축하합니다
          </h1>
        </div>
      </div>
    );
  }

  const displayText =
    schoolCount > 0
      ? `졸업을 축하합니다! - 총 ${schoolCount}개교`
      : "졸업을 축하합니다!";

  return (
    <div className="fixed top-0 left-0 right-0 z-500 bg-linear-to-b from-gray-900 to-black py-4 border-b-4 border-yellow-500 shadow-2xl">
      <div className="container mx-auto px-4">
        <div className="relative overflow-hidden bg-black/50 rounded-lg border-2 border-yellow-600/30 p-4 shadow-inner">
          {/* 상단 인디케이터 라인 */}
          <div className="flex justify-between items-center mb-2 text-xs text-yellow-500/70 font-mono">
            <span>● LIVE</span>
            <span
              className={`transition-opacity duration-300 ${
                isVisible ? "opacity-100" : "opacity-30"
              }`}
            >
              {new Date().toLocaleTimeString("ko-KR", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          </div>

          {/* 메인 텍스트 - 전광판 스타일 */}
          <h1
            className={`text-center text-3xl md:text-5xl font-bold tracking-widest transition-all duration-300 font-[PfStardust30] ${
              isVisible
                ? "text-yellow-400 drop-shadow-[0_0_10px_rgba(250,204,21,0.8)]"
                : "text-yellow-500/80 drop-shadow-[0_0_5px_rgba(250,204,21,0.5)]"
            }`}
          >
            {displayText}
          </h1>

          {/* 하단 스캔라인 효과 */}
          <div className="absolute inset-0 pointer-events-none">
            <div className="absolute inset-0 bg-gradient-to-b from-transparent via-white/5 to-transparent animate-pulse"></div>
          </div>
        </div>
      </div>
    </div>
  );
}
