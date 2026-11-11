// Typed API client for the FloodWatch backend.

export type Severity = "High" | "Medium" | "Low";
export type Status = "Reported" | "Verified" | "Resolved";

export interface Location {
  id: string; name: string; x: number; y: number;
  shelter: string | null; custom: boolean;
  activeReports: number; severity: Severity | null;
  riskScore: number; risk: RiskLabel;
}
export type RiskLabel = "Safe" | "Watch" | "Warning" | "Danger";
export interface Road {
  id: string; a: string; b: string; km: number;
  manual: boolean; blocked: boolean; reportIds: string[];
}
export interface Report {
  id: string; location: string; locId: string; description: string;
  severity: Severity; status: Status; roadId: string | null;
  createdAt: string; updatedAt: string;
  lat?: number | null; lon?: number | null;     // set for Ghana-map (GPS) reports
}
export interface FloodZone {
  id: string; lat: number; lon: number; severity: Severity; radius: number; location: string; status: Status;
}
export interface GeoLayer {
  enabled: boolean; zones?: FloodZone[]; pending?: FloodZone[]; closedSegments?: [number, number][][];
}
export interface GeoPlace { name: string; kind: string; lat: number; lon: number; area?: string | null }
export interface GeoRoute {
  found: boolean; distance: number | null; eta: number | null; coords: [number, number][];
  steps: { name: string; km: number; class: string }[]; roads: string[];
  from: { lat: number; lon: number; snap: [number, number]; snapM: number };
  to: { lat: number; lon: number; snap: [number, number]; snapM: number };
  destinationFlooded: boolean; safePoint: [number, number] | null; warnings: string[]; closedSegments: number;
  algorithm: { settled: number; relaxations: number; heap: { pushes: number; pops: number; peak: number };
    blockedSkipped: number; ms: number; graphNodes: number; graphEdges: number };
}
export interface GeoEvacOption {
  name: string; kind: string; lat: number; lon: number; flooded: boolean; found: boolean;
  distance: number | null; eta?: number; straightKm: number; state: string; coords?: [number, number][];
}
export interface GeoEvac { inFloodZone: boolean; advice: string; options: GeoEvacOption[] }
export interface EventItem { id: number; ts: string; kind: string; message: string; ref: string | null }
export interface Trace {
  settled: string[];
  relaxations: { from: string; to: string; road: string; dist: number }[];
  blockedSkipped: string[];
  heap: { pushes: number; pops: number; peak: number };
}
export interface HashStats {
  size: number; count: number; loadFactor: number;
  collisions: number; longestChain: number; usedBuckets: number;
}
export interface State {
  version: number; serverTime: string; nextId: string;
  locations: Location[]; roads: Road[]; reports: Report[]; queue: string[];
  hash: { stats: HashStats; allowedSizes: number[]; buckets: { key: string; severity: Severity; status: Status }[][] };
  stats: {
    total: number; active: number; high: number; medium: number; low: number;
    verified: number; resolved: number; queue: number; blockedRoads: number;
    roads: number; locations: number; shelters: number; connectivity: number;
  };
  lastRouteTrace: (Trace & { from: string; to: string; settledCount?: number; real?: boolean }) | null;
  geo: GeoLayer;
  events: EventItem[];
  etaSpeedKmh: number;
}
export interface RouteResult {
  from: string; to: string; found: boolean; path: string[]; roads: string[];
  distance: number | null; eta: number | null; trace: Trace;
}
export interface EvacOption {
  id: string; name: string; kind: string; found: boolean;
  distance: number | null; eta: number | null; path: string[]; roads: string[];
  flooded: boolean; riskScore: number; risk: RiskLabel; state: string;
}
export interface EvacResult {
  from: string; riskScore: number; risk: RiskLabel; best: string | null;
  advice: string; options: EvacOption[];
}
export interface LookupResult {
  key: string; hashSum: number; bucket: number; size: number; found: boolean;
  steps: number; visited: string[]; report: Report | null;
}

const TOKEN_KEY = "fw.adminToken";
export const adminToken = {
  get: (): string | null => { try { return localStorage.getItem(TOKEN_KEY); } catch { return null; } },
  set: (t: string | null) => {
    try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch { /* private mode */ }
  },
};

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function req<T>(path: string, init: RequestInit = {}, admin = false): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (admin) { const t = adminToken.get(); if (t) headers["X-Admin-Token"] = t; }
  const res = await fetch(path, { ...init, headers: { ...headers, ...(init.headers as object) } });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail
        : Array.isArray(body.detail) ? body.detail.map((d: { msg: string; loc: string[] }) => `${d.loc.at(-1)}: ${d.msg}`).join("; ")
        : msg;
    } catch { /* non-JSON */ }
    throw new ApiError(res.status, msg);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

const json = (b: unknown) => JSON.stringify(b);

export const api = {
  state: () => req<State>("/api/state"),
  submit: (b: { location: string; description: string; severity: Severity; roadId: string | null; x?: number; y?: number; lat?: number; lon?: number }) =>
    req<Report>("/api/reports", { method: "POST", body: json(b) }),
  lookup: (key: string) => req<LookupResult>(`/api/reports/lookup/${encodeURIComponent(key)}`),
  route: (from: string, to: string) => req<RouteResult>(`/api/route?from=${from}&to=${to}`),
  evacuate: (from: string) => req<EvacResult>(`/api/evacuate?from=${from}`),
  verifyAdmin: () => req<{ ok: boolean }>("/api/auth/verify", { method: "POST" }, true),
  processNext: () => req<{ report: Report; message: string }>("/api/queue/process", { method: "POST" }, true),
  setStatus: (id: string, status: Status) => req<Report>(`/api/reports/${id}`, { method: "PATCH", body: json({ status }) }, true),
  remove: (id: string) => req<void>(`/api/reports/${id}`, { method: "DELETE" }, true),
  clear: () => req<{ cleared: number }>("/api/reports", { method: "DELETE" }, true),
  blockRoad: (id: string, blocked: boolean) => req(`/api/roads/${id}/block`, { method: "PUT", body: json({ blocked }) }, true),
  resizeHash: (size: number) => req<HashStats>("/api/hash/size", { method: "PUT", body: json({ size }) }, true),
  reset: () => req("/api/admin/reset", { method: "POST" }, true),
  // Ghana map
  geoSearch: (q: string) => req<GeoPlace[]>(`/api/geo/search?q=${encodeURIComponent(q)}`),
  geoReverse: (lat: number, lon: number) =>
    req<{ place: { name: string; kind: string; distanceM: number } | null }>(`/api/geo/reverse?at=${lat},${lon}`),
  geoRoute: (a: [number, number], b: [number, number]) => req<GeoRoute>(`/api/geo/route?from=${a.join(",")}&to=${b.join(",")}`),
  geoEvacuate: (a: [number, number]) => req<GeoEvac>(`/api/geo/evacuate?at=${a.join(",")}`),
};
