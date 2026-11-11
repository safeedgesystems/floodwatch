import { FormEvent, useMemo, useState } from "react";
import {
  CheckCheck, Hash, Inbox, RotateCcw, Search, Send, ShieldCheck, Trash2, X,
} from "lucide-react";
import NetworkMap from "../components/NetworkMap";
import { useApp } from "../components/Shell";
import { Empty, Panel, SevBadge, StatusBadge, timeAgo, useUi } from "../components/ui";
import { api, ApiError, LookupResult, Report, Severity, Status } from "../lib/api";

const FILTERS = ["All", "Active", "Reported", "Verified", "Resolved"] as const;

export default function Reports() {
  return (
    <div className="grid-reports">
      <ReportForm />
      <ReportTable />
    </div>
  );
}

/* ------------------------------------------------------------- Submit form */
function ReportForm() {
  const { state } = useApp();
  const { toast } = useUi();
  const [location, setLocation] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState<Severity>("Medium");
  const [roadId, setRoadId] = useState("");
  const [pin, setPin] = useState<{ x: number; y: number } | null>(null);
  const [busy, setBusy] = useState(false);

  const match = state.locations.find((l) => [l.name.toLowerCase(), l.id.toLowerCase()].includes(location.trim().toLowerCase()));
  const roads = useMemo(() => {
    const near = (r: { a: string; b: string }) => (match && (r.a === match.id || r.b === match.id) ? 0 : 1);
    return [...state.roads].sort((a, b) => near(a) - near(b) || a.id.localeCompare(b.id));
  }, [state.roads, match]);
  const name = (id: string) => state.locations.find((l) => l.id === id)?.name ?? id;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api.submit({ location, description, severity, roadId: roadId || null, ...(pin && !match ? pin : {}) });
      toast("success", `${r.id} submitted`, match ? "Added to the verification queue." : `New location “${r.location}” was mapped onto the network.`);
      setLocation(""); setDescription(""); setRoadId(""); setPin(null); setSeverity("Medium");
    } catch (err) {
      toast("error", "Could not submit report", err instanceof ApiError ? err.message : "Network error");
    } finally { setBusy(false); }
  };

  return (
    <Panel className="report-form" title="Report flooding" icon={<Send size={16} />}>
      <form onSubmit={submit} className="stack">
        <label className="field">
          <span>Location</span>
          <input className="input" list="loc-list" required minLength={2} maxLength={60} value={location}
            placeholder="Pick a known place or type a new one" onChange={(e) => setLocation(e.target.value)} />
          <datalist id="loc-list">{state.locations.map((l) => <option key={l.id} value={l.name} />)}</datalist>
          <small className={match ? "ok-text" : "muted"}>
            {location.trim().length < 2 ? "Tap a location on the mini-map, or type a name"
              : match ? `✓ Matches ${match.name} (${match.id})`
              : pin ? "New location — will be placed at your pin" : "New location — tap the map to place it, or we'll auto-place it"}
          </small>
        </label>

        <div className="mini-map">
          <NetworkMap state={state} showKm={false} height={190} pin={match ? null : pin}
            from={match?.id ?? null}
            onNodeClick={(id) => { setLocation(name(id)); setPin(null); }}
            onPick={(x, y) => { setPin({ x, y }); if (match) setLocation(""); }} />
        </div>

        <label className="field">
          <span>What's happening?</span>
          <textarea className="input" rows={3} required minLength={3} maxLength={280} value={description}
            placeholder="e.g. Water covering both lanes near the bridge" onChange={(e) => setDescription(e.target.value)} />
          <small className="muted right">{description.length}/280</small>
        </label>

        <div className="field">
          <span>Severity</span>
          <div className="segmented" role="radiogroup">
            {(["High", "Medium", "Low"] as Severity[]).map((s) => (
              <button type="button" key={s} role="radio" aria-checked={severity === s}
                className={`seg seg-${s.toLowerCase()} ${severity === s ? "on" : ""}`} onClick={() => setSeverity(s)}>{s}</button>
            ))}
          </div>
        </div>

        <label className="field">
          <span>Affected road <em>(optional)</em></span>
          <select className="input" value={roadId} onChange={(e) => setRoadId(e.target.value)}>
            <option value="">None — area flooding only</option>
            {roads.map((r) => <option key={r.id} value={r.id}>{r.id} · {name(r.a)} → {name(r.b)}{r.blocked ? " (closed)" : ""}</option>)}
          </select>
          <small className="muted">Once verified, this road is closed for routing.</small>
        </label>

        <button className="btn btn-primary btn-block" disabled={busy}>
          <Send size={16} /> {busy ? "Submitting…" : `Submit report ${state.nextId}`}
        </button>
      </form>
    </Panel>
  );
}

