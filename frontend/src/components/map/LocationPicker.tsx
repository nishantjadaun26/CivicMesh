import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import type { Coordinates } from '../../types/civic';
import { MAP_CENTER } from '../../types/civic';

export function LocationPicker({ value, onChange, onIncomplete }: {
  value: Coordinates | null; onChange: (point: Coordinates) => void; onIncomplete: () => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const marker = useRef<L.Marker | null>(null);
  const change = useRef(onChange); change.current = onChange;
  const alive = useRef(true);
  const [latitude, setLatitude] = useState(value ? String(value.lat) : '');
  const [longitude, setLongitude] = useState(value ? String(value.lng) : '');
  const [message, setMessage] = useState('');
  const configured = Boolean(import.meta.env.VITE_MAP_TILE_URL && import.meta.env.VITE_MAP_ATTRIBUTION);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => {
    if (!host.current || !configured) return;
    const instance = L.map(host.current, { scrollWheelZoom: false }).setView([MAP_CENTER.lat, MAP_CENTER.lng], 2);
    map.current = instance;
    L.tileLayer(import.meta.env.VITE_MAP_TILE_URL, { attribution: import.meta.env.VITE_MAP_ATTRIBUTION })
      .on('tileerror', () => setMessage('Map tiles unavailable. Enter coordinates below or use your location.')).addTo(instance);
    instance.attributionControl.setPrefix(false);
    instance.on('click', (event: L.LeafletMouseEvent) => change.current({ lat: event.latlng.lat, lng: event.latlng.lng }));
    const observer = new ResizeObserver(() => instance.invalidateSize()); observer.observe(host.current);
    return () => { observer.disconnect(); instance.remove(); map.current = null; marker.current = null; };
  }, [configured]);
  useEffect(() => {
    if (!value) { marker.current?.remove(); marker.current = null; return; }
    setLatitude(String(value.lat)); setLongitude(String(value.lng));
    if (!map.current) return;
    if (!marker.current) {
      marker.current = L.marker([value.lat, value.lng], { draggable: true,
        icon: L.divIcon({ className: 'location-pin', html: '<span></span>', iconSize: [32, 40], iconAnchor: [16, 38] }) }).addTo(map.current);
      marker.current.on('dragend', () => { const point = marker.current!.getLatLng(); change.current({ lat: point.lat, lng: point.lng }); });
    } else marker.current.setLatLng([value.lat, value.lng]);
    map.current.setView([value.lat, value.lng], 16);
  }, [value]);
  function edit(lat: string, lng: string) {
    setLatitude(lat); setLongitude(lng);
    if (lat.trim() !== '' && lng.trim() !== '' && Number.isFinite(Number(lat)) && Number.isFinite(Number(lng)) && Math.abs(Number(lat)) <= 90 && Math.abs(Number(lng)) <= 180) {
      change.current({ lat: Number(lat), lng: Number(lng) });
    } else onIncomplete();
  }
  function gps() {
    if (!navigator.geolocation) { setMessage('GPS is unavailable. Enter both coordinates manually.'); return; }
    setMessage('Finding your location…');
    navigator.geolocation.getCurrentPosition(position => {
      if (!alive.current) return;
      change.current({ lat: position.coords.latitude, lng: position.coords.longitude });
      setMessage('Location selected. Verify that it is the actual incident location.');
    }, () => { if (alive.current) setMessage('Location permission unavailable. Enter both coordinates manually.'); }, { timeout: 10000, maximumAge: 60000 });
  }
  return <>
    {configured ? <div className="location-picker" ref={host} role="region" aria-label="Select report location" /> : <p role="status">Map service is not configured. Enter coordinates or use your location.</p>}
    <button type="button" className="secondary-button" onClick={gps}>Use my location</button>
    <p className="help" role="status">{message || 'Choose the actual incident location before confirming.'}</p>
    <div className="field-row">
      <label>Latitude<input type="number" step="any" min="-90" max="90" value={latitude} onChange={event => edit(event.target.value, longitude)} /></label>
      <label>Longitude<input type="number" step="any" min="-180" max="180" value={longitude} onChange={event => edit(latitude, event.target.value)} /></label>
    </div>
  </>;
}
