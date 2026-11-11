"""Ghana real-map mode.

Loads the real Ghana road network (built from OpenStreetMap by
tools/build_ghana_graph.py) into the SAME data structures and the SAME
Dijkstra used by the simulation:

  * graph.build_graph + graph.dijkstra       -> routing (unchanged)
  * structures.HashTable (polynomial hash)   -> spatial grid index ("spatial hashing")
  * structures.prefix_range (binary search)  -> place-name search

Flood model: every VERIFIED report with GPS coordinates becomes a circular
flood zone (radius by severity). Road segments passing through a zone are
added to the closed-road set that Dijkstra skips.
"""
from __future__ import annotations

import gzip
import json
import math
import time
from pathlib import Path
from typing import Iterable, Optional

from .graph import build_graph, dijkstra
from .structures import HashTable, prefix_range

DATA_FILE = Path(__file__).resolve().parent / "data" / "ghana_graph.json.gz"
GHANA_BOUNDS = (4.5, -3.5, 11.5, 1.5)                 # lat_min, lon_min, lat_max, lon_max
ZONE_RADIUS_M = {"High": 400, "Medium": 200, "Low": 80}
AVG_SPEED_KMH = 30                                    # evacuation ETA (flood conditions, like simulation)
CLASS_SPEED_KMH = {1: 80, 2: 70, 3: 55, 4: 45, 5: 35, 6: 30}   # typical speeds for route ETA
CELL_DEG = 0.02                                       # spatial grid cell ≈ 2.2 km
ROAD_CLASS = {1: "Motorway", 2: "Trunk road", 3: "Primary road", 4: "Secondary road",
              5: "Tertiary road", 6: "Rural road"}
KIND_RANK = {"city": 0, "town": 1, "suburb": 2, "hospital": 3, "university": 3, "airport": 3,
             "village": 4, "neighbourhood": 4, "quarter": 4, "marketplace": 5, "mall": 5,
             "bus_station": 5, "police": 6, "fire_station": 6, "college": 6, "clinic": 6,
             "school": 7, "fuel": 8, "hamlet": 8}


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def point_segment_m(lat, lon, a_lat, a_lon, b_lat, b_lon) -> float:
    """Distance (m) from a point to a short segment, local flat-earth projection."""
    kx, ky = 111320 * math.cos(math.radians(lat)), 110540
    px, py = 0.0, 0.0
    ax, ay = (a_lon - lon) * kx, (a_lat - lat) * ky
    bx, by = (b_lon - lon) * kx, (b_lat - lat) * ky
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(ax + t * dx, ay + t * dy)


def in_ghana(lat: float, lon: float) -> bool:
    a, b, c, d = GHANA_BOUNDS
    return a <= lat <= c and b <= lon <= d


def _cell(lat: float, lon: float) -> tuple[int, int]:
    return int(math.floor(lat / CELL_DEG)), int(math.floor(lon / CELL_DEG))


def _key(r: int, c: int) -> str:
    return f"{r}:{c}"


