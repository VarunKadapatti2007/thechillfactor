# ChillPrint Build Prompt

For: Claude Code, two sessions in parallel. Put this file at the repo root as `BUILD.md`. Read all of it before writing any code. Work one phase at a time. Every phase ends with a gate.

---

## 0. How to run this

### Two agents

| Agent | Owns | Language |
| --- | --- | --- |
| **A (engine)** | Data pipeline, science engine, validation, products, API | Python 3.11 |
| **B (app)** | The web app. Builds against mock JSON that follows the API contract (section 7), then switches to the real API | TypeScript, Next.js |

### Kickoff messages

- **Agent A:** "Read BUILD.md fully. You are Agent A. Do Phase 0 A-tasks, then continue phase by phase using the gate rule. Log everything in PROGRESS.md."
- **Agent B:** "Read BUILD.md fully. You are Agent B. Do Phase 0 B-tasks, then Phase 5a and 5b against web/mocks. Start 5c only when PROGRESS.md shows GATE 4 PASSED."

### Gate rule

At the end of each phase:
1. Run every check listed for that gate.
2. Write a `GATE N` block in `PROGRESS.md`: what passed, key numbers, known issues.
3. All checks pass: continue to the next phase.
4. A check fails: make two fix attempts. Still failing: stop and write what failed, why, and the smallest fallback.
5. Never mark a gate passed while a check fails. Never fake data to pass a check.

### Time budget

Deadline: Unite Ideas submission by **3:00 pm Saturday, Oct 24** (Davis). Stanford is due 5:00 pm. The venue opens at noon.

| Phase | Owner | Target finish |
| --- | --- | --- |
| 0. Setup, contract, data spike | A + B | 11:15 pm Fri |
| 1. Data pipeline | A | 1:30 am |
| 2. Science engine | A | 3:00 am |
| 3. Validation (long compute, runs unattended) | A | 7:00 am |
| 4. Products and API | A | 10:00 am |
| 5. App (5a and 5b from 11:15 pm; 5c after GATE 4) | B | 12:00 pm |
| 6. Gated upgrades | A | 12:00 pm, only if GATES 1 to 4 passed |
| 7. Demo hardening and submission | A + B | 2:30 pm |

Human checkpoints: confirm GATE 2 before sleeping. Read GATE 3 on waking.

---

## 1. Mission

### What we are building

ChillPrint answers one question for California fruit and nut growers: **is this winter enough for my trees, here?**

A grower drops a pin on their orchard and picks a crop and variety. ChillPrint estimates chill at that exact spot, not at the nearest CIMIS station. It shows a green, amber or red verdict against that variety's chill need, the past winter this one most resembles, the odds of reaching the need by a set date, and a measured error bar on every number.

### Who it serves

| User | Question | Feature |
| --- | --- | --- |
| Grower, PCA, crop consultant | Is this winter on track? | Verdict card, season chart, odds |
| FNRIC | Can we cover places with no station? | Open API, validation results |
| Land buyer, investor, new planting | Is this parcel a safe bet for a 20-year orchard? | Land history card: every winter since 1981 at the parcel |

### Julia's asks, mapped to features

| Her words, paraphrased | Feature |
| --- | --- |
| Color-coded good or bad year, quick to read | Verdict card (green, amber, red) |
| A station miles away is not my orchard | Any-pin estimate plus hidden-station validation |
| Can a daily high and low replace hourly data? | Hourly rebuild plus "one reading a day" test |
| Data has gaps | Data-diet test with a tolerance rule |
| How much chill so far, versus past years, and what's coming | Season chart, closest past winter, outlook odds |
| Land buyers and investors need more than a few past years | Land history card |

### Definition of done

- Drop a pin in the Central Valley, pick a crop and variety, see a verdict in under 2 seconds for cached pins, under 8 seconds for new pins.
- Every chill number shows an error bar that comes from the validation results.
- A validation table compares our method with "nearest station" on hidden stations, with real numbers.
- A time machine replays any past winter day by day.
- A land history card works for any pin, back to the 1980-81 winter.
- Six demo pins work fully offline.

### Rules for the agent

1. **Accuracy over features.** If something can't be validated, ship it labeled "Experimental" or don't ship it.
2. **No invented numbers in the product.** Every number in the UI traces back to a computed file. If data is missing, show "Not available."
3. **Cache every remote response to disk.** Reruns read from the cache. Never loop on the FNRIC API; it runs on a limited budget.
4. **Units.** Store °C internally. Display °F by default, with a °C toggle. Show chill in chill portions (CP).
5. **Time.** CIMIS hourly data is in Pacific Standard Time with no daylight saving. Keep hourly series in PST.
6. **Fixed random seeds** everywhere.
7. **Skip:** auth, security hardening, code review, CI, Docker, microservices, i18n. Keep the CIMIS key in `.env` (gitignored) because the repo will be public.
8. **Words.** Say "grower," never "farmer." Julia asked for this.
9. **Non-goals:** phenology modeling, irrigation or ET, replacing in-orchard sensors, rebuilding 2050 climate projections (link out instead).

---

## 2. Architecture

```
SOURCES                        ENGINE (engine/, Python)                    SERVING                 APP (web/)

FNRIC API ---------+
 stations, daily   |      1. Station store: CIMIS hourly, FNRIC daily
 chill truth,      |         chill, Wildeye raw  (Parquet)
 Wildeye raw       |
                   +----> 2. Pin store: Daymet daily min/max 1980-2025,
CIMIS API ---------+         elevation, nearest stations
 hourly temp,      |
 solar, humidity   |      3. Hourly rebuild: borrowed station shape
                   |         (fallback Linvill curve)
Daymet API --------+
 1 km daily        |      4. Chill + heat: Dynamic Model, chill hours,     FastAPI  ---------->  Next.js app
                   |         Utah, GDD (FNRIC single sine)                 (api/)                 map, verdict,
PRISM (optional) --+                                                       + static JSON          charts, time
                   |      5. Validation: hidden stations, Wildeye,         for demo pins          machine, land
Open-Meteo --------+         data diet, outlook backtest  -> error model   (offline mode)         history,
 forecast, ERA5,   |                                                                              accuracy page
 elevation         |      6. Products: outlook odds, verdict, closest
                   |         winter, time machine frames, land history
```

Repo layout:

