# Data sources: what the Phase 0 spike actually returned

Spike run 2026-10-23 (Fri night, Pacific). Raw spike responses are cached in `engine/data/cache/spike/`.
Where a source differs from BUILD.md, the difference is called out under **Differs from BUILD.md**.

## FNRIC API

Base `https://f5dby14cj5.execute-api.us-west-2.amazonaws.com/prod/`. No key. Limited budget: every call is cached to disk and never repeated.

| Endpoint | Status | Latency | Size | Notes |
| --- | --- | --- | --- | --- |
| `stations` | 200 | 1.6 s | 67 KB | 303 stations; 172 active; 26 Wildeye |
| `chill-models-download?station-id=CIMIS-6` | 200 | 4.9 s | 575 KB | CSV, 16,167 daily rows, 1982-07-17 to 2026-10-22 |
| `chill-models?station-id=CIMIS-6&chill-year=2025-2026` | 200 | 1.9 s | 47 KB | 363 rows, unsorted |
| `stemwater?station-id=CIMIS-6` | 200 | 2.0 s | 84 KB | 300 hourly rows, unsorted |
| `almond-hull-split-gdd90?station-id=CIMIS-6&fbd=2025-02-20` | 200 | 0.9 s | 6 KB | 91 rows |
| `wildeye?siteID=Wildeye-111086&startDate=2025-11-01&endDate=2025-11-07&variables=all&format=csv_wide` | 302 then 200 | 9.7 s | 36 KB | Hourly CSV |

Field names (exact):

- `stations` → `{stations:[{StationID, Name, County, ConnectDate, IsActive, HmsLatitude, HmsLongitude}]}`.
  - `HmsLatitude` like `"39º36'31N / 39.608639"` (the degree sign arrives mis-encoded); Wildeye rows have an empty DMS part: `" / 35.9598619910292"`. Parse the number after `/`.
  - Wildeye `County` is `""`. `ConnectDate` like `"1982-10-19 00:00:00"`.
- `chill-models-download` → CSV header `"Date","hours_lt_45","hours_32_45","units_utah","portions_dynamic"`. Daily amounts. This file came back **sorted** and with no duplicate dates, but we sort anyway.
- `chill-models` → `{model_values:[{Date, hours_32_45, hours_lt_45, n_hours, portions_dynamic, units_utah}]}`.
- `stemwater` → `{hourly_values:[{ChillYear, StationID, Timestamp, HlyAirTmp_Value, HlyAirTmp_Qc, HlyRelHum_Value, HlyVapPres_Value, portions_dynamic, dynmod_inter_e, dynmod_xi}]}`. `Timestamp` like `"2026-10-22 23:00:00"`; `HlyAirTmp_Value` in °F.
- `almond-hull-split-gdd90` → `{model_values:[{Date, grow_degr_days_ss}]}` (°C-days).
- `wildeye` (csv_wide) → columns `date, hour, ..., Solar radiation, Wind speed (mile/hour), Air Temperature (raw), Humidity (raw), Relative Humidity, Air Temperature, Vapour pressure, Chill hours, Chill portions, Heat Hours, ETo`. `Air Temperature` is °F.

**Differs from BUILD.md / quirks**

- Wildeye `date`/`hour` are **local Pacific time with daylight saving**. The request window is interpreted in UTC (asking from 2025-11-01 returned rows starting 2025-10-31 17:00 PDT = 00:00 UTC). On the fall-back day the repeated 1 am hour is merged (24 rows, not 25). We convert to PST (UTC-8) by localizing to America/Los_Angeles and dropping the ambiguous/nonexistent hour.
- Wildeye ships its own `Chill portions` column (cumulative); we ignore it and compute truth with our engine.
- FNRIC's `chill-models-download` already includes the current season to yesterday (2026-10-22), so it doubles as a live-season source for any FNRIC station.

## CIMIS

| Call | Status | Latency | Notes |
| --- | --- | --- | --- |
| `GET https://et.water.ca.gov/api/station` | 200 (flaky: one timeout, one 503, then 200) | 0.9 s | 276 stations |
| `GET https://et.water.ca.gov/StationWeb/GetDataByStationNumber?...` without key | 401 `Access denied due to missing subscription key` | 0.1 s | Needs `Ocp-Apim-Subscription-Key` header |
| `ftp://ftpcimis.water.ca.gov` | connection refused | – | No keyless bulk fallback |

Station list fields: `StationNbr, Name, City, RegionalOffice, County, ConnectDate ("6/7/1982"), DisconnectDate ("7/30/2025"; active stations show "12/31/2050"), IsActive ("True"/"False" strings), IsEtoStation, Elevation, GroundCover, HmsLatitude, HmsLongitude, ZipCodes, SitingDesc`.

**Differs from BUILD.md**

- `Elevation` is in **feet** (Davis "60", Durham "130"; Daymet puts Durham at 43 m). Converted to metres on load.
- Durham (12) `DisconnectDate` is 7/30/2025, matching "stopped reporting July 2025".
- Hourly data fields: recorded after the key arrives (see section below).

### CIMIS hourly (verified 2026-10-24 with the key)

`GET https://et.water.ca.gov/StationWeb/GetDataByStationNumber?stationNbrs=6&startDate=2014-11-01&endDate=2014-11-30&isHourly=true&unitOfMeasure=E&dataItems=hly-air-tmp,hly-sol-rad,hly-rel-hum` with header `Ocp-Apim-Subscription-Key` → 200 in about 1.0 s, about 200 KB per station-month (raw, gzipped in the cache).

