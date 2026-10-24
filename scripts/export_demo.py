"""Write the offline demo bundle into web/public/demo/ (BUILD.md Phase 4 step 7).

Full API responses for the six demo pins, every crop and variety, the 2014-15
and 2015-16 replays, heat for the default bloom date, plus crops, stations,
validation and grid layers. Goes through the real FastAPI app, so every file
passes the same schema checks as the live API.

    engine/.venv/Scripts/python scripts/export_demo.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from fastapi.testclient import TestClient  # noqa: E402

from chillprint import config as C  # noqa: E402
from chillprint.api.main import app  # noqa: E402

OUT = C.WEB_DEMO_DIR
REPLAYS = ("2014-2015", "2015-2016")
BLOOMS = ("02-20",)


def dump(rel: str, obj) -> int:
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    s = json.dumps(obj, separators=(",", ":"))
    assert '"mock"' not in s, f"mock data leaked into {rel}"
    p.write_text(s, encoding="utf-8")
    return len(s)


def main() -> None:
    t0 = time.time()
    c = TestClient(app)
    total = 0
    all_pins = C.DEMO_PINS + C.GLOBAL_DEMO_PINS
    pins = [{"id": p.id, "label": p.label, "lat": p.lat, "lon": p.lon} for p in all_pins]
    total += dump("pins.json", pins)
    for name in ("crops", "stations"):
        r = c.get(f"/api/{name}")
        r.raise_for_status()
        total += dump(f"{name}.json", r.json())
    r = c.get("/api/validation")
    if r.status_code == 200:
        total += dump("validation.json", r.json())
    else:
        print("validation not available:", r.status_code)
    for layer in ("safe_chill", "chill_so_far"):
        for _, v in C.all_varieties():
            r = c.get("/api/grid", params={"layer": layer, "variety": v.id})
            if r.status_code == 200:
                total += dump(f"grid/{layer}_{v.id}.json", r.json())
    for p in all_pins:
        tp = time.time()
        for crop, v in C.all_varieties():
            q = {"lat": p.lat, "lon": p.lon, "crop": crop.id, "variety": v.id}
            r = c.get("/api/point", params=q)
            r.raise_for_status()
            total += dump(f"point/{p.id}_{crop.id}_{v.id}.json", r.json())
            r = c.get("/api/history", params=q)
            r.raise_for_status()
            total += dump(f"history/{p.id}_{crop.id}_{v.id}.json", r.json())
            for season in REPLAYS:
                r = c.get("/api/replay", params={**q, "season": season})
                r.raise_for_status()
                total += dump(f"replay/{p.id}_{crop.id}_{v.id}_{season}.json", r.json())
        for b in BLOOMS:
            r = c.get("/api/heat", params={"lat": p.lat, "lon": p.lon, "bloom": b})
            r.raise_for_status()
            total += dump(f"heat/{p.id}_{b}.json", r.json())
        print(f"  {p.id}: {time.time() - tp:.1f}s")
    print(f"demo bundle: {total / 1e6:.1f} MB in {OUT} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
