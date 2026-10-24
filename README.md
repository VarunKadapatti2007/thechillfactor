# ChillPrint

**Is this winter enough for my trees, here?**

ChillPrint estimates winter chill for California fruit and nut growers at the exact spot of their orchard, not at the nearest CIMIS station. Drop a pin, pick a crop and variety, and get:

- a green, amber or red verdict against that variety's chill need,
- chill so far with a measured error bar,
- the odds of reaching the need by a set date,
- the past winter this one most resembles,
- a time machine that replays any past winter day by day,
- a land history card: every winter since 1980-81 at that parcel, with the trend and safe winter chill.

Built for the UC Davis Reboot the Earth hackathon (FNRIC "Counting the Cold" challenge), October 2026.

## How it works

```
FNRIC API ──── station daily chill (cross-check), Wildeye in-orchard hourly (independent test)
CIMIS API ──── station hourly temperature, 1982 to today (°F, PST), 87 Central Valley stations
Daymet ─────── 1 km daily min/max, 1980-2025: pin-vs-station monthly offsets
Open-Meteo ─── 16-day forecast (live season)
        │
        ▼
 hourly temperature at the pin, chosen by a hidden-station test:
   E4 = nearest station with a complete record that winter, shifted to the pin by the
        Daymet 1 km monthly difference (low and high shifted separately)
   winters with no station record: Daymet + a machine-learned daily curve
        │
        ▼
 Dynamic Model (chill portions), chill hours, Utah, GDD (FNRIC single sine)
        │
        ├── outlook: observed + bias-corrected forecast + every past winter played
        │   forward from today's model state  ->  P10/P50/P90, odds, verdict
        ├── land history: every winter since 1980-81, Theil-Sen trend, safe winter chill
        └── validation: hide a station, estimate it, compare  ->  error bars
        ▼
 FastAPI (engine/)  ──►  Next.js app (web/), with an offline demo bundle
```

The engine reproduces FNRIC's own numbers exactly: on Davis CIMIS hourly over three winters our Dynamic Model gives 61.613, 91.277 and 83.401 CP, the same as FNRIC to three decimals, with identical daily values. That needed FNRIC's conventions, which we found by testing: chill is computed from CIMIS's °F readings, with T + 273 K, and missing hours are skipped rather than filled.

**What did not work, said plainly:** the textbook plan was Daymet daily + a borrowed station shape (E3). On hidden stations it misses by more than simply using the nearest station (4.9 vs 3.9 CP), because Daymet runs warm at night at these irrigated, cold-air-pooling sites. The borrowed shape itself is fine: given the orchard's own daily low and high it is the best method we tested (1.6 CP). So the default became E4.

## Validation

<!-- validation:start -->
Hidden-station test: 65 Central Valley CIMIS stations, 855 station-winters (mode: full). Errors are chill portions at Feb 1 and Mar 1, the same cases for every method.

| Method | Typical miss (CP) | 8 in 10 within (CP) | Bias (CP) |
| --- | --- | --- | --- |
| E0 Nearest station | 3.86 | 5.87 | 0.14 |
| E1 3-station average | 3.43 | 4.96 | -0.1 |
| E2 Daymet + textbook curve | 4.22 | 6.54 | -3.19 |
| E3 Daymet + borrowed shape | 4.94 | 7.48 | -4.04 |
| E4 Station + Daymet offset (default) | 3.44 | 5.27 | 0.48 |
| E5 One reading a day | 1.56 | 2.48 | 0.2 |
| E8 3 stations + Daymet offset (tested, not adopted) | 3.26 | 5.12 | 1.18 |
| E7 Daymet + ML night-low fix (not shipped) | 4.25 | 6.69 | -3.31 |

In-orchard test, 18 Wildeye stations: E0 3.12 CP, E2 4.0 CP, E3 5.3 CP, E4 3.52 CP, E8 3.84 CP.

Outlook backtest: Brier 0.0108 vs 0.0168 for climatology (lower is better).

Data gaps: Up to 30% missing days scattered through the winter, or gaps up to 4 days, keeps the typical error under 2 CP (with no gaps, 8 in 10 winters land within 2.8 CP).

Findings:

