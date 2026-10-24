"""Read the Phase 1 hourly stores (CIMIS per station-season, Wildeye) as regular hourly series."""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd

from .. import config as C
from ..science.hourly import MIDNIGHT, Window, regular_hourly

HOURLY_DIR = C.PROCESSED_DIR / "cimis_hourly"
WILDEYE_PQ = C.PROCESSED_DIR / "wildeye_hourly.parquet"
ALIGN_JSON = C.PROCESSED_DIR / "alignment.json"
STATIONS_PQ = C.PROCESSED_DIR / "stations.parquet"


@lru_cache(maxsize=1)
def stations() -> pd.DataFrame:
    return pd.read_parquet(STATIONS_PQ)


@lru_cache(maxsize=1)
def hourly_index() -> dict[str, list[int]]:
    """station id -> seasons with a non-empty hourly file."""
    out: dict[str, list[int]] = {}
    if not HOURLY_DIR.exists():
        return out
    for p in HOURLY_DIR.glob("station=*/season=*.parquet"):
        if p.stat().st_size < 2000:  # empty frames are tiny
            continue
        sid = p.parent.name.split("=", 1)[1]
        out.setdefault(sid, []).append(int(p.stem.split("=")[1]))
    for v in out.values():
        v.sort()
    return out


@lru_cache(maxsize=96)
def station_hourly(sid: str) -> pd.Series:
    """All pulled hours for a CIMIS station, °C, on a regular hourly PST index (gaps NaN)."""
    seasons = hourly_index().get(sid, [])
    frames = []
    for y in seasons:
        df = pd.read_parquet(HOURLY_DIR / f"station={sid}" / f"season={y}.parquet", columns=["ts", "t_c"])
        if len(df):
            frames.append(df)
    if not frames:
        return pd.Series(dtype="float64")
    df = pd.concat(frames)
    s = pd.Series(df["t_c"].to_numpy(dtype=np.float64), index=pd.to_datetime(df["ts"]))
    return regular_hourly(s)


@lru_cache(maxsize=1)
def _wildeye_all() -> pd.DataFrame:
    if not WILDEYE_PQ.exists():
        return pd.DataFrame(columns=["station_id", "ts", "t_c"])
    return pd.read_parquet(WILDEYE_PQ, columns=["station_id", "ts", "t_c", "srad"])


@lru_cache(maxsize=32)
def wildeye_hourly(sid: str) -> pd.Series:
    w = _wildeye_all()
    w = w[w.station_id == sid]
    s = pd.Series(w["t_c"].to_numpy(dtype=np.float64), index=pd.to_datetime(w["ts"]))
    return regular_hourly(s)


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(np.asarray(lon2) - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def nearest_cimis(lat: float, lon: float, exclude: tuple[str, ...] = (), with_hourly: bool = False,
                  season: int | None = None, k: int = 6) -> pd.DataFrame:
    """Nearest CIMIS stations (any county) sorted by distance, optionally only those with hourly data."""
    st = stations()
    st = st[(st.network == "CIMIS") & ~st.id.isin(exclude)].copy()
    if with_hourly:
        idx = hourly_index()
        st = st[st.id.map(lambda s: s in idx and (season is None or season in idx[s]))]
    st["dist_km"] = haversine_km(lat, lon, st.lat.to_numpy(), st.lon.to_numpy())
    return st.sort_values("dist_km").head(k)


@lru_cache(maxsize=1)
def complete_seasons() -> dict[str, set[int]]:
    """station id -> seasons with >= 95% of hours Sept 1 - Mar 1 (from the QC coverage table)."""
    p = C.PROCESSED_DIR / "hourly_coverage.parquet"
    if not p.exists():
        return {}
    t = pd.read_parquet(p)
    t = t[t.coverage >= 0.95]
    out: dict[str, set[int]] = {}
    for sid, y in zip(t.station_id, t.season):
        out.setdefault(sid, set()).add(int(y))
    return out


def window_for(product: str = "daymet") -> Window:
    if ALIGN_JSON.exists():
        js = json.loads(ALIGN_JSON.read_text())
        if product in js and "best" in js[product]:
            b = js[product]["best"]
            return Window(int(b["start_hour"]), int(b["lag_days"]))
    return MIDNIGHT
