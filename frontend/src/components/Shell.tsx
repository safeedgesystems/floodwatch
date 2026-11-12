import { createContext, FormEvent, ReactNode, useContext, useState } from "react";
import {
  Binary, Compass, Home, LayoutDashboard, LifeBuoy, ListChecks, LogOut, Map as MapIcon, Menu, ShieldCheck, ShieldOff, Waves, X,
} from "lucide-react";
import { adminToken, api, ApiError, State } from "../lib/api";
import type { Conn } from "../lib/live";
import { Modal, useUi } from "./ui";

export type View = "dashboard" | "ghana" | "reports" | "routing" | "evacuation" | "internals";

/* ------------------------------------------------------------ App context */
interface AppCtx {
  state: State;
  isAdmin: boolean;
  /** Runs fn if admin; otherwise opens the sign-in dialog first. */
  admin: (fn: () => Promise<unknown>) => Promise<void>;
  go: (v: View, params?: Record<string, string>) => void;
  params: URLSearchParams;
}
const Ctx = createContext<AppCtx>(null!);
export const useApp = () => useContext(Ctx);

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <div className="logo">
      <span className="logo-mark"><Waves size={compact ? 18 : 20} /></span>
      {!compact && <span className="logo-text">Flood<b>Watch</b></span>}
    </div>
  );
}

// The simulation-city Routing and Evacuation views are hidden: routing and
// evacuation are done on the Ghana Live Map. Set to true to bring them back.
export const SHOW_SIM_VIEWS = false;
export const HIDDEN_VIEWS: View[] = SHOW_SIM_VIEWS ? [] : ["routing", "evacuation"];

const ALL_NAV: { id: View; label: string; icon: ReactNode }[] = [
  { id: "dashboard", label: "Command Center", icon: <LayoutDashboard size={18} /> },
  { id: "ghana", label: "Ghana Live Map", icon: <MapIcon size={18} /> },
  { id: "reports", label: "Reports & Queue", icon: <ListChecks size={18} /> },
  { id: "routing", label: "Sim · Safe Routing", icon: <Compass size={18} /> },
  { id: "evacuation", label: "Sim · Evacuation", icon: <LifeBuoy size={18} /> },
  { id: "internals", label: "Under the Hood", icon: <Binary size={18} /> },
];
const NAV = ALL_NAV.filter((n) => !HIDDEN_VIEWS.includes(n.id));

const TITLES: Record<View, [string, string]> = {
  dashboard: ["Command Center", "Live situational picture across the network"],
  ghana: ["Ghana Live Map", "Real roads across Ghana · report floods · flood-aware routing with our Dijkstra"],
  reports: ["Reports & Verification Queue", "Submit, triage and verify community flood reports"],
  routing: ["Safe Routing · Simulation", "Offline demo city: Dijkstra shortest open route, step by step"],
  evacuation: ["Evacuation Advisor · Simulation", "Offline demo city: ranked shelters, avoiding flooded areas"],
  internals: ["Under the Hood", "Hash table, FIFO queue and min-heap — live"],
};

