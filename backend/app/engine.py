"""FloodWatch domain engine.

Owns the runtime state (hash table of reports, FIFO verification queue,
road graph) and keeps SQLite in sync. All public methods are thread-safe
and return plain dicts ready for JSON.
"""
from __future__ import annotations

import math
import random
import threading
from datetime import datetime, timezone
from typing import Optional

from .graph import build_graph, connectivity, dijkstra, eta_minutes
from .seed import SEED_LOCATIONS, SEED_REPORTS, SEED_ROADS, SEED_MANUAL_BLOCKS
from .store import Store
from .structures import FIFOQueue, HashTable

SEVERITIES = ("High", "Medium", "Low")
STATUSES = ("Reported", "Verified", "Resolved")
SEV_RANK = {"High": 0, "Medium": 1, "Low": 2}
RISK_WEIGHT = {"High": 3, "Medium": 2, "Low": 1}
MAP_BOUNDS = (40, 40, 680, 420)          # x1, y1, x2, y2 of the map canvas
PX_PER_KM = 85.0


class DomainError(Exception):
    """Business rule violation -> HTTP 4xx."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def risk_label(score: int) -> str:
    if score == 0:
        return "Safe"
    if score <= 2:
        return "Watch"
    if score <= 4:
        return "Warning"
    return "Danger"


class FloodWatchEngine:
    def __init__(self, store: Store) -> None:
        self.store = store
        self._lock = threading.RLock()
        self.version = 0
        self.table = HashTable(8)
        self.queue: FIFOQueue[str] = FIFOQueue()
        self.locations: dict[str, dict] = {}
        self.roads: dict[str, dict] = {}
        self.graph: dict = {}
        self.blocked: set[str] = set()
        self.next_num = 1
        self.last_route_trace: Optional[dict] = None
        self._queue_seq = 0
        self.geo = None                 # GeoNetwork, attached by main.py when map data exists
        self._flood_cache: tuple[int, dict] | None = None
        if store.is_empty():
            self._seed()
        else:
            self._load()

    # ======================================================================
    # Bootstrapping
    # ======================================================================
    def _seed(self) -> None:
        with self._lock:
            self.store.wipe()
            self.table = HashTable(8)
            self.queue.clear()
            self.locations, self.roads = {}, {}
            self.next_num, self._queue_seq = 1, 0
            for loc in SEED_LOCATIONS:
                self._add_location({**loc, "custom": False})
            for road in SEED_ROADS:
                self._add_road({**road, "manual": road["id"] in SEED_MANUAL_BLOCKS})
            self._rebuild_graph()
            for r in SEED_REPORTS:
                self._create_report(r["location"], r["description"], r["severity"],
                                    loc_id=r["locId"], road_id=r["roadId"], log=False)
            self.store.set_meta("bucket_size", self.table.size)
            self._log("system", "Demo network loaded with 3 sample reports")
            self._sync_blocked()

    def _load(self) -> None:
        with self._lock:
            for row in self.store.query("SELECT * FROM locations"):
                self.locations[row["id"]] = {"id": row["id"], "name": row["name"],
                                             "x": row["x"], "y": row["y"],
                                             "shelter": row["shelter"],
                                             "custom": bool(row["custom"])}
            for row in self.store.query("SELECT * FROM roads"):
                self.roads[row["id"]] = {"id": row["id"], "a": row["a"], "b": row["b"],
                                         "km": row["km"], "manual": bool(row["manual_block"])}
            self.table = HashTable(self.store.get_meta("bucket_size", 8))
            for row in self.store.query("SELECT * FROM reports"):
                self.table.put(row["id"], {
                    "id": row["id"], "location": row["location"], "locId": row["loc_id"],
                    "description": row["description"], "severity": row["severity"],
                    "status": row["status"], "roadId": row["road_id"],
                    "createdAt": row["created_at"], "updatedAt": row["updated_at"],
                    "lat": row["lat"], "lon": row["lon"]})
            for row in self.store.query(
                    "SELECT id, queue_seq FROM reports WHERE queue_seq IS NOT NULL ORDER BY queue_seq"):
                self.queue.enqueue(row["id"])
                self.table.get(row["id"])["value"]["_seq"] = row["queue_seq"]
                self._queue_seq = max(self._queue_seq, row["queue_seq"])
            self.next_num = self.store.get_meta("next_num", 1)
            self._rebuild_graph()
            self._sync_blocked()

    def reset_demo(self) -> dict:
        with self._lock:
            self._seed()
            return self._bump()

    # ======================================================================
    # Internal helpers (caller holds the lock)
    # ======================================================================
    def _bump(self) -> dict:
        self.version += 1
        return {"version": self.version}

    def _log(self, kind: str, message: str, ref: Optional[str] = None) -> None:
        self.store.add_event({"ts": _now(), "kind": kind, "message": message, "ref": ref})

    def _rebuild_graph(self) -> None:
        self.graph = build_graph(self.locations.values(), self.roads.values())

    def _add_location(self, loc: dict) -> None:
        self.locations[loc["id"]] = loc
        self.store.upsert_location(loc)

    def _add_road(self, road: dict) -> None:
        self.roads[road["id"]] = road
        self.store.upsert_road(road)

    def _sync_blocked(self) -> None:
        """Blocked = manual closures ∪ roads named by Verified reports."""
        by_report = {r["roadId"] for r in self.table.values()
                     if r["status"] == "Verified" and r["roadId"]}
        manual = {rid for rid, r in self.roads.items() if r["manual"]}
        self.blocked = manual | by_report

    def _persist_report(self, rec: dict) -> None:
        seq = None
        if rec["id"] in self.queue:
            seq = rec.get("_seq")
        self.store.upsert_report({k: v for k, v in rec.items() if not k.startswith("_")}, seq)

    def _enqueue(self, rec: dict) -> None:
        if rec["id"] not in self.queue:
            self._queue_seq += 1
            rec["_seq"] = self._queue_seq
            self.queue.enqueue(rec["id"])

    def _resolve_location(self, name: str, x: Optional[float], y: Optional[float]) -> str:
        """Match an existing location by name/id, else create a custom node."""
        clean = name.strip()
        for loc in self.locations.values():
            if clean.lower() in (loc["name"].lower(), loc["id"].lower()):
                return loc["id"]
        return self._create_custom_location(clean, x, y)

    def _create_custom_location(self, name: str, x: Optional[float], y: Optional[float]) -> str:
        if len(self.locations) >= 40:
            raise DomainError("Map is full (40 locations). Use an existing location.")
        # ID from initials, made unique.
        base = "".join(w[0] for w in name.split() if w[0].isalnum())[:3].upper() or "X"
        new_id, n = base, 2
        while new_id in self.locations:
            new_id, n = f"{base}{n}", n + 1

        x1, y1, x2, y2 = MAP_BOUNDS
        if x is None or y is None:
            # Deterministic placement maximising distance from existing nodes
            # (the original placed nodes at random and could overlap labels).
            rng = random.Random(name.lower())
            best, best_gap = (0.0, 0.0), -1.0
            for _ in range(80):
                cx, cy = rng.uniform(x1 + 80, x2 - 80), rng.uniform(y1 + 50, y2 - 50)
                gap = min(math.hypot(cx - l["x"], cy - l["y"]) for l in self.locations.values())
                if gap > best_gap:
                    best, best_gap = (cx, cy), gap
            x, y = best
        x, y = round(min(max(x, x1), x2)), round(min(max(y, y1), y2))

        self._add_location({"id": new_id, "name": name, "x": x, "y": y,
                            "shelter": None, "custom": True})
        # Connect to the two nearest nodes so it isn't a dead end.
        nearest = sorted((l for l in self.locations.values() if l["id"] != new_id),
                         key=lambda l: math.hypot(l["x"] - x, l["y"] - y))[:2]
        for other in nearest:
            km = max(0.3, round(math.hypot(other["x"] - x, other["y"] - y) / PX_PER_KM, 1))
            self._add_road({"id": f"{other['id']}-{new_id}", "a": other["id"], "b": new_id,
                            "km": km, "manual": False})
        self._rebuild_graph()
        self._log("network", f"New location '{name}' ({new_id}) mapped and linked to "
                             f"{' & '.join(o['name'] for o in nearest)}", new_id)
        return new_id

    def _create_report(self, location: str, description: str, severity: str, *,
                       loc_id: Optional[str] = None, road_id: Optional[str] = None,
                       x: Optional[float] = None, y: Optional[float] = None,
                       lat: Optional[float] = None, lon: Optional[float] = None,
                       log: bool = True) -> dict:
        if severity not in SEVERITIES:
            raise DomainError("Invalid severity")
        if road_id and road_id not in self.roads:
            raise DomainError(f"Unknown road {road_id}")
        if lat is not None and lon is not None:
            # Ghana map report: positioned by GPS, not on the simulated network.
            from .geo import in_ghana
            if not in_ghana(lat, lon):
                raise DomainError("That location is outside Ghana")
            loc_id, road_id = "", None
        elif loc_id is None:
            loc_id = self._resolve_location(location, x, y)
        elif loc_id not in self.locations:
            raise DomainError(f"Unknown location {loc_id}")

        rid = f"FL{self.next_num:03d}"
        self.next_num += 1
        self.store.set_meta("next_num", self.next_num)
        ts = _now()
        rec = {"id": rid, "location": self.locations[loc_id]["name"] if loc_id else location.strip(),
               "locId": loc_id, "description": description.strip(), "severity": severity,
               "status": "Reported", "roadId": road_id, "createdAt": ts, "updatedAt": ts,
               "lat": round(lat, 6) if lat is not None else None,
               "lon": round(lon, 6) if lon is not None else None}
        self.table.put(rid, rec)
        self._enqueue(rec)
        self._persist_report(rec)
        if log:
            where = f"{rec['location']} (GPS)" if rec["lat"] is not None else rec["location"]
            self._log("report", f"{rid} · {severity} flooding reported at {where}", rid)
        return rec

    def _public(self, rec: dict) -> dict:
        return {k: v for k, v in rec.items() if not k.startswith("_")}

    def _get(self, report_id: str) -> dict:
        res = self.table.get(report_id.upper())
        if not res["found"]:
            raise DomainError(f"Report {report_id} not found", 404)
        return res["value"]

    # ======================================================================
    # Commands
    # ======================================================================
    def submit_report(self, location: str, description: str, severity: str,
                      road_id: Optional[str], x: Optional[float], y: Optional[float],
                      lat: Optional[float] = None, lon: Optional[float] = None) -> dict:
        with self._lock:
            rec = self._create_report(location, description, severity,
                                      road_id=road_id, x=x, y=y, lat=lat, lon=lon)
            self._bump()
            return self._public(rec)

    def process_next(self) -> dict:
        with self._lock:
            while True:
                rid = self.queue.dequeue()
                if rid is None:
                    raise DomainError("No reports are waiting for review", 409)
                res = self.table.get(rid)
                if res["found"]:
                    break                      # skip ids deleted meanwhile
            rec = res["value"]
            rec["status"], rec["updatedAt"] = "Verified", _now()
            self._persist_report(rec)
            self._sync_blocked()
            msg = (f"{rid} verified — road {rec['roadId']} closed in the network" if rec["roadId"]
                   else f"{rid} verified — flood zone active on the Ghana map, nearby roads closed"
                   if rec.get("lat") is not None
                   else f"{rid} verified — no road affected, routing unchanged")
            self._log("verify", msg, rid)
            self._bump()
            return {"report": self._public(rec), "message": msg}

    def set_status(self, report_id: str, status: str) -> dict:
        if status not in STATUSES:
            raise DomainError("Invalid status")
        with self._lock:
            rec = self._get(report_id)
            if rec["status"] == status:
                return self._public(rec)
            rec["status"], rec["updatedAt"] = status, _now()
            if status == "Reported":
                self._enqueue(rec)            # re-opened reports go back in the queue
            else:
                self.queue.remove(rec["id"])
            self._persist_report(rec)
            self._sync_blocked()
            self._log("status", f"{rec['id']} marked {status}", rec["id"])
            self._bump()
            return self._public(rec)

    def delete_report(self, report_id: str) -> None:
        with self._lock:
            rec = self._get(report_id)
            self.table.remove(rec["id"])
            self.queue.remove(rec["id"])
            self.store.delete_report(rec["id"])
            self._sync_blocked()
            self._log("delete", f"{rec['id']} deleted", rec["id"])
            self._bump()

    def clear_reports(self) -> int:
        with self._lock:
            n = self.table.count
            for rid in [r["id"] for r in self.table.values()]:
                self.store.delete_report(rid)
            self.table.clear()
            self.queue.clear()
            # IDs keep counting up so a cleared FL001 is never confused with a new one.
            self._sync_blocked()
            self._log("delete", f"All reports cleared ({n})")
            self._bump()
            return n

    def set_road_block(self, road_id: str, blocked: bool) -> dict:
        with self._lock:
            road = self.roads.get(road_id)
            if not road:
                raise DomainError(f"Road {road_id} not found", 404)
            road["manual"] = blocked
            self.store.upsert_road(road)
            self._sync_blocked()
            a, b = self.locations[road["a"]]["name"], self.locations[road["b"]]["name"]
            self._log("road", f"Road {road_id} ({a} — {b}) manually "
                              f"{'closed' if blocked else 'reopened'}", road_id)
            self._bump()
            return {"id": road_id, "manual": blocked, "blocked": road_id in self.blocked}

    def resize_hash(self, size: int) -> dict:
        if size not in HashTable.ALLOWED_SIZES:
            raise DomainError(f"Bucket size must be one of {HashTable.ALLOWED_SIZES}")
        with self._lock:
            self.table.resize(size)
            self.store.set_meta("bucket_size", size)
            self._log("system", f"Hash table rehashed to {size} buckets")
            self._bump()
            return self.table.stats()

    # ======================================================================
    # Ghana map (real roads) - same Dijkstra, closures come from GPS reports
    # ======================================================================
    def _geo(self):
        if not self.geo:
            raise DomainError("Ghana map data is not installed on this server", 503)
        return self.geo

    def geo_flood(self) -> dict:
        with self._lock:
            if self._flood_cache and self._flood_cache[0] == self.version:
                return self._flood_cache[1]
            state = self._geo().flood_state(self.table.values())
            self._flood_cache = (self.version, state)
            return state

    def geo_route(self, a: tuple[float, float], b: tuple[float, float]) -> dict:
        flood = self.geo_flood()
        res = self._geo().route(a, b, flood)
        with self._lock:
            self.last_route_trace = {"from": "GPS", "to": "GPS", "settled": [],
                                     "relaxations": [], "blockedSkipped": [],
                                     "heap": res["algorithm"]["heap"],
                                     "settledCount": res["algorithm"]["settled"], "real": True}
        return res

    def geo_evacuate(self, a: tuple[float, float]) -> dict:
        return self._geo().evacuate(a, self.geo_flood())

    def geo_layer(self) -> dict:
        """Zones + closed road shapes for drawing on the map."""
        if not self.geo:
            return {"enabled": False}
        f = self.geo_flood()
        edges = self.geo.edges
        closed = [[[e[5][j], e[5][j + 1]] for j in range(0, len(e[5]), 2)]
                  for e in (edges[i] for i in sorted(f["closed"]))]
        return {"enabled": True, "zones": f["zones"], "pending": f["pending"],
                "closedSegments": closed}

    # ======================================================================
    # Queries
    # ======================================================================
    def lookup(self, key: str) -> dict:
        key = key.strip().upper()
        with self._lock:
            res = self.table.get(key)
            return {"key": key, "hashSum": HashTable.sum_key(key), "bucket": res["index"],
                    "size": self.table.size, "found": res["found"], "steps": res["steps"],
                    "visited": res["visited"],
                    "report": self._public(res["value"]) if res["found"] else None}

    def route(self, start: str, goal: str) -> dict:
        with self._lock:
            if start not in self.locations or goal not in self.locations:
                raise DomainError("Unknown location", 404)
            result = dijkstra(self.graph, self.blocked, start, goal)
            self.last_route_trace = {"from": start, "to": goal, **result["trace"]}
            return {"from": start, "to": goal, **result}

    def _location_risk(self, loc_id: str) -> int:
        score = sum(RISK_WEIGHT[r["severity"]] for r in self.table.values()
                    if r["status"] != "Resolved" and r["locId"] == loc_id)
        score += sum(1 for r in self.roads.values()
                     if loc_id in (r["a"], r["b"]) and r["id"] in self.blocked)
        return score

    def _has_high(self, loc_id: str) -> bool:
        return any(r["status"] != "Resolved" and r["locId"] == loc_id and r["severity"] == "High"
                   for r in self.table.values())

    def evacuate(self, start: str) -> dict:
        with self._lock:
            if start not in self.locations:
                raise DomainError("Unknown location", 404)
            options = []
            for sid, loc in self.locations.items():
                if not loc["shelter"]:
                    continue
                res = dijkstra(self.graph, self.blocked, start, sid)
                score = self._location_risk(sid)
                options.append({"id": sid, "name": loc["name"], "kind": loc["shelter"],
                                "found": res["found"], "distance": res["distance"],
                                "eta": res["eta"], "path": res["path"], "roads": res["roads"],
                                "flooded": self._has_high(sid), "riskScore": score,
                                "risk": risk_label(score)})
            options.sort(key=lambda o: (not o["found"], o["flooded"], o["distance"] or 0))
            best = next((o for o in options if o["found"] and not o["flooded"]), None)
            for o in options:
                o["state"] = ("Cut off" if not o["found"] else "Recommended" if o is best
                              else "Flooded – avoid" if o["flooded"] else "Available")
            score = self._location_risk(start)
            if best:
                advice = ("You are already at a shelter." if len(best["path"]) == 1 else
                          f"Head to {best['name']} — {best['distance']} km, about {best['eta']} min.")
            elif any(o["found"] for o in options):
                advice = ("Every reachable shelter reports severe flooding. Move to higher "
                          "ground and contact emergency services.")
            else:
                advice = ("No shelter can be reached on open roads. Stay on a high floor "
                          "and contact emergency services.")
            return {"from": start, "riskScore": score, "risk": risk_label(score),
                    "best": best["id"] if best else None, "advice": advice, "options": options}

    def snapshot(self) -> dict:
        with self._lock:
            reports = sorted((self._public(r) for r in self.table.values()),
                             key=lambda r: (r["status"] == "Resolved", SEV_RANK[r["severity"]], r["id"]))
            active = [r for r in reports if r["status"] != "Resolved"]

            loc_info: dict[str, dict] = {}
            for r in active:
                info = loc_info.setdefault(r["locId"], {"count": 0, "severity": r["severity"]})
                info["count"] += 1
                if SEV_RANK[r["severity"]] < SEV_RANK[info["severity"]]:
                    info["severity"] = r["severity"]

            locations = []
            for loc in self.locations.values():
                score = self._location_risk(loc["id"])
                info = loc_info.get(loc["id"])
                locations.append({**loc, "activeReports": info["count"] if info else 0,
                                  "severity": info["severity"] if info else None,
                                  "riskScore": score, "risk": risk_label(score)})

            verified_by_road: dict[str, list[str]] = {}
            for r in reports:
                if r["status"] == "Verified" and r["roadId"]:
                    verified_by_road.setdefault(r["roadId"], []).append(r["id"])
            roads = [{**road, "blocked": road["id"] in self.blocked,
                      "reportIds": verified_by_road.get(road["id"], [])}
                     for road in self.roads.values()]

            events = self.store.query("SELECT * FROM events ORDER BY id DESC LIMIT 40")
            shelters = [l["id"] for l in self.locations.values() if l["shelter"]]
            return {
                "version": self.version,
                "serverTime": _now(),
                "nextId": f"FL{self.next_num:03d}",
                "locations": locations,
                "roads": roads,
                "reports": reports,
                "queue": list(self.queue),
                "hash": {"stats": self.table.stats(), "allowedSizes": list(HashTable.ALLOWED_SIZES),
                         "buckets": self.table.layout(lambda v: {"severity": v["severity"],
                                                                 "status": v["status"]})},
                "stats": {
                    "total": len(reports), "active": len(active),
                    "high": sum(r["severity"] == "High" for r in active),
                    "medium": sum(r["severity"] == "Medium" for r in active),
                    "low": sum(r["severity"] == "Low" for r in active),
                    "verified": sum(r["status"] == "Verified" for r in reports),
                    "resolved": sum(r["status"] == "Resolved" for r in reports),
                    "queue": len(self.queue), "blockedRoads": len(self.blocked),
                    "roads": len(self.roads), "locations": len(self.locations),
                    "shelters": len(shelters),
                    "connectivity": connectivity(self.graph, self.blocked),
                },
                "lastRouteTrace": self.last_route_trace,
                "geo": self.geo_layer(),
                "events": events,
                "etaSpeedKmh": 30,
            }


__all__ = ["FloodWatchEngine", "DomainError", "eta_minutes"]
