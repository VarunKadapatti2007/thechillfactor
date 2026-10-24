"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { getCrops, getGrid, getHeat, getHistory, getPoint, getReplay, getStations, getValidation } from "./api";
import { useAsync, type AsyncState } from "./hooks";
import { useStore } from "./store";
import type {
  CropsResponse,
  GridResponse,
  HeatResponse,
  HistoryResponse,
  PointResponse,
  ReplayResponse,
  StationsResponse,
  ValidationResponse,
} from "./types";

interface Data {
  crops: AsyncState<CropsResponse>;
  stations: AsyncState<StationsResponse>;
  point: AsyncState<PointResponse>;
  history: AsyncState<HistoryResponse>;
  replay: AsyncState<ReplayResponse>;
  heat: AsyncState<HeatResponse>;
  validation: AsyncState<ValidationResponse>;
  grid: AsyncState<GridResponse>;
  bloom: string;
  setBloom: (v: string) => void;
}

const Ctx = createContext<Data | null>(null);

export function DataProvider({ children }: { children: ReactNode }) {
  const { s } = useStore();
  const [bloom, setBloom] = useState("02-20");
  const pinKey = s.pin ? `${s.pin.lat.toFixed(4)},${s.pin.lon.toFixed(4)}` : null;
  const ready = pinKey && s.crop && s.variety;

  const crops = useAsync(getCrops, "crops");
  const stations = useAsync(getStations, "stations");
  const validation = useAsync(getValidation, "validation");

  const pointQ = ready
    ? {
        lat: s.pin!.lat,
        lon: s.pin!.lon,
        crop: s.crop!,
        variety: s.variety!,
        start: s.start === "sep1" ? undefined : s.start,
        by: s.byOverride ?? undefined,
        climate: s.climate ?? undefined,
      }
    : null;
  const point = useAsync(() => getPoint(pointQ!), pointQ ? JSON.stringify(pointQ) : null);

  const histQ = ready ? { lat: s.pin!.lat, lon: s.pin!.lon, crop: s.crop!, variety: s.variety!, by: s.byOverride ?? undefined } : null;
  const history = useAsync(() => getHistory(histQ!), histQ && s.tab === "history" ? JSON.stringify(histQ) : null);

  const repQ = ready && s.replaySeason
    ? { lat: s.pin!.lat, lon: s.pin!.lon, crop: s.crop!, variety: s.variety!, season: s.replaySeason, ...(s.climate ? { climate: s.climate } : {}) }
    : null;
  const replay = useAsync(() => getReplay(repQ!), repQ ? JSON.stringify(repQ) : null);

  const heatQ = pinKey ? { lat: s.pin!.lat, lon: s.pin!.lon, bloom } : null;
  const heat = useAsync(() => getHeat(heatQ!), heatQ && s.tab === "heat" ? JSON.stringify(heatQ) : null);

  const gridVariety = s.variety ?? "kerman";
  const grid = useAsync(
    () => getGrid(s.layers.grid as "safe_chill" | "chill_so_far", gridVariety),
    s.layers.grid === "off" ? null : `${s.layers.grid}:${gridVariety}`,
  );

  const v = useMemo(
    () => ({ crops, stations, point, history, replay, heat, validation, grid, bloom, setBloom }),
    [crops, stations, point, history, replay, heat, validation, grid, bloom],
  );
  return <Ctx.Provider value={v}>{children}</Ctx.Provider>;
}

export function useData() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useData outside DataProvider");
  return v;
}
