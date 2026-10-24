"""Reading grower files: common layouts work without the AI reader, and every number comes from the file."""
import io

import pandas as pd
import pytest

from chillprint.products import readings_parse as R
from chillprint.products.point import BadRequest


def _csv(text: str) -> bytes:
    return text.encode("utf-8")


def test_daily_csv_with_units_in_headers():
    out = R.parse_file("log.csv", _csv("Date,Min Temp (°F),Max Temp (°F)\n11/01/2026,38,62\n11/02/2026,40,64\n11/03/2026,36,58\n"))
    assert (out["kind"], out["unit"], out["method"]) == ("daily", "F", "rules")
    assert out["dates"] == ["2026-11-01", "2026-11-02", "2026-11-03"]
    assert out["lows"] == [38, 40, 36] and out["highs"] == [62, 64, 58]


def test_tab_separated_celsius_and_a_low_above_its_high_is_flagged_not_swapped():
    out = R.parse_file("log.txt", _csv("day\tlow °C\thigh °C\n2026-11-01\t16.5\t3.2\n2026-11-02\t4.1\t17.0\n2026-11-03\t2.0\t15.2\n"))
    assert out["unit"] == "C"
    assert out["lows"][0] == 16.5 and out["highs"][0] == 3.2  # kept exactly as written
    assert out["suspect"][0]["when"] == "2026-11-01" and "above the high" in out["suspect"][0]["reason"]


def test_logger_with_title_line_index_and_other_channels():
    rows = ["Logger export, block 7", "Reading #,Date,Time,Air Temp (°F),RH (%),Battery Temp (°C)"]
    for i in range(96):
        d, h = 1 + i // 24, i % 24
        rows.append(f"{i + 1},11/0{d}/2026,{(h % 12) or 12}:00 {'AM' if h < 12 else 'PM'},{45 + i % 10},{60 + i % 5},{20 + i % 3}")
    out = R.parse_file("logger.csv", _csv("\n".join(rows) + "\n"))
    assert (out["kind"], out["unit"]) == ("hourly", "F")
    assert out["columns"]["temp"] == "Air Temp (°F)"
    assert out["times"][13] == "2026-11-01 13:00" and out["temps"][0] == 45


def test_excel_xlsx_reads_the_sheet_with_data():
    buf = io.BytesIO()
    pd.DataFrame({"Date": pd.date_range("2026-11-01", periods=5).date, "Low (°F)": [38, 39, 40, 41, 42],
                  "High (°F)": [60, 61, 62, 63, 64]}).to_excel(buf, index=False)
    out = R.parse_file("thermometer.xlsx", buf.getvalue())
    assert out["rows"] == 5 and out["first"] == "2026-11-01" and out["highs"][-1] == 64


def test_unclear_layout_without_ai_says_what_to_do(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(BadRequest, match="date, low, high"):
        R.parse_file("notes.csv", _csv("When,Coldest overnight,Warmest afternoon\n1-Nov-2026,38,62\n2-Nov-2026,40,64\n3-Nov-2026,36,58\n"))


def test_ai_layout_is_applied_by_code(monkeypatch):
    # The AI reader only names columns; the values come from the file.
    monkeypatch.setattr(R, "ai_available", lambda: True)
    monkeypatch.setattr(R, "ai_mapping", lambda rows, fn, where: {
        "kind": "daily", "header_rows": 1, "date_column": 0, "time_column": -1, "low_column": 1, "high_column": 2,
        "temp_column": -1, "date_format": "%d-%b-%Y", "day_first": True, "unit": "F", "explanation": "x"})
    out = R.parse_file("notes.csv", _csv("When,Coldest overnight,Warmest afternoon\n1-Nov-2026,38,62\n2-Nov-2026,40,64\n3-Nov-2026,36,58\n"))
    assert out["method"] == "ai" and out["dates"][1] == "2026-11-02" and out["lows"] == [38, 40, 36]
