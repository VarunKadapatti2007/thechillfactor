"""Stage the real data the API needs into engine/deploy_data/ for the Cloud Run image.

Copies: station list, CIMIS hourly store, coverage and alignment, Daymet at station pixels,
the ML fallback model, validation outputs (accuracy page, error bars), grid layers, and the raw
Daymet/ERA5 responses for the demo pins so they answer instantly. Skips rebuildable caches.

    engine/.venv/Scripts/python scripts/stage_api_data.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from chillprint import config as C  # noqa: E402
from chillprint.sources import cache, daymet  # noqa: E402

OUT = ROOT / "engine" / "deploy_data"
PROC = ["stations.parquet", "hourly_coverage.parquet", "alignment.json", "fnric_daily_chill.parquet",
        "cimis_hourly", "daymet", "models", "grid", "validation"]


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "processed").mkdir(parents=True)
    for name in PROC:
        src = C.PROCESSED_DIR / name
        dst = OUT / "processed" / name
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("e7_table.parquet"))
        elif src.exists():
            shutil.copy2(src, dst)
    # Raw responses for the demo pins (Daymet) and the global pin (ERA5), so the first request is instant.
    keep = []
    for p in C.DEMO_PINS + C.GLOBAL_DEMO_PINS:
        keep.append(cache.cache_path("daymet", daymet._key(round(p.lat, 4), round(p.lon, 4))))
    keep += list((C.CACHE_DIR / "openmeteo").glob("archive_era5_34.740_10.760_*.gz"))
    keep += list((C.CACHE_DIR / "elevation").glob("*.gz"))
    # Raw CIMIS responses for this season's completed months, so a live refresh only asks for the current month.
    from datetime import date
    today = date.today()
    y = C.current_season(today)
    for (yy, m) in [(y, 9), (y, 10), (y, 11), (y, 12), (y + 1, 1), (y + 1, 2), (y + 1, 3)]:
        if (yy, m) < (today.year, today.month):
            keep += list((C.CACHE_DIR / "cimis").glob(f"hlyE3_*_{yy:04d}-{m:02d}.gz"))
    for f in keep:
        if f.exists():
            dst = OUT / "cache" / f.parent.name / f.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"staged {total / 1e6:.0f} MB into {OUT}")


if __name__ == "__main__":
    main()
