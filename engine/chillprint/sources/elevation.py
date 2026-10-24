"""Point elevation: USGS EPQS (3DEP), falling back to Open-Meteo's elevation endpoint."""
from __future__ import annotations

import json

from . import cache

EPQS = "https://epqs.nationalmap.gov/v1/json"
OM = "https://api.open-meteo.com/v1/elevation"


def elevation_m(lat: float, lon: float) -> float | None:
    key = f"elev_{lat:.4f}_{lon:.4f}"
    raw = cache.read("elevation", key)
    if raw is not None:
        v = json.loads(raw).get("elev_m")
        return None if v is None else float(v)
    val = None
    try:
        js = json.loads(cache.http_get(EPQS, params={"x": f"{lon:.5f}", "y": f"{lat:.5f}", "units": "Meters", "wkid": 4326}, timeout=30))
        v = float(js["value"])
        if v > -1000:
            val = v
    except Exception:
        pass
    if val is None:
        try:
            js = json.loads(cache.http_get(OM, params={"latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}"}, timeout=30))
            val = float(js["elevation"][0])
        except Exception:
            val = None
    cache.write("elevation", key, json.dumps({"elev_m": val}).encode())
    return val