class GeoNetwork:
    def __init__(self, path: Path = DATA_FILE) -> None:
        t0 = time.perf_counter()
        with gzip.open(path, "rt", encoding="utf-8") as f:
            d = json.load(f)
        self.source = d["source"]
        self.nodes: list[tuple[float, float]] = [tuple(n) for n in d["nodes"]]
        self.names: list[str] = d["names"]
        self.edges = d["edges"]                       # [a, b, metres, class, name_idx, flat shape]
        # Same graph structure as the simulation: vertex "n<i>", road "e<i>", weight in km.
        self.graph = build_graph(
            ({"id": f"n{i}"} for i in range(len(self.nodes))),
            ({"id": f"e{i}", "a": f"n{e[0]}", "b": f"n{e[1]}", "km": e[2] / 1000} for i, e in enumerate(self.edges)),
        )
        # ---- spatial hashing: grid cell key -> node ids / edge ids, stored in OUR HashTable
        self.node_grid = HashTable(16381, hash_fn="poly")
        self.edge_grid = HashTable(16381, hash_fn="poly")
        for i, (lat, lon) in enumerate(self.nodes):
            self._grid_add(self.node_grid, _cell(lat, lon), i)
        for i, e in enumerate(self.edges):
            shape = e[5]
            cells = set()
            for j in range(0, len(shape) - 2, 2):
                (r1, c1), (r2, c2) = _cell(shape[j], shape[j + 1]), _cell(shape[j + 2], shape[j + 3])
                for r in range(min(r1, r2), max(r1, r2) + 1):
                    for c in range(min(c1, c2), max(c1, c2) + 1):
                        cells.add((r, c))
            for rc in cells:
                self._grid_add(self.edge_grid, rc, i)
        # ---- places: sorted search keys for binary-search prefix lookup
        self.places = d["places"]                     # [name, kind, lat, lon]
        self.shelters = d["shelters"]
        keys = []
        for idx, (name, *_rest) in enumerate(self.places):
            words = name.lower().replace(",", " ").split()
            for w in range(len(words)):
                keys.append((" ".join(words[w:]), idx))   # every word can start a match
        keys.sort()
        self.search_keys = [k for k, _ in keys]
        self.search_ids = [i for _, i in keys]
        self.place_grid = HashTable(8191, hash_fn="poly")
        for idx, p in enumerate(self.places):
            if p[1] in ("city", "town", "village", "suburb", "neighbourhood", "quarter", "hamlet"):
                self._grid_add(self.place_grid, _cell(p[2], p[3]), idx)
        self.load_ms = round((time.perf_counter() - t0) * 1000)

    @staticmethod
    def _grid_add(table: HashTable, rc: tuple[int, int], item: int) -> None:
        key = _key(*rc)
        bucket = table.get_value(key)
        if bucket is None:
            table.put(key, [item])
        else:
            bucket.append(item)

    def _ring(self, table: HashTable, lat: float, lon: float, k: int) -> Iterable[int]:
        r0, c0 = _cell(lat, lon)
        for r in range(r0 - k, r0 + k + 1):
            for c in range(c0 - k, c0 + k + 1):
                if max(abs(r - r0), abs(c - c0)) == k:
                    yield from table.get_value(_key(r, c), [])

    def offline_layer_gz(self) -> bytes:
        """Every road shape + city/town labels, gzip-compressed once. Lets the UI draw
        a real Ghana base map with NO internet (classroom Wi-Fi fallback)."""
        if not hasattr(self, "_offline_gz"):
            towns = [[p[0], p[1], p[2], p[3]] for p in self.places if p[1] in ("city", "town")]
            body = {"roads": [[e[3], e[5]] for e in self.edges], "towns": towns}
            self._offline_gz = gzip.compress(json.dumps(body, separators=(",", ":")).encode(), 6)
        return self._offline_gz

    # ------------------------------------------------------------------ basics
    def info(self) -> dict:
        return {"junctions": len(self.nodes), "segments": len(self.edges),
                "roadKm": round(sum(e[2] for e in self.edges) / 1000),
                "places": len(self.places), "shelters": len(self.shelters),
                "bounds": GHANA_BOUNDS, "source": self.source, "loadMs": self.load_ms,
                "spatialIndex": self.node_grid.stats()}

    def nearest_node(self, lat: float, lon: float, exclude: set[int] = frozenset(),
                     max_rings: int = 25) -> Optional[int]:
        """Grid search outward ring by ring until the best candidate can't be beaten."""
        best, best_d = None, math.inf
        for k in range(max_rings + 1):
            for i in self._ring(self.node_grid, lat, lon, k):
                if i in exclude:
                    continue
                d = haversine_m(lat, lon, *self.nodes[i])
                if d < best_d:
                    best, best_d = i, d
            if best is not None and best_d < k * CELL_DEG * 100000:
                break
        return best

    def nearest_place(self, lat: float, lon: float) -> Optional[dict]:
        best, best_d = None, math.inf
        for k in range(6):
            for i in self._ring(self.place_grid, lat, lon, k):
                p = self.places[i]
                d = haversine_m(lat, lon, p[2], p[3])
                if d < best_d:
                    best, best_d = p, d
            if best is not None and best_d < k * CELL_DEG * 100000:
                break
        if not best:
            return None
        return {"name": best[0], "kind": best[1], "lat": best[2], "lon": best[3], "distanceM": round(best_d)}

    def search(self, q: str, limit: int = 8) -> list[dict]:
        words = q.lower().replace(",", " ").split()
        if not words:
            return []
        start, end = prefix_range(self.search_keys, " ".join(words))   # binary search
        seen, hits = set(), []
        for pos in range(start, min(end, start + 4000)):
            idx = self.search_ids[pos]
            if idx in seen:
                continue
            seen.add(idx)
            hits.append(idx)
        def rank(i):
            name, kind = self.places[i][0], self.places[i][1]
            return (name.lower() != q.lower().strip(), not name.lower().startswith(words[0]),
                    KIND_RANK.get(kind, 9), len(name))
        hits.sort(key=rank)
        out = []
        for i in hits[:limit]:
            name, kind, lat, lon = self.places[i]
            near = self.nearest_place(lat, lon) if kind not in ("city", "town") else None
            area = near["name"] if near and near["name"] != name else None
            out.append({"name": name, "kind": kind, "lat": lat, "lon": lon, "area": area})
        return out

    # ------------------------------------------------------------------ floods
    def flood_state(self, reports: Iterable[dict]) -> dict:
        """Verified GPS reports -> zones -> closed road segments."""
        zones, pending = [], []
        for r in reports:
            if r.get("lat") is None or r["status"] == "Resolved":
                continue
            z = {"id": r["id"], "lat": r["lat"], "lon": r["lon"], "severity": r["severity"],
                 "radius": ZONE_RADIUS_M[r["severity"]], "location": r["location"], "status": r["status"]}
            (zones if r["status"] == "Verified" else pending).append(z)
        closed: set[int] = set()
        for z in zones:
            reach = math.ceil(z["radius"] / (CELL_DEG * 110000)) + 1
            cand = set()
            for k in range(reach + 1):
                cand.update(self._ring(self.edge_grid, z["lat"], z["lon"], k))
            for i in cand:
                s = self.edges[i][5]
                for j in range(0, len(s) - 2, 2):
                    if point_segment_m(z["lat"], z["lon"], s[j], s[j + 1], s[j + 2], s[j + 3]) <= z["radius"]:
                        closed.add(i)
                        break
        return {"zones": zones, "pending": pending, "closed": closed}

    def _zone_of(self, lat: float, lon: float, zones: list[dict]) -> Optional[dict]:
        for z in zones:
            if haversine_m(lat, lon, z["lat"], z["lon"]) <= z["radius"]:
                return z
        return None

    # ------------------------------------------------------------------ routing
    def _path_geometry(self, roads: list[str], path: list[str]) -> tuple[list, list, float]:
        """Expand Dijkstra's road list into map coordinates, readable steps and drive time."""
        coords, raw, minutes = [], [], 0.0
        for rid, a in zip(roads, path):
            e = self.edges[int(rid[1:])]
            s = e[5]
            pts = [[s[j], s[j + 1]] for j in range(0, len(s), 2)]
            if int(a[1:]) != e[0]:
                pts.reverse()
            coords.extend(pts if not coords else pts[1:])
            minutes += e[2] / 1000 / CLASS_SPEED_KMH[e[3]] * 60
            raw.append({"name": self.names[e[4]] or ROAD_CLASS[e[3]], "km": e[2] / 1000, "class": ROAD_CLASS[e[3]]})
        steps = []
        for st in raw:                      # merge consecutive pieces of the same road
            if steps and (steps[-1]["name"] == st["name"] or st["km"] < 0.05):
                steps[-1]["km"] += st["km"]
            else:
                steps.append(dict(st))
        for st in steps:
            st["km"] = round(st["km"], 1)
        return coords, steps, minutes

    def _run(self, s: int, t: int, blocked: set[str]) -> dict:
        return dijkstra(self.graph, blocked, f"n{s}", f"n{t}")

    def route(self, a: tuple[float, float], b: tuple[float, float], flood: dict) -> dict:
        zones = flood["zones"]
        blocked = {f"e{i}" for i in flood["closed"]}
        warnings = []
        start_zone = self._zone_of(*a, zones)
        if start_zone:
            # Let people escape: roads inside the zone they're standing in stay usable.
            escape = self.flood_state([{**start_zone, "status": "Verified"}])["closed"]
            blocked -= {f"e{i}" for i in escape}
            warnings.append(f"You are inside the {start_zone['severity'].lower()}-severity flood zone at "
                            f"{start_zone['location']}. Leave carefully; the route exits the zone first.")
        s = self.nearest_node(*a)
        dest_zone = self._zone_of(*b, zones)
        target_latlon, safe_point = b, None
        if dest_zone:
            # Destination is flooded: aim for the nearest junction just outside the zone.
            bad = set()
            for _ in range(40):
                cand = self.nearest_node(*b, exclude=bad)
                if cand is None:
                    break
                lat, lon = self.nodes[cand]
                if not self._zone_of(lat, lon, zones):
                    target_latlon, safe_point = (lat, lon), cand
                    break
                bad.add(cand)
            warnings.append(f"Your destination is inside a verified {dest_zone['severity'].lower()}-severity "
                            f"flood zone ({dest_zone['location']}, {dest_zone['radius']} m radius). "
                            f"Routing you to the nearest safe point outside it.")
        t = safe_point if safe_point is not None else self.nearest_node(*target_latlon)
        t0 = time.perf_counter()
        res = self._run(s, t, blocked)
        ms = round((time.perf_counter() - t0) * 1000, 1)
        base = {"from": {"lat": a[0], "lon": a[1], "snap": self.nodes[s], "snapM": round(haversine_m(*a, *self.nodes[s]))},
                "to": {"lat": b[0], "lon": b[1], "snap": self.nodes[t], "snapM": round(haversine_m(*b, *self.nodes[t]))},
                "destinationFlooded": bool(dest_zone), "safePoint": self.nodes[t] if dest_zone else None,
                "warnings": warnings, "closedSegments": len(blocked),
                "algorithm": {"settled": len(res["trace"]["settled"]), "relaxations": len(res["trace"]["relaxations"]),
                              "heap": res["trace"]["heap"], "blockedSkipped": len(res["trace"]["blockedSkipped"]),
                              "ms": ms, "graphNodes": len(self.nodes), "graphEdges": len(self.edges)}}
        if not res["found"]:
            return {**base, "found": False, "coords": [], "steps": [], "distance": None, "eta": None,
                    "roads": []}
        coords, steps, minutes = self._path_geometry(res["roads"], res["path"])
        km = round(res["distance"], 1)
        return {**base, "found": True, "coords": coords, "steps": steps, "distance": km,
                "eta": max(1, round(minutes)), "roads": res["roads"]}

    def evacuate(self, a: tuple[float, float], flood: dict, k: int = 6) -> dict:
        zones = flood["zones"]
        blocked = {f"e{i}" for i in flood["closed"]}
        start_zone = self._zone_of(*a, zones)
        if start_zone:
            blocked -= {f"e{i}" for i in self.flood_state([{**start_zone, "status": "Verified"}])["closed"]}
        s = self.nearest_node(*a)
        near = sorted(self.shelters, key=lambda p: haversine_m(*a, p[2], p[3]))[:k * 2]
        options = []
        for name, kind, lat, lon in near:
            flooded = self._zone_of(lat, lon, zones) is not None
            t = self.nearest_node(lat, lon)
            res = self._run(s, t, blocked)
            opt = {"name": name, "kind": kind, "lat": lat, "lon": lon, "flooded": flooded,
                   "found": res["found"], "distance": round(res["distance"], 1) if res["found"] else None,
                   "straightKm": round(haversine_m(*a, lat, lon) / 1000, 1)}
            if res["found"]:
                opt["eta"] = max(1, round(opt["distance"] / AVG_SPEED_KMH * 60))
                opt["coords"], _, _ = self._path_geometry(res["roads"], res["path"])
            options.append(opt)
        options.sort(key=lambda o: (not o["found"], o["flooded"], o["distance"] or 0))
        options = options[:k]
        best = next((o for o in options if o["found"] and not o["flooded"]), None)
        for o in options:
            o["state"] = ("Cut off" if not o["found"] else "Recommended" if o is best
                          else "Flooded – avoid" if o["flooded"] else "Available")
            if o is not best:
                o.pop("coords", None)
        advice = (f"Head to {best['name']} ({best['kind'].replace('_', ' ')}) — {best['distance']} km, about {best['eta']} min."
                  if best else "No safe place is reachable on open roads. Move to higher ground and call 112.")
        return {"inFloodZone": bool(start_zone), "advice": advice, "options": options}
