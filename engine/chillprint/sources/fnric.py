"""FNRIC weather models API client (BUILD.md 3.1).

Limited budget: every resource is fetched once and cached forever. Never loop.
"""
from __future__ import annotations

import io
import json
from datetime import date

import pandas as pd

from . import cache

BASE = "https://f5dby14cj5.execute-api.us-west-2.amazonaws.com/prod/"
SRC = "fnric"


def _num_after_slash(s: str) -> float:
    return float(str(s).split("/")[-1].strip())


def stations() -> pd.DataFrame:
    raw = cache.cached(SRC, "stations", lambda: cache.http_get(BASE + "stations"))
    st = pd.DataFrame(json.loads(raw)["stations"])
    st["lat"] = st["HmsLatitude"].map(_num_after_slash)
    st["lon"] = st["HmsLongitude"].map(_num_after_slash)
    st["network"] = st["StationID"].str.split("-").str[0]
    st["active"] = st["IsActive"].astype(bool)
    st["connect_date"] = pd.to_datetime(st["ConnectDate"]).dt.date
    return st.rename(columns={"StationID": "id", "Name": "name", "County": "county"})[
        ["id", "name", "county", "network", "lat", "lon", "active", "connect_date"]
    ]


def chill_download(station_id: str, refresh_tag: str | None = None) -> pd.DataFrame:
    """Full daily chill history for a station: daily amounts, sorted by date.

    `refresh_tag` lets the live season re-pull once per tag (e.g. a date); the
    default historical pull is cached forever.
    """
    key = f"chill_download_{station_id}" + (f"_{refresh_tag}" if refresh_tag else "")
    raw = cache.cached(SRC, key, lambda: cache.http_get(
        BASE + "chill-models-download", params={"station-id": station_id}, timeout=180))
    if not raw.strip():
        return pd.DataFrame(columns=["date", "hours_lt_45", "hours_32_45", "units_utah", "portions_dynamic"])
    df = pd.read_csv(io.BytesIO(raw))
    df = df.rename(columns={"Date": "date"})
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df.sort_values("date").drop_duplicates("date").reset_index(drop=True)


def chill_models(station_id: str, chill_year: str) -> pd.DataFrame:
    assert len(chill_year) == 9 and chill_year[4] == "-", "chill-year must be like 2025-2026"
    raw = cache.cached(SRC, f"chill_models_{station_id}_{chill_year}", lambda: cache.http_get(
        BASE + "chill-models", params={"station-id": station_id, "chill-year": chill_year}))
    df = pd.DataFrame(json.loads(raw).get("model_values", []))
    if df.empty:
        return df
    df = df.rename(columns={"Date": "date"})
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["gap"] = df["n_hours"] < 24
    return df.sort_values("date").reset_index(drop=True)


def stemwater(station_id: str, tag: str) -> pd.DataFrame:
    """Latest 300 hourly readings (°F) plus Dynamic Model state. `tag` scopes the cache (e.g. today's date)."""
    raw = cache.cached(SRC, f"stemwater_{station_id}_{tag}", lambda: cache.http_get(
        BASE + "stemwater", params={"station-id": station_id}))
    df = pd.DataFrame(json.loads(raw).get("hourly_values", []))
    if df.empty:
        return df
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    return df.sort_values("Timestamp").reset_index(drop=True)


def hull_split_gdd90(station_id: str, fbd: date) -> pd.DataFrame:
    raw = cache.cached(SRC, f"hullsplit_{station_id}_{fbd}", lambda: cache.http_get(
        BASE + "almond-hull-split-gdd90", params={"station-id": station_id, "fbd": str(fbd)}))
    df = pd.DataFrame(json.loads(raw).get("model_values", []))
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    return df.sort_values("Date").reset_index(drop=True)


def wildeye_raw(site_id: str, start: date, end: date) -> pd.DataFrame:
    """Raw in-orchard data (csv_wide). Times are local Pacific with DST; see DATA_SOURCES.md."""
    key = f"wildeye_{site_id}_{start}_{end}"

    def fetch() -> bytes:
        return cache.http_get_once(BASE + "wildeye", params={
            "siteID": site_id, "startDate": str(start), "endDate": str(end),
            "variables": "all", "format": "csv_wide"}, timeout=120)

    try:
        raw = cache.cached(SRC, key, fetch)
    except cache.RemoteError as e:
        if str(e).startswith("404"):
            cache.write(SRC, key, b"")
            raw = b""
        else:
            raise
    if not raw.strip():
        return pd.DataFrame()
    return pd.read_csv(io.BytesIO(raw))
