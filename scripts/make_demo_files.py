"""Write upload-ready demo files from a real in-orchard sensor.

Source: Wildeye station "CA Pistachio # 5 - Terra Bella" (a pistachio orchard), via the FNRIC API.
The same real readings in four formats growers really have, so a demo shows the reader at work:

  1  this winter so far, daily lows and highs, Excel           (min/max thermometer log)
  2  last winter, daily lows and highs, CSV                     (simple spreadsheet export)
  3  last winter, hourly logger export with extra columns, CSV  (a temperature logger)
  4  last winter, a hand-kept notebook sheet, Excel             (odd headers: the AI reader works it out)

    engine/.venv/Scripts/python scripts/make_demo_files.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from chillprint.pipeline import station_hourly as SH  # noqa: E402
from chillprint.pipeline.build_station_store import wildeye_to_pst  # noqa: E402
from chillprint.science.hourly import MIDNIGHT  # noqa: E402
from chillprint.sources import fnric  # noqa: E402
from chillprint.validation import common as V  # noqa: E402

SID = "Wildeye-111086"
OUT = ROOT / "demo_files"
F = lambda c: c * 9 / 5 + 32  # noqa: E731


def this_winter_hourly() -> pd.Series:
    today = date.today()
    raw = fnric.wildeye_raw(SID, date(today.year, 8, 31), today)  # one FNRIC call, cached
    df = wildeye_to_pst(raw)
    s = pd.Series(((df["t_f"] - 32) * 5 / 9).to_numpy(), index=pd.to_datetime(df["ts"]))
    return s[~s.index.duplicated()].sort_index()


def daily(h: pd.Series, d0: str, d1: str) -> pd.DataFrame:
    season = pd.Timestamp(d0).year
    d = V.own_window_daily(h.reindex(pd.date_range(h.index.min(), h.index.max(), freq="h")), season, MIDNIGHT)
    return d.loc[d0:d1].dropna()


def main() -> None:
    OUT.mkdir(exist_ok=True)
    last = SH.wildeye_hourly(SID)
    now = this_winter_hourly()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    # 1. This winter so far: a simple min/max thermometer log in Excel.
    d1 = daily(now, f"{date.today().year}-09-01", yesterday)
    x1 = pd.DataFrame({"Date": d1.index.date, "Low (°F)": F(d1.tmin).round(1), "High (°F)": F(d1.tmax).round(1)})
    x1.to_excel(OUT / "1_orchard_this-winter_daily.xlsx", index=False, sheet_name="Thermometer log")

    # 2. Last winter: the same kind of log as CSV.
    d2 = daily(last, "2025-09-01", "2026-03-01")
    x2 = pd.DataFrame({"date": d2.index.strftime("%Y-%m-%d"), "low_f": F(d2.tmin).round(1), "high_f": F(d2.tmax).round(1)})
    x2.to_csv(OUT / "2_orchard_last-winter_daily.csv", index=False)

    # 5. File 2 with three values changed on purpose, to show the error checks (labeled in README.txt).
    x5 = x2.astype({"low_f": object, "high_f": object}).set_index("date")
    x5.loc["2025-12-15", "low_f"], x5.loc["2026-01-10", "high_f"], x5.loc["2026-02-02", "low_f"] = -6, 100, 100
    x5.reset_index().to_csv(OUT / "5_orchard_last-winter_with-3-mistakes.csv", index=False)

    # 3. Last winter as an hourly logger export: local clock time, a title line, and the sensor's other real
    #    channels (humidity, battery temperature), which the reader must not mistake for air temperature.
    raw = fnric.wildeye_raw(SID, date(2025, 8, 31), date(2026, 3, 31))  # cached from the validation pull
    raw = raw[(raw["date"] >= "2025-09-01") & (raw["date"] <= "2026-03-01")].dropna(subset=["Air Temperature"])
    when = pd.to_datetime(raw["date"]) + pd.to_timedelta(raw["hour"], unit="h")
    log = pd.DataFrame({"Reading #": np.arange(1, len(raw) + 1), "Date": when.dt.strftime("%m/%d/%Y").to_numpy(),
                        "Time": when.dt.strftime("%I:%M %p").to_numpy(),
                        "Air Temp (°F)": raw["Air Temperature"].round(1).to_numpy(),
                        "RH (%)": raw["Relative Humidity"].round(0).to_numpy(),
                        "Battery Temp (°C)": raw["Battery Temperature"].round(1).to_numpy()})
    with open(OUT / "3_orchard_last-winter_logger.csv", "w", encoding="utf-8", newline="") as f:
        f.write("Orchard logger export - Block 7, air sensor at 5 ft in shade\n")
        log.to_csv(f, index=False)

    # 4. Last winter as a hand-kept notebook sheet: title rows, plain-English headers, notes column.
    notes = ["" for _ in range(len(d2))]
    for i in range(0, len(d2), 23):
        notes[i] = "checked shield"
    x4 = pd.DataFrame({"When": d2.index.strftime("%d-%b-%Y"), "Coldest overnight": F(d2.tmin).round(0).astype(int),
                       "Warmest afternoon": F(d2.tmax).round(0).astype(int), "Notes": notes})
    with pd.ExcelWriter(OUT / "4_orchard_last-winter_notebook.xlsx") as w:
        pd.DataFrame([["Terra Bella pistachios - winter readings"], [""]]).to_excel(w, index=False, header=False, sheet_name="Winter")
        x4.to_excel(w, index=False, startrow=2, sheet_name="Winter")

    (OUT / "README.txt").write_text(
        "ChillPrint demo files - all real readings from an in-orchard sensor in a pistachio orchard near Terra Bella\n"
        "(Wildeye station 'CA Pistachio # 5', via the UC FNRIC API). Upload any of them in step 3.\n\n"
        f"1_orchard_this-winter_daily.xlsx     this winter so far ({len(d1)} days), daily low and high, Excel\n"
        f"2_orchard_last-winter_daily.csv      last winter ({len(d2)} days, Sep 1 to Mar 1), daily low and high\n"
        f"3_orchard_last-winter_logger.csv     last winter, hourly logger export ({len(log):,} readings, local clock,\n"
        "                                     plus the sensor's humidity and battery columns, which ChillPrint ignores)\n"
        "4_orchard_last-winter_notebook.xlsx  last winter as a hand-kept sheet with odd headers\n"
        "                                     ('Coldest overnight', 'Warmest afternoon'): the AI reader works it out\n\n"
        "5_orchard_last-winter_with-3-mistakes.csv  file 2 with three values changed ON PURPOSE to show the error checks:\n"
        "                                     Dec 15 low set to -6, Jan 10 high set to 100, Feb 2 low set to 100.\n"
        "                                     ChillPrint flags all three and sets them aside. Everything else is real.\n\n"
        "Put the pin on the orchard (Terra Bella, about 35.96, -119.07) so the comparison with the stations is for the\n"
        "same place.\n",
        encoding="utf-8")
    print(f"wrote {OUT}: this winter {len(d1)} days, last winter {len(d2)} days, logger {len(log)} rows")


if __name__ == "__main__":
    main()
