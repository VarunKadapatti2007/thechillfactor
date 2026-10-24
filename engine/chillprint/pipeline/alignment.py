"""Day alignment test (BUILD.md 4.6).

For each candidate window (midnight, 4 am, 7 am PST) and lag (0, -1 day),
compute station daily min and max from CIMIS hourly and correlate with the
gridded product at the station pixel. Pick the best and record it.

    python -m chillprint.pipeline.alignment
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .. import config as C
from ..science.hourly import Window, window_minmax
from . import station_hourly as SH

CANDIDATES = [Window(h, lag) for h in (0, 4, 7) for lag in (0, -1)]


def daymet_pixel(sid: str) -> pd.DataFrame | None:
    p = C.PROCESSED_DIR / "daymet" / f"{sid}.parquet"
    return pd.read_parquet(p) if p.exists() else None


def run(max_stations: int = 40) -> dict:
    """Use CIMIS hourly when pulled; otherwise Wildeye in-orchard hourly (keyless)."""
    idx = SH.hourly_index()
    source = "cimis"
    sids = [s for s in idx if daymet_pixel(s) is not None][:max_stations]
    get = SH.station_hourly
    if not sids:
        source = "wildeye"
        st = SH.stations()
        sids = [s for s in st[st.network == "Wildeye"].id if daymet_pixel(s) is not None]
        get = SH.wildeye_hourly
    if not sids:
        raise SystemExit("no stations with both hourly data and Daymet")
    res = {w.label(): {"tmin": [], "tmax": []} for w in CANDIDATES}
    n_days = 0
    for sid in sids:
        hourly = get(sid)
        if hourly.empty:
            continue
        dm = daymet_pixel(sid)
        # Sept-Mar days inside the hourly record and Daymet (ends 2025-12-31)
        days = dm.index[(dm.index >= hourly.index.min() + pd.Timedelta(days=2)) &
                        (dm.index <= min(hourly.index.max() - pd.Timedelta(days=2), pd.Timestamp("2025-12-30"))) &
                        (dm.index.month.isin([9, 10, 11, 12, 1, 2, 3]))]
        days = days[~dm.loc[days, "filled"].to_numpy()]
        if len(days) < 200:
            continue
        n_days += len(days)
        for w in CANDIDATES:
            tmin, tmax, _ = window_minmax(hourly, pd.DatetimeIndex(days), w)
            ok = np.isfinite(tmin) & np.isfinite(tmax)
            res[w.label()]["tmin"].append(np.corrcoef(tmin[ok], dm.loc[days, "tmin"].to_numpy()[ok])[0, 1])
            res[w.label()]["tmax"].append(np.corrcoef(tmax[ok], dm.loc[days, "tmax"].to_numpy()[ok])[0, 1])
    table = {k: {"tmin_r": float(np.mean(v["tmin"])), "tmax_r": float(np.mean(v["tmax"])),
                 "mean_r": float((np.mean(v["tmin"]) + np.mean(v["tmax"])) / 2)} for k, v in res.items()}
    best_label = max(table, key=lambda k: table[k]["mean_r"])
    best = next(w for w in CANDIDATES if w.label() == best_label)
    out = {"daymet": {"table": table, "best": {"start_hour": best.start_hour, "lag_days": best.lag_days,
                                               "label": best_label, **table[best_label]},
                      "n_stations": len(sids), "n_days": int(n_days), "source": source}}
    prev = json.loads(SH.ALIGN_JSON.read_text()) if SH.ALIGN_JSON.exists() else {}
    prev.update(out)
    SH.ALIGN_JSON.write_text(json.dumps(prev, indent=1))
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    run()
