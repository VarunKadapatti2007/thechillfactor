# Unite Ideas entry: ChillPrint

**Title:** ChillPrint: winter chill for your orchard, not the nearest station

**One line:** A map-first tool that tells California fruit and nut growers whether this winter is enough for their trees at their exact orchard, with error bars measured by hiding real weather stations.

**Description (about 150 words):**

Fruit and nut trees need enough winter cold ("chill") to bloom well, and California's winters are getting warmer. Growers today read chill off the nearest CIMIS station, which can be miles away and in a different microclimate. ChillPrint estimates chill at any pin. It uses the nearest station with a complete record, shifted to the pin by the 1 km Daymet climate difference. It then gives a green, amber or red verdict for the grower's variety, the odds of reaching its need by a set date, the past winter this one most resembles, a day-by-day replay of any past winter, and every winter since 1980 at that parcel for land buyers. We tested it honestly: hiding 65 Central Valley stations over 855 station-winters, ChillPrint misses by 3.4 chill portions versus 3.9 for the nearest station, and one daily min/max reading at the orchard cuts that to 1.6. The engine reproduces UC Davis FNRIC's own chill numbers exactly.

**Key numbers (all from `engine/data/processed/validation/validation_summary.json`):**
- Hidden-station test: 65 stations, 855 station-winters. ChillPrint (E4) 3.44 CP typical miss vs nearest station 3.86; one daily reading 1.56.
- Outlook odds beat climatology: Brier 0.0108 vs 0.0168 (21,192 cases).
- Matches FNRIC's Davis chill to three decimals over three winters (61.613, 91.277, 83.401 CP).
- Same engine anywhere: Sfax, Tunisia (ERA5, labeled lower resolution) shows Kerman pistachio short of chill in all 46 winters.

**Built with:** CIMIS (California DWR), UC Davis FNRIC API, Daymet (ORNL), Open-Meteo, Python (FastAPI, numba, LightGBM), Next.js, MapLibre.

**Code link:** _add the public GitHub URL once the repo is published_
**Demo link:** _runs locally (`scripts/start_local.ps1`); add a hosted URL if one is set up_
**Video link:** _add the 2-minute screen recording of the demo script (README "Demo script")_
