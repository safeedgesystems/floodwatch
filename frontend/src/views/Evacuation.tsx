import { useEffect, useState } from "react";
import { AlertTriangle, Ban, Crosshair, LifeBuoy, Navigation, ShieldAlert, ShieldCheck } from "lucide-react";
import NetworkMap from "../components/NetworkMap";
import { useApp } from "../components/Shell";
import { Panel, RiskBadge, useUi } from "../components/ui";
import { api, EvacResult, RiskLabel } from "../lib/api";

const RISK_LEVEL: Record<RiskLabel, number> = { Safe: 0, Watch: 1, Warning: 2, Danger: 3 };

export default function Evacuation() {
  const { state, params } = useApp();
  const { toast } = useUi();
  const [from, setFrom] = useState(params.get("from") ?? "RS");
  const [res, setRes] = useState<EvacResult | null>(null);
  const [focus, setFocus] = useState<string | null>(null);

  useEffect(() => {
    api.evacuate(from).then((r) => { setRes(r); setFocus(r.best); })
      .catch((e) => toast("error", "Evacuation advisor failed", e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [from, state.version]);

  const here = state.locations.find((l) => l.id === from);
  const shown = res?.options.find((o) => o.id === focus && o.found);
  const level = res ? RISK_LEVEL[res.risk] : 0;

  return (
    <div className="grid-evac">
      <div className="col">
        <Panel title="Where are you now?" icon={<Crosshair size={16} />}>
          <select className="input" value={from} onChange={(e) => setFrom(e.target.value)}>
            {state.locations.map((l) => <option key={l.id} value={l.id}>{l.name} ({l.id})</option>)}
          </select>

          {res && here && (
            <>
              <div className="gauge-row">
                <Gauge level={level} />
                <div>
                  <span className="muted small">Your area</span>
                  <h3 className="gauge-title">{here.name}</h3>
                  <RiskBadge r={res.risk} /> <span className="muted small">risk score {res.riskScore}</span>
                </div>
              </div>
              <div className={`advice ${res.best ? "advice-ok" : "advice-bad"}`}>
                {res.best ? <Navigation size={20} /> : <AlertTriangle size={20} />}
                <p>{res.advice}</p>
              </div>
            </>
          )}
        </Panel>

        <Panel title="Shelters ranked" icon={<LifeBuoy size={16} />}>
          <ul className="shelters">
            {res?.options.map((o, i) => (
              <li key={o.id} className={`shelter state-${o.state.split(" ")[0].toLowerCase()} ${focus === o.id ? "focus" : ""}`}
                onClick={() => o.found && setFocus(o.id)}>
                <span className="rank">{i + 1}</span>
                <div className="sh-main">
                  <strong>{o.name}</strong><span className="muted small">{o.kind}</span>
                  <div className="sh-meta">
                    {o.found ? <><b>{o.distance?.toFixed(1)} km</b> · ~{o.eta} min</> : <span>Unreachable on open roads</span>}
                    <RiskBadge r={o.risk} />
                  </div>
                </div>
                <span className="sh-state">
                  {o.state === "Recommended" ? <ShieldCheck size={16} /> : o.state === "Cut off" ? <Ban size={16} /> : o.flooded ? <ShieldAlert size={16} /> : null}
                  {o.state}
                </span>
              </li>
            ))}
          </ul>
          <p className="hint">ETA assumes {state.etaSpeedKmh} km/h in flood conditions. Shelters with an active High-severity report rank last.</p>
        </Panel>
      </div>

      <Panel className="evac-map" title={shown ? `Route to ${shown.name}` : "Evacuation map"} icon={<Navigation size={16} />}
        actions={<div className="legend"><span><i className="lg lg-safe" />Evacuation route</span><span><i className="lg lg-shelter" />Shelter</span></div>}>
        <NetworkMap state={state} showShelters height={560} from={from} to={shown?.id ?? null}
          route={shown ?? null} routeTone="safe" onNodeClick={setFrom} />
        <p className="hint">Click any location to evacuate from there. Click a shelter card to preview its route.</p>
      </Panel>
    </div>
  );
}

function Gauge({ level }: { level: number }) {
  // 4-segment semicircle gauge
  const colors = ["var(--ok)", "var(--watch)", "var(--warn)", "var(--danger)"];
  const arc = (i: number) => {
    const a0 = Math.PI + (i * Math.PI) / 4 + 0.04, a1 = Math.PI + ((i + 1) * Math.PI) / 4 - 0.04;
    const p = (a: number) => `${50 + 40 * Math.cos(a)},${50 + 40 * Math.sin(a)}`;
    return `M${p(a0)} A40,40 0 0 1 ${p(a1)}`;
  };
  const needle = Math.PI + ((level + 0.5) * Math.PI) / 4;
  return (
    <svg viewBox="0 0 100 58" className="gauge" aria-hidden>
      {colors.map((c, i) => <path key={i} d={arc(i)} stroke={c} strokeWidth="9" fill="none" opacity={i <= level ? 1 : 0.18} strokeLinecap="round" />)}
      <line x1="50" y1="50" x2={50 + 30 * Math.cos(needle)} y2={50 + 30 * Math.sin(needle)} stroke="var(--text)" strokeWidth="3" strokeLinecap="round" className="needle" />
      <circle cx="50" cy="50" r="4" fill="var(--text)" />
    </svg>
  );
}
