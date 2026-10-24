// Typed client for the ChillPrint API.
//
// - USE_MOCKS (NEXT_PUBLIC_USE_MOCKS=1, dev only) serves web/mocks/*.json.
// - Otherwise calls the FastAPI server at NEXT_PUBLIC_API_BASE.
// - If the API fails (offline, server down), falls back to the static export in
//   public/demo/ written by scripts/export_demo.py. The fallback is automatic.

import type {
  CropsResponse,
  DemoPin,
  AreaResponse,
  GridResponse,
  HeatResponse,
  HistoryResponse,
  AdviceResponse,
  OrchardResponse,
  PointQuery,
  Readings,
  PointResponse,
  ReplayResponse,
  StationsResponse,
  ValidationResponse,
} from "./types";

export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000").replace(/\/$/, "");
export const USE_MOCKS = process.env.NODE_ENV !== "production" && process.env.NEXT_PUBLIC_USE_MOCKS === "1";

export type DataOrigin = "api" | "demo" | "mock";

export interface Result<T> {
  data: T;
  origin: DataOrigin;
}

export class NoDataError extends Error {}

async function loadMock<T>(name: string): Promise<T> {
  // Guarded so production builds drop the mock files entirely.
  if (process.env.NODE_ENV !== "production") {
    const mod = await import(`../mocks/${name}.json`);
    return mod.default as T;
  }
  throw new NoDataError("mocks are disabled in production");
}

