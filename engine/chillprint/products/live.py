"""Live-season helpers: bias-shifted Open-Meteo forecast at the pin (BUILD.md 4.7 step 2)."""
from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd

from ..pipeline.build_pin import Pin, season_stamps
from ..sources import openmeteo


def forecast_hours(pin: Pin, season: int, asof: date, max_days: int = 16) -> tuple[np.ndarray | None, float | None]:
    """Hourly forecast for whole days after `asof`, shifted by the mean (Open-Meteo minus pin estimate)
    over the previous 14 days. Returns (hours or None, bias °C or None)."""
    tag = datetime.now().strftime("%Y%m%d%H")
    try:
        fc = openmeteo.forecast_hourly(pin.lat, pin.lon, tag)
    except Exception:
        return None, None
    stamps = season_stamps(season)
    est = pd.Series(pin.hourly[season], index=stamps)
    a0 = pd.Timestamp(asof) - pd.Timedelta(days=13) + pd.Timedelta(hours=1)
    a1 = pd.Timestamp(asof) + pd.Timedelta(days=1)
    both = pd.concat([fc.loc[a0:a1], est.loc[a0:a1]], axis=1, keys=["om", "pin"]).dropna()
    bias = float((both["om"] - both["pin"]).mean()) if len(both) > 48 else 0.0
    start = pd.Timestamp(asof) + pd.Timedelta(days=1, hours=1)
    fut = fc.loc[start:].dropna()
    nd = min(max_days, len(fut) // 24)
    if nd < 1:
        return None, bias
    idx = pd.date_range(start, periods=nd * 24, freq="h")
    hrs = fut.reindex(idx).interpolate(limit_direction="both").to_numpy() - bias
    return hrs, bias
