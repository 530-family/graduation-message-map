"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function ApplyPage() {
  const router = useRouter();

  useEffect(() => {
    // 메인 페이지로 리다이렉트하면서 쿼리 파라미터 추가
    router.replace("/?apply=true");
  }, [router]);

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 to-black flex items-center justify-center p-4">
      <div className="text-white text-center">
        <p>로딩 중...</p>
      </div>
    </div>
  );
}
