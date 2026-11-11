import { useEffect, useState } from "react";
import { ArrowRight, Binary, Boxes, Cpu, Hash, ListOrdered, ShieldCheck } from "lucide-react";
import { useApp } from "../components/Shell";
import { Panel, useUi } from "../components/ui";
import { api, LookupResult } from "../lib/api";

export default function Internals() {
  return (
    <div className="grid-internals">
      <HashPanel />
      <div className="col">
        <QueuePanel />
        <HeapPanel />
        <Complexity />
      </div>
    </div>
  );
}

function HashPanel() {
  const { state, admin } = useApp();
  const { toast } = useUi();
  const [key, setKey] = useState("FL001");
  const [res, setRes] = useState<LookupResult | null>(null);
  const h = state.hash.stats;

  useEffect(() => {
    if (!key.trim()) { setRes(null); return; }
    const t = window.setTimeout(() => api.lookup(key.trim()).then(setRes).catch(() => setRes(null)), 150);
    return () => window.clearTimeout(t);
  }, [key, state.version]);

  const chars = key.trim().toUpperCase().split("");
  return (
    <Panel title="Hash table · separate chaining" icon={<Hash size={16} />}
      actions={<div className="tabs-mini">
        {state.hash.allowedSizes.map((s) => (
          <button key={s} className={h.size === s ? "on" : ""}
            onClick={() => admin(async () => { await api.resizeHash(s); toast("success", `Rehashed into ${s} buckets`); })}>{s}</button>
        ))}
      </div>}>
      <div className="hash-stats">
        <div><b>{h.count}</b><span>entries</span></div>
        <div><b>{h.size}</b><span>buckets</span></div>
        <div><b className={h.loadFactor > 0.75 ? "warn-text" : ""}>{h.loadFactor.toFixed(2)}</b><span>load factor</span></div>
        <div><b className={h.collisions ? "warn-text" : ""}>{h.collisions}</b><span>collisions</span></div>
        <div><b>{h.longestChain}</b><span>longest chain</span></div>
      </div>
      <div className="bar lf"><i style={{ width: `${Math.min(100, h.loadFactor * 100)}%` }} className={h.loadFactor > 0.75 ? "hot" : ""} /></div>

      <div className="probe">
        <label className="field"><span>Probe a key</span>
          <input className="input mono" value={key} maxLength={12} onChange={(e) => setKey(e.target.value)} /></label>
        {res && (
          <div className="formula mono">
            <div className="chars">{chars.map((c, i) => <span key={i}><b>{c}</b><small>{c.charCodeAt(0)}</small></span>)}</div>
            <div>Σ = <b>{res.hashSum}</b> &nbsp;→&nbsp; {res.hashSum} mod {res.size} = <b className="accent">bucket {res.bucket}</b></div>
            <div className={res.found ? "ok-text" : "warn-text"}>{res.found ? `Found after ${res.steps} probe${res.steps > 1 ? "s" : ""}` : `Not found — ${res.steps} entr${res.steps === 1 ? "y" : "ies"} checked`}</div>
          </div>
        )}
      </div>

      <div className="buckets">
        {state.hash.buckets.map((chain, i) => {
          const active = res?.bucket === i;
          return (
            <div key={i} className={`bucket ${active ? "active" : ""}`}>
              <span className="bucket-idx mono">{i}</span>
              <div className="chain">
                {chain.length === 0 ? <span className="null mono">∅</span> : chain.map((e, j) => {
                  const probed = active && res!.visited.includes(e.key);
                  const hit = active && res!.found && res!.report?.id === e.key;
                  return (
                    <span key={e.key} className="chain-item">
                      {j > 0 && <ArrowRight size={12} className="muted" />}
                      <span className={`entry sev-${e.severity.toLowerCase()} ${probed ? "probed" : ""} ${hit ? "hit" : ""}`} style={{ animationDelay: `${j * 0.12}s` }}>
                        <i />{e.key}<small>{e.status[0]}</small>
                      </span>
                    </span>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
      <p className="hint">Hash = sum of character codes mod bucket count. Try <span className="mono">AB</span> vs <span className="mono">BA</span> — same sum, same bucket. Resizing rehashes every entry (admin).</p>
    </Panel>
  );
}

function QueuePanel() {
  const { state, admin } = useApp();
  const { toast } = useUi();
  return (
    <Panel title="Verification queue · FIFO (linked list)" icon={<ListOrdered size={16} />}
      actions={<button className="btn btn-sm btn-primary" disabled={!state.queue.length}
        onClick={() => admin(async () => { const r = await api.processNext(); toast("success", "Dequeued", r.message); })}>
        <ShieldCheck size={14} /> Dequeue</button>}>
      <div className="lane">
        <span className="lane-cap">HEAD<small>dequeue</small></span>
        <div className="lane-items">
          {state.queue.length === 0 ? <span className="null mono">empty</span> : state.queue.map((id) => {
            const r = state.reports.find((x) => x.id === id);
            return <span key={id} className={`qnode sev-${r?.severity.toLowerCase()}`}><b className="mono">{id}</b><small>{r?.location}</small></span>;
          })}
        </div>
        <span className="lane-cap">TAIL<small>enqueue</small></span>
      </div>
      <p className="hint">O(1) enqueue at the tail on submit, O(1) dequeue at the head on verify. Re-opened reports re-enter at the tail.</p>
    </Panel>
  );
}

function HeapPanel() {
  const { state } = useApp();
  // Route queries don't broadcast, so pull a fresh snapshot for the latest trace.
  const [fresh, setFresh] = useState(state.lastRouteTrace);
  useEffect(() => { api.state().then((s) => setFresh(s.lastRouteTrace)).catch(() => {}); }, [state.version]);
  const t = fresh ?? state.lastRouteTrace;
  return (
    <Panel title="Min-heap · last Dijkstra run" icon={<Cpu size={16} />}>
      {!t ? <p className="muted">Plan a route to see the priority queue at work.</p> : (
        <>
          <p className="muted small">{t.real ? <>Last route on the <b>Ghana road network</b> ({(t.settledCount ?? 0).toLocaleString()} junctions settled)</> : <>Route <b className="mono">{t.from} → {t.to}</b></>}</p>
          <div className="algo-figs">
            <div><b>{t.heap.pushes}</b><span>pushes (sift-up)</span></div>
            <div><b>{t.heap.pops}</b><span>pops (sift-down)</span></div>
            <div><b>{t.heap.peak}</b><span>peak size</span></div>
            <div><b>{t.heap.pushes - (t.settledCount ?? t.settled.length)}</b><span>pushes not settled</span></div>
          </div>
          <div className="settle-seq">{t.settled.map((id, i) => <span key={id} className="chip-node on">{i + 1}. {id}</span>)}</div>
          <p className="hint">Lazy deletion: instead of decrease-key, a node is re-pushed with its better distance and stale entries are skipped on pop.</p>
        </>
      )}
    </Panel>
  );
}

function Complexity() {
  const rows = [
    ["Submit report", "Hash put + queue enqueue", "O(1) avg"],
    ["Lookup by ID", "Hash get (chain walk)", "O(1 + α)"],
    ["Verify next", "Queue dequeue", "O(1)"],
    ["Shortest route", "Dijkstra + binary heap", "O((V+E) log V)"],
    ["Evacuation", "Dijkstra × shelters", "O(S·(V+E) log V)"],
    ["Rehash", "Re-insert all entries", "O(n)"],
  ];
  return (
    <Panel title="Complexity at a glance" icon={<Boxes size={16} />} pad={false}>
      <table className="table compact">
        <thead><tr><th>Operation</th><th>Structure</th><th>Cost</th></tr></thead>
        <tbody>{rows.map((r) => <tr key={r[0]}><td>{r[0]}</td><td className="muted">{r[1]}</td><td className="mono accent"><Binary size={12} /> {r[2]}</td></tr>)}</tbody>
      </table>
    </Panel>
  );
}
