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

## GATE 1 (2026-10-24 02:30): PASSED

| Check | Result |
| --- | --- |
| >= 30 Central Valley stations with >= 10 complete winters (>= 95% hours Sept 1-Mar 1) | PASS: **59 stations**; 1,521 complete station-seasons (1982-83 .. 2025-26); median coverage 99.8% |
| Durham hourly covers >= 10 complete winters | PASS: **40 complete winters** (1982-83 .. 2024-25; the station closed July 2025) |
| Daymet cached for every station pixel and all six demo pins | PASS (113 station pixels + 6 pins, plus 1,109 grid points) |
| Day alignment chosen and recorded, with its correlation | PASS: midnight PST, lag 0. CIMIS (40 stations, 131,107 days): r 0.951 Tmin / 0.986 Tmax; Wildeye agrees (0.946 / 0.983) |
| Rerun makes zero network calls | PASS: stations, FNRIC, Wildeye, Daymet, and both CIMIS ranges re-run with `CHILLPRINT_OFFLINE=1`: 0 calls, no errors |

Pull: 12,300+ station-month requests in English units, 3 workers under one global 0.3 s throttle. 28 station-seasons hit "Remote end closed connection" after 5 retries; a resumable rerun fetched all 147 missing months. QC: 64k flagged temperature values dropped (1.4%; most at Shafter CIMIS-5).

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

## GATE 3 (2026-10-24 03:05): PASSED

Full run on real CIMIS hourly: 65 hidden Central Valley stations, 855 station-winters (2005-06 .. 2025-26), the same cases for every estimator; errors pool Feb 1 and Mar 1. Outputs: `validation_summary.json`, `validation_by_station.parquet`, `error_model.json`, `REPORT.md` (engine/chillprint/validation/REPORT.md). No NaNs in headline metrics.

| Estimator | MAE (CP) | P80 | Bias | Days off at 54 CP | Hourly RMSE (°C) |
| --- | --- | --- | --- | --- | --- |
| E0 Nearest station | 3.86 | 5.87 | 0.14 | 5.9 | None |
| E1 3-station average | 3.43 | 4.96 | -0.1 | 5.3 | None |
| E2 Daymet + textbook curve | 4.22 | 6.54 | -3.19 | 7.0 | 2.38 |
| E3 Daymet + borrowed shape | 4.94 | 7.48 | -4.04 | 8.2 | 2.03 |
| E4 Station + Daymet offset | 3.44 | 5.27 | 0.48 | 5.4 | 1.79 |
| E5 One reading a day | 1.56 | 2.48 | 0.2 | 2.6 | 1.24 |
| E7 Daymet + ML night-low fix (not shipped) | 4.25 | 6.69 | -3.31 |  |  |

| Estimator | 0-10 km | 10-25 | 25-50 | 50+ | valley | foothill |
| --- | --- | --- | --- | --- | --- | --- |
| E0 | 3.19 | 4.19 | 4.11 | 7.64 | 3.92 | 7.12 |
| E1 | 2.82 | 3.69 | 3.29 | 8.32 | 3.36 | 6.81 |
| E2 | 5.53 | 5.27 | 4.05 | 5.08 | 4.87 | 4.32 |
| E3 | 6.88 | 6.25 | 4.87 | 5.2 | 5.84 | 4.59 |
| E4 | 2.65 | 4.17 | 3.5 | 5.12 | 3.77 | 4.81 |
| E5 | 1.46 | 1.58 | 1.75 | 2.0 | 1.59 | 2.13 |

The five questions, one sentence each:
- **Does E3 beat E0?** No: 4.94 vs 3.86 CP. Daymet's daily min/max run warm at night at these irrigated, cold-pooling sites (E3 bias -4.0 CP); the borrowed shape itself is fine (E5 uses it and scores 1.56).
- **Does E4 beat E0?** Yes: 3.44 vs 3.86 CP overall, with the biggest gains beyond 50 km (5.15 vs 7.75 in stage 1) and in the foothills.
- **What does one daily reading (E5) buy?** The typical miss falls from 3.86 (nearest station) to 1.56 CP.
- **Is the outlook better than climatology?** Yes: Brier 0.0108 vs 0.0168 over 21,192 station-winter-date-variety cases.
- **Today's-climate shift on or off?** On (Brier 0.0108 with, 0.0111 without).

