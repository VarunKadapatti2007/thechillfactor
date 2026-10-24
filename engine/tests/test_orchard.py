"""Grower readings: parsing, units, clock time to PST, and the gap rule."""
import numpy as np
import pandas as pd
import pytest

from chillprint.products import orchard as O
from chillprint.products.point import BadRequest


def test_daily_fahrenheit_to_celsius_and_rows_kept_as_written():
    df = O.parse_daily(["2026-11-01", "2026-11-02", "2026-11-03", "2026-11-03"], [32, 41, 50, 50], [50, 59, 68, 60], "F")
    assert list(df.index.strftime("%Y-%m-%d")) == ["2026-11-01", "2026-11-02", "2026-11-03"]
    assert df.tmin.iloc[0] == pytest.approx(0.0)
    assert df.tmax.iloc[-1] == pytest.approx((60 - 32) * 5 / 9)  # a repeated date keeps the last row
    # A low above its high is not dropped here; qc_daily sets it aside and says so.
    bad = O.parse_daily(["2026-11-01", "2026-11-02"], [20, 20], [10, 10], "C")
    assert len(bad) == 2


def test_logger_local_clock_becomes_hour_ending_pst():
    # 10-minute readings on Oct 1 (daylight time): 13:10..14:00 local is 12:10..13:00 PST -> the 13:00 PST hour.
    times = pd.date_range("2026-10-01 13:10", periods=6, freq="10min").strftime("%Y-%m-%d %H:%M").tolist()
    s = O.parse_hourly(times, [10, 11, 12, 13, 14, 15], "C")
    assert s.loc[pd.Timestamp("2026-10-01 13:00")] == pytest.approx(12.5)
    # In winter (standard time) the local clock already is PST.
    w = O.parse_hourly(["2026-12-01 01:00"], [5.0], "C")
    assert w.index[0] == pd.Timestamp("2026-12-01 01:00")


def test_gap_rule_short_filled_long_left_to_station():
    from types import SimpleNamespace
    from chillprint.pipeline import station_hourly as SH
    if not SH.hourly_index():
        pytest.skip("CIMIS hourly not pulled yet")
    days = pd.date_range("2025-11-01", "2025-11-30", freq="D")
    df = pd.DataFrame({"tmin": np.linspace(2, 6, len(days)), "tmax": np.linspace(14, 18, len(days))}, index=days)
    df = df.drop(days[5:8].union(days[15:21]))  # a 3-day gap (filled) and a 6-day gap (station estimate)
    hrs, short, long_ = O._daily_hours(SimpleNamespace(lat=36.82, lon=-119.74), df, 2025)
    assert (short, long_) == (3, 6)
    day = lambda d: hrs.loc[d + pd.Timedelta(hours=1):d + pd.Timedelta(hours=24)]
    assert day(days[6]).notna().all() and day(days[17]).isna().all()
    assert day(days[0]).min() == pytest.approx(2.0, abs=0.3) and day(days[0]).max() == pytest.approx(14.0, abs=0.3)


def _fake_pin(season=2025):
    from types import SimpleNamespace
    from chillprint.pipeline.build_pin import season_stamps
    st = season_stamps(season)
    h = ((st - pd.Timedelta(hours=1)).hour.to_numpy() - 5) % 24
    est = 5 + 10 * np.clip(np.sin(np.pi * h / 18), 0, 1)  # every day: about 5 C at night, 15 C in the afternoon
    return SimpleNamespace(hourly={season: est.astype(float)})


def test_quality_checks_set_aside_impossible_and_out_of_place_readings():
    days = pd.date_range("2025-12-01", "2025-12-20", freq="D")
    df = pd.DataFrame({"tmin": 6.0, "tmax": 16.0}, index=days)  # the orchard runs about 1 C warmer than the estimate
    df.loc["2025-12-05", "tmin"] = (-6 - 32) * 5 / 9     # -6 F: colder than the valley gets
    df.loc["2025-12-09", "tmax"] = (100 - 32) * 5 / 9    # 100 F in December: far from the stations
    df.loc["2025-12-12", "tmin"] = (100 - 32) * 5 / 9    # a low above its high
    clean, flags = O.qc_daily(df, _fake_pin(), 2025, "F")
    got = {(f["when"], f["field"]) for f in flags}
    assert got == {("2025-12-05", "low"), ("2025-12-09", "high"), ("2025-12-12", "low")}
    assert np.isnan(clean.loc["2025-12-05", "tmin"]) and clean.loc["2025-12-12", "tmax"] == 16.0  # the good high stays
    assert all(f["expected"] is not None for f in flags)


def test_quality_checks_leave_ordinary_orchard_differences_alone():
    days = pd.date_range("2025-12-01", "2025-12-20", freq="D")
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"tmin": 3 + rng.normal(0, 2, len(days)), "tmax": 17 + rng.normal(0, 3, len(days))}, index=days)
    _, flags = O.qc_daily(df, _fake_pin(), 2025, "C")
    assert flags == []
