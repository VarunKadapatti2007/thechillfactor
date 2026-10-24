"""Sunrise, sunset and day length from latitude and day of year.

Implemented from Spencer (1971) solar declination and the standard sunrise
equation with -0.8333° for refraction and the solar disc, matching the
values in the chillR hourly-temperatures vignette (BUILD.md 4.5).
"""
from __future__ import annotations

import numpy as np


def daylength(lat: float, jday) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (sunrise, sunset, daylength) in decimal hours (local solar time)."""
    j = np.asarray(jday, dtype=np.float64)
    gamma = 2 * np.pi / 365 * (j - 1)
    delta = 180 / np.pi * (0.006918 - 0.399912 * np.cos(gamma) + 0.070257 * np.sin(gamma)
                           - 0.006758 * np.cos(2 * gamma) + 0.000907 * np.sin(2 * gamma)
                           - 0.002697 * np.cos(3 * gamma) + 0.00148 * np.sin(3 * gamma))
    cos_wo = (np.sin(-0.8333 / 360 * 2 * np.pi) - np.sin(lat / 360 * 2 * np.pi) * np.sin(delta / 360 * 2 * np.pi)) / (
        np.cos(lat / 360 * 2 * np.pi) * np.cos(delta / 360 * 2 * np.pi))
    normal = (cos_wo >= -1) & (cos_wo <= 1)
    w = np.arccos(np.clip(cos_wo, -1, 1)) / (15 / 360 * 2 * np.pi)
    sunrise = np.where(normal, 12 - w, np.where(cos_wo > 1, 12.0, 0.0))
    sunset = np.where(normal, 12 + w, np.where(cos_wo > 1, 12.0, 24.0))
    dl = sunset - sunrise
    return sunrise, sunset, dl
