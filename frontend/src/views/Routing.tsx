import { useEffect, useRef, useState } from "react";
import { ArrowDownUp, Ban, Cpu, Milestone, Play, Route as RouteIcon, TrafficCone } from "lucide-react";
import NetworkMap from "../components/NetworkMap";
import { useApp } from "../components/Shell";
import { Panel, useUi } from "../components/ui";
import { api, RouteResult } from "../lib/api";

export default function Routing() {
  const { state, params, admin, isAdmin } = useApp();
  const { toast } = useUi();
  const ids = state.locations.map((l) => l.id);
  const [from, setFrom] = useState(params.get("from") && ids.includes(params.get("from")!) ? params.get("from")! : "RS");
  const [to, setTo] = useState(params.get("to") ?? (from === "HC" ? "AP" : "HC"));
  const [next, setNext] = useState<"from" | "to">("to");
  const [res, setRes] = useState<RouteResult | null>(null);
  const [step, setStep] = useState<number | null>(null);   // animation cursor into trace.settled
  const timer = useRef<number>();
  const loc = (id: string) => state.locations.find((l) => l.id === id);

  const animate = (r: RouteResult) => {
    window.clearInterval(timer.current);
    setStep(0);
    timer.current = window.setInterval(() => {
      setStep((s) => {
        if (s === null || s >= r.trace.settled.length) { window.clearInterval(timer.current); return null; }
        return s + 1;
      });
    }, 280);
  };

  // New endpoints → fetch and animate. State changes (road closures) → refetch silently.
  const lastPair = useRef("");
  useEffect(() => {
    if (from === to || !loc(from) || !loc(to)) { setRes(null); return; }
    let cancelled = false;
    api.route(from, to).then((r) => {
      if (cancelled) return;
      setRes(r);
      const pair = `${from}>${to}`;
      if (pair !== lastPair.current) { lastPair.current = pair; animate(r); }
    }).catch((e) => toast("error", "Routing failed", e.message));
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [from, to, state.version]);
  useEffect(() => () => window.clearInterval(timer.current), []);

  const animating = step !== null;
  const explored = res ? (animating ? res.trace.settled.slice(0, step!) : res.trace.settled) : [];
  const segs = res?.found ? res.roads.map((rid, i) => ({ rid, a: res.path[i], b: res.path[i + 1], km: state.roads.find((r) => r.id === rid)?.km ?? 0 })) : [];

  const pick = (id: string) => {
    if (next === "from") { setFrom(id); setNext("to"); } else { setTo(id); setNext("from"); }
  };
  const toggle = (id: string) => admin(async () => {
    const r = state.roads.find((x) => x.id === id)!;
    await api.blockRoad(id, !r.manual);
    toast("success", `Road ${id} ${r.manual ? "reopened" : "closed"}`);
  });

  return (
    <div className="grid-routing">
      <div className="col">
        <Panel title="Plan a route" icon={<RouteIcon size={16} />}>
          <div className="od">
            <label className="field"><span><i className="dot dot-a">A</i> From</span>
              <select className="input" value={from} onChange={(e) => setFrom(e.target.value)}>
                {state.locations.map((l) => <option key={l.id} value={l.id}>{l.name} ({l.id})</option>)}
              </select></label>
            <button className="icon-btn swap" aria-label="Swap" onClick={() => { setFrom(to); setTo(from); }}><ArrowDownUp size={16} /></button>
            <label className="field"><span><i className="dot dot-b">B</i> To</span>
              <select className="input" value={to} onChange={(e) => setTo(e.target.value)}>
                {state.locations.map((l) => <option key={l.id} value={l.id}>{l.name} ({l.id})</option>)}
              </select></label>
          </div>

          {from === to ? <p className="muted">Choose two different locations.</p> : res && (
            res.found ? (
              <div className="route-card">
                <div className="route-figs">
                  <div><b>{res.distance?.toFixed(1)}</b><span>km</span></div>
                  <div><b>{res.eta}</b><span>min ETA</span></div>
                  <div><b>{res.roads.length}</b><span>segments</span></div>
                </div>
                <ol className="steps">
                  {segs.map((s, i) => (
                    <li key={s.rid}>
                      <span className="step-dot">{i === 0 ? "A" : i + 1}</span>
                      <div><strong>{loc(s.a)?.name}</strong> → {loc(s.b)?.name}<small className="mono">{s.rid} · {s.km.toFixed(1)} km</small></div>
                    </li>
                  ))}
                  <li className="arrive"><span className="step-dot">B</span><div><strong>Arrive at {loc(to)?.name}</strong></div></li>
                </ol>
              </div>
            ) : (
              <div className="route-none"><Ban size={20} /><div><strong>No open route</strong><p>Every path between these locations crosses a closed road. Try evacuation to a shelter instead.</p></div></div>
            )
          )}
        </Panel>

        {res && (
          <Panel title="Algorithm trace" icon={<Cpu size={16} />}
            actions={<button className="btn btn-sm btn-ghost" onClick={() => animate(res)} disabled={animating}><Play size={14} /> {animating ? "Searching…" : "Replay search"}</button>}>
            <div className="algo-figs">
              <div><b>{res.trace.settled.length}</b><span>nodes settled</span></div>
              <div><b>{res.trace.relaxations.length}</b><span>edge relaxations</span></div>
              <div><b>{res.trace.heap.pushes}/{res.trace.heap.pops}</b><span>heap push/pop</span></div>
              <div><b>{res.trace.heap.peak}</b><span>peak heap size</span></div>
            </div>
            <div className="settle-seq">
              {res.trace.settled.map((id, i) => (
                <span key={id} className={`chip-node ${animating && i >= step! ? "pending" : ""} ${res.path.includes(id) ? "on" : ""}`}>{i + 1}. {id}</span>
              ))}
            </div>
            {res.trace.blockedSkipped.length > 0 && <p className="hint"><TrafficCone size={13} /> Skipped closed roads: <span className="mono">{res.trace.blockedSkipped.join(", ")}</span></p>}
          </Panel>
        )}
      </div>

      <div className="col">
        <Panel title="Route map" icon={<Milestone size={16} />}
          actions={<span className="pick-hint">Click map to set <b className={`dot dot-${next === "from" ? "a" : "b"}`}>{next === "from" ? "A" : "B"}</b></span>}>
          <NetworkMap state={state} height={430} from={from} to={to} explored={explored}
            route={!animating && res?.found ? res : null} onNodeClick={pick} onRoadClick={isAdmin ? toggle : undefined} />
        </Panel>

        <Panel title="Road status" icon={<TrafficCone size={16} />} pad={false}>
          <div className="table-wrap tall">
            <table className="table">
              <thead><tr><th>Road</th><th>Segment</th><th>Km</th><th>Status</th><th>Source</th><th>Manual closure</th></tr></thead>
              <tbody>
                {state.roads.map((r) => (
                  <tr key={r.id} className={res?.roads.includes(r.id) ? "hl" : ""}>
                    <td className="mono">{r.id}</td>
                    <td>{loc(r.a)?.name} — {loc(r.b)?.name}</td>
                    <td className="mono">{r.km.toFixed(1)}</td>
                    <td>{r.blocked ? <span className="badge st-blocked">Closed</span> : <span className="badge st-open">Open</span>}</td>
                    <td className="muted">{[r.manual && "Manual", r.reportIds.length && `Report ${r.reportIds.join(", ")}`].filter(Boolean).join(" + ") || "—"}</td>
                    <td><button role="switch" aria-checked={r.manual} className={`switch ${r.manual ? "on" : ""}`} onClick={() => toggle(r.id)}><i /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="hint pad">Roads named in a <b>Verified</b> report close automatically and reopen when it is resolved.{!isAdmin && " Manual closures need admin."}</p>
        </Panel>
      </div>
    </div>
  );
}