export function Shell({ view, state, conn, params, go, onHome, children }: {
  view: View; state: State; conn: Conn; params: URLSearchParams;
  go: AppCtx["go"]; onHome: () => void; children: ReactNode;
}) {
  const { toast } = useUi();
  const [isAdmin, setIsAdmin] = useState(() => !!adminToken.get());
  const [login, setLogin] = useState<null | { resume?: () => Promise<unknown> }>(null);
  const [navOpen, setNavOpen] = useState(false);

  const admin: AppCtx["admin"] = async (fn) => {
    if (!adminToken.get()) { setLogin({ resume: fn }); return; }
    try { await fn(); } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        adminToken.set(null); setIsAdmin(false); setLogin({ resume: fn });
        toast("error", "Admin session expired", "Sign in again to continue.");
      } else toast("error", "Action failed", (e as Error).message);
    }
  };

  const [title, sub] = TITLES[view];
  return (
    <Ctx.Provider value={{ state, isAdmin, admin, go, params }}>
      <div className={`shell ${navOpen ? "nav-open" : ""}`}>
        <aside className="sidebar">
          <div className="sidebar-top">
            <button className="logo-btn" onClick={onHome} aria-label="Home"><Logo /></button>
            <button className="icon-btn mobile-only" onClick={() => setNavOpen(false)} aria-label="Close menu"><X size={18} /></button>
          </div>
          <nav>
            {NAV.map((n) => (
              <button key={n.id} className={`nav-item ${view === n.id ? "active" : ""}`}
                onClick={() => { go(n.id); setNavOpen(false); }}>
                {n.icon}<span>{n.label}</span>
                {n.id === "reports" && state.stats.queue > 0 && <em className="nav-count">{state.stats.queue}</em>}
              </button>
            ))}
          </nav>
          <div className="sidebar-foot">
            <div className="net-health">
              <div className="net-health-head"><span>Network health</span><b>{Math.round(state.stats.connectivity * 100)}%</b></div>
              <div className="bar"><i style={{ width: `${state.stats.connectivity * 100}%` }} /></div>
              <small>{state.stats.roads - state.stats.blockedRoads}/{state.stats.roads} roads open · {state.stats.locations} locations</small>
            </div>
            <button className="nav-item" onClick={onHome}><Home size={18} /><span>Landing page</span></button>
          </div>
        </aside>
        <div className="scrim" onClick={() => setNavOpen(false)} />

        <div className="main">
          <header className="topbar">
            <button className="icon-btn mobile-only" onClick={() => setNavOpen(true)} aria-label="Open menu"><Menu size={20} /></button>
            <div className="topbar-title"><h1>{title}</h1><p>{sub}</p></div>
            <div className="topbar-right">
              <div className="chips">
                <span className="chip"><b>{state.stats.active}</b> active</span>
                <span className="chip chip-high"><b>{state.stats.high}</b> high</span>
                <span className="chip chip-blocked"><b>{state.stats.blockedRoads}</b> closed</span>
              </div>
              <span className={`conn conn-${conn}`} title={`Realtime: ${conn}`}><i />{conn === "live" ? "Live" : conn === "connecting" ? "Connecting" : "Reconnecting"}</span>
              {isAdmin ? (
                <button className="btn btn-sm btn-admin" onClick={() => { adminToken.set(null); setIsAdmin(false); toast("info", "Signed out of admin mode"); }}>
                  <ShieldCheck size={15} /> Admin <LogOut size={13} />
                </button>
              ) : (
                <button className="btn btn-sm btn-ghost" onClick={() => setLogin({})}><ShieldOff size={15} /> Resident</button>
              )}
            </div>
          </header>
          <main className="content" key={view}>{children}</main>
        </div>
      </div>

      {login && (
        <AdminLogin onClose={() => setLogin(null)} onOk={async () => {
          setIsAdmin(true);
          const resume = login.resume; setLogin(null);
          toast("success", "Admin mode enabled", "You can now verify reports and manage roads.");
          if (resume) await admin(resume);
        }} />
      )}
    </Ctx.Provider>
  );
}

function AdminLogin({ onClose, onOk }: { onClose: () => void; onOk: () => void }) {
  const [token, setToken] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr("");
    adminToken.set(token.trim());
    try { await api.verifyAdmin(); onOk(); } catch { adminToken.set(null); setErr("That token was not accepted."); } finally { setBusy(false); }
  };
  return (
    <Modal onClose={onClose}>
      <div className="modal-icon"><ShieldCheck size={22} /></div>
      <h3>Admin sign-in</h3>
      <p className="muted">Verifying reports, closing roads and managing data requires the admin token configured on the server.</p>
      <form onSubmit={submit} className="stack">
        <input className="input" type="password" autoFocus placeholder="Admin token" value={token} onChange={(e) => setToken(e.target.value)} />
        {err && <div className="form-error">{err}</div>}
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={!token || busy}>{busy ? "Checking…" : "Sign in"}</button>
        </div>
      </form>
      <p className="hint">Demo default: <code>floodwatch-admin</code> (change via <code>FLOODWATCH_ADMIN_TOKEN</code>).</p>
    </Modal>
  );
}