Defaults: **E4 for past winters and the live season** (lowest MAE among estimators that produce hours). Not tuned on the test set: the choice is among the pre-defined estimators.
Wildeye in-orchard (18 stations, common set): E0 3.12, E2 4.00, E3 5.30, E4 3.52 CP. In orchards the nearest station does best; orchard air runs warmer than CIMIS grass sites (E0 bias +1.5).
Durham (last 15 winters): E0 3.06, E3 5.25, E4 3.98 CP. For Durham the nearest station is better than E4.
Data diet: Up to 30% missing days scattered through the winter, or gaps up to 4 days, keeps the typical error under 2 CP (with no gaps, 8 in 10 winters land within 2.8 CP).
Error model: E4 P80 by distance 0-10 km 3.3, 10-25 5.4, 25-50 4.6, 50+ 7.9 CP; error grows through the season (16% of the Mar 1 error by Nov 1, 49% by Dec 1, 65% by Jan 1, 76% by Feb 1).

## GATE 4 (2026-10-24 03:20): PASSED

| Check | Result |
| --- | --- |
| Every endpoint returns schema-valid JSON for all six demo pins | PASS: `scripts/export_demo.py` drives the real FastAPI app (TestClient) for 6 pins x 9 varieties: point, history, replay 2014-15 and 2015-16, heat, plus crops, stations, validation and 18 grid layers; point/history/replay/crops/stations/validation are checked against `schemas.py` on every response. Bundle 16.2 MB, no "mock" anywhere |
| Replay of 2014-15 at the Shafter-area pin shows Kerman amber or red by Feb 1 | **The data say no, and that is reported, not forced.** With E4 (Shafter station, 2 km) the Feb 1 frame is green: 58.1 CP so far, P10/P50/P90 67/72/75 by Mar 1; final 68.1 CP. FNRIC's own record for the Shafter station agrees: 58.9 CP by Feb 1, 67.8 by Mar 1 in 2014-15. The low-chill winter was real nearby: FNRIC shows Arvin-Edison 49.4 and Belridge 53.7 CP by Mar 1 (below Kerman's 54). The replay still turns (amber until Nov 1, then green). The keyless E2 run had shown red (48.6 CP) only because E2 runs 3 CP low |
| Land history for the Durham pin returns 45 winters with trend and safe chill | PASS: 46 winters (1980-81 .. 2025-26), 43 with E4 from the Durham/Biggs stations and 3 faded (no complete station record: 1980-81, 1981-82, 1982-83); trend -0.7 CP/decade, 90% range -2.2 to +0.8, p = 0.36, "no clear trend"; safe chill 67.4 (1981-2000) vs 64.6 CP (2006-2025) |
| Cached `/api/point` responds in under 1 second | PASS: 0.21-0.23 s for all six demo pins; a new pin (Visalia area) 7.2 s first, 0.25 s cached |

Products now default to E4 (validated best). Live season E4 reads 0.00 CP so far at every demo pin on 2026-10-23, matching FNRIC's real stations (all 0 CP). Error bars in October are about ±0.5 CP (validated growth curve); foothill pin ±1.3.

**GATE 4 PASSED**

## GATE 5 (2026-10-24 03:55): PASSED

| Check | Result |
| --- | --- |
| First-time user to a verdict in 3 clicks or fewer | PASS: 2 clicks (quick-pick or map pin, then crop; the first variety is preselected). Real-API run: Durham + Pistachio shows "Watch: 10 in 10 similar winters reached Kerman's 54 CP by Mar 1", 0 CP so far ±1 (early season) |
| No mock numbers in production paths | PASS: production build (`NEXT_DIST_DIR=.next-prod next build`) has 0 files containing mock data; mocks load only behind `NODE_ENV !== "production"`; `public/demo` is the real export (no "mock" key, checked on write) |
| Works at 375 px and 1440 px | PASS: headless Edge at 375x812 (bottom sheet peek/half/full, no horizontal scroll, no console errors) and 1440x900 (map + 440 px panel) |
| Lighthouse accessibility >= 90; no color-only status | PASS: 100 on empty state, This winter, Land history and Accuracy; status pills always carry an icon and a word |
| Time machine plays 2014-15 smoothly and the verdict updates as it plays | PASS: time-based playback (~10 days/s, frames skipped rather than slowed), verdict pill, sentence, ring and odds update each frame; tested online and offline |

