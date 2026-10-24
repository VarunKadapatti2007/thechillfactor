"""Generate web/mocks/*.json for development against the API contract.

Every file carries "mock": true. These numbers are not real and must never
reach production paths (GATE 5 greps the build for "mock": true).
"""
import datetime as dt
import json
import random
import sys
from pathlib import Path

random.seed(7)
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "web" / "mocks")
OUT.mkdir(parents=True, exist_ok=True)


def d(s):
    return dt.date.fromisoformat(s)


def series(start, end, rate, onset):
    res, cp, day = [], 0.0, d(start)
    while day <= d(end):
        if day >= d(onset):
            cp += max(0, rate + random.gauss(0, 0.25))
        res.append({"date": day.isoformat(), "cp": round(cp, 2)})
        day += dt.timedelta(days=1)
    return res


crops = {"mock": True, "crops": [
    {"id": "almond", "name": "Almond", "icon": "TreeDeciduous", "varieties": [
        {"id": "nonpareil", "name": "Nonpareil", "need_low": 22, "need_high": 23, "by_date_default": "02-01"},
        {"id": "desmayo-largueta", "name": "Desmayo Largueta", "need_low": 28, "need_high": 28, "by_date_default": "02-01"},
        {"id": "ferragnes", "name": "Ferragnes", "need_low": 32, "need_high": 32, "by_date_default": "02-01"}]},
    {"id": "pistachio", "name": "Pistachio", "icon": "Nut", "varieties": [
        {"id": "kerman", "name": "Kerman", "need_low": 54, "need_high": 58, "by_date_default": "03-01"},
        {"id": "peters", "name": "Peters", "need_low": 60, "need_high": 65, "by_date_default": "03-01"}]},
    {"id": "walnut", "name": "Walnut", "icon": "TreeDeciduous", "varieties": [
        {"id": "chandler", "name": "Chandler", "need_low": 45, "need_high": 50, "by_date_default": "03-01"}]},
    {"id": "prune", "name": "Prune", "icon": "TreeDeciduous", "varieties": [
        {"id": "improved-french", "name": "Improved French", "need_low": 55, "need_high": 60, "by_date_default": "03-01"}]},
    {"id": "cherry", "name": "Cherry", "icon": "Cherry", "varieties": [
        {"id": "brooks", "name": "Brooks", "need_low": 37, "need_high": 37, "by_date_default": "02-15"}]},
    {"id": "apple", "name": "Apple", "icon": "Apple", "varieties": [
        {"id": "golden-delicious", "name": "Golden Delicious", "need_low": 50, "need_high": 50, "by_date_default": "03-01"}]}],
    "source": "UCCE, K. Pope", "sources": ["mock"], "method": "config"}

stations = {"mock": True, "stations": [
    {"id": "CIMIS-12", "name": "Durham", "network": "CIMIS", "lat": 39.6086, "lon": -121.8244, "elev_m": 40, "active": False, "closed": "2025-07"},
    {"id": "CIMIS-6", "name": "Davis", "network": "CIMIS", "lat": 38.5357, "lon": -121.7764, "elev_m": 18, "active": True, "closed": None},
    {"id": "CIMIS-39", "name": "Parlier", "network": "CIMIS", "lat": 36.5974, "lon": -119.504, "elev_m": 103, "active": True, "closed": None},
    {"id": "CIMIS-5", "name": "Shafter", "network": "CIMIS", "lat": 35.5326, "lon": -119.2818, "elev_m": 110, "active": True, "closed": None},
    {"id": "CIMIS-2", "name": "FivePoints", "network": "CIMIS", "lat": 36.3362, "lon": -120.1129, "elev_m": 87, "active": True, "closed": None},
    {"id": "Wildeye-111086", "name": "CA Pistachio # 5 - Terra Bella", "network": "Wildeye", "lat": 35.9599, "lon": -119.0664, "elev_m": None, "active": True, "closed": None}],
    "sources": ["mock"], "method": "mock"}

