import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle, ArrowDownUp, Cpu, LifeBuoy, Loader2, Map as MapIcon, Megaphone, Navigation, RefreshCw, Route, Send, ShieldCheck, X,
} from "lucide-react";
import GhanaLeaflet, { LatLon, MapLine, MapMarker, MapTheme } from "../components/GhanaLeaflet";
import LocationPicker, { describe, Picked } from "../components/LocationPicker";
import { useApp } from "../components/Shell";
import { Empty, Panel, useUi } from "../components/ui";
import { api, ApiError, GeoEvac, GeoRoute, Severity } from "../lib/api";

type Tab = "navigate" | "report" | "evacuate";
type PickTarget = "from" | "to" | "report" | "evac" | null;

export default function GhanaMap() {
  const { state, params } = useApp();
  const { toast } = useUi();
  const [tab, setTab] = useState<Tab>((params.get("tab") as Tab) || "navigate");
  const [pick, setPick] = useState<PickTarget>(null);
  const [theme, setTheme] = useState<MapTheme>(() => (navigator.onLine ? "dark" : "offline"));
  const [fitTo, setFitTo] = useState<LatLon[] | null>(null);

  // navigation
  const [from, setFrom] = useState<Picked | null>(null);
  const [to, setTo] = useState<Picked | null>(null);
  const [route, setRoute] = useState<GeoRoute | null>(null);
  const [oldRoute, setOldRoute] = useState<GeoRoute | null>(null);
  const [rerouted, setRerouted] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const active = useRef<{ a: LatLon; b: LatLon } | null>(null);
  const routeRef = useRef<GeoRoute | null>(null);       // latest route, read by the live-update effect
  routeRef.current = route;

  // report
  const [repAt, setRepAt] = useState<Picked | null>(null);
  const [desc, setDesc] = useState("");
  const [sev, setSev] = useState<Severity>("High");
  // evacuation
  const [evacAt, setEvacAt] = useState<Picked | null>(null);
  const [evac, setEvac] = useState<GeoEvac | null>(null);

  const geo = state.geo;

  const onPick = async (p: LatLon) => {
    if (!pick) return;
    const target = pick;
    setPick(null);
    const val: Picked = { lat: p[0], lon: p[1], label: await describe(p[0], p[1], "Pinned"), source: "map" };
    if (target === "from") setFrom(val);
    if (target === "to") setTo(val);
    if (target === "report") setRepAt(val);
    if (target === "evac") setEvacAt(val);
  };

  const findRoute = async (silent = false) => {
    if (!from || !to) return;
    const a: LatLon = [from.lat, from.lon], b: LatLon = [to.lat, to.lon];
    if (!silent) setBusy(true);
    try {
      const r = await api.geoRoute(a, b);
      const prev = routeRef.current;
      if (silent && prev && r.roads.join() !== prev.roads.join()) {
        const delta = (r.distance ?? 0) - (prev.distance ?? 0);
        const msg = r.found
          ? `A newly verified flood affects your route — rerouted (${delta >= 0 ? "+" : ""}${delta.toFixed(1)} km, ${r.eta} min).`
          : "A newly verified flood has cut off every open route to your destination.";
        setOldRoute(prev); setRerouted(msg);
        toast("info", "Route updated", msg);
      }
      setRoute(r); routeRef.current = r;
      active.current = { a, b };
      if (!silent) { setOldRoute(null); setRerouted(null); if (r.coords.length) setFitTo(r.coords); }
      if (!r.found && !silent) toast("error", "No open route", "Every road path is blocked by verified floods.");
    } catch (e) { toast("error", "Routing failed", e instanceof ApiError ? e.message : "Network error"); }
    finally { setBusy(false); }
  };

  // Live rerouting: whenever the shared state changes (a flood verified/resolved), re-check the trip.
  const lastVersion = useRef(state.version);
  useEffect(() => {
    if (state.version !== lastVersion.current && active.current && from && to) findRoute(true);
    lastVersion.current = state.version;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.version]);

  const submitReport = async () => {
    if (!repAt) return;
    try {
      const label = repAt.label.replace(/^(My location|Pinned) · (near )?/, "");
      const r = await api.submit({ location: label.slice(0, 60), description: desc, severity: sev, roadId: null, lat: repAt.lat, lon: repAt.lon });
      toast("success", `${r.id} submitted`, "Shown as a dashed circle until an admin verifies it — then nearby roads close.");
      setDesc(""); setRepAt(null);
    } catch (e) { toast("error", "Could not submit", e instanceof ApiError ? e.message : "Network error"); }
  };

  const runEvac = async () => {
    if (!evacAt) return;
    setBusy(true);
    try {
      const r = await api.geoEvacuate([evacAt.lat, evacAt.lon]);
      setEvac(r);
      const best = r.options.find((o) => o.coords);
      setFitTo([[evacAt.lat, evacAt.lon], ...(best?.coords ?? []), ...r.options.map((o) => [o.lat, o.lon] as LatLon)]);
    } catch (e) { toast("error", "Evacuation advisor failed", (e as Error).message); }
    finally { setBusy(false); }
  };
  useEffect(() => { if (evacAt && tab === "evacuate") runEvac(); /* refresh on state change */ // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [evacAt, state.version]);

  // ---- map content
  const { markers, lines } = useMemo(() => {
    const mk: MapMarker[] = [], ln: MapLine[] = [];
    if (tab === "navigate") {
      if (oldRoute?.coords.length) ln.push({ coords: oldRoute.coords, tone: "old" });
      if (route?.found) ln.push({ coords: route.coords, tone: "route" });
      if (from) mk.push({ at: [from.lat, from.lon], kind: "from", label: from.label });
      if (to) mk.push({ at: [to.lat, to.lon], kind: "to", label: to.label });
      if (route?.safePoint) mk.push({ at: route.safePoint, kind: "safe", label: "Nearest safe point outside the flood zone" });
    } else if (tab === "report") {
      if (repAt) mk.push({ at: [repAt.lat, repAt.lon], kind: "pin", label: repAt.label });
    } else {
      if (evacAt) mk.push({ at: [evacAt.lat, evacAt.lon], kind: "from", label: evacAt.label });
      evac?.options.forEach((o) => {
        mk.push({ at: [o.lat, o.lon], kind: "shelter", label: `${o.name} — ${o.state}` });
        if (o.coords) ln.push({ coords: o.coords, tone: "safe" });
      });
    }
    return { markers: mk, lines: ln };
  }, [tab, route, oldRoute, from, to, repAt, evacAt, evac]);

  if (!geo?.enabled) {
    return <Panel title="Ghana live map" icon={<MapIcon size={16} />}>
      <Empty icon={<MapIcon />} title="Ghana map data is not installed" body="Run tools/build_ghana_graph.py (see README). The simulation views still work offline." />
    </Panel>;
  }
  const zones = geo.zones?.length ?? 0, pending = geo.pending?.length ?? 0;

  return (
    <div className="grid-ghana">
      <div className="col ghana-side">
        <div className="tabs-big">
          {([["navigate", <Navigation size={15} />, "Navigate"], ["report", <Megaphone size={15} />, "Report"], ["evacuate", <LifeBuoy size={15} />, "Evacuate"]] as const)
            .map(([id, ic, lbl]) => <button key={id} className={tab === id ? "on" : ""} onClick={() => { setTab(id); setPick(null); }}>{ic}{lbl}</button>)}
        </div>

        {tab === "navigate" && (
          <Panel title="Safe route anywhere in Ghana" icon={<Route size={16} />}>
            <div className="stack">
              <LocationPicker label="From" icon={<i className="dot dot-a">A</i>} value={from} onChange={(v) => { setFrom(v); setRoute(null); active.current = null; }}
                picking={pick === "from"} onStartPick={() => setPick(pick === "from" ? null : "from")} placeholder="Search a town, suburb, hospital…" />
              <button className="icon-btn swap-inline" aria-label="Swap" onClick={() => { setFrom(to); setTo(from); setRoute(null); }}><ArrowDownUp size={15} /></button>
              <LocationPicker label="Destination" icon={<i className="dot dot-b">B</i>} value={to} onChange={(v) => { setTo(v); setRoute(null); active.current = null; }}
                picking={pick === "to"} onStartPick={() => setPick(pick === "to" ? null : "to")} placeholder="Where are you going?" />
              <button className="btn btn-primary btn-block" disabled={!from || !to || busy} onClick={() => findRoute(false)}>
                {busy ? <Loader2 size={16} className="spin" /> : <Navigation size={16} />} Find safe route
              </button>
            </div>

            {rerouted && <div className="advice advice-bad reroute"><RefreshCw size={18} /><p>{rerouted}</p><button className="icon-btn" onClick={() => { setRerouted(null); setOldRoute(null); }}><X size={14} /></button></div>}
            {route?.warnings.map((w, i) => <div key={i} className="advice advice-warn"><AlertTriangle size={18} /><p>{w}</p></div>)}

            {route && (route.found ? (
              <div className="route-card">
                <div className="route-figs">
                  <div><b>{route.distance?.toFixed(1)}</b><span>km</span></div>
                  <div><b>{fmtTime(route.eta ?? 0)}</b><span>drive time</span></div>
                  <div><b>{route.steps.length}</b><span>roads</span></div>
                </div>
                <ol className="steps compact-steps">
                  {route.steps.slice(0, 12).map((s, i) => (
                    <li key={i}><span className="step-dot">{i + 1}</span><div><strong>{s.name}</strong><small className="mono">{s.km.toFixed(1)} km · {s.class}</small></div></li>
                  ))}
                  {route.steps.length > 12 && <li className="muted small">…{route.steps.length - 12} more roads</li>}
                </ol>
                <div className="algo-mini"><Cpu size={14} />
                  <span>Our Dijkstra settled <b>{route.algorithm.settled.toLocaleString()}</b> of {route.algorithm.graphNodes.toLocaleString()} junctions ·
                    heap {route.algorithm.heap.pushes.toLocaleString()} push / {route.algorithm.heap.pops.toLocaleString()} pop ·
                    {" "}{route.closedSegments} flooded road segments avoided · {route.algorithm.ms} ms</span>
                </div>
                {route.from.snapM > 300 && <p className="hint">Start is {fmtM(route.from.snapM)} from the nearest mapped road.</p>}
              </div>
            ) : <div className="route-none"><AlertTriangle size={20} /><div><strong>No open route</strong><p>Verified floods cut every road path. Try the Evacuate tab.</p></div></div>)}
          </Panel>
        )}

        {tab === "report" && (
          <Panel title="Report flooding at a real location" icon={<Megaphone size={16} />}>
            <div className="stack">
              <LocationPicker label="Where is the flooding?" value={repAt} onChange={setRepAt}
                picking={pick === "report"} onStartPick={() => setPick(pick === "report" ? null : "report")} placeholder="Search a place, or use My location" />
              <label className="field"><span>What's happening?</span>
                <textarea className="input" rows={3} maxLength={280} value={desc} placeholder="e.g. Knee-deep water across the road near the bridge"
                  onChange={(e) => setDesc(e.target.value)} /></label>
              <div className="field"><span>Severity <em>(sets the flood-zone radius)</em></span>
                <div className="segmented">
                  {(["High", "Medium", "Low"] as Severity[]).map((s) => (
                    <button key={s} type="button" className={`seg seg-${s.toLowerCase()} ${sev === s ? "on" : ""}`} onClick={() => setSev(s)}>
                      {s}<small className="seg-sub">{s === "High" ? "400 m" : s === "Medium" ? "200 m" : "80 m"}</small></button>
                  ))}
                </div>
              </div>
              <button className="btn btn-primary btn-block" disabled={!repAt || desc.trim().length < 3} onClick={submitReport}>
                <Send size={16} /> Submit report {state.nextId}</button>
              <p className="hint"><ShieldCheck size={13} /> Goes into the same hash table and FIFO verification queue as every report. Roads only close once an admin verifies it.</p>
            </div>
          </Panel>
        )}

        {tab === "evacuate" && (
          <Panel title="Nearest safe place" icon={<LifeBuoy size={16} />}>
            <div className="stack">
              <LocationPicker label="Where are you?" value={evacAt} onChange={(v) => { setEvacAt(v); setEvac(null); }}
                picking={pick === "evac"} onStartPick={() => setPick(pick === "evac" ? null : "evac")} placeholder="Search, or use My location" />
              {busy && <p className="muted"><Loader2 size={14} className="spin" /> Running Dijkstra to nearby hospitals, police & fire stations…</p>}
              {evac && <>
                <div className={`advice ${evac.options.some((o) => o.state === "Recommended") ? "advice-ok" : "advice-bad"}`}><Navigation size={18} /><p>{evac.advice}</p></div>
                {evac.inFloodZone && <div className="advice advice-warn"><AlertTriangle size={18} /><p>You are inside a verified flood zone. Move carefully toward the route shown.</p></div>}
                <ul className="shelters">
                  {evac.options.map((o, i) => (
                    <li key={i} className={`shelter state-${o.state.split(" ")[0].toLowerCase()}`}>
                      <span className="rank">{i + 1}</span>
                      <div className="sh-main"><strong>{o.name}</strong><span className="muted small">{o.kind.replace("_", " ")}</span>
                        <div className="sh-meta">{o.found ? <><b>{o.distance?.toFixed(1)} km</b> · ~{o.eta} min</> : "Unreachable on open roads"}</div></div>
                      <span className="sh-state">{o.state}</span>
                    </li>
                  ))}
                </ul>
              </>}
            </div>
          </Panel>
        )}
      </div>

      <Panel className="ghana-map-panel" pad={false} title={<>Ghana live map <span className="muted small">· {zones} verified flood zone{zones === 1 ? "" : "s"} · {pending} awaiting verification</span></>}
        icon={<MapIcon size={16} />}
        actions={<div className="tabs-mini">
          <button className={theme === "dark" ? "on" : ""} onClick={() => setTheme("dark")}>Dark</button>
          <button className={theme === "street" ? "on" : ""} onClick={() => setTheme("street")}>Street</button>
          <button className={theme === "offline" ? "on" : ""} onClick={() => setTheme("offline")} title="Our own Ghana road data, no internet needed">Offline</button>
        </div>}>
        {pick && <div className="pick-banner"><MapIcon size={15} /> Tap the map to set <b>{pick === "from" ? "your start" : pick === "to" ? "your destination" : pick === "report" ? "the flood location" : "your position"}</b>
          <button className="icon-btn" onClick={() => setPick(null)}><X size={14} /></button></div>}
        <GhanaLeaflet geo={geo} markers={markers} lines={lines} picking={!!pick} onPick={onPick} fitTo={fitTo} theme={theme}
          onTilesFailed={() => { setTheme("offline"); toast("info", "No map images — switched to offline map", "Drawing Ghana's roads from FloodWatch's own data instead."); }} />
        <div className="map-legend">
          <span><i className="lg lg-route" />Safe route</span><span><i className="lg lg-old" />Previous route</span>
          <span><i className="lg lg-blocked" />Closed road</span><span><i className="lg lg-zone" />Verified flood zone</span>
          <span><i className="lg lg-pending" />Awaiting verification</span>
        </div>
      </Panel>
    </div>
  );
}

const fmtTime = (m: number) => (m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} m`);
const fmtM = (m: number) => (m < 1000 ? `${m} m` : `${(m / 1000).toFixed(1)} km`);
