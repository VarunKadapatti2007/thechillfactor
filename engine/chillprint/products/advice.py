"""What to do next: recommendations for one farm from everything ChillPrint knows about it (POST /api/advice).

The server rebuilds the farm's full picture from the same inputs as the analysis (it never trusts
numbers sent by the page): this winter's chill counted from the grower's readings, the error bar,
the odds and verdict, the readings against the station estimate and any readings set aside, the
closest past winter, 45 winters of history at the spot with the trend, the sunny-stretch flag, the
measured accuracy, and the daily lows and highs themselves. Claude turns that into structured
advice (Claude Sonnet, with the API's server-side fallback if it declines). The prompt keeps it to the numbers given and to practices UC has documented, with no product
rates, and points the grower to their farm advisor or PCA for treatment decisions.

A different farm, outline, crop or set of readings changes the context and so the answer; the same
context is answered from a cache.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date

import numpy as np
import pandas as pd

from .. import config as C
from ..pipeline.pins import get_pin
from .history import history as history_product
from .orchard import orchard_point, parse_daily, parse_hourly
from .point import BadRequest
from .readings_parse import _api_key

MODEL = "claude-sonnet-5-5"  # stronger reasoning for advice; the file reader stays on Haiku
CACHE = C.PROCESSED_DIR / "api_cache"

SYSTEM = """You are ChillPrint's orchard advisor for California fruit and nut growers. You get one \
farm's complete winter-chill picture as JSON: the location and block size, the crop and variety with \
its chill need and need-by date, this winter's chill counted from the grower's own daily low/high \
readings, the measured error bar, the odds of reaching the need (from 40+ past winters played forward \
from today), the verdict, how the readings compare with the nearby-station estimate, readings that \
were set aside as wrong, the closest past winter, the 45-winter history at the spot with its trend, \
and the daily readings.

Write practical, specific next steps for this grower.
- Use only the numbers in the JSON. Quote them rounded the way a grower would say them: whole chill \nportions ("68 CP"), dates like "Mar 1", odds like "8 in 10", temperatures to the nearest degree.
- When comparing, use percentages: chill as a percent of the minimum need (100% = need met, higher is \nbetter) and errors as a percent (lower is better), with the chill portions in brackets if useful.
- Fit the advice to the verdict and the time of season: early season (before mid-November) is about \
monitoring and data; mid-winter about tracking and protecting chill; near the need date about bloom \
preparation; a past winter about lessons and planning.
- Options you may raise when they fit, always as things to discuss with a UC farm advisor or PCA, \
never with product names or rates: kaolin clay sprays in warm, sunny, fog-free spells to keep buds \
cooler (UC Davis TreeChill research); dormant oil timing to help bloom in low-chill years (studied \
in pistachio and other crops); planning pollination and bloom overlap (for pistachio, male and female \
bloom overlap) when chill is short; frost protection readiness around bloom; for planning, matching \
varieties to the spot's safe winter chill and its trend.
- Data actions are always useful: keep logging daily lows and highs; fix readings that were set \
aside; keep the thermometer shaded and ventilated about 5 ft up.
- Be honest about uncertainty: mention the error bar when the result is close to the need.
- Plain words for growers. No jargon beyond "chill portions". No markdown in strings."""

SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "summary": {"type": "string"},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "when": {"type": "string"},
                    "why": {"type": "string"},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                    "category": {"type": "string", "enum": ["monitor", "protect_chill", "bloom", "data", "planning"]},
                },
                "required": ["title", "when", "why", "priority", "category"],
                "additionalProperties": False,
            },
        },
        "watch_for": {"type": "array", "items": {"type": "string"}},
        "data_notes": {"type": "array", "items": {"type": "string"}},
        "longer_term": {"type": "string"},
    },
    "required": ["headline", "summary", "actions", "watch_for", "data_notes", "longer_term"],
    "additionalProperties": False,
}


def _daily_table(kind: str, unit: str, dates, lows, highs, times, temps) -> list[list]:
    """The grower's readings as [date, low, high] in their unit (logger hours become daily low/high)."""
    if kind == "daily":
        df = parse_daily(dates or [], lows or [], highs or [], unit)
    else:
        h = parse_hourly(times or [], temps or [], unit).dropna()
        g = h.groupby((h.index - pd.Timedelta(hours=1)).normalize())
        df = pd.DataFrame({"tmin": g.min(), "tmax": g.max()})
    back = (lambda c: c * 9 / 5 + 32) if unit == "F" else (lambda c: c)
    return [[d.strftime("%Y-%m-%d"), None if not np.isfinite(r.tmin) else round(float(back(r.tmin)), 1),
             None if not np.isfinite(r.tmax) else round(float(back(r.tmax)), 1)] for d, r in df.iterrows()]


def _accuracy() -> dict:
    """Measured typical error, as a percent of the chill actually measured (lower is better)."""
    try:
        t = json.loads((C.VALIDATION_DIR / "orchard_readings.json").read_text())["tests"]["wildeye_orchard"]
        return {"typical_error_with_daily_readings_pct": t["scenarios"]["readings_from_sep1"].get("mape_mar1"),
                "typical_error_stations_only_pct": t["scenarios"]["station_only"].get("mape_mar1"),
                "tested_at": f"{t['n_sites']} Wildeye pistachio orchards (UC FNRIC data)", "lower_is_better": True}
    except Exception:
        return {}


