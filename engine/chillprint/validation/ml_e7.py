"""E7: ML nighttime-low correction (BUILD.md Phase 6 step 1).

LightGBM predicts the station-minus-Daymet daily Tmin residual from Daymet Tmin,
daily range, month, elevation, elevation difference to neighbors, terrain
position (TPI at 1 and 5 km, AWS Terrain Tiles) and distance-weighted neighbor
residuals that day. Grouped cross-validation leaves one station out per fold;
the held-out station's corrected Tmin (Tmax stays Daymet) is rebuilt with
Method B and scored exactly like E3. Ships only if it beats the default on
hidden stations and on Wildeye.

    python -m chillprint.validation.ml_e7
"""
from __future__ import annotations

import json

import lightgbm as lgb
import numpy as np
import pandas as pd
from tqdm import tqdm

from .. import config as C
from ..pipeline import station_hourly as SH
from ..sources import daymet, terrain
from . import common as V

FEATURES = ["dm_tmin", "dm_range", "month", "elev", "delev", "tpi1", "tpi5", "nb_resid"]
PARAMS = dict(n_estimators=400, learning_rate=0.05, num_leaves=31, min_child_samples=50,
              subsample=0.8, subsample_freq=1, colsample_bytree=0.9, random_state=C.SEED, verbose=-1)


def _station_daily_tmin(sid: str, src: str = "cimis") -> pd.Series:
    win = SH.window_for("daymet")
    h = SH.station_hourly(sid) if src == "cimis" else SH.wildeye_hourly(sid)
    if h.empty:
        return pd.Series(dtype=float)
    days = pd.date_range(h.index.min().normalize() + pd.Timedelta(days=1), h.index.max().normalize() - pd.Timedelta(days=1), freq="D")
    days = days[days.month.isin([9, 10, 11, 12, 1, 2, 3]) & (days <= pd.Timestamp("2025-12-31"))]
    from ..science.hourly import window_minmax
    tmin, _, _ = window_minmax(h, days, win)
    return pd.Series(tmin, index=days)


def _site_static(lat: float, lon: float, elev: float | None, nb: pd.DataFrame) -> dict:
    e = elev if elev is not None and np.isfinite(elev) else terrain.elevation(lat, lon)
    nbe = nb.elev_m.dropna()
    return {"elev": e, "delev": e - float(nbe.mean()) if len(nbe) else 0.0,
            "tpi1": terrain.tpi(lat, lon, 1.0), "tpi5": terrain.tpi(lat, lon, 5.0)}


def build_table() -> pd.DataFrame:
    """One row per station-day with features, target residual and neighbor residuals."""
    st = SH.stations().set_index("id")
    complete = V.complete_set()
    sids = sorted({s for s, _ in complete} & set(st[st.central_valley].index))
    resid = {}
    for sid in tqdm(sids, desc="residuals"):
        dm = V.daymet_pixel(sid)
        tmin = _station_daily_tmin(sid)
        if dm is None or tmin.empty:
            continue
        r = (tmin - dm["tmin"].reindex(tmin.index)).dropna()
        # keep only complete station-seasons
        seasons = r.index.year.where(r.index.month >= 9, r.index.year - 1)
        keep = [(sid, int(y)) in complete for y in seasons]
        resid[sid] = r[keep]
    R = pd.DataFrame(resid)
    rows = []
    for sid in tqdm(list(R.columns), desc="features"):
        s = st.loc[sid]
        nb = SH.nearest_cimis(s.lat, s.lon, exclude=(sid,), k=6)
        nb = nb[nb.id.isin(R.columns)].head(3)
        if nb.empty:
            continue
        static = _site_static(s.lat, s.lon, s.elev_m, nb)
        w = 1.0 / np.maximum(nb.dist_km.to_numpy(), 0.5) ** 2
        nbr = R[nb.id.tolist()]
        nb_res = (nbr * w).sum(axis=1, min_count=1) / (nbr.notna() * w).sum(axis=1).replace(0, np.nan)
        dm = V.daymet_pixel(sid)
        y = R[sid].dropna()
        df = pd.DataFrame({"station_id": sid, "date": y.index, "target": y.to_numpy(),
                           "dm_tmin": dm["tmin"].reindex(y.index).to_numpy(),
                           "dm_range": (dm["tmax"] - dm["tmin"]).reindex(y.index).to_numpy(),
                           "month": y.index.month, "nb_resid": nb_res.reindex(y.index).to_numpy(), **static})
        rows.append(df)
    return pd.concat(rows, ignore_index=True)


