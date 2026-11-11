import { useEffect, useRef } from "react";
import { ArrowRight, ClipboardCheck, Compass, Database, LifeBuoy, Megaphone, Radio } from "lucide-react";
import type { State } from "../lib/api";
import { Logo } from "../components/Shell";

const CARDS = [
  { icon: <Megaphone />, title: "Report", body: "Residents submit flood reports from any phone — severity, location and the road affected." },
  { icon: <ClipboardCheck />, title: "Verify", body: "A FIFO admin queue and a separate-chaining hash table store, triage and find every report." },
  { icon: <Compass />, title: "Route", body: "Dijkstra's algorithm on a binary min-heap finds the shortest open route around floods." },
  { icon: <LifeBuoy />, title: "Evacuate", body: "The advisor ranks shelters from wherever you are and steers you away from flooded ones." },
];

export default function Landing({ state, onEnter, onReport }: { state: State | null; onEnter: () => void; onReport: () => void }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useStormCanvas(canvas);

  return (
    <div className="landing">
      <canvas ref={canvas} className="landing-canvas" aria-hidden />
      <div className="landing-inner">
        <nav className="landing-nav">
          <Logo />
          <div className="landing-live">
            <Radio size={14} /> {state ? <>{state.stats.active} active reports · {state.stats.blockedRoads} roads closed</> : "Connecting…"}
          </div>
        </nav>

        <header className="hero">
          <span className="eyebrow"><Database size={14} /> Community flood intelligence</span>
          <h1>See the water.<br /><span className="grad">Find the way through.</span></h1>
          <p>FloodWatch turns community flood reports into verified road closures and the safest
            route across the city — updated live for everyone, the moment an admin verifies a report.</p>
          <div className="hero-cta">
            <button className="btn btn-primary btn-lg" onClick={onEnter}>Open Command Center <ArrowRight size={18} /></button>
            <button className="btn btn-glass btn-lg" onClick={onReport}>Report flooding near me</button>
          </div>
        </header>

        <div className="hero-cards">
          {CARDS.map((c, i) => (
            <article key={c.title} className="hero-card" style={{ animationDelay: `${0.15 + i * 0.1}s` }}>
              <div className="hero-card-icon">{c.icon}</div>
              <h3><span>{i + 1}</span>{c.title}</h3>
              <p>{c.body}</p>
            </article>
          ))}
        </div>

        <footer className="landing-foot">
          <span><i className="lg lg-route" />Open recommended route</span>
          <span><i className="lg lg-blocked" />Blocked road</span>
          <span><i className="lg lg-flood" />Reported flooding</span>
          <span className="muted">Simulation · all roads, reports and distances are demonstration data</span>
        </footer>
      </div>
    </div>
  );
}

/* Animated storm / network / skyline / tide background (port of the Tk splash). */
const NODES: [number, number][] = [[80, 330], [110, 110], [300, 220], [340, 70], [520, 120], [510, 280], [610, 350], [280, 380]];
const EDGES = [[0, 1], [1, 2], [0, 2], [2, 3], [3, 4], [2, 4], [4, 5], [2, 5], [5, 6], [2, 7], [0, 7], [7, 6]];
const BLOCKED = new Set(["0-2", "3-4"]);
const ROUTE = [0, 1, 2, 5, 6];

