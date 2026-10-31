"use client";
import { MapContainer, TileLayer, CircleMarker } from "react-leaflet";
export default function LocationMap({
  latitude,
  longitude,
}: {
  latitude: number;
  longitude: number;
}) {
  const url = process.env.NEXT_PUBLIC_MAP_TILE_URL;
  const attribution = process.env.NEXT_PUBLIC_MAP_ATTRIBUTION;
  if (!url || !attribution)
    return (
      <p className="text-sm p-4 bg-stone-100 rounded-lg">
        Map service is not configured. You can confirm coordinates manually.
      </p>
    );
  return (
    <MapContainer
      key={`${latitude},${longitude}`}
      center={[latitude, longitude]}
      zoom={16}
      className="h-64 rounded-lg"
      scrollWheelZoom={false}
    >
      <TileLayer url={url} attribution={attribution} />
      <CircleMarker center={[latitude, longitude]} radius={8} />
    </MapContainer>
  );
}
