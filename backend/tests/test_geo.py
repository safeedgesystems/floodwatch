"""Ghana real-map mode: same HashTable + Dijkstra on the real OpenStreetMap road network."""
import importlib
import math

import pytest
from fastapi.testclient import TestClient

from app.engine import FloodWatchEngine
from app.geo import DATA_FILE, haversine_m
from app.store import Store
from app.structures import HashTable, lower_bound, prefix_range

pytestmark = pytest.mark.skipif(not DATA_FILE.exists(), reason="Ghana map data not installed")
ADMIN = {"X-Admin-Token": "test-token"}
ACCRA, KUMASI = (5.5570, -0.2012), (6.6986, -1.6233)
q = lambda p: f"{p[0]},{p[1]}"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    d = tmp_path_factory.mktemp("geo")
    mp.setenv("FLOODWATCH_DB", str(d / "g.db"))
    mp.setenv("FLOODWATCH_ADMIN_TOKEN", "test-token")
    mp.setenv("FLOODWATCH_STATIC", str(d / "x"))
    mp.setenv("FLOODWATCH_RATE_LIMIT", "1000")
    import app.main as main
    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c
    mp.undo()


def test_binary_search_prefix_range():
    keys = sorted(["accra", "accra mall", "ada", "kaneshie", "kaneshie market", "kumasi"])
    assert lower_bound(keys, "b") == 3
    s, e = prefix_range(keys, "kaneshie")
    assert keys[s:e] == ["kaneshie", "kaneshie market"]
    assert prefix_range(keys, "zz") == (len(keys), len(keys))


def test_polynomial_hash_table_spreads_grid_keys():
    t = HashTable(1009, hash_fn="poly")
    keys = [f"{r}:{c}" for r in range(250, 300) for c in range(-150, -100)]   # 2,500 grid cells
    for k in keys:
        t.put(k, k)
    assert all(t.get_value(k) == k for k in keys[::97])
    s = HashTable(1009)                               # original char-sum hash, same keys
    for k in keys:
        s.put(k, k)
    # polynomial: ~600 buckets used, longest chain ~10; char-sum: 26 buckets, chain of 214
    assert t.stats()["usedBuckets"] > 20 * s.stats()["usedBuckets"]
    assert t.stats()["longestChain"] < s.stats()["longestChain"] / 10


def test_info_and_search(client):
    info = client.get("/api/geo/info").json()
    assert info["junctions"] > 40000 and info["roadKm"] > 50000
    names = [p["name"] for p in client.get("/api/geo/search", params={"q": "korle bu"}).json()]
    assert "Korle Bu Teaching Hospital" in names
    assert client.get("/api/geo/search", params={"q": "Kumasi"}).json()[0]["kind"] == "city"


def test_route_accra_kumasi_is_valid_path(client):
    r = client.get("/api/geo/route", params={"from": q(ACCRA), "to": q(KUMASI)}).json()
    assert r["found"] and 200 < r["distance"] < 320
    assert r["from"]["snapM"] < 1000 and r["to"]["snapM"] < 1000
    # consecutive coordinates are close together -> one continuous drawn line
    gaps = [haversine_m(*a, *b) for a, b in zip(r["coords"], r["coords"][1:])]
    assert max(gaps) < 25000


def test_verified_flood_reroutes_and_unblocks_when_resolved(client):
    a, b = (5.5570, -0.2012), (5.5700, -0.2350)
    before = client.get("/api/geo/route", params={"from": q(a), "to": q(b)}).json()
    mid = before["coords"][len(before["coords"]) // 2]
    rep = client.post("/api/reports", json={"location": "Test flood", "description": "Road under water",
                                            "severity": "High", "lat": mid[0], "lon": mid[1]}).json()
    unverified = client.get("/api/geo/route", params={"from": q(a), "to": q(b)}).json()
    assert unverified["distance"] == before["distance"]          # unverified reports change nothing
    client.patch(f"/api/reports/{rep['id']}", json={"status": "Verified"}, headers=ADMIN)
    after = client.get("/api/geo/route", params={"from": q(a), "to": q(b)}).json()
    assert after["closedSegments"] > 0 and not set(after["roads"]) & set(before["roads"][len(before["roads"]) // 2:][:1])
    assert after["distance"] >= before["distance"]
    for lat, lon in after["coords"]:                             # new path never enters the zone centre
        assert haversine_m(lat, lon, *mid) > 150
    client.patch(f"/api/reports/{rep['id']}", json={"status": "Resolved"}, headers=ADMIN)
    again = client.get("/api/geo/route", params={"from": q(a), "to": q(b)}).json()
    assert again["distance"] == before["distance"] and again["closedSegments"] == 0


def test_flooded_destination_goes_to_safe_point(client):
    spot = (5.5450, -0.2080)
    rep = client.post("/api/reports", json={"location": "Dest flood", "description": "Flooded junction",
                                            "severity": "Medium", "lat": spot[0], "lon": spot[1]}).json()
    client.patch(f"/api/reports/{rep['id']}", json={"status": "Verified"}, headers=ADMIN)
    r = client.get("/api/geo/route", params={"from": q(ACCRA), "to": q(spot)}).json()
    assert r["destinationFlooded"] and r["found"] and r["warnings"]
    assert haversine_m(*r["safePoint"], *spot) > 200            # outside the 200 m zone
    # starting INSIDE the zone still lets you drive out
    out = client.get("/api/geo/route", params={"from": q(spot), "to": q(KUMASI)}).json()
    assert out["found"] and out["warnings"]
    client.patch(f"/api/reports/{rep['id']}", json={"status": "Resolved"}, headers=ADMIN)


def test_evacuation_and_bounds(client):
    ev = client.get("/api/geo/evacuate", params={"at": "5.5700,-0.2300"}).json()
    assert ev["options"][0]["state"] == "Recommended" and ev["options"][0]["coords"]
    assert client.get("/api/geo/route", params={"from": "51.5,-0.1", "to": q(ACCRA)}).status_code == 422
    assert client.post("/api/reports", json={"location": "London", "description": "not ghana",
                                             "lat": 51.5, "lon": -0.1}).status_code == 422


def test_gps_report_uses_same_hash_table_and_queue(client):
    rep = client.post("/api/reports", json={"location": "Kaneshie", "description": "Market flooded",
                                            "severity": "Low", "lat": 5.5666, "lon": -0.2345}).json()
    lk = client.get(f"/api/reports/lookup/{rep['id']}").json()
    assert lk["found"] and lk["report"]["lat"] == 5.5666
    assert rep["id"] in client.get("/api/state").json()["queue"]


def test_gps_reports_survive_restart(tmp_path):
    db = tmp_path / "p.db"
    e1 = FloodWatchEngine(Store(db))
    rec = e1.submit_report("Circle", "Interchange flooded", "High", None, None, None, 5.5717, -0.2165)
    e2 = FloodWatchEngine(Store(db))
    got = e2.lookup(rec["id"])["report"]
    assert got["lat"] == 5.5717 and got["lon"] == -0.2165 and got["locId"] == ""
