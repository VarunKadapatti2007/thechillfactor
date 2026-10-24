"""ChillPrint API (BUILD.md section 7).

    uvicorn chillprint.api.main:app --port 8000

Responses are validated against schemas.py and cached on disk; cached pins
answer in well under a second.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date
from functools import lru_cache

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .. import config as C
from ..pipeline import station_hourly as SH
from ..pipeline.build_pin import _version_tag
from ..pipeline.pins import get_pin as build_pin
from ..products.heat import heat as heat_product
from ..products.history import history as history_product
from ..products.advice import advice as advice_product, farm_context
from ..products.orchard import orchard_point
from ..products.readings_parse import ai_available, parse_file
from ..products.point import BadRequest, point as point_product
from ..products.replay import replay as replay_product
from . import schemas as S

app = FastAPI(title="ChillPrint API", version="0.1")


def _warm() -> None:
    """Load the ML curve and compile the numba kernels once at start, so no grower's request pays for it."""
    try:
        import numpy as np
        from ..science import chill, ml_shape
        if ml_shape.available():
            ml_shape._booster()
        chill.dynamic_portions(np.full(48, 5.0))
        chill.dynamic_batch_cumulative(np.full((2, 48), 5.0), state=(0.0, 0.0))
        chill.dynamic_with_day_states(np.full(48, 5.0))
    except Exception:
        pass


import threading  # noqa: E402

threading.Thread(target=_warm, daemon=True).start()

from ..pipeline import live_refresh  # noqa: E402

live_refresh.start_background()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])

CACHE = C.PROCESSED_DIR / "api_cache"
# Code fingerprint: responses cached by an older engine are never served after a code change.
CODE_TAG = str(int(max(f.stat().st_mtime for f in (C.ENGINE_DIR / "chillprint").rglob("*.py"))))
CACHE.mkdir(parents=True, exist_ok=True)
GRID_DIR = C.PROCESSED_DIR / "grid"


def _clean(o):
    """Replace NaN/inf with None so responses are valid JSON."""
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else o
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    return o


def _cached(name: str, params: dict, build, model=None):
    tag = f"{_version_tag()}|{CODE_TAG}|{live_refresh.STATE['stamp']}|{date.today()}"
    key = hashlib.sha1(json.dumps([name, params, tag], sort_keys=True, default=str).encode()).hexdigest()[:24]
    p = CACHE / f"{name}_{key}.json"
    if p.exists():
        return JSONResponse(json.loads(p.read_text(encoding="utf-8")))
    try:
        out = _clean(build())
    except BadRequest as e:
        raise HTTPException(400, str(e))
    if model is not None:
        model(**out)  # schema check: raises if the shape drifts from the contract
    p.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    return JSONResponse(out)


def _variety(crop: str, variety: str):
    try:
        return C.find_variety(crop, variety)
    except KeyError as e:
        raise HTTPException(400, str(e))


def _mmdd(v: str | None) -> str | None:
    if v is None or v == "":
        return None
    try:
        m, d = (int(x) for x in v.split("-"))
        date(2001 if m >= 9 else 2002, m, d)
    except Exception:
        raise HTTPException(400, "by must be MM-DD")
    return f"{m:02d}-{d:02d}"


@app.get("/api/health")
def health():
    return {"ai_file_reader": ai_available(), "ok": True, "hourly_stations": len(SH.hourly_index()), "tag": _version_tag(),
            "live_refresh": {k: v for k, v in live_refresh.STATE.items() if k != "stamp"}}


@app.get("/api/crops")
def crops():
    out = {"crops": [{"id": c.id, "name": c.name, "icon": c.icon,
                      "varieties": [{"id": v.id, "name": v.name, "need_low": v.need_low, "need_high": v.need_high,
                                     "by_date_default": v.by_date_default} for v in c.varieties]} for c in C.CROPS],
           "source": "UCCE, K. Pope", "sources": [C.CROP_SOURCE, C.BY_DATE_NOTE], "method": "config"}
    S.CropsResponse(**out)
    return out


