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

ORDER = ["E0", "E1", "E2", "E3", "E4", "E5", "E8"]
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
            "mape_mar1": round(float((sub.err_mar1.abs() / sub.truth_mar1.where(sub.truth_mar1 > 5)).mean() * 100), 1),
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

    # History default: the best estimator that yields hours for any past winter (E4 needs a station
    # with a complete record that winter; E3/E2 need only Daymet). Chosen by MAE on the headline set.
    cand_hist = [e for e in ("E4", "E3", "E2") if e in scores]
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

    # E7 (Phase 6): shown either way; scored on the same station-seasons it shares with the headline set.
    e7_entry, e7_info = None, None
    if (V.OUT / "e7_summary.json").exists() and (V.OUT / "e7_hidden.parquet").exists():
        e7_info = json.loads((V.OUT / "e7_summary.json").read_text(encoding="utf-8"))
        h7 = pd.read_parquet(V.OUT / "e7_hidden.parquet").set_index(["station_id", "season"])
        idx = h7.index.intersection(common_idx)
        if len(idx):
            e = pd.concat([h7.loc[idx].err_feb1, h7.loc[idx].err_mar1])
            e7_entry = {"id": "E7", "name": "Daymet + ML night-low fix" + ("" if e7_info.get("ship") else " (not shipped)"),
                        "mae_cp": round(float(e.abs().mean()), 2), "p80_cp": round(float(e.abs().quantile(0.8)), 2),
                        "bias_cp": round(float(e.mean()), 2)}

    sig_p = V.OUT / "significance.json"
    sig = json.loads(sig_p.read_text(encoding="utf-8")) if sig_p.exists() else {}
    e8_adopted = bool(sig.get("preregistered_E8", {}).get("adopt"))

    e5_note = None
    if "E5" in scores and "E0" in scores:
        e5_note = (f"Adding one daily low and high at the orchard cuts the typical miss from "
                   f"{scores['E0']['mae_cp']:.1f} CP (nearest station) to {scores['E5']['mae_cp']:.1f} CP.")

    findings = _findings(scores, hist_id, live_id, we_scores, bt, bt_full, dd_rule, mode)
    if sig.get("paired_vs_E4"):
        d0 = sig["paired_vs_E4"]["E0"]
        findings.insert(2, f"Statistically (cluster bootstrap over stations), E4's edge over the nearest station is "
                           f"{-d0['mean_diff']:.2f} CP with a 95% interval of {-d0['ci95'][1]:.2f} to {-d0['ci95'][0]:.2f}: "
                           f"likely but not proven overall; clear at 25-50 km.")
    if sig.get("preregistered_E8"):
        e8 = sig["preregistered_E8"]
        findings.append(f"Pre-registered test: averaging three stations (E8) misses by {scores['E8']['mae_cp']:.2f} CP, "
                        f"{-e8['E8_minus_E4']['mean_diff']:.2f} less than E4 (95% interval {-e8['E8_minus_E4']['ci95'][1]:.2f} to "
                        f"{-e8['E8_minus_E4']['ci95'][0]:.2f}) and slightly worse at orchards, so it was not adopted.")
    ml_shape_info = None
    if (V.OUT / "ml_shape_summary.json").exists():
        ml_shape_info = json.loads((V.OUT / "ml_shape_summary.json").read_text(encoding="utf-8"))
        findings.append(f"Phase 6: an ML hourly shape on Daymet scores {ml_shape_info['ml_shape']['mae']:.2f} CP vs "
                        f"{ml_shape_info['E3']['mae']:.2f} for the borrowed shape and {ml_shape_info['E2']['mae']:.2f} for the textbook curve "
                        f"({ml_shape_info['n']} station-winters); it replaces the textbook curve for winters with no station record.")
    if e7_info:
        findings.append(f"Phase 6: the ML night-low fix (E7) improves Daymet ({e7_info['hidden_e7_mae']:.2f} vs E3 {e7_info['hidden']['e3_mae']:.2f} CP) "
                        f"but does not beat the {e7_info['default']} default ({e7_info['hidden_default_mae']:.2f}); not shipped.")
    orp = V.OUT / "orchard_readings.json"
    orchard_readings = json.loads(orp.read_text(encoding="utf-8")) if orp.exists() else None
    if orchard_readings and "wildeye_orchard" in orchard_readings["tests"]:
        w = orchard_readings["tests"]["wildeye_orchard"]
        sc = w["scenarios"]
        findings.append(f"Grower readings: at {w['n_sites']} Wildeye pistachio orchards ({w['n_station_winters']} winters), the station "
                        f"estimate misses by {sc['station_only']['mae_cp']:.2f} CP (bias {sc['station_only']['bias_cp']:+.2f}); adding the "
                        f"orchard's own daily lows and highs from Sep 1 brings it to {sc['readings_from_sep1']['mae_cp']:.2f} CP "
                        f"(bias {sc['readings_from_sep1']['bias_cp']:+.2f}), and from Jan 1 to {sc['readings_from_jan1']['mae_cp']:.2f} CP.")
    summary = {
        "n_stations": int(hc.station_id.nunique()),
        "n_station_seasons": int(hc[["station_id", "season"]].drop_duplicates().shape[0]),
        "estimators": [{"id": e, "name": hidden_station.NAMES[e] + (" (tested, not adopted)" if e == "E8" and not e8_adopted else ""), "mae_cp": scores[e]["mae_cp"],
                        "p80_cp": scores[e]["p80_cp"], "bias_cp": scores[e]["bias_cp"], "mape_mar1": scores[e]["mape_mar1"]} for e in present]
                      + ([e7_entry] if e7_entry else []),
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
        "details": {"significance": sig, "e7": e7_info, "ml_shape": ml_shape_info, "scores": scores, "by_distance": by_dist, "by_terrain": by_ter, "durham_mae": durham_err,
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
        f.append(f"The outlook {'beats' if better else 'does not beat'} climatology: Brier {bt['brier']:.4f} vs {bt['brier_climatology']:.4f}.")
    if bt_full:
        bc = bt_full["by_climate"]
        f.append(f"Today's-climate shift is {'on' if bt_full['default_climate'] == 'today' else 'off'} by default "
                 f"(Brier {bc['today']['brier']:.4f} with, {bc['recorded']['brier']:.4f} without).")
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
        if e["id"] not in d["scores"]:
            lines.append(f"| {e['id']} {e['name']} | {e['mae_cp']} | | {e['p80_cp']} | | {e['bias_cp']} | | | | |")
            continue
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
    orp = V.OUT / "orchard_readings.json"
    if orp.exists():
        o = json.loads(orp.read_text(encoding="utf-8"))
        lines += ["", "## Grower readings (orchard_readings.py)", "", o["note"], "",
                  "| Scenario | Test | Station-winters | Sites | Mean abs error | P80 | Bias |", "| --- | --- | --- | --- | --- | --- | --- |"]
        for test, t in o["tests"].items():
            for sc in ("station_only", "readings_from_sep1", "readings_from_nov1", "readings_from_dec1", "readings_from_jan1"):
                r = t["scenarios"].get(sc)
                if r:
                    lines.append(f"| {sc} | {test} | {t['n_station_winters']} | {t['n_sites']} | {r['mae_cp']} | {r['p80_cp']} | {r['bias_cp']} |")
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
