# ChillPrint: every calculation, and why daily highs and lows cut the error

This document explains how ChillPrint turns weather data into a chill count, an outlook and an error bar. It gives every formula, and it shows with real-data tests why the orchard's own daily high and low are the single best way to reduce error.

Numbers come from our validation runs on real data: CIMIS hourly records, Daymet, and Wildeye in-orchard sensors via FNRIC. The code that produced each one is named in brackets.

---

## 1. Answer first: do daily highs and lows make the model better?

**Yes, by about half.** This is the core of ChillPrint's solution. We tested it on real data in two ways:

| Typical miss in chill portions (CP), Feb 1 and Mar 1 | 18 pistachio orchards (in-orchard sensors), 30 winters | 65 hidden CIMIS stations, 855 winters |
| --- | --- | --- |
| Station data only (best public-data method) | 3.52 (always over-counts, by +2.29) | 3.44 |
| + the orchard's daily low and high from Sep 1 | **1.84** (bias −0.05) | **1.56** |
| ... from Nov 1 | 1.75 | 1.67 |
| ... from Dec 1 | 2.16 | 2.19 |
| ... from Jan 1 | 2.77 | 2.64 |

[`engine/chillprint/validation/orchard_readings.py`]

**Why this is the solution:** no method built only on public weather stations gets much below about 3.5 CP at an orchard. That holds for ours and for kriging with a 731-sensor in-orchard network in the published literature (Martínez-Lüscher et al. 2022). An inexpensive min/max thermometer in the orchard halves that error and removes the systematic over-count. Section 9 explains the mechanism.

---

## 2. The data and its units

