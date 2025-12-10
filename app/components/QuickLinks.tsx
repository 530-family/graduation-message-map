"use client";

import { ExternalLink, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";

export default function QuickLinks() {
  const [isExpanded, setIsExpanded] = useState(true);

  const links = [
    {
      name: "국회의원 이준석",
      url: "https://dongtanman.kr",
    },
    {
      name: "펭귄밥주기 - 후원 사이트",
      url: "https://givemoney.kr",
    },
    {
      name: "이준석 페이스북",
      url: "https://www.facebook.com/junseokandylee/",
    },
    {
      name: "이준석 네이버 블로그",
      url: "https://blog.naver.com/PostList.naver?blogId=futurejslee&categoryNo=1&skinType=&skinId=&from=menu&userSelectMenu=true",
    },
    {
      name: "이준석 인스타그램",
      url: "https://www.instagram.com/junseokandylee/",
    },
    {
      name: "이준석 유튜브",
      url: "https://www.youtube.com/@junseoktube",
    },
  ];

  return (
    <div
      className={`fixed bottom-4 right-4 rounded-lg shadow-lg p-4 z-400
    ${isExpanded ? "bg-white" : "bg-linear-to-b from-white to-white/70"}`}
    >
      <div className="flex flex-col gap-2">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center justify-between text-sm font-semibold text-gray-800 md:cursor-default"
        >
          <span>바로가기</span>
          <span className="md:hidden">
            {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </span>
        </button>
        <div
          className={`flex flex-col gap-2 transition-all duration-300 overflow-hidden ${
            isExpanded
              ? "max-h-96 opacity-100"
              : "max-h-0 opacity-0 md:max-h-96 md:opacity-100"
          }`}
        >
          {links.map((link) => (
            <a
              key={link.name}
              href={link.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-gray-700 hover:text-gray-900 hover:underline transition-colors"
            >
              <ExternalLink size={14} />
              {link.name}
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