cur = series("2014-09-01", "2015-01-15", 0.42, "2014-10-20")
past = []
for y in range(1980, 2025):
    if y == 2014:
        continue
    s = series(f"{y}-09-01", f"{y + 1}-03-31", random.uniform(0.35, 0.6), f"{y}-10-{random.randint(10, 30)}")
    past.append({"season": f"{y}-{y + 1}", "series": s[::2]})
fan, p = [], cur[-1]["cp"]
day, k = d("2015-01-16"), 0
while day <= d("2015-03-01"):
    k += 1
    m = p + 0.38 * k
    fan.append({"date": day.isoformat(), "p10": round(m - 0.08 * k, 2), "p50": round(m, 2), "p90": round(m + 0.08 * k, 2)})
    day += dt.timedelta(days=1)

point = {"mock": True,
         "location": {"lat": 35.52, "lon": -119.30, "elev_m": 110, "nearest_station": {"id": "CIMIS-5", "name": "Shafter", "dist_km": 2.4}},
         "season": "2014-2015", "asof": "2015-01-15", "start": "sep1", "method": "E3",
         "chill": {"to_date": cur[-1]["cp"], "error_cp": 3.1, "series": cur},
         "need": {"low": 54, "high": 58, "by": "2015-03-01"},
         "outlook": {"p10": fan[-1]["p10"], "p50": fan[-1]["p50"], "p90": fan[-1]["p90"], "chance_low": 0.3,
                     "chance_high": 0.1, "n_analogs": 44, "fan": fan},
         "past_seasons": past, "closest": {"season": "2013-2014", "rmse_cp": 1.8},
         "verdict": {"level": "amber", "label": "Watch", "sentence": "3 in 10 similar winters reached Kerman's 54 CP by Mar 1.", "early": False},
         "flags": {"sunny_stretch": None, "data_gaps_days": 0}, "sources": ["mock"]}

winters = []
for y in range(1980, 2026):
    cp = round(random.gauss(60 - 0.12 * (y - 1980), 7), 1)
    winters.append({"season": f"{y}-{y + 1}", "cp_by": cp, "met_low": cp >= 54, "met_high": cp >= 58, "filled": y == 2025})
history = {"mock": True, "winters": winters,
           "share_met_low": round(sum(w["met_low"] for w in winters) / len(winters), 3),
           "share_met_high": round(sum(w["met_high"] for w in winters) / len(winters), 3),
           "trend": {"cp_per_decade": -1.2, "ci90": [-2.4, -0.1], "p_value": 0.07, "label": "likely decline"},
           "safe_chill": {"early": {"years": "1981-2000", "p10": 52.1, "ci": [47.0, 55.3]},
                          "recent": {"years": "2006-2025", "p10": 47.8, "ci": [42.2, 51.0]},
                          "today_replay": {"p10": 46.9, "p50": 55.0}},
           "links": [{"title": "UC ANR Projected Winter Chill", "url": "https://ucanr.edu/"}, {"title": "Cal-Adapt", "url": "https://cal-adapt.org/"}],
           "sources": ["mock"], "method": "E3"}

frames, cp = [], 0.0
day = d("2014-09-01")
while day <= d("2015-03-01"):
    if day >= d("2014-10-20"):
        cp += 0.42
    frac = (day - d("2014-09-01")).days / 181
    p50 = cp + (1 - frac) * 35
    ch = max(0, min(1, (p50 - 50) / 12))
    frames.append({"date": day.isoformat(), "cp": round(cp, 2), "p10": round(p50 - 6 * (1 - frac), 2), "p50": round(p50, 2),
                   "p90": round(p50 + 6 * (1 - frac), 2), "chance_low": round(ch, 2),
                   "level": "green" if ch > 0.9 else ("red" if p50 < 54 else "amber")})
    day += dt.timedelta(days=1)
replay = {"mock": True, "season": "2014-2015", "frames": frames, "actual_final_cp": round(cp, 2), "sources": ["mock"], "method": "E3"}

