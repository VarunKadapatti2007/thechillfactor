"""Growing degree days: FNRIC's single-sine function, verbatim (BUILD.md 4.4).

°C, lower threshold 5, upper 35. Every asin argument is clipped to [-1, 1] so
floating-point rounding cannot raise a domain error. When tmax == tmin the early
branches return before any division.
"""
from __future__ import annotations

from math import asin, cos, pi

import numpy as np


def _asin(x: float) -> float:
    return asin(max(-1.0, min(1.0, x)))


def gdd_single_sine(tmin: float, tmax: float, lo: float = 5.0, hi: float = 35.0) -> float:
    mean, a = (tmax + tmin) / 2, (tmax - tmin) / 2
    if tmin >= hi:
        return hi - lo
    if tmax <= lo:
        return 0.0
    if tmax <= hi and tmin >= lo:
        return mean - lo
    if tmax <= hi:  # tmin < lo
        s1 = _asin((lo - mean) / a)
        return ((mean - lo) * (pi / 2 - s1) + a * cos(s1)) / pi
    if tmin >= lo:  # tmax > hi
        s2 = _asin((hi - mean) / a)
        return ((mean - lo) * (s2 + pi / 2) + (hi - lo) * (pi / 2 - s2) - a * cos(s2)) / pi
    s1, s2 = _asin((lo - mean) / a), _asin((hi - mean) / a)
    return ((mean - lo) * (s2 - s1) + a * (cos(s1) - cos(s2)) + (hi - lo) * (pi / 2 - s2)) / pi


def gdd_series(tmin, tmax, lo: float = 5.0, hi: float = 35.0) -> np.ndarray:
    return np.array([np.nan if (np.isnan(a) or np.isnan(b)) else gdd_single_sine(a, b, lo, hi)
                     for a, b in zip(np.asarray(tmin, float), np.asarray(tmax, float))])
