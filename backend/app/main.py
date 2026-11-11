"""FloodWatch API - FastAPI application.

Run:  uvicorn app.main:app --reload            (from backend/)
Docs: http://localhost:8000/api/docs
"""
from __future__ import annotations

import asyncio
import logging
import os
import secrets
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .engine import DomainError, FloodWatchEngine
from .geo import DATA_FILE, GeoNetwork
from .store import Store

# --------------------------------------------------------------------------
# Configuration (env vars, 12-factor style)
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (KEY=value lines) so local runs need no extra package.
    Real environment variables always win over the file."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR.parent / ".env")      # project-root .env (see .env.example)
DB_PATH = os.getenv("FLOODWATCH_DB", str(BASE_DIR / "data" / "floodwatch.db"))
ADMIN_TOKEN = os.getenv("FLOODWATCH_ADMIN_TOKEN", "floodwatch-admin")
STATIC_DIR = Path(os.getenv("FLOODWATCH_STATIC", str(BASE_DIR / "static")))
CORS_ORIGINS = [o for o in os.getenv("FLOODWATCH_CORS", "http://localhost:5173").split(",") if o]
REPORTS_PER_MINUTE = int(os.getenv("FLOODWATCH_RATE_LIMIT", "12"))
# Browser-side key for CARTO basemap tiles (free at carto.com/basemaps/apikey). It is sent to
# the browser by design (tile URLs are public); restrict it to your domains in CARTO.
CARTO_KEY = os.getenv("FLOODWATCH_CARTO_KEY", "").strip()

log = logging.getLogger("floodwatch")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


# --------------------------------------------------------------------------
# Live update hub (WebSocket fan-out)
# --------------------------------------------------------------------------
class Hub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    async def broadcast(self, payload: dict) -> None:
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_json(payload)
            except Exception:  # client went away mid-send
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


hub = Hub()
engine: FloodWatchEngine  # initialised in lifespan


async def publish() -> None:
    await hub.broadcast({"type": "state", "data": engine.snapshot()})


@asynccontextmanager
async def lifespan(_: FastAPI):
    global engine
    engine = FloodWatchEngine(Store(DB_PATH))
    if DATA_FILE.exists() and os.getenv("FLOODWATCH_DISABLE_GEO") != "1":
        engine.geo = GeoNetwork()
        log.info("Ghana map loaded: %s", {k: v for k, v in engine.geo.info().items() if k != "spatialIndex"})
    else:
        log.warning("Ghana map data not found (%s) - only the simulation map is available", DATA_FILE)
    if ADMIN_TOKEN == "floodwatch-admin":
        log.warning("Using the default admin token. Set FLOODWATCH_ADMIN_TOKEN for any real deployment.")
    log.info("FloodWatch ready - db=%s static=%s", DB_PATH, STATIC_DIR.exists())
    yield


app = FastAPI(title="FloodWatch API", version="2.0.0", lifespan=lifespan,
              docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"],
                   allow_headers=["*"])


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError):
    return JSONResponse(status_code=exc.status, content={"detail": str(exc)})


# --------------------------------------------------------------------------
# Security: admin token + simple per-IP rate limit for public submissions
# --------------------------------------------------------------------------
def require_admin(x_admin_token: Optional[str] = Header(default=None)) -> None:
    if not x_admin_token or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(401, "Admin token required")


_hits: dict[str, list[float]] = defaultdict(list)


def rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = [t for t in _hits[ip] if now - t < 60]
    if len(window) >= REPORTS_PER_MINUTE:
        raise HTTPException(429, "Too many reports from this device. Try again in a minute.")
    window.append(now)
    _hits[ip] = window


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------
Severity = Literal["High", "Medium", "Low"]
Status = Literal["Reported", "Verified", "Resolved"]


