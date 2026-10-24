"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { getArea, getCrops, getGrid, getHeat, getHistory, getPoint, getReplay, getStations, getValidation, postOrchard } from "./api";
import { useAsync, type AsyncState } from "./hooks";
import { useStore } from "./store";
import type {
  AreaResponse,
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
  area: AsyncState<AreaResponse>;
  bloom: string;
  setBloom: (v: string) => void;
}

const Ctx = createContext<Data | null>(null);

// Everything below "run" is fetched only after the grower presses Run analysis, from the frozen inputs.
export function DataProvider({ children }: { children: ReactNode }) {
  const { s } = useStore();
  const [bloom, setBloom] = useState("02-20");
  const r = s.run;

  const crops = useAsync(getCrops, "crops");
  const stations = useAsync(getStations, "stations");
  const validation = useAsync(getValidation, "validation");

  const pointQ = r
    ? {
        lat: r.lat,
        lon: r.lon,
        crop: r.crop,
        variety: r.variety,
        start: r.start === "sep1" ? undefined : r.start,
        by: r.by ?? undefined,
        climate: r.climate ?? undefined,
      }
    : null;
  // With the grower's own readings, the main answer comes from them (POST /api/orchard).
  const point = useAsync<PointResponse>(
    () => (r?.readings ? postOrchard(pointQ!, r.readings) : getPoint(pointQ!)),
    pointQ ? `${r!.n}:${JSON.stringify(pointQ)}:${r!.readings?.sig ?? ""}` : null,
  );

  const histQ = r ? { lat: r.lat, lon: r.lon, crop: r.crop, variety: r.variety, by: r.by ?? undefined } : null;
  // Secondary sections load after the main answer so they never slow it down.
  const history = useAsync(() => getHistory(histQ!), histQ && point.data ? JSON.stringify(histQ) : null);

  const repQ = r && s.replaySeason
    ? { lat: r.lat, lon: r.lon, crop: r.crop, variety: r.variety, season: s.replaySeason, ...(r.climate ? { climate: r.climate } : {}) }
    : null;
  const replay = useAsync(() => getReplay(repQ!), repQ ? JSON.stringify(repQ) : null);

  const heatQ = r ? { lat: r.lat, lon: r.lon, bloom } : null;
  const heat = useAsync(() => getHeat(heatQ!), heatQ && point.data ? JSON.stringify(heatQ) : null);

  // The block check starts after the main answer, so the two do not compete on the server.
  const areaQ = r && r.samplePts && r.samplePts.length > 1 && point.data
    ? { pts: r.samplePts, crop: r.crop, variety: r.variety, by: r.by ?? undefined, start: r.start === "sep1" ? undefined : r.start, climate: r.climate ?? undefined }
    : null;
  const area = useAsync(() => getArea(areaQ!), areaQ ? `${r!.n}:${JSON.stringify(areaQ)}` : null);

  const gridVariety = r?.variety ?? s.variety ?? "kerman";
  const grid = useAsync(
    () => getGrid(s.layers.grid as "safe_chill" | "chill_so_far", gridVariety),
    s.layers.grid === "off" ? null : `${s.layers.grid}:${gridVariety}`,
  );

  const v = useMemo(
    () => ({ crops, stations, point, history, replay, heat, validation, grid, area, bloom, setBloom }),
    [crops, stations, point, history, replay, heat, validation, grid, area, bloom],
  );
  return <Ctx.Provider value={v}>{children}</Ctx.Provider>;
}

export function useData() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useData outside DataProvider");
  return v;
}
