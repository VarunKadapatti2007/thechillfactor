"""Grower readings test: how close does chill get when a grower adds their own daily low and high?

A min/max thermometer in the orchard gives one low and one high per calendar day. The app turns
those into hours with the nearest stations' shape (Method B, as E5) and uses the station estimate
(E4) for the days before the readings start. This test does exactly that on real data:

- Hidden CIMIS stations: the station's own daily low/high stands in for the thermometer.
- Wildeye in-orchard sensors (pistachio orchards): the orchard sensor's daily low/high, the case
  that matters to growers, with truth from the same sensor's hours.

Readings start Sep 1, Nov 1, Dec 1 or Jan 1. Errors are CP at Feb 1 and Mar 1 against hourly truth.

    engine/.venv/Scripts/python -m chillprint.validation.orchard_readings
"""
from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from .. import config as C
from ..pipeline import station_hourly as SH
from ..pipeline.build_pin import _daymet_station
from ..science.hourly import MIDNIGHT
from ..sources import daymet
from . import common as V

STARTS = {"sep1": "09-01", "nov1": "11-01", "dec1": "12-01", "jan1": "01-01"}
SEASONS = range(C.VALIDATION_FIRST_SEASON, C.LAST_COMPLETE_DAYMET_SEASON + 2)
OUT_TABLE = V.OUT / "orchard_readings.parquet"
OUT_SUMMARY = V.OUT / "orchard_readings.json"


def merged_cum(e4: np.ndarray, e5: np.ndarray, season: int, start: str) -> np.ndarray:
    """Station estimate before the readings start, readings-based hours after; one Dynamic Model run."""
    k0 = V.dos(season, STARTS[start]) if start != "sep1" else 0
    h = e4.copy()
    h[k0 * 24:] = e5[k0 * 24:]
    return V.daily_cum(h)


def _rows(base: dict, truth_h: np.ndarray, own: pd.Series, lat: float, season: int,
          nb: pd.DataFrame, dm: pd.DataFrame | None) -> list[dict]:
    shapes = [SH.station_hourly(i) for i in nb.id.head(3)]
    own_d = V.own_window_daily(own, season, MIDNIGHT)
    e5 = V.b_hours(lat, own_d, season, shapes, MIDNIGHT)
    dm_nb = _daymet_station(nb.iloc[0].id, float(nb.iloc[0].lat), float(nb.iloc[0].lon))
    if dm is None or dm_nb is None:
        return []
    e4 = V.e4_hours(SH.station_hourly(nb.iloc[0].id), dm, dm_nb, season)
    tm = V.metrics(V.daily_cum(truth_h), season)
    out = []
    e4m = V.metrics(V.daily_cum(e4), season)
    out.append({**base, "scenario": "station_only", **{f"err_{k}": e4m[f"cp_{k}"] - tm[f"cp_{k}"] for k in ("feb1", "mar1")},
                "truth_mar1": tm["cp_mar1"]})
    for s in STARTS:
        m = V.metrics(merged_cum(e4, e5, season, s), season)
        out.append({**base, "scenario": f"readings_from_{s}",
                    **{f"err_{k}": m[f"cp_{k}"] - tm[f"cp_{k}"] for k in ("feb1", "mar1")}, "truth_mar1": tm["cp_mar1"]})
    return out


def run_station(sid: str) -> list[dict]:
    st = SH.stations().set_index("id")
    s = st.loc[sid]
    complete = V.complete_set()
    own = SH.station_hourly(sid)
    dm = V.daymet_pixel(sid)
    rows = []
    for y in SEASONS:
        if (sid, y) not in complete or y > C.LAST_COMPLETE_DAYMET_SEASON:
            continue
        nb = V.neighbors(s.lat, s.lon, y, (sid,), complete, k=3)
        if nb.empty:
            continue
        base = {"test": "hidden_station", "station_id": sid, "season": y, "dist_km": float(nb.iloc[0].dist_km)}
        rows += _rows(base, V.season_hourly(own, y), own, s.lat, y, nb, dm)
    return rows


def run_wildeye() -> list[dict]:
    st = SH.stations()
    we = st[(st.network == "Wildeye") & st.active]
    complete = V.complete_set()
    rows = []
    for s in we.itertuples():
        h = SH.wildeye_hourly(s.id)
        if h.empty:
            continue
        try:
            dm, _ = daymet.daily(round(s.lat, 4), round(s.lon, 4))
        except Exception:
            continue
        for y in SEASONS:
            if V.coverage(h, y) < V.MIN_COVERAGE or y > C.LAST_COMPLETE_DAYMET_SEASON:
                continue
            nb = V.neighbors(s.lat, s.lon, y, (), complete, k=3)
            if nb.empty:
                continue
            base = {"test": "wildeye_orchard", "station_id": s.id, "season": y, "dist_km": float(nb.iloc[0].dist_km)}
            rows += _rows(base, V.season_hourly(h, y), h, s.lat, y, nb, dm)
    return rows


def summarize(df: pd.DataFrame) -> dict:
    out = {"note": "Mean absolute CP error (and 80th percentile) when the grower supplies daily low/high readings "
                   "from the given start date; before that, the station estimate (E4). Truth is hourly data at the "
                   "same site.", "tests": {}}
    for test, g in df.groupby("test"):
        t = {"n_station_winters": int(g[g.scenario == "station_only"].shape[0]),
             "n_sites": int(g.station_id.nunique()), "scenarios": {}}
        for sc, gs in g.groupby("scenario"):
            e = pd.concat([gs.err_feb1, gs.err_mar1]).dropna()
            t["scenarios"][sc] = {"mae_cp": round(float(e.abs().mean()), 2), "p80_cp": round(float(e.abs().quantile(0.8)), 2),
                                  "bias_cp": round(float(e.mean()), 2),
                                  "mae_mar1": round(float(gs.err_mar1.abs().mean()), 2),
                                  "mape_mar1": round(float((gs.err_mar1.abs() / gs.truth_mar1.where(gs.truth_mar1 > 5)).mean() * 100), 1)}
        out["tests"][test] = t
    return out


def run() -> dict:
    hidden_ids = sorted(pd.read_parquet(V.OUT / "validation_by_station.parquet").station_id.unique())
    rows = []
    with ProcessPoolExecutor(max_workers=6) as ex:
        for r in ex.map(run_station, hidden_ids):
            rows += r
    rows += run_wildeye()
    df = pd.DataFrame(rows)
    df.to_parquet(OUT_TABLE, index=False)
    summ = summarize(df)
    OUT_SUMMARY.write_text(json.dumps(summ, indent=1))
    return summ


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