function useStormCanvas(ref: React.RefObject<HTMLCanvasElement>) {
  useEffect(() => {
    const cv = ref.current!;
    const ctx = cv.getContext("2d")!;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let w = 0, h = 0, raf = 0, t = 0;
    const drops = Array.from({ length: 140 }, () => [Math.random(), Math.random(), 0.004 + Math.random() * 0.008, 10 + Math.random() * 14]);
    let skyline: { x: number; w: number; h: number; win: [number, number][] }[] = [];

    const resize = () => {
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      w = cv.clientWidth; h = cv.clientHeight;
      cv.width = w * dpr; cv.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      // deterministic skyline
      let seed = 7; const rnd = () => ((seed = (seed * 9301 + 49297) % 233280) / 233280);
      skyline = []; let x = 0;
      while (x < w) {
        const bw = 34 + rnd() * 50, bh = 40 + rnd() * 110, win: [number, number][] = [];
        for (let wy = 10; wy < bh - 8; wy += 16) for (let wx = 7; wx < bw - 8; wx += 14) if (rnd() < 0.28) win.push([wx, wy]);
        skyline.push({ x, w: bw, h: bh, win }); x += bw + rnd() * 6;
      }
    };
    const pos = (i: number) => {
      const [x, y] = NODES[i];
      return [60 + ((x - 80) * (w - 120)) / 530, h * 0.12 + ((y - 70) * (h * 0.62)) / 310] as const;
    };

    const draw = () => {
      t += 1;
      const g = ctx.createLinearGradient(0, 0, 0, h);
      g.addColorStop(0, "#0d0f12"); g.addColorStop(1, "#2a2f36");
      ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);

      // network
      ctx.lineCap = "round";
      EDGES.forEach(([a, b]) => {
        const [ax, ay] = pos(a), [bx, by] = pos(b);
        const blocked = BLOCKED.has(`${a}-${b}`);
        ctx.setLineDash(blocked ? [6, 6] : []);
        ctx.strokeStyle = blocked ? "rgba(224,90,58,.55)" : "rgba(245,165,36,.18)";
        ctx.lineWidth = blocked ? 2 : 1.5;
        ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.stroke();
      });
      ctx.setLineDash([]);
      ctx.strokeStyle = "rgba(245,165,36,.45)"; ctx.lineWidth = 4;
      ctx.beginPath(); ROUTE.forEach((n, i) => { const [x, y] = pos(n); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }); ctx.stroke();
      NODES.forEach((_, i) => {
        const [x, y] = pos(i); const hot = i === 0 || i === 2 || i === 4;
        ctx.beginPath(); ctx.arc(x, y, 7, 0, Math.PI * 2);
        ctx.fillStyle = "#1b1f24"; ctx.fill();
        ctx.strokeStyle = hot ? "rgba(239,68,68,.8)" : "rgba(245,165,36,.6)"; ctx.lineWidth = 2; ctx.stroke();
      });
      // pulse on flooded node + traveller on route
      const [rx, ry] = pos(0); const r = 12 + 8 * Math.abs(Math.sin(t * 0.04));
      ctx.beginPath(); ctx.arc(rx, ry, r, 0, Math.PI * 2); ctx.strokeStyle = `rgba(239,68,68,${0.9 - r / 30})`; ctx.stroke();
      const pts = ROUTE.map(pos); const lens = pts.slice(1).map((p, i) => Math.hypot(p[0] - pts[i][0], p[1] - pts[i][1]));
      let d = (t * 2.2) % lens.reduce((s, x) => s + x, 0);
      for (let i = 0; i < lens.length; i++) {
        if (d <= lens[i]) {
          const f = d / lens[i], px = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f, py = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f;
          ctx.beginPath(); ctx.arc(px, py, 6, 0, Math.PI * 2); ctx.fillStyle = "#ffd38a"; ctx.shadowColor = "#f5a524"; ctx.shadowBlur = 18; ctx.fill(); ctx.shadowBlur = 0;
          break;
        }
        d -= lens[i];
      }

      // skyline
      const base = h * 0.95;
      skyline.forEach((b) => {
        ctx.fillStyle = "#15181c"; ctx.fillRect(b.x, base - b.h, b.w, b.h + 40);
        ctx.fillStyle = "rgba(242,197,92,.75)"; b.win.forEach(([wx, wy]) => ctx.fillRect(b.x + wx, base - b.h + wy, 4, 6));
      });

      // rain
      ctx.strokeStyle = "rgba(200,206,214,.35)"; ctx.lineWidth = 1;
      ctx.beginPath();
      drops.forEach((dr) => {
        if (!reduce) { dr[1] += dr[2]; if (dr[1] > 1) { dr[1] = 0; dr[0] = Math.random(); } }
        const x = dr[0] * w, y = dr[1] * h; ctx.moveTo(x, y); ctx.lineTo(x - 3, y + dr[3]);
      });
      ctx.stroke();

      // tide
      const level = h * 0.93 + 5 * Math.sin(t * 0.015);
      [[8, 0.035, "rgba(58,74,92,.85)", 0], [6, 0.05, "rgba(38,48,60,.95)", 14]].forEach(([amp, sp, col, off]) => {
        ctx.beginPath(); ctx.moveTo(0, h);
        for (let x = 0; x <= w + 12; x += 12) ctx.lineTo(x, level + (off as number) + (amp as number) * Math.sin(x * 0.02 + t * (sp as number)));
        ctx.lineTo(w, h); ctx.closePath(); ctx.fillStyle = col as string; ctx.fill();
      });

      if (!reduce) raf = requestAnimationFrame(draw);
    };

    resize(); draw();
    window.addEventListener("resize", resize);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", resize); };
  }, [ref]);
}
