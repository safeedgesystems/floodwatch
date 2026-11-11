import { MouseEvent, useMemo, useRef, useState } from "react";
import type { Location, Road, State } from "../lib/api";

export interface MapProps {
  state: State;
  route?: { path: string[]; roads: string[] } | null;
  routeTone?: "primary" | "safe";
  showShelters?: boolean;
  explored?: string[];                 // Dijkstra settle order (partial while animating)
  from?: string | null;
  to?: string | null;
  onNodeClick?: (id: string) => void;
  onRoadClick?: (id: string) => void;
  onPick?: (x: number, y: number) => void;
  pin?: { x: number; y: number } | null;
  showKm?: boolean;
  height?: number | string;
}

const W = 720, H = 460;

export default function NetworkMap({
  state, route, routeTone = "primary", showShelters, explored, from, to,
  onNodeClick, onRoadClick, onPick, pin, showKm = true, height = "100%",
}: MapProps) {
  const svg = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<{ kind: "node" | "road"; id: string } | null>(null);
  const loc = useMemo(() => Object.fromEntries(state.locations.map((l) => [l.id, l])), [state.locations]);
  const routeRoads = new Set(route?.roads ?? []);
  const settleIdx = new Map((explored ?? []).map((id, i) => [id, i]));

  const toSvg = (e: MouseEvent) => {
    const pt = svg.current!.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const p = pt.matrixTransform(svg.current!.getScreenCTM()!.inverse());
    return { x: Math.round(p.x), y: Math.round(p.y) };
  };

  const routeD = route?.path.length
    ? route.path.map((id, i) => `${i ? "L" : "M"}${loc[id]?.x},${loc[id]?.y}`).join(" ")
    : null;

  const hovered = hover?.kind === "node" ? loc[hover.id] : null;
  const hoveredRoad = hover?.kind === "road" ? state.roads.find((r) => r.id === hover.id) : null;

  return (
    <div className="map-wrap" style={{ height }}>
      <svg
        ref={svg}
        viewBox={`0 0 ${W} ${H}`}
        className={`map ${onPick ? "pickable" : ""}`}
        onClick={(e) => onPick && e.target === e.currentTarget.querySelector(".map-bg") && onPick(toSvg(e).x, toSvg(e).y)}
        role="img"
        aria-label="Simulated road network map"
      >
        <defs>
          <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
            <path d="M24 0H0V24" fill="none" stroke="var(--map-grid)" strokeWidth="1" />
          </pattern>
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="4" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <linearGradient id="river" x1="0" x2="1">
            <stop offset="0" stopColor="#3a4a5c" stopOpacity=".55" />
            <stop offset="1" stopColor="#3a4a5c" stopOpacity=".15" />
          </linearGradient>
        </defs>

        <rect className="map-bg" width={W} height={H} fill="url(#grid)" />
        {/* Decorative river - purely visual context */}
        <path d="M-10 410 C 90 380, 120 300, 70 250 S 40 120, 150 60 S 260 -10, 300 -10"
          fill="none" stroke="url(#river)" strokeWidth="26" strokeLinecap="round" pointerEvents="none" />

        {/* Roads */}
        {state.roads.map((r) => <RoadLine key={r.id} r={r} a={loc[r.a]} b={loc[r.b]} onRoute={routeRoads.has(r.id)}
          showKm={showKm} hovered={hover?.id === r.id}
          onClick={onRoadClick ? () => onRoadClick(r.id) : undefined}
          onHover={(h) => setHover(h ? { kind: "road", id: r.id } : null)} />)}

        {/* Recommended route */}
        {routeD && (
          <g pointerEvents="none" className={`route route-${routeTone}`}>
            <path d={routeD} className="route-glow" filter="url(#glow)" />
            <path d={routeD} className="route-line" />
            <path d={routeD} className="route-flow" />
          </g>
        )}

        {/* Nodes */}
        {state.locations.map((l) => (
          <Node key={l.id} l={l} shelter={!!showShelters && !!l.shelter}
            settle={settleIdx.get(l.id)} isFrom={from === l.id} isTo={to === l.id}
            onRoute={route?.path.includes(l.id) ?? false}
            onClick={onNodeClick ? () => onNodeClick(l.id) : undefined}
            onHover={(h) => setHover(h ? { kind: "node", id: l.id } : null)} />
        ))}

        {pin && (
          <g transform={`translate(${pin.x},${pin.y})`} className="pin" pointerEvents="none">
            <circle r="18" className="pin-pulse" />
            <path d="M0 0 C -9 -12 -9 -26 0 -26 C 9 -26 9 -12 0 0 Z" className="pin-body" />
            <circle cy="-17" r="3.5" fill="#fff" />
          </g>
        )}
      </svg>

      {hovered && (
        <div className="map-tip" style={{ left: `${(hovered.x / W) * 100}%`, top: `${(hovered.y / H) * 100}%` }}>
          <strong>{hovered.name}</strong><span className="mono"> · {hovered.id}</span>
          <div>Risk: <b className={`risk-text-${hovered.risk.toLowerCase()}`}>{hovered.risk}</b> ({hovered.riskScore})</div>
          <div>{hovered.activeReports} active report{hovered.activeReports === 1 ? "" : "s"}{hovered.severity ? ` · worst ${hovered.severity}` : ""}</div>
          {hovered.shelter && <div className="tip-safe">Shelter · {hovered.shelter}</div>}
        </div>
      )}
      {hoveredRoad && (
        <div className="map-tip" style={{
          left: `${((loc[hoveredRoad.a].x + loc[hoveredRoad.b].x) / 2 / W) * 100}%`,
          top: `${((loc[hoveredRoad.a].y + loc[hoveredRoad.b].y) / 2 / H) * 100}%`,
        }}>
          <strong>{loc[hoveredRoad.a].name} — {loc[hoveredRoad.b].name}</strong>
          <div className="mono">{hoveredRoad.id} · {hoveredRoad.km.toFixed(1)} km</div>
          <div>{hoveredRoad.blocked ? <b className="risk-text-danger">BLOCKED</b> : <b className="risk-text-safe">OPEN</b>}
            {hoveredRoad.manual && " · manual closure"}{hoveredRoad.reportIds.length > 0 && ` · ${hoveredRoad.reportIds.join(", ")}`}</div>
          {onRoadClick && <div className="muted small">Click to {hoveredRoad.manual ? "reopen" : "close"}</div>}
        </div>
      )}
    </div>
  );
}