```
chillprint/
  BUILD.md                this file
  PROGRESS.md             gate reports and log
  DATA_SOURCES.md         what each endpoint returned in the spike
  .env.example            CIMIS_APP_KEY=
  engine/
    chillprint/
      sources/            fnric.py cimis.py daymet.py prism.py openmeteo.py elevation.py
      science/            daylength.py hourly.py chill.py gdd.py
      pipeline/           build_station_store.py build_pin.py build_grid.py
      validation/         hidden_station.py wildeye.py data_diet.py backtest.py error_model.py report.py
      products/           outlook.py analogs.py verdict.py history.py replay.py
      api/                main.py schemas.py
      config.py           crops, varieties, windows, paths
    tests/
    data/                 raw/ cache/ processed/   (gitignored except data/demo/)
  web/
    app/ components/ lib/ mocks/ public/demo/
  scripts/                export_demo.py run_validation.sh
```

Python dependencies: pandas, numpy, numba, scipy, pyarrow, duckdb, requests, tenacity, tqdm, fastapi, uvicorn, pydantic, pymannkendall, pytest, xclim (test reference only). Phase 6 adds lightgbm and scikit-learn.

---

## 3. Data sources

Verify each source in the Phase 0 spike and record the real field names in `DATA_SOURCES.md`. If a source behaves differently from what's written here, trust what it actually returns and note the difference.

### 3.1 FNRIC API (primary truth for station chill)

- Base URL: `https://f5dby14cj5.execute-api.us-west-2.amazonaws.com/prod/`
- Public, no key, CORS enabled. **Limited budget: fetch each resource once, cache it, never loop.**
- Reference: https://github.com/ucdavis/fnric-reboot-the-eath-hackathon (read `FNRIC-Weather-Data-Cheat-Sheet.md` and `fnric-api.openapi.yaml` in Phase 0).

| Endpoint | Params | Use |
| --- | --- | --- |
| `GET stations` | none | 303 stations (277 CIMIS, 26 Wildeye; 172 active). IDs look like `CIMIS-6`, `Wildeye-111090` |
| `GET chill-models-download` | `station-id` | CSV of the full daily chill history: `Date, hours_lt_45, hours_32_45, units_utah, portions_dynamic`. **Ground truth for station chill.** |
| `GET chill-models` | `station-id`, `chill-year=2025-2026` | Daily rows plus `n_hours` (hours of data that day) |
| `GET stemwater` | `station-id` | Last 300 hourly readings in °F plus Dynamic Model state `dynmod_inter_e`, `dynmod_xi` |
| `GET almond-hull-split-gdd90` | `station-id`, `fbd` | 91 days of single-sine GDD (°C) from bloom |
| `GET wildeye` | `siteID`, `startDate`, `endDate`, `variables`, `format` | 302 redirect to raw in-orchard data (air temp, RH, solar, wind). **Independent truth.** |

FNRIC gotchas (from their cheat sheet):
- `chill-year` must be the two-year form `2025-2026`; `2025` returns an empty array with status 200.
- Arrays are unsorted. Sort by `Date` or `Timestamp`.
- Values are daily amounts, not running totals. Take the cumulative sum yourself.
- FNRIC's season starts Sept 1. Many growers count from Nov 1. Support both, label which.
- Rows with `n_hours < 24` have missing data. Flag them.
- Lat and lon are strings like `"36º20'10N / 36.336222"`. Use the number after `/`.
- Hull-split GDD is in °C; chill thresholds are in °F.
- Data refreshes from CIMIS every 3 hours.

### 3.2 CIMIS Web API (hourly temperature, solar radiation)

- Register at cimis.water.ca.gov ("New CIMIS"); phone number digits only. The app key is on the account page.
- Station list (no key): `https://et.water.ca.gov/api/station`. Use it for elevation and coordinates.
- Data request pattern (key goes in header `Ocp-Apim-Subscription-Key`, never in the URL):
  ```
  https://et.water.ca.gov/StationWeb/GetDataByStationNumber?stationNbrs=6&startDate=2014-11-01&endDate=2014-11-30&isHourly=true&unitOfMeasure=M&dataItems=hly-air-tmp,hly-sol-rad,hly-rel-hum
  ```
- Response: `Data -> Providers -> Records`. Each value carries a QC flag. Treat flagged values as missing unless the flag is documented as acceptable; log counts per station.
- **Request one station and one month at a time.** Large requests are refused. Retry with backoff (tenacity), sleep 0.3 s between calls, checkpoint progress so the pull can resume.
- Hours run `0100` to `2400` PST. Map `2400` to 00:00 of the next day.
- Durham (station 12, Butte County) stopped reporting in July 2025. It's the hero case study.

### 3.3 Daymet single-pixel API (pin history, 1 km daily)

- No key. Example:
  ```
  https://daymet.ornl.gov/single-pixel/api/data?lat=39.62&lon=-121.80&vars=tmax,tmin,srad,dayl&start=1980-01-01&end=2025-12-31
  ```
- Returns CSV with header lines before the table; parse robustly by finding the `year,yday` header row.
- Historical only: data ends with the last full year. No current season.
- **Calendar trap:** Daymet uses 365-day years. In leap years it drops Dec 31. Fill Dec 31 by linear interpolation and flag it.
- Confirm in Daymet's documentation which station networks feed it. If CIMIS isn't an input, Daymet is the lower-leakage grid for validation (section 5.3).

### 3.4 PRISM 800 m daily (optional; best terrain handling)

- Free to the public at 800 m since March 2025. Access through PRISM's web services or FTP, or Earth Engine `OREGONSTATE/PRISM/AN81d` if a teammate has access.
- The PRISM day runs from 1200 UTC to 1200 UTC and is labeled by the day it ends.
- PRISM models temperature inversions, which matters for valley cold pools.
- PRISM dailies use hourly stations, which likely include CIMIS. Treat any PRISM result on CIMIS stations as **possibly leaked** (section 5.3).
- PRISM warns against century-long trend analysis. Our 45-year trends are indicative only; say so.
- Use PRISM only if the Phase 0 spike shows point extraction is fast. Otherwise skip it.

### 3.5 Open-Meteo (forecast, global pin, elevation)

