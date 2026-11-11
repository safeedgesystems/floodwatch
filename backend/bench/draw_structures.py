"""Draws clean data-structure representation diagrams for the report/slides.
Run from backend/:  python -m bench.draw_structures   → docs/diagrams/05_hash_table.png, 07_heap.png"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "docs" / "diagrams"
BLUE, INK, SEV = "#D98A0B", "#121417", {"High": "#EF4444", "Medium": "#F97316", "Low": "#22C55E"}  # Graphite + Amber


def box(ax, x, y, w, h, text, fc="#FFF4DE", ec=BLUE, tc=INK, fs=11, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec=ec, lw=1.6))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color=tc, fontsize=fs,
            fontweight="bold" if bold else "normal", family="DejaVu Sans")


def arrow(ax, x1, y1, x2, y2, color=INK):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=14, color=color, lw=1.4))


def hash_table():
    # Real layout of the demo data in an 8-bucket table, plus an injected collision.
    chains = {3: [("FL001", "High"), ("FL010", "Low")], 4: [("FL002", "Medium")], 5: [("FL003", "Low")]}
    fig, ax = plt.subplots(figsize=(11, 6.2))
    ax.set_xlim(0, 11); ax.set_ylim(-0.6, 9.2); ax.axis("off")
    ax.text(0.2, 8.85, "Hash table with separate chaining (8 buckets)", fontsize=15, fontweight="bold", color=INK)
    # hash computation
    box(ax, 0.2, 7.2, 4.6, 1.2, "key = \"FL001\"\nF70 + L76 + 0 48 + 0 48 + 1 49 = 291", fc="#F1F3F5", ec="#4A525C", fs=11)
    box(ax, 5.4, 7.2, 2.6, 1.2, "291 mod 8 = 3", fc="#F1F3F5", ec="#4A525C", fs=12, bold=True)
    arrow(ax, 4.8, 7.8, 5.4, 7.8)
    arrow(ax, 6.7, 7.2, 1.55, 4.55, color="#4A525C")
    for i in range(8):
        y = 6.3 - i * 0.85
        hot = i == 3
        box(ax, 0.6, y, 0.9, 0.65, str(i), fc=BLUE if hot else "#FFF4DE", tc="white" if hot else INK, bold=True)
        x = 1.5
        for key, sev in chains.get(i, []):
            arrow(ax, x, y + 0.33, x + 0.6, y + 0.33)
            box(ax, x + 0.6, y, 2.2, 0.65, f"{key} · {sev}", fc="white", ec=SEV[sev], fs=10.5)
            x += 2.8
        arrow(ax, x, y + 0.33, x + 0.5, y + 0.33, color="#AEB5BE")
        ax.text(x + 0.6, y + 0.33, "None", va="center", color="#8B949E", fontsize=10)
    ax.text(0.6, 7.0, "index", color="#8B949E", fontsize=9)
    ax.text(3.0, 1.15, "↑ collision: FL010 has the same characters as FL001\n   rearranged → same sum 291 → bucket 3.\n   It is appended to the chain; get(FL010) takes 2 probes.", fontsize=10, color="#B91C1C")
    ax.text(0.2, -0.45, "put: O(1) average · get: O(1 + α) where α = entries/buckets · resize: O(n) rehash", fontsize=10, color="#4A525C")
    fig.tight_layout(); fig.savefig(OUT / "05_hash_table.png", dpi=170, facecolor="white"); plt.close(fig)


def heap():
    # Heap state during Dijkstra from RS (demo network) after relaxing RS's neighbours
    items = [(0.0, "RS"), (2.1, "OB"), (3.5, "HB"), (3.9, "MS"), (4.6, "MS")]
    fig, ax = plt.subplots(figsize=(11, 5.4))
    ax.set_xlim(0, 11); ax.set_ylim(0, 6.6); ax.axis("off")
    ax.text(0.2, 6.25, "Binary min-heap (array-backed) — Dijkstra's priority queue (illustrative values)", fontsize=15, fontweight="bold", color=INK)
    pos = {0: (5.5, 5.0), 1: (3.3, 3.6), 2: (7.7, 3.6), 3: (2.2, 2.2), 4: (4.4, 2.2)}
    for i, (x, y) in pos.items():
        for c in (2 * i + 1, 2 * i + 2):
            if c in pos:
                ax.plot([x, pos[c][0]], [y, pos[c][1]], color="#AEB5BE", lw=1.6, zorder=0)
    for i, (x, y) in pos.items():
        d, n = items[i]
        stale = i == 4
        ax.add_patch(plt.Circle((x, y), 0.52, fc=BLUE if i == 0 else ("#f3f3f3" if stale else "#FFF4DE"),
                                ec="#AEB5BE" if stale else BLUE, lw=1.8, ls="--" if stale else "-"))
        ax.text(x, y + 0.12, n, ha="center", va="center", fontsize=12, fontweight="bold",
                color="white" if i == 0 else INK)
        ax.text(x, y - 0.2, f"{d} km", ha="center", va="center", fontsize=9.5, color="white" if i == 0 else INK)
        ax.text(x + 0.62, y + 0.4, f"[{i}]", fontsize=9, color="#8B949E")
    ax.text(5.5, 5.75, "root = smallest distance → pop() next", ha="center", fontsize=10, color=BLUE)
    ax.text(5.2, 1.45, "stale entry: MS was first pushed at 4.6, then a\nshorter 3.9 path was found and pushed again.\nThe 4.6 copy is skipped when popped (lazy deletion).", fontsize=9.5, color="#8B949E")
    # array view
    ax.text(0.2, 0.95, "array:", fontsize=11, color=INK, fontweight="bold")
    for i, (d, n) in enumerate(items):
        box(ax, 1.2 + i * 1.9, 0.6, 1.75, 0.65, f"[{i}] ({d}, {n})", fc="#f3f3f3" if i == 4 else "#FFF4DE",
            ec="#AEB5BE" if i == 4 else BLUE, fs=10)
    ax.text(0.2, 0.15, "parent(i) = (i−1)//2 · children = 2i+1, 2i+2 · push: sift-up O(log n) · pop: sift-down O(log n)",
            fontsize=10, color="#4A525C")
    ax.text(8.7, 4.4, "Heap property:\nparent ≤ children", fontsize=10.5, color=INK,
            bbox=dict(boxstyle="round", fc="#F1F3F5", ec="#4A525C"))
    fig.tight_layout(); fig.savefig(OUT / "07_heap.png", dpi=170, facecolor="white"); plt.close(fig)


if __name__ == "__main__":
    hash_table(); heap(); print("diagrams written to", OUT)
