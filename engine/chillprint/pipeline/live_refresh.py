"""Keep the live season current on a long-running server.

Re-pulls this month's CIMIS hourly data (one request per station, same throttle as the main pull)
for every Central Valley station, then clears the in-memory caches so new answers use it. If CIMIS
refuses, the rest of that cycle uses FNRIC's relay of the same CIMIS readings instead of asking
CIMIS again. Enabled with CHILLPRINT_LIVE_REFRESH=1 (set on Cloud Run); runs at start and every
3 hours. /api/health reports the sources used and how fresh the data is.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import date

import pandas as pd

from .. import config as C

STATE = {"stamp": "initial", "last": None, "stations": 0, "sources": {}, "latest_hour": None, "age_hours": None,
         "error": None}
EVERY_HOURS = 3.0
_lock = threading.Lock()


def refresh() -> dict:
    from . import build_pin as B
    from . import station_hourly as SH
    from .build_station_store import cv_cimis, load_stations, pull_station_season, station_seasons

    if not C.cimis_key():
        STATE["error"] = "no CIMIS key"
        return STATE
    with _lock:
        today = date.today()
        y = C.current_season(today)
        jobs = [s for s in cv_cimis(load_stations()).itertuples() if station_seasons(s, y, y)]

        # Gentle: one station at a time. After CIMIS refuses once, use FNRIC's relay for the rest of the cycle.
        done, sources, errors, cimis_ok = [], {}, [], True
        for s in jobs:
            try:
                r = pull_station_season(s, y, today, cimis_ok=cimis_ok)
            except Exception as e:
                errors.append(f"{s.id}: {str(e)[:120]}")
                continue
            done.append(r)
            for src in r["sources"]:
                sources[src] = sources.get(src, 0) + 1
            if r["cimis_rejected"]:
                if cimis_ok:
                    errors.append("CIMIS refused a request; this cycle used FNRIC's relay of the same CIMIS readings")
                cimis_ok = False
        for f in (SH.hourly_index, SH.station_hourly, SH.complete_seasons, B.build_pin, B.station_season_parts):
            f.cache_clear()
        latest = None
        idx = SH.hourly_index()
        for s in jobs:
            if s.id in idx and y in idx[s.id]:
                h = SH.station_hourly(s.id).dropna()
                if len(h) and (latest is None or h.index.max() > latest):
                    latest = h.index.max()
        age = None if latest is None else round((pd.Timestamp.now() - latest).total_seconds() / 3600, 1)
        STATE.update(stamp=f"{today}-{int(time.time())}", last=time.strftime("%Y-%m-%d %H:%M"), stations=len(done),
                     sources=sources, latest_hour=None if latest is None else str(latest), age_hours=age,
                     error="; ".join(errors[:3]) or None)
    return STATE


def start_background(every_hours: float = EVERY_HOURS) -> None:
    if os.environ.get("CHILLPRINT_LIVE_REFRESH") != "1":
        return

    def loop():
        while True:
            try:
                refresh()
            except Exception as e:  # keep serving with the data we have
                STATE["error"] = str(e)[:200]
            time.sleep(every_hours * 3600)

    threading.Thread(target=loop, daemon=True).start()
