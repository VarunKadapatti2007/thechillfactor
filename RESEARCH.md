# Does ChillPrint close the gap Julia asked about?

A scientific check of the method, what limits its accuracy, and what we changed. Every number below comes from our validation runs on real data (CIMIS hourly records, Daymet, Wildeye in-orchard sensors via FNRIC) or from the cited papers.

## Bottom line

- **The chill model is right.** The Dynamic Model (chill portions) is the standard for California fruit and nut crops. It runs on air temperature at weather-station height, the same kind of data the chill requirements were derived from.
- **The real gap is space, not the model.** A public weather station 10 to 30 km away cannot see an orchard's own microclimate. The best public-data methods, including ours and kriging in a 2022 study of 731 in-orchard stations, miss by about 3.5 to 4 chill portions (CP) over a winter. Our "any pin" estimate (E4) sits at that floor: 3.4 CP typical miss on 855 hidden-station winters, against 3.9 for the nearest station.
- **Only local data breaks through that floor.** The orchard's own daily low and high, from an inexpensive min/max thermometer or any logger, cut the typical miss at 18 real pistachio orchards from **3.5 to 1.8 CP**. They also removed the orchard bias, from +2.3 to −0.05 CP. Readings that start as late as Jan 1 still bring it to 2.8 CP.
- **What we built today.** The app now takes the grower's own readings (step 3, optional). It counts chill from them, fills short gaps by the validated rule, uses the station estimate only where the readings are missing, and shows an error bar measured for the reading's start date.

## Julia's asks, scored honestly

| Her ask | Status | Evidence |
| --- | --- | --- |
| Color-coded good or bad year | Done | Verdict card; the odds behind it beat climatology (Brier 0.0108 vs 0.0168, backtested on every station-winter) |
| "A station miles away is not my orchard" | **Partly from public data alone; solved with the grower's readings** | Public data floor about 3.5 CP (ours and the literature). With orchard readings: 1.8 CP at real orchards |
| Can a daily high and low replace hourly data? | **Yes, now in the product** | Daily low/high plus the nearest stations' hourly shape: 1.6 CP typical miss on 855 hidden-station winters, 1.8 CP at 18 orchards |
| Data has gaps | Done | Data-diet test: up to 30% scattered missing days, or gaps up to 4 days, keeps the typical miss under 2 CP. The readings step applies this rule |
| Chill so far vs past years, and what's coming | Done | Season chart, closest past winter, outlook fan from 40+ past winters |
| Land buyers need more than a few years | Done | Every winter since 1980-81 at the parcel; winters with no station record are shown faded and left out of trends |

## What the science says

### 1. The model

