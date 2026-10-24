// API contract types (BUILD.md section 7). Keep in sync with engine/chillprint/api/schemas.py.

export type Level = "green" | "amber" | "red";
export type StartOpt = "sep1" | "nov1";
export type ClimateOpt = "today" | "recorded";

export interface Variety {
  id: string;
  name: string;
  need_low: number;
  need_high: number;
  by_date_default: string; // MM-DD
}

export interface Crop {
  id: string;
  name: string;
  icon: string;
  varieties: Variety[];
}

export interface CropsResponse {
  crops: Crop[];
  source: string;
  sources?: string[];
  method?: string;
}

export interface Station {
  id: string;
  name: string;
  network: "CIMIS" | "Wildeye";
  lat: number;
  lon: number;
  elev_m: number | null;
  active: boolean;
  closed: string | null;
}

export interface StationsResponse {
  stations: Station[];
  sources?: string[];
}

export interface CpPoint {
  date: string;
  cp: number;
}

export interface FanPoint {
  date: string;
  p10: number;
  p50: number;
  p90: number;
}

export interface PointResponse {
  location: {
    lat: number;
    lon: number;
    elev_m: number | null;
    nearest_station: { id: string; name: string; dist_km: number };
  };
  season: string;
  asof: string;
  start: StartOpt;
  method: string;
  chill: { to_date: number; error_cp: number | null; series: CpPoint[] };
  need: { low: number; high: number; by: string };
  outlook: {
    p10: number;
    p50: number;
    p90: number;
    chance_low: number;
    chance_high: number;
    n_analogs: number;
    fan: FanPoint[];
  };
  past_seasons: { season: string; series: CpPoint[] }[];
  closest: { season: string | null; rmse_cp: number | null };
  verdict: { level: Level; label: "On track" | "Watch" | "At risk"; sentence: string; early: boolean };
  flags: { sunny_stretch: boolean | null; data_gaps_days: number };
  sources: string[];
}

// The grower's own thermometer (daily lows/highs) or logger (time, temperature) readings.
export interface Readings {
  kind: "daily" | "hourly";
  unit: "F" | "C";
  dates?: string[];
  lows?: number[];
  highs?: number[];
  times?: string[];
  temps?: number[];
  first: string;
  last: string;
  rows: number;
  source: string; // file name or "sample"
  sig: string; // identifies these readings without comparing every value
}

export interface OrchardInfo {
  kind: "daily" | "hourly";
  first: string;
  last: string;
  days: number;
  readings_hours: number;
  gap_filled: number;
  gap_estimated: number;
  gap_unit: "days" | "hours";
  before_start_from_station: boolean;
  station_estimate_cp: number | null;
  difference_cp: number | null;
  error_source: string;
  flagged: ReadingFlag[];
  flagged_count: number;
}

export interface ReadingFlag {
  when: string;
  field: "low" | "high" | "reading";
  value: number;
  expected: number | null;
  reason: string;
}

export interface OrchardResponse extends PointResponse {
  orchard: OrchardInfo;
}

export interface AdviceAction {
  title: string;
  when: string;
  why: string;
  priority: "high" | "medium" | "low";
  category: "monitor" | "protect_chill" | "bloom" | "data" | "planning";
}

export interface AdviceResponse {
  headline: string;
  summary: string;
  actions: AdviceAction[];
  watch_for: string[];
  data_notes: string[];
  longer_term: string;
  context: { season: string; as_of: string; crop: string; variety: string; chill_so_far_cp: number; verdict: string; readings_days: number };
  model: string;
}

export interface OrchardReadingsScenario {
  mae_cp: number;
  p80_cp: number;
  bias_cp: number;
  mae_mar1: number;
}

export interface OrchardReadingsSummary {
  note: string;
  tests: Record<string, { n_station_winters: number; n_sites: number; scenarios: Record<string, OrchardReadingsScenario> }>;
}

export interface Winter {
  season: string;
  cp_by: number;
  met_low: boolean;
  met_high: boolean;
  filled: boolean;
}

export interface HistoryResponse {
  winters: Winter[];
  share_met_low: number;
  share_met_high: number;
  trend: {
    cp_per_decade: number;
    ci90: [number, number];
    p_value: number;
    label: "likely decline" | "no clear trend" | "likely increase";
  };
  safe_chill: {
    early: { years: string; p10: number; ci: [number, number] };
    recent: { years: string; p10: number; ci: [number, number] };
    today_replay: { p10: number; p50: number };
  };
  links: { title: string; url: string }[];
  sources: string[];
  method?: string;
}

export interface Frame {
  date: string;
  cp: number;
  p10: number;
  p50: number;
  p90: number;
  chance_low: number;
  level: Level;
}

export interface ReplayResponse {
  season: string;
  frames: Frame[];
  actual_final_cp: number | null;
  sources?: string[];
  method?: string;
}

export interface EstimatorScore {
  id: string;
  name: string;
  mae_cp: number | null;
  p80_cp: number | null;
  bias_cp: number | null;
}

export interface StationError {
  id: string;
  name: string;
  lat: number;
  lon: number;
  dist_km: number | null;
  n_seasons: number;
  e0_mae: number | null;
  e3_mae: number | null;
  e4_mae: number | null;
}

export interface ValidationResponse {
  n_stations: number;
  n_station_seasons: number;
  estimators: EstimatorScore[];
  wildeye: { n_stations: number; estimators: { id: string; mae_cp: number | null }[] };
  durham: { winters: { season: string; truth: number | null; e0: number | null; e3: number | null; e4: number | null }[] };
  data_diet: { missing_pct: number; gap_days: number; mae_cp: number }[];
  backtest: {
    brier: number | null;
    brier_climatology: number | null;
    reliability: { bin: string; predicted: number; observed: number; n: number }[];
  };
  leakage_note: string;
  // Additive fields (not in the section 7 contract) used by the Accuracy tab.
  default_ids?: { history: string; live: string; climate?: ClimateOpt };
  by_station?: StationError[];
  diet_rule?: string | null;
  e5_note?: string | null;
  findings?: string[];
  sources?: string[];
  method?: string;
  orchard_readings?: OrchardReadingsSummary;
}

export interface GridResponse {
  type: "FeatureCollection";
  features: { type: "Feature"; geometry: { type: "Point"; coordinates: [number, number] }; properties: { value: number } }[];
  layer?: string;
  variety?: string;
  sources?: string[];
}

// Additive endpoint (not in section 7): GDD since bloom by season.
export interface HeatResponse {
  bloom: string; // MM-DD
  seasons: { season: string; series: { date: string; gdd: number }[] }[];
  latest: string | null;
  sources?: string[];
  method?: string;
}

// Additive endpoint: the same analysis at several points across an orchard block.
export interface AreaResponse {
  points: { lat: number; lon: number; elev_m: number | null; chill_to_date: number; p10: number; p50: number; p90: number; chance_low: number; level: Level; safe_chill_recent: number | null; method: string }[];
  n_distinct_cells: number;
  p50_range: [number, number];
  levels: Level[];
  same_verdict: boolean;
  sources?: string[];
  method?: string;
}

export interface DemoPin {
  id: string;
  label: string;
  lat: number;
  lon: number;
}

export interface PointQuery {
  lat: number;
  lon: number;
  crop: string;
  variety: string;
  asof?: string;
  start?: StartOpt;
  by?: string; // MM-DD
  climate?: ClimateOpt;
}
