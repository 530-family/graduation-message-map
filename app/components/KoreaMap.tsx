"use client";

import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useState } from "react";
import L from "leaflet";

interface SchoolData {
  schoolName: string;
  address: string;
  coordinates: {
    longitude: number;
    latitude: number;
  };
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

// Create orange marker icon
const orangeIcon = new L.Icon({
  iconUrl:
    "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-orange.png",
  shadowUrl:
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

export default function KoreaMap() {
  const [schools, setSchools] = useState<SchoolData[]>([]);

  useEffect(() => {
    fixMarkerIcon();

    // NDJSON 파일 로드
    fetch("/data/coordinates.ndjson")
      .then((response) => {
        // console.log("Response status:", response.status);
        return response.text();
      })
      .then((text) => {
        // console.log("Raw text:", text);
        // JSON 객체들을 배열로 파싱 (여러 줄에 걸쳐 있는 경우)
        // "}\n{" 패턴을 찾아서 분리
        const jsonObjects = text
          .trim()
          .split(/\}\s*\{/)
          .map((obj, index, array) => {
            // 첫 번째가 아니면 앞에 { 추가
            if (index > 0) obj = "{" + obj;
            // 마지막이 아니면 뒤에 } 추가
            if (index < array.length - 1) obj = obj + "}";
            return obj.trim();
          })
          .filter((obj) => obj);

        const data = jsonObjects.map((obj) => JSON.parse(obj));
        // console.log("Parsed schools data:", data);
        setSchools(data);
      })
      .catch((error) => {
        console.error("Failed to load coordinates data:", error);
      });
  }, []);

  // 한국의 중심 좌표 (서울)
  const center: [number, number] = [36.6665, 127.878];

  return (
    <div className="w-full h-screen">
      <MapContainer
        center={center}
        zoom={7}
        scrollWheelZoom={true}
        className="w-full h-full"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {schools.map((school, index) => (
          <Marker
            key={index}
            position={[
              school.coordinates.latitude,
              school.coordinates.longitude,
            ]}
            icon={orangeIcon}
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
