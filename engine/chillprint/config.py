"""Crops, varieties, seasons, demo pins and paths.

Crop chill needs: UCCE chill portion requirements compiled by Katherine Pope,
https://ccfruitandnuts.ucanr.edu/node/128184
"By" dates are placeholders from BUILD.md section 3.6 and still need
confirmation from Julia / FNRIC (see PROGRESS.md). The UI lets growers edit them.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = ENGINE_DIR.parent
DATA_DIR = ENGINE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
CACHE_DIR = DATA_DIR / "cache"
PROCESSED_DIR = DATA_DIR / "processed"
DEMO_DIR = DATA_DIR / "demo"
VALIDATION_DIR = PROCESSED_DIR / "validation"
WEB_DEMO_DIR = REPO_DIR / "web" / "public" / "demo"

for _d in (RAW_DIR, CACHE_DIR, PROCESSED_DIR, DEMO_DIR, VALIDATION_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def _load_env() -> None:
    env = REPO_DIR / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()


def default_climate() -> str:
    """Today's-climate shift on or off by default, as decided by the outlook backtest (BUILD.md 5.6)."""
    import json
    p = VALIDATION_DIR / "validation_summary.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))["default_ids"].get("climate", "today")
    except Exception:
        return "today"


def cimis_key() -> str | None:
    return os.environ.get("CIMIS_APP_KEY") or None


SEED = 20261024

# --- Crops ------------------------------------------------------------------

CROP_SOURCE = "UCCE chill portion requirements, compiled by K. Pope (ccfruitandnuts.ucanr.edu/node/128184)"
BY_DATE_NOTE = "By dates are placeholders pending confirmation from FNRIC."


@dataclass(frozen=True)
class VarietySpec:
    id: str
    name: str
    need_low: float
    need_high: float
    by_date_default: str  # MM-DD


@dataclass(frozen=True)
class CropSpec:
    id: str
    name: str
    icon: str  # lucide-react icon name
    varieties: tuple[VarietySpec, ...]


CROPS: tuple[CropSpec, ...] = (
    CropSpec("almond", "Almond", "TreeDeciduous", (
        VarietySpec("nonpareil", "Nonpareil", 22, 23, "02-01"),
        VarietySpec("desmayo-largueta", "Desmayo Largueta", 28, 28, "02-01"),
        VarietySpec("ferragnes", "Ferragnes", 32, 32, "02-01"),
    )),
    CropSpec("pistachio", "Pistachio", "Nut", (
        VarietySpec("kerman", "Kerman", 54, 58, "03-01"),
        VarietySpec("peters", "Peters", 60, 65, "03-01"),
    )),
    CropSpec("walnut", "Walnut", "TreeDeciduous", (
        VarietySpec("chandler", "Chandler", 45, 50, "03-01"),
    )),
    CropSpec("prune", "Prune", "TreeDeciduous", (
        VarietySpec("improved-french", "Improved French", 55, 60, "03-01"),
    )),
    CropSpec("cherry", "Cherry", "Cherry", (
        VarietySpec("brooks", "Brooks", 37, 37, "02-15"),
    )),
    CropSpec("apple", "Apple", "Apple", (
        VarietySpec("golden-delicious", "Golden Delicious", 50, 50, "03-01"),
    )),
)


def find_variety(crop_id: str, variety_id: str) -> tuple[CropSpec, VarietySpec]:
    for c in CROPS:
        if c.id == crop_id:
            for v in c.varieties:
                if v.id == variety_id:
                    return c, v
    raise KeyError(f"unknown crop/variety {crop_id}/{variety_id}")


def all_varieties() -> list[tuple[CropSpec, VarietySpec]]:
    return [(c, v) for c in CROPS for v in c.varieties]


# --- Seasons ----------------------------------------------------------------

# Hourly and daily series are stored Sept 1 through Mar 31 (BUILD.md 4.1).
SEASON_END_MMDD = "03-31"
FIRST_SEASON = 1980          # 1980-1981
LAST_COMPLETE_DAYMET_SEASON = 2024  # 2024-2025: Daymet ends 2025-12-31, so 2025-26 lacks Jan-Mar
VALIDATION_FIRST_SEASON = 2005      # 2005-2006
EARLY_SEASON_MMDD = "11-15"


def season_label(start_year: int) -> str:
    return f"{start_year}-{start_year + 1}"


def season_start_year(label: str) -> int:
    return int(label.split("-")[0])


def season_of(d: date) -> int:
    """Start year of the chill season containing date d (season runs Sept 1 - Aug 31)."""
    return d.year if d.month >= 9 else d.year - 1


def season_start(start_year: int, start: str = "sep1") -> date:
    return date(start_year, 9, 1) if start == "sep1" else date(start_year, 11, 1)


def season_end(start_year: int) -> date:
    return date(start_year + 1, 3, 31)


def by_date(start_year: int, mmdd: str) -> date:
    m, d = (int(x) for x in mmdd.split("-"))
    y = start_year if m >= 9 else start_year + 1
    return date(y, m, d)


def current_season(today: date | None = None) -> int:
    return season_of(today or date.today())


# --- Stations / regions -----------------------------------------------------

CENTRAL_VALLEY_COUNTIES = (
    "Butte", "Colusa", "Fresno", "Glenn", "Kern", "Kings", "Madera", "Merced",
    "Placer", "Sacramento", "San Joaquin", "Shasta", "Solano", "Stanislaus",
    "Sutter", "Tehama", "Tulare", "Yolo", "Yuba",
)

DURHAM_ID = "CIMIS-12"

# --- Demo pins --------------------------------------------------------------


@dataclass(frozen=True)
class DemoPin:
    id: str
    label: str
    lat: float
    lon: float


DEMO_PINS: tuple[DemoPin, ...] = (
    DemoPin("durham", "Durham, Butte Co.", 39.630, -121.800),
    DemoPin("parlier", "Parlier, Fresno Co.", 36.600, -119.530),
    DemoPin("shafter", "Shafter, Kern Co.", 35.520, -119.300),
    DemoPin("davis", "Davis, Yolo Co.", 38.560, -121.800),
    DemoPin("foothill", "Foothills east of Fresno", 36.800, -119.250),
    DemoPin("westside", "West side, Fresno Co.", 36.450, -120.250),
)

# Phase 6 global pin: same engine on ERA5, labeled "Lower resolution, not validated here."
GLOBAL_DEMO_PINS: tuple[DemoPin, ...] = (
    DemoPin("sfax", "Sfax, Tunisia", 34.740, 10.760),
)

# --- Error model bins (BUILD.md 4.10) ---------------------------------------

DIST_BINS_KM = (0, 10, 25, 50, float("inf"))
DIST_BIN_LABELS = ("0-10", "10-25", "25-50", "50+")
FOOTHILL_ELEV_M = 150.0
FOOTHILL_DELEV_M = 100.0

LINKS_2050 = (
    ("UC ANR Projected Winter Chill", "https://ucanr-igis.shinyapps.io/chill/"),
    ("Cal-Adapt", "https://cal-adapt.org/"),
)

SOURCES = {
    "fnric": "FNRIC weather models API (fruitsandnuts.ucdavis.edu)",
    "cimis": "CIMIS, California Department of Water Resources",
    "daymet": "Daymet V4 R1, ORNL DAAC (doi:10.3334/ORNLDAAC/2129)",
    "gridmet": "gridMET, University of Idaho (fallback)",
    "openmeteo": "Open-Meteo (CC BY 4.0)",
    "usgs": "USGS 3DEP Elevation Point Query Service",
    "ucce": CROP_SOURCE,
}
