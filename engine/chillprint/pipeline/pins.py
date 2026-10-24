"""Pick the right pin builder: Daymet + CIMIS inside California, ERA5 elsewhere (Phase 6)."""
from __future__ import annotations

from datetime import date

from .build_pin import Pin, build_pin
from .global_pin import build_global_pin, in_california


def get_pin(lat: float, lon: float, today: date | None = None) -> Pin:
    lat, lon = round(lat, 4), round(lon, 4)
    if in_california(lat, lon):
        return build_pin(lat, lon, today) if today else build_pin(lat, lon)
    return build_global_pin(lat, lon, today)


def is_global(pin: Pin) -> bool:
    return not in_california(pin.lat, pin.lon)