@lru_cache(maxsize=1)
def _stations_payload():
    st = SH.stations()
    keep = st[(st.network == "Wildeye") | st.central_valley | st.id.isin(SH.hourly_index().keys())]
    out = []
    for r in keep.itertuples():
        out.append({"id": r.id, "name": r.name, "network": r.network, "lat": round(float(r.lat), 5),
                    "lon": round(float(r.lon), 5), "elev_m": None if pd.isna(r.elev_m) else round(float(r.elev_m), 1),
                    "active": bool(r.active), "closed": r.closed if isinstance(r.closed, str) else None})
    payload = {"stations": out, "sources": [C.SOURCES["fnric"], C.SOURCES["cimis"], C.SOURCES["usgs"]],
               "method": "FNRIC + CIMIS station lists"}
    S.StationsResponse(**payload)
    return payload


@app.get("/api/stations")
def stations():
    return _stations_payload()


@app.get("/api/point")
def point(lat: float = Query(..., ge=-60, le=70), lon: float = Query(..., ge=-180, le=180), crop: str = "pistachio",
          variety: str = "kerman", asof: date | None = None, start: str = "sep1", by: str | None = None,
          climate: str | None = None):
    _variety(crop, variety)
    climate = climate or C.default_climate()
    params = dict(lat=round(lat, 4), lon=round(lon, 4), crop=crop, variety=variety, asof=asof, start=start,
                  by=_mmdd(by), climate=climate)
    return _cached("point", params, lambda: point_product(**params), S.PointResponse)


@app.get("/api/history")
def history(lat: float = Query(..., ge=-60, le=70), lon: float = Query(..., ge=-180, le=180), crop: str = "pistachio",
            variety: str = "kerman", by: str | None = None, start: str = "sep1"):
    _, v = _variety(crop, variety)
    by_mmdd = _mmdd(by) or v.by_date_default
    params = dict(lat=round(lat, 4), lon=round(lon, 4), crop=crop, variety=variety, by=by_mmdd, start=start)

    def build():
        pin = build_pin(params["lat"], params["lon"])
        return history_product(pin, v.need_low, v.need_high, by_mmdd, start)

    return _cached("history", params, build, S.HistoryResponse)


@app.get("/api/replay")
def replay(lat: float = Query(..., ge=-60, le=70), lon: float = Query(..., ge=-180, le=180), crop: str = "pistachio",
           variety: str = "kerman", season: str = "2014-2015", by: str | None = None, climate: str | None = None):
    _, v = _variety(crop, variety)
    climate = climate or C.default_climate()
    by_mmdd = _mmdd(by) or v.by_date_default
    try:
        y = C.season_start_year(season)
    except Exception:
        raise HTTPException(400, "season must look like 2014-2015")
    params = dict(lat=round(lat, 4), lon=round(lon, 4), crop=crop, variety=variety, season=season, by=by_mmdd, climate=climate)

    def build():
        pin = build_pin(params["lat"], params["lon"])
        if y not in pin.hourly or y > C.LAST_COMPLETE_DAYMET_SEASON + 1:
            raise BadRequest(f"no complete record for {season}")
        return replay_product(pin, y, v.need_low, v.need_high, by_mmdd, climate)

    return _cached("replay", params, build, S.ReplayResponse)


@app.get("/api/area")
def area(pts: str = Query(..., description="lat,lon;lat,lon;... up to 9 points across a block"),
         crop: str = "pistachio", variety: str = "kerman", by: str | None = None, start: str = "sep1",
         climate: str | None = None):
    """Chill across an orchard block: the same analysis at up to 9 points (Daymet cells are 1 km,
    so points closer than that share a cell)."""
    _, v = _variety(crop, variety)
    try:
        points = [tuple(float(x) for x in p.split(",")) for p in pts.split(";") if p.strip()][:9]
    except ValueError:
        raise HTTPException(400, "pts must look like lat,lon;lat,lon")
    if not points:
        raise HTTPException(400, "no points")
    climate = climate or C.default_climate()
    by_mmdd = _mmdd(by)
    params = dict(pts=[(round(a, 4), round(b, 4)) for a, b in points], crop=crop, variety=variety, by=by_mmdd,
                  start=start, climate=climate)

    def one(pt):
        r = point_product(pt[0], pt[1], crop, variety, start=start, by=by_mmdd, climate=climate)
        pin = build_pin(pt[0], pt[1])
        try:
            h = history_product(pin, v.need_low, v.need_high, by_mmdd or v.by_date_default, start)
            safe = h["safe_chill"]["recent"]["p10"]
        except Exception:
            safe = None
        o = r["outlook"]
        return {"lat": pt[0], "lon": pt[1], "elev_m": r["location"]["elev_m"], "chill_to_date": r["chill"]["to_date"],
                "p10": o["p10"], "p50": o["p50"], "p90": o["p90"], "chance_low": o["chance_low"],
                "level": r["verdict"]["level"], "safe_chill_recent": safe, "method": r["method"]}

    def build():
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as ex:
            rows = list(ex.map(one, params["pts"]))
        cells = {(round(r["lat"] / 0.009), round(r["lon"] / 0.011)) for r in rows}
        p50s = [r["p50"] for r in rows]
        levels = sorted({r["level"] for r in rows})
        return {"points": rows, "n_distinct_cells": len(cells), "p50_range": [round(min(p50s), 1), round(max(p50s), 1)],
                "levels": levels, "same_verdict": len(levels) == 1,
                "sources": [C.SOURCES["cimis"], C.SOURCES["daymet"]], "method": "E4 at each point"}

    return _cached("area", params, build, S.AreaResponse)


