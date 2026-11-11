import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import type { RiskLabel, Severity, Status } from "../lib/api";

/* ---------------------------------------------------------------- Toasts */
type ToastKind = "success" | "error" | "info";
interface Toast { id: number; kind: ToastKind; title: string; body?: string }
type ConfirmOpts = { title: string; body: string; confirm?: string; danger?: boolean };

interface UiCtx {
  toast: (kind: ToastKind, title: string, body?: string) => void;
  confirm: (opts: ConfirmOpts) => Promise<boolean>;
}
const Ctx = createContext<UiCtx>(null!);
export const useUi = () => useContext(Ctx);

export function UiProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [dialog, setDialog] = useState<(ConfirmOpts & { resolve: (v: boolean) => void }) | null>(null);
  const seq = useRef(0);

  const toast = useCallback((kind: ToastKind, title: string, body?: string) => {
    const id = ++seq.current;
    setToasts((t) => [...t.slice(-3), { id, kind, title, body }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "error" ? 6000 : 4000);
  }, []);

  const confirm = useCallback((opts: ConfirmOpts) =>
    new Promise<boolean>((resolve) => setDialog({ ...opts, resolve })), []);

  const close = (v: boolean) => { dialog?.resolve(v); setDialog(null); };

  const icons = { success: <CheckCircle2 size={18} />, error: <XCircle size={18} />, info: <Info size={18} /> };
  return (
    <Ctx.Provider value={{ toast, confirm }}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.kind}`}>
            {icons[t.kind]}
            <div><strong>{t.title}</strong>{t.body && <p>{t.body}</p>}</div>
            <button className="icon-btn" aria-label="Dismiss" onClick={() => setToasts((x) => x.filter((y) => y.id !== t.id))}><X size={14} /></button>
          </div>
        ))}
      </div>
      {dialog && (
        <Modal onClose={() => close(false)}>
          <div className="modal-icon" data-danger={dialog.danger}><AlertTriangle size={22} /></div>
          <h3>{dialog.title}</h3>
          <p className="muted">{dialog.body}</p>
          <div className="modal-actions">
            <button className="btn btn-ghost" onClick={() => close(false)}>Cancel</button>
            <button className={`btn ${dialog.danger ? "btn-danger" : "btn-primary"}`} autoFocus onClick={() => close(true)}>
              {dialog.confirm ?? "Confirm"}
            </button>
          </div>
        </Modal>
      )}
    </Ctx.Provider>
  );
}

export function Modal({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true">{children}</div>
    </div>
  );
}

/* --------------------------------------------------------------- Badges */
export const SevBadge = ({ s }: { s: Severity }) => <span className={`badge sev-${s.toLowerCase()}`}><i />{s}</span>;
export const StatusBadge = ({ s }: { s: Status }) => <span className={`badge st-${s.toLowerCase()}`}>{s}</span>;
export const RiskBadge = ({ r }: { r: RiskLabel }) => <span className={`badge risk-${r.toLowerCase()}`}>{r}</span>;

/* ---------------------------------------------------------------- Panel */
export function Panel({ title, icon, actions, children, className = "", pad = true }: {
  title?: ReactNode; icon?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; pad?: boolean;
}) {
  return (
    <section className={`panel ${className}`}>
      {(title || actions) && (
        <header className="panel-head">
          <h2>{icon}{title}</h2>
          <div className="panel-actions">{actions}</div>
        </header>
      )}
      <div className={pad ? "panel-body" : ""}>{children}</div>
    </section>
  );
}

export function Stat({ label, value, hint, tone = "default", icon }: {
  label: string; value: ReactNode; hint?: ReactNode; tone?: string; icon?: ReactNode;
}) {
  return (
    <div className={`stat tone-${tone}`}>
      <div className="stat-top"><span>{label}</span>{icon}</div>
      <div className="stat-value">{value}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  );
}

export function Empty({ icon, title, body }: { icon: ReactNode; title: string; body?: string }) {
  return <div className="empty">{icon}<strong>{title}</strong>{body && <p>{body}</p>}</div>;
}

export function timeAgo(iso: string) {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString();
}
