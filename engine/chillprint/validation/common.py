"""Shared helpers for the validation protocol (BUILD.md section 5)."""
from __future__ import annotations

from datetime import date
from functools import lru_cache

import numpy as np
import pandas as pd

from .. import config as C
from ..pipeline import station_hourly as SH
from ..pipeline.build_pin import monthly_offset, offset_hourly, season_stamps
from ..science import chill
from ..science.hourly import Window, borrowed_shape, linvill_series, window_minmax

OUT = C.VALIDATION_DIR
BY_DATES = {"feb1": "02-01", "mar1": "03-01"}
# Earlier as-of dates, used to scale the error bar through the season (errorbar.py).
ASOF_DATES = {"nov1": "11-01", "dec1": "12-01", "jan1": "01-01"}
CROSS = (23.0, 54.0)
MIN_COVERAGE = 0.95
MAX_GAP_H = 6


def dos(season: int, mmdd: str) -> int:
    return (C.by_date(season, mmdd) - date(season, 9, 1)).days


def coverage(hourly: pd.Series, season: int) -> float:
    """Share of hours present from Sept 1 through Mar 1 (BUILD.md 5.1)."""
    idx = pd.date_range(f"{season}-09-01 01:00", f"{season + 1}-03-02 00:00", freq="h")
    return float(hourly.reindex(idx).notna().mean())


def season_hourly(hourly: pd.Series, season: int) -> np.ndarray:
    """Station truth hours on standard stamps. Missing hours stay NaN: the Dynamic Model skips
    them and holds its state, FNRIC's convention, which reproduces FNRIC's daily chill exactly."""
    return hourly.reindex(season_stamps(season)).to_numpy(dtype=np.float64)


def daily_cum(hours: np.ndarray) -> np.ndarray:
    p, _ = chill.dynamic_portions(hours)
    return np.cumsum(p)[23::24]


def cross_day(cum: np.ndarray, level: float) -> float:
    i = np.argmax(cum >= level)
    return float(i) if cum[i] >= level else np.nan


def metrics(cum: np.ndarray, season: int) -> dict:
    out = {f"cp_{k}": float(cum[dos(season, v)]) for k, v in {**ASOF_DATES, **BY_DATES}.items()}
    for lv in CROSS:
        out[f"cross{int(lv)}"] = cross_day(cum, lv)
    return out


def terrain(elev: float | None, nb_elev: float | None) -> str:
    if elev is None or (isinstance(elev, float) and np.isnan(elev)):
        return "valley"
    if elev > C.FOOTHILL_ELEV_M or (nb_elev is not None and not np.isnan(nb_elev) and elev - nb_elev > C.FOOTHILL_DELEV_M):
        return "foothill"
    return "valley"


@lru_cache(maxsize=256)
def daymet_pixel(sid: str) -> pd.DataFrame | None:
    p = C.PROCESSED_DIR / "daymet" / f"{sid}.parquet"
    return pd.read_parquet(p) if p.exists() else None


@lru_cache(maxsize=1)
def coverage_table() -> pd.DataFrame:
    """(station_id, season) -> coverage, for every pulled CIMIS station-season."""
    p = C.PROCESSED_DIR / "hourly_coverage.parquet"
    if p.exists():
        return pd.read_parquet(p)
    rows = []
    for sid, seasons in SH.hourly_index().items():
        h = SH.station_hourly(sid)
        for y in seasons:
            rows.append({"station_id": sid, "season": y, "coverage": coverage(h, y)})
    return pd.DataFrame(rows)


def complete_set() -> set[tuple[str, int]]:
    t = coverage_table()
    t = t[t.coverage >= MIN_COVERAGE]
    return set(zip(t.station_id, t.season))


def neighbors(lat: float, lon: float, season: int, exclude: tuple[str, ...], complete: set, k: int = 5) -> pd.DataFrame:
    """Nearest other CIMIS stations with a complete record that season."""
    st = SH.stations()
    st = st[(st.network == "CIMIS") & ~st.id.isin(exclude)].copy()
    st = st[[(s, season) in complete for s in st.id]]
    st["dist_km"] = SH.haversine_km(lat, lon, st.lat.to_numpy(), st.lon.to_numpy())
    return st.sort_values("dist_km").head(k)


def e2_hours(lat: float, dm: pd.DataFrame, season: int, win: Window) -> np.ndarray:
    d = dm.loc[pd.Timestamp(season, 8, 29):pd.Timestamp(season + 1, 4, 3), ["tmin", "tmax"]].interpolate(limit_direction="both")
    lin = linvill_series(lat, d.shift(-win.lag_days) if win.lag_days else d)
    return lin.reindex(season_stamps(season)).interpolate(limit_direction="both").to_numpy()


def b_hours(lat: float, daily: pd.DataFrame, season: int, shapes: list[pd.Series], win: Window) -> np.ndarray:
    d = daily.loc[pd.Timestamp(season, 8, 29):pd.Timestamp(season + 1, 4, 3), ["tmin", "tmax"]].interpolate(limit_direction="both")
    s, _ = borrowed_shape(d, shapes, lat, win)
    return s.reindex(season_stamps(season)).interpolate(limit_direction="both").to_numpy()


def e4_hours(nb_hourly: pd.Series, dm_s: pd.DataFrame, dm_nb: pd.DataFrame, season: int) -> np.ndarray:
    off = monthly_offset(dm_s, dm_nb)
    seg = nb_hourly.loc[pd.Timestamp(season, 8, 31):pd.Timestamp(season + 1, 4, 2)]
    seg = seg.interpolate(limit=MAX_GAP_H, limit_area="inside")
    e4 = offset_hourly(seg, off)
    return e4.reindex(season_stamps(season)).interpolate(limit_direction="both").to_numpy()


def own_window_daily(hourly: pd.Series, season: int, win: Window) -> pd.DataFrame:
    days = pd.date_range(pd.Timestamp(season, 8, 29), pd.Timestamp(season + 1, 4, 3), freq="D")
    tmin, tmax, _ = window_minmax(hourly, days, win, max_missing=4)
    return pd.DataFrame({"tmin": tmin, "tmax": tmax}, index=days)


def hourly_rmse(est: np.ndarray, truth: np.ndarray, season: int) -> float:
    n = (dos(season, "03-01") + 1) * 24
    a, b = est[:n], truth[:n]
    ok = np.isfinite(a) & np.isfinite(b)
    return float(np.sqrt(np.mean((a[ok] - b[ok]) ** 2)))


def fnric_truth_cum(sid: str, season: int) -> np.ndarray | None:
    """FNRIC daily portions cumulated from Sept 1 (fallback truth when CIMIS hourly is absent)."""
    f = _fnric()
    if sid not in f.index.get_level_values(0):
        return None
    s = f.loc[sid]["portions_dynamic"].reindex(pd.date_range(f"{season}-09-01", f"{season + 1}-03-31", freq="D"))
    if s.loc[:f"{season + 1}-03-01"].isna().mean() > 0.05:
        return None
    return s.fillna(0).cumsum().to_numpy()


@lru_cache(maxsize=1)
def _fnric() -> pd.DataFrame:
    f = pd.read_parquet(C.PROCESSED_DIR / "fnric_daily_chill.parquet")
    f["date"] = pd.to_datetime(f["date"])
    return f.set_index(["station_id", "date"]).sort_index()
