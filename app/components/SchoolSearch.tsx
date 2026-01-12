"use client";

import { useState, useEffect } from "react";

interface SchoolData {
  schoolName: string;
  address: string;
  coordinates: {
    longitude: number;
    latitude: number;
  };
  videoStatus?: string;
  videoUrl?: string;
}

interface SchoolSearchProps {
  schools: SchoolData[];
  selectedSchool: SchoolData | null;
  onSchoolSelect: (school: SchoolData) => void;
  onClearSelection: () => void;
}

export default function SchoolSearch({
  schools,
  selectedSchool,
  onSchoolSelect,
  onClearSelection,
}: SchoolSearchProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [showSearchResults, setShowSearchResults] = useState(true);

  // Filter schools based on search term
  const filteredSchools = schools.filter((school) => {
    const validCoordinates =
      school.coordinates.latitude !== 0 || school.coordinates.longitude !== 0;
    const matchesSearch =
      searchTerm === "" ||
      school.schoolName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      school.address.toLowerCase().includes(searchTerm.toLowerCase());
    return validCoordinates && matchesSearch;
  });

  const handleSearchClick = (school: SchoolData) => {
    onSchoolSelect(school);
    setShowSearchResults(false);
  };

  return (
    <div className="fixed top-[60px] md:top-[140px] left-0 right-0 z-[1002] w-full flex justify-center px-4 py-2 md:py-3 pointer-events-none">
      <div className="w-full max-w-md bg-black/80 backdrop-blur-md rounded-lg border-2 border-yellow-600/30 shadow-2xl overflow-hidden pointer-events-auto">
        <div className="p-2 md:p-3">
          <div className="relative">
            <input
              type="text"
              placeholder="🔍 학교 이름 또는 주소로 검색..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setShowSearchResults(true);
              }}
              onFocus={() => setShowSearchResults(true)}
              className="w-full px-3 py-2 md:px-4 md:py-2 bg-black/50 border border-yellow-600/30 rounded-md focus:outline-none focus:ring-2 focus:ring-yellow-500/50 text-yellow-100 placeholder-yellow-600/50 text-sm md:text-base"
            />
            {searchTerm && (
              <button
                onClick={() => {
                  setSearchTerm("");
                  setShowSearchResults(true);
                }}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-yellow-600/50 hover:text-yellow-400 transition-colors"
              >
                ✕
              </button>
            )}
          </div>
        </div>
        {/* Search Results */}
        {showSearchResults && searchTerm && (
          <div className="max-h-60 md:max-h-64 overflow-y-auto border-t border-yellow-600/20 bg-black/90">
            {filteredSchools.length > 0 ? (
              filteredSchools.map((school, index) => (
                <button
                  key={index}
                  onClick={() => handleSearchClick(school)}
                  className="w-full px-3 py-2 md:px-4 md:py-3 text-left hover:bg-yellow-600/10 transition-colors border-b border-yellow-600/10 last:border-b-0 flex items-center gap-2 md:gap-3"
                >
                  <div
                    className={`w-2 h-2 md:w-3 md:h-3 rounded-full flex-shrink-0 ${
                      school.videoStatus === "Sent"
                        ? "bg-orange-500 drop-shadow-[0_0_8px_rgba(249,115,22,0.8)]"
                        : "bg-gray-400"
                    }`}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-yellow-100 text-xs md:text-sm truncate">
                      {school.schoolName}
                    </p>
                    <p className="text-[10px] md:text-xs text-yellow-600/70 truncate">
                      {school.address}
                    </p>
                  </div>
                </button>
              ))
            ) : (
              <div className="px-4 py-6 md:py-8 text-yellow-600/50 text-sm text-center">
                <p className="text-2xl md:text-3xl mb-2">🔍</p>
                <p>검색 결과가 없습니다</p>
              </div>
            )}
          </div>
        )}
        {/* Selected school display */}
        {!showSearchResults && selectedSchool && (
          <div className="p-2 md:p-3 bg-yellow-600/10 border-t border-yellow-600/30">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <div
                  className={`w-2 h-2 md:w-3 md:h-3 rounded-full flex-shrink-0 ${
                    selectedSchool.videoStatus === "Sent"
                      ? "bg-orange-500 drop-shadow-[0_0_8px_rgba(249,115,22,0.8)]"
                      : "bg-gray-400"
                  }`}
                />
                <span className="text-xs md:text-sm font-medium text-yellow-100 truncate">
                  {selectedSchool.schoolName}
                </span>
              </div>
              <button
                onClick={onClearSelection}
                className="text-xs md:text-sm text-yellow-400 hover:text-yellow-200 transition-colors flex-shrink-0 px-2 py-1 hover:bg-yellow-600/20 rounded"
              >
                닫기 ✕
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
