import tkinter as tk
from tkinter import ttk, messagebox
import math
import random
from collections import deque

# FloodWatch: simulated flood reporting and alternative-route prototype.
# All roads, reports and distances in this project are demonstration data.

SEV_RANK = {"High": 0, "Medium": 1, "Low": 2}

LOCATIONS = [
    {"id": "RS", "name": "Riverside", "x": 80, "y": 330},
    {"id": "OB", "name": "Old Bridge", "x": 110, "y": 110},
    {"id": "MS", "name": "Market Square", "x": 300, "y": 220},
    {"id": "HJ", "name": "Hospital Junction", "x": 340, "y": 70},
    {"id": "HC", "name": "Hillcrest", "x": 520, "y": 120},
    {"id": "UG", "name": "University Gate", "x": 510, "y": 280},
    {"id": "AP", "name": "Airport", "x": 610, "y": 350},
    {"id": "HB", "name": "Harbour", "x": 280, "y": 380},
]

ROADS = [
    {"id": "RS-OB", "a": "RS", "b": "OB", "km": 2.1},
    {"id": "OB-MS", "a": "OB", "b": "MS", "km": 1.8},
    {"id": "RS-MS", "a": "RS", "b": "MS", "km": 2.9},
    {"id": "MS-HJ", "a": "MS", "b": "HJ", "km": 1.2},
    {"id": "HJ-HC", "a": "HJ", "b": "HC", "km": 2.2},
    {"id": "MS-HC", "a": "MS", "b": "HC", "km": 3.0},
    {"id": "HC-UG", "a": "HC", "b": "UG", "km": 1.9},
    {"id": "MS-UG", "a": "MS", "b": "UG", "km": 3.1},
    {"id": "UG-AP", "a": "UG", "b": "AP", "km": 3.4},
    {"id": "MS-HB", "a": "MS", "b": "HB", "km": 2.8},
    {"id": "RS-HB", "a": "RS", "b": "HB", "km": 3.5},
    {"id": "HB-AP", "a": "HB", "b": "AP", "km": 6.8},
]

LOC_MAP = {loc["id"]: loc for loc in LOCATIONS}
ROAD_MAP = {road["id"]: road for road in ROADS}
ROAD_CHOICES = ["None"] + [
    f"{r['id']} — {LOC_MAP[r['a']]['name']} to {LOC_MAP[r['b']]['name']}"
    for r in ROADS
]


# Safe destinations used by the Evacuation Advisor.
SHELTERS = {
    "HJ": "Hospital Junction (medical)",
    "HC": "Hillcrest (high ground)",
    "UG": "University Gate (shelter hall)",
    "AP": "Airport (terminal)",
}
RISK_WEIGHT = {"High": 3, "Medium": 2, "Low": 1}


def mix_colour(c1, c2, f):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3))


class HashTable:
    """Hash table using separate chaining to store reports by report ID."""

    def __init__(self, size=8):
        self.size = size
        self.buckets = [[] for _ in range(size)]
        self.count = 0

    @staticmethod
    def sum_key(key):
        return sum(ord(char) for char in key)

    def index(self, key):
        return self.sum_key(key) % self.size

    def put(self, key, value):
        bucket = self.buckets[self.index(key)]
        for entry in bucket:
            if entry["key"] == key:
                entry["value"] = value
                return False
        bucket.append({"key": key, "value": value})
        self.count += 1
        return True

    def get(self, key):
        idx = self.index(key)
        steps = 0
        for entry in self.buckets[idx]:
            steps += 1
            if entry["key"] == key:
                return {"found": True, "index": idx, "steps": steps, "entry": entry}
        return {"found": False, "index": idx, "steps": steps}

    def entries(self):
        return [entry for bucket in self.buckets for entry in bucket]

    def resize(self, new_size):
        old_entries = self.entries()
        self.size = new_size
        self.buckets = [[] for _ in range(new_size)]
        self.count = 0
        for entry in old_entries:
            self.put(entry["key"], entry["value"])


class MinHeap:
    """Binary min heap used by Dijkstra's algorithm."""

    def __init__(self):
        self.items = []

    @property
    def size(self):
        return len(self.items)

    def push(self, priority, value):
        self.items.append({"pri": priority, "val": value})
        i = len(self.items) - 1
        while i > 0:
            parent = (i - 1) // 2
            if self.items[parent]["pri"] <= self.items[i]["pri"]:
                break
            self.items[parent], self.items[i] = self.items[i], self.items[parent]
            i = parent

    def pop(self):
        if not self.items:
            return None
        smallest = self.items[0]
        last = self.items.pop()
        if self.items:
            self.items[0] = last
            i, n = 0, len(self.items)
            while True:
                left, right = 2 * i + 1, 2 * i + 2
                smallest_child = i
                if left < n and self.items[left]["pri"] < self.items[smallest_child]["pri"]:
                    smallest_child = left
                if right < n and self.items[right]["pri"] < self.items[smallest_child]["pri"]:
                    smallest_child = right
                if smallest_child == i:
                    break
                self.items[i], self.items[smallest_child] = (
                    self.items[smallest_child], self.items[i]
                )
                i = smallest_child
        return smallest


def build_graph():
    graph = {loc["id"]: [] for loc in LOCATIONS}
    for road in ROADS:
        graph[road["a"]].append(
            {"to": road["b"], "weight": road["km"], "road": road["id"]}
        )
        graph[road["b"]].append(
            {"to": road["a"], "weight": road["km"], "road": road["id"]}
        )
    return graph


def dijkstra(graph, blocked_roads, start, goal):
    distances = {node: float("inf") for node in graph}
    previous = {}
    previous_road = {}
    settled = []
    distances[start] = 0

    heap = MinHeap()
    heap.push(0, start)

    while heap.size:
        item = heap.pop()
        distance, node = item["pri"], item["val"]
        if distance > distances[node]:
            continue

        settled.append(node)
        if node == goal:
            break

        for edge in graph[node]:
            if edge["road"] in blocked_roads:
                continue
            new_distance = distance + edge["weight"]
            if new_distance < distances[edge["to"]]:
                distances[edge["to"]] = new_distance
                previous[edge["to"]] = node
                previous_road[edge["to"]] = edge["road"]
                heap.push(new_distance, edge["to"])

    if distances[goal] == float("inf"):
        return None

    path, roads = [], []
    current = goal
    while True:
        path.insert(0, current)
        if current in previous_road:
            roads.insert(0, previous_road[current])
        if current not in previous:
            break
        current = previous[current]

    return {
        "path": path,
        "roads": roads,
        "distance": round(distances[goal], 1),
        "settled": settled,
    }


