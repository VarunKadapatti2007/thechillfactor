"""Production use of the ML hourly shape (Phase 6 step 2; validation/ml_shape.py trains and scores it).

LightGBM predicts each hour's position between the day's low and high from the
hour, day length, Daymet range and solar radiation, month and latitude. The
predicted positions act as a synthetic "station" inside Method B, so the same
rescaling to the pin's Daymet min/max and boundary blending apply.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from .. import config as C
from .daylength import daylength
from .hourly import MIDNIGHT, Window, borrowed_shape

MODEL = C.PROCESSED_DIR / "models" / "ml_shape.txt"
FEATURES = ["hour", "daylen", "range", "srad", "month", "lat"]


@lru_cache(maxsize=1)
def _booster():
    import lightgbm as lgb
    return lgb.Booster(model_file=str(MODEL))


def available() -> bool:
    return MODEL.exists()


def shape_series(lat: float, daily: pd.DataFrame, win: Window = MIDNIGHT) -> pd.Series:
    days = pd.DatetimeIndex(daily.index)
    d = daily.interpolate(limit_direction="both")
    _, _, dl = daylength(lat, days.day_of_year.to_numpy())
    X = pd.DataFrame({"hour": np.tile(np.arange(24), len(days)), "daylen": np.repeat(dl, 24),
                      "range": np.repeat((d["tmax"] - d["tmin"]).to_numpy(), 24),
                      "srad": np.repeat(d["srad"].to_numpy(), 24),
                      "month": np.repeat(days.month.to_numpy(), 24), "lat": float(lat)})[FEATURES].astype(float)
    p = _booster().predict(X).reshape(len(days), 24)
    first = win.first_stamp(days)
    stamps = (first[:, None] + (np.arange(24) * np.timedelta64(1, "h"))[None, :]).ravel()
    return pd.Series(p.ravel(), index=pd.DatetimeIndex(stamps))


def ml_hours(lat: float, daily: pd.DataFrame, win: Window = MIDNIGHT) -> pd.Series:
    """Hourly series at a pin from Daymet daily (tmin, tmax, srad) with the ML shape."""
    d = daily[["tmin", "tmax", "srad"]].interpolate(limit_direction="both")
    s, _ = borrowed_shape(d, [shape_series(lat, d, win)], lat, win)
    return s
