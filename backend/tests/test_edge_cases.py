"""Edge-case and correctness tests (assignment Step 3: 'test using various
inputs, including edge cases'). Each test name states the case it covers."""
import heapq
import importlib
import itertools
import random

import pytest
from fastapi.testclient import TestClient

from app.engine import FloodWatchEngine
from app.graph import build_graph, connectivity, dijkstra
from app.seed import SEED_LOCATIONS, SEED_ROADS
from app.store import Store
from app.structures import FIFOQueue, HashTable, MinHeap

ADMIN = {"X-Admin-Token": "test-token"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FLOODWATCH_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("FLOODWATCH_ADMIN_TOKEN", "test-token")
    monkeypatch.setenv("FLOODWATCH_STATIC", str(tmp_path / "nostatic"))
    monkeypatch.setenv("FLOODWATCH_DISABLE_GEO", "1")   # Ghana map has its own tests
    monkeypatch.setenv("FLOODWATCH_RATE_LIMIT", "1000")
    import app.main as main
    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c


# ------------------------------------------------------------------ hash table
def test_hash_single_bucket_everything_collides():
    t = HashTable(1)
    keys = [f"FL{i:03d}" for i in range(50)]
    for k in keys:
        t.put(k, k)
    assert t.stats()["longestChain"] == 50 and t.stats()["collisions"] == 49
    assert t.get("FL049")["steps"] == 50          # worst case: walk whole chain
    assert all(t.get(k)["value"] == k for k in keys)


def test_hash_lookup_on_empty_table():
    t = HashTable(8)
    r = t.get("FL001")
    assert not r["found"] and r["steps"] == 0 and r["visited"] == []


def test_hash_remove_middle_of_chain_keeps_others():
    t = HashTable(1)
    for k in ("A", "B", "C"):
        t.put(k, k)
    assert t.remove("B") and [t.get(k)["found"] for k in "ABC"] == [True, False, True]


def test_hash_rejects_zero_size():
    with pytest.raises(ValueError):
        HashTable(0)


# ------------------------------------------------------------------ min-heap
def test_heap_single_and_duplicate_priorities():
    h = MinHeap()
    h.push(1, "only")
    assert h.pop() == (1, "only") and h.pop() is None
    for v in "abc":
        h.push(5, v)
    assert sorted(h.pop()[1] for _ in range(3)) == ["a", "b", "c"]


def test_heap_matches_heapq_on_random_data():
    rng = random.Random(42)
    data = [rng.uniform(0, 1000) for _ in range(2000)]
    h = MinHeap()
    for x in data:
        h.push(x, None)
    assert [h.pop()[0] for _ in data] == sorted(data)


# ------------------------------------------------------------------ queue
def test_queue_remove_tail_then_enqueue_keeps_order():
    q = FIFOQueue()
    for x in (1, 2, 3):
        q.enqueue(x)
    q.remove(3)                    # tail pointer must move back to 2
    q.enqueue(4)
    assert list(q) == [1, 2, 4]


def test_queue_remove_only_item_and_missing_item():
    q = FIFOQueue()
    q.enqueue("x")
    assert q.remove("x") and len(q) == 0 and q.dequeue() is None
    assert not q.remove("ghost")
    q.enqueue("y")                 # still usable after becoming empty
    assert q.dequeue() == "y"


# ------------------------------------------------------------------ Dijkstra
GRAPH = build_graph(SEED_LOCATIONS, SEED_ROADS)


def test_dijkstra_start_equals_goal():
    r = dijkstra(GRAPH, set(), "RS", "RS")
    assert r["found"] and r["path"] == ["RS"] and r["distance"] == 0 and r["eta"] == 0


def test_dijkstra_all_roads_blocked():
    r = dijkstra(GRAPH, {road["id"] for road in SEED_ROADS}, "RS", "AP")
    assert not r["found"] and r["trace"]["heap"]["pushes"] == 1


def test_dijkstra_unknown_node_raises():
    with pytest.raises(KeyError):
        dijkstra(GRAPH, set(), "RS", "ZZ")


def test_dijkstra_prefers_longer_open_path_over_blocked_short_one():
    # Direct RS-MS (2.9) is blocked -> must use RS-OB-MS (3.9)
    r = dijkstra(GRAPH, {"RS-MS"}, "RS", "MS")
    assert r["path"] == ["RS", "OB", "MS"] and r["distance"] == 3.9


def _reference_shortest(graph, blocked, s):
    """Independent reference (stdlib heapq) to cross-check our implementation."""
    dist = {n: float("inf") for n in graph}
    dist[s] = 0
    pq = [(0, s)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for e in graph[u]:
            if e["road"] in blocked:
                continue
            if d + e["weight"] < dist[e["to"]]:
                dist[e["to"]] = d + e["weight"]
                heapq.heappush(pq, (dist[e["to"]], e["to"]))
    return dist


def test_dijkstra_matches_reference_on_200_random_graphs():
    rng = random.Random(7)
    for _ in range(200):
        n = rng.randint(2, 25)
        locs = [{"id": f"N{i}"} for i in range(n)]
        roads = [{"id": f"R{a}-{b}", "a": f"N{a}", "b": f"N{b}", "km": round(rng.uniform(0.5, 9), 1)}
                 for a, b in itertools.combinations(range(n), 2) if rng.random() < 0.25]
        g = build_graph(locs, roads)
        blocked = {r["id"] for r in roads if rng.random() < 0.2}
        ref = _reference_shortest(g, blocked, "N0")
        for goal in g:
            r = dijkstra(g, blocked, "N0", goal)
            if ref[goal] == float("inf"):
                assert not r["found"]
            else:
                assert r["found"] and r["distance"] == round(ref[goal], 1)
                # the returned path must be valid: consecutive nodes joined by open roads
                for a, b, rid in zip(r["path"], r["path"][1:], r["roads"]):
                    assert rid not in blocked and any(e["to"] == b and e["road"] == rid for e in g[a])


def test_connectivity_bounds():
    assert connectivity(GRAPH, set()) == 1.0
    assert connectivity(GRAPH, {r["id"] for r in SEED_ROADS}) == 0.0
    assert connectivity({"A": []}, set()) == 1.0


# ------------------------------------------------------------------ API / engine
def test_route_same_node_and_unknown_node(client):
    r = client.get("/api/route", params={"from": "RS", "to": "RS"}).json()
    assert r["found"] and r["distance"] == 0
    assert client.get("/api/route", params={"from": "RS", "to": "ZZ"}).status_code == 404
    assert client.get("/api/evacuate", params={"from": "ZZ"}).status_code == 404


def test_evacuate_from_a_shelter_is_zero_distance(client):
    ev = client.get("/api/evacuate", params={"from": "UG"}).json()
    assert ev["best"] == "UG" and ev["options"][0]["distance"] == 0


def test_evacuation_avoids_flooded_shelter(client):
    # Riverside's nearest shelter is HJ. Flood it (High, verified) -> advisor must move away.
    client.post("/api/reports", json={"location": "Hospital Junction", "description": "Ward flooded",
                                      "severity": "High"})
    ev = client.get("/api/evacuate", params={"from": "RS"}).json()
    hj = next(o for o in ev["options"] if o["id"] == "HJ")
    assert hj["flooded"] and ev["best"] != "HJ"


def test_invalid_inputs_rejected(client):
    bad = [
        {"location": "Riverside", "description": "x", "severity": "Extreme"},     # bad enum
        {"location": "Riverside", "description": "     ", "severity": "Low"},     # whitespace only
        {"location": "R" * 61, "description": "long name", "severity": "Low"},    # too long
        {"location": "Riverside", "description": "ok desc", "x": -5, "y": 10},    # out of bounds
    ]
    for body in bad:
        assert client.post("/api/reports", json=body).status_code == 422
    unknown_road = {"location": "Riverside", "description": "ok desc", "roadId": "NO-SUCH"}
    assert client.post("/api/reports", json=unknown_road).status_code == 400
    assert client.patch("/api/reports/FL001", json={"status": "Gone"}, headers=ADMIN).status_code == 422
    assert client.patch("/api/reports/FL999", json={"status": "Verified"}, headers=ADMIN).status_code == 404
    assert client.put("/api/roads/NOPE/block", json={"blocked": True}, headers=ADMIN).status_code == 404


def test_reopened_report_goes_to_queue_tail(client):
    client.post("/api/queue/process", headers=ADMIN)                     # FL001 verified
    client.patch("/api/reports/FL001", json={"status": "Reported"}, headers=ADMIN)
    assert client.get("/api/state").json()["queue"] == ["FL002", "FL003", "FL001"]


def test_two_reports_close_same_road_until_both_resolved(client):
    client.post("/api/reports", json={"location": "Riverside", "description": "Second report",
                                      "severity": "Low", "roadId": "RS-OB"})       # FL004
    for rid in ("FL001", "FL004"):
        client.patch(f"/api/reports/{rid}", json={"status": "Verified"}, headers=ADMIN)
    client.patch("/api/reports/FL001", json={"status": "Resolved"}, headers=ADMIN)
    roads = {r["id"]: r for r in client.get("/api/state").json()["roads"]}
    assert roads["RS-OB"]["blocked"]                                    # FL004 still holds it
    client.patch("/api/reports/FL004", json={"status": "Resolved"}, headers=ADMIN)
    roads = {r["id"]: r for r in client.get("/api/state").json()["roads"]}
    assert not roads["RS-OB"]["blocked"]


def test_duplicate_custom_location_names_get_unique_ids(client):
    a = client.post("/api/reports", json={"location": "Kaneshie Market", "description": "one"}).json()
    b = client.post("/api/reports", json={"location": "Kotobabi Market", "description": "two"}).json()
    assert a["locId"] != b["locId"]                         # both start with 'KM'
    c = client.post("/api/reports", json={"location": "kaneshie market", "description": "three"}).json()
    assert c["locId"] == a["locId"]                         # case-insensitive match reuses node


def test_ids_never_reused_after_clear(client):
    client.delete("/api/reports", headers=ADMIN)
    r = client.post("/api/reports", json={"location": "Harbour", "description": "after clear"}).json()
    assert r["id"] == "FL004"


def test_rate_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("FLOODWATCH_DB", str(tmp_path / "r.db"))
    monkeypatch.setenv("FLOODWATCH_RATE_LIMIT", "2")
    monkeypatch.setenv("FLOODWATCH_STATIC", str(tmp_path / "x"))
    import app.main as main
    importlib.reload(main)
    with TestClient(main.app) as c:
        body = {"location": "Harbour", "description": "spam test"}
        codes = [c.post("/api/reports", json=body).status_code for _ in range(3)]
    assert codes == [201, 201, 429]


def test_state_survives_restart(tmp_path):
    db = tmp_path / "persist.db"
    e1 = FloodWatchEngine(Store(db))
    e1.submit_report("Accra Mall", "Car park flooded", "High", None, None, None)
    e1.process_next()                                       # FL001 verified, leaves queue
    e1.resize_hash(13)
    e2 = FloodWatchEngine(Store(db))                        # simulated restart
    s = e2.snapshot()
    assert s["queue"] == ["FL002", "FL003", "FL004"]
    assert s["hash"]["stats"]["size"] == 13 and s["nextId"] == "FL005"
    assert any(l["name"] == "Accra Mall" for l in s["locations"])
    assert any(r["id"] == "RS-OB" and r["blocked"] for r in s["roads"])
