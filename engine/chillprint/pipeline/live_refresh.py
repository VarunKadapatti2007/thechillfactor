"""Keep the live season current on a long-running server.

Re-pulls this season's CIMIS hourly data (one station-month per request, same throttle as the
main pull) for every Central Valley station, then clears the in-memory caches so new answers use
it. Enabled with CHILLPRINT_LIVE_REFRESH=1 (set on Cloud Run); runs at start and every 6 hours.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import date

from .. import config as C

STATE = {"stamp": "initial", "last": None, "stations": 0, "error": None}
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

        # Gentle: one station at a time; stop the cycle at the first firewall rejection.
        from ..sources.cimis import Rejected
        done, rejected = [], None
        for s in jobs:
            try:
                done.append(pull_station_season(s, y, today))
            except Rejected as e:
                rejected = str(e)[:160]
                break
            except Exception:
                continue
        for f in (SH.hourly_index, SH.station_hourly, SH.complete_seasons, B.build_pin, B.station_season_parts):
            f.cache_clear()
        latest = SH.station_hourly("CIMIS-6").dropna().index.max() if "CIMIS-6" in SH.hourly_index() else None
        STATE.update(stamp=f"{today}-{int(time.time())}", last=time.strftime("%Y-%m-%d %H:%M"), stations=len(done),
                     latest_hour=str(latest), error=rejected)
    return STATE


def start_background(every_hours: float = 6.0) -> None:
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
