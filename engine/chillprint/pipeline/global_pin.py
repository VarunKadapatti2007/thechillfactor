"""Pins outside California (BUILD.md Phase 6 step 5): the same engine on Open-Meteo ERA5 hourly.

No Daymet or CIMIS there, so hours come straight from ERA5 (about 25 km),
shifted to local standard time by longitude. Labeled "Lower resolution, not
validated here." Credit: Open-Meteo (CC BY 4.0), Copernicus ERA5.
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

from .. import config as C
from ..sources import elevation, openmeteo
from .build_pin import Pin, season_stamps

CA_BBOX = (32.4, 42.1, -124.6, -114.0)
LABEL = "ERA5 hourly via Open-Meteo. Lower resolution, not validated here."


def in_california(lat: float, lon: float) -> bool:
    return CA_BBOX[0] <= lat <= CA_BBOX[1] and CA_BBOX[2] <= lon <= CA_BBOX[3]


def _era5(lat: float, lon: float, today: date) -> pd.Series:
    parts = []
    y0 = C.FIRST_SEASON
    end = today - timedelta(days=6)  # ERA5 lags about five days
    for a in range(y0, end.year + 1, 8):
        s = date(a, 1, 1)
        e = min(date(a + 7, 12, 31), end)
        parts.append(openmeteo.archive_hourly(lat, lon, s, e, model="era5"))
    utc_pst = pd.concat(parts)  # archive_hourly returns UTC-8 stamps; undo and apply local standard offset
    offset = round(lon / 15)
    local = utc_pst.copy()
    local.index = local.index + pd.Timedelta(hours=8 + offset)
    local = local[~local.index.duplicated()].sort_index()
    return local


@lru_cache(maxsize=8)
def build_global_pin(lat: float, lon: float, today: date | None = None) -> Pin:
    today = today or date.today()
    lat, lon = round(lat, 4), round(lon, 4)
    h = _era5(lat, lon, today)
    # ERA5 instantaneous values on the hour; treat each as the hour-ending reading.
    hourly, method, filled, share = {}, {}, {}, {}
    last_obs = h.dropna().index.max()
    for y in range(C.FIRST_SEASON, C.season_of(today) + 1):
        st = season_stamps(y)
        arr = h.reindex(st).to_numpy().copy()
        if np.isnan(arr).all():
            continue
        if y < C.season_of(today) and np.isnan(arr[: (dos_mar1(y) + 1) * 24]).mean() > 0.05:
            continue
        if y < C.season_of(today):
            arr = pd.Series(arr).interpolate(limit_direction="both").to_numpy()
        hourly[y], method[y], filled[y], share[y] = arr, LABEL, False, 0.0
    day = (h.index - pd.Timedelta(hours=1)).normalize()
    daily = pd.DataFrame({"tmin": h.groupby(day).min(), "tmax": h.groupby(day).max()})
    daily["filled"] = False
    daily.index.name = "date"
    live = str((last_obs - pd.Timedelta(hours=1)).normalize().date() - timedelta(days=1)) if pd.notna(last_obs) else None
    return Pin(lat, lon, elevation.elevation_m(lat, lon), [], hourly, method, filled, share, daily, "local standard time", live,
               [C.SOURCES["openmeteo"], "Copernicus ERA5 reanalysis"])


def dos_mar1(y: int) -> int:
    return (date(y + 1, 3, 1) - date(y, 9, 1)).days
