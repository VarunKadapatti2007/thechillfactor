# ChillPrint validation report

Mode: **keyless**. 65 hidden stations, 884 station-winters (the same cases for every estimator). Errors pool Feb 1 and Mar 1.

## Hidden-station test (BUILD.md 5.2)

| Estimator | Mean abs error (CP) | Median | P80 | P90 | Bias | Days off at 23 CP | Days off at 54 CP | Hourly RMSE (°C) | GDD error Feb-Mar (°C-days) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E0 Nearest station | 5.32 | 3.18 | 7.11 | 11.88 | 0.18 | 5.5 | 7.3 | None | None |
| E1 3-station average | 4.61 | 2.68 | 6.26 | 10.84 | -0.05 | 4.8 | 6.7 | None | None |
| E2 Daymet + textbook curve | 4.75 | 3.68 | 7.06 | 9.7 | -2.28 | 4.8 | 7.5 | None | None |

By distance to the nearest station (mean abs error by Mar 1, CP):

| Estimator | 0-10 | 10-25 | 25-50 | 50+ |
| --- | --- | --- | --- | --- |
| E0 | 3.5 | 5.72 | 5.8 | 8.88 |
| E1 | 3.11 | 5.03 | 4.58 | 9.18 |
| E2 | 5.57 | 5.89 | 4.56 | 5.28 |

By terrain:

| Estimator | valley | foothill |
| --- | --- | --- |
| E0 | 5.41 | 8.78 |
| E1 | 4.63 | 7.89 |
| E2 | 5.4 | 4.9 |

## Findings

- The outlook beats climatology: Brier 0.021 vs 0.031.
- Today's-climate shift is off by default (Brier 0.022 with, 0.021 without).
- At Wildeye in-orchard stations: E0 3.2 CP, E2 4.0 CP.
- Even with no gaps, one daily reading misses by up to 3.2 CP in 8 of 10 winters, so no gap rule keeps error under 2 CP here.
- Run without CIMIS hourly: truth is FNRIC daily chill and only E0, E1 and E2 were possible.

Default for past winters: **E2**. Default for the live season: **E2**. Chosen by lowest mean absolute error on the headline set; nothing was tuned on the test set.

## Wildeye in-orchard test (BUILD.md 5.3)

18 stations. E0: 3.19 CP, E2: 4.01 CP

## Durham (CIMIS 12) case study (BUILD.md 5.7)

| Winter | Measured | E0 | E3 | E4 |
| --- | --- | --- | --- | --- |
| 2010-2011 | 80.63 | 78.55 | None | None |
| 2011-2012 | 70.78 | 79.3 | None | None |
| 2012-2013 | 67.83 | 60.68 | None | None |
| 2013-2014 | 58.13 | 55.05 | None | None |
| 2014-2015 | 62.91 | 51.87 | None | None |
| 2015-2016 | 70.7 | 72.05 | None | None |
| 2016-2017 | 71.35 | 66.99 | None | None |
| 2017-2018 | 71.39 | 57.87 | None | None |
| 2018-2019 | 79.11 | 77.31 | None | None |
| 2019-2020 | 66.32 | 65.97 | None | None |
| 2020-2021 | 71.55 | 71.19 | None | None |
| 2021-2022 | 73.4 | 68.8 | None | None |
| 2022-2023 | 81.72 | 83.14 | None | None |
| 2023-2024 | 72.57 | 74.68 | None | None |
| 2024-2025 | 72.23 | 75.05 | None | None |

Mean abs error: {'e0': 4.3}

## Data diet (BUILD.md 5.5)

48 station-winters. Rule: Even with no gaps, one daily reading misses by up to 3.2 CP in 8 of 10 winters, so no gap rule keeps error under 2 CP here.

| Missing % | Gap length (days) | Mean abs error | P80 |
| --- | --- | --- | --- |
| 0 | 1 | 1.64 | 3.22 |
| 5 | 1 | 1.66 | 2.83 |
| 10 | 1 | 1.8 | 2.86 |
| 20 | 1 | 1.88 | 3.05 |
| 30 | 1 | 1.93 | 3.1 |
| 40 | 1 | 2.17 | 3.76 |
| 50 | 1 | 2.64 | 4.67 |
| 0 | 3 | 1.64 | 3.22 |
| 5 | 3 | 1.99 | 3.15 |
| 10 | 3 | 1.88 | 3.09 |
| 20 | 3 | 2.1 | 3.5 |
| 30 | 3 | 2.42 | 3.9 |
| 40 | 3 | 2.85 | 4.4 |
| 50 | 3 | 3.19 | 4.82 |
| 0 | 7 | 1.64 | 3.22 |
| 5 | 7 | 2.02 | 3.48 |
| 10 | 7 | 2.17 | 3.54 |
| 20 | 7 | 2.57 | 4.28 |
| 30 | 7 | 3.27 | 4.87 |
| 40 | 7 | 3.49 | 5.53 |
| 50 | 7 | 4.64 | 7.22 |
| 0 | 14 | 1.64 | 3.22 |
| 5 | 14 | 2.27 | 3.63 |
| 10 | 14 | 2.54 | 3.93 |
| 20 | 14 | 3.39 | 5.78 |
| 30 | 14 | 4.2 | 6.47 |
| 40 | 14 | 4.85 | 7.52 |
| 50 | 14 | 5.54 | 8.21 |

## Outlook backtest (BUILD.md 5.6)

- today: Brier 0.0222 vs climatology 0.0308 (n=720)
- recorded: Brier 0.0208 vs climatology 0.0308 (n=720)

| Predicted bin | Mean predicted | Observed | n |
| --- | --- | --- | --- |
| 0.1-0.2 | 0.17 | 0.0 | 2 |
| 0.2-0.3 | 0.295 | 0.0 | 1 |
| 0.3-0.4 | 0.341 | 0.5 | 2 |
| 0.4-0.5 | 0.443 | 0.333 | 6 |
| 0.5-0.6 | 0.553 | 0.833 | 6 |
| 0.6-0.7 | 0.652 | 0.6 | 10 |
| 0.7-0.8 | 0.754 | 0.737 | 19 |
| 0.8-0.9 | 0.855 | 0.833 | 24 |
| 0.9-1.0 | 0.993 | 0.997 | 650 |

## Caveats

- Daymet may include some of the same weather records as the hidden stations, so hidden-station scores may be a little optimistic; the Wildeye in-orchard test has no such overlap.
- GDD is scored Feb 1 to Mar 31 because the hourly pull ends Mar 31, not 90 days from bloom.
- Air temperature is not bud temperature.
