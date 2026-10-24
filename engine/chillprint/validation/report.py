"""Run the validation protocol and write validation_summary.json, error_model.json and REPORT.md.

    python -m chillprint.validation.report            # run everything, then report
    python -m chillprint.validation.report --report   # only rebuild the report from saved results
"""
from __future__ import annotations

import json
import sys
import time

import numpy as np
import pandas as pd

from .. import config as C
from ..pipeline import station_hourly as SH
from . import backtest, data_diet, error_model, hidden_station, wildeye
from . import common as V

ORDER = ["E0", "E1", "E2", "E3", "E4", "E5"]
LEAKAGE = ("Daymet may include some of the same weather records as the hidden stations, so hidden-station "
           "scores may be a little optimistic; the Wildeye in-orchard test has no such overlap.")


def _score(sub: pd.DataFrame) -> dict:
    e = pd.concat([sub.err_mar1, sub.err_feb1])
    a = e.abs()
    return {"mae_cp": round(float(a.mean()), 2), "median_cp": round(float(a.median()), 2),
            "p80_cp": round(float(a.quantile(0.8)), 2), "p90_cp": round(float(a.quantile(0.9)), 2),
            "bias_cp": round(float(e.mean()), 2), "mae_mar1": round(float(sub.err_mar1.abs().mean()), 2),
            "mae_feb1": round(float(sub.err_feb1.abs().mean()), 2),
            "cross23_days": round(float(sub.cross23_err.abs().mean()), 1) if sub.cross23_err.notna().any() else None,
            "cross54_days": round(float(sub.cross54_err.abs().mean()), 1) if sub.cross54_err.notna().any() else None,
            "hourly_rmse_c": round(float(sub.hourly_rmse.mean()), 2) if sub.hourly_rmse.notna().any() else None,
            "gdd_mae": round(float(sub.gdd_err.abs().mean()), 1) if sub.gdd_err.notna().any() else None,
            "n": int(len(sub))}


