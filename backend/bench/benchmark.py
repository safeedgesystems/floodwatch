"""FloodWatch performance benchmarks (assignment Step 3: 'record ... performance observations').

Run from backend/:   python -m bench.benchmark
Outputs: ../docs/benchmarks/results.json + PNG charts, and prints markdown tables.
      python -m bench.benchmark --plot-only   redraws charts from the saved results.json

Experiments
  1. Dijkstra with our MinHeap vs a naive O(V^2) array-scan Dijkstra, on road-like
     sparse graphs (each node linked to its 3 nearest neighbours) from 50 to 5,000 nodes.
  2. Hash table: average probes per successful lookup for the project's
     char-sum hash vs a polynomial hash, across load factors.
  3. FIFO queue: our linked-list dequeue vs Python list.pop(0) when draining N items.
  4. End-to-end engine operations on the demo network (route, evacuate, submit, lookup).
"""
from __future__ import annotations

import json
import math
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from app.engine import FloodWatchEngine  # noqa: E402
from app.graph import build_graph, dijkstra  # noqa: E402
from app.store import Store  # noqa: E402
from app.structures import FIFOQueue, HashTable  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "docs" / "benchmarks"
OUT.mkdir(parents=True, exist_ok=True)
RNG = random.Random(2026)
plt.rcParams.update({"figure.dpi": 140, "font.size": 10, "axes.grid": True, "grid.alpha": .3})
AMBER, RED, GREEN, INK = "#D98A0B", "#EF4444", "#22C55E", "#4A525C"  # FloodWatch Graphite + Amber palette


def timeit(fn, repeat: int) -> float:
    """Median wall time in milliseconds."""
    samples = []
    for _ in range(repeat):
        t = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t) * 1000)
    return statistics.median(samples)


# ---------------------------------------------------------------- 1. Dijkstra
def road_graph(n: int):
    pts = [(RNG.random(), RNG.random()) for _ in range(n)]
    locs = [{"id": str(i)} for i in range(n)]
    roads, seen = [], set()
    for i, (x, y) in enumerate(pts):
        near = sorted(range(n), key=lambda j: (pts[j][0] - x) ** 2 + (pts[j][1] - y) ** 2)[1:4]
        for j in near:
            key = (min(i, j), max(i, j))
            if key not in seen:
                seen.add(key)
                km = round(math.dist(pts[i], pts[j]) * 50 + 0.1, 2)
                roads.append({"id": f"{key[0]}-{key[1]}", "a": str(key[0]), "b": str(key[1]), "km": km})
    return build_graph(locs, roads), len(roads)


def naive_dijkstra(graph, blocked, start):
    """Textbook O(V^2): linear scan for the closest unvisited node, no heap."""
    dist = {v: math.inf for v in graph}
    dist[start] = 0
    unvisited = set(graph)
    while unvisited:
        u = min(unvisited, key=dist.__getitem__)
        if dist[u] == math.inf:
            break
        unvisited.remove(u)
        for e in graph[u]:
            if e["road"] not in blocked and dist[u] + e["weight"] < dist[e["to"]]:
                dist[e["to"]] = dist[u] + e["weight"]
    return dist


def bench_dijkstra():
    rows = []
    for n in (50, 100, 250, 500, 1000, 2000, 5000):
        g, e = road_graph(n)
        nodes = list(g)
        # Worst case for a route query: the goal is the FARTHEST reachable node,
        # so both versions settle the whole network (fair like-for-like comparison).
        starts = [RNG.choice(nodes) for _ in range(5)]
        heap_t, naive_t = [], []
        for s in starts:
            d = naive_dijkstra(g, set(), s)
            far = max((v for v in d if d[v] < math.inf), key=d.__getitem__)
            heap_t.append(timeit(lambda s=s, far=far: dijkstra(g, set(), s, far), 3))
            naive_t.append(timeit(lambda s=s: naive_dijkstra(g, set(), s), 1))
        heap_ms, naive_ms = statistics.median(heap_t), statistics.median(naive_t)
        rows.append({"V": n, "E": e, "heap_ms": round(heap_ms, 3), "naive_ms": round(naive_ms, 3),
                     "speedup": round(naive_ms / heap_ms, 1)})
        print(f"  dijkstra V={n:>5} E={e:>5}  heap {heap_ms:8.2f} ms   naive {naive_ms:9.2f} ms", file=sys.stderr)

    return rows


