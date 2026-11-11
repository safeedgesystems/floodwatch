// Choose a location three ways: device GPS, search (our place index), or tap the map.
import { useEffect, useRef, useState } from "react";
import { Crosshair, Loader2, MapPin, Search, X } from "lucide-react";
import { api, GeoPlace } from "../lib/api";
import { useUi } from "./ui";

export interface Picked { lat: number; lon: number; label: string; source: "gps" | "search" | "map" }

const KIND_LABEL: Record<string, string> = {
  city: "City", town: "Town", village: "Village", suburb: "Suburb", neighbourhood: "Neighbourhood", quarter: "Area",
  hamlet: "Hamlet", hospital: "Hospital", clinic: "Clinic", university: "University", college: "College", school: "School",
  marketplace: "Market", police: "Police", fire_station: "Fire station", bus_station: "Station", fuel: "Fuel station",
  mall: "Mall", airport: "Airport",
};

export async function describe(lat: number, lon: number, prefix: string): Promise<string> {
  try {
    const r = await api.geoReverse(lat, lon);
    if (r.place) return r.place.distanceM < 300 ? `${prefix} · ${r.place.name}` : `${prefix} · near ${r.place.name}`;
  } catch { /* ignore */ }
  return `${prefix} · ${lat.toFixed(4)}, ${lon.toFixed(4)}`;
}

export function locateMe(): Promise<[number, number]> {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) return reject(new Error("This browser has no location support."));
    if (!window.isSecureContext) return reject(new Error("Location needs HTTPS (or localhost). Open the app via https or on this computer, or search / tap the map instead."));
    navigator.geolocation.getCurrentPosition(
      (p) => resolve([+p.coords.latitude.toFixed(6), +p.coords.longitude.toFixed(6)]),
      (e) => reject(new Error(e.code === 1 ? "Location permission was denied." : "Could not get your location.")),
      { enableHighAccuracy: true, timeout: 12000 },
    );
  });
}

export default function LocationPicker({ label, icon, value, onChange, picking, onStartPick, placeholder }: {
  label: string; icon?: React.ReactNode; value: Picked | null; onChange: (p: Picked | null) => void;
  picking: boolean; onStartPick: () => void; placeholder: string;
}) {
  const { toast } = useUi();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<GeoPlace[]>([]);
  const [open, setOpen] = useState(false);
  const [locating, setLocating] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (q.trim().length < 2) { setResults([]); return; }
    const t = window.setTimeout(() => api.geoSearch(q.trim()).then((r) => { setResults(r); setOpen(true); }).catch(() => setResults([])), 180);
    return () => window.clearTimeout(t);
  }, [q]);

  useEffect(() => {
    const close = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const gps = async () => {
    setLocating(true);
    try {
      const [lat, lon] = await locateMe();
      if (lat < 4.5 || lat > 11.5 || lon < -3.5 || lon > 1.5) throw new Error("Your device location is outside Ghana — search or tap the map instead.");
      onChange({ lat, lon, label: await describe(lat, lon, "My location"), source: "gps" });
    } catch (e) { toast("error", "Location unavailable", (e as Error).message); }
    finally { setLocating(false); }
  };

  return (
    <div className="field picker" ref={box}>
      <span>{icon}{label}</span>
      {value ? (
        <div className={`picked picked-${value.source}`}>
          <MapPin size={15} />
          <div><strong>{value.label}</strong><small className="mono">{value.lat.toFixed(5)}, {value.lon.toFixed(5)}</small></div>
          <button type="button" className="icon-btn" aria-label="Clear" onClick={() => onChange(null)}><X size={14} /></button>
        </div>
      ) : (
        <>
          <div className="search picker-search">
            <Search size={15} />
            <input placeholder={placeholder} value={q} onChange={(e) => setQ(e.target.value)} onFocus={() => results.length && setOpen(true)} />
          </div>
          {open && results.length > 0 && (
            <ul className="picker-results">
              {results.map((r, i) => (
                <li key={i} onMouseDown={() => { onChange({ lat: r.lat, lon: r.lon, label: r.name, source: "search" }); setQ(""); setOpen(false); }}>
                  <strong>{r.name}</strong>
                  <small>{KIND_LABEL[r.kind] ?? r.kind}{r.area ? ` · ${r.area}` : ""}</small>
                </li>
              ))}
            </ul>
          )}
          <div className="picker-actions">
            <button type="button" className="btn btn-xs btn-ghost" onClick={gps} disabled={locating}>
              {locating ? <Loader2 size={13} className="spin" /> : <Crosshair size={13} />} My location
            </button>
            <button type="button" className={`btn btn-xs ${picking ? "btn-primary" : "btn-ghost"}`} onClick={onStartPick}>
              <MapPin size={13} /> {picking ? "Tap the map…" : "Pick on map"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
