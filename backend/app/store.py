"""SQLite persistence (write-through). The in-memory engine is the source of
truth at runtime; SQLite makes state survive restarts. Stdlib only."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS locations (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, x REAL NOT NULL, y REAL NOT NULL,
    shelter TEXT, custom INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS roads (
    id TEXT PRIMARY KEY, a TEXT NOT NULL REFERENCES locations(id),
    b TEXT NOT NULL REFERENCES locations(id), km REAL NOT NULL CHECK (km > 0),
    manual_block INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY, location TEXT NOT NULL, loc_id TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('High','Medium','Low')),
    status TEXT NOT NULL CHECK (status IN ('Reported','Verified','Resolved')),
    road_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    queue_seq INTEGER, lat REAL, lon REAL
);
CREATE INDEX IF NOT EXISTS ix_reports_queue ON reports(queue_seq) WHERE queue_seq IS NOT NULL;
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, kind TEXT NOT NULL,
    message TEXT NOT NULL, ref TEXT
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


class Store:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)
            # migration for databases created before the Ghana map (adds GPS columns)
            cols = {r[1] for r in self._conn.execute("PRAGMA table_info(reports)")}
            for col in ("lat", "lon"):
                if col not in cols:
                    self._conn.execute(f"ALTER TABLE reports ADD COLUMN {col} REAL")
            self._conn.commit()

    # -- generic helpers ------------------------------------------------------
    def execute(self, sql: str, params: tuple | dict = ()) -> None:
        with self._lock, self._conn:
            self._conn.execute(sql, params)

    def executemany(self, sql: str, rows: list) -> None:
        with self._lock, self._conn:
            self._conn.executemany(sql, rows)

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    # -- meta -----------------------------------------------------------------
    def get_meta(self, key: str, default: Any = None) -> Any:
        rows = self.query("SELECT value FROM meta WHERE key=?", (key,))
        return json.loads(rows[0]["value"]) if rows else default

    def set_meta(self, key: str, value: Any) -> None:
        self.execute("INSERT INTO meta(key,value) VALUES(?,?) "
                     "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                     (key, json.dumps(value)))

    def is_empty(self) -> bool:
        return not self.query("SELECT 1 FROM locations LIMIT 1")

    # -- entities -------------------------------------------------------------
    def upsert_location(self, loc: dict) -> None:
        self.execute(
            "INSERT INTO locations(id,name,x,y,shelter,custom) VALUES(:id,:name,:x,:y,:shelter,:custom) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name,x=excluded.x,y=excluded.y,"
            "shelter=excluded.shelter,custom=excluded.custom",
            {**loc, "custom": int(loc.get("custom", False))})

    def upsert_road(self, road: dict) -> None:
        self.execute(
            "INSERT INTO roads(id,a,b,km,manual_block) VALUES(:id,:a,:b,:km,:manual) "
            "ON CONFLICT(id) DO UPDATE SET km=excluded.km,manual_block=excluded.manual_block",
            {**road, "manual": int(road.get("manual", False))})

    def upsert_report(self, r: dict, queue_seq: Optional[int]) -> None:
        self.execute(
            "INSERT INTO reports(id,location,loc_id,description,severity,status,road_id,"
            "created_at,updated_at,queue_seq,lat,lon) VALUES(:id,:location,:locId,:description,"
            ":severity,:status,:roadId,:createdAt,:updatedAt,:seq,:lat,:lon) "
            "ON CONFLICT(id) DO UPDATE SET status=excluded.status,updated_at=excluded.updated_at,"
            "queue_seq=excluded.queue_seq",
            {"lat": None, "lon": None, **r, "seq": queue_seq})

    def delete_report(self, report_id: str) -> None:
        self.execute("DELETE FROM reports WHERE id=?", (report_id,))

    def add_event(self, ev: dict) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO events(ts,kind,message,ref) VALUES(?,?,?,?)",
                (ev["ts"], ev["kind"], ev["message"], ev.get("ref")))
            # keep the log bounded
            self._conn.execute("DELETE FROM events WHERE id <= ?", (cur.lastrowid - 500,))
            return cur.lastrowid

    def wipe(self) -> None:
        with self._lock, self._conn:
            for t in ("reports", "roads", "locations", "events", "meta"):
                self._conn.execute(f"DELETE FROM {t}")