# ---------------------------------------------------------------- 2. Hash table
class PolyHashTable(HashTable):
    """Same table, polynomial rolling hash: h = (h*31 + ord(c)) mod size."""
    def index(self, key: str) -> int:
        h = 0
        for c in key:
            h = (h * 31 + ord(c)) % self.size
        return h


def bench_hash():
    keys = [f"FL{i:04d}" for i in range(1, 2001)]   # 2,000 report IDs
    rows = []
    for size in (101, 251, 503, 1009, 2003, 4001):
        row = {"buckets": size, "load": round(len(keys) / size, 2)}
        for name, cls in (("sum", HashTable), ("poly", PolyHashTable)):
            t = cls(size)
            for k in keys:
                t.put(k, k)
            probes = statistics.mean(t.get(k)["steps"] for k in keys)
            row[f"{name}_probes"] = round(probes, 2)
            row[f"{name}_used"] = t.stats()["usedBuckets"]
            row[f"{name}_longest"] = t.stats()["longestChain"]
            row[f"{name}_lookup_us"] = round(timeit(lambda t=t: [t.get(k) for k in keys], 3) * 1000 / len(keys), 2)
        row["theory_probes"] = round(1 + row["load"] / 2, 2)   # expected for uniform hashing
        rows.append(row)
        print(f"  hash size={size:>5} α={row['load']:5.2f}  sum {row['sum_probes']:7.1f} probes "
              f"({row['sum_used']} buckets used)  poly {row['poly_probes']:5.2f}", file=sys.stderr)

    return rows


# ---------------------------------------------------------------- 3. Queue
def bench_queue():
    rows = []
    for n in (1_000, 10_000, 50_000, 100_000):
        def ll():
            q = FIFOQueue()
            for i in range(n):
                q.enqueue(i)
            while len(q):
                q.dequeue()

        def lst():
            q = []
            for i in range(n):
                q.append(i)
            while q:
                q.pop(0)
        rows.append({"N": n, "linked_ms": round(timeit(ll, 3), 2), "list_ms": round(timeit(lst, 3), 2)})
        print(f"  queue N={n:>6}  linked {rows[-1]['linked_ms']:8.2f} ms  list.pop(0) {rows[-1]['list_ms']:8.2f} ms",
              file=sys.stderr)
    return rows


# ---------------------------------------------------------------- 4. Engine ops
def bench_engine():
    with tempfile.TemporaryDirectory() as d:
        eng = FloodWatchEngine(Store(Path(d) / "b.db"))
        ops = {
            "Route RS→AP (Dijkstra)": lambda: eng.route("RS", "AP"),
            "Evacuate from RS (4× Dijkstra)": lambda: eng.evacuate("RS"),
            "Hash lookup FL002": lambda: eng.lookup("FL002"),
            "Full state snapshot": lambda: eng.snapshot(),
            "Submit report (hash+queue+SQLite)": lambda: eng.submit_report(
                "Harbour", "benchmark", "Low", None, None, None),
        }
        rows = [{"operation": k, "ms": round(timeit(f, 200), 4)} for k, f in ops.items()]
    for r in rows:
        print(f"  {r['operation']:<36} {r['ms']:.3f} ms", file=sys.stderr)
    return rows