The Dynamic Model (Fishman, Erez and colleagues; implemented by Luedeling in chillR and by UC's FNRIC) is considered the most reliable chill model for warm-winter regions. Its author calls it "far from perfect" but much more reliable than chill hours or Utah units. Chill accrues between about 32 °F and 54 °F, most at 43 to 47 °F, and warm spells can undo chill that has not yet been fixed ([UC FNRIC chill models](https://fruitsandnuts.ucanr.edu/Weather_Services/chilling_accumulation_models/), [chillR](https://rdrr.io/cran/chillR/man/chilling.html)). Our implementation reproduces FNRIC's daily chill exactly from the same CIMIS hours (Gate 2).

### 2. Where the error comes from, largest first

| Source | Size | What we do |
| --- | --- | --- |
| **Orchard microclimate vs the nearest station** | 5 to 12 CP between a CIMIS station and orchards within 20 km in one winter ([Martínez-Lüscher et al. 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9119484/)); 3.9 CP typical miss for the nearest station in our hidden-station test | E4 adds the station-to-pin climate difference; the grower's own readings replace the estimate where they exist |
| **Chill requirement uncertainty** | Bud-break requirements for pistachio and walnut run 19 to 32% above the chill linked to average yields ([Pope et al. 2015](https://link.springer.com/article/10.1007/s00484-014-0881-x)); Kerman's 54 to 58 CP was set from the 2014 harvest ([UCCE table](https://ccfruitandnuts.ucanr.edu/node/128184)) | The need is shown as a range; the verdict uses odds against both ends; "by" dates are editable and flagged for FNRIC to confirm |
| **Bud temperature vs air temperature** | Bark temperature instead of air lowered chill by roughly 8 to 12 CP in UC's TreeChill work ([Progressive Crop](https://www.progressivecrop.com/?p=9602)); winter fog, which shades buds, fell 46% over 32 winters ([Baldocchi and Waller 2014](https://news.berkeley.edu/2014/05/20/central-valley-gets-less-winter-tule-fog-for-crops)) | Requirements are calibrated on air temperature, so we count air temperature; a sunny-stretch flag warns when buds are likely warmer |
| **Gridded daily data in valleys** | Gridded products agree near stations but can differ by more than 6 °C away from them in complex terrain (Walton and Hall 2018); PRISM ranks best overall and TopoWx best for minimum temperature against 1,231 California stations ([USGS](https://pubs.usgs.gov/publication/70241859)) | Daymet only sets the monthly station-to-pin difference (E4), never the day-to-day weather; Daymet alone (E2, E3) scored worse and is not the default |
| **Rebuilding hours from a daily low and high** | 1.6 CP typical miss in our test | The nearest stations' measured daily shape, with the textbook curve only as a fallback |

### 3. How good can a public-data estimate get?

In the largest in-orchard study in the Central Valley (731 Semios stations, 2020-21), kriging the CIMIS stations with elevation and distance to the coast explained under 10% of the spatial variation in winter chill, with an RMSE of 3.7 CP. Adding 650 in-orchard stations brought it to 2.4 CP, and the gains leveled off after about 250 added stations ([Martínez-Lüscher et al. 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9119484/)). Our results agree:

| Test (real data) | Nearest station (E0) | ChillPrint default (E4) | With the grower's readings from Sep 1 |
| --- | --- | --- | --- |
| 855 hidden CIMIS station-winters, typical miss (Feb 1 and Mar 1) | 3.9 CP | 3.4 CP | **1.6 CP** |
| 18 Wildeye pistachio orchards, 30 winters | 3.1 to 3.4 CP | 3.5 CP (bias +2.3) | **1.8 CP (bias −0.05)** |

We tried two more statistical fixes for the no-readings estimate today, with leave-one-station-out cross-validation:
- **Shrinking the Daymet offset:** 3.95 vs 3.91 CP on hidden stations (no gain), 3.29 vs 3.53 at orchards.
- **Stacking E0, E1 and E4:** 3.71 vs 3.91 MAE on hidden stations, but a worse RMSE.

Neither improved both tests, so neither ships. A pre-registered three-station blend (E8) was also not adopted earlier. The cluster-bootstrap test puts E4's edge over the nearest station at 0.42 CP (95% interval −0.12 to 1.22): real at 25 to 50 km, not proven overall. We report that as it is.

**Conclusion:** without data from the orchard itself, about 3.5 CP is the honest floor for any method built on the public station network. ChillPrint reaches it and puts a measured error bar on every number. The way past it is local data, which is why we built the readings step.

## The new readings step

**What the grower does:** upload a CSV with date, low and high (a min/max thermometer), or a logger export with date-time and temperature, in °F or °C. "Try a real example" loads last winter's daily lows and highs from a real Wildeye pistachio-orchard sensor in Terra Bella.

**What the engine does:**
1. Daily lows and highs become hours using the nearest CIMIS stations' measured shape for each day. Logger readings are averaged to hour-ending Pacific Standard Time hours.
2. Gaps up to 4 days, or 6 logger hours, are filled from the days around them. Longer gaps, and days before the readings start, use the station estimate.
3. The Dynamic Model runs once over the merged winter, so its state carries across.
4. The outlook, verdict and closest past winter come from the same validated code. The live forecast is bias-matched to the orchard's own recent readings.

**How accurate (`engine/chillprint/validation/orchard_readings.py`, real data):**

| Readings start | In orchards (18 sites, 30 winters) | Hidden stations (65 sites, 855 winters) |
| --- | --- | --- |
| No readings (station estimate) | 3.52 CP | 3.44 CP |
| Sep 1 | 1.84 CP | 1.56 CP |
| Nov 1 | 1.75 CP | 1.67 CP |
| Dec 1 | 2.16 CP | 2.19 CP |
| Jan 1 | 2.77 CP | 2.64 CP |

The error bar shown with readings is the 80th-percentile miss for the matching start date, from the in-orchard test.

**One caveat for growers:** the thermometer must be shaded and ventilated, about 5 ft up. A sunlit sensor reads warm and undercounts chill. The app says so.

## What would cut error further (next steps for FNRIC)

1. **Feed in-orchard networks into the estimate.** FNRIC already carries Wildeye stations. The Semios study shows kriging a dense in-orchard network brings the no-readings miss from 3.7 to 2.4 CP. The data path exists, but the FNRIC API has a limited budget, so this needs FNRIC's agreement.
2. **A bud-temperature correction.** TreeChill-style corrections for sunny, fog-free spells (8 to 12 CP in the cited work) would need field validation against bud phenology before shipping.
3. **Confirm the "by" dates and requirement ranges with FNRIC.** Requirement uncertainty is as large as our measurement error.
4. **Live CIMIS on the hosted server (fixed).** The rejections were not about Google Cloud: the key line in `.env` carried about 700 stray spaces and a character after the 32-character key, and CIMIS's firewall rejects a header like that from anywhere. The engine now reads only the key itself. The server re-pulls this month every 3 hours, falls back to FNRIC's relay of the same CIMIS readings if CIMIS ever refuses, and reports sources and freshness at `/api/health`.

## Sources

- Martínez-Lüscher J. et al. (2022). High-resolution weather network reveals a high spatial variability in air temperature in the Central Valley of California with implications for crop and pest management. PLOS ONE 17(5): e0267607. https://pmc.ncbi.nlm.nih.gov/articles/PMC9119484/
- Pope K.S. et al. (2015). Nut crop yield records show that budbreak-based chilling requirements may not reflect yield decline chill thresholds. Int J Biometeorol. https://link.springer.com/article/10.1007/s00484-014-0881-x
- UCCE (K. Pope, compiler). Chill portion requirements calculated using the Dynamic Model. https://ccfruitandnuts.ucanr.edu/node/128184
- UC FNRIC. Chilling accumulation models: calculation, explanation and comparison. https://fruitsandnuts.ucanr.edu/Weather_Services/chilling_accumulation_models/
- Luedeling E. chillR: statistical methods for phenology analysis in temperate fruit trees. https://rdrr.io/cran/chillR/man/chilling.html ; hourly gap interpolation: https://rdrr.io/cran/chillR/man/interpolate_gaps_hourly.html
- Baldocchi D., Waller E. (2014). Winter fog is decreasing in the fruit growing region of the Central Valley of California. GRL. Coverage: https://news.berkeley.edu/2014/05/20/central-valley-gets-less-winter-tule-fog-for-crops
- TreeChill (UC Davis): bark vs air temperature and chill. https://www.progressivecrop.com/?p=9602
- USGS: Selecting the optimal fine-scale historical climate data (1,231 California stations). https://pubs.usgs.gov/publication/70241859
- Walton D., Hall A. (2018). An assessment of high-resolution gridded temperature datasets over California. J Climate.
