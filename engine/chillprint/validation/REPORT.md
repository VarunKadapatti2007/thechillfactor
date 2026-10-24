# ChillPrint validation report

Mode: **full**. 65 hidden stations, 855 station-winters (the same cases for every estimator). Errors pool Feb 1 and Mar 1.

## Hidden-station test (BUILD.md 5.2)

| Estimator | Mean abs error (CP) | Median | P80 | P90 | Bias | Days off at 23 CP | Days off at 54 CP | Hourly RMSE (°C) | GDD error Feb-Mar (°C-days) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E0 Nearest station | 3.86 | 2.75 | 5.87 | 7.87 | 0.14 | 4.1 | 5.9 | None | 36.0 |
| E1 3-station average | 3.43 | 2.31 | 4.96 | 6.91 | -0.1 | 3.7 | 5.3 | None | None |
| E2 Daymet + textbook curve | 4.22 | 3.45 | 6.54 | 8.74 | -3.19 | 4.2 | 7.0 | 2.38 | 43.0 |
| E3 Daymet + borrowed shape | 4.94 | 4.43 | 7.48 | 9.46 | -4.04 | 4.8 | 8.2 | 2.03 | 43.0 |
| E4 Station + Daymet offset | 3.44 | 2.59 | 5.27 | 7.54 | 0.48 | 3.3 | 5.4 | 1.79 | None |
| E5 One reading a day | 1.56 | 1.22 | 2.48 | 3.22 | 0.2 | 1.7 | 2.6 | 1.24 | 0.0 |
| E7 Daymet + ML night-low fix (not shipped) | 4.25 | | 6.69 | | -3.31 | | | | |

By distance to the nearest station (mean abs error by Mar 1, CP):

| Estimator | 0-10 | 10-25 | 25-50 | 50+ |
| --- | --- | --- | --- | --- |
| E0 | 3.19 | 4.19 | 4.11 | 7.64 |
| E1 | 2.82 | 3.69 | 3.29 | 8.32 |
| E2 | 5.53 | 5.27 | 4.05 | 5.08 |
| E3 | 6.88 | 6.25 | 4.87 | 5.2 |
| E4 | 2.65 | 4.17 | 3.5 | 5.12 |
| E5 | 1.46 | 1.58 | 1.75 | 2.0 |

By terrain:

| Estimator | valley | foothill |
| --- | --- | --- |
| E0 | 3.92 | 7.12 |
| E1 | 3.36 | 6.81 |
| E2 | 4.87 | 4.32 |
| E3 | 5.84 | 4.59 |
| E4 | 3.77 | 4.81 |
| E5 | 1.59 | 2.13 |

## Findings

- E3 (Daymet + borrowed shape) does not beat the nearest station: typical miss 4.9 vs 3.9 CP.
- E4 (Station + Daymet offset) beats the nearest station: typical miss 3.4 vs 3.9 CP.
- One daily reading at the orchard (E5) brings the typical miss to 1.6 CP.
- The outlook beats climatology: Brier 0.0108 vs 0.0168.
- Today's-climate shift is on by default (Brier 0.0108 with, 0.0111 without).
- At Wildeye in-orchard stations: E0 3.1 CP, E2 4.0 CP, E3 5.3 CP, E4 3.5 CP.
- Up to 30% missing days scattered through the winter, or gaps up to 4 days, keeps the typical error under 2 CP (with no gaps, 8 in 10 winters land within 2.8 CP).
- Phase 6: an ML hourly shape on Daymet scores 3.55 CP vs 4.94 for the borrowed shape and 4.20 for the textbook curve (832 station-winters); it replaces the textbook curve for winters with no station record.
- Phase 6: the ML night-low fix (E7) improves Daymet (4.25 vs E3 4.96 CP) but does not beat the E4 default (3.45); not shipped.

Default for past winters: **E4**. Default for the live season: **E4**. Chosen by lowest mean absolute error on the headline set; nothing was tuned on the test set.

## Wildeye in-orchard test (BUILD.md 5.3)

18 stations. E0: 3.12 CP, E2: 4.0 CP, E3: 5.3 CP, E4: 3.52 CP

## Durham (CIMIS 12) case study (BUILD.md 5.7)

