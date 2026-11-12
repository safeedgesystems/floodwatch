import { useCallback, useEffect, useState } from "react";
import { HIDDEN_VIEWS, Shell, View } from "./components/Shell";
import { UiProvider } from "./components/ui";
import { useLiveState } from "./lib/live";
import Dashboard from "./views/Dashboard";
import Evacuation from "./views/Evacuation";
import GhanaMap from "./views/GhanaMap";
import Internals from "./views/Internals";
import Landing from "./views/Landing";
import Reports from "./views/Reports";
import Routing from "./views/Routing";

// Tiny hash router: #/  (landing)  |  #/app/<view>?k=v
const VIEWS: View[] = ["dashboard", "ghana", "reports", "routing", "evacuation", "internals"];
function parse() {
  const [path, qs = ""] = location.hash.replace(/^#/, "").split("?");
  const m = path.match(/^\/app\/(\w+)/);
  let view = m && VIEWS.includes(m[1] as View) ? (m[1] as View) : null;
  // Old links to the hidden simulation views open the Ghana Live Map instead.
  if (view && HIDDEN_VIEWS.includes(view)) view = "ghana";
  return { view, params: new URLSearchParams(qs) };
}

export default function App() {
  const { state, conn } = useLiveState();
  const [route, setRoute] = useState(parse);

  useEffect(() => {
    const on = () => { setRoute(parse()); window.scrollTo(0, 0); };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);

  const go = useCallback((v: View, params?: Record<string, string>) => {
    location.hash = `/app/${v}${params ? "?" + new URLSearchParams(params) : ""}`;
  }, []);

  return (
    <UiProvider>
      {!route.view ? (
        <Landing state={state} onEnter={() => go("dashboard")} onReport={() => go("ghana", { tab: "report" })} />
      ) : !state ? (
        <div className="boot"><div className="spinner" /><p>{conn === "offline" ? "Cannot reach the FloodWatch server — retrying…" : "Loading live network…"}</p></div>
      ) : (
        <Shell view={route.view} state={state} conn={conn} params={route.params} go={go} onHome={() => (location.hash = "/")}>
          {route.view === "dashboard" && <Dashboard />}
          {route.view === "ghana" && <GhanaMap key={route.params.toString()} />}
          {route.view === "reports" && <Reports />}
          {route.view === "routing" && <Routing key={route.params.toString()} />}
          {route.view === "evacuation" && <Evacuation key={route.params.toString()} />}
          {route.view === "internals" && <Internals />}
        </Shell>
      )}
    </UiProvider>
  );
}
