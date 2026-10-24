"""Assemble the /api/point response (BUILD.md section 7)."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from .. import config as C
from ..pipeline import station_hourly as SH
from ..pipeline.build_pin import Pin
from ..pipeline.pins import get_pin, is_global
from .analogs import closest_winter
from .core import dos, season_daily_cum, start_dos
from .errorbar import error_cp
from .live import forecast_hours
from .outlook import outlook
from .sunny import sunny_stretch
from .verdict import verdict


class BadRequest(ValueError):
    pass


def default_asof(pin: Pin, today: date | None = None) -> date:
    today = today or date.today()
    if pin.live_until:
        return min(date.fromisoformat(pin.live_until), today - timedelta(days=1))
    return today - timedelta(days=1)


def nearest_active(lat: float, lon: float) -> dict:
    st = SH.nearest_cimis(lat, lon, k=12)
    act = st[st.active]
    r = (act if len(act) else st).iloc[0]
    return {"id": str(r["id"]), "name": str(r["name"]), "dist_km": round(float(r["dist_km"]), 1)}


def series_from(cum: np.ndarray, season: int, k0: int, k1: int, step: int = 1) -> list[dict]:
    out = []
    for k in range(k0, k1 + 1, step):
        v = cum[k]
        if np.isfinite(v):
            out.append({"date": (date(season, 9, 1) + timedelta(days=k)).isoformat(), "cp": round(float(v), 2)})
    if step > 1 and k1 >= k0 and (k1 - k0) % step and np.isfinite(cum[k1]):
        out.append({"date": (date(season, 9, 1) + timedelta(days=k1)).isoformat(), "cp": round(float(cum[k1]), 2)})
    return out


def point(lat: float, lon: float, crop: str, variety: str, asof: date | None = None, start: str = "sep1",
          by: str | None = None, climate: str = "today", today: date | None = None) -> dict:
    try:
        _, v = C.find_variety(crop, variety)
    except KeyError as e:
        raise BadRequest(str(e))
    if start not in ("sep1", "nov1"):
        raise BadRequest("start must be sep1 or nov1")
    if climate not in ("today", "recorded"):
        raise BadRequest("climate must be today or recorded")
    today = today or date.today()
    pin = get_pin(lat, lon, today)
    glob = is_global(pin)
    asof = asof or default_asof(pin, today)
    season = C.season_of(asof)
    if season not in pin.hourly:
        raise BadRequest(f"no data for season {C.season_label(season)}")
    live = season == C.season_of(today) and (glob or season > C.LAST_COMPLETE_DAYMET_SEASON + 1)
    if live and pin.live_until and asof > date.fromisoformat(pin.live_until):
        asof = date.fromisoformat(pin.live_until)
    if asof < date(season, 9, 1):
        raise BadRequest("asof before the season start")
    by_mmdd = by or v.by_date_default
    by_d = C.by_date(season, by_mmdd)
    if by_d > C.season_end(season):
        raise BadRequest("by date must fall between Sep 1 and Mar 31")

    fc, bias = (forecast_hours(pin, season, asof) if live else (None, None))
    ol = outlook(pin, season, asof, by_d, start, climate, forecast=fc)
    p10, p50, p90 = ol.pct(10), ol.pct(50), ol.pct(90)
    ch_lo, ch_hi = ol.chance(v.need_low), ol.chance(v.need_high)

    cum = season_daily_cum(pin, season, start)
    kd = dos(season, asof)
    k0 = start_dos(start)
    series = series_from(cum, season, k0, kd) if kd >= k0 else []

    past = []
    for y in pin.history_seasons():
        if y == season:
            continue
        c = season_daily_cum(pin, y, start)
        past.append({"season": C.season_label(y), "series": series_from(c, y, k0, len(c) - 1, step=2)})

    cy, rmse = closest_winter(pin, season, asof, start)
    method = pin.method.get(season, "")
    sources = list(pin.sources) + [C.CROP_SOURCE]
    if fc is not None:
        sources.append(C.SOURCES["openmeteo"])
    gaps = int(pin.daily.loc[str(date(season, 9, 1)):str(asof), "filled"].sum()) if not (live or glob) else 0
    return {
        "location": {"lat": pin.lat, "lon": pin.lon, "elev_m": None if pin.elev_m is None else round(float(pin.elev_m), 1),
                     "nearest_station": ({"id": "", "name": "No CIMIS station (outside California)", "dist_km": 0.0}
                                         if glob else nearest_active(pin.lat, pin.lon))},
        "season": C.season_label(season),
        "asof": asof.isoformat(),
        "start": start,
        "method": method,
        "chill": {"to_date": round(float(ol.cp_obs), 2),
                  "error_cp": None if glob else error_cp(pin, "live" if live else "history", min(kd, dos(season, by_d))),
                  "series": series},
        "need": {"low": v.need_low, "high": v.need_high, "by": by_d.isoformat()},
        "outlook": {"p10": round(p10, 2), "p50": round(p50, 2), "p90": round(p90, 2),
                    "chance_low": round(ch_lo, 3), "chance_high": round(ch_hi, 3),
                    "n_analogs": len(ol.analogs),
                    "fan": [{"date": d.isoformat(), "p10": round(float(r[0]), 2), "p50": round(float(r[1]), 2),
                             "p90": round(float(r[2]), 2)} for d, r in zip(ol.fan_days, ol.fan)]},
        "past_seasons": past,
        "closest": {"season": C.season_label(cy) if cy is not None else None,
                    "rmse_cp": None if rmse is None else round(rmse, 2)},
        "verdict": verdict(p10, p50, v.need_low, v.need_high, ch_lo, v.name, by_d, asof, season),
        "flags": {"sunny_stretch": None if glob else sunny_stretch(pin.lat, pin.lon, asof), "data_gaps_days": gaps},
        "sources": sources,
    }
