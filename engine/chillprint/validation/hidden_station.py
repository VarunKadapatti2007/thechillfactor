"""Hidden-station test (BUILD.md 5.2): hide station S, estimate it with E0-E5, compare with S.

Truth is our engine on S's CIMIS hourly (>= 95% hours Sept 1 - Mar 1). Without
CIMIS hourly, the keyless mode uses FNRIC's daily portions as truth and runs only
E0, E1 and E2. Results: validation_by_station.parquet (one row per station-season-estimator).
"""
from __future__ import annotations

import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
from tqdm import tqdm

from .. import config as C
from ..pipeline import station_hourly as SH
from ..science.gdd import gdd_series
from ..science.hourly import window_minmax
from . import common as V

NAMES = {
    "E0": "Nearest station",
    "E1": "3-station average",
    "E2": "Daymet + textbook curve",
    "E3": "Daymet + borrowed shape",
    "E4": "Station + Daymet offset",
    "E5": "One reading a day",
    "E8": "3 stations + Daymet offset",
}
SEASONS = range(C.VALIDATION_FIRST_SEASON, C.LAST_COMPLETE_DAYMET_SEASON + 2)  # 2005-06 .. 2025-26


def _truth_cache(sids_seasons, keyless: bool) -> dict:
    out = {}
    for sid, y in sids_seasons:
        if keyless:
            c = V.fnric_truth_cum(sid, y)
            if c is not None:
                out[(sid, y)] = c
        else:
            h = V.season_hourly(SH.station_hourly(sid), y)
            out[(sid, y)] = V.daily_cum(h)
    return out


def _gdd_window(daily: pd.DataFrame, season: int) -> float:
    """GDD Feb 1 - Mar 31 (our hourly pull ends Mar 31; see REPORT.md)."""
    sub = daily.loc[f"{season + 1}-02-01":f"{season + 1}-03-31"]
    return float(np.nansum(gdd_series(sub["tmin"].to_numpy(), sub["tmax"].to_numpy())))