Offline (Phase 7 rehearsal): with the tile server, geocoder and API blocked, the demo flow runs end to end from `public/demo` (offline basemap image, "Offline: showing saved demo data", replay, land history, accuracy).

## GATE 6 (2026-10-24 03:40): PASSED (two upgrades shipped, two labeled features shipped, one held, one skipped)

| Upgrade | Check | Before | After | Shipped? |
| --- | --- | --- | --- | --- |
| 1. E7 ML night-low correction (LightGBM, LOSO, TPI from AWS Terrain Tiles) | must beat the default on hidden stations **and** Wildeye | default E4: 3.45 CP hidden (826), 3.53 Wildeye (30) | E7: 4.25 hidden, 4.19 Wildeye (it does improve Daymet: Tmin RMSE 2.07 -> 1.71 °C, E3 4.96 -> 4.25) | **No.** Shown on the Accuracy page as "not shipped" |
| 2. ML hourly shape (LightGBM on hour, day length, Daymet range and solar, month, latitude; station-grouped 8-fold CV) | must beat Method B on hidden stations | Method B (E3) 4.94 CP; textbook curve (E2) 4.20 | ML shape 3.55 CP, bias -2.07 (same 832 station-winters) | **Yes**, as the fallback for winters with no complete station record (Durham: 1980-81, 1981-82, 1982-83). The E4 default (3.47) is unchanged |
| 3. Sunny-stretch flag (station solar, 7+ near-clear days in 14) | heuristic, labeled | no flag | fires on 34-40% of dormant mid-month dates at Shafter/Durham 2005-2025 with an 85% clear-sky threshold (70% fired on 65-71%) | **Yes**, display-only, labeled a heuristic with the TreeChill citation; no metric affected |
| 4. Orchard mask (DWR crop mapping) | - | - | - | **Skipped**: statewide crop-mapping shapefiles are large and the grid already restricts to valley and foothill land under 600 m; not worth the risk before the deadline |
| 5. Global pin, Sfax (ERA5 via Open-Meteo, same engine) | labeled "Lower resolution, not validated here" | - | Kerman red; met the need in 0 of 46 winters; -5.0 CP/decade (p = 0.001) | **Yes**, labeled; exported for offline use |

Nothing shipped makes a headline metric worse: the validation table and the E4 default are untouched; the fallback winters improve from 4.20 to 3.55 CP typical miss.

## GATE 7 (2026-10-24 04:10): PARTIAL (the open items need the team's accounts)

| Check | Result |
| --- | --- |
| Offline demo passes end to end | PASS (emulated): the demo script runs from `web/public/demo` with the tile server, geocoder and API blocked in headless Edge (offline basemap image, saved data notice, replay, land history, accuracy). Recommend one real Wi-Fi-off rehearsal on the demo laptop |
| Deployed URL works on a phone | **Not done, by decision**: the team chose to run locally (`scripts/start_local.ps1`, production build checked on :3100). Mobile layout verified at 375 px |
| README shows real validation numbers | PASS: generated from `validation_summary.json` by `scripts/readme_table.py` |
| Submission is in | **Not done**: needs the team's Unite Ideas account. Text ready in `SUBMISSION.md` (code, demo and video links to fill). Backup video: record the README demo script with Win+Alt+R (no ffmpeg here) |

GitHub: skipped by decision; the repo is committed locally and ready to publish (`gh auth login`, then create a public repo and push).

## Statistical check of the default, and a pre-registered test (2026-10-24 05:52)