def summarize() -> dict:
    hs = pd.read_parquet(V.OUT / "validation_by_station.parquet")
    mode = hs["mode"].iloc[0]
    present = [e for e in ORDER if e in set(hs.estimator)]
    # Headline set: station-seasons where every present estimator exists (same cases for all).
    piv = hs.pivot_table(index=["station_id", "season"], columns="estimator", values="err_mar1", aggfunc="first")
    common_idx = piv.dropna(subset=present).index
    hc = hs.set_index(["station_id", "season"]).loc[common_idx].reset_index()
    scores = {e: _score(hc[hc.estimator == e]) for e in present}

    cand_hist = [e for e in ("E3", "E2") if e in scores]
    hist_id = min(cand_hist, key=lambda e: scores[e]["mae_cp"]) if cand_hist else "E0"
    # Live season: E4 when station hourly exists. Keyless, the live estimate is gridMET + Method L,
    # whose closest validated analog is E2 (gridded daily + textbook curve).
    live_id = "E4" if "E4" in scores else ("E2" if "E2" in scores else "E0")

    # Breakdowns by distance and terrain
    hc["dbin"] = pd.cut(hc.dist_km, [0, 10, 25, 50, 1e9], labels=list(C.DIST_BIN_LABELS), right=False)
    by_dist = {e: {str(k): round(float(g.err_mar1.abs().mean()), 2) for k, g in hc[hc.estimator == e].groupby("dbin", observed=True)}
               for e in present}
    by_ter = {e: {k: round(float(g.err_mar1.abs().mean()), 2) for k, g in hc[hc.estimator == e].groupby("terrain")}
              for e in present}
    em = error_model.build(hs, hist_id, live_id)

    # Wildeye
    we_scores, we_n = [], 0
    p = V.OUT / "wildeye_results.parquet"
    if p.exists():
        we = pd.read_parquet(p)
        if len(we):
            wp = we.pivot_table(index=["station_id", "season"], columns="estimator", values="err_mar1", aggfunc="first")
            wpres = [e for e in ORDER if e in wp.columns]
            widx = wp.dropna(subset=wpres).index
            wc = we.set_index(["station_id", "season"]).loc[widx].reset_index()
            we_n = int(wc.station_id.nunique())
            we_scores = [{"id": e, "mae_cp": round(float(pd.concat([wc[wc.estimator == e].err_mar1, wc[wc.estimator == e].err_feb1]).abs().mean()), 2)}
                         for e in wpres]

    # Durham (CIMIS-12): last 15 winters
    du = hs[hs.station_id == C.DURHAM_ID]
    winters = []
    if len(du):
        seasons = sorted(du.season.unique())[-15:]
        for y in seasons:
            g = du[du.season == y].set_index("estimator")
            winters.append({"season": C.season_label(int(y)),
                            "truth": round(float(g.truth_mar1.iloc[0]), 2),
                            **{k.lower(): (round(float(g.loc[k, "cp_mar1"]), 2) if k in g.index else None) for k in ("E0", "E3", "E4")}})
    durham_err = {}
    for k in ("e0", "e3", "e4"):
        vals = [abs(w[k] - w["truth"]) for w in winters if w.get(k) is not None]
        if vals:
            durham_err[k] = round(float(np.mean(vals)), 2)
    (V.OUT / "durham.json").write_text(json.dumps({"winters": winters, "mae": durham_err}, indent=1), encoding="utf-8")

    # Data diet
    dd_curve, dd_rule, dd_n = [], None, 0
    p = V.OUT / "data_diet.parquet"
    if p.exists():
        dd = pd.read_parquet(p)
        dd_curve, dd_rule = data_diet.summarize(dd)
        dd_n = int(dd[["station_id", "season"]].drop_duplicates().shape[0])

    # Backtest
    bt = {"brier": None, "brier_climatology": None, "reliability": []}
    bt_full = None
    p = V.OUT / "backtest.parquet"
    if p.exists():
        b = pd.read_parquet(p)
        if len(b):
            bt_full = backtest.summarize(b)
            d = bt_full["by_climate"][bt_full["default_climate"]]
            bt = {"brier": round(d["brier"], 4), "brier_climatology": round(d["brier_climatology"], 4),
                  "reliability": bt_full["reliability"]}

    by_station = []
    for sid, g in hc.groupby("station_id"):
        s = SH.stations().set_index("id").loc[sid]
        row = {"id": sid, "name": s["name"], "lat": float(s.lat), "lon": float(s.lon),
               "dist_km": round(float(g.dist_km.median()), 1), "n_seasons": int(g.season.nunique())}
        for e in ("E0", "E3", "E4"):
            ge = g[g.estimator == e]
            row[f"{e.lower()}_mae"] = round(float(ge.err_mar1.abs().mean()), 2) if len(ge) else None
        by_station.append(row)

    e5_note = None
    if "E5" in scores and "E0" in scores:
        e5_note = (f"Adding one daily low and high at the orchard cuts the typical miss from "
                   f"{scores['E0']['mae_cp']:.1f} CP (nearest station) to {scores['E5']['mae_cp']:.1f} CP.")

    findings = _findings(scores, hist_id, live_id, we_scores, bt, bt_full, dd_rule, mode)
    summary = {
        "n_stations": int(hc.station_id.nunique()),
        "n_station_seasons": int(hc[["station_id", "season"]].drop_duplicates().shape[0]),
        "estimators": [{"id": e, "name": hidden_station.NAMES[e], "mae_cp": scores[e]["mae_cp"],
                        "p80_cp": scores[e]["p80_cp"], "bias_cp": scores[e]["bias_cp"]} for e in present],
        "wildeye": {"n_stations": we_n, "estimators": we_scores},
        "durham": {"winters": winters},
        "data_diet": [{"missing_pct": c["missing_pct"], "gap_days": c["gap_days"], "mae_cp": c["mae_cp"]} for c in dd_curve],
        "backtest": bt,
        "leakage_note": LEAKAGE,
        "default_ids": {"history": hist_id, "live": live_id,
                        "climate": bt_full["default_climate"] if bt_full else "today"},
        "by_station": by_station,
        "diet_rule": dd_rule,
        "e5_note": e5_note,
        "findings": findings,
        "mode": mode,
        "details": {"scores": scores, "by_distance": by_dist, "by_terrain": by_ter, "durham_mae": durham_err,
                    "backtest": bt_full, "data_diet_curve": dd_curve, "data_diet_station_seasons": dd_n},
        "sources": [C.SOURCES["cimis"], C.SOURCES["fnric"], C.SOURCES["daymet"]],
        "method": "hidden-station validation (BUILD.md section 5)",
    }
    (V.OUT / "validation_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    _write_report(summary)
    return summary


def _findings(scores, hist_id, live_id, we, bt, bt_full, rule, mode) -> list[str]:
    f = []
    e0 = scores.get("E0", {}).get("mae_cp")
    for e in ("E3", "E4"):
        if e in scores and e0 is not None:
            d = scores[e]["mae_cp"]
            verb = "beats" if d < e0 else "does not beat"
            f.append(f"{e} ({hidden_station.NAMES[e]}) {verb} the nearest station: typical miss {d:.1f} vs {e0:.1f} CP.")
    if "E5" in scores and e0 is not None:
        f.append(f"One daily reading at the orchard (E5) brings the typical miss to {scores['E5']['mae_cp']:.1f} CP.")
    if bt.get("brier") is not None:
        better = bt["brier"] < bt["brier_climatology"]
        f.append(f"The outlook {'beats' if better else 'does not beat'} climatology: Brier {bt['brier']:.3f} vs {bt['brier_climatology']:.3f}.")
    if bt_full:
        bc = bt_full["by_climate"]
        f.append(f"Today's-climate shift is {'on' if bt_full['default_climate'] == 'today' else 'off'} by default "
                 f"(Brier {bc['today']['brier']:.3f} with, {bc['recorded']['brier']:.3f} without).")
    if we:
        f.append("At Wildeye in-orchard stations: " + ", ".join(f"{w['id']} {w['mae_cp']:.1f} CP" for w in we) + ".")
    if rule:
        f.append(rule)
    if mode == "keyless":
        f.append("Run without CIMIS hourly: truth is FNRIC daily chill and only E0, E1 and E2 were possible.")
    return f


def _write_report(s: dict) -> None:
    d = s["details"]
    lines = ["# ChillPrint validation report", "",
             f"Mode: **{s['mode']}**. {s['n_stations']} hidden stations, {s['n_station_seasons']} station-winters "
             f"(the same cases for every estimator). Errors pool Feb 1 and Mar 1.", "",
             "## Hidden-station test (BUILD.md 5.2)", "",
             "| Estimator | Mean abs error (CP) | Median | P80 | P90 | Bias | Days off at 23 CP | Days off at 54 CP | Hourly RMSE (°C) | GDD error Feb-Mar (°C-days) |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for e in s["estimators"]:
        sc = d["scores"][e["id"]]
        lines.append(f"| {e['id']} {e['name']} | {sc['mae_cp']} | {sc['median_cp']} | {sc['p80_cp']} | {sc['p90_cp']} | {sc['bias_cp']} | "
                     f"{sc['cross23_days']} | {sc['cross54_days']} | {sc['hourly_rmse_c']} | {sc['gdd_mae']} |")
    lines += ["", "By distance to the nearest station (mean abs error by Mar 1, CP):", "",
              "| Estimator | " + " | ".join(C.DIST_BIN_LABELS) + " |", "| --- |" + " --- |" * len(C.DIST_BIN_LABELS)]
    for e, row in d["by_distance"].items():
        lines.append(f"| {e} | " + " | ".join(str(row.get(b, "")) for b in C.DIST_BIN_LABELS) + " |")
    lines += ["", "By terrain:", "", "| Estimator | valley | foothill |", "| --- | --- | --- |"]
    for e, row in d["by_terrain"].items():
        lines.append(f"| {e} | {row.get('valley', '')} | {row.get('foothill', '')} |")
    lines += ["", "## Findings", ""] + [f"- {x}" for x in s["findings"]]
    lines += ["", f"Default for past winters: **{s['default_ids']['history']}**. Default for the live season: "
              f"**{s['default_ids']['live']}**. Chosen by lowest mean absolute error on the headline set; nothing was tuned on the test set.", "",
              "## Wildeye in-orchard test (BUILD.md 5.3)", "",
              f"{s['wildeye']['n_stations']} stations. " + ", ".join(f"{w['id']}: {w['mae_cp']} CP" for w in s["wildeye"]["estimators"]), "",
              "## Durham (CIMIS 12) case study (BUILD.md 5.7)", "",
              "| Winter | Measured | E0 | E3 | E4 |", "| --- | --- | --- | --- | --- |"]
    for w in s["durham"]["winters"]:
        lines.append(f"| {w['season']} | {w['truth']} | {w.get('e0')} | {w.get('e3')} | {w.get('e4')} |")
    lines += ["", f"Mean abs error: {d['durham_mae']}", "", "## Data diet (BUILD.md 5.5)", "",
              f"{d['data_diet_station_seasons']} station-winters. Rule: {s['diet_rule']}", "",
              "| Missing % | Gap length (days) | Mean abs error | P80 |", "| --- | --- | --- | --- |"]
    for c in d["data_diet_curve"]:
        lines.append(f"| {c['missing_pct']:.0f} | {c['gap_days']:.0f} | {c['mae_cp']} | {c['p80_cp']} |")
    lines += ["", "## Outlook backtest (BUILD.md 5.6)", ""]
    if d["backtest"]:
        for k, v in d["backtest"]["by_climate"].items():
            lines.append(f"- {k}: Brier {v['brier']:.4f} vs climatology {v['brier_climatology']:.4f} (n={v['n']})")
        lines += ["", "| Predicted bin | Mean predicted | Observed | n |", "| --- | --- | --- | --- |"]
        for r in d["backtest"]["reliability"]:
            lines.append(f"| {r['bin']} | {r['predicted']} | {r['observed']} | {r['n']} |")
    lines += ["", "## Caveats", "", f"- {s['leakage_note']}",
              "- GDD is scored Feb 1 to Mar 31 because the hourly pull ends Mar 31, not 90 days from bloom.",
              "- Air temperature is not bud temperature."]
    (V.OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (C.ENGINE_DIR / "chillprint" / "validation" / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    t0 = time.time()
    if "--report" not in sys.argv:
        hidden_station.run()
        wildeye.run()
        data_diet.run()
        backtest.run()
    s = summarize()
    print(json.dumps({k: s[k] for k in ("n_stations", "n_station_seasons", "estimators", "default_ids", "findings")}, indent=1))
    print(f"validation done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
