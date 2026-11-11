"""Road network graph + Dijkstra's shortest path (using our MinHeap)."""
from __future__ import annotations

import math
from typing import Iterable, Optional

from .structures import MinHeap

AVG_FLOOD_SPEED_KMH = 30  # ETA assumption for flooded conditions


def build_graph(locations: Iterable[dict], roads: Iterable[dict]) -> dict[str, list[dict]]:
    """Undirected adjacency list: node -> [{to, weight, road}]."""
    graph: dict[str, list[dict]] = {loc["id"]: [] for loc in locations}
    for r in roads:
        graph[r["a"]].append({"to": r["b"], "weight": r["km"], "road": r["id"]})
        graph[r["b"]].append({"to": r["a"], "weight": r["km"], "road": r["id"]})
    return graph


def eta_minutes(km: float) -> int:
    return max(1, round(km / AVG_FLOOD_SPEED_KMH * 60)) if km > 0 else 0


def dijkstra(graph: dict, blocked: set[str], start: str, goal: str) -> dict:
    """Shortest open path from start to goal.

    Returns a result dict that always contains the algorithm trace
    (settle order + relaxations + heap counters) so the UI can replay
    the search even when no route exists.
    """
    if start not in graph or goal not in graph:
        raise KeyError("Unknown location")

    dist = {n: math.inf for n in graph}
    prev: dict[str, str] = {}
    prev_road: dict[str, str] = {}
    settled: list[str] = []
    relaxations: list[dict] = []
    skipped_blocked: set[str] = set()

    dist[start] = 0.0
    heap = MinHeap()
    heap.push(0.0, start)

    while len(heap):
        d, node = heap.pop()
        if d > dist[node]:          # stale heap entry (lazy deletion)
            continue
        settled.append(node)
        if node == goal:
            break
        for edge in graph[node]:
            if edge["road"] in blocked:
                skipped_blocked.add(edge["road"])
                continue
            nd = d + edge["weight"]
            if nd < dist[edge["to"]]:
                dist[edge["to"]] = nd
                prev[edge["to"]] = node
                prev_road[edge["to"]] = edge["road"]
                heap.push(nd, edge["to"])
                relaxations.append({"from": node, "to": edge["to"],
                                    "road": edge["road"], "dist": round(nd, 2)})

    trace = {
        "settled": settled,
        "relaxations": relaxations,
        "blockedSkipped": sorted(skipped_blocked),
        "heap": {"pushes": heap.pushes, "pops": heap.pops, "peak": heap.peak},
    }

    if dist[goal] == math.inf:
        return {"found": False, "path": [], "roads": [], "distance": None,
                "eta": None, "trace": trace}

    path, roads, cur = [goal], [], goal
    while cur in prev:
        roads.insert(0, prev_road[cur])
        cur = prev[cur]
        path.insert(0, cur)

    km = round(dist[goal], 1)
    return {"found": True, "path": path, "roads": roads, "distance": km,
            "eta": eta_minutes(km), "trace": trace}


def connectivity(graph: dict, blocked: set[str]) -> float:
    """Share of node pairs still mutually reachable over open roads (0..1).
    Cheap BFS-based component count - a 'network health' KPI."""
    nodes = list(graph)
    n = len(nodes)
    if n < 2:
        return 1.0
    seen: set[str] = set()
    sizes: list[int] = []
    for s in nodes:
        if s in seen:
            continue
        stack, size = [s], 0
        seen.add(s)
        while stack:
            u = stack.pop()
            size += 1
            for e in graph[u]:
                if e["road"] not in blocked and e["to"] not in seen:
                    seen.add(e["to"])
                    stack.append(e["to"])
        sizes.append(size)
    reachable_pairs = sum(s * (s - 1) for s in sizes)
    return round(reachable_pairs / (n * (n - 1)), 3)
