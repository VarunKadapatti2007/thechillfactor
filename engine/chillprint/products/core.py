"""Shared season math for products: cumulative CP per season, day indexing, climate shift."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
from scipy.stats import theilslopes

from .. import config as C
from ..pipeline.build_pin import Pin
from ..science import chill


def dos(season: int, d: date) -> int:
    """Day of season, 0 = Sept 1."""
    return (d - date(season, 9, 1)).days


def start_dos(start: str) -> int:
    return 0 if start == "sep1" else 61  # Nov 1 is always day 61


def day_date(season: int, k: int) -> date:
    return date(season, 9, 1) + timedelta(days=k)


def observed_days(pin: Pin, season: int) -> int:
    """Days up to the last observed hour (a live season ends in NaN; interior gaps are skipped hours)."""
    a = pin.hourly[season]
    fin = np.flatnonzero(np.isfinite(a))
    return 0 if len(fin) == 0 else int((fin[-1] + 1) // 24)


def season_daily_cum(pin: Pin, season: int, start: str = "sep1") -> np.ndarray:
    """Cumulative CP at the end of each day of the season (index = day of season). NaN beyond observed data."""
    ck = ("cum", season, start)
    if ck in pin.memo:
        return pin.memo[ck]
    a = pin.hourly[season]
    nd = len(a) // 24
    s0 = start_dos(start)
    n_obs = observed_days(pin, season)
    out = np.full(nd, np.nan)
    out[:s0] = 0.0
    if n_obs > s0:
        p, _ = chill.dynamic_portions(a[s0 * 24:n_obs * 24])
        cum = np.cumsum(p)
        out[s0:n_obs] = cum[23::24][: n_obs - s0]
    pin.memo[ck] = out
    return out


def state_at_day_end(pin: Pin, season: int, k: int, start: str = "sep1"):
    """Dynamic Model state and CP after day k (day of season), counted from the season start."""
    a = pin.hourly[season]
    s0 = start_dos(start)
    if k < s0:
        return None, 0.0
    p, st = chill.dynamic_portions(a[s0 * 24:(k + 1) * 24])
    return st, float(p.sum())


# --- Today's-climate shift (BUILD.md 4.7 step 6) --------------------------------------


def monthly_slopes(pin: Pin) -> dict[int, tuple[float, float]]:
    """Theil-Sen trend (°C/yr) of each month's mean Tmin and Tmax at the pin, 1981-2025."""
    if "slopes" in pin.memo:
        return pin.memo["slopes"]
    df = pin.daily.loc["1981-01-01":"2025-12-31", ["tmin", "tmax"]].dropna()
    out = {}
    for m in (9, 10, 11, 12, 1, 2, 3, 4):
        sub = df[df.index.month == m]
        ann = sub.groupby(sub.index.year).mean().loc[1981:2025]
        if len(ann) < 10:
            out[m] = (0.0, 0.0)
            continue
        yrs = ann.index.to_numpy(dtype=float)
        out[m] = (float(theilslopes(ann["tmin"].to_numpy(), yrs)[0]), float(theilslopes(ann["tmax"].to_numpy(), yrs)[0]))
    pin.memo["slopes"] = out
    return out


def shifted_hourly(pin: Pin, season: int, ref_season: int) -> np.ndarray:
    """Season's hours shifted to the climate of ref_season: Tmin by slope_min*dy, Tmax by slope_max*dy."""
    ck = ("shift", season, ref_season)
    if ck in pin.memo:
        return pin.memo[ck]
    a = pin.hourly[season]
    dy = ref_season - season
    if dy == 0:
        return a
    sl = monthly_slopes(pin)
    nd = len(a) // 24
    m = a[: nd * 24].reshape(nd, 24)
    lo = np.nanmin(m, axis=1, keepdims=True)
    hi = np.nanmax(m, axis=1, keepdims=True)
    rng = np.where(hi - lo > 0.1, hi - lo, np.nan)
    p = np.nan_to_num((m - lo) / rng, nan=0.5).clip(0, 1)
    months = np.array([day_date(season, k).month for k in range(nd)])
    dmin = np.array([sl.get(mm, (0, 0))[0] for mm in months])[:, None] * dy
    dmax = np.array([sl.get(mm, (0, 0))[1] for mm in months])[:, None] * dy
    out = (m + dmin + p * (dmax - dmin)).ravel()
    pin.memo[ck] = out
    return out