class ReportIn(BaseModel):
    location: str = Field(min_length=2, max_length=60)
    description: str = Field(min_length=3, max_length=280)
    severity: Severity = "Medium"
    roadId: Optional[str] = Field(default=None, max_length=20)
    x: Optional[float] = Field(default=None, ge=0, le=720)
    y: Optional[float] = Field(default=None, ge=0, le=460)
    lat: Optional[float] = Field(default=None, ge=4.5, le=11.5)     # Ghana map reports (GPS)
    lon: Optional[float] = Field(default=None, ge=-3.5, le=1.5)

    @field_validator("location", "description")
    @classmethod
    def strip(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("too short")
        return v


class StatusIn(BaseModel):
    status: Status


class BlockIn(BaseModel):
    blocked: bool


class SizeIn(BaseModel):
    size: int


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok", "version": engine.version, "clients": len(hub.clients)}


@app.get("/api/state", tags=["system"])
def state():
    return engine.snapshot()


@app.post("/api/auth/verify", tags=["system"], dependencies=[Depends(require_admin)])
def verify_admin():
    return {"ok": True}


@app.post("/api/reports", status_code=201, tags=["reports"], dependencies=[Depends(rate_limit)])
async def submit_report(body: ReportIn):
    rec = engine.submit_report(body.location, body.description, body.severity,
                               body.roadId, body.x, body.y, body.lat, body.lon)
    await publish()
    return rec


@app.get("/api/reports/lookup/{key}", tags=["reports"])
def lookup(key: str):
    return engine.lookup(key[:20])


@app.patch("/api/reports/{report_id}", tags=["reports"], dependencies=[Depends(require_admin)])
async def set_status(report_id: str, body: StatusIn):
    rec = engine.set_status(report_id, body.status)
    await publish()
    return rec


@app.delete("/api/reports/{report_id}", status_code=204, tags=["reports"],
            dependencies=[Depends(require_admin)])
async def delete_report(report_id: str):
    engine.delete_report(report_id)
    await publish()


@app.delete("/api/reports", tags=["reports"], dependencies=[Depends(require_admin)])
async def clear_reports():
    n = engine.clear_reports()
    await publish()
    return {"cleared": n}


@app.post("/api/queue/process", tags=["queue"], dependencies=[Depends(require_admin)])
async def process_next():
    res = engine.process_next()
    await publish()
    return res


@app.put("/api/roads/{road_id}/block", tags=["network"], dependencies=[Depends(require_admin)])
async def block_road(road_id: str, body: BlockIn):
    res = engine.set_road_block(road_id, body.blocked)
    await publish()
    return res


@app.put("/api/hash/size", tags=["hash"], dependencies=[Depends(require_admin)])
async def resize(body: SizeIn):
    res = engine.resize_hash(body.size)
    await publish()
    return res


@app.get("/api/route", tags=["network"])
def route(start: str = Query(alias="from"), goal: str = Query(alias="to")):
    return engine.route(start, goal)


@app.get("/api/evacuate", tags=["network"])
def evacuate(start: str = Query(alias="from")):
    return engine.evacuate(start)


# --------------------------------------------------------------------------
# Ghana map (real OpenStreetMap roads)
# --------------------------------------------------------------------------
def _latlon(v: str) -> tuple[float, float]:
    try:
        lat, lon = (float(x) for x in v.split(","))
    except ValueError:
        raise HTTPException(422, "Expected 'lat,lon'")
    if not (4.5 <= lat <= 11.5 and -3.5 <= lon <= 1.5):
        raise HTTPException(422, "That location is outside Ghana")
    return lat, lon


def _geo():
    if not engine.geo:
        raise HTTPException(503, "Ghana map data is not installed on this server")
    return engine.geo


@app.get("/api/geo/info", tags=["ghana map"])
def geo_info():
    return {**_geo().info(), "cartoKey": CARTO_KEY or None}


@app.get("/api/geo/offline-roads", tags=["ghana map"])
def geo_offline_roads():
    """Pre-compressed road shapes for the offline base map (≈2.6 MB, cached by the browser)."""
    return Response(_geo().offline_layer_gz(), media_type="application/json",
                    headers={"Content-Encoding": "gzip", "Cache-Control": "public, max-age=86400"})


@app.get("/api/geo/search", tags=["ghana map"])
def geo_search(q: str = Query(min_length=2, max_length=60)):
    return _geo().search(q)


@app.get("/api/geo/reverse", tags=["ghana map"])
def geo_reverse(at: str):
    lat, lon = _latlon(at)
    return {"lat": lat, "lon": lon, "place": _geo().nearest_place(lat, lon)}


@app.get("/api/geo/route", tags=["ghana map"])
def geo_route(start: str = Query(alias="from"), goal: str = Query(alias="to")):
    _geo()
    return engine.geo_route(_latlon(start), _latlon(goal))


@app.get("/api/geo/evacuate", tags=["ghana map"])
def geo_evacuate(at: str):
    _geo()
    return engine.geo_evacuate(_latlon(at))


@app.post("/api/admin/reset", tags=["system"], dependencies=[Depends(require_admin)])
async def reset():
    engine.reset_demo()
    await publish()
    return {"ok": True}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await hub.connect(ws)
    try:
        await ws.send_json({"type": "state", "data": engine.snapshot()})
        while True:  # keep-alive: client sends "ping"
            msg = await asyncio.wait_for(ws.receive_text(), timeout=90)
            if msg == "ping":
                await ws.send_json({"type": "pong"})
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        hub.disconnect(ws)


# --------------------------------------------------------------------------
# Frontend (built SPA) - served from the same origin in production
# --------------------------------------------------------------------------
if (STATIC_DIR / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404)
        candidate = (STATIC_DIR / full_path).resolve()
        if full_path and candidate.is_file() and STATIC_DIR.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
