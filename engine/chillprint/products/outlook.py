"""Odds of reaching the need (BUILD.md 4.7).

Observed hours to the as-of date, then (live only) the bias-shifted Open-Meteo
forecast, then each past winter's hours through the by date. The Dynamic Model
continues from the observed state over each concatenated series; CP totals are
never added across segments. Analogs always exclude the season being judged.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from .. import config as C
from ..pipeline.build_pin import Pin
from ..science import chill
from .analogs import analog_seasons
from .core import dos, shifted_hourly, start_dos, state_at_day_end


@dataclass
class Outlook:
    cp_obs: float
    finals: np.ndarray
    fan_days: list[date]
    fan: np.ndarray  # (n_days, 3) p10 p50 p90 of cumulative CP
    analogs: list[int]
    forecast_days: int

    def pct(self, q: float) -> float:
        return float(np.percentile(self.finals, q)) if len(self.finals) else self.cp_obs

    def chance(self, need: float) -> float:
        return float(np.mean(self.finals >= need - 1e-9)) if len(self.finals) else float(self.cp_obs >= need)


def _analog_matrix(pin: Pin, analogs: list[int], k0: int, k1: int, climate: str, ref_season: int) -> np.ndarray:
    """Hours of day k0..k1 (inclusive, day of season) for each analog, shifted to ref_season's climate if asked."""
    rows = []
    n = (k1 - k0 + 1) * 24
    for y in analogs:
        a = shifted_hourly(pin, y, ref_season) if climate == "today" else pin.hourly[y]
        seg = a[k0 * 24:(k1 + 1) * 24]
        if len(seg) < n:  # leap-year length differences: pad with the last day
            seg = np.concatenate([seg, np.resize(seg[-24:], n - len(seg))])
        rows.append(seg)
    return np.vstack(rows) if rows else np.zeros((0, n))


def outlook(pin: Pin, season: int, asof: date, by: date, start: str = "sep1", climate: str = "today",
            forecast: np.ndarray | None = None, analogs: list[int] | None = None) -> Outlook:
    """`forecast`: hourly temps for whole days starting the day after `asof` (live mode only)."""
    kd = dos(season, asof)
    kb = dos(season, by)
    s0 = start_dos(start)
    analogs = analog_seasons(pin, season) if analogs is None else analogs

    if kd >= kb:  # the by date has passed: everything is observed
        _, cp = state_at_day_end(pin, season, kb, start)
        return Outlook(cp, np.array([cp] * max(1, len(analogs))), [], np.zeros((0, 3)), analogs, 0)

    if kd < s0:
        state, cp_obs = (0.0, 0.0), 0.0
        nxt = s0
    else:
        state, cp_obs = state_at_day_end(pin, season, kd, start)
        nxt = kd + 1

    fan_days: list[date] = []
    fan_rows: list[tuple[float, float, float]] = []
    cp_run = cp_obs
    nf = 0
    if forecast is not None and len(forecast) >= 24 and nxt == kd + 1:
        nf = min(len(forecast) // 24, kb - nxt + 1)
        fp, state = chill.dynamic_portions(forecast[: nf * 24], state=state)
        daily = np.cumsum(fp)[23::24]
        for i in range(nf):
            v = cp_obs + float(daily[i])
            fan_days.append(date(season, 9, 1) + timedelta(days=nxt + i))
            fan_rows.append((v, v, v))
        cp_run = cp_obs + float(fp.sum())
        nxt += nf

    if nxt > kb:
        return Outlook(cp_obs, np.array([cp_run] * max(1, len(analogs))), fan_days, np.array(fan_rows), analogs, nf)

    M = _analog_matrix(pin, analogs, nxt, kb, climate, season)
    cum = chill.dynamic_batch_cumulative(M, state=state)  # (n_analogs, hours)
    day_end = cp_run + cum[:, 23::24]
    q = np.percentile(day_end, [10, 50, 90], axis=0).T
    for i in range(day_end.shape[1]):
        fan_days.append(date(season, 9, 1) + timedelta(days=nxt + i))
        fan_rows.append(tuple(q[i]))
    return Outlook(cp_obs, day_end[:, -1], fan_days, np.array(fan_rows), analogs, nf)