def run_station(args) -> list[dict]:
    sid, keyless = args
    st = SH.stations().set_index("id")
    s = st.loc[sid]
    win = SH.window_for("daymet")
    dm = V.daymet_pixel(sid)
    complete = V.complete_set() if not keyless else None
    rows = []
    if keyless:
        seasons = [y for y in SEASONS if V.fnric_truth_cum(sid, y) is not None]
    else:
        seasons = [y for y in SEASONS if (sid, y) in complete]
    own = None if keyless else SH.station_hourly(sid)
    for y in seasons:
        if keyless:
            truth = V.fnric_truth_cum(sid, y)
            pool = [x for x in _keyless_pool(y) if x != sid]
            nb = _rank(s.lat, s.lon, pool, st)
        else:
            truth_h = V.season_hourly(own, y)
            truth = V.daily_cum(truth_h)
            nb = V.neighbors(s.lat, s.lon, y, (sid,), complete, k=5)
        if nb.empty:
            continue
        d0 = float(nb.iloc[0].dist_km)
        ter = V.terrain(s.elev_m, nb.iloc[0].elev_m)
        base = {"station_id": sid, "season": y, "dist_km": d0, "terrain": ter, "lat": s.lat, "lon": s.lon}
        tm = V.metrics(truth, y)
        ests: dict[str, dict] = {}

        def nb_cum(nid):
            if keyless:
                return V.fnric_truth_cum(nid, y)
            if (nid, y) not in _TRUTH:
                _TRUTH[(nid, y)] = V.daily_cum(V.season_hourly(SH.station_hourly(nid), y))
            return _TRUTH[(nid, y)]

        c0 = nb_cum(nb.iloc[0].id)
        if c0 is not None:
            ests["E0"] = {**V.metrics(c0, y)}
        cs, ws = [], []
        for r in nb.head(3).itertuples():
            c = nb_cum(r.id)
            if c is not None:
                cs.append(c)
                ws.append(1.0 / max(r.dist_km, 0.5) ** 2)
        if cs:
            ests["E1"] = V.metrics(np.average(np.vstack(cs), axis=0, weights=ws), y)
        has_dm = dm is not None and y <= C.LAST_COMPLETE_DAYMET_SEASON
        hourly_est = {}
        if has_dm:
            hourly_est["E2"] = V.e2_hours(s.lat, dm, y, win)
        if not keyless:
            shapes = [SH.station_hourly(r.id) for r in nb.head(3).itertuples()]
            if has_dm:
                hourly_est["E3"] = V.b_hours(s.lat, dm, y, shapes, win)
            dm_nb = V.daymet_pixel(nb.iloc[0].id)
            if dm is not None and dm_nb is not None:
                hourly_est["E4"] = V.e4_hours(SH.station_hourly(nb.iloc[0].id), dm, dm_nb, y)
            if dm is not None and len(nb) >= 2:
                e8 = V.e8_hours([(r.id, r.dist_km, r.lat, r.lon) for r in nb.head(3).itertuples()], dm, y)
                if e8 is not None:
                    hourly_est["E8"] = e8
            own_d = V.own_window_daily(own, y, win)
            hourly_est["E5"] = V.b_hours(s.lat, own_d, y, shapes, win)
        for k, h in hourly_est.items():
            ests[k] = V.metrics(V.daily_cum(h), y)
            if not keyless:
                ests[k]["hourly_rmse"] = V.hourly_rmse(h, truth_h, y)
        # GDD (Feb 1 - Mar 31) from daily min/max: truth from station hours, estimates from their daily inputs
        if not keyless:
            days = pd.date_range(f"{y + 1}-02-01", f"{y + 1}-03-31", freq="D")
            tmin, tmax, _ = window_minmax(own, days, win)
            g_truth = float(np.nansum(gdd_series(tmin, tmax)))
            if has_dm:
                g_dm = _gdd_window(dm, y)
                for k in ("E2", "E3"):
                    if k in ests:
                        ests[k]["gdd_err"] = g_dm - g_truth
            if "E5" in ests:
                ests["E5"]["gdd_err"] = 0.0
            nb_d = V.own_window_daily(SH.station_hourly(nb.iloc[0].id), y, win)
            if "E0" in ests:
                ests["E0"]["gdd_err"] = _gdd_window(nb_d, y) - g_truth
        for k, m in ests.items():
            row = {**base, "estimator": k}
            for key in ("cp_nov1", "cp_dec1", "cp_jan1", "cp_feb1", "cp_mar1"):
                row[key] = m[key]
                row[key.replace("cp_", "truth_")] = tm[key]
                row[key.replace("cp_", "err_")] = m[key] - tm[key]
            for lv in V.CROSS:
                t, e = tm[f"cross{int(lv)}"], m[f"cross{int(lv)}"]
                row[f"cross{int(lv)}_err"] = e - t if np.isfinite(t) and np.isfinite(e) else np.nan
            row["hourly_rmse"] = m.get("hourly_rmse", np.nan)
            row["gdd_err"] = m.get("gdd_err", np.nan)
            rows.append(row)
    return rows


_POOL_CACHE: dict = {}
_TRUTH: dict = {}


def _keyless_pool(season: int) -> list[str]:
    if season not in _POOL_CACHE:
        st = SH.stations()
        ids = st[(st.network == "CIMIS") & st.central_valley].id
        _POOL_CACHE[season] = [s for s in ids if V.fnric_truth_cum(s, season) is not None]
    return _POOL_CACHE[season]


def _rank(lat, lon, ids, st):
    sub = st.loc[ids].reset_index()
    sub["dist_km"] = SH.haversine_km(lat, lon, sub.lat.to_numpy(), sub.lon.to_numpy())
    return sub.sort_values("dist_km").head(5)


def run(keyless: bool | None = None, workers: int = 6) -> pd.DataFrame:
    if keyless is None:
        keyless = len(SH.hourly_index()) == 0
    st = SH.stations()
    if keyless:
        sids = list(st[(st.network == "CIMIS") & st.central_valley].id)
    else:
        sids = sorted({s for s, _ in V.complete_set()} & set(st[st.central_valley].id))
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for r in tqdm(ex.map(run_station, [(s, keyless) for s in sids]), total=len(sids), desc="hidden stations"):
            rows.extend(r)
    df = pd.DataFrame(rows)
    df["mode"] = "keyless" if keyless else "full"
    df.to_parquet(V.OUT / "validation_by_station.parquet", index=False)
    print(f"hidden-station rows: {len(df)}; stations {df.station_id.nunique()}; station-seasons "
          f"{df[['station_id', 'season']].drop_duplicates().shape[0]}; mode {'keyless' if keyless else 'full'}")
    return df


if __name__ == "__main__":
    run(keyless=("--keyless" in sys.argv) or None)