@app.post("/api/orchard")
def orchard(req: S.OrchardRequest):
    """Chill at the orchard from the grower's own thermometer or logger readings (validated: orchard_readings)."""
    if not (-60 <= req.lat <= 70 and -180 <= req.lon <= 180):
        raise HTTPException(400, "lat/lon out of range")
    _variety(req.crop, req.variety)
    params = {**req.model_dump(), "lat": round(req.lat, 4), "lon": round(req.lon, 4), "by": _mmdd(req.by)}
    return _cached("orchard", params, lambda: orchard_point(**params), S.OrchardResponse)


@app.post("/api/advice")
def advice(req: S.AdviceRequest):
    """What to do next for this farm: its full chill picture, turned into actions by Claude Sonnet."""
    if not (-60 <= req.lat <= 70 and -180 <= req.lon <= 180):
        raise HTTPException(400, "lat/lon out of range")
    _variety(req.crop, req.variety)
    params = {**req.model_dump(), "lat": round(req.lat, 4), "lon": round(req.lon, 4), "by": _mmdd(req.by)}
    try:
        return JSONResponse(_clean(advice_product(farm_context(**params))))
    except BadRequest as e:
        raise HTTPException(400, str(e))


@app.post("/api/readings/parse")
def readings_parse(req: S.ReadingsFile):
    """Read a thermometer or logger file in any common format (Excel, CSV, text, Word, PDF).
    Cached by file content, so the same file is read once."""
    import base64
    try:
        data = base64.b64decode(req.content_b64, validate=True)
    except Exception:
        raise HTTPException(400, "content_b64 must be base64")
    key = hashlib.sha1(data + req.filename.lower().encode()).hexdigest()[:24]
    p = CACHE / f"parse_{key}.json"
    if p.exists():
        return JSONResponse(json.loads(p.read_text(encoding="utf-8")))
    try:
        out = _clean(parse_file(req.filename, data))
    except BadRequest as e:
        raise HTTPException(400, str(e))
    p.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    return JSONResponse(out)


@app.get("/api/heat")
def heat(lat: float = Query(..., ge=-60, le=70), lon: float = Query(..., ge=-180, le=180), bloom: str = "02-20"):
    b = _mmdd(bloom)
    params = dict(lat=round(lat, 4), lon=round(lon, 4), bloom=b)
    return _cached("heat", params, lambda: heat_product(build_pin(params["lat"], params["lon"]), b))


@app.get("/api/validation")
def validation():
    p = C.VALIDATION_DIR / "validation_summary.json"
    if not p.exists():
        raise HTTPException(503, "validation has not been run yet")
    out = json.loads(p.read_text(encoding="utf-8"))
    S.ValidationResponse(**{k: v for k, v in out.items() if k in S.ValidationResponse.model_fields})
    orp = C.VALIDATION_DIR / "orchard_readings.json"
    if orp.exists():
        out["orchard_readings"] = json.loads(orp.read_text(encoding="utf-8"))
    return out


@app.get("/api/grid")
def grid(layer: str = "safe_chill", variety: str = "kerman"):
    if layer not in ("safe_chill", "chill_so_far"):
        raise HTTPException(400, "layer must be safe_chill or chill_so_far")
    p = GRID_DIR / f"{layer}_{variety}.json"
    if not p.exists():
        raise HTTPException(404, "grid layer not built yet")
    return json.loads(p.read_text(encoding="utf-8"))
