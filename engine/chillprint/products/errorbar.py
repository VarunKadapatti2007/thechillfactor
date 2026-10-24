"""Per-pin error bar from the validation error model (BUILD.md 4.10)."""
from __future__ import annotations

import json
from functools import lru_cache

from .. import config as C
from ..pipeline.build_pin import Pin
from ..pipeline import station_hourly as SH

ERROR_MODEL = C.VALIDATION_DIR / "error_model.json"


@lru_cache(maxsize=1)
def _model() -> dict | None:
    if not ERROR_MODEL.exists():
        return None
    return json.loads(ERROR_MODEL.read_text())


def dist_bin(km: float) -> str:
    for lo, hi, lab in zip(C.DIST_BINS_KM[:-1], C.DIST_BINS_KM[1:], C.DIST_BIN_LABELS):
        if lo <= km < hi:
            return lab
    return C.DIST_BIN_LABELS[-1]


def terrain(pin_elev: float | None, station_elev: float | None) -> str:
    if pin_elev is None:
        return "valley"
    if pin_elev > C.FOOTHILL_ELEV_M or (station_elev is not None and pin_elev - station_elev > C.FOOTHILL_DELEV_M):
        return "foothill"
    return "valley"


def pin_context(pin: Pin) -> tuple[float, str]:
    """Distance to the nearest CIMIS station with hourly data, and terrain class."""
    near = SH.nearest_cimis(pin.lat, pin.lon, with_hourly=True, k=1)
    if near.empty:
        near = SH.nearest_cimis(pin.lat, pin.lon, k=1)
    r = near.iloc[0]
    return float(r.dist_km), terrain(pin.elev_m, None if r.elev_m != r.elev_m else float(r.elev_m))


def error_cp(pin: Pin, method: str = "history") -> float | None:
    """80th-percentile absolute CP error for this pin's distance and terrain bin, or None if not validated."""
    m = _model()
    if not m:
        return None
    km, ter = pin_context(pin)
    table = m.get(method) or m.get("history")
    key = f"{dist_bin(km)}|{ter}"
    v = table.get("bins", {}).get(key)
    if v is None:
        v = table.get("by_distance", {}).get(dist_bin(km))
    if v is None:
        v = table.get("overall")
    return None if v is None else round(float(v), 1)
