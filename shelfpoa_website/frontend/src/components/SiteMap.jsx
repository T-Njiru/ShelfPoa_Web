import { useEffect } from "react";
import { Circle, CircleMarker, MapContainer, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import "leaflet/dist/leaflet.css";

// Nairobi map for the New outlet planner: click to drop a pin; existing outlets shown as grey dots,
// the pin with its 1 km and 2 km catchment rings. CircleMarkers only (no image icons -> no bundler issues).
const NAIROBI = [-1.29, 36.82];

function ClickToPin({ onPick }) {
  useMapEvents({ click: (e) => onPick(e.latlng.lat, e.latlng.lng) });
  return null;
}

function FlyTo({ pin }) {
  const map = useMap();
  useEffect(() => {
    if (pin) map.flyTo([pin.lat, pin.lon], Math.max(map.getZoom(), 13), { duration: 0.6 });
  }, [pin?.lat, pin?.lon]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

export default function SiteMap({ pin, outlets = [], onPick, height = 340 }) {
  return (
    <div className="rounded-card overflow-hidden bg-card" style={{ height }}>
      <MapContainer center={NAIROBI} zoom={12} style={{ height: "100%", width: "100%", cursor: "crosshair" }}>
                {/* standard OpenStreetMap tiles: no API key; darkened with a CSS filter to match the app */}
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          maxZoom={19}
          className="map-dark"
        />
        <ClickToPin onPick={onPick} />
        <FlyTo pin={pin} />
        {outlets.map((o) => (
          <CircleMarker key={`${o.chain}|${o.branch}`} center={[o.lat, o.lon]} radius={4}
            pathOptions={{ color: "#a8a6ad", weight: 1, fillColor: "#a8a6ad", fillOpacity: 0.7 }}>
            <Tooltip direction="top">{o.chain} {o.branch}</Tooltip>
          </CircleMarker>
        ))}
        {pin && (
          <>
            <Circle center={[pin.lat, pin.lon]} radius={2000} interactive={false}
              pathOptions={{ color: "#f4784e", weight: 1, dashArray: "4 4", fillOpacity: 0.04 }} />
            <Circle center={[pin.lat, pin.lon]} radius={1000} interactive={false}
              pathOptions={{ color: "#f4784e", weight: 1, fillOpacity: 0.08 }} />
            <CircleMarker center={[pin.lat, pin.lon]} radius={7} interactive={false}
              pathOptions={{ color: "#1c1b22", weight: 2, fillColor: "#f4784e", fillOpacity: 1 }} />
          </>
        )}
      </MapContainer>
    </div>
  );
}