Paired cluster bootstrap (resampling whole stations, 5,000 draws) on 855 hidden station-winters, `validation/significance.py`:
- E4 vs nearest station (E0): -0.42 CP, 95% CI -1.22 to +0.12. **Not conclusive overall.** Conclusive at 25-50 km (-0.51, CI -0.96 to -0.04) and under 10 km (-0.50, 6 stations); no difference at 10-25 km.
- E4 vs 3-station average (E1): tie (+0.02, CI -0.80 to +0.53). E4 vs E2 and E3: E4 better (CIs exclude zero).
- Wildeye orchards, E4 vs E0: +0.11, CI -0.37 to +0.63 (no difference).
- Split-sample: chosen on 2005-14, E4 still beats E0 on 2015-26 (3.23 vs 3.60); chosen on half the stations (E1 wins that half), both E1 and E4 beat E0 on the other half (3.84, 3.51 vs 4.28).
- Corrected claim: E4 clearly beats the gridded methods; its edge over the nearest station is real at 25-50 km but not proven overall. The decisive gain is an orchard's own daily reading (E5, 1.56 CP; CI vs E4 excludes zero).

**Pre-registered test, written before running it.** E8 = the three nearest stations with a complete record that winter, each shifted to the pin by the Daymet monthly offset (as in E4), averaged hour by hour with 1/distance² weights (the same weights as E1). No tuned parameters. E8 replaces E4 as the default only if all three hold:
1. paired cluster-bootstrap 95% CI of (E8 - E4) on the 855 hidden station-winters lies entirely below zero;
2. it beats E4 in both split-sample halves (2015-26 winters; second half of stations);
3. it is not worse than E4 at the Wildeye orchards (mean difference <= 0).
Otherwise E4 stays and E8 is reported as tested.

**Result (run after the criteria above were written):** E8 MAE 3.26 vs E4 3.44 CP. (1) E8 - E4 = -0.19 CP, 95% CI -0.42 to +0.07: **fails** (interval includes zero). (2) beats E4 on both held-out halves (3.04 vs 3.23 on 2015-26; 3.23 vs 3.51 on the other stations): passes. (3) Wildeye: +0.12 CP worse than E4: **fails**. **E8 not adopted; E4 stays the default.** E8 is shown on the Accuracy page as "tested, not adopted".

## Scientific review and grower readings (2026-10-24 10:00)

Question from the user: are we really closing Julia's gap? Full write-up in RESEARCH.md.

