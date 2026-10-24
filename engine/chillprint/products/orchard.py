"""Chill at the orchard from the grower's own readings (POST /api/orchard).

A min/max thermometer (one low and one high per day) or a data logger (readings every few minutes
to every hour) in the orchard. Daily readings become hours with the nearest CIMIS stations' shape
(Method B, the E5 path); logger readings are averaged to hour-ending PST hours. Days before the
readings start, and gaps the readings cannot cover, use the station estimate (E4), and the Dynamic
Model runs once over the merged winter so its state carries across. Accuracy for each start date
comes from validation/orchard_readings.py (hidden stations and Wildeye in-orchard sensors).
"""
from __future__ import annotations

import copy
import json
from datetime import date, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

from .. import config as C
from ..pipeline import station_hourly as SH
from ..pipeline.build_pin import Pin, season_stamps
from ..pipeline.pins import get_pin, is_global
from ..science.hourly import MIDNIGHT, borrowed_shape
from .core import dos, season_daily_cum, start_dos
from .errorbar import _growth
from .point import BadRequest, check_inputs, point_for_pin

MAX_GAP_DAYS = 4    # data-diet rule: gaps up to 4 days, filled by interpolation, keep the typical error under 2 CP
MAX_GAP_HOURS = 6   # logger gaps up to 6 hours are interpolated (same limit as the station store)
MAX_ROWS = 80_000   # a winter of 5-minute readings
SUMMARY = C.VALIDATION_DIR / "orchard_readings.json"
STARTS = (("sep1", "09-01"), ("nov1", "11-01"), ("dec1", "12-01"), ("jan1", "01-01"))


def _to_c(x: np.ndarray, unit: str) -> np.ndarray:
    return (x - 32.0) * 5.0 / 9.0 if unit == "F" else x


def parse_daily(dates: list[str], lows: list[float], highs: list[float], unit: str) -> pd.DataFrame:
    if not (len(dates) == len(lows) == len(highs)) or not dates:
        raise BadRequest("daily readings need the same number of dates, lows and highs")
    if len(dates) > MAX_ROWS:
        raise BadRequest("too many readings")
    try:
        idx = pd.to_datetime(pd.Series(dates), errors="raise").dt.normalize()
    except Exception:
        raise BadRequest("dates must look like 2026-11-05")
    df = pd.DataFrame({"tmin": _to_c(np.asarray(lows, dtype=float), unit),
                       "tmax": _to_c(np.asarray(highs, dtype=float), unit)}, index=pd.DatetimeIndex(idx))
    df = df[~df.index.duplicated(keep="last")].sort_index()
    bad = ~((df.tmin > -30) & (df.tmax < 50) & (df.tmin <= df.tmax + 0.05))
    if bad.mean() > 0.2:
        raise BadRequest("many readings look wrong (low above high, or out of range); check the columns and units")
    return df[~bad]


def parse_hourly(times: list[str], temps: list[float], unit: str) -> pd.Series:
    if len(times) != len(temps) or not times:
        raise BadRequest("logger readings need the same number of times and temperatures")
    if len(times) > MAX_ROWS:
        raise BadRequest("too many readings; export hourly or 10-minute data")
    try:
        ts = pd.DatetimeIndex(pd.to_datetime(pd.Series(times), errors="raise"))
    except Exception:
        raise BadRequest("times must look like 2026-11-05 13:00")
    if ts.tz is not None:
        ts = ts.tz_convert("Etc/GMT+8").tz_localize(None)
    else:
        # Logger clocks run on California local time; CIMIS hours are PST all year.
        loc = ts.tz_localize("America/Los_Angeles", ambiguous="NaT", nonexistent="NaT")
        ts = loc.tz_convert("Etc/GMT+8").tz_localize(None)
    s = pd.Series(_to_c(np.asarray(temps, dtype=float), unit), index=ts)
    s = s[s.index.notna() & (s > -30) & (s < 50)]
    if s.empty:
        raise BadRequest("no usable logger readings")
    # Hour-ending means, like CIMIS: readings in (12:00, 13:00] are the 13:00 hour.
    return s.resample("h", label="right", closed="right").mean()


@lru_cache(maxsize=1)
def _summary() -> dict | None:
    return json.loads(SUMMARY.read_text()) if SUMMARY.exists() else None


def readings_error(first: date, season: int, asof: date) -> tuple[float | None, str]:
    """80th-percentile CP error for readings that start on `first`, from the in-orchard test (Wildeye)
    when it has enough winters, else hidden stations; scaled through the season like the main error bar."""
    s = _summary()
    if not s:
        return None, "not validated"
    tests = s["tests"]
    test = "wildeye_orchard" if tests.get("wildeye_orchard", {}).get("n_station_winters", 0) >= 20 else "hidden_station"
    sc = "station_only"
    for key, mmdd in STARTS:
        if first <= C.by_date(season, mmdd):
            sc = f"readings_from_{key}"
            break
    v = tests[test]["scenarios"].get(sc, {}).get("p80_cp")
    if v is None:
        return None, "not validated"
    em = json.loads((C.VALIDATION_DIR / "error_model.json").read_text())
    g = _growth(em["history"], dos(season, asof))
    label = {"wildeye_orchard": "in-orchard sensors", "hidden_station": "hidden CIMIS stations"}[test]
    when = {"readings_from_sep1": "Sep 1", "readings_from_nov1": "Nov 1", "readings_from_dec1": "Dec 1",
            "readings_from_jan1": "Jan 1"}.get(sc)
    what = f"test of readings starting {when}" if when else "station-only test"
    return round(float(v) * g, 1), f"{what} at {tests[test]['n_sites']} {label}"


