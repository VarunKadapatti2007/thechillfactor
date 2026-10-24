"""Time machine frames for a past winter (Phase 4 step 3).

Every day from Sept 1 to the by date: chill so far and the outlook that would
have been shown that day, using only that day's knowledge (analogs exclude the
replayed winter; today's-climate shift is relative to the replayed winter).
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from .. import config as C
from ..pipeline.build_pin import Pin
from ..science import chill
from .analogs import analog_seasons
from .core import dos, season_daily_cum
from .outlook import _analog_matrix
from .verdict import level


def replay(pin: Pin, season: int, low: float, high: float, by_mmdd: str, climate: str = "today", step: int = 1) -> dict:
    by = C.by_date(season, by_mmdd)
    kb = dos(season, by)
    analogs = analog_seasons(pin, season)
    a = pin.hourly[season]
    _, states = chill.dynamic_with_day_states(a[: (kb + 1) * 24])
    cum = season_daily_cum(pin, season, "sep1")
    # Hours of all analogs for the whole window, built once; each frame continues from its own day.
    M = _analog_matrix(pin, analogs, 0, kb, climate, season)
    frames = []
    for k in range(0, kb + 1, step):
        d = date(season, 9, 1) + timedelta(days=k)
        cp = float(cum[k])
        if k >= kb:
            finals = np.array([cp])
        else:
            st = (float(states[k, 0]), float(states[k, 1]))
            c = chill.dynamic_batch_cumulative(M[:, (k + 1) * 24:(kb + 1) * 24], state=st)
            finals = cp + c[:, -1]
        p10, p50, p90 = (float(x) for x in np.percentile(finals, [10, 50, 90]))
        ch = float(np.mean(finals >= low - 1e-9))
        frames.append({"date": d.isoformat(), "cp": round(cp, 2), "p10": round(p10, 2), "p50": round(p50, 2),
                       "p90": round(p90, 2), "chance_low": round(ch, 3), "level": level(p10, p50, low, high)})
    return {"season": C.season_label(season), "frames": frames, "actual_final_cp": round(float(cum[kb]), 2),
            "sources": pin.sources, "method": pin.method.get(season, "")}
