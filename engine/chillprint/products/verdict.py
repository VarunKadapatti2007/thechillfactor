"""Verdict and sentence (BUILD.md 4.8)."""
from __future__ import annotations

from datetime import date

from .. import config as C

LABELS = {"green": "On track", "amber": "Watch", "red": "At risk"}


def level(p10: float, p50: float, low: float, high: float) -> str:
    if p10 >= high:
        return "green"
    if p50 < low:
        return "red"
    return "amber"


def fmt_need(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def fmt_day(d: date) -> str:
    return f"{d:%b} {d.day}"


def verdict(p10: float, p50: float, low: float, high: float, chance_low: float, variety: str, by: date,
            asof: date, season: int) -> dict:
    lv = level(p10, p50, low, high)
    k = int(round(chance_low * 10))
    m, d = (int(x) for x in C.EARLY_SEASON_MMDD.split("-"))
    early = asof < date(season, m, d)
    return {
        "level": lv,
        "label": LABELS[lv],
        "sentence": f"{k} in 10 similar winters reached {variety}'s {fmt_need(low)} CP by {fmt_day(by)}.",
        "early": early,
    }