def loso_predictions(T: pd.DataFrame) -> pd.Series:
    pred = pd.Series(np.nan, index=T.index)
    for sid in tqdm(T.station_id.unique(), desc="LOSO folds"):
        tr = T.station_id != sid
        m = lgb.LGBMRegressor(**PARAMS).fit(T.loc[tr, FEATURES], T.loc[tr, "target"])
        pred[~tr] = m.predict(T.loc[~tr, FEATURES])
    return pred


def score_hidden(T: pd.DataFrame, pred: pd.Series) -> pd.DataFrame:
    """E7 CP errors on hidden stations, same seasons and metrics as E3."""
    st = SH.stations().set_index("id")
    complete = V.complete_set()
    win = SH.window_for("daymet")
    T = T.assign(pred=pred)
    rows = []
    for sid, g in tqdm(T.groupby("station_id"), desc="E7 hidden scoring"):
        s = st.loc[sid]
        dm = V.daymet_pixel(sid).copy()
        corr = g.set_index("date")["pred"]
        dm.loc[corr.index, "tmin"] = dm.loc[corr.index, "tmin"] + corr
        dm["tmin"] = np.minimum(dm["tmin"], dm["tmax"] - 0.1)
        for y in sorted({int(d.year if d.month >= 9 else d.year - 1) for d in g.date}):
            if (sid, y) not in complete or y > C.LAST_COMPLETE_DAYMET_SEASON:
                continue
            nb = V.neighbors(s.lat, s.lon, y, (sid,), complete, k=3)
            if nb.empty:
                continue
            truth = V.daily_cum(V.season_hourly(SH.station_hourly(sid), y))
            est = V.daily_cum(V.b_hours(s.lat, dm, y, [SH.station_hourly(i) for i in nb.id], win))
            tm, em = V.metrics(truth, y), V.metrics(est, y)
            rows.append({"station_id": sid, "season": y, "err_feb1": em["cp_feb1"] - tm["cp_feb1"],
                         "err_mar1": em["cp_mar1"] - tm["cp_mar1"]})
    return pd.DataFrame(rows)


def score_wildeye(T: pd.DataFrame) -> pd.DataFrame:
    """Train on all CIMIS stations, correct Daymet at Wildeye sites, score against in-orchard truth."""
    model = lgb.LGBMRegressor(**PARAMS).fit(T[FEATURES], T["target"])
    st = SH.stations()
    R = T.pivot_table(index="date", columns="station_id", values="target")
    win = SH.window_for("daymet")
    rows = []
    for s in st[(st.network == "Wildeye") & st.active].itertuples():
        h = SH.wildeye_hourly(s.id)
        if h.empty:
            continue
        nb = SH.nearest_cimis(s.lat, s.lon, k=8)
        nb = nb[nb.id.isin(R.columns)].head(3)
        if nb.empty:
            continue
        dm, _ = daymet.daily(round(s.lat, 4), round(s.lon, 4))
        static = _site_static(s.lat, s.lon, s.elev_m, nb)
        w = 1.0 / np.maximum(nb.dist_km.to_numpy(), 0.5) ** 2
        nbr = R[nb.id.tolist()]
        nb_res = (nbr * w).sum(axis=1, min_count=1) / (nbr.notna() * w).sum(axis=1).replace(0, np.nan)
        idx = dm.index[(dm.index >= "2023-08-25") & dm.index.month.isin([8, 9, 10, 11, 12, 1, 2, 3, 4])]
        X = pd.DataFrame({"dm_tmin": dm.loc[idx, "tmin"], "dm_range": dm.loc[idx, "tmax"] - dm.loc[idx, "tmin"],
                          "month": idx.month, "nb_resid": nb_res.reindex(idx).to_numpy(), **static}, index=idx)[FEATURES]
        dm2 = dm.copy()
        dm2.loc[idx, "tmin"] = np.minimum(dm.loc[idx, "tmin"] + model.predict(X), dm.loc[idx, "tmax"] - 0.1)
        for y in (2023, 2024):
            if V.coverage(h, y) < V.MIN_COVERAGE:
                continue
            truth = V.daily_cum(V.season_hourly(h, y))
            cims = SH.nearest_cimis(s.lat, s.lon, with_hourly=True, season=y, k=3)
            shapes = [SH.station_hourly(i) for i in cims.id]
            e7 = V.daily_cum(V.b_hours(s.lat, dm2, y, shapes, win))
            e3 = V.daily_cum(V.b_hours(s.lat, dm, y, shapes, win))
            tm = V.metrics(truth, y)
            for k, c in (("E7", e7), ("E3", e3)):
                m = V.metrics(c, y)
                rows.append({"station_id": s.id, "season": y, "estimator": k,
                             "err_feb1": m["cp_feb1"] - tm["cp_feb1"], "err_mar1": m["cp_mar1"] - tm["cp_mar1"]})
    return pd.DataFrame(rows)


