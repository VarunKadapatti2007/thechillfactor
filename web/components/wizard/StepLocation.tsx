"use client";

import * as Slider from "@radix-ui/react-slider";
import { Circle, LocateFixed, MapPin, PenLine, Undo2 } from "lucide-react";
import { useState } from "react";
import { polygonAreaKm2 } from "@/lib/area";
import { EXPLAIN } from "@/lib/explain";
import { useStore, type DrawMode } from "@/lib/store";
import { QUICK_PICKS } from "../EmptyState";
import SearchBox from "../SearchBox";
import { Button, InfoTip, cn } from "../ui";
import StepCard from "./StepCard";

const MODES: { v: DrawMode; label: string; icon: typeof MapPin }[] = [
  { v: "pin", label: "One spot", icon: MapPin },
  { v: "circle", label: "Circle", icon: Circle },
  { v: "outline", label: "Draw outline", icon: PenLine },
];

export default function StepLocation() {
  const { s, d } = useStore();
  const [geoMsg, setGeoMsg] = useState<string | null>(null);

  function locate() {
    if (!navigator.geolocation) {
      setGeoMsg("Your browser can't share its location. Search or tap the map instead.");
      return;
    }
    setGeoMsg("Finding you...");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGeoMsg(null);
        d({ type: "pin", pin: { lat: pos.coords.latitude, lon: pos.coords.longitude, label: "My location" }, fly: true });
      },
      () => setGeoMsg("Couldn't get your location. Allow location access, or search or tap the map."),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  const where = s.pin ? s.pin.label ?? `${s.pin.lat.toFixed(4)}, ${s.pin.lon.toFixed(4)}` : null;
  const blockText =
    s.drawMode === "circle" && s.pin
      ? `Circle, ${s.radiusKm.toFixed(1)} km radius`
      : s.drawMode === "outline" && s.outlineClosed
        ? `Outlined block, about ${(polygonAreaKm2(s.outline) * 247.1).toFixed(0)} acres`
        : null;

  return (
    <StepCard n={1} title="Where is your orchard?" done={!!s.pin && (s.drawMode !== "outline" || s.outlineClosed)}>
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={locate}>
            <LocateFixed size={15} aria-hidden /> Locate me
          </Button>
          <span className="text-[12px] text-muted">or search, or tap the map</span>
        </div>
        {geoMsg && <p className="text-[12px] text-muted" role="status">{geoMsg}</p>}
        <SearchBox />

        <div>
          <div className="mb-1 flex items-center gap-1 text-[12px] font-semibold text-muted">
            Mark
            <InfoTip label="marking a block">{EXPLAIN.block}</InfoTip>
          </div>
          <div role="radiogroup" aria-label="How to mark your orchard" className="grid grid-cols-3 gap-1 rounded-[8px] bg-bg p-1">
            {MODES.map((m) => {
              const Icon = m.icon;
              return (
                <button
                  key={m.v}
                  role="radio"
                  aria-checked={s.drawMode === m.v}
                  onClick={() => d({ type: "drawMode", mode: m.v })}
                  className={cn(
                    "flex h-9 items-center justify-center gap-1.5 rounded-[6px] text-[12px] font-medium",
                    s.drawMode === m.v ? "bg-surface text-ink shadow-sm" : "text-muted",
                  )}
                >
                  <Icon size={14} aria-hidden /> {m.label}
                </button>
              );
            })}
          </div>
        </div>

        {s.drawMode === "circle" && (
          <div>
            <div className="mb-1 flex justify-between text-[12px] text-muted">
              <span>{s.pin ? "Radius around your pin" : "Tap the map for the center, then set the radius"}</span>
              <span className="num font-medium text-ink">{s.radiusKm.toFixed(1)} km</span>
            </div>
            <Slider.Root
              className="relative flex h-5 touch-none select-none items-center"
              min={0.5}
              max={5}
              step={0.5}
              value={[s.radiusKm]}
              onValueChange={([v]) => d({ type: "radius", km: v })}
              aria-label="Circle radius in kilometers"
            >
              <Slider.Track className="relative h-1.5 grow rounded-full bg-line">
                <Slider.Range className="absolute h-full rounded-full bg-brand" />
              </Slider.Track>
              <Slider.Thumb className="block h-5 w-5 rounded-full border-2 border-brand bg-surface shadow" aria-label={`${s.radiusKm} km`} />
            </Slider.Root>
          </div>
        )}

        {s.drawMode === "outline" && (
          <div className="rounded-[8px] bg-bg p-2 text-[12px]">
            {s.outlineClosed ? (
              <span>Block outlined.</span>
            ) : (
              <span>Tap the map at each corner of your block ({s.outline.length} so far, 3 or more needed), then press Finish.</span>
            )}
            <div className="mt-2 flex gap-2">
              {!s.outlineClosed && (
                <Button className="h-8 min-h-8 px-2 text-[12px]" disabled={s.outline.length < 3} onClick={() => d({ type: "outlineClose" })}>
                  Finish outline
                </Button>
              )}
              {s.outline.length > 0 && (
                <Button className="h-8 min-h-8 px-2 text-[12px]" onClick={() => d({ type: "outlineClear" })}>
                  <Undo2 size={13} aria-hidden /> Start again
                </Button>
              )}
            </div>
          </div>
        )}

        {where && (
          <p className="flex items-start gap-1.5 text-[12px] text-ink">
            <MapPin size={14} aria-hidden className="mt-0.5 shrink-0 text-brand" />
            <span>
              <span className="font-medium">{where}</span>
              {blockText && <span className="text-muted"> · {blockText}</span>}
            </span>
          </p>
        )}

        {!s.pin && (
          <div className="text-[12px] text-muted">
            Or try a demo orchard:{" "}
            {QUICK_PICKS.map((p, i) => (
              <span key={p.id}>
                <button className="text-chill underline" onClick={() => d({ type: "pin", pin: { lat: p.lat, lon: p.lon, label: p.label }, fly: true })}>
                  {p.label}
                </button>
                {i < QUICK_PICKS.length - 1 ? ", " : ""}
              </span>
            ))}
          </div>
        )}
      </div>
    </StepCard>
  );
}
