#!/usr/bin/env bash
# Full rebuild, Phases 1 -> 6, once CIMIS_APP_KEY is in .env. Every step reads its cache on rerun,
# so running it again makes zero network calls (GATE 1).
set -euo pipefail
cd "$(dirname "$0")/../engine"
PY=./.venv/Scripts/python.exe
[ -x "$PY" ] || PY=./.venv/bin/python
store="$PY -m chillprint.pipeline.build_station_store"

$store stations
$store fnric
$store wildeye
$store daymet
$store cimis                  # 2005-06 .. today, one station-month per request, 3 workers, 0.3 s global spacing
$store cimis --backfill       # 1982-83 .. 2004-05
$store cimis && $store cimis --backfill   # second pass fetches any months CIMIS dropped
$store qc
$PY -m chillprint.pipeline.alignment
$PY -m pytest tests -q -p no:cacheprovider                   # GATE 2 incl. Davis vs FNRIC
$PY -m chillprint.validation.ml_e7                            # Phase 6 step 1 (scored, ships only if it beats E4)
$PY -m chillprint.validation.ml_shape                         # Phase 6 step 2 (fallback curve)
$PY -m chillprint.validation.report                           # GATE 3: hidden stations, Wildeye, diet, backtest
$PY -m chillprint.pipeline.build_grid --step 0.072            # 8 km summary grid
rm -f data/processed/api_cache/*.json
$PY ../scripts/export_demo.py                                 # GATE 4 demo bundle -> web/public/demo
$PY ../scripts/readme_table.py                                # README numbers from validation_summary.json
