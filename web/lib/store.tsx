"use client";

import { createContext, useContext, useMemo, useReducer, type Dispatch, type ReactNode } from "react";
import type { Units } from "./format";
import type { ClimateOpt, Readings, StartOpt } from "./types";

export type Tab = "winter" | "history" | "heat" | "accuracy";
export type GridLayer = "off" | "safe_chill" | "chill_so_far";
export type SheetSnap = "peek" | "half" | "full";

export type DrawMode = "pin" | "outline";

// Inputs frozen when the grower presses "Run analysis"; results always describe this snapshot.
export interface RunSpec {
  lat: number;
  lon: number;
  label?: string;
  crop: string;
  variety: string;
  by: string | null;
  start: StartOpt;
  climate: ClimateOpt | null;
  samplePts: [number, number][] | null; // [lat, lon] across a block
  areaLabel: string | null;
  readings: Readings | null;
  n: number;
}

export interface Pin {
  lat: number;
  lon: number;
  label?: string;
}

export interface AppState {
  pin: Pin | null;
  crop: string | null;
  variety: string | null;
  units: Units;
  start: StartOpt;
  byOverride: string | null; // MM-DD
  climate: ClimateOpt | null; // null = the validated default from the API
  tab: Tab;
  replaySeason: string | null;
  highlight: string | null;
  layers: { cimis: boolean; wildeye: boolean; grid: GridLayer };
  sheet: SheetSnap;
  flyTo: { lat: number; lon: number; zoom: number; n: number } | null;
  coach: number | null; // onboarding step 0..2, null = hidden
  drawMode: DrawMode; // "outline": the next map taps draw the farm boundary
  areaSkipped: boolean; // the grower chose to use just the pin
  outline: [number, number][]; // [lon, lat]
  outlineClosed: boolean;
  readings: Readings | null;
  run: RunSpec | null;
}

export type Action =
  | { type: "pin"; pin: Pin | null; fly?: boolean }
  | { type: "crop"; crop: string; variety?: string | null }
  | { type: "variety"; variety: string }
  | { type: "units"; units: Units }
  | { type: "start"; start: StartOpt }
  | { type: "by"; by: string | null }
  | { type: "climate"; climate: ClimateOpt }
  | { type: "tab"; tab: Tab }
  | { type: "replay"; season: string | null }
  | { type: "highlight"; season: string | null }
  | { type: "layers"; layers: Partial<AppState["layers"]> }
  | { type: "sheet"; sheet: SheetSnap }
  | { type: "coach"; step: number | null }
  | { type: "drawMode"; mode: DrawMode }
  | { type: "outlineAdd"; lon: number; lat: number }
  | { type: "outlineClose" }
  | { type: "outlineClear" }
  | { type: "outlineUndo" }
  | { type: "skipArea" }
  | { type: "drawArea" }
  | { type: "readings"; readings: Readings | null }
  | { type: "run"; spec: Omit<RunSpec, "n"> }
  | { type: "resetRun" };

const initial: AppState = {
  pin: null,
  crop: null,
  variety: null,
  units: "F",
  start: "sep1",
  byOverride: null,
  climate: null,
  tab: "winter",
  replaySeason: null,
  highlight: null,
  layers: { cimis: true, wildeye: true, grid: "off" },
  sheet: "peek",
  flyTo: null,
  coach: null,
  drawMode: "pin",
  areaSkipped: false,
  outline: [],
  outlineClosed: false,
  readings: null,
  run: null,
};

function reducer(s: AppState, a: Action): AppState {
  switch (a.type) {
    case "pin":
      // A new pin starts the farm outline around it (unless the grower chose to use just the pin).
      return {
        ...s,
        pin: a.pin,
        drawMode: a.pin && !s.areaSkipped ? "outline" : "pin",
        outline: [],
        outlineClosed: false,
        replaySeason: null,
        sheet: a.pin ? (s.sheet === "peek" ? "half" : s.sheet) : "peek",
        flyTo: a.pin && a.fly ? { lat: a.pin.lat, lon: a.pin.lon, zoom: 15, n: (s.flyTo?.n ?? 0) + 1 } : s.flyTo,
        coach: a.pin && s.coach === 0 ? 1 : s.coach,
      };
    case "crop":
      return { ...s, crop: a.crop, variety: a.variety ?? null, byOverride: null, coach: s.coach === 1 ? 2 : s.coach };
    case "variety":
      return { ...s, variety: a.variety, byOverride: null };
    case "units":
      return { ...s, units: a.units };
    case "start":
      return { ...s, start: a.start };
    case "by":
      return { ...s, byOverride: a.by };
    case "climate":
      return { ...s, climate: a.climate };
    case "tab":
      return { ...s, tab: a.tab };
    case "replay":
      return { ...s, replaySeason: a.season, tab: "winter" };
    case "highlight":
      return { ...s, highlight: a.season };
    case "layers":
      return { ...s, layers: { ...s.layers, ...a.layers } };
    case "sheet":
      return { ...s, sheet: a.sheet };
    case "coach":
      return { ...s, coach: a.step };
    case "drawMode":
      return { ...s, drawMode: a.mode, outline: [], outlineClosed: false };
    case "outlineAdd": {
      if (s.outlineClosed) return s;
      const outline = [...s.outline, [a.lon, a.lat] as [number, number]];
      return { ...s, outline, pin: s.pin ?? { lat: a.lat, lon: a.lon } };
    }
    case "outlineClose": {
      if (s.outline.length < 3) return s;
      const c = centroid(s.outline);
      return { ...s, outlineClosed: true, pin: { lat: c[1], lon: c[0], label: s.pin?.label ?? "My orchard" } };
    }
    case "outlineClear":
      return { ...s, outline: [], outlineClosed: false };
    case "outlineUndo":
      return s.outlineClosed ? s : { ...s, outline: s.outline.slice(0, -1) };
    case "skipArea":
      return { ...s, drawMode: "pin", areaSkipped: true, outline: [], outlineClosed: false };
    case "drawArea":
      return { ...s, drawMode: "outline", areaSkipped: false, outline: [], outlineClosed: false };
    case "readings":
      return { ...s, readings: a.readings };
    case "run":
      return { ...s, run: { ...a.spec, n: (s.run?.n ?? 0) + 1 }, replaySeason: null, sheet: s.sheet === "peek" ? "half" : s.sheet };
    case "resetRun":
      return { ...s, run: null, replaySeason: null };
  }
}

export function centroid(pts: [number, number][]): [number, number] {
  // Area-weighted polygon centroid (lon, lat); falls back to the vertex mean for degenerate shapes.
  let a = 0, cx = 0, cy = 0;
  for (let i = 0; i < pts.length; i++) {
    const [x0, y0] = pts[i];
    const [x1, y1] = pts[(i + 1) % pts.length];
    const f = x0 * y1 - x1 * y0;
    a += f;
    cx += (x0 + x1) * f;
    cy += (y0 + y1) * f;
  }
  if (Math.abs(a) < 1e-12) return [pts.reduce((t, p) => t + p[0], 0) / pts.length, pts.reduce((t, p) => t + p[1], 0) / pts.length];
  return [cx / (3 * a), cy / (3 * a)];
}

const Ctx = createContext<{ s: AppState; d: Dispatch<Action> } | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [s, d] = useReducer(reducer, initial);
  const v = useMemo(() => ({ s, d }), [s]);
  return <Ctx.Provider value={v}>{children}</Ctx.Provider>;
}

export function useStore() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useStore outside StoreProvider");
  return v;
}
