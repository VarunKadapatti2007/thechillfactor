"""Phase 1 station store.

    python -m chillprint.pipeline.build_station_store stations
    python -m chillprint.pipeline.build_station_store fnric
    python -m chillprint.pipeline.build_station_store wildeye
    python -m chillprint.pipeline.build_station_store daymet
    python -m chillprint.pipeline.build_station_store cimis [--backfill]
    python -m chillprint.pipeline.build_station_store qc
    python -m chillprint.pipeline.build_station_store all

Every remote response is cached (data/cache), so a rerun makes zero network calls.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, timedelta

import numpy as np
import pandas as pd
from tqdm import tqdm

from .. import config as C
from ..sources import cache, cimis, daymet, elevation, fnric

P = C.PROCESSED_DIR
STATIONS_PQ = P / "stations.parquet"
FNRIC_PQ = P / "fnric_daily_chill.parquet"
WILDEYE_PQ = P / "wildeye_hourly.parquet"
DAYMET_DIR = P / "daymet"
HOURLY_DIR = P / "cimis_hourly"
QC_JSON = P / "qc_report.json"


# --- 1. stations ---------------------------------------------------------------

def build_stations() -> pd.DataFrame:
    f = fnric.stations()
    c = cimis.stations()
    m = f.merge(c[["id", "nbr", "elev_m", "connect_date", "disconnect_date", "active"]].rename(
        columns={"connect_date": "cimis_connect", "active": "cimis_active"}), on="id", how="left")
    m["connect_date"] = m["cimis_connect"].fillna(m["connect_date"])
    m["active"] = np.where(m["cimis_active"].notna(), m["cimis_active"], m["active"]).astype(bool)
    m = m.drop(columns=["cimis_connect", "cimis_active"])
    # CIMIS disconnect date 12/31/2050 means "still running".
    m["disconnect_date"] = m["disconnect_date"].where(m["disconnect_date"] < date(2050, 1, 1))
    m["closed"] = [d.strftime("%Y-%m") if (isinstance(d, date) and not a) else None
                   for d, a in zip(m["disconnect_date"], m["active"])]
    # Wildeye has no county or elevation in either list: look up elevation (cached).
    for i in m.index[m["elev_m"].isna()]:
        m.at[i, "elev_m"] = elevation.elevation_m(m.at[i, "lat"], m.at[i, "lon"])
    m["central_valley"] = m["county"].isin(C.CENTRAL_VALLEY_COUNTIES)
    m["nbr"] = m["nbr"].astype("Int64")
    m.to_parquet(STATIONS_PQ, index=False)
    print(f"stations: {len(m)} total, {int((m.network == 'CIMIS').sum())} CIMIS, "
          f"{int((m.network == 'Wildeye').sum())} Wildeye, {int(m.central_valley.sum())} Central Valley CIMIS")
    return m


def load_stations() -> pd.DataFrame:
    if not STATIONS_PQ.exists():
        return build_stations()
    return pd.read_parquet(STATIONS_PQ)


def cv_cimis(st: pd.DataFrame) -> pd.DataFrame:
    return st[(st.network == "CIMIS") & st.central_valley].copy()


def wildeye_stations(st: pd.DataFrame) -> pd.DataFrame:
    return st[st.network == "Wildeye"].copy()


# --- 2. FNRIC daily chill --------------------------------------------------------

def build_fnric(st: pd.DataFrame) -> pd.DataFrame:
    ids = list(cv_cimis(st).id) + list(wildeye_stations(st).id)
    frames = []
    for sid in tqdm(ids, desc="fnric chill"):
        try:
            df = fnric.chill_download(sid)
        except Exception as e:  # keep going; log
            print(f"  {sid}: {e}", file=sys.stderr)
            continue
        if df.empty:
            continue
        df.insert(0, "station_id", sid)
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out.to_parquet(FNRIC_PQ, index=False)
    print(f"fnric: {out.station_id.nunique()} stations, {len(out)} daily rows")
    return out


# --- 4. Wildeye raw ------------------------------------------------------------------

def wildeye_to_pst(df: pd.DataFrame) -> pd.DataFrame:
    """Wildeye date/hour are local Pacific with DST. Convert to PST (UTC-8) hour stamps."""
    if df.empty:
        return df
    local = pd.to_datetime(df["date"]) + pd.to_timedelta(df["hour"], unit="h")
    aware = local.dt.tz_localize("America/Los_Angeles", ambiguous="NaT", nonexistent="NaT")
    keep = aware.notna()
    pst = aware[keep].dt.tz_convert("Etc/GMT+8").dt.tz_localize(None)
    out = pd.DataFrame({
        "ts": pst.to_numpy(),
        "t_f": pd.to_numeric(df.loc[keep, "Air Temperature"], errors="coerce").to_numpy(),
        "srad": pd.to_numeric(df.loc[keep, "Solar radiation"], errors="coerce").to_numpy()
        if "Solar radiation" in df else np.nan,
        "rh": pd.to_numeric(df.loc[keep, "Relative Humidity"], errors="coerce").to_numpy()
        if "Relative Humidity" in df else np.nan,
    })
    return out.dropna(subset=["ts"]).sort_values("ts").drop_duplicates("ts")


# One request per site per chill season (a multi-year request times out upstream with 503).
# The window is in UTC upstream, so start a day early to cover Sept 1 00:00 PST.
WILDEYE_SEASONS = (2023, 2024, 2025)


def build_wildeye(st: pd.DataFrame) -> pd.DataFrame:
    frames = []
    jobs = [(s, y) for _, s in wildeye_stations(st).iterrows() for y in WILDEYE_SEASONS]
    for s, y in tqdm(jobs, desc="wildeye"):
        if isinstance(s.connect_date, date) and s.connect_date > date(y + 1, 3, 1):
            continue
        try:
            raw = fnric.wildeye_raw(s.id, date(y, 8, 31), date(y + 1, 3, 31))
        except Exception as e:
            print(f"  {s.id} {y}: {e}", file=sys.stderr)
            continue
        df = wildeye_to_pst(raw)
        if df.empty:
            continue
        df.insert(0, "station_id", s.id)
        frames.append(df)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    out["t_c"] = (out["t_f"] - 32) * 5 / 9
    # sanity: drop physically implausible air temperatures
    out.loc[(out.t_c < -25) | (out.t_c > 52), "t_c"] = np.nan
    out.to_parquet(WILDEYE_PQ, index=False)
    print(f"wildeye: {out.station_id.nunique()} stations, {len(out)} hourly rows, "
          f"{out.ts.min()} .. {out.ts.max()}")
    return out


# --- 5. Daymet at station pixels and demo pins ----------------------------------------

def daymet_path(key: str):
    return DAYMET_DIR / f"{key}.parquet"


def build_daymet(st: pd.DataFrame) -> None:
    DAYMET_DIR.mkdir(parents=True, exist_ok=True)
    targets = [(r.id, r.lat, r.lon) for r in pd.concat([cv_cimis(st), wildeye_stations(st)]).itertuples()]
    targets += [(f"pin_{p.id}", p.lat, p.lon) for p in C.DEMO_PINS]
    meta = {}
    for key, lat, lon in tqdm(targets, desc="daymet"):
        out = daymet_path(key)
        try:
            df, m = daymet.daily(lat, lon)
        except Exception as e:
            print(f"  {key}: {e}", file=sys.stderr)
            continue
        meta[key] = {"lat": lat, "lon": lon, **m}
        if not out.exists():
            df.to_parquet(out)
    (DAYMET_DIR / "_meta.json").write_text(json.dumps(meta, indent=1))
    print(f"daymet: {len(meta)} of {len(targets)} pixels cached")


# --- 3. CIMIS hourly -------------------------------------------------------------------

def season_months(start_year: int) -> list[tuple[int, int]]:
    return [(start_year, m) for m in (9, 10, 11, 12)] + [(start_year + 1, m) for m in (1, 2, 3)]


def station_seasons(s, first: int, last: int) -> list[int]:
    out = []
    for y in range(first, last + 1):
        s0, s1 = date(y, 9, 1), date(y + 1, 3, 31)
        if isinstance(s.connect_date, date) and s.connect_date > s1:
            continue
        if isinstance(s.disconnect_date, date) and s.disconnect_date < s0:
            continue
        out.append(y)
    return out


def hourly_path(sid: str, season: int):
    return HOURLY_DIR / f"station={sid}" / f"season={season}.parquet"


def pull_station_season(s, season: int, today: date) -> dict:
    """Pull (or read from cache) one station-season and write its parquet. Returns QC counts."""
    frames, qc_counts = [], {"t_c": 0, "srad": 0, "rh": 0, "t_c_phys": 0}
    for (y, m) in season_months(season):
        if date(y, m, 1) >= today:
            continue
        live = (y, m) == (today.year, today.month)
        try:
            raw = cimis.fetch_month_raw(int(s.nbr), y, m, live=live)
            df = cimis.parse_month(raw)
            src = "cimis"
        except Exception as e:  # CIMIS refused or failed: try the Synoptic backup if configured
            df, src = _synoptic_month(s, y, m), "synoptic"
            if df is None:
                raise
            print(f"  {s.id} {y}-{m:02d}: CIMIS failed ({str(e)[:80]}); used Synoptic", file=sys.stderr)
        if df.empty:
            continue
        if src == "cimis":
            df, cnt = cimis.apply_qc(df)
            for k, v in cnt.items():
                qc_counts[k] += v
        df["source"] = src
        frames.append(df)
    out = hourly_path(s.id, season)
    out.parent.mkdir(parents=True, exist_ok=True)
    if frames:
        df = pd.concat(frames, ignore_index=True).sort_values("ts").drop_duplicates("ts")
        df.to_parquet(out, index=False)
        n = int(df["t_c"].notna().sum())
    else:
        pd.DataFrame(columns=["ts", "cimis_date", "hour", "t_c", "t_qc", "srad", "srad_qc", "rh", "rh_qc"]).to_parquet(out, index=False)
        n = 0
    return {"station": s.id, "season": season, "hours": n, **{f"qc_{k}": v for k, v in qc_counts.items()}}


def _synoptic_month(s, y: int, m: int):
    from ..sources import synoptic
    if not synoptic.token():
        return None
    stid = synoptic.match_station(s.id, float(s.lat), float(s.lon))
    if not stid:
        return None
    df = synoptic.month_hourly(stid, y, m)
    for c in ("cimis_date", "hour", "t_qc", "srad_qc", "rh_qc"):
        df[c] = None
    df.loc[(df.t_c < -30) | (df.t_c > 55), "t_c"] = np.nan
    return df


def build_cimis(st: pd.DataFrame, first: int, last: int, stations: list[str] | None = None) -> pd.DataFrame:
    if not C.cimis_key():
        raise SystemExit("CIMIS_APP_KEY missing from .env; hourly pull skipped")
    today = date.today()
    cv = cv_cimis(st)
    if stations:
        cv = cv[cv.id.isin(stations)]
    # Durham first (hero case), Davis second (GATE 2 test), then by station number.
    cv = cv.assign(_o=cv.id.map({C.DURHAM_ID: 0, "CIMIS-6": 1}).fillna(2)).sort_values(["_o", "nbr"])
    jobs = [(s, y) for s in cv.itertuples() for y in station_seasons(s, first, last)]
    log = []
    for s, y in tqdm(jobs, desc=f"cimis {first}-{last}"):
        try:
            log.append(pull_station_season(s, y, today))
        except Exception as e:
            print(f"  {s.id} {y}: {e}", file=sys.stderr)
            time.sleep(5)
    df = pd.DataFrame(log)
    tag = f"{first}_{last}"
    df.to_csv(P / f"cimis_pull_log_{tag}.csv", index=False)
    return df


# --- 7. QC report --------------------------------------------------------------------

def season_coverage(df: pd.DataFrame, season: int) -> float:
    """Share of hours present from Sept 1 through Mar 1 (BUILD.md 5.1)."""
    s0 = pd.Timestamp(season, 9, 1, 1)
    s1 = pd.Timestamp(season + 1, 3, 2, 0)
    expected = int((s1 - s0) / pd.Timedelta(hours=1)) + 1
    if df.empty:
        return 0.0
    m = (df.ts >= s0) & (df.ts <= s1) & df.t_c.notna()
    return float(m.sum()) / expected


def longest_gap_hours(df: pd.DataFrame, season: int) -> int:
    s0 = pd.Timestamp(season, 9, 1, 1)
    s1 = pd.Timestamp(season + 1, 3, 2, 0)
    idx = pd.date_range(s0, s1, freq="h")
    t = df.set_index("ts")["t_c"].reindex(idx)
    isna = t.isna().to_numpy()
    best = run = 0
    for v in isna:
        run = run + 1 if v else 0
        best = max(best, run)
    return best


def build_qc(st: pd.DataFrame) -> dict:
    rows = []
    for p in sorted(HOURLY_DIR.glob("station=*/season=*.parquet")):
        sid = p.parent.name.split("=")[1]
        season = int(p.stem.split("=")[1])
        df = pd.read_parquet(p)
        if len(df):
            df["ts"] = pd.to_datetime(df["ts"])
        rows.append({"station_id": sid, "season": season, "coverage": season_coverage(df, season),
                     "longest_gap_h": longest_gap_hours(df, season) if len(df) else None,
                     "n_hours": int(df["t_c"].notna().sum()) if len(df) else 0,
                     "qc_dropped": int((df["t_c"].isna() & df["t_qc"].notna()).sum()) if len(df) else 0})
    cov = pd.DataFrame(rows)
    cov.to_parquet(P / "hourly_coverage.parquet", index=False)
    complete = cov[cov.coverage >= 0.95]
    per_station = complete[complete.season <= C.current_season() - 1].groupby("station_id").size()
    rep = {
        "station_seasons": int(len(cov)),
        "complete_station_seasons": int(len(complete)),
        "stations_with_10plus_complete_winters": int((per_station >= 10).sum()),
        "durham_complete_winters": int(per_station.get(C.DURHAM_ID, 0)),
        "qc_values_dropped": int(cov.qc_dropped.sum()),
        "median_coverage": float(cov.coverage.median()) if len(cov) else None,
    }
    QC_JSON.write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["stations", "fnric", "wildeye", "daymet", "cimis", "qc", "all"])
    ap.add_argument("--first", type=int, default=C.VALIDATION_FIRST_SEASON)
    ap.add_argument("--last", type=int, default=None)
    ap.add_argument("--backfill", action="store_true", help="pull 1982-83..2004-05 winters")
    ap.add_argument("--stations", nargs="*")
    a = ap.parse_args(argv)
    t0 = time.time()
    n0 = cache.NETWORK_CALLS["count"]
    st = build_stations() if a.step in ("stations", "all") else load_stations()
    if a.step in ("fnric", "all"):
        build_fnric(st)
    if a.step in ("wildeye", "all"):
        build_wildeye(st)
    if a.step in ("daymet", "all"):
        build_daymet(st)
    if a.step in ("cimis", "all"):
        last = a.last if a.last is not None else C.current_season()
        if a.backfill:
            build_cimis(st, 1982, C.VALIDATION_FIRST_SEASON - 1, a.stations)
        else:
            build_cimis(st, a.first, last, a.stations)
    if a.step in ("qc", "all"):
        build_qc(st)
    print(f"done in {time.time() - t0:.1f}s; network calls this run: {cache.NETWORK_CALLS['count'] - n0}")


if __name__ == "__main__":
    main()
