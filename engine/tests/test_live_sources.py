"""Live data sources: the CIMIS key is one token, and FNRIC's relay lands on CIMIS hour-ending stamps."""
from types import SimpleNamespace

import pandas as pd
import pytest

from chillprint import config as C
from chillprint.pipeline import build_station_store as B


def test_cimis_key_drops_stray_text(monkeypatch):
    monkeypatch.setenv("CIMIS_APP_KEY", "0123456789abcdef0123456789abcdef" + " " * 700 + "x")
    assert C.cimis_key() == "0123456789abcdef0123456789abcdef"
    monkeypatch.setenv("CIMIS_APP_KEY", "   ")
    assert C.cimis_key() is None


def test_fnric_relay_aligns_to_cimis_hours(monkeypatch, tmp_path):
    # FNRIC labels the hour by its start: 23:00 on Oct 23 is CIMIS hour 2400 of Oct 23 (stamp Oct 24 00:00).
    sw = pd.DataFrame({"Timestamp": pd.to_datetime(["2026-10-23 22:00", "2026-10-23 23:00", "2026-10-31 23:00"]),
                       "HlyAirTmp_Value": [61.0, 60.4, 50.0], "HlyAirTmp_Qc": ["", "", ""], "HlyRelHum_Value": [43, 43, 80]})
    monkeypatch.setattr(B.fnric, "stemwater", lambda sid, tag: sw)
    monkeypatch.setattr(B, "hourly_path", lambda sid, season: tmp_path / "none.parquet")
    df = B._fnric_live_month(SimpleNamespace(id="CIMIS-6"), 2026, 10, 2026)
    assert list(df.ts) == list(pd.to_datetime(["2026-10-23 23:00", "2026-10-24 00:00", "2026-11-01 00:00"]))
    row = df[df.ts == pd.Timestamp("2026-10-24 00:00")].iloc[0]
    assert (str(row.cimis_date), int(row.hour)) == ("2026-10-23", 24)
    assert row.t_c == pytest.approx((60.4 - 32) * 5 / 9)
    # Oct 31's last hour still belongs to October (stamp Nov 1 00:00, CIMIS date Oct 31).
    assert str(df.iloc[-1].cimis_date) == "2026-10-31"
