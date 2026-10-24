"""Independent test on Wildeye in-orchard stations (BUILD.md 5.3).

Truth: our engine on each Wildeye station's own hourly air temperature.
Estimators: E0 (nearest CIMIS station), E2, E3 (Daymet at the orchard), E4
(nearest CIMIS hourly + Daymet offset). E3/E4 need CIMIS hourly.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config as C
from ..pipeline import station_hourly as SH
from ..sources import daymet
from . import common as V

SEASONS = (2023, 2024, 2025)


def _cimis_cum(sid: str, season: int, keyless: bool) -> np.ndarray | None:
    if not keyless and sid in SH.hourly_index() and season in SH.hourly_index()[sid]:
        h = SH.station_hourly(sid)
        if V.coverage(h, season) >= V.MIN_COVERAGE:
            return V.daily_cum(V.season_hourly(h, season))
    return V.fnric_truth_cum(sid, season)


def run() -> pd.DataFrame:
    keyless = len(SH.hourly_index()) == 0
    st = SH.stations()
    we = st[(st.network == "Wildeye") & st.active]
    win = SH.window_for("daymet")
    rows = []
    for s in we.itertuples():
        h = SH.wildeye_hourly(s.id)
        if h.empty:
            continue
        try:
            dm, _ = daymet.daily(round(s.lat, 4), round(s.lon, 4))
        except Exception:
            dm = None
        for y in SEASONS:
            if V.coverage(h, y) < V.MIN_COVERAGE:
                continue
            truth_h = V.season_hourly(h, y)
            truth = V.daily_cum(truth_h)
            cands = SH.nearest_cimis(s.lat, s.lon, k=8)
            base = {"station_id": s.id, "name": s.name, "season": y, "lat": s.lat, "lon": s.lon}
            ests = {}
            for r in cands.itertuples():  # E0: nearest CIMIS station with a usable record that winter
                c = _cimis_cum(r.id, y, keyless)
                if c is not None:
                    ests["E0"] = c
                    base["nearest"] = r.id
                    base["dist_km"] = float(r.dist_km)
                    break
            has_dm = dm is not None and y <= C.LAST_COMPLETE_DAYMET_SEASON
            if has_dm:
                ests["E2"] = V.daily_cum(V.e2_hours(s.lat, dm, y, win))
            if not keyless:
                nb = SH.nearest_cimis(s.lat, s.lon, with_hourly=True, season=y, k=3)
                nb = nb[[V.coverage(SH.station_hourly(i), y) >= V.MIN_COVERAGE for i in nb.id]]
                if len(nb):
                    shapes = [SH.station_hourly(i) for i in nb.id]
                    if has_dm:
                        ests["E3"] = V.daily_cum(V.b_hours(s.lat, dm, y, shapes, win))
                    dm_nb = V.daymet_pixel(nb.iloc[0].id)
                    if dm is not None and dm_nb is not None:
                        ests["E4"] = V.daily_cum(V.e4_hours(SH.station_hourly(nb.iloc[0].id), dm, dm_nb, y))
                    if dm is not None and len(nb) >= 2:
                        e8 = V.e8_hours([(r.id, r.dist_km, r.lat, r.lon) for r in nb.head(3).itertuples()], dm, y)
                        if e8 is not None:
                            ests["E8"] = V.daily_cum(e8)
            tm = V.metrics(truth, y)
            for k, c in ests.items():
                m = V.metrics(c, y)
                rows.append({**base, "estimator": k, "truth_mar1": tm["cp_mar1"], "cp_mar1": m["cp_mar1"],
                             "err_mar1": m["cp_mar1"] - tm["cp_mar1"], "truth_feb1": tm["cp_feb1"],
                             "err_feb1": m["cp_feb1"] - tm["cp_feb1"]})
    df = pd.DataFrame(rows)
    df.to_parquet(V.OUT / "wildeye_results.parquet", index=False)
    if len(df):
        print("wildeye:", df.groupby("estimator").err_mar1.apply(lambda e: e.abs().mean()).round(2).to_dict(),
              "station-seasons", df[["station_id", "season"]].drop_duplicates().shape[0])
    return df


if __name__ == "__main__":
    run()
