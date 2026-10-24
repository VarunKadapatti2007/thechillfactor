"""Analog winters: which past seasons feed the outlook, and the closest past winter (BUILD.md 4.8)."""
from __future__ import annotations

from datetime import date

import numpy as np

from ..pipeline.build_pin import Pin
from .core import dos, season_daily_cum, start_dos


def analog_seasons(pin: Pin, exclude: int) -> list[int]:
    return [y for y in pin.complete_seasons() if y != exclude]


def closest_winter(pin: Pin, season: int, asof: date, start: str = "sep1", window: int = 30):
    """Past winter whose cumulative CP curve over the last 30 days best matches (RMSE, CP).

    When the curves are uninformative (early season, near-zero chill), ties are
    broken by daily mean temperature over the same days.
    """
    kd = dos(season, asof)
    k0 = max(start_dos(start), kd - window + 1)
    cur = season_daily_cum(pin, season, start)
    if kd < k0 or np.isnan(cur[kd]):
        return None, None
    a = cur[k0:kd + 1]
    ta = pin.hourly[season][k0 * 24:(kd + 1) * 24].reshape(-1, 24).mean(axis=1)
    best = []
    for y in pin.history_seasons():
        if y == season:
            continue
        b = season_daily_cum(pin, y, start)[k0:kd + 1]
        if len(b) != len(a) or np.isnan(b).any():
            continue
        tb = pin.hourly[y][k0 * 24:(kd + 1) * 24].reshape(-1, 24).mean(axis=1)
        rmse = float(np.sqrt(np.mean((a - b) ** 2)))
        trmse = float(np.sqrt(np.mean((ta - tb) ** 2)))
        best.append((round(rmse, 1), trmse, y, rmse))
    if not best:
        return None, None
    best.sort()
    _, _, y, rmse = best[0]
    return y, rmse
