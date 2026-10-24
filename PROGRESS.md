# ChillPrint progress log

One agent is running both roles (A: engine, B: app), phase by phase, using the gate rule in BUILD.md.

## Environment notes

- Python 3.12 venv at `engine/.venv` (BUILD.md says 3.11; 3.12 is what this machine has, and numba 0.68 / xclim 0.62 support it).
- Disk: C: was full at start. pip cache purged with the user's OK; installs use `--no-cache-dir`; raw caches are gzipped.
- CIMIS app key: pending from the user (goes in `.env`, which is gitignored).

## Open questions for Julia / FNRIC

- **"By" dates** for every crop in `config.py` are placeholders from BUILD.md (Almond Feb 1, Cherry Feb 15, others Mar 1). Confirm. They are editable in the UI.
- Is Daymet free of CIMIS inputs? We assume yes (Daymet V4 uses GHCN-Daily). Confirm with Carson or Julia.
- Are Wildeye in-orchard stations excluded from all gridded products? We assume yes.

## GATE 0 (2026-10-23 23:15)

| Check | Result |
| --- | --- |
| Every source answered, or has a written fallback | PASS. FNRIC (all 6 endpoints incl. Wildeye), CIMIS station list, Daymet (after three 504s), Open-Meteo forecast + archive + elevation, USGS EPQS, PRISM (answered; skipped as too slow) all answered. CIMIS hourly answered 401 without a key; the key is pending and the keyless fallback is written in DATA_SOURCES.md |
| DATA_SOURCES.md lists real field names for FNRIC, CIMIS and Daymet | PASS for FNRIC, Daymet, CIMIS station list. **Open:** CIMIS hourly record field names can only be confirmed with the key; the parser accepts both documented spellings and is verified on the first pull |
| Web app starts and renders the map with mocks | PASS. `next dev` with `NEXT_PUBLIC_USE_MOCKS=1`; headless Edge screenshot shows the Positron basemap and mock stations, zero console errors (after fixing the MapLibre v6 worker URL under Turbopack) |

Key numbers: FNRIC Davis chill history 16,167 days back to 1982-07-17; Daymet 46 years for one pin in 1.3 s; gridMET point query 0.4 s; PRISM one CONUS day 43 MB / 15 s.

Known issues: CIMIS key pending. Daymet single-pixel was down for ~15 minutes; the client retries and has a gridMET fallback.

**GATE 0 PASSED** with the one open item above (CIMIS hourly field names, blocked on the key, not on code).

## GATE 1 (2026-10-24 00:40): BLOCKED on the CIMIS key

| Check | Result |
| --- | --- |
| >= 30 Central Valley stations with >= 10 complete winters of hourly, or a written explanation | Explanation: CIMIS hourly needs an app key (401 without it). The CIMIS FTP bulk archive refuses connections and FNRIC exposes only the last 300 hours, so there is no keyless route to historical hourly. Done instead: FNRIC daily chill pulled for all 87 Central Valley stations + 26 Wildeye (truth for E0/E1/E2), Wildeye in-orchard hourly pulled (25 stations, 290k hours), and the CIMIS client is ready to run the moment the key appears |
| Durham hourly covers >= 10 complete winters | **FAIL** (no CIMIS hourly). FNRIC daily chill for Durham covers 1982-2025 |
| Daymet cached for every station pixel and all six demo pins | PASS (113 station pixels + 6 pins) |
| Day alignment chosen and recorded, with its correlation | PASS on Wildeye hourly: midnight PST, lag 0, r = 0.946 Tmin / 0.983 Tmax (26 stations, 9,927 days) |
| Rerun makes zero network calls | PASS for stations, FNRIC, Wildeye, Daymet (`CHILLPRINT_OFFLINE=1`, 0 calls) |

Fix attempts: (1) asked for the key at 22:50 and sent a reminder at 00:30; (2) looked for keyless hourly (FTP, FNRIC stemwater). Still failing. **Smallest fallback (running now):** keyless mode. History = Daymet + Method L (E2), the live season = gridMET + Method L, truth = FNRIC daily chill, and the independent test = Wildeye hourly. Everything is labeled with the method used. When `CIMIS_APP_KEY` lands, `scripts/run_validation.sh` reruns Phases 1-4 with Method B.

## GATE 2 (2026-10-24 01:05): PASSED

| Check | Result |
| --- | --- |
| Linvill and daylength vectors within 1e-3 | PASS (all 13 values; daylength needed the textbook Spencer 2γ terms) |
| Dynamic Model vs xclim within 0.05 CP, full season | PASS: 60.122 vs 60.122 CP (same Kelvin series) |
| Davis (CIMIS-6) three seasons vs FNRIC within 0.5 CP, daily r > 0.99 | PASS on real CIMIS hourly. Dynamic CP: 2014-15 61.613 vs 61.613, 2018-19 91.277 vs 91.277, 2023-24 83.401 vs 83.401; r = 1.000, 0 mismatched days. Both chill-hour counts identical. Utah r >= 0.999; totals differ by +4, +8 and 0 units, each from one day where CIMIS flagged hours "R" (far out of range): we drop them per BUILD.md, FNRIC counts them |
| GDD vs numeric integration, 10,000 cases | PASS (max error < 1e-3) |
| Continuation: two halves with saved state = whole | PASS (exact to 1e-12) |