/* --------------------------------------------------------- Table + admin */
function ReportTable() {
  const { state, admin, isAdmin, params } = useApp();
  const { toast, confirm } = useUi();
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("All");
  const [q, setQ] = useState("");
  const [lookupKey, setLookupKey] = useState(params.get("id") ?? "");
  const [lookup, setLookup] = useState<LookupResult | null>(null);

  const rows = state.reports.filter((r) => {
    if (filter === "Active" && r.status === "Resolved") return false;
    if (filter !== "All" && filter !== "Active" && r.status !== filter) return false;
    const t = q.toLowerCase();
    return !t || [r.id, r.location, r.description, r.roadId ?? ""].some((v) => v.toLowerCase().includes(t));
  });

  const doLookup = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!lookupKey.trim()) return setLookup(null);
    setLookup(await api.lookup(lookupKey.trim()));
  };

  const setStatus = (r: Report, s: Status) => admin(async () => {
    await api.setStatus(r.id, s);
    toast("success", `${r.id} → ${s}`, s === "Verified" && r.roadId ? `Road ${r.roadId} is now closed.` : undefined);
  });
  const del = (r: Report) => admin(async () => {
    if (await confirm({ title: `Delete ${r.id}?`, body: `${r.severity} report at ${r.location} will be permanently removed.`, confirm: "Delete", danger: true })) {
      await api.remove(r.id); toast("success", `${r.id} deleted`);
    }
  });

  return (
    <Panel className="report-table" title="All reports" icon={<Inbox size={16} />}
      actions={<>
        <button className="btn btn-sm btn-primary" disabled={!state.queue.length}
          onClick={() => admin(async () => { const r = await api.processNext(); toast("success", "Report verified", r.message); })}>
          <ShieldCheck size={14} /> Verify next ({state.queue.length})
        </button>
        <button className="btn btn-sm btn-ghost danger-hover" disabled={!state.reports.length}
          onClick={() => admin(async () => {
            if (await confirm({ title: "Clear all reports?", body: "Every report and queue entry will be removed. Manual road closures stay.", confirm: "Clear all", danger: true })) {
              const r = await api.clear(); toast("success", `Cleared ${r.cleared} reports`);
            }
          })}><Trash2 size={14} /> Clear</button>
      </>}>

      <div className="toolbar">
        <div className="tabs-mini">
          {FILTERS.map((f) => <button key={f} className={filter === f ? "on" : ""} onClick={() => setFilter(f)}>{f}</button>)}
        </div>
        <div className="search"><Search size={15} /><input placeholder="Search reports…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <form className="lookup" onSubmit={doLookup}>
          <Hash size={15} />
          <input placeholder="Hash lookup: FL001" value={lookupKey} onChange={(e) => setLookupKey(e.target.value)} />
          <button className="btn btn-sm btn-ghost">Find</button>
        </form>
      </div>

      {lookup && (
        <div className={`lookup-result ${lookup.found ? "ok" : "miss"}`}>
          <div>
            <strong>{lookup.found ? `Found ${lookup.key}` : `${lookup.key} not found`}</strong>
            <span className="mono"> · Σchar = {lookup.hashSum} → {lookup.hashSum} mod {lookup.size} = bucket {lookup.bucket} · {lookup.steps} probe{lookup.steps === 1 ? "" : "s"}</span>
            {lookup.report && <p>{lookup.report.location} — {lookup.report.severity} — {lookup.report.status}</p>}
          </div>
          <button className="icon-btn" onClick={() => setLookup(null)} aria-label="Close"><X size={14} /></button>
        </div>
      )}

      {rows.length === 0 ? <Empty icon={<Inbox />} title="No reports" body={state.reports.length ? "Nothing matches your filters." : "Submitted reports will appear here."} /> : (
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>ID</th><th>Severity</th><th>Location</th><th>Road</th><th>Status</th><th>Description</th><th /></tr></thead>
            <tbody>
              {rows.map((r) => {
                const qpos = state.queue.indexOf(r.id);
                return (
                  <tr key={r.id} className={`${lookup?.report?.id === r.id ? "hl" : ""} ${r.status === "Resolved" ? "dim" : ""}`}>
                    <td className="mono">{r.id}<small className="cell-sub">{timeAgo(r.updatedAt)}</small></td>
                    <td><SevBadge s={r.severity} /></td>
                    <td>{r.location}</td>
                    <td className="mono">{r.lat != null ? <span className="badge st-verified" title={`${r.lat}, ${r.lon}`}>GPS</span> : r.roadId ?? "—"}</td>
                    <td><StatusBadge s={r.status} />{qpos >= 0 && <span className="qtag">queue #{qpos + 1}</span>}</td>
                    <td className="desc">{r.description}</td>
                    <td className="row-actions">
                      {r.status === "Reported" && <button className="btn btn-xs btn-ok" title="Verify" onClick={() => setStatus(r, "Verified")}><ShieldCheck size={13} /> Verify</button>}
                      {r.status === "Verified" && <button className="btn btn-xs btn-ghost" title="Resolve" onClick={() => setStatus(r, "Resolved")}><CheckCheck size={13} /> Resolve</button>}
                      {r.status === "Resolved" && <button className="btn btn-xs btn-ghost" title="Reopen" onClick={() => setStatus(r, "Reported")}><RotateCcw size={13} /> Reopen</button>}
                      <button className="icon-btn danger-hover" title="Delete" onClick={() => del(r)}><Trash2 size={14} /></button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {!isAdmin && <p className="hint">Verify, resolve and delete actions ask for the admin token.</p>}
    </Panel>
  );
}
