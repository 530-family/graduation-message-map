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
  videoStatus?: string;
  videoUrl?: string;
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

// Create marker icons for different statuses
// Orange: for "Sent" status
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

// Grey icon for other statuses
const greyIcon = new L.Icon({
  iconUrl:
    "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-grey.png",
  shadowUrl:
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

// Function to get marker icon based on videoStatus
const getMarkerIcon = (videoStatus?: string) => {
  if (videoStatus === "Sent") return orangeIcon;
  return greyIcon; // default for others
};

export default function KoreaMap() {
  const [schools, setSchools] = useState<SchoolData[]>([]);

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
        {schools
          .filter((school) => school.coordinates.latitude !== 0 || school.coordinates.longitude !== 0)
          .map((school, index) => (
          <Marker
            key={index}
            position={[
              school.coordinates.latitude,
              school.coordinates.longitude,
            ]}
            icon={getMarkerIcon(school.videoStatus)}
            zIndexOffset={school.videoStatus === "Sent" ? 1000 : 500}
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
