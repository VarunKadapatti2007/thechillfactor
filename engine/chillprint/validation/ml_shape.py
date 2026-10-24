"""ML hourly shape (BUILD.md Phase 6 step 2).

LightGBM predicts the normalized hourly position (T - Tmin) / (Tmax - Tmin)
within each day window from the hour, day length, daily range, daily solar
radiation and month, trained on CIMIS hourly with Daymet-side predictors (what a
pin has). Grouped cross-validation holds out whole stations. The predicted
shape replaces the neighbour's shape inside Method B (same rescaling and
blending), and is scored against E3 on the same hidden station-seasons.
Ships only if it beats Method B.

    python -m chillprint.validation.ml_shape
"""
from __future__ import annotations

import json

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from tqdm import tqdm

from .. import config as C
from ..pipeline import station_hourly as SH
from ..science.daylength import daylength
from ..science.hourly import window_matrix
from . import common as V

FEATURES = ["hour", "daylen", "range", "srad", "month", "lat"]
PARAMS = dict(n_estimators=300, learning_rate=0.05, num_leaves=63, min_child_samples=200,
              subsample=0.7, subsample_freq=1, random_state=C.SEED, verbose=-1)


def _station_days(sid: str, seasons: list[int], win) -> pd.DataFrame:
    st = SH.stations().set_index("id").loc[sid]
    dm = V.daymet_pixel(sid)
    h = SH.station_hourly(sid)
    rows = []
    for y in seasons:
        if y > C.LAST_COMPLETE_DAYMET_SEASON:
            continue
        days = pd.date_range(f"{y}-09-01", f"{y + 1}-03-31", freq="D")
        m = window_matrix(h, days, win)
        ok = ~np.isnan(m).any(axis=1)
        lo, hi = m.min(axis=1), m.max(axis=1)
        rng = hi - lo
        ok &= rng >= 0.5
        pos = (m - lo[:, None]) / np.where(rng > 0, rng, 1)[:, None]
        _, _, dl = daylength(float(st.lat), days.day_of_year.to_numpy())
        d = dm.reindex(days)
        for i in np.flatnonzero(ok):
            rows.append(np.column_stack([np.arange(24), np.full(24, dl[i]), np.full(24, d["tmax"].iloc[i] - d["tmin"].iloc[i]),
                                         np.full(24, d["srad"].iloc[i]), np.full(24, days[i].month), np.full(24, float(st.lat)),
                                         pos[i]]).astype(np.float64))
    if not rows:
        return pd.DataFrame(columns=FEATURES + ["target"])
    a = np.vstack(rows).astype(np.float64)
    return pd.DataFrame(a, columns=FEATURES + ["target"])


def build_table(max_rows: int = 1_500_000) -> pd.DataFrame:
    win = SH.window_for("daymet")
    by_st: dict[str, list[int]] = {}
    for s, y in V.complete_set():
        by_st.setdefault(s, []).append(y)
    frames = [_station_days(s, ys, win).assign(station_id=s) for s, ys in tqdm(sorted(by_st.items()), desc="shape rows")]
    T = pd.concat(frames, ignore_index=True)
    T[FEATURES + ["target"]] = T[FEATURES + ["target"]].astype(np.float64)
    if len(T) > max_rows:  # subsample whole days evenly (keep 24-hour blocks intact)
        days = len(T) // 24
        keep = np.random.default_rng(C.SEED).choice(days, size=max_rows // 24, replace=False)
        idx = (keep[:, None] * 24 + np.arange(24)[None, :]).ravel()
        T = T.iloc[np.sort(idx)].reset_index(drop=True)
    return T


def _shape_series(model, sid_lat: float, dm: pd.DataFrame, season: int, win) -> pd.Series:
    """Synthetic 'station' series of predicted positions (0..1 per day) on the window's stamps."""
    days = pd.date_range(pd.Timestamp(season, 8, 29), pd.Timestamp(season + 1, 4, 3), freq="D")
    _, _, dl = daylength(sid_lat, days.day_of_year.to_numpy())
    d = dm.reindex(days).interpolate(limit_direction="both")
    X = pd.DataFrame({"hour": np.tile(np.arange(24), len(days)), "daylen": np.repeat(dl, 24),
                      "range": np.repeat((d["tmax"] - d["tmin"]).to_numpy(), 24), "srad": np.repeat(d["srad"].to_numpy(), 24),
                      "month": np.repeat(days.month.to_numpy(), 24), "lat": sid_lat})[FEATURES]
    p = model.predict(X).reshape(len(days), 24)
    first = win.first_stamp(days)
    stamps = (first[:, None] + (np.arange(24) * np.timedelta64(1, "h"))[None, :]).ravel()
    return pd.Series(p.ravel(), index=pd.DatetimeIndex(stamps))


def run(n_folds: int = 8) -> dict:
    T = build_table()
    win = SH.window_for("daymet")
    st = SH.stations().set_index("id")
    hs = pd.read_parquet(V.OUT / "validation_by_station.parquet")
    e3 = hs[hs.estimator == "E3"].set_index(["station_id", "season"])
    rows = []
    for tr, te in tqdm(list(GroupKFold(n_splits=n_folds).split(T, groups=T.station_id)), desc="shape folds"):
        model = lgb.LGBMRegressor(**PARAMS).fit(T.iloc[tr][FEATURES], T.iloc[tr]["target"])
        for sid in T.iloc[te].station_id.unique():
            s = st.loc[sid]
            dm = V.daymet_pixel(sid)
            for (sid2, y) in [k for k in e3.index if k[0] == sid]:
                if y > C.LAST_COMPLETE_DAYMET_SEASON:
                    continue
                shape = _shape_series(model, float(s.lat), dm, y, win)
                hrs = V.b_hours(float(s.lat), dm, y, [shape], win)
                truth = V.daily_cum(V.season_hourly(SH.station_hourly(sid), y))
                m, tm = V.metrics(V.daily_cum(hrs), y), V.metrics(truth, y)
                rows.append({"station_id": sid, "season": y, "err_feb1": m["cp_feb1"] - tm["cp_feb1"],
                             "err_mar1": m["cp_mar1"] - tm["cp_mar1"]})
    R = pd.DataFrame(rows)
    R.to_parquet(V.OUT / "ml_shape_hidden.parquet", index=False)
    R = R.set_index(["station_id", "season"])
    by = {e: hs[hs.estimator == e].set_index(["station_id", "season"]) for e in ("E2", "E3", "E4")}
    common = R.index
    for d in by.values():
        common = common.intersection(d.index)
    errs = lambda d: pd.concat([d.err_feb1, d.err_mar1])  # noqa: E731
    out = {"n": int(len(common))}
    for name, d in (("ml_shape", R), *[(k, v) for k, v in by.items()]):
        e = errs(d.loc[common])
        out[name] = {"mae": round(float(e.abs().mean()), 3), "p80": round(float(e.abs().quantile(0.8)), 3), "bias": round(float(e.mean()), 3)}
    out["method_b_mae"] = out["E3"]["mae"]
    out["ml_shape_mae"] = out["ml_shape"]["mae"]
    out["ship"] = out["ml_shape_mae"] < out["method_b_mae"]
    # Final model on every station, for production use in the no-station-record fallback.
    model = lgb.LGBMRegressor(**PARAMS).fit(T[FEATURES], T["target"])
    mdir = C.PROCESSED_DIR / "models"
    mdir.mkdir(parents=True, exist_ok=True)
    model.booster_.save_model(str(mdir / "ml_shape.txt"))
    (V.OUT / "ml_shape_summary.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    run()
