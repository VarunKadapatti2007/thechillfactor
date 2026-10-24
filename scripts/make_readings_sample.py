"""Write the "Try a real example" file for the orchard-readings step.

Daily lows and highs (°F, calendar days, PST) from a real in-orchard sensor: Wildeye station
"CA Pistachio # 5 - Terra Bella" (pistachio orchard), pulled through the FNRIC API, winter 2025-26.
It is exactly what a min/max thermometer in that orchard would have recorded.

    engine/.venv/Scripts/python scripts/make_readings_sample.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from chillprint.pipeline import station_hourly as SH  # noqa: E402
from chillprint.science.hourly import MIDNIGHT  # noqa: E402
from chillprint.validation import common as V  # noqa: E402

SID, SEASON = "Wildeye-111086", 2025
OUT = ROOT / "web" / "public" / "samples" / "terra-bella-pistachio-2025-26.csv"


def main() -> None:
    d = V.own_window_daily(SH.wildeye_hourly(SID), SEASON, MIDNIGHT).loc[f"{SEASON}-09-01":f"{SEASON + 1}-03-01"].dropna()
    f = d * 9 / 5 + 32
    lines = ["date,low_f,high_f"] + [f"{i:%Y-%m-%d},{r.tmin:.1f},{r.tmax:.1f}" for i, r in f.iterrows()]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(d)} days to {OUT}")


if __name__ == "__main__":
    main()
