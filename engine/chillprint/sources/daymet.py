"""Daymet V4 single-pixel client (BUILD.md 3.3), with gridMET as a fallback grid.

Daymet uses 365-day years: in leap years Dec 31 is dropped. We fill it by
linear interpolation and flag it (`filled=True`).
"""
from __future__ import annotations

import io
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import numpy as np
import pandas as pd

from . import cache

SRC = "daymet"
URL = "https://daymet.ornl.gov/single-pixel/api/data"
START, END = "1980-01-01", "2025-12-31"


def _key(lat: float, lon: float) -> str:
    return f"daymet_{lat:.4f}_{lon:.4f}_{START}_{END}"


def fetch_raw(lat: float, lon: float) -> bytes:
    return cache.cached(SRC, _key(lat, lon), lambda: cache.http_get(URL, params={
        "lat": f"{lat:.4f}", "lon": f"{lon:.4f}", "vars": "tmax,tmin,srad,dayl",
        "start": START, "end": END}, timeout=180))


def is_cached(lat: float, lon: float) -> bool:
    return cache.has(SRC, _key(lat, lon))


def parse(raw: bytes) -> tuple[pd.DataFrame, dict]:
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    meta = {}
    hdr = None
    for i, ln in enumerate(lines):
        if ln.startswith("year,yday"):
            hdr = i
            break
        if ln.startswith("Elevation:"):
            try:
                meta["elev_m"] = float(ln.split(":")[1].split()[0])
            except ValueError:
                pass
    if hdr is None:
        raise ValueError("Daymet response has no 'year,yday' header: " + text[:200])
    df = pd.read_csv(io.StringIO("\n".join(lines[hdr:])))
    df.columns = [c.split(" (")[0].strip() for c in df.columns]
    df["date"] = pd.to_datetime(df["year"].astype(str) + "-01-01") + pd.to_timedelta(df["yday"] - 1, unit="D")
    df = df.set_index("date")[["tmin", "tmax", "srad", "dayl"]]
    # Fill leap-year Dec 31 (Daymet drops it) by interpolation, and flag it.
    full = pd.date_range(df.index.min(), df.index.max(), freq="D")
    df = df.reindex(full)
    df["filled"] = df["tmin"].isna()
    df[["tmin", "tmax", "srad", "dayl"]] = df[["tmin", "tmax", "srad", "dayl"]].interpolate(limit=3)
    df.index.name = "date"
    return df, meta


def daily(lat: float, lon: float) -> tuple[pd.DataFrame, dict]:
    """Daily tmin/tmax (°C), srad, dayl at a pixel, 1980-01-01..2025-12-31."""
    df, meta = parse(fetch_raw(lat, lon))
    meta["source"] = "daymet"
    return df, meta


# --- gridMET fallback (4 km; includes the current season) ---------------------

GRIDMET_URL = "http://thredds.northwestknowledge.net:8080/thredds/ncss/agg_met_{v}_1979_CurrentYear_CONUS.nc"
GRIDMET_VARS = {"tmmn": "daily_minimum_temperature", "tmmx": "daily_maximum_temperature"}


def _gridmet_var(short: str, long: str, lat: float, lon: float, start: date, end: date, tag: str) -> pd.Series:
    key = f"gridmet_{short}_{lat:.4f}_{lon:.4f}_{start}_{end}{tag}"
    raw = cache.cached("gridmet", key, lambda: cache.http_get_once(
        GRIDMET_URL.format(v=short), params={
            "var": long, "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}",
            "time_start": f"{start}T00:00:00Z", "time_end": f"{end}T00:00:00Z", "accept": "csv"},
        timeout=45))
    df = pd.read_csv(io.BytesIO(raw))
    col = [c for c in df.columns if c.startswith(long)][0]
    vals = df[col].astype(float)
    vals = vals.where(vals != 32767)
    # NCSS returns packed values: K = raw * 0.1 + 210 (see DATA_SOURCES.md).
    return pd.Series(vals.to_numpy() * 0.1 + 210.0 - 273.15,
                     index=pd.to_datetime(df["time"]).dt.tz_localize(None).dt.normalize())


def gridmet_daily(lat: float, lon: float, start: date, end: date, tag: str = "") -> pd.DataFrame:
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = {short: ex.submit(_gridmet_var, short, long, lat, lon, start, end, tag) for short, long in GRIDMET_VARS.items()}
        out = {k: f.result() for k, f in futs.items()}
    res = pd.DataFrame({"tmin": out["tmmn"], "tmax": out["tmmx"]})
    res.index.name = "date"
    res["filled"] = False
    return res.astype({"tmin": np.float64, "tmax": np.float64})
