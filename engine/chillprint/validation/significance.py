"""Is the default's advantage real, and does the choice survive data it was not chosen on?

1. Paired cluster bootstrap: per station-winter, |error| averaged over Feb 1 and Mar 1; the
   difference between two estimators on the same cases; resample whole stations (winters at one
   station are not independent) 5,000 times for a 95% interval on the mean difference.
2. Split-sample selection: rank estimators on one half (early winters / half the stations),
   then check the ranking on the other half, which played no part in the choice.

    python -m chillprint.validation.significance
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .. import config as C
from . import common as V

ESTS = ["E0", "E1", "E2", "E3", "E4", "E5"]


def per_case(df: pd.DataFrame) -> pd.DataFrame:
    df = df.assign(abs_err=(df.err_feb1.abs() + df.err_mar1.abs()) / 2)
    return df.pivot_table(index=["station_id", "season"], columns="estimator", values="abs_err", aggfunc="first")


def cluster_bootstrap(diff: pd.Series, n: int = 5000, seed: int = C.SEED) -> dict:
    """diff indexed by (station_id, season); resample stations with replacement."""
    by_st = diff.groupby(level=0)
    sums = by_st.sum().to_numpy()
    counts = by_st.size().to_numpy()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(sums), size=(n, len(sums)))
    boot = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {"mean_diff": round(float(diff.mean()), 3), "ci95": [round(float(lo), 3), round(float(hi), 3)],
            "n_cases": int(len(diff)), "n_stations": int(len(sums)),
            "share_cases_better": round(float((diff < 0).mean()), 3)}


def run() -> dict:
    hs = pd.read_parquet(V.OUT / "validation_by_station.parquet")
    P = per_case(hs).dropna(subset=[e for e in ESTS if e in hs.estimator.unique()])
    out = {"n_cases": int(len(P)), "mae": {e: round(float(P[e].mean()), 3) for e in P.columns}}

    # 1. Paired differences, default (E4) minus each alternative: negative = E4 better.
    out["paired_vs_E4"] = {e: cluster_bootstrap(P["E4"] - P[e]) for e in P.columns if e != "E4"}
    st = pd.read_parquet(C.PROCESSED_DIR / "stations.parquet").set_index("id")
    dist = hs.groupby(["station_id", "season"]).dist_km.first().reindex(P.index)
    bins = pd.cut(dist, [0, 10, 25, 50, 1e9], labels=list(C.DIST_BIN_LABELS), right=False)
    out["E4_minus_E0_by_distance"] = {str(b): cluster_bootstrap((P["E4"] - P["E0"])[bins == b])
                                      for b in bins.cat.categories if (bins == b).sum() >= 20}

    # 2. Split-sample selection.
    seasons = P.index.get_level_values(1)
    stations = P.index.get_level_values(0)
    candidates = [e for e in ("E0", "E1", "E2", "E3", "E4") if e in P.columns]  # E5 needs an orchard reading; E8 judged separately below
    halves = {
        "time: choose on 2005-06..2014-15, confirm on 2015-16..2025-26": (seasons <= 2014, seasons >= 2015),
        "stations: choose on half the stations, confirm on the other half": (
            stations.isin(sorted(set(stations))[::2]), ~stations.isin(sorted(set(stations))[::2])),
    }
    out["split_sample"] = {}
    for name, (a, b) in halves.items():
        pick = min(candidates, key=lambda e: P.loc[a, e].mean())
        out["split_sample"][name] = {
            "chosen_on_first_half": pick,
            "first_half_mae": {e: round(float(P.loc[a, e].mean()), 3) for e in candidates},
            "second_half_mae": {e: round(float(P.loc[b, e].mean()), 3) for e in candidates},
            "chosen_still_beats_nearest_station_on_second_half": bool(P.loc[b, pick].mean() < P.loc[b, "E0"].mean()),
        }

    # 3. Independent in-orchard set (Wildeye), same paired bootstrap.
    we = pd.read_parquet(V.OUT / "wildeye_results.parquet")
    W = per_case(we)
    if {"E4", "E0"} <= set(W.columns):
        w = W.dropna(subset=["E4", "E0"])
        out["wildeye_E4_minus_E0"] = cluster_bootstrap(w["E4"] - w["E0"])
    # 4. Pre-registered E8 test (criteria fixed in PROGRESS.md before E8 was run).
    if "E8" in P.columns:
        Q = P.dropna(subset=["E4", "E8"])
        boot = cluster_bootstrap(Q["E8"] - Q["E4"])
        qs, qst = Q.index.get_level_values(1), Q.index.get_level_values(0)
        half_st = qst.isin(sorted(set(stations))[::2])
        c2a = float(Q.loc[qs >= 2015, "E8"].mean()) < float(Q.loc[qs >= 2015, "E4"].mean())
        c2b = float(Q.loc[~half_st, "E8"].mean()) < float(Q.loc[~half_st, "E4"].mean())
        wd = None
        if {"E4", "E8"} <= set(W.columns):
            ww = W.dropna(subset=["E4", "E8"])
            wd = cluster_bootstrap(ww["E8"] - ww["E4"])
        crit = {"1_ci_below_zero": bool(boot["ci95"][1] < 0), "2_beats_E4_both_second_halves": bool(c2a and c2b),
                "3_not_worse_at_wildeye": bool(wd is not None and wd["mean_diff"] <= 0)}
        out["preregistered_E8"] = {"E8_minus_E4": boot, "second_half_2015_26": {"E8": round(float(Q.loc[qs >= 2015, "E8"].mean()), 3), "E4": round(float(Q.loc[qs >= 2015, "E4"].mean()), 3)},
                                   "second_half_stations": {"E8": round(float(Q.loc[~half_st, "E8"].mean()), 3), "E4": round(float(Q.loc[~half_st, "E4"].mean()), 3)},
                                   "wildeye_E8_minus_E4": wd, "criteria": crit, "adopt": all(crit.values())}
    (V.OUT / "significance.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    run()
