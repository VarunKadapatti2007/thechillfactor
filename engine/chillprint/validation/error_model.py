"""Error model (BUILD.md 4.10): 80th-percentile absolute CP error at the by date,
binned by distance to the nearest station and terrain, for the history and live defaults."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .. import config as C
from ..products.errorbar import dist_bin
from . import common as V

MIN_N = 15


def build(df: pd.DataFrame, history_id: str, live_id: str) -> dict:
    out = {"note": "80th percentile of |estimate - truth| CP by Mar 1 and Feb 1 on hidden stations; "
                   "8 in 10 hidden-station tests landed within this range."}
    for role, eid in (("history", history_id), ("live", live_id)):
        sub = df[df.estimator == eid].copy()
        if sub.empty:
            continue
        err = pd.concat([sub.assign(e=sub.err_mar1.abs()), sub.assign(e=sub.err_feb1.abs())])
        err["dbin"] = err.dist_km.map(dist_bin)
        bins, counts = {}, {}
        for (db, ter), g in err.groupby(["dbin", "terrain"]):
            counts[f"{db}|{ter}"] = int(len(g))
            if len(g) >= MIN_N:
                bins[f"{db}|{ter}"] = round(float(g.e.quantile(0.8)), 2)
        by_d = {db: round(float(g.e.quantile(0.8)), 2) for db, g in err.groupby("dbin") if len(g) >= MIN_N}
        out[role] = {"estimator": eid, "bins": bins, "by_distance": by_d, "counts": counts,
                     "overall": round(float(err.e.quantile(0.8)), 2)}
    (V.OUT / "error_model.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out