def _daily_hours(pin: Pin, df: pd.DataFrame, season: int) -> tuple[pd.Series, int, int]:
    """Hours from daily low/high; short gaps interpolated, long gaps left NaN (station estimate fills)."""
    days = pd.date_range(df.index.min(), df.index.max(), freq="D")
    d = df.reindex(days)
    miss = d.tmin.isna() | d.tmax.isna()
    run = miss.groupby((~miss).cumsum()).transform("sum").where(miss, 0)
    short = miss & (run <= MAX_GAP_DAYS)
    d = d.interpolate(limit_area="inside")
    d[miss & ~short] = np.nan
    near = SH.nearest_cimis(pin.lat, pin.lon, with_hourly=True, season=season, k=3)
    shapes = [SH.station_hourly(i) for i in near.id]
    full = d.interpolate(limit_direction="both")  # borrowed_shape needs every day; long gaps are masked below
    hrs, _ = borrowed_shape(full, shapes, pin.lat, MIDNIGHT)
    long_days = days[(miss & ~short).to_numpy()]
    for dd in long_days:
        hrs.loc[dd + pd.Timedelta(hours=1):dd + pd.Timedelta(hours=24)] = np.nan
    return hrs, int(short.sum()), int((miss & ~short).sum())


def _logger_hours(s: pd.Series) -> tuple[pd.Series, int, int]:
    filled = s.interpolate(limit=MAX_GAP_HOURS, limit_area="inside")
    short = int((s.isna() & filled.notna()).sum())
    return filled, short, int(filled.isna().sum())


def orchard_point(lat: float, lon: float, crop: str, variety: str, kind: str, unit: str,
                  dates: list[str] | None = None, lows: list[float] | None = None, highs: list[float] | None = None,
                  times: list[str] | None = None, temps: list[float] | None = None,
                  start: str = "sep1", by: str | None = None, climate: str = "today", today: date | None = None) -> dict:
    v = check_inputs(crop, variety, start, climate)
    if unit not in ("F", "C"):
        raise BadRequest("unit must be F or C")
    today = today or date.today()
    pin = get_pin(lat, lon, today)
    if is_global(pin):
        raise BadRequest("orchard readings work for California orchards (they borrow the daily shape from CIMIS stations)")

    if kind == "daily":
        df = parse_daily(dates or [], lows or [], highs or [], unit)
        last_day = df.index.max().date()
    elif kind == "hourly":
        hs = parse_hourly(times or [], temps or [], unit)
        last_day = (hs.dropna().index.max() - pd.Timedelta(hours=1)).date()
    else:
        raise BadRequest("kind must be daily or hourly")
    last_day = min(last_day, today - timedelta(days=1))
    season = C.season_of(last_day)
    if season not in pin.hourly:
        raise BadRequest(f"no station record for the {C.season_label(season)} winter to compare with")
    s0, s1 = pd.Timestamp(season, 9, 1), pd.Timestamp(last_day)
    if kind == "daily":
        df = df.loc[s0:s1]
        if len(df) < 3:
            raise BadRequest("need at least 3 days of readings within one winter (Sep 1 onward)")
        hrs, short, long_ = _daily_hours(pin, df, season)
        first_day = df.index.min().date()
    else:
        hs = hs.loc[s0 + pd.Timedelta(hours=1):s1 + pd.Timedelta(hours=24)]
        if hs.notna().sum() < 72:
            raise BadRequest("need at least 3 days of logger readings within one winter (Sep 1 onward)")
        hrs, short, long_ = _logger_hours(hs)
        first_day = (hs.dropna().index.min() - pd.Timedelta(hours=1)).date()

    # Merge: station estimate everywhere, the orchard's hours wherever they exist, nothing after the last reading.
    stamps = season_stamps(season)
    est = pd.Series(pin.hourly[season], index=stamps)
    own = hrs.reindex(stamps)
    merged = est.where(own.isna(), own)
    k_last = dos(season, last_day)
    arr = merged.to_numpy(dtype=np.float64).copy()
    arr[(k_last + 1) * 24:] = np.nan
    readings_hours = int(own.iloc[: (k_last + 1) * 24].notna().sum())

    opin = copy.copy(pin)
    opin.hourly = dict(pin.hourly)
    opin.hourly[season] = arr
    opin.memo = {}
    opin.live_until = last_day.isoformat() if season == C.season_of(today) else pin.live_until
    recent = last_day >= today - timedelta(days=2)
    out = point_for_pin(opin, v, last_day, start, by, climate, today, use_forecast=recent)

    station_cum = season_daily_cum(pin, season, start)
    k = dos(season, last_day)
    st_cp = float(station_cum[k]) if k < len(station_cum) and np.isfinite(station_cum[k]) else None
    err, err_src = readings_error(first_day, season, last_day)
    if out["chill"]["error_cp"] is not None and err is not None:
        out["chill"]["error_cp"] = err
    out["method"] = (f"Your orchard's {'daily lows and highs' if kind == 'daily' else 'logger readings'} "
                     f"from {first_day:%b} {first_day.day}")
    out["sources"] = ["Your orchard readings (uploaded)"] + out["sources"]
    n_days = (last_day - first_day).days + 1
    out["orchard"] = {
        "kind": kind,
        "first": first_day.isoformat(),
        "last": last_day.isoformat(),
        "days": n_days,
        "readings_hours": readings_hours,
        "gap_filled": short,
        "gap_estimated": long_,
        "gap_unit": "days" if kind == "daily" else "hours",
        "before_start_from_station": first_day > date(season, 9, 1) + timedelta(days=start_dos(start)),
        "station_estimate_cp": None if st_cp is None else round(st_cp, 2),
        "difference_cp": None if st_cp is None else round(float(out["chill"]["to_date"]) - st_cp, 2),
        "error_source": err_src,
    }
    return out
