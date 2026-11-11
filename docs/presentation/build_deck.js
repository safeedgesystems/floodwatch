// FloodWatch — BDSA209 semester project presentation (10 slides).
const pptxgen = require("pptxgenjs");
const sharp = require("sharp");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const fa = require("react-icons/fa");
const { applyTheme } = require("/root/.claude/skills/synced/9f185c37-d7b7-4c3b-bac6-a66b71331c8c_0b41b3ba-9cbb-4790-bc57-5f444da8d80f/pptx/scripts/apply_theme.js");

const DOCS = "/home/claude/floodwatch/docs";
const IMG = "/home/claude/deckbuild/img";
const OUT = `${DOCS}/presentation/FloodWatch_Presentation.pptx`;
const RES = require(`${DOCS}/benchmarks/results.json`);

const THEME = {
  name: "FloodWatch",
  headFontFace: "Calibri",
  bodyFontFace: "Calibri",
  colors: {
    // Graphite + Amber
    dk1: "121417", lt1: "FFFFFF", dk2: "16191D", lt2: "F3F4F6",
    accent1: "B97508", accent2: "EF4444", accent3: "16A34A", accent4: "EA580C",
    accent5: "F5A524", accent6: "4A525C", hlink: "B97508", folHlink: "4A525C",
  },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.title = "FloodWatch — Flood Hazard Reporting & Safe Route Recommendation";
pres.subject = "BDSA209 Data Structures and Algorithms — Semester Project";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const W = 13.333, H = 7.5, M = 0.6;

// ---------------------------------------------------------------- helpers
async function icon(Comp, color, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: `#${color}`, size: String(size) }));
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}
async function fit(path, x, y, maxW, maxH, opts = {}) {
  const m = await sharp(path).metadata();
  const r = m.width / m.height;
  let w = maxW, h = maxW / r;
  if (h > maxH) { h = maxH; w = maxH * r; }
  const ox = opts.align === "left" ? 0 : (maxW - w) / 2;
  const oy = opts.valign === "top" ? 0 : (maxH - h) / 2;
  return { path, x: x + ox, y: y + oy, w, h };
}
const shadow = () => ({ type: "outer", color: "121417", opacity: 0.18, blur: 8, offset: 3, angle: 90 });

// ---------------------------------------------------------------- layouts
pres.defineSlideMaster({
  title: "DARK",
  background: { color: C.text2 },
  objects: [],
  slideNumber: { x: W - 1.0, y: H - 0.5, w: 0.5, h: 0.3, color: "8B949E", fontSize: 10, align: "right" },
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.35, w: W - 2 * M, h: 0.8,
      fontSize: 34, bold: true, color: C.text1, valign: "middle", margin: 0 }, text: "" } },
    { text: { text: "FloodWatch · BDSA209 Data Structures & Algorithms", options: {
      x: M, y: H - 0.5, w: 7, h: 0.3, fontSize: 10, color: "8B949E", margin: 0 } } },
  ],
  slideNumber: { x: W - 1.1, y: H - 0.5, w: 0.5, h: 0.3, color: "8B949E", fontSize: 10, align: "right" },
});

