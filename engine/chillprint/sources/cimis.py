"""CIMIS Web API client (BUILD.md 3.2).

- Station list needs no key.
- Hourly data needs CIMIS_APP_KEY, sent in the Ocp-Apim-Subscription-Key header.
- One station and one month per request; 0.3 s between calls; every month is
  cached gzipped, so the cache doubles as the resume checkpoint.
- Hours run 0100..2400 PST (hour ending). 2400 maps to 00:00 of the next day.
"""
from __future__ import annotations

import calendar
import json
import time
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from ..config import cimis_key
from . import cache

SRC = "cimis"
STATION_URL = "https://et.water.ca.gov/api/station"
DATA_URL = "https://et.water.ca.gov/StationWeb/GetDataByStationNumber"
FT_TO_M = 0.3048

# We request English units (°F, Ly/day) because FNRIC computes its chill from the
# °F values; converting the same °F readings reproduces FNRIC exactly (tests/test_fnric_davis.py).
LY_PER_DAY_TO_WM2 = 0.4843

# CIMIS QC flags. Blank = good. Y (moderately out of historical range) and
# P (provisional) are kept; everything else is treated as missing.
QC_KEEP = {"", " ", "Y", "P"}

_last_call = {"t": 0.0}


def _num_after_slash(s: str) -> float:
    return float(str(s).split("/")[-1].strip())


def stations() -> pd.DataFrame:
    raw = cache.cached(SRC, "stations", lambda: cache.http_get(STATION_URL, timeout=120))
    st = pd.DataFrame(json.loads(raw)["Stations"])
    out = pd.DataFrame({
        "nbr": st["StationNbr"].astype(int),
        "name": st["Name"],
        "county": st["County"],
        "lat": st["HmsLatitude"].map(_num_after_slash),
        "lon": st["HmsLongitude"].map(_num_after_slash),
        "elev_m": pd.to_numeric(st["Elevation"], errors="coerce") * FT_TO_M,
        "active": st["IsActive"].astype(str).str.lower() == "true",
        "connect_date": pd.to_datetime(st["ConnectDate"], format="%m/%d/%Y").dt.date,
        "disconnect_date": pd.to_datetime(st["DisconnectDate"], format="%m/%d/%Y").dt.date,
    })
    out["id"] = "CIMIS-" + out["nbr"].astype(str)
    return out


def _throttle() -> None:
    dt = time.time() - _last_call["t"]
    if dt < 0.3:
        time.sleep(0.3 - dt)
    _last_call["t"] = time.time()


def month_key(nbr: int, year: int, month: int, items: str = "hlyE3") -> str:
    return f"{items}_{nbr}_{year:04d}-{month:02d}"


def fetch_month_raw(nbr: int, year: int, month: int, live: bool = False) -> bytes:
    """Raw JSON for one station-month of hourly data (cached).

    For the current, still-growing month pass live=True: the cache key then
    carries today's date so it is re-pulled once per day.
    """
    key = month_key(nbr, year, month)
    if live:
        key += f"_asof{date.today()}"
    if cache.has(SRC, key):
        return cache.read(SRC, key)
    k = cimis_key()
    if not k:
        raise RuntimeError("CIMIS_APP_KEY missing from .env")
    last = calendar.monthrange(year, month)[1]
    end = min(date(year, month, last), date.today() - timedelta(days=1))
    params = {
        "stationNbrs": str(nbr),
        "startDate": f"{year:04d}-{month:02d}-01",
        "endDate": end.isoformat(),
        "isHourly": "true",
        "unitOfMeasure": "E",
        "dataItems": "hly-air-tmp,hly-sol-rad,hly-rel-hum",
    }
    _throttle()
    try:
        raw = cache.http_get(DATA_URL, params=params, headers={"Ocp-Apim-Subscription-Key": k}, timeout=120)
    except cache.RemoteError as e:
        msg = str(e)
        # A station with no data for the month answers 4xx with a message; cache it as empty.
        if msg.startswith(("400", "404")):
            raw = b'{"Data":{"Providers":[{"Records":[]}]},"_note":' + json.dumps(msg[:200]).encode() + b"}"
        else:
            raise
    cache.write(SRC, key, raw)
    return raw


def _records(raw: bytes) -> list[dict]:
    if not raw or not raw.strip():
        return []
    js = json.loads(raw)
    data = js.get("Data") or js.get("data") or {}
    provs = data.get("Providers") or data.get("providers") or []
    recs: list[dict] = []
    for p in provs:
        recs.extend(p.get("Records") or p.get("records") or [])
    return recs


def _field(rec: dict, *names: str) -> tuple[float, str]:
    for n in names:
        v = rec.get(n)
        if isinstance(v, dict):
            val = v.get("Value", v.get("value"))
            qc = v.get("Qc", v.get("qc", "")) or ""
            try:
                return (float(val) if val not in (None, "") else np.nan), str(qc).strip()
            except (TypeError, ValueError):
                return np.nan, str(qc).strip()
    return np.nan, "M"


def parse_month(raw: bytes) -> pd.DataFrame:
    """Parse hourly records into a frame indexed by hour-ending PST timestamp."""
    rows = []
    for r in _records(raw):
        d = datetime.strptime(r["Date"][:10], "%Y-%m-%d")
        hr = int(str(r["Hour"]).strip())  # 100..2400
        h = hr // 100
        ts = d + timedelta(hours=h)        # 2400 -> 00:00 next day
        t, tq = _field(r, "HlyAirTmp", "hly-air-tmp")
        s, sq = _field(r, "HlySolRad", "hly-sol-rad")
        rh, rq = _field(r, "HlyRelHum", "hly-rel-hum")
        if str(r.get("Standard", "")).lower() == "english":
            t = (t - 32.0) * 5.0 / 9.0
            s = s * LY_PER_DAY_TO_WM2
        rows.append((ts, d.date(), h, t, tq, s, sq, rh, rq))
    df = pd.DataFrame(rows, columns=["ts", "cimis_date", "hour", "t_c", "t_qc", "srad", "srad_qc", "rh", "rh_qc"])
    if df.empty:
        return df
    df = df.sort_values("ts").drop_duplicates("ts")
    return df.reset_index(drop=True)


def apply_qc(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Treat values with non-accepted QC flags as missing. Returns (frame, counts)."""
    counts = {}
    for col, qc in (("t_c", "t_qc"), ("srad", "srad_qc"), ("rh", "rh_qc")):
        bad = ~df[qc].fillna("M").isin(QC_KEEP)
        counts[col] = int(bad.sum())
        df.loc[bad, col] = np.nan
    # physical sanity for air temperature
    phys = (df["t_c"] < -30) | (df["t_c"] > 55)
    counts["t_c_phys"] = int(phys.sum())
    df.loc[phys, "t_c"] = np.nan
    return df, counts
