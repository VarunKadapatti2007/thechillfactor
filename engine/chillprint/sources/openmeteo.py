"""Open-Meteo forecast and historical (ERA5) client (BUILD.md 3.5). Credit: Open-Meteo, CC BY 4.0.

We request timezone=GMT and shift to PST (UTC-8, no daylight saving) ourselves,
so every hourly series in the engine shares the CIMIS convention.
"""
from __future__ import annotations

import json
from datetime import date

import pandas as pd

from . import cache

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
PST = pd.Timedelta(hours=-8)


def _hourly_frame(js: dict) -> pd.Series:
    h = js["hourly"]
    idx = pd.to_datetime(h["time"]) + PST  # GMT -> PST (naive)
    return pd.Series(h["temperature_2m"], index=idx, dtype="float64", name="t_c")


def forecast_hourly(lat: float, lon: float, tag: str) -> pd.Series:
    """Hourly temperature, 14 past days + 16 forecast days, PST. `tag` scopes the cache (e.g. date+hour)."""
    key = f"forecast_{lat:.3f}_{lon:.3f}_{tag}"
    raw = cache.cached("openmeteo", key, lambda: cache.http_get(FORECAST_URL, params={
        "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "hourly": "temperature_2m",
        "past_days": 14, "forecast_days": 16, "timezone": "GMT"}))
    return _hourly_frame(json.loads(raw))


def archive_hourly(lat: float, lon: float, start: date, end: date, model: str = "era5") -> pd.Series:
    key = f"archive_{model}_{lat:.3f}_{lon:.3f}_{start}_{end}"
    raw = cache.cached("openmeteo", key, lambda: cache.http_get(ARCHIVE_URL, params={
        "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "start_date": str(start), "end_date": str(end),
        "hourly": "temperature_2m", "timezone": "GMT", "models": model}, timeout=180))
    return _hourly_frame(json.loads(raw))


def archive_daily(lat: float, lon: float, start: date, end: date, model: str = "era5") -> pd.DataFrame:
    key = f"archive_daily_{model}_{lat:.3f}_{lon:.3f}_{start}_{end}"
    raw = cache.cached("openmeteo", key, lambda: cache.http_get(ARCHIVE_URL, params={
        "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "start_date": str(start), "end_date": str(end),
        "daily": "temperature_2m_min,temperature_2m_max", "timezone": "Etc/GMT+8", "models": model}, timeout=180))
    js = json.loads(raw)["daily"]
    df = pd.DataFrame({"tmin": js["temperature_2m_min"], "tmax": js["temperature_2m_max"]},
                      index=pd.to_datetime(js["time"]))
    df.index.name = "date"
    return df
