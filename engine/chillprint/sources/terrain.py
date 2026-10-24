"""Terrain from AWS Terrain Tiles (terrarium PNG, open data) for the Phase 6 ML features.

TPI (topographic position index) = point elevation minus the mean elevation
within a radius. Negative TPI marks valley bottoms and cold-air pools.
Tiles are cached on disk like every other remote response.
"""
from __future__ import annotations

import io
import math
from functools import lru_cache

import numpy as np
from PIL import Image

from . import cache

URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
Z = 10  # ~120 m pixels at 37°N


def _tile_xy(lat: float, lon: float, z: int = Z) -> tuple[float, float]:
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    return x, y


@lru_cache(maxsize=256)
def _tile(x: int, y: int, z: int = Z) -> np.ndarray:
    raw = cache.cached("terrain", f"terrarium_{z}_{x}_{y}", lambda: cache.http_get(URL.format(z=z, x=x, y=y), timeout=60))
    a = np.asarray(Image.open(io.BytesIO(raw)).convert("RGB"), dtype=np.float64)
    return a[:, :, 0] * 256 + a[:, :, 1] + a[:, :, 2] / 256 - 32768


def elevation(lat: float, lon: float) -> float:
    x, y = _tile_xy(lat, lon)
    t = _tile(int(x), int(y))
    return float(t[min(255, int((y % 1) * 256)), min(255, int((x % 1) * 256))])


def tpi(lat: float, lon: float, radius_km: float) -> float:
    """Elevation minus mean elevation of points on rings within radius_km."""
    center = elevation(lat, lon)
    vals = []
    for r in np.linspace(radius_km / 4, radius_km, 4):
        for ang in np.linspace(0, 2 * np.pi, 12, endpoint=False):
            dlat = r / 111.0 * math.cos(ang)
            dlon = r / (111.0 * math.cos(math.radians(lat))) * math.sin(ang)
            vals.append(elevation(lat + dlat, lon + dlon))
    return center - float(np.mean(vals))
