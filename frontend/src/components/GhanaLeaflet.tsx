// Leaflet map of Ghana. Draws flood zones, closed roads, routes and markers.
// Leaflet is imperative, so this wrapper syncs React props into map layers.
import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { GeoLayer } from "../lib/api";

export type LatLon = [number, number];
export interface MapMarker { at: LatLon; kind: "from" | "to" | "safe" | "pin" | "shelter" | "report"; label?: string }
export interface MapLine { coords: LatLon[]; tone: "route" | "safe" | "old" }

const GHANA: L.LatLngBoundsExpression = [[4.6, -3.3], [11.2, 1.3]];
const OSM_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
const CARTO_ATTR = OSM_ATTR + ' &copy; <a href="https://carto.com/attributions">CARTO</a>';
// CARTO basemaps need a (free) key; the server passes it via /api/geo/info.
// Without a key, "dark" falls back to OpenStreetMap tiles darkened with a CSS filter.
let cartoKey: Promise<string | null> | null = null;
const getCartoKey = () =>
  (cartoKey ??= fetch("/api/geo/info").then((r) => r.json()).then((i) => i.cartoKey ?? null).catch(() => null));
function tileConfig(theme: "dark" | "street", key: string | null) {
  if (theme === "dark" && key)
    return { url: `https://basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}{r}.png?key=${encodeURIComponent(key)}`, attr: CARTO_ATTR, filter: false };
  return { url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png", attr: OSM_ATTR, filter: theme === "dark" };
}
const COLORS = { route: "#f5a524", safe: "#22c55e", old: "#8b949e", high: "#ef4444", medium: "#f97316", low: "#facc15" };

// Offline base map: our own Ghana road graph drawn on a canvas (no internet needed).
let offlineData: Promise<{ roads: [number, number[]][]; towns: [string, string, number, number][] }> | null = null;
const ROAD_STYLE: Record<number, [string, number]> = {
  1: ["#9aa3ad", 2.6], 2: ["#7d8691", 2.2], 3: ["#646d78", 1.8], 4: ["#525a64", 1.4], 5: ["#424951", 1.1], 6: ["#33383f", 0.8],
};
function buildOffline(): Promise<{ roads: L.LayerGroup; cities: L.LayerGroup; towns: L.LayerGroup }> {
  offlineData ??= fetch("/api/geo/offline-roads").then((r) => r.json());
  return offlineData.then(({ roads, towns }) => {
    const renderer = L.canvas({ padding: 0.3 });
    const g = L.layerGroup(), cities = L.layerGroup(), townLayer = L.layerGroup();
    // draw minor roads first so trunk roads sit on top
    [...roads].sort((a, b) => b[0] - a[0]).forEach(([cls, flat]) => {
      const pts: L.LatLngTuple[] = [];
      for (let i = 0; i < flat.length; i += 2) pts.push([flat[i], flat[i + 1]]);
      const [color, weight] = ROAD_STYLE[cls];
      L.polyline(pts, { renderer, color, weight, interactive: false }).addTo(g);
    });
    towns.forEach(([name, kind, lat, lon]) => L.marker([lat, lon], { interactive: false, keyboard: false,
      icon: L.divIcon({ className: `lf-town lf-${kind}`, html: `<span>${name}</span>`, iconSize: [0, 0] }) })
      .addTo(kind === "city" ? cities : townLayer));
    return { roads: g, cities, towns: townLayer };
  });
}

function icon(kind: MapMarker["kind"], label?: string) {
  const text = kind === "from" ? "A" : kind === "to" ? "B" : kind === "safe" ? "✓" : kind === "shelter" ? "+" : kind === "report" ? "!" : "";
  return L.divIcon({
    className: "",
    html: `<div class="lf-marker lf-${kind}" title="${label ?? ""}"><span>${text}</span></div>`,
    iconSize: [28, 28], iconAnchor: [14, kind === "pin" ? 28 : 14],
  });
}

export type MapTheme = "dark" | "street" | "offline";

export default function GhanaLeaflet({ geo, markers, lines, onPick, picking, fitTo, theme = "dark", onTilesFailed }: {
  geo: GeoLayer; markers: MapMarker[]; lines: MapLine[]; onPick?: (p: LatLon) => void;
  picking: boolean; fitTo?: LatLon[] | null; theme?: MapTheme; onTilesFailed?: () => void;
}) {
  const offline = useRef<L.LayerGroup>();
  const failRef = useRef(onTilesFailed);
  failRef.current = onTilesFailed;
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map>();
  const tiles = useRef<L.TileLayer>();
  const floodLayer = useRef<L.LayerGroup>();
  const drawLayer = useRef<L.LayerGroup>();
  const pickRef = useRef(onPick);
  pickRef.current = onPick;

  // init once
  useEffect(() => {
    const m = L.map(el.current!, { zoomControl: true, attributionControl: true, minZoom: 6, maxBounds: [[3.5, -4.5], [12.5, 2.5]] });
    m.fitBounds(GHANA);
    floodLayer.current = L.layerGroup().addTo(m);
    drawLayer.current = L.layerGroup().addTo(m);
    m.on("click", (e: L.LeafletMouseEvent) => pickRef.current?.([+e.latlng.lat.toFixed(6), +e.latlng.lng.toFixed(6)]));
    map.current = m;
    const ro = new ResizeObserver(() => m.invalidateSize());
    ro.observe(el.current!);
    return () => { ro.disconnect(); m.remove(); };
  }, []);

  useEffect(() => {
    const m = map.current!;
    tiles.current?.remove(); tiles.current = undefined;
    offline.current?.remove();
    let cancelled = false;
    if (theme === "offline") {
      m.attributionControl.addAttribution("Roads © OpenStreetMap contributors (offline copy)");
      buildOffline().then(({ roads, cities, towns }) => {
        if (cancelled) return;
        // labels: cities from zoom 8, towns only when zoomed in (avoids clutter)
        const sync = () => { m.getZoom() >= 8 ? cities.addTo(m) : cities.remove(); m.getZoom() >= 11 ? towns.addTo(m) : towns.remove(); };
        const grp = L.layerGroup([roads]).addTo(m);
        offline.current = grp;
        m.on("zoomend", sync); sync();
        grp.on("remove", () => { m.off("zoomend", sync); cities.remove(); towns.remove(); });
      });
    } else {
      getCartoKey().then((key) => {
        if (cancelled) return;
        const t = tileConfig(theme, key);
        let errors = 0;
        tiles.current = L.tileLayer(t.url, { attribution: t.attr, maxZoom: 19, className: t.filter ? "tiles-darkened" : "" })
          .on("tileerror", () => { if (++errors === 6) failRef.current?.(); })
          .addTo(m);
        tiles.current.bringToBack();
      });
    }
    return () => { cancelled = true; tiles.current?.remove(); };
  }, [theme]);

  // flood zones + closed roads (from live state)
  useEffect(() => {
    const g = floodLayer.current!;
    g.clearLayers();
    (geo.closedSegments ?? []).forEach((seg) =>
      L.polyline(seg, { color: COLORS.high, weight: 5, opacity: 0.9, dashArray: "6 6" }).addTo(g));
    (geo.zones ?? []).forEach((z) => {
      const c = COLORS[z.severity.toLowerCase() as "high"];
      L.circle([z.lat, z.lon], { radius: z.radius, color: c, weight: 2, fillColor: c, fillOpacity: 0.22 })
        .bindPopup(`<b>${z.id} · ${z.severity} flood (verified)</b><br>${z.location}<br>Roads within ${z.radius} m are closed`).addTo(g);
    });
    (geo.pending ?? []).forEach((z) => {
      L.circle([z.lat, z.lon], { radius: z.radius, color: COLORS.medium, weight: 2, dashArray: "4 6", fillOpacity: 0.05 })
        .bindPopup(`<b>${z.id} · ${z.severity} (awaiting verification)</b><br>${z.location}<br>Not affecting routes yet`).addTo(g);
    });
  }, [geo]);

  // routes & markers
  useEffect(() => {
    const g = drawLayer.current!;
    g.clearLayers();
    lines.forEach((ln) => {
      if (!ln.coords.length) return;
      if (ln.tone !== "old") L.polyline(ln.coords, { color: COLORS[ln.tone], weight: 12, opacity: 0.25 }).addTo(g);
      L.polyline(ln.coords, { color: COLORS[ln.tone], weight: ln.tone === "old" ? 4 : 6, opacity: ln.tone === "old" ? 0.7 : 1,
        dashArray: ln.tone === "old" ? "4 8" : undefined, className: ln.tone !== "old" ? "lf-route-flow" : "" }).addTo(g);
    });
    markers.forEach((mk) => L.marker(mk.at, { icon: icon(mk.kind, mk.label), zIndexOffset: mk.kind === "from" || mk.kind === "to" ? 1000 : 0 })
      .bindTooltip(mk.label ?? "", { direction: "top", offset: [0, -14] }).addTo(g));
  }, [lines, markers]);

  useEffect(() => {
    if (fitTo && fitTo.length) map.current!.fitBounds(L.latLngBounds(fitTo), { padding: [50, 50], maxZoom: 15 });
  }, [fitTo]);

  return <div ref={el} className={`ghana-map ${picking ? "picking" : ""}`} />;
}
