"""GDD since bloom by season (additive /api/heat). FNRIC single sine, °C, 5/35, from Daymet daily."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from .. import config as C
from ..pipeline.build_pin import Pin
from ..science.gdd import gdd_series


def heat(pin: Pin, bloom_mmdd: str = "02-20", days: int = 91) -> dict:
    m, d = (int(x) for x in bloom_mmdd.split("-"))
    seasons = []
    daily = pin.daily
    last = daily.index.max().date()
    for y in range(C.FIRST_SEASON, C.LAST_COMPLETE_DAYMET_SEASON + 1):
        b = date(y + 1, m, d)
        e = b + timedelta(days=days - 1)
        if e > last:
            continue
        sub = daily.loc[str(b):str(e)]
        g = np.cumsum(gdd_series(sub["tmin"].to_numpy(), sub["tmax"].to_numpy()))
        seasons.append({"season": C.season_label(y),
                        "series": [{"date": str(x.date()), "gdd": round(float(v), 1)} for x, v in zip(sub.index, g)]})
    return {"bloom": bloom_mmdd, "seasons": seasons, "latest": seasons[-1]["season"] if seasons else None,
            "sources": [C.SOURCES["daymet"]], "method": "Daymet daily at the pin; FNRIC single-sine GDD (5 to 35 °C)"}
