"""Synoptic Data (MesoWest) client: backup source for station hourly temperature.

Used only when a CIMIS month request fails. Needs SYNOPTIC_TOKEN in .env.
Stations are matched to CIMIS stations by searching within 1 mile of the CIMIS
coordinates (preferring Synoptic's CIMIS network). Times arrive in UTC and are
converted to PST hour-ending stamps to match the CIMIS store.
"""
from __future__ import annotations

import calendar
import json
import os
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from . import cache

BASE = "https://api.synopticdata.com/v2/"
SRC = "synoptic"


def token() -> str | None:
    return os.environ.get("SYNOPTIC_TOKEN") or None


def match_station(cimis_id: str, lat: float, lon: float) -> str | None:
    """Synoptic STID for a CIMIS station, or None."""
    t = token()
    if not t:
        return None
    raw = cache.cached(SRC, f"match_{cimis_id}", lambda: cache.http_get(BASE + "stations/metadata", params={
        "token": t, "radius": f"{lat:.5f},{lon:.5f},1", "limit": 10, "complete": 1}, timeout=60))
    js = json.loads(raw)
    sts = js.get("STATION") or []
    if not sts:
        return None

    def score(s):
        net = str(s.get("MNET_SHORTNAME", "") or s.get("SHORTNAME", "")).upper()
        d = float(s.get("DISTANCE", 9) or 9)
        return (0 if "CIMIS" in net else 1, d)

    return sorted(sts, key=score)[0].get("STID")


def month_hourly(stid: str, year: int, month: int) -> pd.DataFrame:
    """One month of hourly air temperature (°C), solar radiation and RH on PST hour-ending stamps."""
    t = token()
    last = calendar.monthrange(year, month)[1]
    # PST month -> UTC window (PST = UTC-8)
    start = datetime(year, month, 1, 8)
    end = datetime(year, month, last, 8) + timedelta(days=1)
    key = f"ts_{stid}_{year:04d}-{month:02d}"
    raw = cache.cached(SRC, key, lambda: cache.http_get(BASE + "stations/timeseries", params={
        "token": t, "stid": stid, "start": start.strftime("%Y%m%d%H%M"), "end": end.strftime("%Y%m%d%H%M"),
        "vars": "air_temp,solar_radiation,relative_humidity", "units": "metric", "obtimezone": "utc"}, timeout=120))
    js = json.loads(raw)
    sts = js.get("STATION") or []
    if not sts:
        return pd.DataFrame(columns=["ts", "t_c", "srad", "rh"])
    ob = sts[0].get("OBSERVATIONS", {})
    times = pd.to_datetime(ob.get("date_time", []), utc=True).tz_convert(None) - pd.Timedelta(hours=8)
    def col(prefix):
        k = next((k for k in ob if k.startswith(prefix)), None)
        return np.asarray(ob[k], dtype=float) if k else np.full(len(times), np.nan)
    df = pd.DataFrame({"ts": times.round("h"), "t_c": col("air_temp"), "srad": col("solar_radiation"),
                       "rh": col("relative_humidity")})
    df = df.groupby("ts", as_index=False).mean()
    return df.sort_values("ts").reset_index(drop=True)