| Source | What we use | Units and time |
| --- | --- | --- |
| CIMIS (California Irrigation Management Information System) | Hourly air temperature, 87 Central Valley stations, 1982 to yesterday | Pulled in °F (FNRIC's convention), stored as °C; hour-ending Pacific Standard Time all year (CIMIS hour 2400 = 00:00 next day) |
| FNRIC (UC Fruit & Nut Research & Information Center) | Wildeye in-orchard sensors (truth for the orchard test); daily chill for cross-checks; relay of CIMIS hours when CIMIS refuses | °F, converted |
| Daymet v4 | 1 km daily low and high, 1980–2025 | °C; used only for station-to-orchard differences |
| Open-Meteo | 16-day hourly forecast (live season) | °C, bias-corrected (section 7) |
| The grower | Daily low/high or logger readings from the orchard | °F or °C, any interval |

**Quality control:** CIMIS values flagged blank, `Y` or `P` are kept. Anything else (for example `R`, far out of range) counts as missing. So does any temperature outside −30 to 55 °C. °F → °C: `T_C = (T_F − 32) × 5/9`.

---

## 3. The chill model (Dynamic Model, chill portions)

The Dynamic Model (Fishman, Erez and colleagues, 1987) treats chill as a two-step process:
1. Cool temperatures build up an intermediate product.
2. Warm temperatures can destroy that product before it is locked in.
3. Once the product reaches a threshold, a share of it is locked in as one chill portion and can no longer be lost.

**Constants:** `E0 = 4153.5 K`, `E1 = 12888.8 K`, `A0 = 1.395×10^5`, `A1 = 2.567×10^18`, `slope = 1.6`, `Tf = 277 K`.

**For every hour h,** with air temperature `T` in °C [`engine/chillprint/science/chill.py`]:

```
TK      = T + 273                                    (FNRIC's Kelvin convention)
sr      = exp( slope · Tf · (TK − Tf) / TK )
xi      = sr / (1 + sr)                              share of product locked in when the threshold is reached
xs      = (A0 / A1) · exp( (E1 − E0) / TK )          equilibrium level of the intermediate product
k1      = A1 · exp( −E1 / TK )                       rate of approach to that level
S       = E_prev                  if E_prev < 1
        = E_prev − E_prev · xi_prev   if E_prev ≥ 1  (a portion was just locked in)
E       = xs − (xs − S) · exp(−k1)                   intermediate product after this hour
portion = E · xi   if E ≥ 1,  else 0
CP(season so far) = sum of portions since Sep 1 (or Nov 1)
```

**Rules that keep the count exact:**
- The model has memory (`E`, `xi`), so a season is always one continuous run. We never add up chill from separate pieces. To continue a season (for example after today), we pass the saved state forward.
- A missing hour is skipped: the state holds, and nothing is added. This is FNRIC's convention.
- With these rules our count matches FNRIC to three decimals on Davis CIMIS data (61.613, 91.277 and 83.401 CP over three winters) [`engine/tests/test_fnric_davis.py`].

**What temperatures do, from the model itself** (chill per day at a steady temperature):

| Steady temperature | 0 °C (32 °F) | 2 °C | 4 °C | 6 °C | 7 °C (45 °F) | 8 °C | 10 °C | 12 °C | 13 °C (55 °F) and above |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CP per day | 0.13 | 0.65 | 0.73 | 0.83 | **0.85** | 0.81 | 0.81 | 0.60 | **0** |

**Real days cycle between a low and a high,** and the high matters as much as the low. Over 30 days of the same daily cycle:

| Night low | Afternoon high 12 °C | 16 °C | 20 °C |
| --- | --- | --- | --- |
| 2 °C | 23.4 CP | 13.1 CP | 14.2 CP |
| 5 °C | 23.3 CP | 18.6 CP | **0.0 CP** |

A warm afternoon can wipe out a night's progress, and the effect is strongly non-linear. This is why the orchard's own low and high matter (section 9).

**Also computed** [`chill.py`, `gdd.py`]:
- **Chill hours:** hours at or below 45 °F, and hours between 32 and 45 °F.
- **Utah units** (°F): ≤34 → 0; 34–36 → 0.5; 36–48 → 1; 48–54 → 0.5; 54–60 → 0; 60–65 → −0.5; >65 → −1.
- **Growing degree days** (single sine, 5–35 °C), with `mean = (Tmax + Tmin)/2` and `a = (Tmax − Tmin)/2`:
  - inside both limits: `GDD = mean − 5`;
  - low below 5 °C: `GDD = ((mean − 5)(π/2 − s1) + a·cos s1)/π`, where `s1 = asin((5 − mean)/a)`;
  - the other cases follow the same sine geometry.

---

## 4. Getting hourly temperatures at the orchard

The model needs hourly temperatures at the orchard. There is rarely a station there, so we build them.

### 4a. Station-to-orchard estimate (E4, the default when the grower has no readings)

Take the nearest CIMIS station with a complete record that winter, then shift each of its hours by the station-to-orchard climate difference that Daymet sees at 1 km [`engine/chillprint/pipeline/build_pin.py`: `monthly_offset`, `offset_hourly`]:

```
ΔTmin(m) = mean over 2010–2025 of [ Daymet_orchard Tmin − Daymet_station Tmin ]  for calendar month m
ΔTmax(m) = same for the daily high
p(h)     = (T_station(h) − day's low) / (day's high − day's low),  clipped to 0..1   (0 at the low, 1 at the high)
T_orchard(h) = T_station(h) + ΔTmin(m) + p(h) · (ΔTmax(m) − ΔTmin(m))
```

Night hours get the low's difference and afternoon hours get the high's. Daymet sets only the long-run difference; every day's actual weather comes from the station.

### 4b. From a daily low and high to 24 hours (borrowed shape; used for grower readings)

Each day, take the nearest station's real hourly curve and stretch it between the orchard's low and high [`engine/chillprint/science/hourly.py`: `borrowed_shape`]:

```
T_orchard(h) = Low_orchard + (T_station(h) − Low_station) / (High_station − Low_station) × (High_orchard − Low_orchard)
```

- **Which station:** the nearest one whose day is usable (at most 4 missing hours, range at least 0.5 °C); otherwise the next nearest of three.
- **No usable station:** the Linvill (1990) textbook curve is used instead:
  - day: `T(h) = Low + (High − Low) · sin(π (h − sunrise) / (daylength + 4))`;
  - night: a logarithmic fall from the sunset temperature to the next morning's low.
- **Day boundaries:** consecutive days are blended linearly over ±3 hours, so midnight has no jump.

### 4c. Winters with no station record nearby (before 1982, or gaps)

Daymet's daily low and high are turned into hours with a machine-learned daily curve. It is validated at 3.55 CP, against 4.94 for the borrowed shape on Daymet and 4.20 for the textbook curve. These winters are shown faded and left out of trends.

### 4d. The grower's readings

- **Daily lows and highs** → hours with 4b.
- **Logger readings** → hour-ending averages, with the logger clock converted to Pacific Standard Time.
- **Gaps:** up to 4 days (or 6 logger hours) are filled from the days around them. Longer gaps, and days before the readings start, use E4.
- **One run:** the Dynamic Model runs once over the merged winter, so its state carries across.
- **Any file layout** [`engine/chillprint/products/readings_parse.py`]: Excel, CSV and text exports, Word tables and PDF text become one table. Built-in rules find the date, low and high (or temperature) columns from their headers. When the layout is unusual, an AI reader (Claude Haiku) sees a preview and names the columns. Code then reads every value from the file, so the AI never supplies a number. Before use, the grower sees the first rows exactly as read.
- **The orchard log** (`/log`): one low and one high per day, typed in or imported from a file, saved on the grower's device and sent only when they check their chill.

[`engine/chillprint/products/orchard.py`]

---

## 5. Live data, around the clock

[`engine/chillprint/pipeline/live_refresh.py`]
- Every 3 hours, the server re-pulls this month's CIMIS hours for all 40 active Central Valley stations, one request at a time, at least 0.3 s apart.
- If CIMIS refuses a request, the rest of that cycle uses FNRIC's relay of the same CIMIS readings (FNRIC labels hours by their start, so we shift by one hour). Against CIMIS directly at Davis, 96–99.5% of hours are identical and the rest are within 0.1 °F. Quality flags are the same, so flagged hours are dropped either way.
- A refusal page is never stored as data.
- `/api/health` reports the sources used, the latest hour and its age.

---

## 6. Accuracy: how every error bar is measured

**Hidden-station test** [`validation/hidden_station.py`]:
1. Hide one CIMIS station.
2. Estimate it from everything else, exactly as the app would for an orchard.
3. Compare with the station's own measured chill on Feb 1 and Mar 1.
4. Repeat for 65 stations and 855 winters (2005–2025).

**In-orchard test** [`validation/wildeye.py`, `orchard_readings.py`]: the same comparison at 18 Wildeye pistachio orchards (30 winters). These sensors are not in the public station network, so the test is independent.

**Error bar shown in the app** [`products/errorbar.py`]:
- The 80th-percentile miss: 8 in 10 tests land within it. It is grouped by distance to the nearest station (0–10, 10–25, 25–50, 50+ km) and terrain (foothill = above 150 m, or 100 m above the station).
- Early in the season it is scaled down by how much error has built up by that date, measured in the same test: Nov 1 0.17, Dec 1 0.50, Jan 1 0.65, Feb 1 0.76, Mar 1 1.0.
- **With grower readings,** the error bar is the 80th-percentile miss for readings that start on that date, from the in-orchard test: Sep 1 2.8 CP, Nov 1 3.1, Dec 1 3.4, Jan 1 3.9 (the same seasonal scaling applies).

**Honesty checks:**
- A cluster bootstrap over stations puts E4's edge over the nearest station at 0.42 CP (95% interval −0.12 to 1.22): real at 25–50 km, not proven overall.
- A pre-registered three-station blend was tested and not adopted.
- Re-running the full validation reproduces every published number exactly.

---

## 7. The outlook, the odds and the verdict

[`engine/chillprint/products/outlook.py`, `verdict.py`]

1. **Today's state:** run the Dynamic Model through yesterday and keep its state (`E`, `xi`) and the chill so far.
2. **Next 16 days:** use the Open-Meteo forecast, minus its average error at this spot over the last 14 days: `bias = mean(forecast − our hourly estimate)`. With grower readings, that average is taken against the orchard's own hours.
3. **The rest of the winter:** play every past winter at this spot (40+ complete winters) forward from today's saved state to the need date. Each past winter is first shifted to today's climate:

   ```
   T'(h) = T(h) + years_between × [ s_min(m) + p(h) · (s_max(m) − s_min(m)) ]
   ```

   Here `s_min(m)` and `s_max(m)` are the Theil–Sen trends (°C per year) of that month's average low and high at the spot, 1981–2025. The outlook backtest picked this shift: its Brier score, a measure of forecast accuracy where lower is better, was 0.0108 with the shift and 0.0111 without.
4. **Odds:**
   - P10, P50 and P90 are the 10th, 50th and 90th percentiles of the final chill across those winters.
   - Chance of meeting the need = the share of winters that reach it.
   - Backtested on every station-winter: Brier 0.0108 against 0.0168 for past-winter shares alone.
5. **Verdict:**
   - **Green:** P10 ≥ the top of the need range.
   - **Red:** P50 < the bottom of the need range.
   - **Amber:** otherwise.
6. **Closest past winter:** the one whose chill curve over the last 30 days is nearest (lowest root-mean-square difference in CP). Ties go to the closest daily mean temperatures.

---

## 8. Data gaps

[`validation/data_diet.py`] We deleted days from complete station records, filled them by straight lines, rebuilt the hours and re-counted chill. Up to 30% of days missing at random, or gaps up to 4 days, keep the typical miss under 2 CP. The readings step applies this rule.

---

## 9. Why the orchard's own low and high cut the error

### The error has three parts

For an estimate made from a station 10–30 km away, the miss at the orchard comes from:
1. **A steady microclimate difference.** The orchard sits in a cold-air pocket, or its canopy holds heat. At our 18 orchards this shows up as a consistent +2.29 CP over-count.
2. **Day-to-day weather differences.** Fog that sits over the orchard but not the station, a breeze on one night, cloud on one afternoon.
3. **The shape of the day.** How the hours between the low and the high are spread.

### Chill is very sensitive to the low and the high

Shifting real Davis hours by 1 °C changes the Mar 1 chill count by, on average over five winters:

| Change | Chill by Mar 1 |
| --- | --- |
| Every hour +1 °C | −9.7 CP (−6.9 to −14.3) |
| Every hour −1 °C | +5.6 CP |
| Daily highs +1 °C | −5.7 CP |
| Daily lows +1 °C | −3.1 CP |
| Daily highs −1 °C | +3.4 CP |

A 1 °C difference between station and orchard is normal over 10–30 km, and 1 °C is worth about 5–10 CP. The estimate can only be as good as its lows and highs.

### What the readings fix

Measured at the orchard, the low and high capture parts 1 and 2 directly: the orchard's real nights and afternoons, every day. Only part 3, the daily shape, is still borrowed from the nearest station. It's similar there because the same sun, cloud and fog drive it. In the in-orchard test:

| | Typical miss | RMSE | Systematic part (bias) | Day-to-day scatter (SD) |
| --- | --- | --- | --- | --- |
| Station data only | 3.52 CP | 4.22 CP | +2.29 CP (30% of squared error) | 3.57 CP |
| + daily low/high from Sep 1 | 1.84 CP | 2.26 CP | −0.05 CP (0%) | 2.28 CP |

The readings remove the systematic part completely and cut the scatter by a third.

### Partial winters still help

Readings from Jan 1 still bring the miss from 3.5 to 2.8 CP. The days before the readings start come from stations, so that part of the winter keeps the station error. That is why the error bar depends on the start date. **The best time to start is Sep 1; the second best is today.**

### What a grower needs

- A min/max thermometer that records the daily low and high, or any temperature logger.
- **Shade and air flow,** about 5 ft up, like a weather station (a radiation shield, or a shaded vented box). In the sun it reads warm, undercounts chill and undoes the gain (section 3 shows how much 1 °C is worth).
- Read it at the same time each day. The app treats each row as one calendar day.
- Upload the file in step 3 as a CSV with date, low, high, or a logger export.

---

## 10. What the numbers do not cover

- **Air temperature is not bud temperature.** On sunny, fog-free days buds run warmer than the air. UC's TreeChill work found bark temperature lowers chill by about 8–12 CP. The requirements are calibrated on air temperature, so we count air temperature and flag sunny stretches.
- **The chill requirements are uncertain too.** For pistachio and walnut, bud-break requirements run 19–32% above the chill linked to average yields (Pope et al. 2015). The need is shown as a range, and the "by" dates are editable until FNRIC confirms them.
- **The in-orchard test covers only pistachio.** It covers 18 orchards and 30 winters, all pistachio; the hidden-station test (855 winters) shows the same pattern.

## Sources

- Fishman S., Erez A., Couvillon G.A. (1987). The temperature dependence of dormancy breaking in plants: computer simulation of processes studied under controlled temperatures. J Theor Biol 126.
- Linvill D.E. (1990). Calculating chilling hours and chill units from daily maximum and minimum temperature observations. HortScience 25.
- Luedeling E. chillR. https://rdrr.io/cran/chillR/man/chilling.html
- UC FNRIC chilling models. https://fruitsandnuts.ucanr.edu/Weather_Services/chilling_accumulation_models/
- Martínez-Lüscher J. et al. (2022). PLOS ONE 17(5): e0267607. https://pmc.ncbi.nlm.nih.gov/articles/PMC9119484/
- Pope K.S. et al. (2015). Int J Biometeorol. https://link.springer.com/article/10.1007/s00484-014-0881-x
- UCCE chill portion requirements (K. Pope). https://ccfruitandnuts.ucanr.edu/node/128184
- Thornton P.E. et al. Daymet v4, ORNL DAAC.
