"use client";

import { useEffect, useState } from "react";
import { Mail, X, Copy, Send, Loader2 } from "lucide-react";

export default function LEDDisplayBoard() {
  const [isVisible, setIsVisible] = useState(true);
  const [isMounted, setIsMounted] = useState(false);
  const [schoolCount, setSchoolCount] = useState(0);
  const [sentCount, setSentCount] = useState(0);
  const [pendingCount, setPendingCount] = useState(0);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const [showLegend, setShowLegend] = useState(false);

  useEffect(() => {
    setIsMounted(true);

    // Google Sheets API에서 데이터 로드
    fetch("/api/coordinates")
      .then((res) => res.json())
      .then((data) => {
        const total = data.length;
        const sent = data.filter((s: any) => s.videoStatus === "Sent").length;

        setSchoolCount(total);
        setSentCount(sent);
        setPendingCount(total - sent);
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

  const handleCopyEmail = async () => {
    const email = "j7840790@gmail.com";
    try {
      await navigator.clipboard.writeText(email);
      setIsCopied(true);
      setTimeout(() => {
        setIsCopied(false);
      }, 1500);
    } catch (err) {
      console.error("Failed to copy email:", err);
    }
  };

  const handleEmailClick = () => {
    const subject = encodeURIComponent(
      "[축사] OO중/고등학교 졸업식 축사 요청드립니다"
    );
    const body = encodeURIComponent(`안녕하세요, {자기소개}

다가오는 졸업식을 앞두고,
저희 학교 학생들을 위한 졸업 축하 메세지를 부탁드립니다.

[학교명 / 소재지]:
[졸업식 날짜]:
[꼭 포함했으면 하는 내용]:

축하 영상은 본 메일로 회신해주세요.
감사합니다.`);

    window.location.href = `mailto:j7840790@gmail.com?subject=${subject}&body=${body}`;
    setIsModalOpen(false);
  };

  return (
    <div className="fixed top-0 left-0 right-0 z-[1001] bg-gradient-to-b from-gray-900 to-black py-2 md:py-4 border-b-2 md:border-b-4 border-yellow-500 shadow-2xl">
      <div className="container mx-auto px-2 md:px-4">
        <div className="relative overflow-hidden bg-black/50 rounded-lg border border-yellow-600/30 p-2 md:p-4 shadow-inner">
          {/* 상단 인디케이터 라인 */}
          <div className="flex justify-between items-center mb-1 md:mb-2 text-[10px] md:text-xs text-yellow-500/70 font-mono">
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
            className={`text-center text-lg md:text-3xl lg:text-5xl font-bold tracking-widest transition-all duration-300 font-[PfStardust30] ${
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

          {/* 오른쪽 하단 로딩 표시 */}
          <div className="absolute bottom-1 md:bottom-2 right-2 flex items-center gap-1 md:gap-2 text-yellow-400/70 text-[10px] md:text-xs font-mono">
            <Loader2 className="w-3 h-3 md:w-4 md:h-4 animate-spin drop-shadow-[0_0_5px_rgba(250,204,21,0.5)]" />
            <span className="hidden md:inline drop-shadow-[0_0_5px_rgba(250,204,21,0.5)]">축사 찍는중...</span>
          </div>
        </div>

        {/* 마커 범례 토글 버튼 (모바일) */}
        <button
          onClick={() => setShowLegend(!showLegend)}
          className="md:hidden absolute top-36 left-2 translate-y-2 bg-black/70 backdrop-blur-sm border border-yellow-600/30 rounded px-2 py-1 shadow-lg text-yellow-400 text-xs"
        >
          📊 {sentCount}/{schoolCount}
        </button>

        {/* 마커 범례 및 통계 카드 (데스크톱) */}
        <div className="hidden md:block absolute top-full right-4 translate-y-[15px] bg-black/70 backdrop-blur-sm border-2 border-yellow-600/30 rounded-lg px-4 py-3 shadow-lg">
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <img
                src="https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-orange.png"
                alt="주황색 마커"
                className="w-5 h-8 drop-shadow-md"
              />
              <span className="text-sm text-yellow-100/90 font-medium">
                축사 전송 완료 <span className="font-bold text-orange-400 ml-1">{sentCount}개교</span>
              </span>
            </div>
            <div className="flex items-center gap-2">
              <img
                src="https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-grey.png"
                alt="회색 마커"
                className="w-5 h-8 drop-shadow-md"
              />
              <span className="text-sm text-yellow-100/90 font-medium">
                축사 찍는 중 <span className="font-bold text-gray-400 ml-1">{pendingCount}개교</span>
              </span>
            </div>
          </div>
        </div>

        {/* 모바일 범례 팝업 */}
        {showLegend && (
          <div className="md:hidden fixed top-[150px] left-2 bg-black/90 backdrop-blur-sm border border-yellow-600/30 rounded-lg px-3 py-2 shadow-lg z-[1002]">
            <button
              onClick={() => setShowLegend(false)}
              className="absolute top-1 right-1 text-yellow-400/70 hover:text-yellow-400"
            >
              ✕
            </button>
            <div className="flex flex-col gap-2 text-xs">
              <div className="flex items-center gap-2">
                <div className="w-4 h-6 rounded-full bg-orange-500"></div>
                <span className="text-yellow-100/90">
                  전송 완료 <span className="font-bold text-orange-400 ml-1">{sentCount}개교</span>
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-6 rounded-full bg-gray-400"></div>
                <span className="text-yellow-100/90">
                  찍는 중 <span className="font-bold text-gray-400 ml-1">{pendingCount}개교</span>
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
