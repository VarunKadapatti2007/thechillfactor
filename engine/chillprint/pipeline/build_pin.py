"""Build the hourly temperature history for any pin (BUILD.md 4.9, Phase 4 step 1).

For each winter 1980-81 .. 2024-25: Daymet daily min/max at the pin, rebuilt to
hours with Method B (nearest CIMIS stations' shape that day, aligned window),
falling back to Method L. 2025-26 lacks Daymet Jan-Mar 2026: filled with E4
(nearest station hourly + Daymet monthly pin-minus-station offset) when station
hourly exists, else gridMET + Method L; it is labeled as filled.
The live season uses E4 (or gridMET + Method L without station hourly).

Every season is stored on hour-ending PST stamps from Sept 1 01:00 to Apr 1 00:00.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

from .. import config as C
from ..science.hourly import Window, borrowed_shape, linvill_series, regular_hourly
from ..sources import daymet, elevation
from . import station_hourly as SH

PIN_DIR = C.PROCESSED_DIR / "pins"
PIN_DIR.mkdir(parents=True, exist_ok=True)
VERSION = 5
# Default history and live method, chosen by the hidden-station test (validation/REPORT.md):
# E4 = nearest station with a complete record that winter + Daymet monthly offset.
HISTORY_METHOD = "E4"
# Winters with no complete station record: "E2" (Daymet + Linvill curve) or "ML" (Daymet + ML
# hourly shape, Phase 6 step 2; 3.55 vs 4.20 CP on the same 832 hidden station-winters).
FALLBACK_METHOD = "ML"
N_STATIONS = 3


def season_stamps(y: int) -> pd.DatetimeIndex:
    return pd.date_range(f"{y}-09-01 01:00", f"{y + 1}-04-01 00:00", freq="h")


def season_days(y: int) -> pd.DatetimeIndex:
    return pd.date_range(f"{y}-09-01", f"{y + 1}-03-31", freq="D")


@dataclass
class Pin:
    lat: float
    lon: float
    elev_m: float | None
    nearest: list[dict]
    hourly: dict[int, np.ndarray]
    method: dict[int, str]
    filled: dict[int, bool]
    station_share: dict[int, float]
    daily: pd.DataFrame = field(repr=False)
    window: str = "00h_lag0"
    live_until: str | None = None  # last observed date of the live season
    sources: list[str] = field(default_factory=list)
    memo: dict = field(default_factory=dict, repr=False, compare=False)

    @property
    def key(self) -> str:
        return pin_key(self.lat, self.lon)

    def complete_seasons(self) -> list[int]:
        """Winters usable as analogs: complete records (E4), not fallback estimates or the live season."""
        return [y for y in sorted(self.hourly) if not self.filled.get(y) and y <= C.LAST_COMPLETE_DAYMET_SEASON + 1]

    def history_seasons(self) -> list[int]:
        return [y for y in sorted(self.hourly) if y <= C.LAST_COMPLETE_DAYMET_SEASON + 1]


def pin_key(lat: float, lon: float) -> str:
    return f"{lat:.4f}_{lon:.4f}"


def _daymet_station(sid: str, lat: float, lon: float) -> pd.DataFrame:
    p = C.PROCESSED_DIR / "daymet" / f"{sid}.parquet"
    if p.exists():
        return pd.read_parquet(p)
    df, _ = daymet.daily(lat, lon)
    return df


def monthly_offset(pin_daily: pd.DataFrame, st_daily: pd.DataFrame, years=(2010, 2025)) -> pd.DataFrame:
    """Daymet pin minus Daymet station, per calendar month, for tmin and tmax."""
    a = pin_daily.loc[f"{years[0]}-01-01":f"{years[1]}-12-31", ["tmin", "tmax"]]
    b = st_daily.loc[f"{years[0]}-01-01":f"{years[1]}-12-31", ["tmin", "tmax"]]
    d = (a - b).dropna()
    return d.groupby(d.index.month).mean()


def offset_hourly(st_hourly: pd.Series, off: pd.DataFrame) -> pd.Series:
    """E4: station hourly plus a shape-aware monthly offset (tmin offset at the daily low, tmax at the high)."""
    s = st_hourly.copy()
    day = (s.index - pd.Timedelta(hours=1)).normalize()
    g = s.groupby(day)
    lo = g.transform("min")
    hi = g.transform("max")
    p = ((s - lo) / (hi - lo).where((hi - lo) > 0.1)).clip(0, 1).fillna(0.5)
    m = s.index.month
    dmin = off["tmin"].reindex(m).to_numpy()
    dmax = off["tmax"].reindex(m).to_numpy()
    return s + dmin + p.to_numpy() * (dmax - dmin)


def _rebuild_season(lat, lon, y, pin_daily, win: Window, exclude=(), daily_override=None):
    """Method B (else L) hourly for season y. Returns (array on season stamps, share of days from stations)."""
    pad0 = pd.Timestamp(y, 8, 29)
    pad1 = pd.Timestamp(y + 1, 4, 3)
    d = (daily_override if daily_override is not None else pin_daily).loc[pad0:pad1, ["tmin", "tmax"]]
    if d["tmin"].isna().all():
        return None, 0.0
    d = d.interpolate(limit_direction="both")
    near = SH.nearest_cimis(lat, lon, exclude=exclude, with_hourly=True, season=y, k=N_STATIONS)
    st = [SH.station_hourly(s) for s in near.id]
    if st:
        series, src = borrowed_shape(d, st, lat, win)
        share = float((src.loc[f"{y}-09-01":f"{y + 1}-03-31"] >= 0).mean())
    else:
        series = linvill_series(lat, d.shift(-win.lag_days) if win.lag_days else d)
        share = 0.0
    arr = series.reindex(season_stamps(y)).interpolate(limit_direction="both").to_numpy().copy()
    return arr, share


def rebuild_record(lat, lon, pin_daily, win: Window, exclude=(), k: int = 5):
    """Method B (else L) hourly for the whole Daymet record in one vectorized pass.

    Each day uses the nearest of the k closest stations that has a usable day,
    so seasons before a station's record fall to the next station, then Method L.
    Returns (hourly series on PST stamps, per-day source index: -1 = Method L).
    """
    d = pin_daily[["tmin", "tmax"]].interpolate(limit_direction="both")
    near = SH.nearest_cimis(lat, lon, exclude=exclude, with_hourly=True, k=k)
    st = [SH.station_hourly(s) for s in near.id]
    if st:
        return borrowed_shape(d, st, lat, win)
    lin = linvill_series(lat, d.shift(-win.lag_days) if win.lag_days else d)
    return lin, pd.Series(-1, index=d.index)


def _fallback_record(lat: float, pin_daily: pd.DataFrame) -> tuple[pd.Series, str]:
    """Hours for winters without a complete station record."""
    from ..science import ml_shape
    if FALLBACK_METHOD == "ML" and ml_shape.available():
        return ml_shape.ml_hours(lat, pin_daily, SH.window_for("daymet")), "Daymet + ML shape"
    return linvill_series(lat, pin_daily[["tmin", "tmax"]].interpolate(limit_direction="both")), "E2"


@lru_cache(maxsize=4096)
def station_season_parts(sid: str, y: int):
    """A station-season split for fast E4: hours (days x 24), position of each hour between the
    day's low and high (0.5 on flat days), and each hour's calendar month."""
    stamps = season_stamps(y)
    seg = SH.station_hourly(sid).reindex(stamps).interpolate(limit=6, limit_area="inside")
    a = seg.to_numpy(dtype=np.float64).reshape(-1, 24)
    with np.errstate(all="ignore"), __import__("warnings").catch_warnings():
        __import__("warnings").simplefilter("ignore", RuntimeWarning)
        lo = np.nanmin(a, axis=1, keepdims=True)
        hi = np.nanmax(a, axis=1, keepdims=True)
    rng = hi - lo
    pos = np.where(rng > 0.1, (a - lo) / np.where(rng > 0.1, rng, 1.0), 0.5)
    pos = np.nan_to_num(np.clip(pos, 0, 1), nan=0.5)
    months = stamps.month.to_numpy().reshape(-1, 24)
    return a, pos, months


def e4_hours_fast(sid: str, y: int, off: pd.DataFrame) -> np.ndarray:
    """E4 hours for a season: station hours + shape-aware monthly offset (same math as offset_hourly)."""
    a, pos, months = station_season_parts(sid, y)
    dmin = off["tmin"].reindex(range(1, 13)).fillna(0).to_numpy()[months - 1]
    dmax = off["tmax"].reindex(range(1, 13)).fillna(0).to_numpy()[months - 1]
    out = (a + dmin + pos * (dmax - dmin)).ravel()
    if np.isnan(out).any():
        out = pd.Series(out).interpolate(limit_direction="both").to_numpy()
    return out


def season_e4(lat, lon, pin_daily, y: int, offsets: dict) -> tuple[np.ndarray, str, float] | None:
    """E4 for one complete winter: nearest station with >= 95% of hours that winter, plus the
    Daymet monthly pin-minus-station offset. Returns (hours, label, distance km) or None."""
    comp = SH.complete_seasons()
    near = SH.nearest_cimis(lat, lon, with_hourly=True, k=40)
    for s in near.itertuples():
        if y not in comp.get(s.id, ()):
            continue
        if s.id not in offsets:
            offsets[s.id] = monthly_offset(pin_daily, _daymet_station(s.id, s.lat, s.lon))
        arr = e4_hours_fast(s.id, y, offsets[s.id])
        return arr, f"E4 from {s.name} ({s.dist_km:.0f} km)", float(s.dist_km)
    return None


def _fill_2025(lat, lon, pin_daily, win, arr2025, live_tag: str | None):
    """Jan 1 - Mar 31 2026 for the 2025-26 winter (Daymet ends 2025-12-31)."""
    stamps = season_stamps(2025)
    jan1 = pd.Timestamp("2026-01-01 01:00")
    need = stamps >= jan1
    near = SH.nearest_cimis(lat, lon, with_hourly=True, season=2025, k=3)
    for s in near.itertuples():
        sh = SH.station_hourly(s.id)
        seg = sh.reindex(stamps[need])
        if seg.notna().mean() < 0.9:
            continue
        off = monthly_offset(pin_daily, _daymet_station(s.id, s.lat, s.lon))
        e4 = offset_hourly(regular_hourly(sh.loc["2025-12-25":"2026-04-02"]).interpolate(limit=6), off)
        arr2025[need] = e4.reindex(stamps[need]).interpolate(limit_direction="both").to_numpy()
        return arr2025, f"E4 fill from {s.name}"
    # Keyless fallback: gridMET daily, matched to Daymet by the mean Sept-Dec 2025 difference, Method L hours.
    try:
        gm = daymet.gridmet_daily(lat, lon, date(2025, 9, 1), date(2026, 4, 2))
    except Exception:
        return None, "Not available"
    ov = (pin_daily.loc["2025-09-01":"2025-12-31", ["tmin", "tmax"]] - gm.loc["2025-09-01":"2025-12-31", ["tmin", "tmax"]]).dropna()
    g = gm.loc["2025-12-28":"2026-04-02", ["tmin", "tmax"]].copy()
    g["tmin"] += float(ov["tmin"].mean())
    g["tmax"] += float(ov["tmax"].mean())
    lin = linvill_series(lat, g).reindex(stamps[need]).interpolate(limit_direction="both")
    arr2025[need] = lin.to_numpy()
    return arr2025, "gridMET fill"


def _live_season(lat, lon, pin_daily, today: date):
    """Current season Sept 1 -> yesterday. Returns (array on season stamps with NaN after, method, last date)."""
    y = C.season_of(today)
    stamps = season_stamps(y)
    last = today - timedelta(days=1)
    end_stamp = pd.Timestamp(last) + pd.Timedelta(days=1)
    arr = np.full(len(stamps), np.nan)
    obs = stamps <= end_stamp
    near = SH.nearest_cimis(lat, lon, with_hourly=True, season=y, k=3)
    for s in near.itertuples():
        sh = SH.station_hourly(s.id).reindex(stamps[obs])
        if sh.notna().mean() < 0.9:
            continue
        off = monthly_offset(pin_daily, _daymet_station(s.id, s.lat, s.lon))
        e4 = offset_hourly(sh.interpolate(limit=6, limit_direction="both"), off)
        arr[obs] = e4.interpolate(limit_direction="both").to_numpy()
        return arr, f"E4 from {s.name}", str(last)
    # Keyless fallback: gridMET daily (lags ~1-2 days) + Method L.
    try:
        gm = daymet.gridmet_daily(lat, lon, date(y, 8, 28), last, tag=f"_asof{today}")
    except Exception:
        return arr, "Not available", None
    gm = gm.dropna()
    if gm.empty:
        return arr, "Not available", None
    lin = linvill_series(lat, gm[["tmin", "tmax"]])
    have = lin.dropna()
    last_obs = have.index.max().normalize() - pd.Timedelta(days=1)
    upto = stamps <= last_obs + pd.Timedelta(days=1)
    arr[upto] = lin.reindex(stamps[upto]).interpolate(limit_direction="both").to_numpy()
    return arr, "gridMET + Method L", str(last_obs.date())


def _version_tag() -> str:
    idx = SH.hourly_index()
    n = sum(len(v) for v in idx.values())
    comp = sum(len(v) for v in SH.complete_seasons().values())
    return f"v{VERSION}_h{n}_c{comp}_{FALLBACK_METHOD}_{SH.window_for('daymet').label()}"


@lru_cache(maxsize=32)
def build_pin(lat: float, lon: float, today: date | None = None) -> Pin:
    lat, lon = round(lat, 4), round(lon, 4)
    today = today or date.today()
    key = pin_key(lat, lon)
    meta_p, arr_p = PIN_DIR / f"{key}.json", PIN_DIR / f"{key}.npz"
    tag = _version_tag()
    if meta_p.exists() and arr_p.exists():
        meta = json.loads(meta_p.read_text())
        if meta.get("tag") == tag and meta.get("built_for") == str(today):
            return _load(meta, arr_p, lat, lon)

    t0 = time.time()
    pin_daily, m = daymet.daily(lat, lon)
    elev = m.get("elev_m")
    if elev is None:
        elev = elevation.elevation_m(lat, lon)
    win = SH.window_for("daymet")
    near = SH.nearest_cimis(lat, lon, k=3)
    hourly, method, filled, share = {}, {}, {}, {}
    offsets: dict = {}
    rec = None
    y25 = C.LAST_COMPLETE_DAYMET_SEASON + 1
    for y in range(C.FIRST_SEASON, y25 + 1):
        e4 = season_e4(lat, lon, pin_daily, y, offsets)
        if e4 is not None:
            hourly[y], method[y], filled[y], share[y] = e4[0], e4[1], False, 1.0
            continue
        # No station has a complete record that winter (e.g. before CIMIS began in 1982):
        # fall back to Daymet + Method L (E2) and mark the winter as estimated. Daymet ends
        # Dec 2025, so 2025-26 is only available through E4.
        if y >= y25:
            continue
        if rec is None:
            rec, fb_label = _fallback_record(lat, pin_daily)
        arr = rec.reindex(season_stamps(y)).interpolate(limit_direction="both").to_numpy().copy()
        if not np.isnan(arr).all():
            hourly[y], method[y], filled[y], share[y] = arr, f"{fb_label} (no station record that winter)", True, 0.0
    live_until = None
    cur = C.season_of(today)
    if cur > y25:
        arr, mth, live_until = _live_season(lat, lon, pin_daily, today)
        hourly[cur], method[cur], filled[cur], share[cur] = arr, mth, False, 1.0 if mth.startswith("E4") else 0.0
    srcs = [C.SOURCES["daymet"], C.SOURCES["cimis"], C.SOURCES["fnric"]]
    if any("gridMET" in v for v in method.values()):
        srcs.append(C.SOURCES["gridmet"])
    pin = Pin(lat, lon, elev,
              [{"id": r.id, "name": r.name, "dist_km": float(r.dist_km), "elev_m": None if pd.isna(r.elev_m) else float(r.elev_m)}
               for r in near.itertuples()],
              hourly, method, filled, share, pin_daily, win.label(), live_until, srcs)
    _save(pin, tag, today)
    pin_build_seconds = time.time() - t0
    meta = json.loads(meta_p.read_text())
    meta["build_seconds"] = round(pin_build_seconds, 2)
    meta_p.write_text(json.dumps(meta))
    return pin


def _save(pin: Pin, tag: str, today: date) -> None:
    key = pin.key
    np.savez_compressed(PIN_DIR / f"{key}.npz", **{f"s{y}": a.astype(np.float32) for y, a in pin.hourly.items()})
    meta = {"tag": tag, "built_for": str(today), "lat": pin.lat, "lon": pin.lon, "elev_m": pin.elev_m,
            "nearest": pin.nearest, "method": {str(k): v for k, v in pin.method.items()},
            "filled": {str(k): v for k, v in pin.filled.items()},
            "station_share": {str(k): v for k, v in pin.station_share.items()},
            "window": pin.window, "live_until": pin.live_until, "sources": pin.sources}
    (PIN_DIR / f"{key}.json").write_text(json.dumps(meta))


def _load(meta: dict, arr_p, lat: float, lon: float) -> Pin:
    z = np.load(arr_p)
    hourly = {int(k[1:]): z[k].astype(np.float64) for k in z.files}
    pin_daily, _ = daymet.daily(lat, lon)
    return Pin(lat, lon, meta["elev_m"], meta["nearest"], hourly,
               {int(k): v for k, v in meta["method"].items()}, {int(k): v for k, v in meta["filled"].items()},
               {int(k): v for k, v in meta["station_share"].items()}, pin_daily, meta["window"],
               meta.get("live_until"), meta.get("sources", []))


if __name__ == "__main__":
    import sys
    t = time.time()
    p = build_pin(float(sys.argv[1]), float(sys.argv[2]))
    print(f"built {p.key} in {time.time() - t:.1f}s; seasons {min(p.hourly)}..{max(p.hourly)}; "
          f"methods {sorted(set(p.method.values()))}; live until {p.live_until}")