- E3 (Daymet + borrowed shape) does not beat the nearest station: typical miss 4.9 vs 3.9 CP.
- E4 (Station + Daymet offset) beats the nearest station: typical miss 3.4 vs 3.9 CP.
- Statistically (cluster bootstrap over stations), E4's edge over the nearest station is 0.42 CP with a 95% interval of -0.12 to 1.22: likely but not proven overall; clear at 25-50 km.
- One daily reading at the orchard (E5) brings the typical miss to 1.6 CP.
- The outlook beats climatology: Brier 0.0108 vs 0.0168.
- Today's-climate shift is on by default (Brier 0.0108 with, 0.0111 without).
- At Wildeye in-orchard stations: E0 3.1 CP, E2 4.0 CP, E3 5.3 CP, E4 3.5 CP, E8 3.8 CP.
- Up to 30% missing days scattered through the winter, or gaps up to 4 days, keeps the typical error under 2 CP (with no gaps, 8 in 10 winters land within 2.8 CP).
- Pre-registered test: averaging three stations (E8) misses by 3.26 CP, 0.19 less than E4 (95% interval -0.07 to 0.42) and slightly worse at orchards, so it was not adopted.
- Phase 6: an ML hourly shape on Daymet scores 3.55 CP vs 4.94 for the borrowed shape and 4.20 for the textbook curve (832 station-winters); it replaces the textbook curve for winters with no station record.
- Phase 6: the ML night-low fix (E7) improves Daymet (4.25 vs E3 4.96 CP) but does not beat the E4 default (3.45); not shipped.
<!-- validation:end -->

Full tables: [engine/chillprint/validation/REPORT.md](engine/chillprint/validation/REPORT.md).

## Limits

- Air temperature is not bud temperature. Sunny dormant days warm buds above air temperature (UC Davis TreeChill research).
- Daymet may include some of the same weather records as the hidden stations, so hidden-station scores may be a little optimistic. The Wildeye in-orchard test has no such overlap.
- 45-year trends are indicative only. For 2050 we link to the UC ANR projected chill tools and Cal-Adapt rather than rebuild projections.
- The "by" dates per crop are placeholders until FNRIC confirms them; growers can change them in the app.
- Winters with no complete station record nearby (before CIMIS began in 1982, or gaps) are estimated from Daymet with a machine-learned daily curve and shown faded; they are left out of trends.
- In-orchard air is warmer than CIMIS grass sites: at 18 Wildeye pistachio orchards, every method overestimates chill a little (nearest station +1.5 CP).

## Run it

Engine (Python 3.12):

```bash
cd engine
python -m venv .venv && .venv/Scripts/pip install --no-cache-dir -r requirements.txt   # .venv/bin on macOS/Linux
cp ../.env.example ../.env   # add CIMIS_APP_KEY from cimis.water.ca.gov
bash ../scripts/run_validation.sh          # data pull, tests, validation, demo export
.venv/Scripts/python -m uvicorn chillprint.api.main:app --port 8000
```

App (Node 20+):

```bash
cd web
npm install
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev
```

The app falls back to `web/public/demo/` when the API is unreachable, so the six demo orchards work offline.

For the demo on Windows, one command builds the web app and starts both servers (API on :8000, web on :3000):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_local.ps1
```

Shareable links work too, e.g. `http://localhost:3000/?lat=39.63&lon=-121.8&crop=pistachio&variety=kerman&tab=history`.

## Demo script (90 seconds)

1. Open the app; the coach marks appear.
2. Tap "Durham, Butte Co." The map flies to the pin and shows the closed-station label.
3. Pick Kerman pistachio. Read the verdict card.
4. Press Play on the 2014-15 replay; watch the verdict and odds update as the season runs. (2014-15 was short of chill in southern Kern: FNRIC shows Arvin-Edison at 49 CP by Mar 1, below Kerman's 54. Drop a pin near Arvin to show a red winter.)
5. Open Land history: at Durham, "Met Kerman's need in 43 of 43 winters" with a station record, no clear trend (-0.7 CP per decade).
6. Open Accuracy: our miss versus the nearest station's miss, the Wildeye result, and the data-diet slider.

## How FNRIC could embed it

The API is plain JSON with open CORS. `GET /api/point?lat=..&lon=..&crop=..&variety=..` returns everything the verdict card needs; `/api/history`, `/api/replay` and `/api/validation` back the other tabs. The FNRIC chill calculator could call `/api/point` for any map click, or embed the app in an iframe.

## Data credits and licenses

- CIMIS: California Department of Water Resources.
- FNRIC weather models API: UC Davis Fruit & Nut Research & Information Center.
- Daymet: Thornton, M.M., R. Shrestha, Y. Wei, P.E. Thornton, S-C. Kao, and B.E. Wilson. 2022. Daymet: Daily Surface Weather Data on a 1-km Grid for North America, Version 4 R1. ORNL DAAC, Oak Ridge, Tennessee, USA. https://doi.org/10.3334/ORNLDAAC/2129
- gridMET (fallback): Abatzoglou, J.T. 2013, University of Idaho.
- Open-Meteo forecast and elevation (CC BY 4.0).
- Basemap: OpenFreeMap, OpenMapTiles, OpenStreetMap contributors.
- Crop chill needs: UCCE chill portion requirements compiled by Katherine Pope.
- Hourly rebuild implemented from Linvill (1990) and checked against the chillR vignette values; no chillR code was ported.

Code: MIT License.
