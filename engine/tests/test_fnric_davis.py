"""GATE 2: our engine on CIMIS-6 (Davis) hourly vs FNRIC's daily chill, three seasons.

Season totals within 0.5 CP and daily correlation above 0.99, for Dynamic CP,
Utah units and both chill-hour counts. Skipped until CIMIS hourly is pulled.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from chillprint.science.season import daily_chill

DATA = Path(__file__).resolve().parents[1] / "data" / "processed"
SEASONS = (2014, 2018, 2023)
COLS = ("portions_dynamic", "units_utah", "hours_lt_45", "hours_32_45")


def _hourly(season):
    p = DATA / "cimis_hourly" / "station=CIMIS-6" / f"season={season}.parquet"
    if not p.exists():
        pytest.skip("CIMIS-6 hourly not pulled yet")
    df = pd.read_parquet(p)
    df["ts"] = pd.to_datetime(df["ts"])
    return df.set_index("ts")["t_c"]


def _fnric():
    p = DATA / "fnric_daily_chill.parquet"
    if not p.exists():
        pytest.skip("FNRIC daily chill not pulled yet")
    f = pd.read_parquet(p)
    f = f[f.station_id == "CIMIS-6"].copy()
    f["date"] = pd.to_datetime(f["date"])
    return f.set_index("date")


def compare(season):
    ours = daily_chill(_hourly(season), season)
    fn = _fnric().loc[ours.index.min():ours.index.max()]
    j = ours.join(fn[list(COLS)], rsuffix="_fnric", how="inner")
    out = {}
    for c in COLS:
        a, b = j[c], j[c + "_fnric"]
        out[c] = {"ours_total": float(a.sum()), "fnric_total": float(b.sum()),
                  "diff": float(a.sum() - b.sum()), "corr": float(np.corrcoef(a, b)[0, 1]),
                  "days_mismatch": int((np.abs(a - b) > (0.05 if c == "portions_dynamic" else 0.6)).sum())}
    return out, j


@pytest.mark.parametrize("season", SEASONS)
def test_davis_matches_fnric(season):
    res, _ = compare(season)
    print(f"\n{season}-{season + 1}:", {k: {kk: round(vv, 3) for kk, vv in v.items()} for k, v in res.items()})
    assert abs(res["portions_dynamic"]["diff"]) < 0.5
    for c in COLS:
        assert res[c]["corr"] > 0.99, (c, res[c])
