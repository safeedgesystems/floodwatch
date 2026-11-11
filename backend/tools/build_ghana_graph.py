"""Build FloodWatch's Ghana road graph from an OpenStreetMap extract.

One-off data-preparation step (NOT part of the graded algorithms). It turns the
raw OSM file into a compact graph that our own HashTable / Dijkstra code loads.

    pip install osmium
    # download https://download.geofabrik.de/africa/ghana-latest.osm.pbf
    python tools/build_ghana_graph.py ghana-latest.osm.pbf app/data/ghana_graph.json.gz

What it does
  1. Keeps drivable national/regional/district roads (motorway … tertiary, links,
     unclassified). Residential side-streets are excluded to keep the graph small.
  2. Splits every road at junctions, so a graph VERTEX = junction / dead end and an
     EDGE = road segment between two junctions (length in metres from the
     haversine formula; its shape is kept for drawing on the map).
  3. Keeps only the largest connected component (routable everywhere).
  4. Collects searchable places (cities, towns, villages, suburbs) and landmarks
     (hospitals, schools, markets, police…) for location search, plus safe
     places (hospitals, police, fire stations) for the evacuation advisor.
"""
from __future__ import annotations

import gzip
import json
import math
import sys
import time
from collections import defaultdict

import osmium

ROAD_CLASSES = {
    "motorway": 1, "motorway_link": 1, "trunk": 2, "trunk_link": 2, "primary": 3, "primary_link": 3,
    "secondary": 4, "secondary_link": 4, "tertiary": 5, "tertiary_link": 5, "unclassified": 6,
}
PLACE_KINDS = {"city", "town", "village", "suburb", "neighbourhood", "quarter", "hamlet"}
POI_AMENITY = {"hospital", "clinic", "university", "college", "school", "marketplace", "police",
               "fire_station", "bus_station", "fuel"}
SHELTER_KINDS = {"hospital", "police", "fire_station"}
SIMPLIFY_M = 8.0          # Douglas-Peucker tolerance for drawn road shapes


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def simplify(points, tol_m):
    """Iterative Douglas-Peucker on (lat, lon) using a local metre projection."""
    if len(points) < 3:
        return points
    lat0 = math.radians(points[0][0])
    kx, ky = 111320 * math.cos(lat0), 110540
    xy = [(p[1] * kx, p[0] * ky) for p in points]
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        (ax, ay), (bx, by) = xy[a], xy[b]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy) or 1e-9
        best, idx = 0.0, -1
        for i in range(a + 1, b):
            d = abs(dy * (xy[i][0] - ax) - dx * (xy[i][1] - ay)) / norm
            if d > best:
                best, idx = d, i
        if best > tol_m:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(points, keep) if k]


