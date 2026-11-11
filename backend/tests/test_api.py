import importlib

import pytest
from fastapi.testclient import TestClient

ADMIN = {"X-Admin-Token": "test-token"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FLOODWATCH_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("FLOODWATCH_ADMIN_TOKEN", "test-token")
    monkeypatch.setenv("FLOODWATCH_STATIC", str(tmp_path / "nostatic"))
    monkeypatch.setenv("FLOODWATCH_DISABLE_GEO", "1")   # Ghana map has its own tests
    import app.main as main
    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c


def test_state_seeded(client):
    s = client.get("/api/state").json()
    assert s["stats"]["active"] == 3 and s["stats"]["blockedRoads"] == 2
    assert s["queue"] == ["FL001", "FL002", "FL003"]


def test_admin_required(client):
    assert client.post("/api/queue/process").status_code == 401
    assert client.post("/api/queue/process", headers={"X-Admin-Token": "nope"}).status_code == 401


def test_full_flow(client):
    r = client.post("/api/reports", json={"location": "Riverside", "description": "Deep water",
                                          "severity": "High", "roadId": "RS-HB"})
    assert r.status_code == 201 and r.json()["id"] == "FL004"
    # verify FL001 (road RS-OB) -> RS-OB closes; route RS->HC must avoid it
    res = client.post("/api/queue/process", headers=ADMIN).json()
    assert res["report"]["id"] == "FL001"
    s = client.get("/api/state").json()
    assert any(r["id"] == "RS-OB" and r["blocked"] for r in s["roads"])
    route = client.get("/api/route", params={"from": "RS", "to": "HC"}).json()
    assert "RS-OB" not in route["roads"] and route["found"]
    # resolve -> reopens
    client.patch("/api/reports/FL001", json={"status": "Resolved"}, headers=ADMIN)
    s = client.get("/api/state").json()
    assert not any(r["id"] == "RS-OB" and r["blocked"] for r in s["roads"])


def test_custom_location_and_persistence(client):
    r = client.post("/api/reports", json={"location": "Kaneshie Market", "description": "Flooded drain",
                                          "severity": "Low"}).json()
    s = client.get("/api/state").json()
    loc = next(l for l in s["locations"] if l["id"] == r["locId"])
    assert loc["custom"] and sum(r["b"] == loc["id"] for r in s["roads"]) == 2
    assert client.get("/api/route", params={"from": "RS", "to": loc["id"]}).json()["found"]


def test_lookup_resize_delete_clear(client):
    lk = client.get("/api/reports/lookup/fl002").json()
    assert lk["found"] and lk["bucket"] == lk["hashSum"] % 8
    assert client.put("/api/hash/size", json={"size": 7}, headers=ADMIN).status_code == 400
    assert client.put("/api/hash/size", json={"size": 13}, headers=ADMIN).json()["size"] == 13
    assert client.delete("/api/reports/FL002", headers=ADMIN).status_code == 204
    assert client.delete("/api/reports/FL002", headers=ADMIN).status_code == 404
    assert client.delete("/api/reports", headers=ADMIN).json()["cleared"] == 2
    assert client.post("/api/queue/process", headers=ADMIN).status_code == 409


def test_evacuation_and_validation(client):
    ev = client.get("/api/evacuate", params={"from": "RS"}).json()
    assert ev["best"] and ev["options"][0]["state"] == "Recommended"
    assert client.post("/api/reports", json={"location": "x", "description": "y"}).status_code == 422


def test_websocket_pushes_state(client):
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "state"
        client.post("/api/reports", json={"location": "Harbour", "description": "Waves over wall"})
        msg = ws.receive_json()
        assert msg["type"] == "state" and msg["data"]["stats"]["active"] == 4
