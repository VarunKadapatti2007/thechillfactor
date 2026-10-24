"use client";

import { LocateFixed, Undo2 } from "lucide-react";
import { useState } from "react";
import { polygonAreaKm2 } from "@/lib/area";
import { useStore, type AppState } from "@/lib/store";
import SearchBox from "../SearchBox";
import { Button } from "../ui";
import StepCard from "./StepCard";

// Larger than any orchard block, and big enough to span different climates.
export const MAX_BLOCK_KM2 = 100;

const acres = (s: AppState) => Math.round(polygonAreaKm2(s.outline) * 247.1);

export function locationDone(s: AppState): boolean {
  if (!s.pin) return false;
  if (s.areaSkipped) return true;
  return s.drawMode === "outline" && s.outlineClosed && polygonAreaKm2(s.outline) <= MAX_BLOCK_KM2;
}

export function locationSummary(s: AppState): string {
  if (!s.pin) return "";
  const where = s.pin.label && s.pin.label !== "My orchard" ? s.pin.label : `${s.pin.lat.toFixed(4)}, ${s.pin.lon.toFixed(4)}`;
  return s.areaSkipped ? `${where} · pin only` : `${where} · ${acres(s).toLocaleString()} acres`;
}

export default function StepLocation({ collapsed, onEdit }: { collapsed?: boolean; onEdit?: () => void }) {
  const { s, d } = useStore();
  const [geoMsg, setGeoMsg] = useState<string | null>(null);
  const done = locationDone(s);

  function locate() {
    if (!navigator.geolocation) {
      setGeoMsg("Your browser can't share its location. Search or tap the map.");
      return;
    }
    setGeoMsg("Finding you...");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGeoMsg(null);
        d({ type: "pin", pin: { lat: pos.coords.latitude, lon: pos.coords.longitude, label: "My location" }, fly: true });
      },
      () => setGeoMsg("Couldn't get your location. Search or tap the map."),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  const drawing = !!s.pin && s.drawMode === "outline" && !s.outlineClosed;
  const tooBig = s.outlineClosed && polygonAreaKm2(s.outline) > MAX_BLOCK_KM2;

  return (
    <StepCard n={1} title="Add my orchard" done={done} collapsed={collapsed} summary={locationSummary(s)} onEdit={onEdit}>
      <div className="space-y-3">
        <div className="flex gap-2">
          <div className="min-w-0 flex-1">
            <SearchBox />
          </div>
          <Button onClick={locate} className="shrink-0">
            <LocateFixed size={15} aria-hidden /> Locate me
          </Button>
        </div>
        {geoMsg && (
          <p className="text-[12px] text-muted" role="status">
            {geoMsg}
          </p>
        )}
        {!s.pin && <p className="text-[13px] text-muted">Or tap the map to drop a pin on your farm.</p>}

        {drawing && (
          <div className="rounded-[10px] border border-brand/40 bg-brand/5 p-3">
            <p className="text-[14px] font-semibold">Now tap each corner of your farm on the map.</p>
            <p className="mt-0.5 text-[12px] text-muted">
              {s.outline.length} corner{s.outline.length === 1 ? "" : "s"} so far{s.outline.length < 3 ? ", at least 3 needed" : ""}.
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Button variant="primary" className="h-9" disabled={s.outline.length < 3} onClick={() => d({ type: "outlineClose" })}>
                Finish
              </Button>
              <Button className="h-9" disabled={!s.outline.length} onClick={() => d({ type: "outlineUndo" })}>
                <Undo2 size={14} aria-hidden /> Undo
              </Button>
              <button className="ml-auto text-[12px] text-muted underline" onClick={() => d({ type: "skipArea" })}>
                Use just the pin
              </button>
            </div>
          </div>
        )}

        {s.pin && s.outlineClosed && (
          <div className="flex items-center justify-between gap-2 rounded-[10px] bg-bg p-3 text-[14px]">
            <span>
              {tooBig ? (
                <span className="text-red-700">That area is larger than a farm. Zoom in and draw just your orchard.</span>
              ) : (
                <>
                  Farm outlined · <strong className="num">{acres(s).toLocaleString()} acres</strong>
                </>
              )}
            </span>
            <Button className="h-8" onClick={() => d({ type: "drawArea" })}>
              Redraw
            </Button>
          </div>
        )}

        {s.pin && s.areaSkipped && (
          <div className="flex items-center justify-between gap-2 rounded-[10px] bg-bg p-3 text-[14px]">
            <span>Using the pin only.</span>
            <Button className="h-8" onClick={() => d({ type: "drawArea" })}>
              Draw my farm
            </Button>
          </div>
        )}
      </div>
    </StepCard>
  );
}
