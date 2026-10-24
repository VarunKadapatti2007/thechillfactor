"use client";

import { Play, RefreshCw } from "lucide-react";
import { centroid, useStore, type RunSpec } from "@/lib/store";
import { outlineSamples, polygonAreaKm2 } from "@/lib/area";
import { Button } from "../ui";
import { MAX_BLOCK_KM2 } from "./StepLocation";

export function buildSpec(s: ReturnType<typeof useStore>["s"]): Omit<RunSpec, "n"> | null {
  if (!s.pin || !s.crop || !s.variety || !s.readings) return null;
  if (!s.areaSkipped && !(s.drawMode === "outline" && s.outlineClosed)) return null;
  if (s.drawMode === "outline" && polygonAreaKm2(s.outline) > MAX_BLOCK_KM2) return null;
  let samplePts: [number, number][] | null = null;
  let areaLabel: string | null = null;
  if (s.drawMode === "outline" && s.outline.length >= 3) {
    samplePts = outlineSamples(s.outline, centroid(s.outline));
    areaLabel = "your outlined block";
  }
  return {
    lat: s.pin.lat,
    lon: s.pin.lon,
    label: s.pin.label,
    crop: s.crop,
    variety: s.variety,
    by: s.byOverride,
    start: s.start,
    climate: s.climate,
    samplePts: samplePts && samplePts.length > 1 ? samplePts : null,
    areaLabel: samplePts && samplePts.length > 1 ? areaLabel : null,
    readings: s.readings,
    acres: s.drawMode === "outline" && s.outlineClosed ? Math.round(polygonAreaKm2(s.outline) * 247.1) : null,
  };
}

function same(a: Omit<RunSpec, "n"> | null, b: RunSpec | null): boolean {
  if (!a || !b) return false;
  const { n: _n, readings: rb, ...rest } = b;
  void _n;
  const { readings: ra, ...restA } = a;
  return JSON.stringify(restA) === JSON.stringify(rest) && (ra?.sig ?? null) === (rb?.sig ?? null);
}

export default function RunBar({ onRun }: { onRun: () => void }) {
  const { s, d } = useStore();
  const spec = buildSpec(s);
  const upToDate = same(spec, s.run);
  const missing = !s.pin
    ? "Add your orchard first."
    : !s.areaSkipped && !(s.drawMode === "outline" && s.outlineClosed)
      ? "Finish outlining your farm first."
      : s.drawMode === "outline" && polygonAreaKm2(s.outline) > MAX_BLOCK_KM2
        ? "That outline is larger than a farm. Redraw just your orchard."
        : !s.variety
          ? "Choose your crop and type."
          : !s.readings
            ? "Add your daily temperatures."
            : null;
  return (
    <div className="space-y-1.5">
      <Button
        variant="primary"
        className="h-11 w-full text-[16px]"
        disabled={!spec || upToDate}
        onClick={() => {
          if (!spec) return;
          d({ type: "run", spec });
          onRun();
        }}
      >
        {s.run ? <RefreshCw size={16} aria-hidden /> : <Play size={16} aria-hidden />}
        {s.run ? (upToDate ? "Analysis is up to date" : "Update analysis") : "Run analysis"}
      </Button>
      {missing && <p className="text-center text-[12px] text-muted">{missing}</p>}
    </div>
  );
}
