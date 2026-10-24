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
from ..products.point import BadRequest, point as point_product
from ..products.replay import replay as replay_product
from . import schemas as S

app = FastAPI(title="ChillPrint API", version="0.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

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
    tag = f"{_version_tag()}|{CODE_TAG}|{date.today()}"
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
    return {"ok": True, "hourly_stations": len(SH.hourly_index()), "tag": _version_tag()}


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
    return out


@app.get("/api/grid")
def grid(layer: str = "safe_chill", variety: str = "kerman"):
    if layer not in ("safe_chill", "chill_so_far"):
        raise HTTPException(400, "layer must be safe_chill or chill_so_far")
    p = GRID_DIR / f"{layer}_{variety}.json"
    if not p.exists():
        raise HTTPException(404, "grid layer not built yet")
    return json.loads(p.read_text(encoding="utf-8"))