- Shape: `{"Data": {"Providers": [{"Records": [...]}]}}`; 720 records for November.
- Record fields: `Date` ("2014-11-01"), `Julian`, `Hour` ("0100" .. "2400"), `Station` ("6"), `Standard` ("english" or "metric"), `ZipCodes`, `Scope` ("hourly"), `HlyAirTmp`, `HlyRelHum`, `HlySolRad`, each `{"Value": "61.9", "Qc": " ", "Unit": "(°F)"}`.
- Units: English gives °F and solar in Ly/day (1132 Ly/d = 548 W/m², factor 0.4843); metric gives °C and W/m².
- QC flags seen: blank and `Y` (kept), `R` (far out of historical range; dropped as BUILD.md says).
- `2400` is mapped to 00:00 of the next day; a day's hours are stamps 01:00..24:00 (the CIMIS date of a stamp is stamp − 1 h).

**FNRIC conventions, established by matching Davis exactly (GATE 2):** FNRIC's chill is computed from the **°F** readings (converted to °C with T + 273 K for the Dynamic Model) and **missing hours are skipped** (the model state is held, not interpolated). Pulling metric values instead shifts season totals by up to 0.5 CP through rounding. We therefore pull English units and convert. FNRIC keeps `R`-flagged hours; we drop them, which explains a few Utah-unit differences.

## Daymet single-pixel (V4 R1)

| Call | Status | Latency | Size |
| --- | --- | --- | --- |
| first three tries (22:40–22:55 PT) | 504 Gateway Timeout after 60 s | – | – |
| `lat=39.62&lon=-121.80&vars=tmax,tmin,srad,dayl&years=2020` | 200 | 0.6 s | 14 KB |
| `lat=39.62&lon=-121.80&vars=tmax,tmin&start=1980-01-01&end=2025-12-31` | 200 | 1.3 s | 340 KB |

- 7 header lines (lat/lon, LCC x/y, tile, `Elevation: 43 meters`, version, citation), then `year,yday,dayl (s),srad (W/m^2),tmax (deg c),tmin (deg c)`. Parsed by finding the line starting with `year,yday`.
- Data ends 2025-12-31 (last full year). 365 rows per year; Dec 31 dropped in leap years (filled by interpolation and flagged).
- Inputs: Daymet V4 interpolates GHCN-Daily station observations (Thornton et al. 2021). CIMIS is not a GHCN-Daily source network, so Daymet is treated as the **lower-leakage** grid for hidden-CIMIS validation. Not independently confirmed with ORNL; stated as an assumption on the Accuracy page.
- Fallback when single-pixel is down: retries with backoff, then gridMET (below). ORNL THREDDS now redirects to Earthdata and needs a login (401), so it is not usable keyless.

## gridMET (fallback grid, 4 km, includes the current season)

- `http://thredds.northwestknowledge.net:8080/thredds/ncss/agg_met_tmmn_1979_CurrentYear_CONUS.nc?var=daily_minimum_temperature&latitude=..&longitude=..&time_start=..&time_end=..&accept=csv` → 200 in 0.4 s.
- Values come back **packed**: real K = raw × 0.1 + 210 (from the `.das`). Example 664 → 276.4 K → 3.25 °C.
- gridMET is built from PRISM plus NLDAS-2, so it may carry CIMIS information (possible leakage). Used only as a fallback, never in headline validation.

## PRISM (skipped)

- `https://services.nacse.org/prism/data/get/us/800m/tmin/20200101` → 200, 43 MB zip for a single CONUS day, 15 s. Point extraction would need one such file per variable per day (≈33,000 files for 45 winters). Not fast. **E6 is skipped**, as BUILD.md allows.

## Open-Meteo

| Call | Status | Latency |
| --- | --- | --- |
| Forecast `hourly=temperature_2m&forecast_days=16&past_days=14&timezone=America/Los_Angeles` | 200 | 0.9 s |
| Archive (ERA5) Sfax `2020-09-01..2021-03-31` hourly | 200 | 1.3 s |
| Elevation `v1/elevation?latitude=39.62&longitude=-121.80` | 200 | <1 s, `{"elevation":[43.0]}` |

- Forecast/archive times are local wall-clock strings (`"2026-10-09T00:00"`) in the requested timezone, with `utc_offset_seconds` (−25200 in PDT). For PST series we request `timezone=GMT` and shift by −8 h ourselves.
- Credit: Open-Meteo, CC BY 4.0.

## USGS EPQS (elevation fallback)

- `https://epqs.nationalmap.gov/v1/json?x=-121.80&y=39.62&units=Meters&wkid=4326` → 200, `{"value":"42.552768707", ...}`.

## Day alignment (section 4.6)

Run 2026-10-24 on Wildeye in-orchard hourly vs Daymet at the station pixels (26 stations, 9,927 Sept-Mar days, 2023-24 and 2024-25; `engine/data/processed/alignment.json`). Mean correlation across stations:

| Window (PST, hour-ending stamps) | Lag | r Tmin | r Tmax | mean |
| --- | --- | --- | --- | --- |
| **midnight to midnight** | **0** | **0.946** | **0.983** | **0.965** |
| 4 am to 4 am | 0 | 0.941 | 0.983 | 0.962 |
| 7 am to 7 am | 0 | 0.900 | 0.983 | 0.941 |
| 7 am to 7 am | -1 | 0.933 | 0.927 | 0.930 |
| 4 am to 4 am | -1 | 0.912 | 0.927 | 0.920 |
| midnight to midnight | -1 | 0.886 | 0.927 | 0.906 |

**Chosen: midnight-to-midnight PST, lag 0.** Daymet's day label matches the calendar day. To be re-run on CIMIS hourly once the key arrives (the script uses CIMIS automatically when present).
