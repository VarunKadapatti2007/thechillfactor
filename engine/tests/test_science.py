"""Phase 2 science checks (BUILD.md 4.3-4.5, GATE 2)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from chillprint.science import chill, gdd, hourly
from chillprint.science.daylength import daylength

DATA = Path(__file__).resolve().parents[1] / "data"


# --- daylength (chillR vignette vectors) ------------------------------------------

@pytest.mark.parametrize("lat,jday,rise,sset,dl", [
    (50.4, 15, 7.766425, 16.23357, 8.467149),
    (50.5, 1, 7.962814, 16.03719, 8.074373),
])
def test_daylength_vectors(lat, jday, rise, sset, dl):
    r, s, d = daylength(lat, [jday])
    assert abs(r[0] - rise) < 1e-3
    assert abs(s[0] - sset) < 1e-3
    assert abs(d[0] - dl) < 1e-3


# --- Method L (chillR vignette vectors) ---------------------------------------------

def test_linvill_vectors():
    h = hourly.linvill_hourly(50.4, [1, 2], [5.1, 5.0], [8.2, 9.1])
    day1 = [6.424223, 6.203183, 6.022917, 5.870701, 5.738969]
    day2 = [5.574983, 5.468975, 5.373123, 5.285650, 5.205208, 5.130750]
    assert np.allclose(h[0, 19:24], day1, atol=1e-3), h[0, 19:24]
    assert np.allclose(h[1, 0:6], day2, atol=1e-3), h[1, 0:6]


def test_linvill_daytime_reaches_tmax():
    days = pd.date_range("2014-12-01", periods=5, freq="D")
    daily = pd.DataFrame({"tmin": [2.0, 3, 1, 4, 2], "tmax": [12.0, 14, 11, 15, 13]}, index=days)
    s = hourly.linvill_series(38.5, daily)
    for d, row in daily.iloc[1:-1].iterrows():
        day = s[d:d + pd.Timedelta(hours=23)]
        assert day.max() <= row.tmax + 1e-9
        assert day.max() > row.tmax - 0.6


# --- Method B ----------------------------------------------------------------------

def _station_series(days, base_shape, mins, maxs):
    vals = []
    for mn, mx in zip(mins, maxs):
        vals.extend(mn + base_shape * (mx - mn))
    idx = pd.date_range(days[0] + pd.Timedelta(hours=1), periods=24 * len(days), freq="h")
    return pd.Series(vals, index=idx)


def test_borrowed_shape_reproduces_pin_minmax_and_shape():
    days = pd.date_range("2015-01-01", periods=6, freq="D")
    shape = (np.sin(np.linspace(-np.pi / 2, 3 * np.pi / 2, 24)) + 1) / 2
    shape = (shape - shape.min()) / (shape.max() - shape.min())  # exactly 0..1
    st = _station_series(days, shape, [0.0] * 6, [10.0] * 6)
    pin = pd.DataFrame({"tmin": [2.0] * 6, "tmax": [8.0] * 6}, index=days)
    s, src = hourly.borrowed_shape(pin, [st], lat=38.5)
    assert (src == 0).all()
    # identical neighbouring days -> blending changes nothing; curve = 2 + 6*shape
    assert np.allclose(s.to_numpy(), np.tile(2 + 6 * shape, 6), atol=1e-9)


def test_borrowed_shape_falls_back_when_station_flat_or_missing():
    days = pd.date_range("2015-01-01", periods=4, freq="D")
    shape = (np.sin(np.linspace(-np.pi / 2, 3 * np.pi / 2, 24)) + 1) / 2
    flat = _station_series(days, shape, [5.0, 5.0, 5.0, 5.0], [5.2, 5.2, 5.2, 5.2])  # range 0.2 < 0.5
    good = _station_series(days, shape, [0.0] * 4, [10.0] * 4)
    good.iloc[24:24 + 6] = np.nan  # day 2 has 6 missing hours (> 4)
    pin = pd.DataFrame({"tmin": [2.0] * 4, "tmax": [8.0] * 4}, index=days)
    s, src = hourly.borrowed_shape(pin, [flat, good], lat=38.5)
    assert list(src) == [1, -1, 1, 1]  # flat skipped; day 2 -> Method L
    assert s.notna().all()


def test_borrowed_shape_blends_without_jumps():
    days = pd.date_range("2015-01-01", periods=3, freq="D")
    shape = (np.sin(np.linspace(-np.pi / 2, 3 * np.pi / 2, 24)) + 1) / 2
    st = _station_series(days, shape, [0.0] * 3, [10.0] * 3)
    pin = pd.DataFrame({"tmin": [0.0, 6.0, 0.0], "tmax": [10.0, 16.0, 10.0]}, index=days)
    s, _ = hourly.borrowed_shape(pin, [st], lat=38.5)
    assert np.abs(np.diff(s.to_numpy())).max() < 3.0  # a 6 °C step is spread over 6 hours


# --- Dynamic Model -------------------------------------------------------------------

def _season_hourly():
    """A real season of hourly temps: Daymet at the Davis CIMIS pixel + Method L."""
    p = DATA / "processed" / "daymet" / "CIMIS-6.parquet"
    if not p.exists():
        pytest.skip("Daymet Davis pixel not cached")
    d = pd.read_parquet(p).loc["2014-08-31":"2015-04-01"]
    s = hourly.linvill_series(38.5357, d).loc["2014-09-01 01:00":"2015-04-01 00:00"]
    return s.interpolate(limit_direction="both")


def test_dynamic_matches_xclim_full_season():
    xr = pytest.importorskip("xarray")
    from xclim.indices import chill_portions

    s = _season_hourly()
    ours, _ = chill.dynamic_portions(s.to_numpy())
    # Same Kelvin series for both (FNRIC/chillR convention T + 273).
    da = xr.DataArray(s.to_numpy() + 273.0, coords={"time": s.index.values}, dims="time", attrs={"units": "K"})
    ref = float(chill_portions(da, freq="YS-JUL").sum())
    assert abs(ours.sum() - ref) < 0.05, (ours.sum(), ref)
    # Record the size of the 273 vs 273.15 convention gap (informational).
    da2 = xr.DataArray(s.to_numpy(), coords={"time": s.index.values}, dims="time", attrs={"units": "degC"})
    ref2 = float(chill_portions(da2, freq="YS-JUL").sum())
    print(f"\nseason CP ours(273)={ours.sum():.3f} xclim(273)={ref:.3f} xclim(degC->273.15)={ref2:.3f}")


def test_dynamic_continuation_equals_whole():
    s = _season_hourly().to_numpy()
    whole, end_state = chill.dynamic_portions(s)
    k = len(s) // 2 + 7
    a, st = chill.dynamic_portions(s[:k])
    b, end2 = chill.dynamic_portions(s[k:], state=st)
    assert np.allclose(np.concatenate([a, b]), whole, atol=1e-12)
    assert np.allclose(end_state, end2)
    # Batch continuation matches too.
    cum = chill.dynamic_batch_cumulative(np.vstack([s[k:], s[k:]]), state=st)
    assert np.allclose(cum[0, -1], b.sum())


def test_dynamic_state_matches_fnric_stemwater():
    """FNRIC exposes its running state; our recursion must reproduce it hour by hour."""
    f = DATA / "cache" / "spike" / "fnric_stemwater_CIMIS-6.json"
    if not f.exists():
        pytest.skip("stemwater spike file missing")
    sw = pd.DataFrame(json.loads(f.read_text())["hourly_values"])
    sw["Timestamp"] = pd.to_datetime(sw["Timestamp"])
    sw = sw.sort_values("Timestamp").reset_index(drop=True)
    tc = ((sw.HlyAirTmp_Value - 32) * 5 / 9).to_numpy()
    st = (sw.dynmod_inter_e.iloc[0], sw.dynmod_xi.iloc[0])
    p, end = chill.dynamic_portions(tc[1:], state=st)
    assert abs(end[0] - sw.dynmod_inter_e.iloc[-1]) < 1e-9
    assert abs(end[1] - sw.dynmod_xi.iloc[-1]) < 1e-9


def test_chill_hour_and_utah_definitions():
    f = np.array([31.9, 32.0, 32.1, 34.0, 35.0, 36.0, 40.0, 45.0, 45.1, 48.0, 50.0, 54.0, 57.0, 60.0, 62.0, 65.0, 70.0])
    c = (f - 32) * 5 / 9
    assert list(chill.hours_below_45(c)) == [1] * 8 + [0] * 9
    assert list(chill.hours_32_45(c)) == [0, 0] + [1] * 6 + [0] * 9
    assert list(chill.utah_units(c)) == [0, 0, 0, 0, 0.5, 0.5, 1, 1, 1, 1, 0.5, 0.5, 0, 0, -0.5, -0.5, -1]


# --- GDD -------------------------------------------------------------------------------

def _gdd_numeric(tmin, tmax, lo=5.0, hi=35.0, n=20000):
    th = (np.arange(n) + 0.5) / n * 2 * np.pi
    mean, a = (tmax + tmin) / 2, (tmax - tmin) / 2
    t = mean[:, None] + a[:, None] * np.sin(th)[None, :]
    return (np.clip(t, lo, hi) - lo).mean(axis=1)


def test_gdd_matches_numeric_integration():
    rng = np.random.default_rng(42)
    a = rng.uniform(-10, 45, 10_000)
    b = rng.uniform(-10, 45, 10_000)
    tmin, tmax = np.minimum(a, b), np.maximum(a, b)
    ours = np.array([gdd.gdd_single_sine(x, y) for x, y in zip(tmin, tmax)])
    ref = np.concatenate([_gdd_numeric(tmin[i:i + 500], tmax[i:i + 500]) for i in range(0, 10_000, 500)])
    assert np.abs(ours - ref).max() < 1e-3


def test_gdd_zero_range_and_clipping():
    for t in (-3.0, 5.0, 20.0, 35.0, 40.0):
        v = gdd.gdd_single_sine(t, t)
        assert v == pytest.approx(min(max(t, 5), 35) - 5)
    # values that would push asin just past 1 through rounding
    assert np.isfinite(gdd.gdd_single_sine(5.0 - 1e-15, 35.0 + 1e-15))
