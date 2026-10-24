"""Sunny-stretch flag (BUILD.md Phase 6 step 3). A heuristic, labeled as such.

Counts clear dormant days in the 14 days up to the as-of date, from the nearest
CIMIS station's hourly solar radiation: a day is clear when its total radiation
exceeds 70% of a clear-sky estimate (FAO-56: 0.75 x extraterrestrial radiation).
Seven or more clear days in 14 -> "Sunny stretch: tree chill likely lower than
shown" (UC Davis TreeChill research: sunlit buds run warmer than the air).
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from ..pipeline import station_hourly as SH

CLEAR_FRACTION = 0.70
MIN_CLEAR_DAYS = 7
DORMANT_MONTHS = (11, 12, 1, 2)


def extraterrestrial_mj(lat: float, doy: np.ndarray) -> np.ndarray:
    """FAO-56 eq. 21: daily extraterrestrial radiation, MJ/m²/day."""
    phi = np.radians(lat)
    dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365)
    delta = 0.409 * np.sin(2 * np.pi * doy / 365 - 1.39)
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(delta), -1, 1))
    return 24 * 60 / np.pi * 0.0820 * dr * (ws * np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.sin(ws))


def station_solar(sid: str) -> pd.Series:
    """Hourly solar radiation (W/m²) for a CIMIS station from the hourly store."""
    from ..config import PROCESSED_DIR
    frames = []
    for y in SH.hourly_index().get(sid, []):
        p = PROCESSED_DIR / "cimis_hourly" / f"station={sid}" / f"season={y}.parquet"
        df = pd.read_parquet(p, columns=["ts", "srad"])
        frames.append(df)
    if not frames:
        return pd.Series(dtype=float)
    df = pd.concat(frames)
    return pd.Series(df["srad"].to_numpy(dtype=float), index=pd.to_datetime(df["ts"])).sort_index()


def sunny_stretch(lat: float, lon: float, asof: date) -> bool | None:
    """True/False when it can be judged; None outside the dormant months or without solar data."""
    if asof.month not in DORMANT_MONTHS:
        return None
    near = SH.nearest_cimis(lat, lon, with_hourly=True, k=2)
    for sid in near.id:
        s = station_solar(sid)
        if s.empty:
            continue
        a = pd.Timestamp(asof - timedelta(days=13))
        win = s.loc[a + pd.Timedelta(hours=1):pd.Timestamp(asof) + pd.Timedelta(days=1)]
        if win.notna().sum() < 14 * 20:
            continue
        day = (win.index - pd.Timedelta(hours=1)).normalize()
        daily_mj = win.groupby(day).sum() * 3600 / 1e6  # W/m² hourly means -> MJ/m²/day
        clear_sky = 0.75 * extraterrestrial_mj(lat, daily_mj.index.day_of_year.to_numpy())
        clear_days = int((daily_mj.to_numpy() > CLEAR_FRACTION * clear_sky).sum())
        return clear_days >= MIN_CLEAR_DAYS
    return None