# ---------------------------------------------------------------- charts
def plot_all(results: dict) -> None:
    """Draw every chart from measured results (re-runnable with --plot-only)."""
    rows = results["dijkstra"]
    fig, ax = plt.subplots(figsize=(7, 4))
    V = [r["V"] for r in rows]
    ax.plot(V, [r["heap_ms"] for r in rows], "o-", color=AMBER, lw=2.2, label="Dijkstra + MinHeap  O((V+E) log V)")
    ax.plot(V, [r["naive_ms"] for r in rows], "s--", color=RED, lw=2, label="Naive array scan  O(V²)")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Locations in network (V)"); ax.set_ylabel("Time per route query (ms, log)")
    ax.set_title("Shortest-route query time vs network size")
    ax.legend(); fig.tight_layout(); fig.savefig(OUT / "dijkstra_scaling.png"); plt.close(fig)
    rows = results["hash"]
    fig, ax = plt.subplots(figsize=(7, 4))
    L = [r["load"] for r in rows]
    ax.plot(L, [r["sum_probes"] for r in rows], "s--", color=RED, lw=2, label="Char-sum hash (current)")
    ax.plot(L, [r["poly_probes"] for r in rows], "o-", color=AMBER, lw=2.2, label="Polynomial hash (×31)")
    ax.plot(L, [r["theory_probes"] for r in rows], ":", color=GREEN, lw=2, label="Theory 1 + α/2")
    ax.set_yscale("log"); ax.invert_xaxis()
    ax.set_xlabel("Load factor α = entries / buckets (2,000 report IDs)")
    ax.set_ylabel("Avg probes per lookup (log)")
    ax.set_title("Hash lookup cost: char-sum vs polynomial hash")
    ax.legend(); fig.tight_layout(); fig.savefig(OUT / "hash_probes.png"); plt.close(fig)

    # bucket distribution at the demo's realistic scale (100 reports, 13 buckets)
    small = [f"FL{i:03d}" for i in range(1, 101)]
    fig, axs = plt.subplots(1, 2, figsize=(8, 3), sharey=True)
    for ax, (name, cls, col) in zip(axs, (("Char-sum", HashTable, RED), ("Polynomial", PolyHashTable, AMBER))):
        t = cls(13)
        for k in small:
            t.put(k, k)
        ax.bar(range(13), [len(b) for b in t.buckets], color=col)
        ax.set_title(f"{name}: 100 IDs in 13 buckets"); ax.set_xlabel("Bucket")
    axs[0].set_ylabel("Chain length"); fig.tight_layout(); fig.savefig(OUT / "hash_distribution.png"); plt.close(fig)
    rows = results["queue"]
    fig, ax = plt.subplots(figsize=(7, 4))
    N = [r["N"] for r in rows]
    ax.plot(N, [r["linked_ms"] for r in rows], "o-", color=AMBER, lw=2.2, label="Linked-list FIFOQueue  O(1) dequeue")
    ax.plot(N, [r["list_ms"] for r in rows], "s--", color=RED, lw=2, label="Python list.pop(0)  O(n) dequeue")
    ax.set_xlabel("Reports enqueued then fully processed (N)"); ax.set_ylabel("Total time (ms)")
    ax.set_title("Verification queue: draining N reports"); ax.legend()
    fig.tight_layout(); fig.savefig(OUT / "queue_drain.png"); plt.close(fig)


def md_table(rows, cols):
    head = "| " + " | ".join(c[1] for c in cols) + " |\n|" + "---|" * len(cols) + "\n"
    return head + "\n".join("| " + " | ".join(str(r[c[0]]) for c in cols) + " |" for r in rows)


if __name__ == "__main__":
    import platform
    if "--plot-only" in sys.argv:          # redraw charts from saved results.json
        plot_all(json.loads((OUT / "results.json").read_text()))
        sys.exit(0)
    print("Running FloodWatch benchmarks…", file=sys.stderr)
    results = {
        "machine": {"python": platform.python_version(), "platform": platform.platform(),
                    "processor": platform.processor() or platform.machine()},
        "dijkstra": bench_dijkstra(), "hash": bench_hash(),
        "queue": bench_queue(), "engine": bench_engine(),
    }
    (OUT / "results.json").write_text(json.dumps(results, indent=2))
    plot_all(results)
    print(md_table(results["dijkstra"], [("V", "V"), ("E", "E"), ("heap_ms", "Heap (ms)"),
                                         ("naive_ms", "Naive (ms)"), ("speedup", "Speed-up ×")]))
    print()
    print(md_table(results["hash"], [("buckets", "Buckets"), ("load", "α"), ("sum_probes", "Sum probes"),
                                     ("sum_used", "Sum buckets used"), ("poly_probes", "Poly probes"),
                                     ("theory_probes", "Theory")]))
    print()
    print(md_table(results["queue"], [("N", "N"), ("linked_ms", "Linked list (ms)"), ("list_ms", "list.pop(0) (ms)")]))
    print()
    print(md_table(results["engine"], [("operation", "Operation"), ("ms", "Median ms")]))
    print(f"\nCharts and results.json written to {OUT}", file=sys.stderr)
