"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { X, Search, Loader2, Mail, MapPin } from "lucide-react";

interface School {
  name: string;
  address: string;
  source: "school" | "university" | "manual";
}

interface FormData {
  email: string;
  schoolName: string;
  address: string;
  graduationDate: string;
  requestDetails: string;
}

interface RequestFormProps {
  isOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  initialSchoolName?: string;
  initialAddress?: string;
}

export default function RequestForm({
  isOpen: controlledIsOpen,
  onOpenChange,
  initialSchoolName = "",
  initialAddress = "",
}: RequestFormProps) {
  const [internalIsOpen, setInternalIsOpen] = useState(false);
  const [schools, setSchools] = useState<School[]>([]);
  const [isLoadingData, setIsLoadingData] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedSchool, setSelectedSchool] = useState<School | null>(null);
  const [isManualInput, setIsManualInput] = useState(false);
  const [submitStatus, setSubmitStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");

  const [formData, setFormData] = useState<FormData>({
    email: "",
    schoolName: "",
    address: "",
    graduationDate: "",
    requestDetails: "",
  });

  // 제어된 모드인지 비제어된 모드인지 확인
  const isControlled = controlledIsOpen !== undefined;
  const isOpen = isControlled ? controlledIsOpen : internalIsOpen;

  const handleSetIsOpen = (value: boolean) => {
    if (isControlled && onOpenChange) {
      onOpenChange(value);
    } else {
      setInternalIsOpen(value);
    }
  };

  // 쿼리 파라미터로 모달 열기
  const searchParams = useSearchParams();
  useEffect(() => {
    if (searchParams.get("apply") === "true" || searchParams.get("open") === "true") {
      setInternalIsOpen(true);
    }
  }, [searchParams]);

  // 초기 학교명/주소가 변경될 때 폼 업데이트
  useEffect(() => {
    if (initialSchoolName || initialAddress) {
      setSearchQuery(initialSchoolName);
      setFormData((prev) => ({
        ...prev,
        schoolName: initialSchoolName,
        address: initialAddress,
      }));
      if (initialAddress) {
        const matchedSchool = schools.find(
          (s) => s.name === initialSchoolName && s.address === initialAddress
        );
        if (matchedSchool) {
          setSelectedSchool(matchedSchool);
          setIsManualInput(false);
        } else {
          setSelectedSchool(null);
          setIsManualInput(true);
        }
      }
    }
  }, [initialSchoolName, initialAddress, schools]);

  // CSV 파일에서 학교 데이터 로드
  useEffect(() => {
    const loadSchoolData = async () => {
      try {
        setIsLoadingData(true);
        const [schoolResponse, universityResponse] = await Promise.all([
          fetch("/data/schoolInfo_utf8.csv"),
          fetch("/data/universityInfo_utf8.csv"),
        ]);

        const [schoolText, universityText] = await Promise.all([
          schoolResponse.text(),
          universityResponse.text(),
        ]);

        // 간단한 파싱 - 쉼표로 구분하고 따옴표 처리
        const parseCSV = (text: string): string[][] => {
          const lines = text.split("\n");
          const result: string[][] = [];
          for (const line of lines) {
            if (!line.trim()) continue;
            const columns: string[] = [];
            let current = "";
            let inQuotes = false;
            for (let i = 0; i < line.length; i++) {
              const char = line[i];
              if (char === '"') {
                inQuotes = !inQuotes;
              } else if (char === ',' && !inQuotes) {
                columns.push(current);
                current = "";
              } else {
                current += char;
              }
            }
            if (current) columns.push(current);
            if (columns.length > 0) result.push(columns);
          }
          return result;
        };

        const schoolRows = parseCSV(schoolText);
        const universityRows = parseCSV(universityText);

        const result: School[] = [];

        // schoolInfo.csv: 3번째 열이 학교명, 10번째 열(도로명주소) + 11번째 열(도로명상세주소)가 주소
        for (const row of schoolRows.slice(1)) {
          if (row.length > 11) {
            const name = row[3]?.trim() || "";
            const roadAddress = row[10]?.trim() || "";
            const roadDetail = row[11]?.trim() || "";
            const address = roadDetail ? `${roadAddress} ${roadDetail}` : roadAddress;
            if (name && address) {
              result.push({ name, address, source: "school" });
            }
          }
        }

        // universityInfo.csv: 0번째 열이 학교명, 7번째 열(도로명주소) + 8번째 열(도로명상세주소)가 주소
        for (const row of universityRows.slice(1)) {
          if (row.length > 8) {
            const name = row[0]?.trim() || "";
            const roadAddress = row[7]?.trim() || "";
            const roadDetail = row[8]?.trim() || "";
            const address = roadDetail ? `${roadAddress} ${roadDetail}` : roadAddress;
            if (name && address) {
              result.push({ name, address, source: "university" });
            }
          }
        }

        setSchools(result);
      } catch (error) {
        console.error("Failed to load school data:", error);
      } finally {
        setIsLoadingData(false);
      }
    };

    loadSchoolData();
  }, []);

  // 다음 주소 창 API 로드
  useEffect(() => {
    const script = document.createElement("script");
    script.src = "//t1.daumcdn.net/mapjsapi/bundle/postcode/prod/postcode.v2.js";
    script.async = true;
    document.body.appendChild(script);

    return () => {
      if (document.body.contains(script)) {
        document.body.removeChild(script);
      }
    };
  }, []);

  // 주소 검색 완료 callback
  const handleCompleteAddress = (data: any) => {
    let fullAddress = data.roadAddress || data.jibunAddress || "";
    let extraAddress = "";

    if (data.userSelectedType === "R") {
      // 도로명 주소 선택
      if (data.bname && /[동|로|가]$/g.test(data.bname)) {
        extraAddress += data.bname;
      }
      if (data.buildingName && data.apartment === "Y") {
        extraAddress += extraAddress ? `, ${data.buildingName}` : data.buildingName;
      }
      if (extraAddress) {
        extraAddress = ` (${extraAddress})`;
      }
    }

    fullAddress += extraAddress;
    setFormData((prev) => ({ ...prev, address: fullAddress }));
  };

  // 주소 검색창 열기
  const openAddressSearch = () => {
    if (typeof window !== "undefined" && (window as any).daum && (window as any).daum.postcode) {
      new (window as any).daum.Postcode({
        oncomplete: handleCompleteAddress,
        width: 500,
        height: 600,
      }).open();
    }
  };

  // 학교명 검색 필터링
  const filteredSchools = schools.filter((school) => {
    if (isManualInput) return [];
    const query = searchQuery.toLowerCase().trim();
    if (!query) return [];
    return school.name.toLowerCase().includes(query);
  }).slice(0, 10);

  // 학교 선택
  const handleSelectSchool = (school: School) => {
    setSelectedSchool(school);
    setSearchQuery(school.name);
    setShowSuggestions(false);
    setFormData((prev) => ({
      ...prev,
      schoolName: school.name,
      address: school.address,
    }));
  };

  // 직접 입력 모드
  const handleManualInput = () => {
    setIsManualInput(true);
    setSelectedSchool(null);
    setFormData((prev) => ({
      ...prev,
      schoolName: searchQuery,
      address: "",
    }));
    setShowSuggestions(false);
  };

  // 검색어 변경
  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchQuery(value);

    // 검색어가 비면 주소도 초기화 및 선택된 학교 해제
    if (!value.trim()) {
      setFormData((prev) => ({
        ...prev,
        schoolName: "",
        address: "",
      }));
      setSelectedSchool(null);
      setIsManualInput(false);
      setShowSuggestions(false);
      return;
    }

    // 직접 입력 모드에서 다시 검색어 입력 시 자동 모드로 전환
    if (isManualInput) {
      setIsManualInput(false);
    }

    setFormData((prev) => ({
      ...prev,
      schoolName: value,
    }));
    setShowSuggestions(true);
  };

  // 폼 제출
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.email || !formData.schoolName || !formData.address || !formData.graduationDate || !formData.requestDetails) {
      setErrorMessage("모든 필드를 입력해주세요.");
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(formData.email)) {
      setErrorMessage("유효한 이메일 주소를 입력해주세요.");
      return;
    }

    try {
      setSubmitStatus("loading");
      setErrorMessage("");

      const response = await fetch("/api/submit-request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "제출 실패");
      }

      setSubmitStatus("success");

      setTimeout(() => {
        setFormData({
          email: "",
          schoolName: "",
          address: "",
          graduationDate: "",
          requestDetails: "",
        });
        setSearchQuery("");
        setSelectedSchool(null);
        setIsManualInput(false);
        setSubmitStatus("idle");
        handleSetIsOpen(false);
      }, 3000);
    } catch (error) {
      setSubmitStatus("error");
      setErrorMessage(error instanceof Error ? error.message : "제출 중 오류가 발생했습니다.");
    }
  };

  return (
    <>
      {/* 열기 버튼 (항상 표시) */}
      {!isControlled && (
        <button
          onClick={() => handleSetIsOpen(true)}
          className="cursor-pointer fixed top-[280px] right-4 bg-black/80 hover:bg-black/90 border-2 border-yellow-500 hover:border-yellow-400 rounded-lg px-7 py-3 shadow-[0_0_20px_rgba(234,179,8,0.4)] hover:shadow-[0_0_35px_rgba(234,179,8,0.7)] transition-all duration-300 flex items-center gap-2 font-bold text-yellow-400 hover:text-yellow-300 z-[1002]"
        >
          <Mail className="w-5 h-5 animate-bounce drop-shadow-[0_0_8px_rgba(250,204,21,0.8)]" />
          <span className="drop-shadow-[0_0_8px_rgba(250,204,21,0.8)]">
            우리 학교도 신청하기!
          </span>
        </button>
      )}

      {/* 폼 모달 */}
      {isOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[1003] p-4">
          <div className="bg-gradient-to-b from-gray-900 to-black rounded-lg shadow-2xl max-w-2xl w-full p-6 relative border-2 border-yellow-600/30 max-h-[90vh] overflow-y-auto">
            {/* 닫기 버튼 */}
            <button
              onClick={() => handleSetIsOpen(false)}
              className="cursor-pointer absolute top-4 right-4 text-yellow-400/70 hover:text-yellow-400 transition-colors p-2 -m-2 rounded-lg hover:bg-yellow-900/30"
            >
              <X className="w-6 h-6 drop-shadow-[0_0_5px_rgba(250,204,21,0.5)]" />
            </button>

            {/* 제목 */}
            <h2 className="text-2xl font-bold text-yellow-400 mb-4 drop-shadow-[0_0_10px_rgba(250,204,21,0.8)]">
              우리 학교도 졸업 축하받기! 🙋
            </h2>

            {/* 설명 */}
            <p className="text-yellow-100/80 mb-6">
              이메일이 정확한지 꼭 확인해 주세요! 축사 영상은 입력해 주신 이메일로 보내드립니다. <br />
              정보를 잘못 입력하셨거나, 축사가 누락된 경우 j7840790@gmail.com으로 문의해 주세요. <br />
              외국 소재의 학교도 가능합니다.
            </p>

            {/* 폼 */}
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* 이메일 */}
              <div>
                <label className="block text-sm font-medium text-yellow-300 mb-1 drop-shadow-[0_0_5px_rgba(250,204,21,0.5)]">
                  이메일 <span className="text-red-400">*</span>
                </label>
                <input
                  type="email"
                  required
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="w-full px-4 py-3 bg-black/50 border-2 border-yellow-600/30 rounded-lg text-white placeholder-yellow-100/30 focus:outline-none focus:border-yellow-500/50"
                  placeholder="your@email.com"
                />
              </div>

              {/* 학교명 검색 */}
              <div className="relative">
                <label className="block text-sm font-medium text-yellow-300 mb-1 drop-shadow-[0_0_5px_rgba(250,204,21,0.5)]">
                  학교명 <span className="text-red-400">*</span>
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none z-10">
                    {isLoadingData ? (
                      <Loader2 size={18} className="animate-spin text-yellow-400" />
                    ) : (
                      <Search size={18} className="text-yellow-400" />
                    )}
                  </div>
                  <input
                    type="text"
                    required
                    value={searchQuery}
                    onChange={handleSearchChange}
                    onFocus={() => searchQuery && !isManualInput && !selectedSchool && setShowSuggestions(true)}
                    disabled={!!selectedSchool}
                    className="w-full pl-10 pr-10 py-3 bg-black/50 border-2 border-yellow-600/30 rounded-lg text-white placeholder-yellow-100/30 focus:outline-none focus:border-yellow-500/50 disabled:bg-black/30 disabled:cursor-not-allowed"
                    placeholder={selectedSchool ? "학교 선택됨" : "학교명 검색..."}
                  />
                  {/* 선택된 학교 초기화 X 버튼 */}
                  {selectedSchool && (
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedSchool(null);
                        setSearchQuery("");
                        setFormData((prev) => ({
                          ...prev,
                          schoolName: "",
                          address: "",
                        }));
                        setIsManualInput(false);
                      }}
                      className="cursor-pointer absolute inset-y-0 right-0 pr-3 flex items-center text-yellow-400 hover:text-yellow-300 transition-colors z-10"
                    >
                      <X size={18} />
                    </button>
                  )}
                </div>

                {/* 검색 제안 */}
                {showSuggestions && filteredSchools.length > 0 && (
                  <div className="absolute z-10 w-full mt-1 bg-gray-900 border-2 border-yellow-600/30 rounded-lg shadow-lg max-h-60 overflow-y-auto">
                    {filteredSchools.map((school, index) => (
                      <button
                        key={index}
                        type="button"
                        onClick={() => handleSelectSchool(school)}
                        className="cursor-pointer w-full text-left px-4 py-3 hover:bg-yellow-600/20 transition-colors border-b border-yellow-600/10 last:border-b-0"
                      >
                        <div className="font-medium text-white">{school.name}</div>
                        <div className="text-sm text-yellow-100/50">{school.address}</div>
                      </button>
                    ))}
                    <button
                      type="button"
                      onClick={handleManualInput}
                      className="cursor-pointer w-full text-left px-4 py-3 hover:bg-yellow-600/20 transition-colors text-yellow-400 font-medium border-t border-yellow-600/20"
                    >
                      + 직접 입력하기
                    </button>
                  </div>
                )}

                {showSuggestions && filteredSchools.length === 0 && !isManualInput && !selectedSchool && (
                  <div className="absolute z-10 w-full mt-1 bg-gray-900 border-2 border-yellow-600/30 rounded-lg shadow-lg">
                    <button
                      type="button"
                      onClick={handleManualInput}
                      className="cursor-pointer w-full text-left px-4 py-3 hover:bg-yellow-600/20 transition-colors text-yellow-400 font-medium"
                    >
                      + "{searchQuery}"(으)로 직접 입력하기
                    </button>
                  </div>
                )}
              </div>

              {/* 주소 */}
              <div>
                <label className="block text-sm font-medium text-yellow-300 mb-1 drop-shadow-[0_0_5px_rgba(250,204,21,0.5)]">
                  학교 주소 <span className="text-red-400">*</span>
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    required
                    value={formData.address}
                    onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                    className="flex-1 px-4 py-3 bg-black/50 border-2 border-yellow-600/30 rounded-lg text-white placeholder-yellow-100/30 focus:outline-none focus:border-yellow-500/50 disabled:bg-black/30"
                    placeholder={selectedSchool ? "자동 입력됨" : "주소를 입력해주세요"}
                    disabled={!!selectedSchool}
                  />
                  {isManualInput && !selectedSchool && (
                    <button
                      type="button"
                      onClick={openAddressSearch}
                      className="cursor-pointer px-4 py-3 bg-yellow-600/20 hover:bg-yellow-600/30 border-2 border-yellow-600/30 rounded-lg text-yellow-400 transition-colors flex items-center gap-2 whitespace-nowrap"
                    >
                      <MapPin size={18} />
                      <span>주소 검색</span>
                    </button>
                  )}
                </div>
                {selectedSchool && (
                  <p className="text-xs text-yellow-100/50 mt-1">학교 선택으로 자동 입력된 주소입니다.</p>
                )}
              </div>

              {/* 졸업식 날짜 */}
              <div>
                <label className="block text-sm font-medium text-yellow-300 mb-1 drop-shadow-[0_0_5px_rgba(250,204,21,0.5)]">
                  졸업식 날짜 <span className="text-red-400">*</span>
                </label>
                <input
                  type="date"
                  required
                  value={formData.graduationDate}
                  onChange={(e) => setFormData({ ...formData, graduationDate: e.target.value })}
                  onClick={(e) => (e.target as HTMLInputElement).showPicker?.()}
                  className="w-full px-4 py-3 bg-black/50 border-2 border-yellow-600/30 rounded-lg text-white focus:outline-none focus:border-yellow-500/50 [color-scheme:dark] cursor-pointer"
                />
              </div>

              {/* 요청 사항 */}
              <div>
                <label className="block text-sm font-medium text-yellow-300 mb-1 drop-shadow-[0_0_5px_rgba(250,204,21,0.5)]">
                  축사에 꼭 포함했으면 하는 내용 <span className="text-red-400">*</span>
                </label>
                <textarea
                  required
                  value={formData.requestDetails}
                  onChange={(e) => setFormData({ ...formData, requestDetails: e.target.value })}
                  rows={4}
                  className="w-full px-4 py-3 bg-black/50 border-2 border-yellow-600/30 rounded-lg text-white placeholder-yellow-100/30 focus:outline-none focus:border-yellow-500/50"
                  placeholder="만약 없다면 '없음'이라고 적어주세요."
                />
              </div>

              {/* 에러 메시지 */}
              {errorMessage && (
                <div className="bg-yellow-900/50 border border-yellow-600/50 text-yellow-200 px-4 py-3 rounded-lg">
                  {errorMessage}
                </div>
              )}

              {/* 성공 메시지 */}
              {submitStatus === "success" && (
                <div className="bg-green-900/50 border border-green-600/50 text-green-200 px-4 py-3 rounded-lg">
                  요청이 성공적으로 제출되었습니다!
                </div>
              )}

              {/* 버튼 */}
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => handleSetIsOpen(false)}
                  className="cursor-pointer flex-1 bg-black/70 hover:bg-black/90 border-2 border-yellow-600/30 hover:border-yellow-500/50 text-yellow-400 hover:text-yellow-300 py-3 rounded-lg font-semibold transition-all duration-300"
                  disabled={submitStatus === "loading"}
                >
                  취소
                </button>
                <button
                  type="submit"
                  disabled={submitStatus === "loading"}
                  className="cursor-pointer flex-1 bg-yellow-600 hover:bg-yellow-700 text-white py-3 rounded-lg font-semibold transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {submitStatus === "loading" ? (
                    <span className="flex items-center justify-center gap-2">
                      <Loader2 size={18} className="animate-spin" />
                      제출 중...
                    </span>
                  ) : (
                    "제출"
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