validation = {"mock": True, "n_stations": 41, "n_station_seasons": 612,
              "estimators": [
                  {"id": "E0", "name": "Nearest station", "mae_cp": 4.8, "p80_cp": 7.1, "bias_cp": 0.4},
                  {"id": "E1", "name": "3-station average", "mae_cp": 4.1, "p80_cp": 6.2, "bias_cp": 0.2},
                  {"id": "E2", "name": "Daymet + textbook curve", "mae_cp": 5.6, "p80_cp": 8.0, "bias_cp": -2.1},
                  {"id": "E3", "name": "Daymet + borrowed shape", "mae_cp": 3.4, "p80_cp": 5.0, "bias_cp": -0.6},
                  {"id": "E4", "name": "Station + Daymet offset", "mae_cp": 3.2, "p80_cp": 4.7, "bias_cp": 0.1},
                  {"id": "E5", "name": "One reading a day", "mae_cp": 1.3, "p80_cp": 1.9, "bias_cp": 0.0}],
              "wildeye": {"n_stations": 18, "estimators": [{"id": "E0", "mae_cp": 6.2}, {"id": "E3", "mae_cp": 4.4}, {"id": "E4", "mae_cp": 4.1}]},
              "durham": {"winters": [{"season": f"{y}-{y + 1}", "truth": round(55 + random.gauss(0, 6), 1), "e0": round(55 + random.gauss(0, 8), 1),
                                      "e3": round(55 + random.gauss(0, 5), 1), "e4": round(55 + random.gauss(0, 4), 1)} for y in range(2010, 2025)]},
              "data_diet": [{"missing_pct": m, "gap_days": g, "mae_cp": round(0.1 + m * 0.04 + g * 0.08, 2)}
                            for m in (0, 5, 10, 20, 30, 40, 50) for g in (1, 3, 7, 14)],
              "backtest": {"brier": 0.14, "brier_climatology": 0.21,
                           "reliability": [{"bin": f"{i / 10:.1f}-{(i + 1) / 10:.1f}", "predicted": round(i / 10 + 0.05, 2),
                                            "observed": round(i / 10 + 0.05 + random.gauss(0, 0.04), 2), "n": random.randint(20, 90)} for i in range(10)]},
              "leakage_note": "Gridded data may include some station records, so hidden-station scores may be optimistic; the Wildeye test avoids this.",
              "by_station": [{"id": f"CIMIS-{i}", "name": f"Station {i}", "lat": 35.3 + random.random() * 4.3,
                              "lon": -121.9 + random.random() * 2.7, "dist_km": round(5 + random.random() * 40, 1),
                              "n_seasons": random.randint(8, 20), "e0_mae": round(2 + random.random() * 6, 2),
                              "e3_mae": round(1.5 + random.random() * 4, 2), "e4_mae": round(1.5 + random.random() * 4, 2)}
                             for i in range(30)],
              "diet_rule": "Up to 20% missing days, or gaps up to 7 days, keeps error under 2 CP.",
              "e5_note": "One daily min and max reading cuts the typical miss from 4.8 to 1.3 CP.",
              "findings": ["Mock finding one.", "Mock finding two."],
              "sources": ["mock"], "method": "mock"}

heat_seasons = []
for y in range(1980, 2025):
    acc, s = 0.0, []
    for k in range(91):
        acc += max(0, 6 + k * 0.12 + random.gauss(0, 2))
        s.append({"date": (dt.date(y + 1, 2, 20) + dt.timedelta(days=k)).isoformat(), "gdd": round(acc, 1)})
    heat_seasons.append({"season": f"{y}-{y + 1}", "series": s})
heat = {"mock": True, "bloom": "02-20", "seasons": heat_seasons, "latest": "2024-2025",
        "sources": ["mock"], "method": "Daymet daily, FNRIC single sine (5/35 °C)"}

grid = {"mock": True, "type": "FeatureCollection", "layer": "safe_chill", "variety": "kerman",
        "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [-122.2 + i * 0.25, 40.0 - j * 0.45]},
                      "properties": {"value": round(40 + random.random() * 30, 1)}} for i in range(12) for j in range(12)],
        "sources": ["mock"], "method": "mock"}

for name, obj in [("crops", crops), ("stations", stations), ("point", point), ("history", history),
                  ("replay", replay), ("validation", validation), ("grid", grid), ("heat", heat)]:
    (OUT / f"{name}.json").write_text(json.dumps(obj, separators=(",", ":")))
print("wrote mocks to", OUT)
