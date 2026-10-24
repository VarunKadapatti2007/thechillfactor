"""Outlook backtest (BUILD.md 5.6).

For every station-season and as-of Dec 1, Jan 1, Feb 1: the predicted chance of
reaching each variety's low need by its by date, with analogs that exclude the
tested winter, against what happened. Brier score vs a climatology baseline
(the plain share of past winters that met the need), plus a reliability table.
Run with and without the today's-climate shift.

The observed part comes from the station's own hourly (truth); analogs are the
pin history rebuilt at the station's location, as in the product.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
from tqdm import tqdm

from .. import config as C
from ..pipeline import station_hourly as SH
from ..pipeline.build_pin import build_pin
from ..products.history import cp_by
from ..products.outlook import outlook
from . import common as V

ASOF = ((12, 1), (1, 1), (2, 1))


def _station(args) -> list[dict]:
    sid, seasons, src = args
    st = SH.stations().set_index("id").loc[sid]
    pin0 = build_pin(round(float(st.lat), 4), round(float(st.lon), 4))
    h = SH.station_hourly(sid) if src == "cimis" else SH.wildeye_hourly(sid)
    rows = []
    bys = sorted({v.by_date_default for _, v in C.all_varieties()})
    for y in seasons:
        if y not in pin0.hourly or y > C.LAST_COMPLETE_DAYMET_SEASON:
            continue
        truth_h = V.season_hourly(h, y)
        hourly = dict(pin0.hourly)
        hourly[y] = truth_h
        pin = replace(pin0, hourly=hourly, memo={})
        analogs = [a for a in pin.complete_seasons() if a != y]
        truth_cum = V.daily_cum(truth_h)
        for by_mmdd in bys:
            by = C.by_date(y, by_mmdd)
            k_by = (by - date(y, 9, 1)).days
            outcome_cp = float(truth_cum[k_by])
            clim_vals = np.array([cp_by(pin, a, by_mmdd) for a in analogs])
            for (m, d) in ASOF:
                asof = date(y if m >= 9 else y + 1, m, d)
                if asof >= by:
                    continue
                for climate in ("today", "recorded"):
                    ol = outlook(pin, y, asof, by, "sep1", climate, analogs=analogs)
                    for _, v in C.all_varieties():
                        if v.by_date_default != by_mmdd:
                            continue
                        rows.append({"station_id": sid, "season": y, "asof": asof.isoformat(), "by": by_mmdd,
                                     "variety": v.id, "climate": climate, "p": ol.chance(v.need_low),
                                     "p_clim": float(np.mean(clim_vals >= v.need_low)),
                                     "outcome": float(outcome_cp >= v.need_low)})
    return rows


def run(max_stations: int = 60, workers: int = 6) -> pd.DataFrame:
    if SH.hourly_index():
        cs = sorted(V.complete_set())
        src = "cimis"
    else:
        cs = []
        for s in SH.stations()[SH.stations().network == "Wildeye"].id:
            h = SH.wildeye_hourly(s)
            cs += [(s, y) for y in (2023, 2024) if not h.empty and V.coverage(h, y) >= V.MIN_COVERAGE]
        src = "wildeye"
    by_st: dict[str, list[int]] = {}
    for s, y in cs:
        by_st.setdefault(s, []).append(y)
    sids = sorted(by_st)[:max_stations]
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for r in tqdm(ex.map(_station, [(s, by_st[s], src) for s in sids]), total=len(sids), desc="backtest"):
            rows.extend(r)
    df = pd.DataFrame(rows)
    df["source"] = src
    df.to_parquet(V.OUT / "backtest.parquet", index=False)
    return df


def summarize(df: pd.DataFrame) -> dict:
    out = {}
    for climate in ("today", "recorded"):
        sub = df[df.climate == climate]
        out[climate] = {"brier": float(np.mean((sub.p - sub.outcome) ** 2)),
                        "brier_climatology": float(np.mean((sub.p_clim - sub.outcome) ** 2)), "n": int(len(sub))}
    best = min(out, key=lambda k: out[k]["brier"])
    sub = df[df.climate == best]
    bins = np.linspace(0, 1, 11)
    rel = []
    for i in range(10):
        lo, hi = bins[i], bins[i + 1]
        m = (sub.p >= lo) & ((sub.p < hi) if i < 9 else (sub.p <= hi))
        if m.sum():
            rel.append({"bin": f"{lo:.1f}-{hi:.1f}", "predicted": round(float(sub.p[m].mean()), 3),
                        "observed": round(float(sub.outcome[m].mean()), 3), "n": int(m.sum())})
    return {"by_climate": out, "default_climate": best, "reliability": rel}


if __name__ == "__main__":
    d = run()
    print(summarize(d))
