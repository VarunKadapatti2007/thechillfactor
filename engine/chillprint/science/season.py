"""Season-level chill from an hourly series.

Hourly series use hour-ending PST stamps. A day's hours are stamps 01:00..24:00
(24:00 = 00:00 next day), the CIMIS convention, so the calendar day of a stamp
is (stamp - 1 h).date(). This is also how FNRIC attributes hours to days.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from . import chill
from .hourly import regular_hourly


def season_bounds(season: int, start: str = "sep1", end: date | None = None) -> tuple[pd.Timestamp, pd.Timestamp]:
    s0 = pd.Timestamp(season, 9, 1) if start == "sep1" else pd.Timestamp(season, 11, 1)
    e = pd.Timestamp(end) if end is not None else pd.Timestamp(season + 1, 3, 31)
    return s0 + pd.Timedelta(hours=1), e + pd.Timedelta(days=1)  # first and last hour-ending stamps


def prep_hourly(hourly: pd.Series, season: int, start: str = "sep1", end: date | None = None,
                max_gap_h: int = 0) -> tuple[pd.Series, int]:
    """Season slice on a complete hourly index; gaps up to `max_gap_h` hours linearly filled.

    The default (0) follows FNRIC: missing hours are skipped and the Dynamic Model
    holds its state, which reproduces FNRIC's daily portions exactly.

    Returns (series, number of hours still missing).
    """
    a, b = season_bounds(season, start, end)
    s = regular_hourly(hourly).reindex(pd.date_range(a, b, freq="h"))
    if max_gap_h > 0:
        s = s.interpolate(limit=max_gap_h, limit_area="inside")
    return s, int(s.isna().sum())


def daily_chill(hourly: pd.Series, season: int, start: str = "sep1", end: date | None = None,
                max_gap_h: int = 0) -> pd.DataFrame:
    """Daily chill amounts and cumulative CP for one season from hourly °C."""
    s, _ = prep_hourly(hourly, season, start, end, max_gap_h)
    t = s.to_numpy()
    cp, state = chill.dynamic_portions(t)
    day = (s.index - pd.Timedelta(hours=1)).normalize()
    df = pd.DataFrame({
        "date": day,
        "portions_dynamic": cp,
        "hours_lt_45": chill.hours_below_45(t),
        "hours_32_45": chill.hours_32_45(t),
        "units_utah": chill.utah_units(t),
        "present": ~np.isnan(t),
    })
    g = df.groupby("date").agg(portions_dynamic=("portions_dynamic", "sum"), hours_lt_45=("hours_lt_45", "sum"),
                                hours_32_45=("hours_32_45", "sum"), units_utah=("units_utah", "sum"),
                                n_hours=("present", "sum"))
    g["cp_cum"] = g["portions_dynamic"].cumsum()
    g.attrs["end_state"] = state
    return g


def cp_cumulative_hourly(hourly_values: np.ndarray) -> np.ndarray:
    p, _ = chill.dynamic_portions(hourly_values)
    return np.cumsum(p)
