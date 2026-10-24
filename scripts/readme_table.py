"""Regenerate the validation block in README.md from validation_summary.json (never hand-type numbers)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "engine" / "data" / "processed" / "validation" / "validation_summary.json"
README = ROOT / "README.md"
START, END = "<!-- validation:start -->", "<!-- validation:end -->"


def block() -> str:
    s = json.loads(SUMMARY.read_text(encoding="utf-8"))
    lines = [f"Hidden-station test: {s['n_stations']} Central Valley CIMIS stations, {s['n_station_seasons']} station-winters "
             f"(mode: {s['mode']}). Errors are chill portions at Feb 1 and Mar 1, the same cases for every method.", "",
             "| Method | Typical miss (CP) | 8 in 10 within (CP) | Bias (CP) |", "| --- | --- | --- | --- |"]
    for e in s["estimators"]:
        star = " (default)" if e["id"] in s["default_ids"].values() else ""
        lines.append(f"| {e['id']} {e['name']}{star} | {e['mae_cp']} | {e['p80_cp']} | {e['bias_cp']} |")
    if s["wildeye"]["estimators"]:
        lines += ["", f"In-orchard test, {s['wildeye']['n_stations']} Wildeye stations: "
                  + ", ".join(f"{w['id']} {w['mae_cp']} CP" for w in s["wildeye"]["estimators"]) + "."]
    bt = s["backtest"]
    if bt.get("brier") is not None:
        lines += ["", f"Outlook backtest: Brier {bt['brier']} vs {bt['brier_climatology']} for climatology (lower is better)."]
    if s.get("diet_rule"):
        lines += ["", f"Data gaps: {s['diet_rule']}"]
    lines += ["", "Findings:", ""] + [f"- {f}" for f in s["findings"]]
    return "\n".join(lines)


def main() -> None:
    text = README.read_text(encoding="utf-8")
    new = re.sub(re.escape(START) + r".*?" + re.escape(END), START + "\n" + block() + "\n" + END, text, flags=re.S)
    README.write_text(new, encoding="utf-8")
    print("README validation block updated")


if __name__ == "__main__":
    main()