async function main() {
  const I = {
    rain: await icon(fa.FaCloudShowersHeavy, "F5A524"), road: await icon(fa.FaRoad, "EF4444"),
    shelter: await icon(fa.FaHospital, "16A34A"), hash: await icon(fa.FaHashtag, "FFFFFF"),
    queue: await icon(fa.FaStream, "FFFFFF"), heap: await icon(fa.FaSitemap, "FFFFFF"),
    route: await icon(fa.FaRoute, "FFFFFF"), python: await icon(fa.FaPython, "FFFFFF"),
    check: await icon(fa.FaCheckCircle, "16A34A"), bolt: await icon(fa.FaBolt, "D98A0B"),
    warn: await icon(fa.FaExclamationTriangle, "EA580C"), db: await icon(fa.FaDatabase, "FFFFFF"),
    globe: await icon(fa.FaGlobeAfrica, "FFFFFF"), users: await icon(fa.FaUsers, "F5A524"), map: await icon(fa.FaMapMarkedAlt, "FFFFFF"), usersW: await icon(fa.FaUsers, "FFFFFF"),
    flask: await icon(fa.FaFlask, "D98A0B"), arrow: await icon(fa.FaArrowRight, "F5A524"),
  };

  // ============================================================ 1. Title
  pres.addSection({ title: "Introduction" });
  let s = pres.addSlide({ masterName: "DARK", sectionTitle: "Introduction" });
  s.addImage({ ...(await fit(`${IMG}/landing.png`, 6.7, 0.9, 6.2, 5.6)), objectName: "Landing screenshot",
    altText: "FloodWatch landing page", rounding: false, shadow: { type: "outer", color: "000000", opacity: 0.5, blur: 18, offset: 6, angle: 90 } });
  s.addText("BDSA209 · DATA STRUCTURES & ALGORITHMS · SEMESTER PROJECT", { isTextBox: true, x: M, y: 1.0, w: 6, h: 0.35,
    fontSize: 12, bold: true, color: C.accent5, charSpacing: 1, margin: 0, objectName: "Course" });
  s.addText("FloodWatch", { isTextBox: true, x: M, y: 1.45, w: 6, h: 1.1, fontSize: 60, bold: true, color: C.background1, margin: 0, objectName: "Title" });
  s.addText("Flood hazard reporting & safe route recommendation", { isTextBox: true, x: M, y: 2.55, w: 5.8, h: 0.9,
    fontSize: 22, color: "C3C9D1", margin: 0, objectName: "Subtitle" });
  s.addText("Hash table · FIFO queue · Binary min-heap · Dijkstra's algorithm", { isTextBox: true, x: M, y: 3.55, w: 5.8, h: 0.4,
    fontSize: 14, italic: true, color: C.accent5, margin: 0, objectName: "Tagline" });
  s.addImage({ data: I.users, x: M, y: 4.7, w: 0.38, h: 0.38, objectName: "Team icon" });
  s.addText([
    { text: "Team members", options: { bold: true, color: C.background1, breakLine: true } },
    { text: "[Add team member names and index numbers]", options: { color: "C3C9D1" } },
  ], { isTextBox: true, x: M + 0.55, y: 4.6, w: 5.4, h: 0.8, fontSize: 15, margin: 0, valign: "top", objectName: "Team members" });
  s.addText("November 2026", { isTextBox: true, x: M, y: 5.9, w: 4, h: 0.35, fontSize: 13, color: "8B949E", margin: 0, objectName: "Date" });
  s.addNotes("Introduce the team and the project: FloodWatch turns community flood reports into verified road closures and the shortest safe route across the city. Everything you'll see is built on four data structures and algorithms we implemented ourselves in Python.");

  // ============================================================ 2. Problem
  pres.addSection({ title: "Problem & concept" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem & concept" });
  s.addText("When streets flood, people need three answers fast", { placeholder: "title" });
  const probs = [
    [I.rain, "Where is it flooded?", "Reports are scattered across calls, chats and social media — there is no single trusted picture."],
    [I.road, "Which roads still work?", "The usual shortest route may pass straight through flood water. Driving into floods is a leading cause of flood injuries."],
    [I.shelter, "Where can I reach safety?", "The nearest shelter is useless if every road to it is closed — or if the shelter itself is flooded."],
  ];
  probs.forEach(([ic, h, b], i) => {
    const x = M + i * 4.1;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.5, w: 3.8, h: 3.3, rectRadius: 0.12, fill: { color: C.background2 },
      line: { color: C.background2 }, objectName: `Problem card ${i + 1}` });
    s.addShape(pres.shapes.OVAL, { x: x + 0.35, y: 1.85, w: 0.85, h: 0.85, fill: { color: C.background1 }, line: { color: C.background1 }, objectName: `Problem icon bg ${i + 1}` });
    s.addImage({ data: ic, x: x + 0.55, y: 2.05, w: 0.45, h: 0.45, objectName: `Problem icon ${i + 1}` });
    s.addText(h, { isTextBox: true, x: x + 0.35, y: 2.9, w: 3.2, h: 0.5, fontSize: 20, bold: true, color: C.text1, margin: 0 });
    s.addText(b, { isTextBox: true, x: x + 0.35, y: 3.45, w: 3.15, h: 1.25, fontSize: 14, color: C.accent6, margin: 0, valign: "top" });
  });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 5.15, w: W - 2 * M, h: 1.5, rectRadius: 0.12, fill: { color: C.text2 }, line: { color: C.text2 }, objectName: "Solution banner" });
  s.addText([
    { text: "Our solution: ", options: { bold: true, color: C.accent5 } },
    { text: "residents report flooding at their GPS location → an admin verifies in arrival order → verified floods close nearby roads in a graph of Ghana's real road network → our Dijkstra finds the shortest open route, reroutes live, and steers people to the nearest reachable safe place.", options: { color: C.background1 } },
  ], { isTextBox: true, x: M + 0.4, y: 5.25, w: W - 2 * M - 0.8, h: 1.3, fontSize: 16, margin: 0, valign: "middle", objectName: "Solution text" });
  s.addNotes("Why it matters: time and trust. Routes over open roads avoid the trial-and-error of driving into flooded streets; verification stops one false report from closing a road for everyone.");

  // ============================================================ 3. Concept overview
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem & concept" });
  s.addText("Concept: four structures turn reports into safe routes", { placeholder: "title" });
  s.addImage({ ...(await fit(`${DOCS}/diagrams/10_concept_flow_lr.png`, M, 1.35, W - 2 * M, 1.3)), objectName: "Concept flow", altText: "Report to safe route flow" });
  const concepts = [
    [I.hash, C.accent1, "Hash table", "Stores every report by ID with separate chaining — instant lookup."],
    [I.queue, C.accent4, "FIFO queue", "Admin verification in arrival order — fair, O(1) per step."],
    [I.heap, C.accent6, "Binary min-heap", "Hands Dijkstra the closest unvisited place in O(log n)."],
    [I.route, C.accent2, "Graph + Dijkstra", "Locations = vertices, roads = weighted edges; skips closed roads."],
  ];
  concepts.forEach(([ic, col, h, b], i) => {
    const x = M + (i % 2) * 6.15, y = 3.05 + Math.floor(i / 2) * 1.75;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 5.9, h: 1.5, rectRadius: 0.1, fill: { color: C.background1 },
      line: { color: "DDE1E6", width: 1 }, shadow: shadow(), objectName: `Concept card ${i + 1}` });
    s.addShape(pres.shapes.OVAL, { x: x + 0.3, y: y + 0.35, w: 0.8, h: 0.8, fill: { color: col }, line: { color: col }, objectName: `Concept icon bg ${i + 1}` });
    s.addImage({ data: ic, x: x + 0.5, y: y + 0.55, w: 0.4, h: 0.4, objectName: `Concept icon ${i + 1}` });
    s.addText(h, { isTextBox: true, x: x + 1.35, y: y + 0.2, w: 4.3, h: 0.45, fontSize: 19, bold: true, color: C.text1, margin: 0 });
    s.addText(b, { isTextBox: true, x: x + 1.35, y: y + 0.68, w: 4.35, h: 0.7, fontSize: 14, color: C.accent6, margin: 0, valign: "top" });
  });
  s.addNotes("Walk the pipeline left to right. A report is stored in the hash table and enqueued. The admin dequeues the oldest report and verifies it; its road joins the closed-road set. Dijkstra, driven by our min-heap, then computes the shortest route using only open roads.");

  // ============================================================ 4. Data structures
  pres.addSection({ title: "Design" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Design" });
  s.addText("Data structures: what we built and why", { placeholder: "title" });
  s.addImage({ ...(await fit(`${DOCS}/diagrams/05_hash_table.png`, M, 1.3, 6.6, 3.75)), objectName: "Hash table diagram", altText: "Hash table with separate chaining" });
  s.addText([
    { text: "Hash table — separate chaining", options: { bold: true, color: C.text1, breakLine: true } },
    { text: "Hash = Σ character codes mod buckets. Collisions append to the bucket's chain, so it never fills and deletes are simple.", options: { color: C.accent6 } },
  ], { isTextBox: true, x: M, y: 5.15, w: 6.6, h: 1.25, fontSize: 14, margin: 0, valign: "top", objectName: "Hash caption" });
  s.addImage({ ...(await fit(`${DOCS}/diagrams/06_queue.png`, 7.55, 1.35, 5.2, 1.2)), objectName: "Queue diagram", altText: "Linked list queue" });
  s.addText([
    { text: "FIFO queue — singly linked list", options: { bold: true, color: C.text1, breakLine: true } },
    { text: "Head & tail pointers: enqueue and dequeue are O(1). A Python list.pop(0) would be O(n).", options: { color: C.accent6 } },
  ], { isTextBox: true, x: 7.55, y: 2.6, w: 5.2, h: 0.95, fontSize: 14, margin: 0, valign: "top", objectName: "Queue caption" });
  s.addImage({ ...(await fit(`${DOCS}/diagrams/07_heap.png`, 7.55, 3.6, 5.2, 2.15)), objectName: "Heap diagram", altText: "Binary min-heap" });
  s.addText([
    { text: "Binary min-heap — array-backed", options: { bold: true, color: C.text1, breakLine: true } },
    { text: "Push/pop O(log n). Lazy deletion replaces decrease-key.", options: { color: C.accent6 } },
  ], { isTextBox: true, x: 7.55, y: 5.85, w: 5.2, h: 0.8, fontSize: 14, margin: 0, valign: "top", objectName: "Heap caption" });
  s.addNotes("Hash: FL001 sums to 291, 291 mod 8 = 3. FL010 has the same characters so it collides into bucket 3 and is chained. Queue: linked list because Python list.pop(0) shifts every element. Heap: array representation, children at 2i+1 and 2i+2; we push a node again when we find a shorter distance and skip stale copies when popped. Road graph uses an adjacency list because road networks are sparse.");

  // ============================================================ 5. Algorithm
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Design" });
  s.addText("Algorithm design: Dijkstra over open roads", { placeholder: "title" });
  const code = [
    "Dijkstra(G, closed, s, g):",
    "  dist[v] ← ∞ for all v;  dist[s] ← 0",
    "  heap.PUSH(0, s)",
    "  while heap not empty:",
    "    (d, u) ← heap.POP()            # closest",
    "    if d > dist[u]: continue       # stale",
    "    if u = g: break                # early exit",
    "    for (u→v, km, road) in G[u]:",
    "      if road ∈ closed: continue   # flooded",
    "      if d + km < dist[v]:         # relax",
    "        dist[v] ← d + km; prev[v] ← u",
    "        heap.PUSH(dist[v], v)",
    "  rebuild path g → s via prev[]",
  ].join("\n");
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 1.3, w: 6.5, h: 5.35, rectRadius: 0.1, fill: { color: C.text2 }, line: { color: C.text2 }, objectName: "Pseudocode card" });
  s.addText(code, { isTextBox: true, x: M + 0.3, y: 1.45, w: 6.0, h: 5.05, fontFace: "Courier New", fontSize: 14, color: "F1F3F5", margin: 0, valign: "middle", objectName: "Pseudocode" });
  // complexity table
  const hdr = (t) => ({ text: t, options: { bold: true, color: HEX.accent5, fill: { color: HEX.dk1 } } });
  const rows = [
    [hdr("Operation"), hdr("Structure"), hdr("Time")],
    ["Submit report", "Hash put + enqueue", "O(1) avg"],
    ["Lookup by ID", "Hash get", "O(1 + α)"],
    ["Verify next", "Queue dequeue", "O(1)"],
    ["Heap push / pop", "Binary heap", "O(log n)"],
    ["Shortest route", "Dijkstra + heap", "O((V+E) log V)"],
    ["Evacuation", "Dijkstra × shelters", "O(S·(V+E) log V)"],
  ];
  s.addTable(rows, { x: 7.4, y: 1.3, w: 5.33, colW: [1.75, 1.95, 1.63], fontSize: 13, color: HEX.dk1,
    border: { type: "solid", pt: 0.75, color: "DDE1E6" }, rowH: 0.42, valign: "middle", objectName: "Complexity table" });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 7.4, y: 4.45, w: 5.33, h: 2.2, rectRadius: 0.1, fill: { color: C.background2 }, line: { color: C.background2 }, objectName: "Worked example card" });
  s.addText([
    { text: "Worked example (demo city)", options: { bold: true, color: C.text1, breakLine: true } },
    { text: "Riverside → Hillcrest with RS-MS and HJ-HC closed", options: { color: C.accent6, breakLine: true } },
    { text: "RS → Old Bridge → Market Sq → HC = 6.9 km", options: { bold: true, color: C.accent1, breakLine: true } },
    { text: "6 nodes settled · 8 heap pushes · ~14 min at 30 km/h", options: { color: C.accent6, breakLine: true } },
    { text: "Why not BFS? Roads have different lengths. Why not Bellman-Ford? No negative weights — O(V·E) is unnecessary.", options: { color: C.accent6, fontSize: 12 } },
  ], { isTextBox: true, x: 7.65, y: 4.55, w: 4.85, h: 2.0, fontSize: 14, margin: 0, valign: "top", paraSpaceAfter: 3, objectName: "Worked example" });
  s.addNotes("Each edge is relaxed at most once, each relaxation is one O(log V) heap push, so Dijkstra is O((V+E) log V). The early exit stops as soon as the destination is settled. The worked example matches the app and our automated test.");

  // ============================================================ 6. Implementation
  pres.addSection({ title: "Implementation & results" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Implementation & results" });
  s.addText("Implementation: Python core, live web interface", { placeholder: "title" });
  s.addImage({ ...(await fit(`${DOCS}/diagrams/08_architecture.png`, M, 1.3, W - 2 * M, 2.4)), objectName: "Architecture diagram", altText: "Architecture" });
  const mods = [
    [I.python, C.accent1, "structures.py", "HashTable, MinHeap, FIFOQueue, binary search — written from scratch"],
    [I.route, C.accent2, "graph.py", "Adjacency list + Dijkstra with step trace — one function for both maps"],
    [I.db, C.accent6, "engine.py · store.py", "Rules: submit, verify, close roads, evacuate · SQLite persistence"],
    [I.globe, C.accent3, "geo.py", "Ghana map: spatial hashing, flood zones, safe point, live reroute"],
    [I.map, C.accent4, "build_ghana_graph.py", "OpenStreetMap → 45,928 junctions, 76,620 km of road"],
    [I.usersW, C.text1, "main.py · web UI", "FastAPI input & validation; React + Leaflet only display results"],
  ];
  mods.forEach(([ic, col, h, b], i) => {
    const x = M + (i % 3) * 4.1, y = 4.0 + Math.floor(i / 3) * 1.35;
    s.addShape(pres.shapes.OVAL, { x, y: y + 0.1, w: 0.62, h: 0.62, fill: { color: col }, line: { color: col }, objectName: `Module icon bg ${i + 1}` });
    s.addImage({ data: ic, x: x + 0.15, y: y + 0.25, w: 0.32, h: 0.32, objectName: `Module icon ${i + 1}` });
    s.addText(h, { isTextBox: true, x: x + 0.8, y, w: 3.15, h: 0.4, fontSize: 15, bold: true, fontFace: "Courier New", color: C.text1, margin: 0, fit: "shrink" });
    s.addText(b, { isTextBox: true, x: x + 0.8, y: y + 0.42, w: 3.15, h: 0.85, fontSize: 13, color: C.accent6, margin: 0, valign: "top" });
  });
  s.addNotes("Language: Python 3 for all algorithms and data structures, as required. Input -> process -> output: main.py validates input, engine.py and structures.py process, and the web interface only displays results. The Ghana map reuses the exact same dijkstra() and HashTable - only the data is real. The original Tkinter version is included as an all-Python fallback.");

  // ============================================================ 7. Testing
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Implementation & results" });
  s.addText("Testing: 46 of 46 automated tests pass", { placeholder: "title" });
  const stats = [["46/46", "tests passing", C.accent3], ["24", "edge-case tests", C.accent1], ["200", "random graphs cross-checked", C.accent4]];
  stats.forEach(([n, l, col], i) => {
    const x = M + i * 4.1;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.35, w: 3.8, h: 1.7, rectRadius: 0.12, fill: { color: C.background2 }, line: { color: C.background2 }, objectName: `Stat ${i + 1}` });
    s.addText(n, { isTextBox: true, x: x + 0.3, y: 1.45, w: 3.3, h: 0.95, fontSize: 52, bold: true, color: col, margin: 0, objectName: `Stat value ${i + 1}` });
    s.addText(l, { isTextBox: true, x: x + 0.3, y: 2.4, w: 3.3, h: 0.45, fontSize: 15, color: C.accent6, margin: 0 });
  });
  const groups = [
    ["Data structures", "1-bucket table (all collide) · empty-table lookup · remove mid-chain & queue tail · heap vs Python heapq on 2,000 values"],
    ["Routing", "Start = destination · isolated start · every road closed · unknown place · detour around a closed shortcut"],
    ["Correctness proof-by-test", "Dijkstra matched an independent reference on 200 random graphs for every destination — every path step uses an open road"],
    ["Application", "Invalid input rejected (422/400) · admin-only actions (401) · two reports on one road · IDs never reused · state survives restart"],
    ["Real Ghana network", "Accra→Kumasi valid path · verify flood → reroute → resolve restores · flooded destination → safe point · start inside a flood"],
  ];
  groups.forEach(([h, b], i) => {
    const y = 3.3 + i * 0.68;
    s.addImage({ data: I.check, x: M, y: y + 0.05, w: 0.36, h: 0.36, objectName: `Check ${i + 1}` });
    s.addText([{ text: h + ":  ", options: { bold: true, color: C.text1 } }, { text: b, options: { color: C.accent6 } }],
      { isTextBox: true, x: M + 0.55, y, w: W - 2 * M - 0.55, h: 0.64, fontSize: 14, margin: 0, valign: "top", objectName: `Test group ${i + 1}` });
  });
  s.addNotes("All 37 tests run in under a second with pytest. Highlight the randomised check: we compared our Dijkstra against an independent implementation on 200 random graphs — distances matched for every destination. Full results table is in docs/TEST_REPORT.md.");

  // ============================================================ 8. Performance
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Implementation & results" });
  s.addText("Performance: the heap and queue scale as Big-O predicts", { placeholder: "title" });
  const dj = RES.dijkstra;
  const axis = { catAxisLabelColor: "4A525C", valAxisLabelColor: "4A525C", catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
    catAxisLabelFontSize: 11, valAxisLabelFontSize: 11, valGridLine: { color: "E8EBEE", size: 0.75 }, catGridLine: { style: "none" },
    legendFontFace: "+mn-lt", legendFontSize: 11, legendColor: "4A525C", titleFontFace: "+mn-lt", titleColor: HEX.dk1, titleFontSize: 14 };
  s.addChart(pres.charts.LINE, [
    { name: "Dijkstra + MinHeap", labels: dj.map((r) => String(r.V)), values: dj.map((r) => r.heap_ms) },
    { name: "Naive O(V²) scan", labels: dj.map((r) => String(r.V)), values: dj.map((r) => r.naive_ms) },
  ], { x: M, y: 1.3, w: 6.0, h: 3.9, ...axis, chartColors: ["D98A0B", HEX.accent2], lineSize: 2.5, lineDataSymbolSize: 7,
    showTitle: true, title: "Route query time (ms, log scale) vs locations", valAxisLogScaleBase: 10, showLegend: true, legendPos: "b",
    catAxisTitle: "Locations (V)", showCatAxisTitle: true, catAxisTitleColor: "4A525C", catAxisTitleFontSize: 11, objectName: "Dijkstra chart" });
  const q = RES.queue;
  s.addChart(pres.charts.LINE, [
    { name: "Linked-list queue", labels: q.map((r) => r.N.toLocaleString("en-US")), values: q.map((r) => r.linked_ms) },
    { name: "list.pop(0)", labels: q.map((r) => r.N.toLocaleString("en-US")), values: q.map((r) => r.list_ms) },
  ], { x: 6.75, y: 1.3, w: 6.0, h: 3.9, ...axis, chartColors: ["D98A0B", HEX.accent2], lineSize: 2.5, lineDataSymbolSize: 7,
    showTitle: true, title: "Draining N reports from the queue (ms)", showLegend: true, legendPos: "b",
    catAxisTitle: "Reports (N)", showCatAxisTitle: true, catAxisTitleColor: "4A525C", catAxisTitleFontSize: 11, objectName: "Queue chart" });
  const big = dj[dj.length - 1];
  const callouts = [
    [I.bolt, `${big.speedup}× faster`, `Heap vs naive Dijkstra at ${big.V.toLocaleString("en-US")} locations (${big.heap_ms.toFixed(1)} ms vs ${big.naive_ms.toFixed(0)} ms)`],
    [I.bolt, "151 ms", "Accra → Tamale (564 km) on Ghana's real network: 45,928 junctions, same Dijkstra"],
    [I.warn, "28 buckets used", "Char-sum hash on 2,000 FLxxxx IDs, even with 4,001 buckets: 55 probes per lookup. Fix: polynomial hash"],
  ];
  callouts.forEach(([ic, h, b], i) => {
    const x = M + i * 4.1;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 5.4, w: 3.8, h: 1.3, rectRadius: 0.1, fill: { color: C.background2 }, line: { color: C.background2 }, objectName: `Perf callout ${i + 1}` });
    s.addImage({ data: ic, x: x + 0.25, y: 5.6, w: 0.4, h: 0.4, objectName: `Perf icon ${i + 1}` });
    s.addText(h, { isTextBox: true, x: x + 0.8, y: 5.52, w: 2.85, h: 0.45, fontSize: 18, bold: true, color: i === 2 ? C.accent4 : C.accent1, margin: 0 });
    s.addText(b, { isTextBox: true, x: x + 0.25, y: 6.02, w: 3.4, h: 0.62, fontSize: 11.5, color: C.accent6, margin: 0, valign: "top" });
  });
  s.addNotes("Honest observations: below about 100 locations the naive version is just as fast because the heap has overhead - the heap pays off as the city grows. Same for the queue: list.pop(0) wins at 1,000 items, loses badly at 100,000 (22x). On the real Ghana network a city trip settles about 600 junctions in 4 ms; Accra to Tamale settles 38,000 in 151 ms. Key finding: our simple char-sum hash only ever produces 28 distinct buckets for IDs like FL0001 because the digits always sum to a narrow range. Fine at demo scale, but a polynomial hash is the recommended fix.");

  // ============================================================ 9. Demo screenshots
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Implementation & results" });
  s.addText("Demo: the working application", { placeholder: "title" });
  const shots = [["ghana", "Ghana Live Map — real roads, live reroute"], ["dashboard", "Command Center — KPIs & activity"],
    ["routing", "Simulation — animated Dijkstra"], ["internals", "Under the Hood — live hash table & queue"]];
  for (let i = 0; i < 4; i++) {
    const [f, cap] = shots[i];
    const x = M + (i % 2) * 6.15, y = 1.3 + Math.floor(i / 2) * 2.85;
    s.addImage({ path: `${IMG}/${f}.png`, x, y, w: 3.8, h: 2.375, shadow: shadow(), objectName: `Screenshot ${f}`, altText: cap });
    s.addText(cap.split(" — ")[0], { isTextBox: true, x: x + 4.0, y: y + 0.55, w: 1.95, h: 0.5, fontSize: 17, bold: true, color: C.text1, margin: 0 });
    s.addText(cap.split(" — ")[1], { isTextBox: true, x: x + 4.0, y: y + 1.05, w: 1.95, h: 0.9, fontSize: 14, color: C.accent6, margin: 0, valign: "top" });
  }
  s.addNotes("Switch to the live demo: on the Ghana map, route from My location to Korle Bu; report a flood on that route, verify it as admin and watch the route change live. Then show the simulation's Dijkstra replay and the hash-table probe. If the Wi-Fi is weak, press Offline on the map.");

  // ============================================================ 10. Conclusion
  pres.addSection({ title: "Conclusion" });
  s = pres.addSlide({ masterName: "DARK", sectionTitle: "Conclusion" });
  s.addText("Conclusion & future improvements", { isTextBox: true, x: M, y: 0.55, w: W - 2 * M, h: 0.8, fontSize: 36, bold: true, color: C.background1, margin: 0, objectName: "Conclusion title" });
  s.addText("What we delivered", { isTextBox: true, x: M, y: 1.65, w: 5.8, h: 0.45, fontSize: 20, bold: true, color: C.accent5, margin: 0 });
  s.addText([
    { text: "A working flood-reporting and routing system built on our own hash table, queue, min-heap and Dijkstra", options: { bullet: true, breakLine: true } },
    { text: "Correctness shown by 46 passing tests incl. 200 randomised graphs", options: { bullet: true, breakLine: true } },
    { text: "Efficiency measured: heap Dijkstra 33.6× faster at 5,000 locations", options: { bullet: true, breakLine: true } },
    { text: "Real Ghana road network (76,620 km): GPS reporting, flood-aware routing, live rerouting", options: { bullet: true } },
  ], { isTextBox: true, x: M, y: 2.2, w: 5.8, h: 3.4, fontSize: 16, color: "F1F3F5", margin: 0, valign: "top", paraSpaceAfter: 10, objectName: "Delivered list" });
  s.addText("Next steps", { isTextBox: true, x: 7.0, y: 1.65, w: 5.7, h: 0.45, fontSize: 20, bold: true, color: C.accent5, margin: 0 });
  const nexts = [
    ["Polynomial hash for reports", "already used for the map indexes; add auto-resize"],
    ["A* search", "straight-line heuristic to settle fewer nodes"],
    ["Residential streets", "full street detail for Accra & Kumasi"],
    ["Flood depth weights", "slow roads instead of only open/closed"],
    ["SMS / USSD reporting", "for residents without smartphones"],
  ];
  nexts.forEach(([h, b], i) => {
    const y = 2.2 + i * 0.72;
    s.addImage({ data: I.arrow, x: 7.0, y: y + 0.07, w: 0.3, h: 0.3, objectName: `Next icon ${i + 1}` });
    s.addText([{ text: h, options: { bold: true, color: C.background1 } }, { text: " — " + b, options: { color: "C3C9D1" } }],
      { isTextBox: true, x: 7.45, y, w: 5.3, h: 0.62, fontSize: 15, margin: 0, valign: "top", objectName: `Next step ${i + 1}` });
  });
  s.addText("Thank you — questions?", { isTextBox: true, x: M, y: 6.1, w: 8, h: 0.6, fontSize: 24, bold: true, color: C.accent5, margin: 0, objectName: "Thanks" });
  s.addNotes("Close with the measured hash finding as an example of analysis leading to an improvement. Likely questions: why separate chaining (no tombstones, never full), why lazy deletion (simpler than decrease-key, same Big-O), why a linked list for the queue (O(1) dequeue), why Dijkstra not BFS (weighted roads).");

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
}
main().catch((e) => { console.error(e); process.exit(1); });
