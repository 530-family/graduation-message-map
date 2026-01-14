"use client";

import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useState, useRef } from "react";
import L from "leaflet";

export interface SchoolData {
  schoolName: string;
  address: string;
  coordinates: {
    longitude: number;
    latitude: number;
  };
  videoStatus?: string;
  videoUrl?: string;
}

interface KoreaMapProps {
  selectedSchool: SchoolData | null;
}

// Fix for default marker icon issue in Next.js
const fixMarkerIcon = () => {
  delete (L.Icon.Default.prototype as any)._getIconUrl;
  L.Icon.Default.mergeOptions({
    iconRetinaUrl:
      "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png",
    iconUrl:
      "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
    shadowUrl:
      "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
  });
};

// Orange: 전송완료
const orangeIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-orange.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

// Grey: 대기중
const greyIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-grey.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

// Function to get marker icon based on videoStatus
const getMarkerIcon = (videoStatus?: string) => {
  // 전송완료면 orange, 그 외(대기중/업로드완료/메일작성완료)는 grey
  if (videoStatus === "전송완료") return orangeIcon;
  return greyIcon;
};

// Component to control map programmatically
function MapController({
  selectedSchool,
}: {
  selectedSchool: SchoolData | null;
}) {
  const map = useMap();

  // Pan to selected school
  useEffect(() => {
    if (selectedSchool) {
      const position: [number, number] = [
        selectedSchool.coordinates.latitude,
        selectedSchool.coordinates.longitude,
      ];
      map.flyTo(position, 13, { duration: 1.5 });
    }
  }, [selectedSchool, map]);

  return null;
}

export default function KoreaMap({ selectedSchool }: KoreaMapProps) {
  const [schools, setSchools] = useState<SchoolData[]>([]);
  const markerRefs = useRef<{ [key: string]: L.Marker }>({});

  useEffect(() => {
    fixMarkerIcon();

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

  // 한국의 중심 좌표 (서울)
  const center: [number, number] = [36.6665, 127.878];

  // All valid schools for display
  const validSchools = schools.filter(
    (school) =>
      school.coordinates.latitude !== 0 || school.coordinates.longitude !== 0
  );

  const handleMarkerRef = (marker: L.Marker | null, school: SchoolData) => {
    if (marker) {
      const key = `${school.coordinates.latitude}-${school.coordinates.longitude}`;
      markerRefs.current[key] = marker;
    }
  };

  // Open popup when selectedSchool changes
  useEffect(() => {
    if (selectedSchool) {
      const key = `${selectedSchool.coordinates.latitude}-${selectedSchool.coordinates.longitude}`;
      setTimeout(() => {
        const marker = markerRefs.current[key];
        if (marker) {
          marker.openPopup();
        }
      }, 1600); // Wait for flyTo animation to complete
    }
  }, [selectedSchool]);

  return (
    <div className="w-full h-screen">
      <MapContainer
        center={center}
        zoom={7}
        scrollWheelZoom={true}
        className="w-full h-full"
      >
        <MapController selectedSchool={selectedSchool} />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {validSchools.map((school, index) => (
          <Marker
            key={index}
            position={[
              school.coordinates.latitude,
              school.coordinates.longitude,
            ]}
            icon={getMarkerIcon(school.videoStatus)}
            ref={(marker) => handleMarkerRef(marker, school)}
            zIndexOffset={
              selectedSchool?.schoolName === school.schoolName ? 2000 : school.videoStatus === "전송완료" ? 1000 : 500
            }
          >
            <Popup>
              <div>
                <p className="text-xs text-gray-500 mb-1">#{index + 1}</p>
                <h3 className="font-bold">{school.schoolName}</h3>
                <p className="text-sm">{school.address}</p>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
