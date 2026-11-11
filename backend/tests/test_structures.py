from app.structures import FIFOQueue, HashTable, MinHeap
from app.graph import build_graph, dijkstra
from app.seed import SEED_LOCATIONS, SEED_ROADS


def test_hash_put_get_collision_and_remove():
    t = HashTable(5)
    # "AB" and "BA" have the same char sum -> guaranteed collision
    assert t.put("AB", 1) and t.put("BA", 2)
    assert t.stats()["collisions"] == 1
    res = t.get("BA")
    assert res["found"] and res["steps"] == 2 and res["visited"] == ["AB", "BA"]
    assert not t.put("AB", 9) and t.get("AB")["value"] == 9   # update, no new count
    assert t.remove("AB") and not t.remove("AB") and t.count == 1


def test_hash_resize_keeps_entries():
    t = HashTable(5)
    for i in range(20):
        t.put(f"FL{i:03d}", i)
    t.resize(13)
    assert t.count == 20 and all(t.get(f"FL{i:03d}")["value"] == i for i in range(20))


def test_minheap_orders():
    h = MinHeap()
    for p in [5, 1, 4, 2, 3, 0]:
        h.push(p, str(p))
    assert [h.pop()[0] for _ in range(6)] == [0, 1, 2, 3, 4, 5]
    assert h.pop() is None and h.pushes == 6 and h.peak == 6


def test_fifo_queue():
    q = FIFOQueue()
    for x in "abcd":
        q.enqueue(x)
    assert q.remove("d") and list(q) == ["a", "b", "c"]
    q.enqueue("e")
    assert [q.dequeue() for _ in range(4)] == ["a", "b", "c", "e"]
    assert q.dequeue() is None and len(q) == 0


def test_dijkstra_matches_original_screenshot():
    g = build_graph(SEED_LOCATIONS, SEED_ROADS)
    r = dijkstra(g, {"RS-MS", "HJ-HC"}, "RS", "HC")
    assert r["path"] == ["RS", "OB", "MS", "HC"] and r["distance"] == 6.9


def test_dijkstra_no_route():
    g = build_graph(SEED_LOCATIONS, SEED_ROADS)
    r = dijkstra(g, {"RS-OB", "RS-MS", "RS-HB"}, "RS", "AP")
    assert not r["found"] and r["trace"]["settled"] == ["RS"]
