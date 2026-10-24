"""Hourly temperature rebuild from daily min and max (BUILD.md 4.5).

Method L: Linvill (1990) curve. Sine from sunrise to sunset, logarithmic decay
at night toward the next day's minimum. Implemented from the published
equations; verified against the chillR vignette values (tests/test_hourly.py).

Method B: borrowed station shape. For each gridded day window W, rescale the
nearest station's actual hourly curve to the pin's min and max. Falls back to
the next station, then Method L, when the station day is flat (< 0.5 °C range)
or has more than 4 missing hours. Windows blend linearly over ±3 hours.

Time convention: hourly series are indexed by hour-ending PST timestamps
(CIMIS style, 2400 -> 00:00 next day). A "day window" for gridded day label d is
24 consecutive stamps starting at d + lag_days + start_hour + 1h.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .daylength import daylength

# --- Method L --------------------------------------------------------------------


def linvill_hourly(lat: float, jday, tmin, tmax) -> np.ndarray:
    """Hourly temps (n_days, 24) for clock hours 0..23 of each day.

    The first day's pre-sunrise hours and the last day's post-sunset hours are
    NaN (they need the neighbouring day); pad the input by a day on each side.
    """
    jday = np.asarray(jday, dtype=np.float64)
    tmin = np.asarray(tmin, dtype=np.float64)
    tmax = np.asarray(tmax, dtype=np.float64)
    n = len(tmin)
    j_ext = np.concatenate([[jday[0] - 1], jday, [jday[-1] + 1]])
    rise_e, set_e, dl_e = daylength(lat, j_ext)
    rise, sset, dl = rise_e[1:-1], set_e[1:-1], dl_e[1:-1]
    prev_set = set_e[:-2]
    next_rise = rise_e[2:]
    prev_max = np.concatenate([[np.nan], tmax[:-1]])
    prev_min = np.concatenate([[np.nan], tmin[:-1]])
    next_min = np.concatenate([tmin[1:], [np.nan]])
    prev_dl = np.concatenate([[np.nan], dl[:-1]])
    t_sunset = tmin + (tmax - tmin) * np.sin(np.pi * dl / (dl + 4))
    prev_t_sunset = prev_min + (prev_max - prev_min) * np.sin(np.pi * prev_dl / (prev_dl + 4))

    out = np.full((n, 24), np.nan)
    for h in range(24):
        morn = h <= rise
        day = (h > rise) & (h <= sset)
        eve = h >= sset
        night_prev = np.maximum(1.0, 24 - (prev_set - rise))
        with np.errstate(invalid="ignore", divide="ignore"):
            t_m = prev_t_sunset - (prev_t_sunset - tmin) / np.log(night_prev) * np.log(h + 24 - prev_set + 1)
            t_d = tmin + (tmax - tmin) * np.sin(np.pi * (h - rise) / (dl + 4))
            t_e = t_sunset - (t_sunset - next_min) / np.log(24 - (sset - next_rise) + 1) * np.log(h - sset + 1)
        out[:, h] = np.where(morn, t_m, np.where(day, t_d, np.where(eve, t_e, np.nan)))
    # No sunrise/sunset (polar) is impossible at our latitudes but keep chillR's rule.
    polar = (dl <= 0) | (dl >= 24)
    if polar.any():
        out[polar] = ((tmax + tmin) / 2)[polar][:, None]
    return out


def linvill_series(lat: float, daily: pd.DataFrame) -> pd.Series:
    """Method L hourly series indexed by PST timestamps (clock hour h of day d -> stamp d+h).

    `daily` has a DatetimeIndex of consecutive days and columns tmin, tmax.
    Pre-sunrise hours of the first day and post-sunset hours of the last day are NaN.
    """
    idx = pd.DatetimeIndex(daily.index)
    hrs = linvill_hourly(lat, idx.day_of_year.to_numpy(), daily["tmin"].to_numpy(), daily["tmax"].to_numpy())
    stamps = (idx.values[:, None] + (np.arange(24) * np.timedelta64(1, "h"))[None, :]).ravel()
    return pd.Series(hrs.ravel(), index=pd.DatetimeIndex(stamps), name="t_c")


# --- Day windows ---------------------------------------------------------------------


@dataclass(frozen=True)
class Window:
    """Gridded day label d covers 24 hour-ending stamps starting at d + lag + start_hour + 1h."""
    start_hour: int = 0   # 0 = midnight PST, 4 = 4 am, 7 = 7 am
    lag_days: int = 0     # 0 or -1

    def first_stamp(self, days: pd.DatetimeIndex) -> np.ndarray:
        return (days + pd.Timedelta(days=self.lag_days) + pd.Timedelta(hours=self.start_hour + 1)).values

    def label(self) -> str:
        return f"{self.start_hour:02d}h_lag{self.lag_days}"


MIDNIGHT = Window(0, 0)


def window_minmax(hourly: pd.Series, days: pd.DatetimeIndex, win: Window, max_missing: int = 4):
    """Station daily (tmin, tmax, n_missing) under a window definition.

    `hourly` must be indexed by a regular hourly PST DatetimeIndex.
    Days with more than `max_missing` missing hours get NaN min/max.
    """
    grid = window_matrix(hourly, days, win)
    nmiss = np.isnan(grid).sum(axis=1)
    with np.errstate(all="ignore"):
        tmin = np.nanmin(np.where(np.isnan(grid), np.inf, grid), axis=1)
        tmax = np.nanmax(np.where(np.isnan(grid), -np.inf, grid), axis=1)
    bad = nmiss > max_missing
    tmin = np.where(bad | ~np.isfinite(tmin), np.nan, tmin)
    tmax = np.where(bad | ~np.isfinite(tmax), np.nan, tmax)
    return tmin, tmax, nmiss


def window_matrix(hourly: pd.Series, days: pd.DatetimeIndex, win: Window, pad: int = 0) -> np.ndarray:
    """(n_days, 24 + 2*pad) matrix of station temps for each window, padded by `pad` hours each side."""
    first = win.first_stamp(days)
    offs = np.arange(-pad, 24 + pad) * np.timedelta64(1, "h")
    stamps = (first[:, None] + offs[None, :]).ravel()
    vals = hourly.reindex(pd.DatetimeIndex(stamps)).to_numpy(dtype=np.float64)
    return vals.reshape(len(days), 24 + 2 * pad)


# --- Method B --------------------------------------------------------------------------

BLEND_H = 3


def borrowed_shape(
    pin_daily: pd.DataFrame,
    station_hourly: list[pd.Series],
    lat: float,
    win: Window = MIDNIGHT,
    min_range: float = 0.5,
    max_missing: int = 4,
) -> tuple[pd.Series, pd.Series]:
    """Method B hourly series at the pin.

    pin_daily: DatetimeIndex of consecutive gridded day labels; columns tmin, tmax (°C).
    station_hourly: candidate stations' hourly series (nearest first), each on a
        regular hourly PST index. Short gaps (<= max_missing hours) are interpolated.
    Returns (hourly series on PST stamps, per-day source code: 0..k station index, -1 Method L).
    """
    days = pd.DatetimeIndex(pin_daily.index)
    n = len(days)
    pad = BLEND_H
    pmin = pin_daily["tmin"].to_numpy(dtype=np.float64)
    pmax = pin_daily["tmax"].to_numpy(dtype=np.float64)

    # Per-day choice of station, plus the scaled curve over the padded window.
    curves = np.full((n, 24 + 2 * pad), np.nan)
    source = np.full(n, -1, dtype=np.int64)
    for k, st in enumerate(station_hourly):
        todo = source == -1
        if not todo.any():
            break
        raw = window_matrix(st, days, win, pad=0)
        nmiss = np.isnan(raw).sum(axis=1)
        st_f = st.interpolate(limit=max_missing, limit_area="inside")
        grid = window_matrix(st_f, days, win, pad=pad)
        core = grid[:, pad:pad + 24]
        with np.errstate(all="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN days are expected (station offline)
            smin = np.nanmin(core, axis=1)
            smax = np.nanmax(core, axis=1)
        rng = smax - smin
        ok = todo & (nmiss <= max_missing) & np.isfinite(rng) & (rng >= min_range) & np.isfinite(pmin) & np.isfinite(pmax)
        ok &= ~np.isnan(core).any(axis=1)
        if ok.any():
            scaled = pmin[:, None] + (grid - smin[:, None]) / rng[:, None] * (pmax - pmin)[:, None]
            curves[ok] = scaled[ok]
            source[ok] = k

    # Method L for days no station could serve (and to fill padded edges).
    lin = linvill_series(lat, pin_daily[["tmin", "tmax"]].shift(-win.lag_days) if win.lag_days else pin_daily[["tmin", "tmax"]])
    lin_full = lin.reindex(pd.date_range(lin.index.min() - pd.Timedelta(hours=48), lin.index.max() + pd.Timedelta(hours=48), freq="h"))
    lin_full = lin_full.interpolate(limit_direction="both")
    lgrid = window_matrix(lin_full, days, win, pad=pad)
    use_l = source == -1
    curves[use_l] = lgrid[use_l]
    # Station curves may have NaN in the padding (edges of the record): fill from L.
    holes = np.isnan(curves)
    curves[holes] = lgrid[holes]

    # Assemble with linear blending across window boundaries.
    core = curves[:, pad:pad + 24].copy()
    if n > 1:
        w = (np.arange(2 * pad) + 0.5) / (2 * pad)  # weight on the later day
        # Boundary between day i and i+1: last `pad` stamps of day i, first `pad` of day i+1.
        left = np.concatenate([curves[:-1, pad + 24 - pad:pad + 24], curves[:-1, pad + 24:pad + 24 + pad]], axis=1)
        right = np.concatenate([curves[1:, 0:pad], curves[1:, pad:2 * pad]], axis=1)
        blend = (1 - w)[None, :] * left + w[None, :] * right
        core[:-1, 24 - pad:24] = blend[:, :pad]
        core[1:, 0:pad] = blend[:, pad:]
    first = win.first_stamp(days)
    stamps = (first[:, None] + (np.arange(24) * np.timedelta64(1, "h"))[None, :]).ravel()
    series = pd.Series(core.ravel(), index=pd.DatetimeIndex(stamps), name="t_c")
    return series, pd.Series(source, index=days, name="source")


def regular_hourly(s: pd.Series) -> pd.Series:
    """Put a series on a complete hourly index (missing hours become NaN)."""
    s = s[~s.index.duplicated()].sort_index()
    if s.empty:
        return s
    return s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="h"))
