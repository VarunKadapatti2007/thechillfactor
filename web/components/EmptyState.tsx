"use client";

import { Globe, History, MapPin, Play } from "lucide-react";
import { useStore } from "@/lib/store";
import { Button } from "./ui";

export const QUICK_PICKS = [
  { id: "durham", label: "Durham, Butte Co.", lat: 39.63, lon: -121.8 },
  { id: "parlier", label: "Parlier, Fresno Co.", lat: 36.6, lon: -119.53 },
  { id: "shafter", label: "Shafter, Kern Co.", lat: 35.52, lon: -119.3 },
];

export default function EmptyState() {
  const { d } = useStore();
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-[20px] font-semibold">Is this winter enough for your trees?</h2>
        <p className="mt-1 text-[14px] text-muted">Drop a pin on your orchard to see chill at that spot, not at the nearest station.</p>
      </div>
      <div>
        <div className="mb-2 text-[12px] font-semibold text-muted">Try a demo orchard</div>
        <div className="flex flex-col gap-2">
          {QUICK_PICKS.map((p) => (
            <Button key={p.id} className="justify-start" onClick={() => d({ type: "pin", pin: { lat: p.lat, lon: p.lon, label: p.label }, fly: true })}>
              <MapPin size={15} aria-hidden className="text-brand" />
              {p.label}
            </Button>
          ))}
        </div>
      </div>
      <Button
        variant="primary"
        className="w-full"
        onClick={() => {
          const p = QUICK_PICKS[2];
          d({ type: "pin", pin: { lat: p.lat, lon: p.lon, label: p.label }, fly: true });
          d({ type: "crop", crop: "pistachio", variety: "kerman" });
          d({ type: "replay", season: "2014-2015" });
        }}
      >
        <History size={15} aria-hidden />
        Replay winter 2014-15
        <Play size={13} aria-hidden />
      </Button>
      <div className="border-t border-line pt-3">
        <div className="mb-2 text-[12px] font-semibold text-muted">Same engine, elsewhere</div>
        <Button
          className="w-full justify-start"
          onClick={() => d({ type: "pin", pin: { lat: 34.74, lon: 10.76, label: "Sfax, Tunisia (lower resolution, not validated)" }, fly: true })}
        >
          <Globe size={15} aria-hidden className="text-chill" />
          Sfax, Tunisia
        </Button>
      </div>
    </div>
  );
}