async function getJson<T>(url: string, timeoutMs = 15000): Promise<T> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const r = await fetch(url, { signal: ctl.signal });
    if (!r.ok) throw new Error(`${r.status} ${url}`);
    return (await r.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

function qs(params: Record<string, string | number | undefined>): string {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") u.set(k, String(v));
  return u.toString();
}

// --- demo export lookup ------------------------------------------------------

let demoPinsCache: DemoPin[] | null = null;

export async function demoPins(): Promise<DemoPin[]> {
  if (demoPinsCache) return demoPinsCache;
  try {
    demoPinsCache = await getJson<DemoPin[]>("/demo/pins.json", 5000);
  } catch {
    demoPinsCache = [];
  }
  return demoPinsCache;
}

async function nearestDemoPin(lat: number, lon: number): Promise<DemoPin | null> {
  const pins = await demoPins();
  let best: DemoPin | null = null;
  let bestD = Infinity;
  for (const p of pins) {
    const d = Math.hypot(p.lat - lat, (p.lon - lon) * Math.cos((lat * Math.PI) / 180));
    if (d < bestD) {
      bestD = d;
      best = p;
    }
  }
  return best && bestD < 0.03 ? best : null; // ~3 km
}

// A brand-new location builds 45 winters on the server (5-10 s, longer when several run at once).
const API_TIMEOUT_MS = 60000;

async function withFallback<T>(apiUrl: string, demoPath: () => Promise<string | null>, mockName: string): Promise<Result<T>> {
  if (USE_MOCKS) return { data: await loadMock<T>(mockName), origin: "mock" };
  try {
    return { data: await getJson<T>(apiUrl, API_TIMEOUT_MS), origin: "api" };
  } catch (err) {
    const path = await demoPath();
    if (!path) throw err instanceof Error ? err : new Error(String(err));
    return { data: await getJson<T>(path, 8000), origin: "demo" };
  }
}

// --- endpoints ---------------------------------------------------------------

export function getCrops() {
  return withFallback<CropsResponse>(`${API_BASE}/api/crops`, async () => "/demo/crops.json", "crops");
}

export function getStations() {
  return withFallback<StationsResponse>(`${API_BASE}/api/stations`, async () => "/demo/stations.json", "stations");
}

export function getValidation() {
  return withFallback<ValidationResponse>(`${API_BASE}/api/validation`, async () => "/demo/validation.json", "validation");
}

export function getGrid(layer: "safe_chill" | "chill_so_far", variety: string) {
  return withFallback<GridResponse>(
    `${API_BASE}/api/grid?${qs({ layer, variety })}`,
    async () => `/demo/grid/${layer}_${variety}.json`,
    "grid",
  );
}

export function getPoint(q: PointQuery) {
  return withFallback<PointResponse>(
    `${API_BASE}/api/point?${qs({ ...q })}`,
    async () => {
      // The demo export only holds the default view (no custom as-of / by / start).
      if (q.asof || (q.start && q.start !== "sep1") || q.by || q.climate) return null;
      const pin = await nearestDemoPin(q.lat, q.lon);
      return pin ? `/demo/point/${pin.id}_${q.crop}_${q.variety}.json` : null;
    },
    "point",
  );
}

function readingsBody(q: PointQuery, rd: Readings) {
  return {
    lat: q.lat, lon: q.lon, crop: q.crop, variety: q.variety, kind: rd.kind, unit: rd.unit,
    ...(rd.kind === "daily" ? { dates: rd.dates, lows: rd.lows, highs: rd.highs } : { times: rd.times, temps: rd.temps }),
    ...(q.start ? { start: q.start } : {}), ...(q.by ? { by: q.by } : {}), ...(q.climate ? { climate: q.climate } : {}),
  };
}

async function postJson<T>(path: string, body: unknown, timeoutMs: number): Promise<Result<T>> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const r = await fetch(`${API_BASE}${path}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal: ctl.signal,
    });
    if (!r.ok) {
      let msg = `${r.status}`;
      try { msg = ((await r.json()) as { detail?: string }).detail ?? msg; } catch {}
      throw new Error(msg);
    }
    return { data: (await r.json()) as T, origin: "api" };
  } finally {
    clearTimeout(timer);
  }
}

// What to do next: the server rebuilds this farm's whole picture from the same inputs and asks Claude.
export function postAdvice(q: PointQuery, rd: Readings, extra: { block_acres: number | null; label?: string }) {
  return postJson<AdviceResponse>("/api/advice", { ...readingsBody(q, rd), block_acres: extra.block_acres, label: extra.label }, 150000);
}

// The grower's own readings always go to the live API (they are never in the offline bundle).
export async function postOrchard(q: PointQuery, rd: Readings): Promise<Result<OrchardResponse>> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 120000);
  const body = readingsBody(q, rd);
  try {
    const r = await fetch(`${API_BASE}/api/orchard`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal: ctl.signal,
    });
    if (!r.ok) {
      let msg = `${r.status}`;
      try { msg = ((await r.json()) as { detail?: string }).detail ?? msg; } catch {}
      throw new Error(msg);
    }
    return { data: (await r.json()) as OrchardResponse, origin: "api" };
  } finally {
    clearTimeout(timer);
  }
}

export function getHistory(q: { lat: number; lon: number; crop: string; variety: string; by?: string }) {
  return withFallback<HistoryResponse>(
    `${API_BASE}/api/history?${qs({ ...q })}`,
    async () => {
      if (q.by) return null;
      const pin = await nearestDemoPin(q.lat, q.lon);
      return pin ? `/demo/history/${pin.id}_${q.crop}_${q.variety}.json` : null;
    },
    "history",
  );
}

export async function getArea(q: { pts: [number, number][]; crop: string; variety: string; by?: string; start?: string; climate?: string }): Promise<Result<AreaResponse>> {
  const pts = q.pts.map(([a, b]) => `${a.toFixed(4)},${b.toFixed(4)}`).join(";");
  // Blocks are never in the offline bundle; this needs the live API.
  return { data: await getJson<AreaResponse>(`${API_BASE}/api/area?${qs({ pts, crop: q.crop, variety: q.variety, by: q.by, start: q.start, climate: q.climate })}`, 120000), origin: "api" };
}

export function getHeat(q: { lat: number; lon: number; bloom: string }) {
  return withFallback<HeatResponse>(
    `${API_BASE}/api/heat?${qs({ ...q })}`,
    async () => {
      const pin = await nearestDemoPin(q.lat, q.lon);
      return pin ? `/demo/heat/${pin.id}_${q.bloom}.json` : null;
    },
    "heat",
  );
}

export function getReplay(q: { lat: number; lon: number; crop: string; variety: string; season: string; climate?: string }) {
  return withFallback<ReplayResponse>(
    `${API_BASE}/api/replay?${qs({ ...q })}`,
    async () => {
      if (q.climate) return null;
      const pin = await nearestDemoPin(q.lat, q.lon);
      return pin ? `/demo/replay/${pin.id}_${q.crop}_${q.variety}_${q.season}.json` : null;
    },
    "replay",
  );
}