- Literature: the largest Central Valley in-orchard study (Martinez-Luscher et al. 2022, 731 Semios stations) found CIMIS-only kriging explains under 10% of the spatial variation in winter chill (RMSE 3.7 CP); only dense in-orchard networks reach 2.4 CP. Our E4 (3.44 CP typical miss on 855 hidden-station winters) sits at that public-data floor.
- Tested today, leave-one-station-out: shrinking the Daymet offset (hidden 3.95 vs 3.91 CP; orchards 3.29 vs 3.53) and stacking E0/E1/E4 (hidden MAE 3.71 but RMSE worse). Neither improves both tests; not shipped.
- The answer to the gap is local data, which the product could not take until now. New `engine/chillprint/validation/orchard_readings.py` (real data): a site's own daily low/high from Sep 1 brings the typical miss to 1.84 CP at 18 Wildeye pistachio orchards (30 winters; station-only 3.52 with bias +2.29, readings bias -0.05) and 1.56 CP at hidden stations. From Nov 1: 1.75 / 1.67; Dec 1: 2.16 / 2.19; Jan 1: 2.77 / 2.64.
- Shipped: `POST /api/orchard` (daily lows/highs or logger readings, °F/°C; gaps up to 4 days or 6 logger hours filled, longer gaps and days before the readings use E4; one Dynamic Model run over the merged winter; error bar = P80 for the matching start date from the in-orchard test). Web: optional step 3 "Your orchard's own readings" with CSV upload and a real example (Terra Bella Wildeye sensor, winter 2025-26: readings 68.2 CP vs the sensor's hourly truth 69.5 and the station estimate 70.2). Accuracy tab shows the start-date table.
- Hosting: Firebase Hosting (thechill-d4688.web.app) with /api/** on Cloud Run (chillprint-api, us-west1).

## Live CIMIS, fixed (2026-10-24 10:30)

- Root cause of the "Request Rejected" pages: the `.env` key line held the 32-character key plus ~700 spaces and a stray character, sent whole in the header; CIMIS's firewall rejected it from every address (a test from Google Cloud without a key reached CIMIS normally, 401). My earlier "CIMIS accepts again" probe was a cache hit. `config.cimis_key()` now takes the first token; with it, CIMIS answers from home and from Cloud Run.
- Live refresh every 3 hours (this month re-pulled once per 3-hour block, one request per station). If CIMIS refuses, the rest of the cycle uses FNRIC `stemwater`, which relays the same CIMIS hours: on 300 Davis hours, shifted from hour-beginning to hour-ending labels, 96% identical and the rest within 0.1 °F, with the same QC flags. Container clock set to Pacific time. `/api/health` reports sources, latest hour and age.
- METHODS.md: every formula, plus why daily lows and highs cut the error (sensitivity: 1 °C on every hour = about 10 CP by Mar 1; readings remove the +2.29 CP orchard bias and cut scatter from 3.57 to 2.28 CP).

## Known traps checklist (BUILD.md section 9)

- [x] FNRIC `chill-year` in two-year form (asserted in `fnric.chill_models`); arrays sorted; daily values cumulated
- [x] CIMIS hours 0100..2400 PST, 2400 -> 00:00 next day; QC flags handled (blank/Y/P kept, rest dropped and counted); one station-month per request
- [x] Daymet leap-year Dec 31 filled by interpolation and flagged
- [x] Gridded day window aligned: midnight PST, lag 0 (CIMIS r 0.951 / 0.986)
- [x] Dynamic Model never summed across segments; state carried (continuation test exact; outlook and replay continue from the saved state)
- [x] Analogs exclude the season being judged (outlook, replay and backtest)
- [x] GDD in °C, lower 5, upper 35; chill thresholds in °F (with float-safe rounding at thresholds)
- [x] Leakage caveat shown on the Accuracy page (PRISM skipped; the caveat covers Daymet)
- [x] "By" dates marked as needing confirmation (PROGRESS open questions, config note, in-app tooltip)
- [x] No mock numbers in production paths (0 files in the production build)
- [x] Words: "grower", not "farmer" (checked with grep)

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
- 01:25 CIMIS latency rose from 0.4 s to 4-5 s per month mid-pull. Switched to 3 workers sharing one global throttle (request starts still >= 0.3 s apart, BUILD.md 3.2); throughput back to ~28 station-seasons/min. Backfill (1982-83..2004-05) queued right after, because mixing Method L (bias -2.3 CP) before 2005 with Method B after would put a false step into land-history trends.
- 01:30 Error bar now scales through the season by the validated growth of hidden-station error (P80 at Nov 1/Dec 1/Jan 1/Feb 1 relative to Mar 1), so October's chill so far no longer carries the full by-date error. User chose: GitHub skipped for now (local commits only), demo runs locally (`scripts/start_local.ps1`).
- 02:00-04:10 Full validation on real data, E4 chosen, E7 not shipped, ML-shape fallback shipped, grid on E4, demo bundle re-exported (16.2 MB, 7 pins incl. Sfax), GATES 1-6 passed, README filled from the summary.
- 06:00-07:45 UI rework from user feedback: a three-step form (where is your orchard: Locate me / search / tap, or mark a block as a circle or drawn outline; what are you growing: crop then variety, with the need explained and sourced; Run analysis), a progress screen naming the real computation steps, and a plain-language answer card (verdict as a sentence, chill so far, expected by the need date, odds) with detail sections below. New `/api/area` checks up to 9 spots >= 1 km apart across a block (blocks over 100 km² refused). New pins build in ~3 s (the ML fallback now runs only for winters that need it; model and numba warmed at API start). Lighthouse accessibility 100; production build has no mock data.
- Contract note: `/api/heat` is added (not in section 7) because the Heat tab needs GDD by season. `/api/validation` carries additive fields (`by_station`, `diet_rule`, `e5_note`, `findings`) for the Accuracy tab. All section 7 fields are unchanged.
