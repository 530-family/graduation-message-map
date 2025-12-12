"use client";

import { useEffect, useState } from "react";
import { Mail, X, Copy, Send, Loader2 } from "lucide-react";

export default function LEDDisplayBoard() {
  const [isVisible, setIsVisible] = useState(true);
  const [isMounted, setIsMounted] = useState(false);
  const [schoolCount, setSchoolCount] = useState(0);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isCopied, setIsCopied] = useState(false);

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
    <div className="fixed top-0 left-0 right-0 z-1001 bg-linear-to-b from-gray-900 to-black py-4 border-b-4 border-yellow-500 shadow-2xl">
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

          {/* 오른쪽 하단 로딩 표시 */}
          <div className="absolute bottom-2 right-2 flex items-center gap-2 text-yellow-400/70 text-xs font-mono">
            <Loader2 className="w-4 h-4 animate-spin drop-shadow-[0_0_5px_rgba(250,204,21,0.5)]" />
            <span className="drop-shadow-[0_0_5px_rgba(250,204,21,0.5)]">축사 작성중...</span>
          </div>
        </div>

        {/* 우리 학교도? 버튼 */}
        <button
          onClick={() => setIsModalOpen(true)}
          className="absolute top-full mt-4 right-4 bg-black/70 hover:bg-black/90 border-2 border-yellow-600/30 hover:border-yellow-500/50 rounded-lg px-6 py-3 shadow-lg hover:shadow-xl transition-all duration-300 flex items-center gap-2 font-semibold text-yellow-400 hover:text-yellow-300"
        >
          <Mail className="w-5 h-5 drop-shadow-[0_0_5px_rgba(250,204,21,0.5)]" />
          <span className="font-[PfStardust30] font-(800) drop-shadow-[0_0_5px_rgba(250,204,21,0.5)]">
            우리 학교도?
          </span>
        </button>
      </div>

      {/* 모달 */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[1001] p-4">
          <div className="bg-gradient-to-b from-gray-900 to-black rounded-lg shadow-2xl max-w-md w-full p-6 relative border-2 border-yellow-600/30">
            {/* 닫기 버튼 */}
            <button
              onClick={() => setIsModalOpen(false)}
              className="absolute top-4 right-4 text-yellow-400/70 hover:text-yellow-400 transition-colors"
            >
              <X className="w-6 h-6 drop-shadow-[0_0_5px_rgba(250,204,21,0.5)]" />
            </button>

            {/* 제목 */}
            <h2 className="text-2xl font-bold text-yellow-400 mb-4 font-[PfStardust30] drop-shadow-[0_0_10px_rgba(250,204,21,0.8)]">
              졸업 축하 요청
            </h2>

            {/* 설명 */}
            <p className="text-yellow-100/80 mb-6">
              여러분의 학교에도 졸업 축하 메세지를 전할 수 있습니다. <br />
              보내는 곳: j7840790@gmail.com
            </p>

            {/* 가이드라인 */}
            <div className="bg-black/50 border border-yellow-600/30 rounded-lg p-4 mb-6">
              <h3 className="font-semibold text-yellow-400 mb-2 drop-shadow-[0_0_5px_rgba(250,204,21,0.5)]">
                메일에 포함해주세요:
              </h3>
              <ul className="text-sm text-yellow-100/70 space-y-1">
                <li>
                  • 학교명 / 소재지 (동명의 다른 학교와 헷갈릴 수 있어요!)
                </li>
                <li>• 졸업식 날짜 </li>
                <li>• 축사에 꼭 포함했으면 하는 내용 (선택사항)</li>
                <li>
                  • 아래 <strong>①, ② 각각 하나씩</strong>을 동시에 찍어
                  첨부해주세요.
                </li>
                <div
                  className="ml-4 mt-2 space-y-1 bg-yellow-600/10 rounded p-2 border-l-2 
  border-yellow-600/50"
                >
                  <li>① 학생증 / 청소년증 / 교복 착용샷 중 1가지</li>
                  <li>
                    &nbsp;&nbsp;※ 학생증·청소년증 사진은 주민등록번호, 주소 등{" "}
                    <strong>민감한 개인정보</strong>를 모두 가려주세요.
                  </li>
                  <li>
                    ② 시계 <em>또는</em> &lsquo;이준석 파이팅&rsquo;이라고 쓴
                    쪽지
                  </li>
                </div>
              </ul>
            </div>

            {/* 버튼들 */}
            <div className="flex gap-3">
              {/* 이메일 보내기 버튼 */}
              <button
                onClick={handleEmailClick}
                className="flex-1 bg-black/70 hover:bg-black/90 border-2 border-yellow-600/30 hover:border-yellow-500/50 text-yellow-400 hover:text-yellow-300 py-3 rounded-lg font-semibold flex items-center justify-center gap-2 transition-all duration-300 drop-shadow-[0_0_5px_rgba(250,204,21,0.5)]"
              >
                <Send className="w-5 h-5" />
                이메일 보내기
              </button>

              {/* 이메일 주소 복사하기 버튼 */}
              <button
                onClick={handleCopyEmail}
                className="flex-1 bg-black/70 hover:bg-black/90 border-2 border-yellow-600/30 hover:border-yellow-500/50 text-yellow-400 hover:text-yellow-300 py-3 rounded-lg font-semibold flex items-center justify-center gap-2 transition-all duration-300 drop-shadow-[0_0_5px_rgba(250,204,21,0.5)]"
              >
                <Copy className="w-5 h-5" />
                {isCopied ? "복사완료!" : "주소 복사"}
              </button>
            </div>

            {/* 추가 안내 */}
            <p className="text-xs text-yellow-100/50 text-center leading-5 mt-4">
              제출된 자료는 학생 신분 확인 목적 외에는 사용되지 않습니다. <br />{" "}
              요청해주신 축사는 검토 후 순차적으로 발송됩니다.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