class Collector(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.ways = []            # (class, name, [(osm_node_id, lat, lon), ...])
        self.places = []          # (name, kind, lat, lon)

    def _poi(self, tags, lat, lon):
        name = tags.get("name")
        if not name:
            return
        kind = None
        if tags.get("place") in PLACE_KINDS:
            kind = tags.get("place")
        elif tags.get("amenity") in POI_AMENITY:
            kind = tags.get("amenity")
        elif tags.get("shop") == "mall":
            kind = "mall"
        elif tags.get("aeroway") == "aerodrome":
            kind = "airport"
        if kind:
            self.places.append((name.strip(), kind, round(lat, 5), round(lon, 5)))

    def node(self, n):
        if n.tags and n.location.valid():
            self._poi(n.tags, n.location.lat, n.location.lon)

    def way(self, w):
        hw = w.tags.get("highway")
        try:
            pts = [(n.ref, n.location.lat, n.location.lon) for n in w.nodes if n.location.valid()]
        except osmium.InvalidLocationError:
            return
        if hw in ROAD_CLASSES and w.tags.get("area") != "yes" and len(pts) >= 2:
            name = w.tags.get("name") or w.tags.get("ref") or ""
            self.ways.append((ROAD_CLASSES[hw], name, pts))
        elif len(pts) >= 3 and ("amenity" in w.tags or "shop" in w.tags or "aeroway" in w.tags):
            lat = sum(p[1] for p in pts) / len(pts)
            lon = sum(p[2] for p in pts) / len(pts)
            self._poi(w.tags, lat, lon)


def main(src, dst):
    t0 = time.time()
    c = Collector()
    c.apply_file(src, locations=True)
    print(f"read {len(c.ways):,} road ways, {len(c.places):,} places/landmarks in {time.time()-t0:.0f}s")

    # A node is a junction if it is a way endpoint or is shared by 2+ ways / visits.
    uses = defaultdict(int)
    for _, _, pts in c.ways:
        for i, (nid, _, _) in enumerate(pts):
            uses[nid] += 2 if i in (0, len(pts) - 1) else 1
    junction = {nid for nid, u in uses.items() if u >= 2}

    node_index, nodes = {}, []
    def vid(nid, lat, lon):
        if nid not in node_index:
            node_index[nid] = len(nodes)
            nodes.append((round(lat, 6), round(lon, 6)))
        return node_index[nid]

    edges, names, name_idx = [], [""], {"": 0}
    seen = set()
    for cls, name, pts in c.ways:
        if name not in name_idx:
            name_idx[name] = len(names); names.append(name)
        seg = [pts[0]]
        for p in pts[1:]:
            seg.append(p)
            if p[0] in junction:
                a, b = vid(*seg[0]), vid(*seg[-1])
                if a != b:
                    length = sum(haversine_m(seg[i][1], seg[i][2], seg[i + 1][1], seg[i + 1][2])
                                 for i in range(len(seg) - 1))
                    key = (min(a, b), max(a, b), round(length))
                    if key not in seen:
                        seen.add(key)
                        shape = simplify([(q[1], q[2]) for q in seg], SIMPLIFY_M)
                        edges.append((a, b, round(length, 1), cls, name_idx[name], shape))
                seg = [p]

    # Largest connected component (iterative DFS).
    adj = defaultdict(list)
    for i, (a, b, *_rest) in enumerate(edges):
        adj[a].append(b); adj[b].append(a)
    comp, best = {}, []
    for s in range(len(nodes)):
        if s in comp:
            continue
        stack, members = [s], []
        comp[s] = s
        while stack:
            u = stack.pop(); members.append(u)
            for v in adj[u]:
                if v not in comp:
                    comp[v] = s; stack.append(v)
        if len(members) > len(best):
            best = members
    keep = set(best)
    remap = {old: new for new, old in enumerate(sorted(keep))}
    out_nodes = [nodes[i] for i in sorted(keep)]
    out_edges = []
    for a, b, length, cls, ni, shape in edges:
        if a in keep and b in keep:
            flat = [round(v, 5) for pt in shape for v in pt]
            out_edges.append([remap[a], remap[b], length, cls, ni, flat])

    # De-duplicate places by (name, kind) keeping first; split shelters.
    places, pseen = [], set()
    for name, kind, lat, lon in c.places:
        k = (name.lower(), kind, round(lat, 2), round(lon, 2))
        if k not in pseen:
            pseen.add(k); places.append([name, kind, lat, lon])
    shelters = [p for p in places if p[1] in SHELTER_KINDS]

    data = {"source": "© OpenStreetMap contributors (ODbL), Geofabrik Ghana extract",
            "built": time.strftime("%Y-%m-%d"), "nodes": out_nodes, "edges": out_edges,
            "names": names, "places": places, "shelters": shelters}
    with gzip.open(dst, "wt", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    total_km = sum(e[2] for e in out_edges) / 1000
    print(f"graph: {len(out_nodes):,} junctions, {len(out_edges):,} road segments, {total_km:,.0f} km "
          f"(largest component of {len(nodes):,}); {len(places):,} places, {len(shelters):,} shelters")
    print(f"wrote {dst} in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