function RoadLine({ r, a, b, onRoute, showKm, hovered, onClick, onHover }: {
  r: Road; a: Location; b: Location; onRoute: boolean; showKm: boolean; hovered: boolean;
  onClick?: () => void; onHover: (h: boolean) => void;
}) {
  if (!a || !b) return null;
  const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
  return (
    <g className={`road ${r.blocked ? "blocked" : "open"} ${hovered ? "hover" : ""} ${onClick ? "clickable" : ""}`}
      onMouseEnter={() => onHover(true)} onMouseLeave={() => onHover(false)} onClick={onClick}>
      <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="road-hit" />
      <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="road-line" />
      {r.blocked && (
        <g transform={`translate(${mx},${my})`} className="road-x">
          <circle r="8" /><path d="M-3.5 -3.5 L3.5 3.5 M3.5 -3.5 L-3.5 3.5" />
        </g>
      )}
      {showKm && !r.blocked && !onRoute && (
        <text x={mx} y={my - 6} className="road-km">{r.km.toFixed(1)} km</text>
      )}
    </g>
  );
}

function Node({ l, shelter, settle, isFrom, isTo, onRoute, onClick, onHover }: {
  l: Location; shelter: boolean; settle?: number; isFrom: boolean; isTo: boolean; onRoute: boolean;
  onClick?: () => void; onHover: (h: boolean) => void;
}) {
  const sev = l.severity?.toLowerCase() ?? "none";
  return (
    <g transform={`translate(${l.x},${l.y})`}
      className={`node sev-${sev} ${onClick ? "clickable" : ""} ${onRoute ? "on-route" : ""} ${settle !== undefined ? "settled" : ""}`}
      onClick={onClick} onMouseEnter={() => onHover(true)} onMouseLeave={() => onHover(false)}>
      {l.severity === "High" && <circle r="16" className="node-pulse" />}
      {shelter && <circle r="23" className="node-shelter" />}
      {settle !== undefined && <circle r="20" className="node-explored" />}
      <circle r="14" className="node-core" />
      <text className="node-id" dy="4">{l.activeReports > 0 ? l.activeReports : l.id}</text>
      <text className="node-label" y={shelter ? 38 : 31}>{l.name}</text>
      {shelter && <text className="node-shelter-label" y="49">SHELTER</text>}
      {settle !== undefined && <g transform="translate(14,-15)" className="settle-badge"><circle r="8" /><text dy="3.5">{settle + 1}</text></g>}
      {(isFrom || isTo) && (
        <g transform="translate(-15,-17)" className={`endpoint ${isFrom ? "from" : "to"}`}>
          <circle r="9" /><text dy="3.5">{isFrom ? "A" : "B"}</text>
        </g>
      )}
    </g>
  );
}