def farm_context(lat: float, lon: float, crop: str, variety: str, kind: str, unit: str, dates=None, lows=None,
                 highs=None, times=None, temps=None, start: str = "sep1", by: str | None = None, climate: str = "today",
                 block_acres: float | None = None, label: str | None = None, today: date | None = None) -> dict:
    today = today or date.today()
    cp, v = C.find_variety(crop, variety)
    out = orchard_point(lat, lon, crop, variety, kind, unit, dates=dates, lows=lows, highs=highs, times=times,
                        temps=temps, start=start, by=by, climate=climate, today=today)
    pin = get_pin(lat, lon, today)
    by_mmdd = by or v.by_date_default
    hist = history_product(pin, v.need_low, v.need_high, by_mmdd, start)
    recent = [w for w in hist["winters"] if not w.get("filled")][-10:]
    o = out["orchard"]
    return {
        "today": today.isoformat(),
        "farm": {"name": label or "the grower's orchard", "lat": round(lat, 4), "lon": round(lon, 4),
                 "elevation_m": out["location"]["elev_m"], "block_acres": block_acres,
                 "nearest_station": out["location"]["nearest_station"]},
        "crop": {"crop": cp.name, "variety": v.name, "need_cp_low": v.need_low, "need_cp_high": v.need_high,
                 "need_by": out["need"]["by"], "need_source": "UC Cooperative Extension (Pope)"},
        "winter": {"season": out["season"], "as_of": out["asof"], "counting_from": "Sep 1" if start == "sep1" else "Nov 1",
                   "chill_so_far_cp": out["chill"]["to_date"], "error_bar_cp": out["chill"]["error_cp"],
                   "need_date_passed": out["asof"] >= out["need"]["by"]},
        "outlook_at_need_date": {k: out["outlook"][k] for k in ("p10", "p50", "p90", "chance_low", "chance_high", "n_analogs")},
        "verdict": out["verdict"],
        "closest_past_winter": out["closest"]["season"],
        "readings": {"kind": o["kind"], "first": o["first"], "last": o["last"], "days": o["days"],
                     "gaps_filled": o["gap_filled"], "gaps_from_station_estimate": o["gap_estimated"], "gap_unit": o["gap_unit"],
                     "set_aside_count": o["flagged_count"], "set_aside": o["flagged"][:10],
                     "chill_from_station_estimate_cp": o["station_estimate_cp"], "readings_minus_station_cp": o["difference_cp"],
                     "unit": unit, "daily_low_high": _daily_table(kind, unit, dates, lows, highs, times, temps)},
        "flags": {"sunny_stretch": out["flags"]["sunny_stretch"]},
        "history_at_this_spot": {
            "winters": len(hist["winters"]), "share_reaching_need_low": hist["share_met_low"],
            "share_reaching_need_high": hist["share_met_high"], "trend_cp_per_decade": hist["trend"]["cp_per_decade"],
            "trend": hist["trend"]["label"], "safe_winter_chill_1981_2000": hist["safe_chill"]["early"]["p10"],
            "safe_winter_chill_2006_2025": hist["safe_chill"]["recent"]["p10"],
            "last_10_winters_cp_by_need_date": [[w["season"], w["cp_by"]] for w in recent],
        },
        "percent_of_minimum_need": {"chill_so_far": round(100 * out["chill"]["to_date"] / v.need_low),
                                    "most_likely_at_need_date": round(100 * out["outlook"]["p50"] / v.need_low),
                                    "error_bar": None if out["chill"]["error_cp"] is None else round(100 * out["chill"]["error_cp"] / v.need_low)},
        "accuracy": _accuracy(),
    }


def advice(ctx: dict) -> dict:
    key = hashlib.sha1(json.dumps([MODEL, ctx], sort_keys=True, default=str).encode()).hexdigest()[:24]
    p = CACHE / f"advice_{key}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    k = _api_key()
    if not k:
        raise BadRequest("Recommendations need the AI service, which isn't set up on this server.")
    import anthropic
    client = anthropic.Anthropic(api_key=k, timeout=90.0, max_retries=2)
    try:
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=8000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM,
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": "Farm context:\n" + json.dumps(ctx, default=str)}],
        )
    except anthropic.APIStatusError as e:
        raise BadRequest(f"Recommendations are unavailable right now ({e.status_code}). Try again in a minute.")
    except anthropic.APIConnectionError:
        raise BadRequest("Recommendations are unavailable right now. Try again in a minute.")
    if resp.stop_reason == "refusal":
        raise BadRequest("Couldn't write recommendations for this farm.")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    out = json.loads(text)
    out["context"] = {"season": ctx["winter"]["season"], "as_of": ctx["winter"]["as_of"], "crop": ctx["crop"]["crop"],
                      "variety": ctx["crop"]["variety"], "chill_so_far_cp": ctx["winter"]["chill_so_far_cp"],
                      "verdict": ctx["verdict"]["level"], "readings_days": ctx["readings"]["days"]}
    out["model"] = MODEL
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out), encoding="utf-8")
    return out
