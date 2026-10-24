"use client";

import { createContext, useContext, useMemo, useReducer, type Dispatch, type ReactNode } from "react";
import type { Units } from "./format";
import type { ClimateOpt, StartOpt } from "./types";

export type Tab = "winter" | "history" | "heat" | "accuracy";
export type GridLayer = "off" | "safe_chill" | "chill_so_far";
export type SheetSnap = "peek" | "half" | "full";

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
}

export type Action =
  | { type: "pin"; pin: Pin | null; fly?: boolean }
  | { type: "crop"; crop: string; variety: string }
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
  | { type: "coach"; step: number | null };

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
};

function reducer(s: AppState, a: Action): AppState {
  switch (a.type) {
    case "pin":
      return {
        ...s,
        pin: a.pin,
        replaySeason: null,
        sheet: a.pin ? (s.sheet === "peek" ? "half" : s.sheet) : "peek",
        flyTo: a.pin && a.fly ? { lat: a.pin.lat, lon: a.pin.lon, zoom: 10, n: (s.flyTo?.n ?? 0) + 1 } : s.flyTo,
        coach: a.pin && s.coach === 0 ? 1 : s.coach,
      };
    case "crop":
      return { ...s, crop: a.crop, variety: a.variety, byOverride: null, coach: s.coach === 1 ? 2 : s.coach };
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
  }
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
