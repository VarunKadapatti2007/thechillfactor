"""Pydantic models for the API contract in BUILD.md section 7.

Every response carries `sources` and `method` where the contract names them.
Field names and nesting must match the contract exactly; the web app's mocks
are built from the same shapes.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- /api/crops -------------------------------------------------------------

class Variety(_Model):
    id: str
    name: str
    need_low: float
    need_high: float
    by_date_default: str  # "MM-DD"


class Crop(_Model):
    id: str
    name: str
    icon: str
    varieties: list[Variety]


class CropsResponse(_Model):
    crops: list[Crop]
    source: str
    sources: list[str] = []
    method: str = "config"


# --- /api/stations ----------------------------------------------------------

class Station(_Model):
    id: str
    name: str
    network: Literal["CIMIS", "Wildeye"]
    lat: float
    lon: float
    elev_m: Optional[float]
    active: bool
    closed: Optional[str]  # "YYYY-MM" for closed stations


class StationsResponse(_Model):
    stations: list[Station]
    sources: list[str] = []
    method: str = "fnric+cimis station lists"


# --- /api/point -------------------------------------------------------------

class NearestStation(_Model):
    id: str
    name: str
    dist_km: float


class Location(_Model):
    lat: float
    lon: float
    elev_m: Optional[float]
    nearest_station: NearestStation


class CpPoint(_Model):
    date: str
    cp: float


class Chill(_Model):
    to_date: float
    error_cp: Optional[float]
    series: list[CpPoint]


class Need(_Model):
    low: float
    high: float
    by: str  # "YYYY-MM-DD"


class FanPoint(_Model):
    date: str
    p10: float
    p50: float
    p90: float


class Outlook(_Model):
    p10: float
    p50: float
    p90: float
    chance_low: float
    chance_high: float
    n_analogs: int
    fan: list[FanPoint]


class PastSeason(_Model):
    season: str
    series: list[CpPoint]


class Closest(_Model):
    season: Optional[str]
    rmse_cp: Optional[float]


class Verdict(_Model):
    level: Literal["green", "amber", "red"]
    label: Literal["On track", "Watch", "At risk"]
    sentence: str
    early: bool


class Flags(_Model):
    sunny_stretch: Optional[bool]
    data_gaps_days: int


class PointResponse(_Model):
    location: Location
    season: str
    asof: str
    start: Literal["sep1", "nov1"]
    method: str
    chill: Chill
    need: Need
    outlook: Outlook
    past_seasons: list[PastSeason]
    closest: Closest
    verdict: Verdict
    flags: Flags
    sources: list[str]


# --- /api/orchard (additive: chill from the grower's own readings) ----------

class Flag(_Model):
    when: str
    field: Literal["low", "high", "reading"]
    value: float
    expected: Optional[float]
    reason: str


class OrchardInfo(_Model):
    kind: Literal["daily", "hourly"]
    first: str
    last: str
    days: int
    readings_hours: int
    gap_filled: int
    gap_estimated: int
    gap_unit: Literal["days", "hours"]
    before_start_from_station: bool
    station_estimate_cp: Optional[float]
    difference_cp: Optional[float]
    error_source: str
    flagged: list[Flag]
    flagged_count: int


class OrchardResponse(PointResponse):
    orchard: OrchardInfo


class ReadingsFile(_Model):
    filename: str
    content_b64: str


class OrchardRequest(_Model):
    lat: float
    lon: float
    crop: str = "pistachio"
    variety: str = "kerman"
    kind: Literal["daily", "hourly"]
    unit: Literal["F", "C"] = "F"
    dates: Optional[list[str]] = None
    lows: Optional[list[float]] = None
    highs: Optional[list[float]] = None
    times: Optional[list[str]] = None
    temps: Optional[list[float]] = None
    start: str = "sep1"
    by: Optional[str] = None
    climate: str = "today"


class AdviceRequest(OrchardRequest):
    block_acres: Optional[float] = None
    label: Optional[str] = None


# --- /api/area (additive: chill across an orchard block) ---------------------

class AreaPoint(_Model):
    lat: float
    lon: float
    elev_m: Optional[float]
    chill_to_date: float
    p10: float
    p50: float
    p90: float
    chance_low: float
    level: Literal["green", "amber", "red"]
    safe_chill_recent: Optional[float]
    method: str


class AreaResponse(_Model):
    points: list[AreaPoint]
    n_distinct_cells: int
    p50_range: list[float]
    levels: list[str]
    same_verdict: bool
    sources: list[str]
    method: str


# --- /api/history -----------------------------------------------------------

class Winter(_Model):
    season: str
    cp_by: float
    met_low: bool
    met_high: bool
    filled: bool


class Trend(_Model):
    cp_per_decade: float
    ci90: list[float]
    p_value: float
    label: Literal["likely decline", "no clear trend", "likely increase"]


class SafeChillPeriod(_Model):
    years: str
    p10: float
    ci: list[float]


class TodayReplay(_Model):
    p10: float
    p50: float


class SafeChill(_Model):
    early: SafeChillPeriod
    recent: SafeChillPeriod
    today_replay: TodayReplay


class Link(_Model):
    title: str
    url: str


class HistoryResponse(_Model):
    winters: list[Winter]
    share_met_low: float
    share_met_high: float
    trend: Trend
    safe_chill: SafeChill
    links: list[Link]
    sources: list[str]
    method: str


# --- /api/replay ------------------------------------------------------------

class Frame(_Model):
    date: str
    cp: float
    p10: float
    p50: float
    p90: float
    chance_low: float
    level: Literal["green", "amber", "red"]


class ReplayResponse(_Model):
    season: str
    frames: list[Frame]
    actual_final_cp: Optional[float]
    sources: list[str] = []
    method: str = ""


# --- /api/validation --------------------------------------------------------

class EstimatorScore(_Model):
    id: str
    name: str
    mae_cp: Optional[float]
    p80_cp: Optional[float]
    bias_cp: Optional[float]


class WildeyeEstimator(_Model):
    id: str
    mae_cp: Optional[float]


class WildeyeResult(_Model):
    n_stations: int
    estimators: list[WildeyeEstimator]


class DurhamWinter(_Model):
    season: str
    truth: Optional[float]
    e0: Optional[float]
    e3: Optional[float]
    e4: Optional[float]


class DurhamResult(_Model):
    winters: list[DurhamWinter]


class DietPoint(_Model):
    missing_pct: float
    gap_days: float
    mae_cp: float


class ReliabilityBin(_Model):
    bin: str
    predicted: float
    observed: float
    n: int


class Backtest(_Model):
    brier: Optional[float]
    brier_climatology: Optional[float]
    reliability: list[ReliabilityBin]


class ValidationResponse(_Model):
    n_stations: int
    n_station_seasons: int
    estimators: list[EstimatorScore]
    wildeye: WildeyeResult
    durham: DurhamResult
    data_diet: list[DietPoint]
    backtest: Backtest
    leakage_note: str
    sources: list[str] = []
    method: str = "hidden-station validation"
