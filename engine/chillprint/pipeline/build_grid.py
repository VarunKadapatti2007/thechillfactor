"""Summary grid over the Central Valley and foothills (BUILD.md Phase 4 step 5).

Roughly 4 km spacing inside a valley-and-foothills outline, keeping points with
Daymet elevation under 600 m. For each point: CP at each by date for every
winter 1980-81 .. 2024-25 (default history method), safe winter chill (P10).
"Chill so far" for the live season uses E4 when station hourly is available.
Resumable: finished points are kept in grid/points.parquet. The app works without it.

    python -m chillprint.pipeline.build_grid [--step 0.036] [--max N]
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .. import config as C
from ..science import chill
from ..sources import daymet
from . import station_hourly as SH
from .build_pin import _daymet_station, monthly_offset, offset_hourly, rebuild_record, season_stamps

GRID_DIR = C.PROCESSED_DIR / "grid"
GRID_DIR.mkdir(parents=True, exist_ok=True)
POINTS = GRID_DIR / "points.parquet"

# Valley floor plus the lower foothills, clockwise from Redding.
OUTLINE = [
    (40.75, -122.45), (40.60, -121.95), (39.90, -121.60), (39.20, -121.00), (38.60, -120.90),
    (37.90, -120.50), (37.30, -119.85), (36.80, -119.10), (36.20, -118.85), (35.50, -118.75),
    (35.05, -118.90), (34.95, -119.30), (35.20, -119.65), (35.80, -120.20), (36.30, -120.60),
    (36.90, -121.00), (37.50, -121.40), (38.00, -121.80), (38.40, -122.15), (39.00, -122.35),
    (39.80, -122.50), (40.30, -122.55),
]
BY_DATES = ("02-01", "02-15", "03-01")


def inside(lat: float, lon: float) -> bool:
    """Ray casting point-in-polygon on (lat, lon)."""
    n = len(OUTLINE)
    ins = False
    j = n - 1
    for i in range(n):
        yi, xi = OUTLINE[i]
        yj, xj = OUTLINE[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-12) + xi):
            ins = not ins
        j = i
    return ins


def candidates(step_lat: float) -> list[tuple[float, float]]:
    step_lon = step_lat * 1.25
    lats = np.arange(34.9, 40.8, step_lat)
    lons = np.arange(-122.6, -118.7, step_lon)
    return [(round(float(a), 4), round(float(b), 4)) for a in lats for b in lons if inside(a, b)]


def point_values(lat: float, lon: float) -> dict | None:
    dm, meta = daymet.daily(lat, lon)
    elev = meta.get("elev_m")
    if elev is None or elev >= 600:
        return {"lat": lat, "lon": lon, "elev_m": elev, "skip": True}
    win = SH.window_for("daymet")
    cps = {b: [] for b in BY_DATES}
    rec, _ = rebuild_record(lat, lon, dm, win)
    for y in range(C.FIRST_SEASON, C.LAST_COMPLETE_DAYMET_SEASON + 1):
        arr = rec.reindex(season_stamps(y)).interpolate(limit_direction="both").to_numpy()
        cum = np.cumsum(chill.dynamic_portions(arr)[0])[23::24]
        for b in BY_DATES:
            k = (C.by_date(y, b) - date(y, 9, 1)).days
            cps[b].append(float(cum[k]))
    out = {"lat": lat, "lon": lon, "elev_m": elev, "skip": False}
    for b in BY_DATES:
        v = np.array(cps[b])
        out[f"safe_{b.replace('-', '')}"] = float(np.percentile(v, 10)) if len(v) else np.nan
    out["chill_so_far"] = _chill_so_far(lat, lon, dm)
    return out


def _chill_so_far(lat, lon, dm) -> float:
    y = C.current_season()
    near = SH.nearest_cimis(lat, lon, with_hourly=True, season=y, k=1)
    if near.empty:
        return np.nan
    r = near.iloc[0]
    st = SH.station_hourly(r["id"])
    stamps = season_stamps(y)
    last = pd.Timestamp(date.today() - timedelta(days=1)) + pd.Timedelta(days=1)
    seg = st.reindex(stamps[stamps <= last])
    if seg.notna().mean() < 0.9:
        return np.nan
    off = monthly_offset(dm, _daymet_station(r["id"], r["lat"], r["lon"]))
    e4 = offset_hourly(seg.interpolate(limit_direction="both"), off)
    return float(chill.dynamic_portions(e4.to_numpy())[0].sum())


def write_layers(df: pd.DataFrame) -> None:
    df = df[~df.skip]
    for _, v in C.all_varieties():
        col = f"safe_{v.by_date_default.replace('-', '')}"
        for layer, c in (("safe_chill", col), ("chill_so_far", "chill_so_far")):
            sub = df[np.isfinite(df[c])]
            if sub.empty:
                continue
            fc = {"type": "FeatureCollection", "layer": layer, "variety": v.id,
                  "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [r.lon, r.lat]},
                                "properties": {"value": round(float(getattr(r, c)), 1)}} for r in sub.itertuples()],
                  "sources": [C.SOURCES["daymet"], C.SOURCES["cimis"]],
                  "method": f"{'P10 of CP by ' + v.by_date_default + ', winters 1980-81 to 2024-25' if layer == 'safe_chill' else 'E4 chill so far'}"}
            (GRID_DIR / f"{layer}_{v.id}.json").write_text(json.dumps(fc, separators=(",", ":")), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=float, default=0.036)
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--fetch-only", action="store_true", help="only cache Daymet for every candidate")
    a = ap.parse_args()
    pts = candidates(a.step)
    if a.fetch_only:
        t0 = time.time()
        for i, (lat, lon) in enumerate(pts):
            try:
                daymet.fetch_raw(lat, lon)
            except Exception as e:
                print(f"  {lat},{lon}: {e}")
            if (i + 1) % 100 == 0:
                print(f"  fetched {i + 1}/{len(pts)} in {time.time() - t0:.0f}s")
        return
    done = pd.read_parquet(POINTS) if POINTS.exists() else pd.DataFrame(columns=["lat", "lon"])
    have = set(zip(done.lat.round(4), done.lon.round(4)))
    todo = [p for p in pts if p not in have]
    if a.max:
        todo = todo[: a.max]
    print(f"grid: {len(pts)} candidates, {len(have)} done, {len(todo)} to do")
    rows = [] if done.empty else done.to_dict("records")
    t0 = time.time()
    for i, (lat, lon) in enumerate(todo):
        try:
            v = point_values(lat, lon)
        except Exception as e:
            print(f"  {lat},{lon}: {e}")
            continue
        rows.append(v)
        if (i + 1) % 25 == 0 or i == len(todo) - 1:
            df = pd.DataFrame(rows)
            df.to_parquet(POINTS, index=False)
            write_layers(df)
            print(f"  {i + 1}/{len(todo)} in {time.time() - t0:.0f}s")
    if rows:
        write_layers(pd.DataFrame(rows))


if __name__ == "__main__":
    main()