| Winter | Measured | E0 | E3 | E4 |
| --- | --- | --- | --- | --- |
| 2010-2011 | 80.16 | 73.67 | 73.13 | 75.77 |
| 2011-2012 | 79.85 | 79.39 | 74.68 | 78.98 |
| 2012-2013 | 68.07 | 67.45 | 71.26 | 72.45 |
| 2013-2014 | 57.58 | 55.59 | 51.75 | 53.21 |
| 2014-2015 | 62.9 | 59.3 | 54.38 | 58.43 |
| 2015-2016 | 70.7 | 72.05 | 70.1 | 70.8 |
| 2016-2017 | 71.35 | 66.99 | 71.97 | 65.83 |
| 2017-2018 | 71.61 | 57.86 | 65.42 | 54.23 |
| 2018-2019 | 79.11 | 77.31 | 75.85 | 77.13 |
| 2019-2020 | 66.32 | 65.97 | 59.61 | 63.78 |
| 2020-2021 | 71.55 | 71.46 | 69.74 | 70.3 |
| 2021-2022 | 73.39 | 68.73 | 61.86 | 64.99 |
| 2022-2023 | 81.72 | 83.14 | 79.68 | 80.55 |
| 2023-2024 | 72.57 | 74.67 | 60.21 | 69.89 |
| 2024-2025 | 72.23 | 75.05 | 68.37 | 72.06 |

Mean abs error: {'e0': 3.06, 'e3': 5.25, 'e4': 3.98}

## Data diet (BUILD.md 5.5)

160 station-winters. Rule: Up to 30% missing days scattered through the winter, or gaps up to 4 days, keeps the typical error under 2 CP (with no gaps, 8 in 10 winters land within 2.8 CP).

| Missing % | Gap length (days) | Mean abs error | P80 |
| --- | --- | --- | --- |
| 0 | 1 | 1.73 | 2.75 |
| 5 | 1 | 1.76 | 2.93 |
| 10 | 1 | 1.75 | 2.76 |
| 20 | 1 | 1.95 | 3.06 |
| 30 | 1 | 1.96 | 3.14 |
| 40 | 1 | 2.22 | 3.57 |
| 50 | 1 | 2.43 | 4.0 |
| 0 | 3 | 1.73 | 2.75 |
| 5 | 3 | 1.83 | 2.98 |
| 10 | 3 | 1.91 | 3.02 |
| 20 | 3 | 2.07 | 3.3 |
| 30 | 3 | 2.33 | 3.67 |
| 40 | 3 | 2.64 | 4.28 |
| 50 | 3 | 2.72 | 4.55 |
| 0 | 7 | 1.73 | 2.75 |
| 5 | 7 | 1.96 | 3.07 |
| 10 | 7 | 2.11 | 3.23 |
| 20 | 7 | 2.45 | 4.02 |
| 30 | 7 | 2.94 | 4.72 |
| 40 | 7 | 3.43 | 5.46 |
| 50 | 7 | 4.15 | 6.51 |
| 0 | 14 | 1.73 | 2.75 |
| 5 | 14 | 2.17 | 3.4 |
| 10 | 14 | 2.42 | 3.87 |
| 20 | 14 | 3.33 | 5.39 |
| 30 | 14 | 3.8 | 6.08 |
| 40 | 14 | 4.44 | 7.44 |
| 50 | 14 | 5.22 | 8.34 |

## Outlook backtest (BUILD.md 5.6)

- today: Brier 0.0108 vs climatology 0.0168 (n=21192)
- recorded: Brier 0.0111 vs climatology 0.0168 (n=21192)

| Predicted bin | Mean predicted | Observed | n |
| --- | --- | --- | --- |
| 0.0-0.1 | 0.032 | 0.0 | 21 |
| 0.1-0.2 | 0.161 | 0.0 | 8 |
| 0.2-0.3 | 0.25 | 0.0 | 16 |
| 0.3-0.4 | 0.355 | 0.0 | 13 |
| 0.4-0.5 | 0.451 | 0.105 | 19 |
| 0.5-0.6 | 0.556 | 0.2 | 50 |
| 0.6-0.7 | 0.654 | 0.377 | 69 |
| 0.7-0.8 | 0.755 | 0.659 | 123 |
| 0.8-0.9 | 0.851 | 0.775 | 298 |
| 0.9-1.0 | 0.997 | 0.995 | 20575 |

## Caveats

- Daymet may include some of the same weather records as the hidden stations, so hidden-station scores may be a little optimistic; the Wildeye in-orchard test has no such overlap.
- GDD is scored Feb 1 to Mar 31 because the hourly pull ends Mar 31, not 90 days from bloom.
- Air temperature is not bud temperature.