How the Davis match was reached (two fix attempts, as the gate rule asks):
1. First run (metric pull, short gaps interpolated): totals within 0.5 CP but daily r 0.87 to 0.97. Chill hours matched exactly, so hour mapping was right. All 2018-19 mismatches began right after one missing hour (2019-02-20 12:00); interpolating it shifted later portion completions by an hour, moving whole portions across midnight.
2. FNRIC's conventions, found by testing: it computes from CIMIS's **°F** values and **skips missing hours** (the model holds its state). With both, the match is exact. The pull now requests English units (converted to °C on read) and station truth skips missing hours. A float round-trip at exact °F thresholds was also fixed (`c_to_f` rounds).
Plus FNRIC's stemwater state matches ours to 2e-16 (T + 273 K).

## GATE 3, keyless subset (2026-10-24 00:40): PARTIAL

Ran in 505 s. 65 stations, 884 station-winters, FNRIC daily truth. Errors pool Feb 1 and Mar 1.

| Estimator | MAE | P80 | Bias |
| --- | --- | --- | --- |
| E0 nearest station | 5.32 | 7.11 | +0.18 |
| E1 3-station average | 4.61 | 6.26 | -0.05 |
| E2 Daymet + Method L | 4.75 | 7.06 | -2.28 |

- E2 beats E0 overall and clearly in the foothills (4.9 vs 8.8 CP) and beyond 50 km (5.3 vs 8.9); E0 is better within 10 km (3.5 vs 5.6).
- Wildeye in-orchard (18 stations): E0 3.19, E2 4.01 CP.
- Outlook backtest (Wildeye truth, 720 cases): Brier 0.021 vs climatology 0.031. Today's-climate shift: 0.022 with, 0.021 without, so it defaults **off** in keyless mode.
- Data diet (48 Wildeye station-winters, Method L shape): one daily reading with no gaps misses by 1.6 CP typical, 3.2 CP at P80, so no gap rule keeps P80 under 2 CP with the textbook curve.
- Not yet answerable without CIMIS hourly: does E3 beat E0? Does E4 beat E0? What does E5 (with a station shape) buy?

## Log

- 2026-10-23 22:30 Phase 0 started.
- 2026-10-23 23:15 Phase 0 done. Starting Phase 1 keyless pulls (stations, FNRIC daily chill, Wildeye, Daymet) and Phase 2 science while the CIMIS key is pending.
- 2026-10-23 23:40 Phase 1 keyless pulls: stations.parquet (303; 87 Central Valley CIMIS; 26 Wildeye, elevations from USGS EPQS). FNRIC daily chill for 113 stations (112 calls, once). Daymet for 113 station pixels + 6 demo pins (118 calls). Wildeye: multi-year requests 503 upstream, so one request per site per season (16 s each).
- 23:50 Phase 2 science written and tested (13 tests pass). **Finding:** FNRIC's Dynamic Model uses T + 273 K (their stemwater state matches ours to 2e-16); xclim's °C conversion (273.15) gives 2 CP less over a Davis season (58.1 vs 60.1). We use 273 and test against xclim on the same Kelvin series (exact match, 60.122 CP).
- 2026-10-24 00:05 Phase 5a/5b web app built against mocks: header (search, °F/°C, help), MapLibre map (Positron, station layers, Durham "Closed Jul 2025", grid + hidden-station error layers, layer menu, legend, draggable pin with spring drop and loading pulse, offline image fallback), coach marks, empty state with quick picks, crop/variety picker with by-date / start / climate settings, four tabs (This winter with verdict, ring gauge, tiles, season chart, year highlighter, time machine; Land history; Heat; Accuracy), skeletons, error lines, motion. Checked in headless Edge at 1440 px and 375 px (bottom sheet), zero console errors. Fixed along the way: MapLibre v6 worker URL, a style-fallback race under React dev double-mount, a zero-height bottom-sheet parent, replay pacing (now time-based, ~10 days/s).
- 00:15 Phase 4 engine code written ahead of GATES 1-3 (it runs on Method L until CIMIS hourly exists): build_pin (8.0 s new pin, 0.1 s cached), outlook with state continuation, closest winter, verdict, history (Theil-Sen + Mann-Kendall + bootstrap safe chill), replay (182 frames in 1.1 s), heat, live forecast, FastAPI with on-disk cache. gridMET long requests take over 60 s, so the keyless fill uses a short Sept-Dec 2025 overlap.
- 00:18 Preview, keyless: E2 (Daymet + Method L) against FNRIC truth over 884 station-seasons: MAE 5.3 CP, bias -2.7, P80 8.0.
- 00:25 Phase 3 code written (hidden station E0-E5, Wildeye, data diet, backtest, error model, report). Running the keyless subset now. GATE 1 cache-hit test passes for stations, FNRIC, Wildeye and Daymet (0 network calls on rerun).
- 00:35 User added the CIMIS key. First real request (Davis, Nov 2014): 720 records, fields as documented. Pull started metric, then switched to English units after the GATE 2 investigation (see GATE 2). Keyless live estimate had shown 4-6 CP at Durham/Shafter while FNRIC stations read 0 CP; E4 on real station hourly replaces it.
- 00:55 Phase 6 code prepared but held behind GATES 1-4: Sfax global pin (ERA5 via Open-Meteo; Kerman red, 0 of 46 winters met, -5.0 CP/decade), sunny-stretch heuristic from station solar, E7 LightGBM correction with TPI from AWS Terrain Tiles.
- 01:10 GATE 5 checks against the real API: production build has 0 files containing mock data; Lighthouse accessibility 100 on empty state, This winter, Land history and Accuracy (after fixing heading order, a role on the pin, and a button name). Shareable URL state added (?lat&lon&crop&variety&tab&replay). Offline basemap rendered from the real Positron style (1400x1949, exact Mercator bounds).
- Contract note: `/api/heat` is added (not in section 7) because the Heat tab needs GDD by season. `/api/validation` carries additive fields (`by_station`, `diet_rule`, `e5_note`, `findings`) for the Accuracy tab. All section 7 fields are unchanged.
