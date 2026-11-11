// Live state over WebSocket with automatic reconnect + HTTP fallback.
import { useEffect, useRef, useState } from "react";
import { api, State } from "./api";

export type Conn = "connecting" | "live" | "offline";

export function useLiveState() {
  const [state, setState] = useState<State | null>(null);
  const [conn, setConn] = useState<Conn>("connecting");
  const retry = useRef(0);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let ping: number | undefined;
    let reconnect: number | undefined;
    let closed = false;

    // Seed immediately over HTTP so first paint doesn't wait on the socket.
    api.state().then(setState).catch(() => setConn("offline"));

    const open = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/ws`);
      ws.onopen = () => {
        retry.current = 0;
        setConn("live");
        ping = window.setInterval(() => ws?.readyState === 1 && ws.send("ping"), 30000);
      };
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.type === "state") setState(msg.data);
      };
      ws.onclose = () => {
        window.clearInterval(ping);
        if (closed) return;
        setConn("offline");
        // exponential backoff capped at 10s
        const delay = Math.min(10000, 500 * 2 ** retry.current++);
        reconnect = window.setTimeout(open, delay);
      };
      ws.onerror = () => ws?.close();
    };
    open();

    return () => {
      closed = true;
      window.clearInterval(ping);
      window.clearTimeout(reconnect);
      ws?.close();
    };
  }, []);

  return { state, conn, setState };
}