- Forecast: `https://api.open-meteo.com/v1/forecast?latitude=..&longitude=..&hourly=temperature_2m&forecast_days=16&timezone=America/Los_Angeles`
- Historical (ERA5, any location, decades back): used for the global demo pin and as a last-resort fallback.
- Elevation endpoint for pins, or USGS EPQS as a fallback. Verify in the spike.
- Free for non-commercial use; credit Open-Meteo (CC BY 4.0).

### 3.6 Crop chill needs (UCCE, compiled by Katherine Pope)

| Crop | Variety | Need (CP) | Default "by" date |
| --- | --- | --- | --- |
| Almond | Nonpareil | 22 to 23 | Feb 1 (CONFIRM WITH FNRIC) |
| Almond | Desmayo Largueta | 28 | Feb 1 (CONFIRM) |
| Almond | Ferragnes | 32 | Feb 1 (CONFIRM) |
| Pistachio | Kerman | 54 to 58 | Mar 1 (CONFIRM) |
| Pistachio | Peters | 60 to 65 | Mar 1 (CONFIRM) |
| Walnut | Chandler | 45 to 50 | Mar 1 (CONFIRM) |
| Prune | Improved French | 55 to 60 | Mar 1 (CONFIRM) |
| Cherry | Brooks | 37 | Feb 15 (CONFIRM) |
| Apple | Golden Delicious | 50 | Mar 1 (CONFIRM) |

Store this table in `config.py` with its source. "By" dates are placeholders: make them editable in the UI and list them as an open question for Julia in PROGRESS.md.

---

## 4. Science spec

### 4.1 Seasons and windows