def compare_with_default(hid: pd.DataFrame, we: pd.DataFrame, default: str = "E4") -> dict:
    """E7 against the shipped default on the same cases (BUILD.md: ship only if it beats the default)."""
    mae = lambda e: float(pd.concat([e.err_feb1, e.err_mar1]).abs().mean())  # noqa: E731
    hs = pd.read_parquet(V.OUT / "validation_by_station.parquet")
    d = hs[hs.estimator == default].set_index(["station_id", "season"])
    h7 = hid.set_index(["station_id", "season"])
    idx = h7.index.intersection(d.index)
    w = pd.read_parquet(V.OUT / "wildeye_results.parquet")
    wd = w[w.estimator == default].set_index(["station_id", "season"])
    w7 = we[we.estimator == "E7"].set_index(["station_id", "season"])
    widx = w7.index.intersection(wd.index)
    res = {"default": default, "hidden_n": int(len(idx)),
           "hidden_default_mae": round(mae(d.loc[idx]), 3), "hidden_e7_mae": round(mae(h7.loc[idx]), 3),
           "wildeye_n": int(len(widx)),
           "wildeye_default_mae": round(mae(wd.loc[widx]), 3) if len(widx) else None,
           "wildeye_e7_mae": round(mae(w7.loc[widx]), 3) if len(widx) else None}
    res["beats_default_hidden"] = res["hidden_e7_mae"] < res["hidden_default_mae"]
    res["beats_default_wildeye"] = bool(len(widx)) and res["wildeye_e7_mae"] < res["wildeye_default_mae"]
    return res


def run() -> dict:
    T = build_table()
    T.to_parquet(V.OUT / "e7_table.parquet", index=False)
    pred = loso_predictions(T)
    tmin_rmse_before = float(np.sqrt(np.mean(T.target ** 2)))
    tmin_rmse_after = float(np.sqrt(np.mean((T.target - pred) ** 2)))
    hid = score_hidden(T, pred)
    hid.to_parquet(V.OUT / "e7_hidden.parquet", index=False)
    we = score_wildeye(T)
    we.to_parquet(V.OUT / "e7_wildeye.parquet", index=False)
    hs = pd.read_parquet(V.OUT / "validation_by_station.parquet")
    e3 = hs[hs.estimator == "E3"].set_index(["station_id", "season"])
    common = hid.set_index(["station_id", "season"]).index.intersection(e3.index)
    h7 = hid.set_index(["station_id", "season"]).loc[common]
    e3c = e3.loc[common]
    mae = lambda d: float(pd.concat([d.err_feb1, d.err_mar1]).abs().mean())  # noqa: E731
    out = {"tmin_rmse_daymet": round(tmin_rmse_before, 3), "tmin_rmse_e7": round(tmin_rmse_after, 3),
           "hidden": {"n": int(len(common)), "e3_mae": round(mae(e3c), 3), "e7_mae": round(mae(h7), 3),
                      "e7_p80": round(float(pd.concat([h7.err_feb1, h7.err_mar1]).abs().quantile(0.8)), 3),
                      "e7_bias": round(float(pd.concat([h7.err_feb1, h7.err_mar1]).mean()), 3)}}
    if len(we):
        out["wildeye"] = {k: round(mae(g), 3) for k, g in we.groupby("estimator")}
    out.update(compare_with_default(hid, we))
    out["ship"] = bool(out["beats_default_hidden"] and out["beats_default_wildeye"])
    (V.OUT / "e7_summary.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    run()
