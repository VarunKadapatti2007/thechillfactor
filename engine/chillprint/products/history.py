"""Land history for a pin (BUILD.md 4.9)."""
from __future__ import annotations

import numpy as np
import pymannkendall as mk
from scipy.stats import theilslopes

from .. import config as C
from ..pipeline.build_pin import Pin
from ..science import chill
from .core import dos, season_daily_cum, shifted_hourly, start_dos


def cp_by(pin: Pin, season: int, by_mmdd: str, start: str = "sep1", climate_ref: int | None = None) -> float:
    by = C.by_date(season, by_mmdd)
    k = dos(season, by)
    if climate_ref is None:
        return float(season_daily_cum(pin, season, start)[k])
    a = shifted_hourly(pin, season, climate_ref)
    s0 = start_dos(start)
    p, _ = chill.dynamic_portions(a[s0 * 24:(k + 1) * 24])
    return float(p.sum())


def safe_chill(values: np.ndarray, n_boot: int = 2000, seed: int = C.SEED) -> tuple[float, list[float]]:
    """10th percentile with a 90% bootstrap interval."""
    v = np.asarray(values, dtype=float)
    p10 = float(np.percentile(v, 10))
    rng = np.random.default_rng(seed)
    boots = np.percentile(rng.choice(v, size=(n_boot, len(v)), replace=True), 10, axis=1)
    return p10, [float(np.percentile(boots, 5)), float(np.percentile(boots, 95))]


def history(pin: Pin, low: float, high: float, by_mmdd: str, start: str = "sep1") -> dict:
    seasons = pin.history_seasons()
    winters = []
    for y in seasons:
        v = cp_by(pin, y, by_mmdd, start)
        if not np.isfinite(v):
            continue
        winters.append({"season": C.season_label(y), "cp_by": round(v, 2), "met_low": bool(v >= low),
                        "met_high": bool(v >= high), "filled": bool(pin.filled.get(y, False))})
    complete = [(C.season_start_year(w["season"]), w["cp_by"]) for w in winters if not w["filled"]]
    yrs = np.array([c[0] for c in complete], dtype=float)
    vals = np.array([c[1] for c in complete], dtype=float)

    slope, _, lo, hi = theilslopes(vals, yrs, alpha=0.90)
    p = float(mk.original_test(vals).p)
    if p > 0.1:
        label = "no clear trend"
    else:
        label = "likely decline" if slope < 0 else "likely increase"

    early = vals[(yrs >= 1980) & (yrs <= 1999)]
    recent = vals[(yrs >= 2005) & (yrs <= 2024)]
    e10, eci = safe_chill(early)
    r10, rci = safe_chill(recent)
    cur = C.current_season()
    today_vals = np.array([cp_by(pin, int(y), by_mmdd, start, climate_ref=cur) for y in yrs])

    n = len(vals)
    return {
        "winters": winters,
        "share_met_low": round(float(np.mean(vals >= low)), 3) if n else 0.0,
        "share_met_high": round(float(np.mean(vals >= high)), 3) if n else 0.0,
        "trend": {"cp_per_decade": round(float(slope) * 10, 2), "ci90": [round(float(lo) * 10, 2), round(float(hi) * 10, 2)],
                  "p_value": round(p, 4), "label": label},
        "safe_chill": {
            "early": {"years": "1981-2000", "p10": round(e10, 1), "ci": [round(x, 1) for x in eci]},
            "recent": {"years": "2006-2025", "p10": round(r10, 1), "ci": [round(x, 1) for x in rci]},
            "today_replay": {"p10": round(float(np.percentile(today_vals, 10)), 1),
                             "p50": round(float(np.percentile(today_vals, 50)), 1)},
        },
        "links": [{"title": t, "url": u} for t, u in C.LINKS_2050],
        "sources": pin.sources + [C.CROP_SOURCE],
        "method": _method_summary(pin),
    }


def _method_summary(pin: Pin) -> str:
    ys = pin.complete_seasons()
    e3 = sum(1 for y in ys if pin.method.get(y) == "E3")
    return f"E3 ({e3} of {len(ys)} winters with a station shape; others Method L)" if e3 < len(ys) else "E3"
