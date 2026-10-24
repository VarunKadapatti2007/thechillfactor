#!/usr/bin/env bash
# Full Phase 1 -> 4 rebuild once CIMIS_APP_KEY is in .env. Every step reads its cache on rerun.
set -euo pipefail
cd "$(dirname "$0")/../engine"
PY=./.venv/Scripts/python.exe
[ -x "$PY" ] || PY=./.venv/bin/python

$PY -m chillprint.pipeline.build_station_store stations
$PY -m chillprint.pipeline.build_station_store fnric
$PY -m chillprint.pipeline.build_station_store wildeye
$PY -m chillprint.pipeline.build_station_store daymet
$PY -m chillprint.pipeline.build_station_store cimis            # 2005-06 .. current, one station-month per call
$PY -m chillprint.pipeline.build_station_store qc
$PY -m chillprint.pipeline.alignment
$PY -m pytest tests -q -p no:cacheprovider                      # GATE 2 checks incl. Davis vs FNRIC
$PY -m chillprint.validation.report                             # GATE 3: hidden stations, Wildeye, diet, backtest
rm -f data/processed/pins/*.json data/processed/api_cache/*.json # rebuild pins with Method B
$PY ../scripts/export_demo.py                                   # GATE 4 demo bundle
