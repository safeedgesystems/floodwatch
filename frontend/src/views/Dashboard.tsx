import {
  Activity, AlertOctagon, ArrowRight, CheckCircle2, ClipboardList, Construction, Inbox, MapPinned, Network, Plus, ShieldCheck, Trash2, Waves,
} from "lucide-react";
import NetworkMap from "../components/NetworkMap";
import { useApp } from "../components/Shell";
import { Empty, Panel, RiskBadge, SevBadge, Stat, timeAgo, useUi } from "../components/ui";
import { api } from "../lib/api";

const EVENT_ICON: Record<string, JSX.Element> = {
  report: <Plus size={14} />, verify: <ShieldCheck size={14} />, status: <CheckCircle2 size={14} />,
  delete: <Trash2 size={14} />, road: <Construction size={14} />, network: <MapPinned size={14} />, system: <Activity size={14} />,
};

export default function Dashboard() {
  const { state, go, admin, isAdmin } = useApp();
  const { toast } = useUi();
  const s = state.stats;
  const hotspots = [...state.locations].filter((l) => l.riskScore > 0).sort((a, b) => b.riskScore - a.riskScore).slice(0, 6);
  const queue = state.queue.map((id) => state.reports.find((r) => r.id === id)).filter(Boolean);

  const toggleRoad = (id: string) => admin(async () => {
    const r = state.roads.find((x) => x.id === id)!;
    await api.blockRoad(id, !r.manual);
    toast("success", `Road ${id} ${r.manual ? "reopened" : "closed"}`);
  });

  return (
    <div className="grid-dash">
      <div className="kpis">
        <Stat label="Active reports" value={s.active} icon={<Waves size={18} />}
          hint={<div className="sev-bar">
            <i className="h" style={{ flex: s.high }} /><i className="m" style={{ flex: s.medium }} /><i className="l" style={{ flex: s.low }} />
          </div>} />
        <Stat label="High severity" value={s.high} tone={s.high ? "danger" : "default"} icon={<AlertOctagon size={18} />} hint={`${s.medium} medium · ${s.low} low`} />
        <Stat label="Awaiting verification" value={s.queue} tone={s.queue ? "warn" : "default"} icon={<Inbox size={18} />} hint="FIFO admin queue" />
        <Stat label="Roads closed" value={`${s.blockedRoads}/${s.roads}`} tone={s.blockedRoads ? "danger" : "default"} icon={<Construction size={18} />} hint="Manual + verified reports" />
        <Stat label="Network connectivity" value={`${Math.round(s.connectivity * 100)}%`} tone={s.connectivity < 1 ? "warn" : "ok"} icon={<Network size={18} />} hint="Location pairs still reachable" />
      </div>

      <Panel className="dash-map" title="Live network" icon={<MapPinned size={16} />}
        actions={<div className="legend">
          <span><i className="lg lg-blocked" />Closed</span><span><i className="lg lg-flood" />High</span>
          <span><i className="lg lg-med" />Medium</span><span><i className="lg lg-low" />Low</span><span><i className="lg lg-shelter" />Shelter</span>
        </div>}>
        <NetworkMap state={state} showShelters height={460}
          onNodeClick={() => go("ghana")}
          onRoadClick={isAdmin ? toggleRoad : undefined} />
        <p className="hint">Click a location to plan a real route on the Ghana Live Map{isAdmin ? " · click a road to close or reopen it" : ""}.</p>
      </Panel>

      <Panel className="dash-feed" title="Activity" icon={<Activity size={16} />}>
        <ol className="feed">
          {state.events.map((e) => (
            <li key={e.id} className={`feed-${e.kind}`}>
              <span className="feed-icon">{EVENT_ICON[e.kind] ?? <Activity size={14} />}</span>
              <div><p>{e.message}</p><time>{timeAgo(e.ts)}</time></div>
            </li>
          ))}
        </ol>
      </Panel>

      <Panel className="dash-hot" title="Risk hotspots" icon={<AlertOctagon size={16} />}>
        {hotspots.length === 0 ? <Empty icon={<CheckCircle2 />} title="No risk detected" body="Every location is currently safe." /> : (
          <ul className="hotspots">
            {hotspots.map((l) => (
              <li key={l.id} onClick={() => go("ghana", { tab: "evacuate" })}>
                <div className="hs-name"><strong>{l.name}</strong><span className="mono muted">{l.id}</span></div>
                <div className="hs-meter"><i className={`risk-bg-${l.risk.toLowerCase()}`} style={{ width: `${Math.min(100, l.riskScore * 14)}%` }} /></div>
                <RiskBadge r={l.risk} />
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel className="dash-queue" title="Verification queue" icon={<ClipboardList size={16} />}
        actions={<button className="btn btn-sm btn-primary" disabled={!queue.length}
          onClick={() => admin(async () => { const r = await api.processNext(); toast("success", "Report verified", r.message); })}>
          <ShieldCheck size={14} /> Verify next</button>}>
        {queue.length === 0 ? <Empty icon={<Inbox />} title="Queue is clear" body="New reports land here first." /> : (
          <ul className="mini-queue">
            {queue.slice(0, 5).map((r, i) => r && (
              <li key={r.id}>
                <span className="q-pos">{i === 0 ? "NEXT" : `#${i + 1}`}</span>
                <span className="mono">{r.id}</span>
                <SevBadge s={r.severity} />
                <span className="truncate">{r.location}</span>
              </li>
            ))}
          </ul>
        )}
        <button className="link-btn" onClick={() => go("reports")}>Open reports <ArrowRight size={14} /></button>
      </Panel>
    </div>
  );
}
