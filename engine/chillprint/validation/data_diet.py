"""Data-diet test (BUILD.md 5.5).

Take complete station-seasons, delete 0-50% of days (scattered, or in blocks of
3, 7, 14 days), fill daily min/max by straight lines, rebuild hours with
Method B (nearest other station's shape, or Method L in keyless mode) and
compare CP by Mar 1 with the full-hourly truth. The 0% row is the cost of
having only one daily reading (E5).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from tqdm import tqdm

from .. import config as C
from ..pipeline import station_hourly as SH
from . import common as V

FRACTIONS = (0, 5, 10, 20, 30, 40, 50)
BLOCKS = (1, 3, 7, 14)
REPS = 3


def _mask(n: int, frac: float, block: int, rng: np.random.Generator) -> np.ndarray:
    """Boolean mask of deleted days (never the first/last day so interpolation has anchors)."""
    m = np.zeros(n, dtype=bool)
    target = int(round(n * frac / 100))
    tries = 0
    while m.sum() < target and tries < 10000:
        tries += 1
        s = int(rng.integers(1, max(2, n - block - 1)))
        m[s:s + block] = True
    m[0] = m[-1] = False
    return m


def _longest(m: np.ndarray) -> int:
    best = run = 0
    for v in m:
        run = run + 1 if v else 0
        best = max(best, run)
    return best


def sample_station_seasons(max_n: int = 160, seed: int = C.SEED) -> list[tuple[str, int, str]]:
    """(station id, season, source) pairs with complete hourly truth. Uses Wildeye when no CIMIS hourly."""
    rng = np.random.default_rng(seed)
    if SH.hourly_index():
        cs = sorted(V.complete_set())
        cs = [(s, y, "cimis") for s, y in cs if y <= C.LAST_COMPLETE_DAYMET_SEASON + 1]
    else:
        cs = []
        for s in SH.stations()[SH.stations().network == "Wildeye"].id:
            h = SH.wildeye_hourly(s)
            for y in (2023, 2024, 2025):
                if not h.empty and V.coverage(h, y) >= V.MIN_COVERAGE:
                    cs.append((s, y, "wildeye"))
    if len(cs) > max_n:
        idx = rng.choice(len(cs), size=max_n, replace=False)
        cs = [cs[i] for i in sorted(idx)]
    return cs


def run(max_n: int = 160) -> pd.DataFrame:
    win = SH.window_for("daymet")
    st = SH.stations().set_index("id")
    rng = np.random.default_rng(C.SEED)
    rows = []
    for sid, y, src in tqdm(sample_station_seasons(max_n), desc="data diet"):
        h = SH.station_hourly(sid) if src == "cimis" else SH.wildeye_hourly(sid)
        s = st.loc[sid]
        truth = V.daily_cum(V.season_hourly(h, y))
        t_mar1 = truth[V.dos(y, "03-01")]
        own = V.own_window_daily(h, y, win)
        if own.loc[f"{y}-09-01":f"{y + 1}-03-01"].isna().any().any():
            own = own.interpolate(limit_direction="both")
        nb = SH.nearest_cimis(s.lat, s.lon, exclude=(sid,), with_hourly=True, season=y, k=2)
        shapes = [SH.station_hourly(i) for i in nb.id]
        n = len(own)
        for frac in FRACTIONS:
            for block in BLOCKS:
                reps = 1 if frac == 0 else REPS
                for r in range(reps):
                    if frac == 0 and block > 1:
                        continue
                    m = _mask(n, frac, block, rng) if frac else np.zeros(n, dtype=bool)
                    d = own.copy()
                    d.loc[m, ["tmin", "tmax"]] = np.nan
                    d = d.interpolate(limit_direction="both")
                    if shapes:
                        hrs = V.b_hours(s.lat, d, y, shapes, win)
                    else:
                        from ..science.hourly import linvill_series
                        from ..pipeline.build_pin import season_stamps
                        hrs = linvill_series(s.lat, d).reindex(season_stamps(y)).interpolate(limit_direction="both").to_numpy()
                    cp = V.daily_cum(hrs)[V.dos(y, "03-01")]
                    rows.append({"station_id": sid, "season": y, "source": src, "missing_pct": frac,
                                 "block": block, "rep": r, "actual_pct": float(m.mean() * 100),
                                 "longest_gap": _longest(m), "err": float(cp - t_mar1)})
    df = pd.DataFrame(rows)
    df.to_parquet(V.OUT / "data_diet.parquet", index=False)
    return df


def summarize(df: pd.DataFrame) -> tuple[list[dict], str | None]:
    """Curve rows for the API, plus the plain rule derived from the data (P80 abs error under 2 CP)."""
    curve = []
    base0 = df[df.missing_pct == 0]
    for block in BLOCKS:
        for frac in FRACTIONS:
            sub = base0 if frac == 0 else df[(df.missing_pct == frac) & (df.block == block)]
            if len(sub):
                curve.append({"missing_pct": float(frac), "gap_days": float(block),
                              "mae_cp": round(float(sub.err.abs().mean()), 2),
                              "p80_cp": round(float(sub.err.abs().quantile(0.8)), 2)})
    rnd = [c for c in curve if c["gap_days"] == 1]
    ok_pct = [c["missing_pct"] for c in rnd if c["p80_cp"] < 2.0]
    n_pct = None
    for c in sorted(rnd, key=lambda c: c["missing_pct"]):  # largest fraction before the first failure
        if c["p80_cp"] < 2.0:
            n_pct = c["missing_pct"]
        else:
            break
    by_gap = df.groupby("longest_gap").err.apply(lambda e: e.abs().quantile(0.8))
    k_days = None
    for g in sorted(by_gap.index):
        if g == 0:
            continue
        if by_gap[g] < 2.0:
            k_days = int(g)
        else:
            break
    if base0.err.abs().quantile(0.8) >= 2.0:
        rule = (f"Even with no gaps, one daily reading misses by up to {base0.err.abs().quantile(0.8):.1f} CP "
                f"in 8 of 10 winters, so no gap rule keeps error under 2 CP here.")
    elif n_pct is not None and k_days is not None:
        rule = f"Up to {int(n_pct)}% missing days, or gaps up to {k_days} days, keeps error under 2 CP in 8 of 10 winters."
    else:
        rule = None
    _ = ok_pct
    return curve, rule


if __name__ == "__main__":
    d = run()
    print(summarize(d))