- Season label: `2014-2015`. Default start: **Sept 1** (matches FNRIC's calculator). Option: Nov 1.
- Store hourly and daily series for Sept 1 through Mar 31.
- Handle Feb 29 by day-of-season indexing, not calendar day.

### 4.2 Chill models (FNRIC definitions, hourly °F)

| Model | One hour counts as |
| --- | --- |
| Hours below 45 | 1 if T <= 45, else 0 |
| Hours 32 to 45 | 1 if 32 < T <= 45, else 0 |
| Utah | T <= 34: 0; 34 < T <= 36: 0.5; 36 < T <= 48: 1; 48 < T <= 54: 0.5; 54 < T <= 60: 0; 60 < T <= 65: -0.5; T > 65: -1 |
| Dynamic (CP) | Section 4.3. **Headline metric.** |

### 4.3 Dynamic Model

Constants (Fishman et al., as used in chillR and xclim):

```
E0 = 4153.5      E1 = 12888.8
A0 = 1.395e5     A1 = 2.567e18
slope = 1.6      Tf = 277.0 (K)
```

Reference loop (temperature in °C, one value per hour). Treat it as a guide; the tests decide what's correct:

```python
TK = T_c + 273.0
aa = A0 / A1
ee = E1 - E0
sr = exp(slope * Tf * (TK - Tf) / TK)
xi = sr / (1 + sr)
xs = aa * exp(ee / TK)
ak1 = A1 * exp(-E1 / TK)

inter_e_prev, xi_prev = state_in  # (0.0, 0.0) at season start
for i in range(n):
    S = inter_e_prev if inter_e_prev < 1 else inter_e_prev - inter_e_prev * xi_prev
    inter_e = xs[i] - (xs[i] - S) * exp(-ak1[i])
    portion[i] = inter_e * xi[i] if inter_e >= 1 else 0.0
    inter_e_prev, xi_prev = inter_e, xi[i]
cumulative = cumsum(portion)
```

Requirements:
- Implement with numba. Accept an input state `(inter_e, xi)` and return the final state, so a series can be continued. FNRIC's `stemwater` exposes the same state.
- **Never add CP totals from separate segments.** For outlooks, run the model over the concatenated hourly series (observed plus scenario) or continue from the saved state.
- Tests (GATE 2):
  - Matches `xclim` chill portions on the same hourly series within 0.05 CP over a full season. If the reference loop above disagrees with xclim by an index offset, match xclim and document it.
  - Run on CIMIS-6 (Davis) hourly for three seasons. Season totals must match FNRIC `portions_dynamic` cumulative within 0.5 CP, and daily increments must correlate above 0.99. Investigate any day-level mismatch (QC handling, hour mapping).
  - Spot-check season-to-date against the FNRIC chill calculator page for Davis.

### 4.4 Heat units

- GDD: use FNRIC's single-sine function **verbatim** (°C, lower 5, upper 35), from their cheat sheet:

```python
from math import asin, cos, pi

def gdd_single_sine(tmin, tmax, lo=5.0, hi=35.0):
    mean, a = (tmax + tmin) / 2, (tmax - tmin) / 2
    if tmin >= hi: return hi - lo
    if tmax <= lo: return 0.0
    if tmax <= hi and tmin >= lo: return mean - lo
    if tmax <= hi:  # tmin < lo
        s1 = asin((lo - mean) / a)
        return ((mean - lo) * (pi / 2 - s1) + a * cos(s1)) / pi
    if tmin >= lo:  # tmax > hi
        s2 = asin((hi - mean) / a)
        return ((mean - lo) * (s2 + pi / 2) + (hi - lo) * (pi / 2 - s2) - a * cos(s2)) / pi
    s1, s2 = asin((lo - mean) / a), asin((hi - mean) / a)
    return ((mean - lo) * (s2 - s1) + a * (cos(s1) - cos(s2)) + (hi - lo) * (pi / 2 - s2)) / pi
```

- Clip every `asin` argument to [-1, 1] so floating-point rounding can't raise a domain error. (When `tmax == tmin`, the early branches return before any division, so no extra guard is needed.)
- Test: 10,000 random (tmin, tmax) pairs against numeric integration of a sine over the day, tolerance 1e-3 °C-days.
- Spot-check against FNRIC `almond-hull-split-gdd90` for one station and bloom date.
- GDD runs from a bloom date the user picks, not from the chill season start.

### 4.5 Hourly rebuild from daily min and max

Two methods. Both must exist; validation decides the default.

**Method L (Linvill curve).** Port chillR's `daylength` and `stack_hourly_temps` / `make_hourly_temps` logic (sine by day, log decay at night, sunrise and sunset from latitude). chillR is GPL-3: if you port its code, license the repo GPL-3; if you implement from Linvill (1990), any license works. Test vectors from the chillR vignette (tolerance 1e-3):

- `daylength(lat=50.4, JDay=15)`: sunrise 7.766425, sunset 16.23357, daylength 8.467149
- `daylength(lat=50.5, JDay=1)`: sunrise 7.962814, sunset 16.03719, daylength 8.074373
- Lat 50.4, day 1 (Tmax 8.2, Tmin 5.1), day 2 (Tmax 9.1, Tmin 5.0):
  - Day 1 hours 19 to 23: 6.424223, 6.203183, 6.022917, 5.870701, 5.738969
  - Day 2 hours 0 to 5: 5.574983, 5.468975, 5.373123, 5.285650, 5.205208, 5.130750

**Method B (borrowed station shape).** For each day window W, take the nearest CIMIS station's actual hourly curve that day and rescale it to the pin's min and max:

```
T_pin(h) = Tmin_pin + (T_st(h) - Tmin_st,W) / (Tmax_st,W - Tmin_st,W) * (Tmax_pin - Tmin_pin)
```

- Compute the station's min and max over the **same window definition** as the gridded product (section 4.6).
- If the station range is under 0.5 °C or the station day has more than 4 missing hours, fall back to the next nearest station, then to Method L.
- Blend linearly across plus or minus 3 hours at window boundaries to avoid jumps.
- This keeps foggy days flat and clear nights sharp, which Method L can miss.

### 4.6 Day alignment (do not skip)

Gridded "days" are not calendar days (PRISM's runs 1200 UTC to 1200 UTC). For each gridded product, compute station daily min and max under candidate windows (midnight to midnight PST; 4 am to 4 am PST; 7 am to 7 am PST) and lag 0 or -1 day. Pick the alignment with the highest correlation to the gridded values at station pixels. Record it in DATA_SOURCES.md. A one-day misalignment silently adds error.

### 4.7 Outlook (odds of reaching the need)

FNRIC's own method is "observed so far + forecast + historical average, shown as a band." We extend it to a full distribution:

1. Observed hourly at the pin from season start to the as-of date `d`.
2. Live mode only: next up to 16 days from the Open-Meteo hourly forecast, shifted by the mean difference between Open-Meteo and the pin's estimate over the previous 14 days.
3. For each past season `y` (1980-81 to 2024-25, **excluding the season being judged**), append season `y`'s rebuilt hourly temperatures at the pin from the day after the forecast through the "by" date.
4. Run the Dynamic Model over each concatenated series. The result is about 45 possible CP totals at the by date.
5. Report P10, P50, P90, the chance of reaching the low end of the need, and the chance of reaching the high end. Produce a daily fan (P10, P50, P90) for the chart.
6. **Today's-climate option (default on):** before step 3, shift each past season's daily Tmin and Tmax by `slope_month * (current_year - y)`, where `slope_month` is the Theil-Sen trend of that month's mean Tmin or Tmax at the pin over 1981 to 2025. Then rebuild hours. Validation (section 5.6) decides whether this stays default.

### 4.8 Verdict and closest winter

With final distribution F at the by date and need range [low, high]:
- **Green, "On track":** P10(F) >= high
- **Red, "At risk":** P50(F) < low
- **Amber, "Watch":** everything else
- Before Nov 15, add the label "Early season: mostly past winters."

Sentence template: "{k} in 10 similar winters reached {variety}'s {low} CP by {by_date}." Round k from the chance of reaching low.

Closest past winter: compare this season's cumulative CP curve over the last 30 days up to `d` with each past season's curve over the same days (RMSE in CP). Return the best match and its RMSE. Exclude the current season.

### 4.9 Land history (per pin)

- CP at the by date for every winter 1980-81 to 2024-25 (Daymet, Method B with Method L fallback). For 2025-26, Daymet lacks Jan and Feb 2026: fill using the nearest station plus the Daymet monthly pin-minus-station offset (method E4, section 5.2) and label it.
- Share of winters meeting low and high need, per variety.
- Trend: Theil-Sen slope of CP versus winter start year, with a 90% interval; Mann-Kendall p-value. If p > 0.1, say "No clear trend."
- Safe winter chill (10th percentile, Luedeling's standard) for 1981-2000 winters and for 2006-2025 winters. Add bootstrap intervals; 20 winters make a noisy P10.
- Today's-climate replay: the 45 winters shifted to the current climate (section 4.7 step 6), giving a current safe-chill estimate.
- Links out for 2050: UC ANR Projected Winter Chill app and Cal-Adapt. Don't rebuild projections.

### 4.10 Error bar per pin

From validation (section 5), build a lookup of the 80th-percentile absolute CP error at the by date, binned by:
- distance to the nearest CIMIS station: 0 to 10, 10 to 25, 25 to 50, over 50 km
- terrain: valley floor versus foothill (pin elevation minus nearest-station elevation over 100 m, or pin above 150 m)

Display it as "±X CP" with the tooltip "8 in 10 hidden-station tests landed within this range." Keep it separate from the outlook band: the error bar is estimation error, the band is weather uncertainty.

---

## 5. Validation protocol

This is the credibility core. Results go to `engine/data/processed/validation/` and feed the Accuracy page.

### 5.1 Station set

- Central Valley and foothill CIMIS stations (Butte, Colusa, Fresno, Glenn, Kern, Kings, Madera, Merced, Placer, Sacramento, San Joaquin, Shasta, Solano, Stanislaus, Sutter, Tehama, Tulare, Yolo, Yuba counties), active and inactive.
- Keep station-seasons with at least 95% of hours present from Sept 1 to Mar 1.
- Winters: 2005-06 to 2025-26 for the main test; older winters where available.
- Truth: the station's own CP (our engine on its CIMIS hourly, cross-checked against FNRIC daily chill).

### 5.2 Estimators (hide station S, then estimate S without its data)

| ID | Method | What it represents |
| --- | --- | --- |
| E0 | Nearest other station's CP | What growers do today |
| E1 | Inverse-distance average of the 3 nearest stations' CP | Simple spatial baseline |
| E2 | Daymet daily at S + Method L | Gridded, textbook curve |
| E3 | Daymet daily at S + Method B (nearest other station's shape) | **Candidate default for history** |
| E4 | Nearest station hourly + Daymet monthly offset (Daymet at S minus Daymet at the station, per month, 2010 to 2025) | **Candidate default for the live season** (works in real time) |
| E5 | S's own daily min and max + Method B | "Add one reading a day" (sensor simulation) |
| E6 | PRISM daily at S + Method B (optional) | Best terrain grid; possible leakage |
| E7 | ML correction (Phase 6) | Only if it beats E3 and E4 |

### 5.3 Leakage check

Gridded products may ingest CIMIS observations, so a "hidden" CIMIS station can still leak into the estimate. Defenses:
1. Report Daymet (E2, E3) and PRISM (E6) separately. If PRISM is much better than Daymet only at CIMIS sites, suspect leakage.
2. **Independent test on Wildeye in-orchard stations** (26 stations, pistachio orchards) through the FNRIC `wildeye` endpoint. These are private in-orchard sensors that gridded products very likely don't ingest (confirm with Carson or Julia). Build hourly CP truth from their air temperature and run E0, E3 and E4 there. This is the headline "at the orchard" result.
3. State the leakage caveat on the Accuracy page in one sentence.

### 5.4 Metrics

For each estimator, across station-seasons:
- Mean absolute CP error at the by dates (Feb 1, Mar 1), median, 80th and 90th percentile, mean bias
- Error in the date a station crosses 23 CP and 54 CP (days)
- Hourly temperature RMSE (E2, E3, E5)
- GDD error over 90 days from a fixed bloom date
- Breakdown by distance to nearest station and by terrain class

Output: `validation_summary.json`, `validation_by_station.parquet`, `error_model.json`.

### 5.5 Data-diet test

For complete station-seasons, delete 0, 5, 10, 20, 30, 40 and 50% of days (random and in blocks of 3, 7 and 14 days). Fill daily min and max by linear interpolation, rebuild hours (Method B), compute CP. Report CP error against the missing fraction and the longest gap. Derive a plain rule like "Up to N% missing days, or gaps up to K days, keeps error under 2 CP." N and K come from the data.

### 5.6 Outlook backtest

For every station-season and as-of dates Dec 1, Jan 1 and Feb 1:
- Compute the predicted chance of reaching each variety's low need by its by date, using analogs that **exclude the season being tested**.
- Compare with the outcome. Report the Brier score against a climatology baseline (the plain share of past winters that met the need), plus a reliability table (predicted bins versus observed frequency).
- Run with and without the today's-climate shift. Keep whichever scores better as the default; report both.

### 5.7 Durham case study

Station 12 closed in July 2025. For its last 15 winters, compare truth, E0 (what Butte County growers now get from the nearest station), E3 and E4. Export a small JSON for the pitch: per-winter truth, E0, E3 and E4 values, plus mean errors.

---

## 6. Design spec

### 6.1 Principles

- One question, one screen. A grower should understand the verdict in 3 seconds without reading a paragraph.
- Show, then explain. Every section has one sentence and an Info icon that opens a 2 to 3 line explanation.
- Calm, agricultural, trustworthy. No gradients, glow, glassmorphism, confetti, emoji, or "AI-powered" badges.
- Color is never the only signal: every status color pairs with an icon and a word.

### 6.2 Layout

- Desktop: full-bleed map on the left (about 60%), a 440 px results panel on the right.
- Mobile: map full screen with a draggable bottom sheet (peek, half, full).
- Header: wordmark "ChillPrint", subtitle "Chill for your orchard, not the nearest station", place search, °F/°C toggle, help icon.

### 6.3 First run (onboarding)

Three coach marks, each at most 8 words, with dismiss and "Show me how" to replay:
1. "Drop a pin on your orchard" (pointing at the map)
2. "Pick your crop and variety"
3. "Read your verdict here"

Empty panel state: a short prompt plus three quick-pick demo orchards ("Durham, Butte Co.", "Parlier, Fresno Co.", "Shafter, Kern Co.") and a "Replay winter 2014-15" button.

### 6.4 Results panel

Four tabs in a segmented control with icons:

**1. This winter** (`Snowflake`)
- Verdict hero: status pill with icon (`CircleCheck`, `TriangleAlert`, `OctagonAlert`), the word (On track, Watch, At risk), one sentence from section 4.8.
- Ring gauge: CP so far against the need band.
- Three stat tiles: "Chill so far: 31 CP ±3" (example format), "Need: 54 to 58 by Mar 1", "Closest past winter: 2014-15".
- Season chart: past winters as faint lines, this season bold, need band shaded, outlook fan (P10 to P90) from today to the by date, a "today" marker.
- "Compare with a year you remember": a year picker that highlights that winter's line. (Julia: growers remember "2020 was good, 2017 was bad.")
- Time machine: "View as of" date scrubber plus a Play button that animates a past season day by day. The verdict and odds update live.
- Optional chip: "Sunny stretch: tree chill likely lower" (Phase 6).

**2. Land history** (`History`)
- Headline: "Met Kerman's need in __ of 45 winters" (filled from data).
- Bar chart: one bar per winter since 1980-81, colored met or not met, with the trend line.
- Two tiles: safe winter chill, 1981-2000 versus 2006-2025; trend per decade with "likely" or "no clear trend."
- "Next 20 years" link cards to the UC ANR Projected Winter Chill app and Cal-Adapt.

**3. Heat** (`Sun`)
- Bloom-date picker, GDD since bloom versus past seasons, a link to FNRIC's hull-split model.

**4. Accuracy** (`ShieldCheck`)
- Plain line: "We hid __ stations and predicted them. Typical miss: __ CP. Nearest station: __ CP." (filled from data)
- Bar comparison of estimators E0 to E5.
- Map of hidden-station errors.
- Wildeye in-orchard result.
- Data-diet slider: drag the missing-days percentage and watch the expected error update from the precomputed curve.
- "One reading a day" explainer from E5.
- The leakage caveat in one sentence.

### 6.5 Map

- MapLibre GL via react-map-gl. Basemap: OpenFreeMap Positron (no key). Offline fallback: a pre-rendered Central Valley PNG as an image source.
- Layers (toggle in a small layer menu, icon `Layers`): CIMIS stations (active filled, inactive hollow, Durham labeled "Closed Jul 2025"), Wildeye stations, and a grid layer colored by safe winter chill or chill so far, with a legend.
- Pin: drag to move, spring drop animation, a pulse while loading.
- Place search: Photon (komoot) geocoder, which needs no key, plus support for pasted "lat, lon."

### 6.6 Visual system

- Font: Inter, with `font-variant-numeric: tabular-nums` for all numbers.
- Type scale: 28/20/16/14/12; weights 600 for headings, 400 for body.
- Colors (define as CSS variables, check AA contrast):
  - background `#F7F6F2`, surface `#FFFFFF`, ink `#1F2A24`, muted `#5B6660`, line `#E3E1DA`
  - brand `#2E6A4F`, chill accent `#3B7EA1`, heat accent `#C8742B`
  - status: good `#2F855A`, watch `#B7791F`, risk `#C53030`
- Radius 12 px for cards, 8 px for controls. Soft single shadow only on the floating panel.
- Icons: lucide-react only (`MapPin`, `Snowflake`, `Sun`, `History`, `ShieldCheck`, `Info`, `CalendarClock`, `Play`, `Pause`, `Layers`, `Search`, `TrendingDown`, `TreeDeciduous`, `Nut`, `Cherry`, `Apple`, `CircleCheck`, `TriangleAlert`, `OctagonAlert`).

### 6.7 Motion (Framer Motion)

- 150 to 300 ms, ease-out. Panel content fades up 8 px. Numbers count up over 600 ms. Chart lines draw in once over 800 ms. The time machine runs at about 10 days per second.
- Respect `prefers-reduced-motion`: no draw-ins or count-ups.

### 6.8 Copy rules

- Labels at most 8 words. One sentence per section.
- Grower words: "chill portions" with an Info tooltip ("A chill unit that counts cool hours and discounts warm spells. UC recommends it for California."), "need," "by Mar 1."
- Ranges as "54 to 58." Odds as "7 in 10," never "70% probability."
- Always show units and the season start ("Counting from Sep 1").
- Never write: unlock, empower, revolutionize, seamless, AI-powered.

### 6.9 States

- Loading: skeletons shaped like the final content, never a blank panel.
- Error: one line plus "Try again," and the app falls back to cached demo data when offline.
- Before the chill season has meaningful data: "Chill season just started. Explore a past winter meanwhile," with the Replay button.

---

## 7. API contract (FastAPI)

Agent B builds mocks from these shapes in `web/mocks/` with `"mock": true` at the top level. Agent A must return exactly these shapes. Every response includes `sources` (list of strings) and `method` (estimator ID used).

`GET /api/crops`
```json
{"crops":[{"id":"pistachio","name":"Pistachio","icon":"Nut","varieties":[{"id":"kerman","name":"Kerman","need_low":54,"need_high":58,"by_date_default":"03-01"}]}],"source":"UCCE, K. Pope"}
```

`GET /api/stations`
```json
{"stations":[{"id":"CIMIS-12","name":"Durham","network":"CIMIS","lat":39.6,"lon":-121.8,"elev_m":0,"active":false,"closed":"2025-07"}]}
```

`GET /api/point?lat=&lon=&crop=&variety=&asof=YYYY-MM-DD&start=sep1|nov1&by=MM-DD&climate=today|recorded`
```json
{
  "location":{"lat":0,"lon":0,"elev_m":0,"nearest_station":{"id":"","name":"","dist_km":0}},
  "season":"2014-2015","asof":"2015-01-15","start":"sep1","method":"E3",
  "chill":{"to_date":0,"error_cp":0,"series":[{"date":"","cp":0}]},
  "need":{"low":54,"high":58,"by":"2015-03-01"},
  "outlook":{"p10":0,"p50":0,"p90":0,"chance_low":0,"chance_high":0,"n_analogs":45,
             "fan":[{"date":"","p10":0,"p50":0,"p90":0}]},
  "past_seasons":[{"season":"","series":[{"date":"","cp":0}]}],
  "closest":{"season":"","rmse_cp":0},
  "verdict":{"level":"green|amber|red","label":"On track|Watch|At risk","sentence":"","early":false},
  "flags":{"sunny_stretch":null,"data_gaps_days":0},
  "sources":[]
}
```

`GET /api/history?lat=&lon=&crop=&variety=&by=MM-DD`
```json
{
  "winters":[{"season":"1980-1981","cp_by":0,"met_low":true,"met_high":false,"filled":false}],
  "share_met_low":0,"share_met_high":0,
  "trend":{"cp_per_decade":0,"ci90":[0,0],"p_value":0,"label":"likely decline|no clear trend|likely increase"},
  "safe_chill":{"early":{"years":"1981-2000","p10":0,"ci":[0,0]},"recent":{"years":"2006-2025","p10":0,"ci":[0,0]},"today_replay":{"p10":0,"p50":0}},
  "links":[{"title":"UC ANR Projected Winter Chill","url":""},{"title":"Cal-Adapt","url":"https://cal-adapt.org/"}],
  "sources":[]
}
```

`GET /api/replay?lat=&lon=&crop=&variety=&season=2014-2015`
```json
{"season":"2014-2015","frames":[{"date":"","cp":0,"p10":0,"p50":0,"p90":0,"chance_low":0,"level":"amber"}],"actual_final_cp":0}
```

`GET /api/validation`
```json
{"n_stations":0,"n_station_seasons":0,
 "estimators":[{"id":"E0","name":"Nearest station","mae_cp":0,"p80_cp":0,"bias_cp":0}],
 "wildeye":{"n_stations":0,"estimators":[{"id":"E3","mae_cp":0}]},
 "durham":{"winters":[{"season":"","truth":0,"e0":0,"e3":0,"e4":0}]},
 "data_diet":[{"missing_pct":0,"gap_days":0,"mae_cp":0}],
 "backtest":{"brier":0,"brier_climatology":0,"reliability":[{"bin":"0-0.1","predicted":0,"observed":0,"n":0}]},
 "leakage_note":""}
```

`GET /api/grid?layer=safe_chill|chill_so_far&variety=` returns GeoJSON points with a `value` property, or a PNG tile set if faster.

---

## 8. Phases

### Phase 0: Setup, contract, data spike (A + B, 45 min)

**A tasks**
1. Create the repo layout (section 2), Python env, `.env.example`, `PROGRESS.md`, `DATA_SOURCES.md`.
2. Clone `ucdavis/fnric-reboot-the-eath-hackathon`; read the cheat sheet and the OpenAPI file; note anything that contradicts this prompt.
3. Spike every source with one small call: FNRIC `stations`, `chill-models-download?station-id=CIMIS-6`, `wildeye` (one site, one week), CIMIS hourly (station 6, one month), CIMIS station list, Daymet (one pin, one year), Open-Meteo forecast, Open-Meteo historical, elevation, PRISM (one day). Record status, latency, exact field names and quirks.
4. Write `engine/chillprint/api/schemas.py` (Pydantic) matching section 7.

**B tasks**
1. Next.js (App Router, TypeScript), Tailwind, shadcn/ui, lucide-react, framer-motion, react-map-gl with maplibre-gl, Recharts (or visx if you prefer finer control).
2. Write `web/mocks/*.json` for every endpoint in section 7, flagged `"mock": true`, with plausible shapes.
3. `web/lib/api.ts`: a typed client with a `USE_MOCKS` switch and automatic fallback to `public/demo/` when the API fails.

**GATE 0**
- Every source in the spike answered, or has a written fallback.
- `DATA_SOURCES.md` lists real field names for FNRIC, CIMIS and Daymet.
- The web app starts and renders the map with mocks.

### Phase 1: Data pipeline (A)

1. **Stations:** merge the FNRIC station list with the CIMIS station list (elevation, lat, lon, active, connect and disconnect dates). Save `stations.parquet`.
2. **FNRIC daily chill:** one `chill-models-download` call per Central Valley station plus all Wildeye stations, cached forever. Save `fnric_daily_chill.parquet`.
3. **CIMIS hourly:** Sept to Mar, winters 2005-06 to 2025-26, all Central Valley stations, one station-month per request, resumable, run in the background. Then backfill older winters for stations that have them. Save partitioned Parquet by station and season.
4. **Wildeye raw:** all available history for air temperature and solar radiation, cached.
5. **Daymet at station pixels:** 1980 to 2025 for every station (needed for E2, E3, E4 and the alignment test). Then Daymet for the six demo pins: Durham area, Parlier area, Shafter area, Davis area, one foothill pin east of Fresno, one west-side pin.
6. **Day alignment test** (section 4.6) for Daymet, and for PRISM if used.
7. QC report: hours present per station-season, flags dropped, gaps.

**GATE 1**
- At least 30 Central Valley stations with 10 or more complete winters of hourly data, or a written explanation of why not and what was done.
- Durham's hourly record covers at least 10 complete winters.
- Daymet cached for every station pixel and all six demo pins.
- Day alignment chosen and recorded, with its correlation.
- Re-running the pipeline makes zero network calls (cache hit test).

### Phase 2: Science engine (A)

1. `daylength.py`, `hourly.py` (Methods L and B, boundary blending, fallbacks).
2. `chill.py`: hours below 45, hours 32 to 45, Utah, Dynamic (numba, with state in and out).
3. `gdd.py`: FNRIC single sine with the zero-range guard.
4. Unit tests for every test vector and check in sections 4.3 to 4.5.

**GATE 2**
- Linvill and daylength test vectors pass within 1e-3.
- Dynamic Model matches xclim within 0.05 CP for a full season.
- Davis (CIMIS-6), three seasons: our CP matches FNRIC within 0.5 CP at season end; daily correlation above 0.99. Same check for Utah units and both chill-hour counts.
- GDD matches numeric integration on 10,000 random cases.
- Continuation test: running a season in two halves with saved state equals running it whole.

### Phase 3: Validation and error model (A, long compute)

1. Implement E0 to E5 (E6 if PRISM is available). Parallelize across stations with multiprocessing.
2. Run the hidden-station test (section 5.2), the Wildeye test (5.3), the data diet (5.5), the outlook backtest (5.6) and the Durham study (5.7).
3. Build `error_model.json` (section 4.10).
4. Write `validation/REPORT.md`: tables, plain-language findings, and the default method chosen for history and for the live season, with reasons.

**GATE 3**
- All outputs in section 5.4 exist and have no NaNs in headline metrics.
- The report states, in one sentence each: does E3 beat E0? Does E4 beat E0? What does one daily reading (E5) buy? Is the outlook better than climatology (Brier)? Is today's-climate shift on or off by default?
- If E3 and E4 do **not** beat E0, say so plainly, keep going, and frame the product around the measured map of where the nearest station is good enough. Do not tune on the test set to make numbers look better.

### Phase 4: Products and API (A)

1. `build_pin.py`: for any lat and lon, fetch and cache Daymet, pick nearest stations, rebuild hourly for all winters with the default method, compute daily CP per winter. Target under 8 seconds for a new pin, under 1 second cached.
2. `outlook.py`, `analogs.py`, `verdict.py` (sections 4.7 and 4.8).
3. `history.py` (section 4.9) and `replay.py` (frames every day, or every 2 days if slow).
4. Live season: E4 using FNRIC `stemwater` (last 300 hours) or recent CIMIS hourly, plus the Open-Meteo forecast.
5. `build_grid.py`: a roughly 4 km grid over the Central Valley and foothills (elevation under 600 m), with summary layers (safe chill per variety, chill so far). Run in the background; the app works without it.
6. FastAPI `main.py` implementing section 7 exactly, with CORS open and responses cached in DuckDB or on disk.
7. `scripts/export_demo.py`: write full responses for the six demo pins, every crop and variety, and the 2014-15 and 2015-16 replays into `web/public/demo/`.

**GATE 4**
- Every endpoint returns schema-valid JSON for all six demo pins.
- Replay of 2014-15 at the Shafter-area pin shows Kerman as amber or red by Feb 1. If it doesn't, report what the data says; don't force it.
- Land history for the Durham pin returns 45 winters with trend and safe-chill values.
- Cached `/api/point` responds in under 1 second.
- Write "GATE 4 PASSED" in PROGRESS.md so Agent B can start 5c.

### Phase 5: App (B)

**5a. Shell (against mocks)**
- Layout, header, map, panel, tabs, onboarding coach marks, empty state, search, units toggle, layer menu.

**5b. Components (against mocks)**
- Verdict hero, ring gauge, stat tiles, season chart (faint past lines, bold current, need band, fan, today marker), year highlighter, time machine scrubber with Play, land history bar chart with trend, Heat tab, Accuracy page (estimator bars, error map, data-diet slider), loading skeletons, error states, motion per section 6.7.

**5c. Integration (after GATE 4)**
- Switch `USE_MOCKS` off. Remove every mock number from the UI. Wire all endpoints. Make offline fallback to `public/demo/` automatic.

**GATE 5**
- A first-time user can go from opening the app to reading a verdict in 3 clicks or fewer (pin, crop, variety).
- Every number on screen comes from the API or demo export; grep the build for `"mock": true` and find nothing in production paths.
- Works at 375 px width (mobile) and 1440 px (laptop).
- Lighthouse accessibility score of at least 90; no color-only status.
- Time machine plays 2014-15 smoothly and the verdict updates as it plays.

### Phase 6: Gated upgrades (A; only if GATES 1 to 4 passed)

Do these in order. Each one ships only if it passes its own check.

1. **ML nighttime-low correction (E7).** LightGBM predicting the station-minus-Daymet daily Tmin residual from: Daymet Tmin, daily range, month, elevation, elevation difference to neighbors, terrain position (DEM-based TPI at 1 and 5 km; DEM from AWS Terrain Tiles or USGS 3DEP), distance-weighted neighbor residuals that day. Train with grouped cross-validation, leaving one station out per fold. Ship only if it beats the default method on hidden stations **and** on Wildeye. Add it to the Accuracy page either way.
2. **ML hourly shape.** LightGBM predicting the normalized hourly position (T minus Tmin, divided by the range) from hour, day length, daily range, daily solar radiation, humidity and month, trained on CIMIS hourly. Ship only if it beats Method B on hidden stations.
3. **Sunny-stretch flag.** From nearest-station hourly solar radiation, count clear dormant days (daily radiation over 70% of a clear-sky estimate; the threshold is tunable) in the last 14 days. If 7 or more, show "Sunny stretch: tree chill likely lower than shown," citing UC Davis TreeChill research. Label it a heuristic.
4. **Orchard mask.** DWR statewide crop mapping: show orchard parcels as a faint layer and snap the grid to them.
5. **Global pin.** One pin at Sfax, Tunisia, using Open-Meteo historical (ERA5) hourly, the same engine and Kerman pistachio. Label it "Lower resolution, not validated here." This powers the UN slide: same engine, places with few stations.

**GATE 6**
- Each shipped upgrade has a before-and-after number in PROGRESS.md.
- Nothing shipped makes a headline metric worse.

### Phase 7: Demo hardening and submission (A + B)

1. **Offline mode:** turn off Wi-Fi and run the full demo script below from `public/demo/` with no errors.
2. **Deploy:** web on Vercel; API on Render, Railway or Fly (or a laptop plus a tunnel). The app must still work if the API is down.
3. **Demo script** (90 seconds; also put it in the README):
   1. Open the app; the coach marks appear.
   2. Tap "Durham, Butte Co." The map flies to the pin and shows the closed-station label.
   3. Pick Kerman pistachio. Read the verdict card.
   4. Press Play on the 2014-15 replay; watch the verdict turn as the season runs.
   5. Open Land history: "Met Kerman's need in __ of 45 winters," with the trend.
   6. Open Accuracy: our miss versus the nearest station's miss, the Wildeye result, and the data-diet slider.
4. **README:** what it does, how it works (one diagram), the validation table with real numbers, the limits (air temperature is not bud temperature; possible leakage; trend caveats), data credits and licenses (DWR CIMIS, FNRIC, Daymet citation, PRISM attribution, Open-Meteo CC BY 4.0, chillR if ported), and how FNRIC could embed it.
5. **License:** MIT, or GPL-3 if chillR code was ported. Public GitHub repo.
6. **Backup video:** record the demo script as a 2-minute screen capture.
7. **Unite Ideas entry** (submit by 2:30 pm, editable until 3:00): title, description, code link, demo link, video link.

**GATE 7**
- Offline demo passes end to end.
- Deployed URL works on a phone.
- README shows real validation numbers.
- Submission is in.

---

## 9. Known traps checklist

- [ ] FNRIC `chill-year` in two-year form; arrays sorted; daily values cumulated
- [ ] CIMIS hours `0100` to `2400` PST; QC flags handled; one station-month per request
- [ ] Daymet leap-year Dec 31 filled
- [ ] Gridded day window aligned (section 4.6)
- [ ] Dynamic Model never summed across segments; state carried
- [ ] Analogs exclude the season being judged
- [ ] GDD in °C with lower 5 and upper 35; chill thresholds in °F
- [ ] Leakage caveat shown for PRISM results
- [ ] "By" dates marked as needing confirmation from Julia
- [ ] No mock numbers in production paths
- [ ] Words: "grower," not "farmer"

---

## 10. Sources

- FNRIC hackathon resources and API cheat sheet: https://github.com/ucdavis/fnric-reboot-the-eath-hackathon
- FNRIC chill calculator: https://fruitsandnuts.ucdavis.edu/chill-calculator
- CIMIS: https://cimis.water.ca.gov/ and https://et.water.ca.gov/
- Daymet single-pixel tool: https://daymet.ornl.gov/single-pixel
- PRISM FAQ (800 m free since March 2025): https://prism.oregonstate.edu/faq
- PRISM day definition and inputs: https://climatedataguide.ucar.edu/climate-data/prism-high-resolution-spatial-climate-data-united-states-maxmin-temp-dewpoint
- Open-Meteo: https://open-meteo.com/en/docs and https://open-meteo.com/en/docs/ensemble-api
- chillR hourly temperatures vignette (test vectors, Winters benchmark): https://www.stats.bris.ac.uk/R/web/packages/chillR/vignettes/hourly_temperatures.html
- chillR weather generator and Safe Winter Chill: https://inresgb-lehre.iaas.uni-bonn.de/chillR_book/generating-temperature-scenarios.html
- Luedeling et al. 2009, safe winter chill in California: https://pmc.ncbi.nlm.nih.gov/articles/PMC2707005
- UCCE chill portion requirements (K. Pope): https://ccfruitandnuts.ucanr.edu/node/128184
- Martínez-Lüscher et al. 2022, in-orchard versus CIMIS: https://pmc.ncbi.nlm.nih.gov/articles/PMC9119484
- TreeChill (tree versus air temperature): https://www.progressivecrop.com/?p=9602
- Seasonal chill forecast skill: https://iris.unive.it/handle/10278/5084977
- UC ANR IGIS climate tools: https://ucanr.edu/program/informatics-and-gis-program/weather-and-climate-tools-data
- Cal-Adapt: https://cal-adapt.org/