class SplashScreen(tk.Canvas):
    """Animated welcome screen shown before the system opens."""

    CARDS = [
        ("📝", "Report", "Residents submit flood reports with a severity level and the road affected."),
        ("🗂", "Verify", "An admin queue and a hash table (separate chaining) store and find every report."),
        ("🧭", "Route", "Dijkstra's algorithm with a min-heap finds the shortest open route around floods."),
        ("🛟", "Evacuate", "The advisor ranks safe shelters from wherever you are and avoids flooded ones."),
    ]
    ROUTE = ["RS", "OB", "MS", "UG", "AP"]

    def __init__(self, master, on_enter):
        super().__init__(master, highlightthickness=0, bg="#04202F")
        self.t = 0
        self.w, self.h = 1180, 800
        self.running = False
        self.after_id = None
        self.pos = {}
        self.drops = [
            [random.random(), random.random(), random.uniform(0.012, 0.03),
             random.randint(8, 18)] for _ in range(110)
        ]
        self.button = tk.Button(
            self, text="Enter FloodWatch  →", command=on_enter, bd=0,
            bg="#12A0D8", fg="white", activebackground="#0C7FB0",
            activeforeground="white", cursor="hand2",
            font=("Segoe UI", 14, "bold"), padx=34, pady=12
        )
        self.button.bind("<Enter>", lambda e: self.button.config(bg="#2BB6EE"))
        self.button.bind("<Leave>", lambda e: self.button.config(bg="#12A0D8"))
        self.button_win = self.create_window(0, 0, window=self.button)
        self.bind("<Configure>", self.on_resize)

    def start(self):
        self.running = True
        if self.after_id:
            self.after_cancel(self.after_id)
        self.animate()

    def stop(self):
        self.running = False
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None

    def on_resize(self, event):
        if event.width < 200 or event.height < 200:
            return
        self.w, self.h = event.width, event.height
        self.coords(self.button_win, self.w / 2, self.h * 0.70)
        self.draw_static()

    def round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def draw_static(self):
        self.delete("bg", "net", "sky", "ui")
        w, h = self.w, self.h

        steps = 60
        band = h / steps
        for i in range(steps):
            col = mix_colour("#04202F", "#0E6288", i / (steps - 1))
            self.create_rectangle(0, i * band, w, (i + 1) * band + 1,
                                  fill=col, outline=col, tags="bg")

        top, bottom = h * 0.08, h * 0.84
        self.pos = {
            loc["id"]: (60 + (loc["x"] - 80) * (w - 120) / 530,
                        top + (loc["y"] - 70) * (bottom - top) / 310)
            for loc in LOCATIONS
        }
        for road in ROADS:
            ax, ay = self.pos[road["a"]]
            bx, by = self.pos[road["b"]]
            blocked = road["id"] in ("RS-MS", "HJ-HC")
            self.create_line(ax, ay, bx, by, tags="net", width=2,
                             fill="#8A3A33" if blocked else "#1D6C92",
                             dash=(6, 5) if blocked else None)
        for a, b in zip(self.ROUTE, self.ROUTE[1:]):
            ax, ay = self.pos[a]
            bx, by = self.pos[b]
            self.create_line(ax, ay, bx, by, tags="net", width=5, fill="#1A9AD0")
        for loc in LOCATIONS:
            x, y = self.pos[loc["id"]]
            hot = loc["id"] in ("RS", "MS", "HC")
            self.create_oval(x - 9, y - 9, x + 9, y + 9, tags="net", width=2,
                             fill="#07283B", outline="#B3341A" if hot else "#2A8DB8")

        rng = random.Random(7)
        base, x = h * 0.94, 0
        while x < w:
            bw, bh = rng.randint(34, 80), rng.randint(40, 120)
            self.create_rectangle(x, base - bh, x + bw, base + 40,
                                  fill="#082A3E", outline="", tags="sky")
            for wy in range(int(base - bh + 8), int(base - 6), 16):
                for wx in range(int(x + 7), int(x + bw - 8), 14):
                    if rng.random() < 0.28:
                        self.create_rectangle(wx, wy, wx + 5, wy + 7,
                                              fill="#F2C55C", outline="", tags="sky")
            x += bw + rng.randint(0, 6)

        cx = w / 2
        self.create_text(cx, h * 0.10, text="🌊 FloodWatch", tags="ui",
                         fill="white", font=("Segoe UI", 44, "bold"))
        self.create_text(cx, h * 0.18, tags="ui", fill="#9FD8F0",
                         text="Flood Hazard Reporting & Safe Route Recommendation",
                         font=("Segoe UI", 15))
        self.create_text(cx, h * 0.235, tags="ui", fill="#C9E7F5", width=min(760, w - 80),
                         justify="center", font=("Segoe UI", 11),
                         text="Report flooding, verify it, and see which roads stay open. "
                              "FloodWatch turns community reports into the safest way across the city.")

        gap = 18
        cw = min(250, (w - 100 - gap * 3) / 4)
        total = cw * 4 + gap * 3
        x0, y0, ch = (w - total) / 2, h * 0.32, 175
        for i, (icon, title, body) in enumerate(self.CARDS):
            x = x0 + i * (cw + gap)
            self.round_rect(x + 3, y0 + 4, x + cw + 3, y0 + ch + 4, 16,
                            fill="#031926", outline="", tags="ui")
            self.round_rect(x, y0, x + cw, y0 + ch, 16, fill="#0B3A55",
                            outline="#2287B3", width=2, tags="ui")
            self.create_text(x + 18, y0 + 30, text=icon, anchor="w", tags="ui",
                             fill="white", font=("Segoe UI Emoji", 20))
            self.create_text(x + 56, y0 + 30, text=f"{i + 1}. {title}", anchor="w",
                             tags="ui", fill="#6FD0FF", font=("Segoe UI", 14, "bold"))
            self.create_text(x + 18, y0 + 62, text=body, anchor="nw", width=cw - 36,
                             tags="ui", fill="#D6EBF5", font=("Segoe UI", 10))

        self.create_text(cx, h * 0.80, tags="ui", fill="#9FD8F0", font=("Segoe UI", 10),
                         text="Blue = open recommended route    Red dashed = blocked road    "
                              "Red node = reported flooding")
        self.create_text(cx, h - 14, tags="ui", fill="#7FB6CF", font=("Segoe UI", 9),
                         text="Simulation prototype  •  All roads, reports and distances are demonstration data")
        self.tag_raise("ui")

    def animate(self):
        if not self.running:
            return
        self.t += 1
        self.delete("dyn")
        w, h = self.w, self.h

        for d in self.drops:
            d[1] += d[2]
            if d[1] > 1:
                d[1], d[0] = 0, random.random()
            x, y = d[0] * w, d[1] * h
            self.create_line(x, y, x - 3, y + d[3], fill="#6FB6D6", tags="dyn")

        if self.pos:
            x, y = self.pos["RS"]
            r = 13 + 7 * abs(math.sin(self.t * 0.08))
            self.create_oval(x - r, y - r, x + r, y + r, outline="#E05A3A",
                             width=2, tags="dyn")
            pts = [self.pos[n] for n in self.ROUTE]
            lengths = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
            dist = (self.t * 5) % sum(lengths)
            for (a, b), seg in zip(zip(pts, pts[1:]), lengths):
                if dist <= seg:
                    f = dist / seg
                    px, py = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
                    self.create_oval(px - 7, py - 7, px + 7, py + 7, fill="#4FD1FF",
                                     outline="white", width=2, tags="dyn")
                    break
                dist -= seg

        level = h * 0.925 + 5 * math.sin(self.t * 0.03)
        for amp, speed, colour, off in ((7, 0.07, "#1479A6", 0), (5, 0.10, "#0A5F86", 14)):
            pts = [0, h]
            for x in range(0, w + 12, 12):
                pts += [x, level + off + amp * math.sin(x * 0.02 + self.t * speed)]
            pts += [w, h]
            self.create_polygon(pts, fill=colour, outline="", tags="dyn")

        for tag in ("bg", "net", "sky", "dyn", "ui"):
            self.tag_raise(tag)
        self.after_id = self.after(40, self.animate)


class FloodWatchApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FloodWatch — Flood Hazard & Route Recommendation")
        self.geometry("1180x800")
        self.minsize(1080, 740)

        self.bg = "#F4F7F9"
        self.card = "#FFFFFF"
        self.primary = "#0A6A94"
        self.ink = "#12222B"
        self.muted = "#596E79"
        self.line = "#D4E0E6"
        self.configure(bg=self.bg)

        self.table = HashTable(8)
        self.report_queue = deque()
        self.next_num = 1

        self.manual_blocked_roads = {"RS-MS", "HJ-HC"}
        self.blocked_roads = set(self.manual_blocked_roads)
        self.graph = build_graph()

        self.add_report(
            "Riverside", "Water covering both lanes near the bridge",
            "High", loc_id="RS", road_id="RS-OB"
        )
        self.add_report(
            "Market Square", "Standing water pooling near vendor stalls",
            "Medium", loc_id="MS", road_id="MS-HJ"
        )
        self.add_report(
            "Hillcrest", "Minor overflow near residential gate",
            "Low", loc_id="HC", road_id="HJ-HC"
        )

        self.setup_styles()
        self.main = tk.Frame(self, bg=self.bg)
        self.create_layout()
        self.refresh_all()

        self.splash = SplashScreen(self, self.enter_system)
        self.splash.pack(fill=tk.BOTH, expand=True)
        self.splash.start()
        self.bind("<Return>", lambda e: self.enter_system()
                  if self.splash.winfo_ismapped() else None)

    def enter_system(self):
        self.splash.stop()
        self.splash.pack_forget()
        self.main.pack(fill=tk.BOTH, expand=True)

    def show_home(self):
        self.main.pack_forget()
        self.splash.pack(fill=tk.BOTH, expand=True)
        self.splash.start()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=self.bg, foreground=self.ink,
                        font=("Segoe UI", 10))
        style.configure("TNotebook", background=self.bg, borderwidth=0)
        style.configure("TNotebook.Tab", padding=[14, 9],
                        font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", self.card)],
                  foreground=[("selected", self.primary)])
        style.configure("Card.TFrame", background=self.card)
        style.configure("Heading.TLabel", background=self.card,
                        foreground=self.ink, font=("Segoe UI", 15, "bold"))
        style.configure("Sub.TLabel", background=self.card,
                        foreground=self.ink, font=("Segoe UI", 10, "bold"))
        style.configure("Muted.TLabel", background=self.card,
                        foreground=self.muted, font=("Segoe UI", 9))
        style.configure("Accent.TButton", background=self.primary,
                        foreground="white", font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#085374")])
        style.configure("Treeview", rowheight=25, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def create_layout(self):
        header = tk.Frame(self.main, bg=self.card, height=68,
                          highlightbackground=self.line, highlightthickness=1)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="🌊 FloodWatch", bg=self.card, fg=self.primary,
                 font=("Segoe UI", 19, "bold")).pack(side=tk.LEFT, padx=20)
        tk.Label(
            header, text="Flood reports • Hash table • Shortest safe route simulation",
            bg=self.card, fg=self.muted, font=("Segoe UI", 10)
        ).pack(side=tk.LEFT)

        tk.Button(header, text="⌂ Home", command=self.show_home, bd=0,
                  bg=self.card, fg=self.primary, cursor="hand2",
                  font=("Segoe UI", 10, "bold")).pack(side=tk.RIGHT, padx=(0, 18))
        self.summary = tk.Label(header, text="", bg=self.card, fg=self.ink,
                                font=("Segoe UI", 10, "bold"))
        self.summary.pack(side=tk.RIGHT, padx=18)

        self.tabs = ttk.Notebook(self.main)
        self.tabs.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)
        self.tab_reports = ttk.Frame(self.tabs)
        self.tab_hash = ttk.Frame(self.tabs)
        self.tab_roads = ttk.Frame(self.tabs)
        self.tabs.add(self.tab_reports, text="  Reports & Admin Queue  ")
        self.tabs.add(self.tab_hash, text="  Hash Table  ")
        self.tabs.add(self.tab_roads, text="  Road Network & Routing  ")
        self.tab_evac = ttk.Frame(self.tabs)
        self.tabs.add(self.tab_evac, text="  Evacuation Advisor  ")
        self.setup_reports_tab()
        self.setup_hash_tab()
        self.setup_roads_tab()
        self.setup_evac_tab()

    def setup_reports_tab(self):
        outer = ttk.Frame(self.tab_reports)
        outer.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        form = ttk.Frame(outer, style="Card.TFrame", padding=15)
        form.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        ttk.Label(form, text="Submit a Flood Report",
                  style="Heading.TLabel").pack(anchor=tk.W, pady=(0, 12))

        ttk.Label(form, text="Location name (Custom or Existing)", style="Sub.TLabel").pack(anchor=tk.W)
        self.loc_entry = ttk.Entry(form, width=34)
        self.loc_entry.pack(fill=tk.X, pady=(4, 10))

        ttk.Label(form, text="Description", style="Sub.TLabel").pack(anchor=tk.W)
        self.desc_text = tk.Text(form, width=34, height=4, font=("Segoe UI", 9))
        self.desc_text.pack(fill=tk.X, pady=(4, 10))

        ttk.Label(form, text="Severity", style="Sub.TLabel").pack(anchor=tk.W)
        self.severity_var = tk.StringVar(value="Medium")
        sev_frame = ttk.Frame(form, style="Card.TFrame")
        sev_frame.pack(anchor=tk.W, pady=5)
        for severity in ("High", "Medium", "Low"):
            ttk.Radiobutton(sev_frame, text=severity, value=severity,
                            variable=self.severity_var).pack(side=tk.LEFT, padx=(0, 7))

        ttk.Label(form, text="Affected road (optional)",
                  style="Sub.TLabel").pack(anchor=tk.W, pady=(8, 0))
        self.road_var = tk.StringVar(value="None")
        self.road_combo = ttk.Combobox(
            form, textvariable=self.road_var, values=ROAD_CHOICES,
            state="readonly", width=38
        )
        self.road_combo.pack(fill=tk.X, pady=(4, 10))

        self.next_id_label = ttk.Label(form, text="", style="Muted.TLabel")
        self.next_id_label.pack(anchor=tk.W, pady=(4, 8))
        ttk.Button(form, text="Submit Report", style="Accent.TButton",
                   command=self.on_submit_report).pack(fill=tk.X, ipady=4)

        ttk.Separator(form).pack(fill=tk.X, pady=14)
        ttk.Label(form, text="Admin: Process & Management",
                  style="Sub.TLabel").pack(anchor=tk.W)
        ttk.Label(
            form,
            text="Processing a report marks it Verified. You can also clear all reports or delete selected entries.",
            style="Muted.TLabel", wraplength=270
        ).pack(anchor=tk.W, pady=6)
        self.queue_label = ttk.Label(form, text="", style="Muted.TLabel")
        self.queue_label.pack(anchor=tk.W, pady=4)
        ttk.Button(form, text="Process Next Report",
                   command=self.process_next_report).pack(fill=tk.X, pady=2)
        ttk.Button(form, text="Delete Selected Report",
                   command=self.delete_selected_report).pack(fill=tk.X, pady=2)
        ttk.Button(form, text="Clear All Reports",
                   command=self.clear_all_reports).pack(fill=tk.X, pady=2)

        right = ttk.Frame(outer, style="Card.TFrame", padding=12)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        lookup = ttk.Frame(right, style="Card.TFrame")
        lookup.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(lookup, text="Quick lookup by report ID",
                  style="Sub.TLabel").pack(anchor=tk.W)
        lookup_row = ttk.Frame(lookup, style="Card.TFrame")
        lookup_row.pack(fill=tk.X, pady=4)
        self.lookup_entry = ttk.Entry(lookup_row, width=18)
        self.lookup_entry.pack(side=tk.LEFT, padx=(0, 7))
        ttk.Button(lookup_row, text="Search",
                   command=self.on_lookup_report).pack(side=tk.LEFT)
        self.lookup_result = ttk.Label(lookup, text="", style="Muted.TLabel")
        self.lookup_result.pack(anchor=tk.W)

        ttk.Label(right, text="Reports (double-click a row to cycle status)",
                  style="Sub.TLabel").pack(anchor=tk.W, pady=(8, 5))
        cols = ("id", "severity", "location", "road", "status", "description")
        self.report_tree = ttk.Treeview(right, columns=cols, show="headings", height=17)
        headings = [
            ("id", 65, "ID"), ("severity", 75, "Severity"),
            ("location", 115, "Location"), ("road", 80, "Road"),
            ("status", 85, "Status"), ("description", 260, "Description")
        ]
        for col, width, heading in headings:
            self.report_tree.heading(col, text=heading)
            self.report_tree.column(col, width=width, anchor=tk.W)
        self.report_tree.pack(fill=tk.BOTH, expand=True)
        self.report_tree.bind("<Double-1>", self.on_report_double_click)
        self.report_tree.bind("<Delete>", lambda e: self.delete_selected_report())
        self.report_tree.bind("<BackSpace>", lambda e: self.delete_selected_report())

    def setup_hash_tab(self):
        outer = ttk.Frame(self.tab_hash)
        outer.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        left = ttk.Frame(outer, style="Card.TFrame", padding=16)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        ttk.Label(left, text="Hash Table Mechanics",
                  style="Heading.TLabel").pack(anchor=tk.W)
        ttk.Label(
            left,
            text="The report ID is hashed to a bucket. Collisions are handled using separate chaining.",
            style="Muted.TLabel", wraplength=260
        ).pack(anchor=tk.W, pady=10)

        ttk.Label(left, text="Bucket size", style="Sub.TLabel").pack(anchor=tk.W)
        self.bucket_size = tk.IntVar(value=8)
        for size in (5, 8, 11, 13):
            ttk.Radiobutton(
                left, text=str(size), value=size, variable=self.bucket_size,
                command=self.change_bucket_size
            ).pack(anchor=tk.W)

        self.hash_stats = ttk.Label(left, text="", style="Muted.TLabel")
        self.hash_stats.pack(anchor=tk.W, pady=15)
        ttk.Separator(left).pack(fill=tk.X, pady=8)
        ttk.Label(left, text="Test a key", style="Sub.TLabel").pack(anchor=tk.W)
        self.test_key = ttk.Entry(left)
        self.test_key.insert(0, "FL001")
        self.test_key.pack(fill=tk.X, pady=5)
        self.test_key.bind("<KeyRelease>", lambda event: self.render_hash_view())
        self.hash_test_result = ttk.Label(left, text="", style="Muted.TLabel")
        self.hash_test_result.pack(anchor=tk.W)

        right = ttk.Frame(outer, style="Card.TFrame", padding=14)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        ttk.Label(right, text="Bucket chains",
                  style="Heading.TLabel").pack(anchor=tk.W, pady=(0, 8))
        self.bucket_text = tk.Text(right, font=("Consolas", 10),
                                   bg="#FAFCFD", wrap=tk.NONE)
        self.bucket_text.pack(fill=tk.BOTH, expand=True)

    def setup_roads_tab(self):
        outer = ttk.Frame(self.tab_roads)
        outer.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        left = ttk.Frame(outer, style="Card.TFrame", padding=14)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        ttk.Label(left, text="Shortest Available Route (Dijkstra)",
                  style="Heading.TLabel").pack(anchor=tk.W, pady=(0, 10))

        picks = ttk.Frame(left, style="Card.TFrame")
        picks.pack(anchor=tk.W)
        names = [f"{loc['id']} - {loc['name']}" for loc in LOCATIONS]
        ttk.Label(picks, text="From", style="Sub.TLabel").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(picks, text="To", style="Sub.TLabel").grid(row=0, column=1, sticky=tk.W)
        self.from_combo = ttk.Combobox(picks, values=names, state="readonly", width=22)
        self.to_combo = ttk.Combobox(picks, values=names, state="readonly", width=22)
        self.from_combo.current(0)
        self.to_combo.current(4)
        self.from_combo.grid(row=1, column=0, padx=(0, 10), pady=4)
        self.to_combo.grid(row=1, column=1, pady=4)
        self.from_combo.bind("<<ComboboxSelected>>", lambda event: self.refresh_route())
        self.to_combo.bind("<<ComboboxSelected>>", lambda event: self.refresh_route())

        self.route_result = ttk.Label(left, text="", style="Sub.TLabel",
                                      wraplength=520, foreground=self.primary)
        self.route_result.pack(anchor=tk.W, pady=10)

        ttk.Label(left, text="Roads (double-click to manually block / reopen)",
                  style="Sub.TLabel").pack(anchor=tk.W, pady=(8, 5))
        columns = ("id", "segment", "distance", "status", "source")
        self.road_tree = ttk.Treeview(left, columns=columns, show="headings", height=13)
        for col, width, heading in [
            ("id", 65, "Road"), ("segment", 190, "Segment"),
            ("distance", 70, "Km"), ("status", 85, "Status"),
            ("source", 100, "Block source")
        ]:
            self.road_tree.heading(col, text=heading)
            self.road_tree.column(col, width=width, anchor=tk.W)
        self.road_tree.pack(fill=tk.BOTH, expand=True)
        self.road_tree.bind("<Double-1>", self.toggle_manual_road)

        right = ttk.Frame(outer, style="Card.TFrame", padding=12)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        ttk.Label(right, text="Simulated road map",
                  style="Heading.TLabel").pack(anchor=tk.W, pady=(0, 8))
        self.canvas = tk.Canvas(
            right, width=680, height=500, bg="#FAFCFD",
            highlightthickness=1, highlightbackground=self.line
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            right,
            text="Legend: blue = recommended route; red dashed = blocked road; node colour = highest active report severity.",
            style="Muted.TLabel", wraplength=500
        ).pack(anchor=tk.W, pady=7)

    def setup_evac_tab(self):
        outer = ttk.Frame(self.tab_evac)
        outer.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        left = ttk.Frame(outer, style="Card.TFrame", padding=14)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        ttk.Label(left, text="Evacuation Advisor",
                  style="Heading.TLabel").pack(anchor=tk.W)
        ttk.Label(
            left,
            text="Pick where you are. Dijkstra runs to every shelter over the roads that "
                 "are currently open. Shelters with an active High-severity flood report "
                 "are ranked last and marked to avoid.",
            style="Muted.TLabel", wraplength=520
        ).pack(anchor=tk.W, pady=(6, 10))

        ttk.Label(left, text="Where are you now?", style="Sub.TLabel").pack(anchor=tk.W)
        names = [f"{loc['id']} - {loc['name']}" for loc in LOCATIONS]
        self.evac_combo = ttk.Combobox(left, values=names, state="readonly", width=30)
        self.evac_combo.current(0)
        self.evac_combo.pack(anchor=tk.W, pady=(4, 10))
        self.evac_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_evac())

        self.evac_status = ttk.Label(left, text="", style="Sub.TLabel",
                                     wraplength=520, foreground=self.primary)
        self.evac_status.pack(anchor=tk.W, pady=(0, 4))
        self.evac_risk = ttk.Label(left, text="", style="Muted.TLabel", wraplength=520)
        self.evac_risk.pack(anchor=tk.W, pady=(0, 10))

        cols = ("shelter", "km", "eta", "risk", "state")
        self.evac_tree = ttk.Treeview(left, columns=cols, show="headings", height=6)
        for col, width, heading in [
            ("shelter", 210, "Shelter"), ("km", 60, "Km"), ("eta", 70, "ETA"),
            ("risk", 90, "Area risk"), ("state", 120, "Status")
        ]:
            self.evac_tree.heading(col, text=heading)
            self.evac_tree.column(col, width=width, anchor=tk.W)
        self.evac_tree.tag_configure("best", background="#D9EDE2")
        self.evac_tree.tag_configure("bad", foreground="#B3341A")
        self.evac_tree.pack(fill=tk.X)
        ttk.Label(left, text="ETA assumes 30 km/h on flooded roads.",
                  style="Muted.TLabel").pack(anchor=tk.W, pady=6)

        right = ttk.Frame(outer, style="Card.TFrame", padding=12)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        ttk.Label(right, text="Evacuation map",
                  style="Heading.TLabel").pack(anchor=tk.W, pady=(0, 8))
        self.evac_canvas = tk.Canvas(
            right, width=680, height=500, bg="#FAFCFD",
            highlightthickness=1, highlightbackground=self.line
        )
        self.evac_canvas.pack(fill=tk.BOTH, expand=True)
        ttk.Label(right, text="Green = recommended evacuation route; green ring = shelter.",
                  style="Muted.TLabel").pack(anchor=tk.W, pady=7)

    def location_risk(self, loc_id):
        score = sum(
            RISK_WEIGHT[e["value"]["severity"]]
            for e in self.table.entries()
            if e["value"]["status"] != "Resolved" and e["value"]["locId"] == loc_id
        )
        score += sum(
            1 for r in ROADS
            if loc_id in (r["a"], r["b"]) and r["id"] in self.blocked_roads
        )
        return score

    @staticmethod
    def risk_label(score):
        if score == 0:
            return "Safe"
        if score <= 2:
            return "Watch"
        if score <= 4:
            return "Warning"
        return "Danger"

    def has_high_report(self, loc_id):
        return any(
            e["value"]["status"] != "Resolved" and e["value"]["locId"] == loc_id
            and e["value"]["severity"] == "High"
            for e in self.table.entries()
        )

    def refresh_evac(self):
        if not hasattr(self, "evac_combo"):
            return
        start = self.selected_node(self.evac_combo)
        options = []
        for sid, sname in SHELTERS.items():
            result = dijkstra(self.graph, self.blocked_roads, start, sid)
            options.append({
                "id": sid, "name": sname, "result": result,
                "flooded": self.has_high_report(sid),
                "risk": self.risk_label(self.location_risk(sid)),
            })
        options.sort(key=lambda o: (
            o["result"] is None, o["flooded"],
            o["result"]["distance"] if o["result"] else 0
        ))
        best = next((o for o in options if o["result"] and not o["flooded"]), None)

        for item in self.evac_tree.get_children():
            self.evac_tree.delete(item)
        for o in options:
            if o["result"] is None:
                state, tag = "Cut off", "bad"
                km = eta = "—"
            else:
                km = o["result"]["distance"]
                eta = f"{round(km * 2)} min"
                if o is best:
                    state, tag = "Recommended", "best"
                elif o["flooded"]:
                    state, tag = "Flooded - avoid", "bad"
                else:
                    state, tag = "Available", ""
            self.evac_tree.insert("", tk.END, tags=(tag,),
                                  values=(o["name"], km, eta, o["risk"], state))

        score = self.location_risk(start)
        self.evac_risk.config(
            text=f"Your area ({LOC_MAP[start]['name']}): {self.risk_label(score)} "
                 f"(risk score {score})."
        )
        path = None
        if best:
            path = best["result"]["path"]
            if len(path) == 1:
                text = f"You are already at a shelter: {best['name']}."
            else:
                route = " → ".join(LOC_MAP[n]["name"] for n in path)
                text = (f"Go to {best['name']}: {best['result']['distance']} km, "
                        f"about {round(best['result']['distance'] * 2)} min.\n{route}")
        elif any(o["result"] for o in options):
            text = ("Every reachable shelter reports severe flooding. Move to higher "
                    "ground and contact emergency services.")
        else:
            text = ("No shelter can be reached on open roads. Stay on a high floor "
                    "and contact emergency services.")
        self.evac_status.config(text=text)
        self.draw_network(self.evac_canvas, path, route_colour="#1F8A4C",
                          shelters=True)

    def parse_road_choice(self):
        choice = self.road_var.get()
        return None if choice == "None" else choice.split(" — ")[0]

    def add_report(self, location, description, severity, loc_id=None,
                   road_id=None, enqueue=True):
        report_id = f"FL{self.next_num:03d}"
        self.next_num += 1

        loc_clean = location.strip()
        if loc_id is None:
            match = next(
                (loc for loc in LOCATIONS
                 if loc["name"].lower() == loc_clean.lower()
                 or loc["id"].lower() == loc_clean.lower()),
                None
            )
            if match:
                loc_id = match["id"]
            else:
                # Dynamic node creation for custom locations outside default list
                new_id = "".join([w[0] for w in loc_clean.split()][:2]).upper()
                if not new_id or new_id in LOC_MAP:
                    new_id = f"X{len(LOCATIONS)+1}"
                
                # Pick random coordinates within bounds on the map canvas
                rx = random.randint(150, 500)
                ry = random.randint(100, 300)
                
                new_loc = {"id": new_id, "name": loc_clean, "x": rx, "y": ry}
                LOCATIONS.append(new_loc)
                LOC_MAP[new_id] = new_loc
                
                # Automatically connect it to the closest existing location to integrate into the graph
                closest = min(LOCATIONS[:-1], key=lambda l: math.hypot(l["x"] - rx, l["y"] - ry))
                dist_km = round(math.hypot(closest["x"] - rx, closest["y"] - ry) / 50.0 + 1.0, 1)
                
                new_road_id = f"{closest['id']}-{new_id}"
                new_road = {"id": new_road_id, "a": closest["id"], "b": new_id, "km": dist_km}
                ROADS.append(new_road)
                ROAD_MAP[new_road_id] = new_road
                
                # Rebuild graph & combo choices dynamically
                self.graph = build_graph()
                loc_id = new_id

        record = {
            "id": report_id,
            "location": loc_clean,
            "locId": loc_id,
            "description": description,
            "severity": severity,
            "status": "Reported",
            "road_id": road_id,
        }
        self.table.put(report_id, record)
        if enqueue:
            self.report_queue.append(report_id)
        return report_id

    def on_submit_report(self):
        location = self.loc_entry.get().strip()
        description = self.desc_text.get("1.0", tk.END).strip()
        severity = self.severity_var.get()

        if not location or not description:
            messagebox.showerror("Missing information",
                                 "Enter both a location and a description.")
            return

        report_id = self.add_report(
            location, description, severity,
            road_id=self.parse_road_choice()
        )
        self.loc_entry.delete(0, tk.END)
        self.desc_text.delete("1.0", tk.END)
        self.road_var.set("None")
        
        # Refresh combobox selections across tabs to include any newly created custom location/roads
        names = [f"{loc['id']} - {loc['name']}" for loc in LOCATIONS]
        if hasattr(self, "from_combo"):
            self.from_combo['values'] = names
            self.to_combo['values'] = names
        if hasattr(self, "evac_combo"):
            self.evac_combo['values'] = names
            
        global ROAD_CHOICES
        ROAD_CHOICES = ["None"] + [
            f"{r['id']} — {LOC_MAP[r['a']]['name']} to {LOC_MAP[r['b']]['name']}"
            for r in ROADS
        ]
        self.road_combo['values'] = ROAD_CHOICES

        self.refresh_all()
        messagebox.showinfo(
            "Report received",
            f"{report_id} has been added to the incoming report queue.\n"
            "If it's a new location, it was dynamically mapped onto the network graph."
        )

    def process_next_report(self):
        if not self.report_queue:
            messagebox.showinfo("Queue empty", "There are no reports waiting for review.")
            return

        report_id = self.report_queue.popleft()
        result = self.table.get(report_id)
        if not result["found"]:
            self.refresh_all()
            return

        record = result["entry"]["value"]
        if record["status"] == "Reported":
            record["status"] = "Verified"
            if record["road_id"]:
                self.sync_blocked_roads()
                message = (
                    f"{report_id} verified. Road {record['road_id']} is now "
                    "blocked in the simulated network."
                )
            else:
                message = (
                    f"{report_id} verified. No affected road was selected, "
                    "so routing is unchanged."
                )
        else:
            message = f"{report_id} was no longer awaiting review."

        self.sync_blocked_roads()
        self.refresh_all()
        messagebox.showinfo("Queue processing", message)

    def delete_selected_report(self):
        selected = self.report_tree.selection()
        if not selected:
            messagebox.showwarning("No selection", "Please select a report from the table to delete.")
            return
        
        values = self.report_tree.item(selected[0], "values")
        report_id = values[0]
        
        if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete report {report_id}?"):
            for bucket in self.table.buckets:
                bucket[:] = [entry for entry in bucket if entry["key"] != report_id]
            self.table.count = max(0, self.table.count - 1)
            
            if report_id in self.report_queue:
                self.report_queue.remove(report_id)
                
            self.sync_blocked_roads()
            self.refresh_all()
            messagebox.showinfo("Deleted", f"Report {report_id} has been removed.")

    def clear_all_reports(self):
        if self.table.count == 0:
            messagebox.showinfo("Already empty", "There are no reports to clear.")
            return
            
        if messagebox.askyesno("Confirm Clear All", "Are you sure you want to clear ALL flood reports? This cannot be undone."):
            self.table.buckets = [[] for _ in range(self.table.size)]
            self.table.count = 0
            self.report_queue.clear()
            self.next_num = 1
            
            self.sync_blocked_roads()
            self.refresh_all()
            messagebox.showinfo("Cleared", "All reports have been successfully cleared.")

    def sync_blocked_roads(self):
        report_blocked = {
            entry["value"]["road_id"]
            for entry in self.table.entries()
            if entry["value"]["status"] == "Verified"
            and entry["value"]["road_id"] is not None
        }
        self.blocked_roads = set(self.manual_blocked_roads) | report_blocked

    def on_lookup_report(self):
        key = self.lookup_entry.get().strip().upper()
        if not key:
            self.lookup_result.config(text="")
            return
        result = self.table.get(key)
        if result["found"]:
            report = result["entry"]["value"]
            self.lookup_result.config(
                text=f"Found in bucket {result['index']} after "
                     f"{result['steps']} step(s): {report['location']} — "
                     f"{report['severity']} — {report['status']}"
            )
        else:
            self.lookup_result.config(
                text=f"{key} not found. Checked {result['steps']} entries "
                     f"in bucket {result['index']}."
            )

    def on_report_double_click(self, event):
        selected = self.report_tree.selection()
        if not selected:
            return
        values = self.report_tree.item(selected[0], "values")
        result = self.table.get(values[0])
        if not result["found"]:
            return
        record = result["entry"]["value"]
        statuses = ["Reported", "Verified", "Resolved"]
        record["status"] = statuses[(statuses.index(record["status"]) + 1) % 3]

        if record["status"] == "Verified" and values[0] in self.report_queue:
            self.report_queue.remove(values[0])
        self.sync_blocked_roads()
        self.refresh_all()

    def change_bucket_size(self):
        self.table.resize(self.bucket_size.get())
        self.refresh_all()

    def toggle_manual_road(self, event):
        selected = self.road_tree.selection()
        if not selected:
            return
        road_id = self.road_tree.item(selected[0], "values")[0]

        if road_id in self.manual_blocked_roads:
            self.manual_blocked_roads.remove(road_id)
        else:
            self.manual_blocked_roads.add(road_id)

        self.sync_blocked_roads()
        self.refresh_all()

    def refresh_all(self):
        entries = self.table.entries()
        reports = [entry["value"] for entry in entries]
        active = [r for r in reports if r["status"] != "Resolved"]
        high_count = sum(r["severity"] == "High" for r in active)

        self.summary.config(
            text=f"Active reports: {len(active)}   High: {high_count}   "
                 f"Blocked roads: {len(self.blocked_roads)}"
        )
        self.next_id_label.config(text=f"Next report ID: FL{self.next_num:03d}")
        self.queue_label.config(text=f"Reports waiting for review: {len(self.report_queue)}")

        for item in self.report_tree.get_children():
            self.report_tree.delete(item)
        reports.sort(key=lambda r: (SEV_RANK[r["severity"]], r["id"]))
        for report in reports:
            self.report_tree.insert(
                "", tk.END,
                values=(
                    report["id"], report["severity"], report["location"],
                    report["road_id"] or "—", report["status"],
                    report["description"]
                )
            )

        self.render_hash_view()
        self.refresh_roads_table()
        self.redraw_map()
        self.refresh_route()
        self.refresh_evac()

    def render_hash_view(self):
        nonempty = sum(bool(bucket) for bucket in self.table.buckets)
        longest = max((len(bucket) for bucket in self.table.buckets), default=0)
        collisions = self.table.count - nonempty
        self.hash_stats.config(
            text=f"Reports: {self.table.count}\n"
                 f"Buckets: {self.table.size}\n"
                 f"Load factor: {self.table.count / self.table.size:.2f}\n"
                 f"Collisions: {collisions}\n"
                 f"Longest chain: {longest}"
        )

        lines = []
        for index, bucket in enumerate(self.table.buckets):
            chain = " → ".join(
                f"[{entry['key']}:{entry['value']['severity']}]"
                for entry in bucket
            )
            lines.append(f"Bucket {index:2d}: {chain if chain else 'empty'}")
        self.bucket_text.delete("1.0", tk.END)
        self.bucket_text.insert("1.0", "\n".join(lines))

        key = self.test_key.get().strip().upper()
        if key:
            result = self.table.get(key)
            self.hash_test_result.config(
                text=f"Hash sum: {HashTable.sum_key(key)}\n"
                     f"Bucket: {result['index']}\n"
                     f"Found: {result['found']} | Steps: {result['steps']}"
            )

    def refresh_roads_table(self):
        for item in self.road_tree.get_children():
            self.road_tree.delete(item)
        for road in ROADS:
            blocked = road["id"] in self.blocked_roads
            manual = road["id"] in self.manual_blocked_roads
            reported = any(
                entry["value"]["status"] == "Verified"
                and entry["value"]["road_id"] == road["id"]
                for entry in self.table.entries()
            )
            sources = []
            if manual:
                sources.append("Manual")
            if reported:
                sources.append("Report")
            segment = f"{LOC_MAP[road['a']]['name']} — {LOC_MAP[road['b']]['name']}"
            self.road_tree.insert(
                "", tk.END,
                values=(
                    road["id"], segment, road["km"],
                    "BLOCKED" if blocked else "OPEN",
                    " + ".join(sources) if sources else "—"
                )
            )

    def selected_node(self, combo):
        return combo.get().split(" - ")[0]

    def refresh_route(self):
        if not hasattr(self, "from_combo"):
            return
        start = self.selected_node(self.from_combo)
        goal = self.selected_node(self.to_combo)
        if start == goal:
            self.route_result.config(text="Choose two different locations.")
            self.redraw_map()
            return

        result = dijkstra(self.graph, self.blocked_roads, start, goal)
        if result is None:
            self.route_result.config(text="No open route is available between these locations.")
        else:
            names = " → ".join(LOC_MAP[node]["name"] for node in result["path"])
            self.route_result.config(
                text=f"Recommended shortest open route: {result['distance']} km\n{names}"
            )
        self.redraw_map()

    def redraw_map(self):
        path = None
        if hasattr(self, "from_combo"):
            start = self.selected_node(self.from_combo)
            goal = self.selected_node(self.to_combo)
            if start != goal:
                result = dijkstra(self.graph, self.blocked_roads, start, goal)
                if result:
                    path = result["path"]
        self.draw_network(self.canvas, path)

    def draw_network(self, canvas, route_path=None, route_colour=None,
                     shelters=False):
        route_colour = route_colour or self.primary
        canvas.delete("all")

        for road in ROADS:
            a, b = LOC_MAP[road["a"]], LOC_MAP[road["b"]]
            blocked = road["id"] in self.blocked_roads
            canvas.create_line(
                a["x"], a["y"], b["x"], b["y"],
                fill="#B3341A" if blocked else "#8CA1AF",
                width=3 if blocked else 2,
                dash=(5, 4) if blocked else None
            )
            canvas.create_text(
                (a["x"] + b["x"]) / 2, (a["y"] + b["y"]) / 2,
                text=f"{road['km']} km", font=("Consolas", 8), fill=self.muted
            )

        if route_path:
            for n1, n2 in zip(route_path, route_path[1:]):
                a, b = LOC_MAP[n1], LOC_MAP[n2]
                canvas.create_line(a["x"], a["y"], b["x"], b["y"],
                                   fill=route_colour, width=6)

        location_reports = {}
        for entry in self.table.entries():
            report = entry["value"]
            if report["status"] != "Resolved" and report["locId"]:
                info = location_reports.setdefault(
                    report["locId"], {"count": 0, "severity": report["severity"]}
                )
                info["count"] += 1
                if SEV_RANK[report["severity"]] < SEV_RANK[info["severity"]]:
                    info["severity"] = report["severity"]

        for loc in LOCATIONS:
            x, y = loc["x"], loc["y"]
            fill, outline = "#FFFFFF", self.ink
            if loc["id"] in location_reports:
                severity = location_reports[loc["id"]]["severity"]
                if severity == "High":
                    fill, outline = "#F8DDD6", "#B3341A"
                elif severity == "Medium":
                    fill, outline = "#F6E8C6", "#7D5200"
                else:
                    fill, outline = "#D9EDE2", "#1F6140"

            if shelters and loc["id"] in SHELTERS:
                canvas.create_oval(x - 22, y - 22, x + 22, y + 22,
                                   outline="#1F8A4C", width=2, dash=(3, 3))
            canvas.create_oval(x - 15, y - 15, x + 15, y + 15,
                               fill=fill, outline=outline, width=2)
            label = (str(location_reports[loc["id"]]["count"])
                     if loc["id"] in location_reports else loc["id"])
            canvas.create_text(x, y, text=label, font=("Segoe UI", 9, "bold"),
                               fill=outline)
            canvas.create_text(x, y + 28, text=loc["name"],
                               font=("Segoe UI", 8, "bold"), fill=self.ink)
            if shelters and loc["id"] in SHELTERS:
                canvas.create_text(x, y + 40, text="SHELTER",
                                   font=("Segoe UI", 7, "bold"), fill="#1F8A4C")


if __name__ == "__main__":
    app = FloodWatchApp()
    app.mainloop()