"use client";

import * as Popover from "@radix-ui/react-popover";
import { Apple, CalendarClock, Cherry, MapPin, Nut, TreeDeciduous, X, type LucideIcon } from "lucide-react";
import { useData } from "@/lib/data";
import { elev, km, mmddLabel } from "@/lib/format";
import { useStore } from "@/lib/store";
import type { Crop } from "@/lib/types";
import { Button, IconButton, InfoTip, Skeleton, cn } from "./ui";

export const CROP_ICONS: Record<string, LucideIcon> = { TreeDeciduous, Nut, Cherry, Apple };

const MONTHS = [
  ["01", "Jan"], ["02", "Feb"], ["03", "Mar"], ["04", "Apr"], ["11", "Nov"], ["12", "Dec"],
];

export function PinSummary() {
  const { s, d } = useStore();
  const { point } = useData();
  if (!s.pin) return null;
  const loc = point.data?.location;
  return (
    <div className="flex items-start gap-2">
      <MapPin size={16} aria-hidden className="mt-0.5 shrink-0 text-brand" />
      <div className="min-w-0 flex-1 text-[12px] leading-snug text-muted">
        <div className="truncate text-[14px] font-medium text-ink">
          {s.pin.label ?? `${s.pin.lat.toFixed(4)}, ${s.pin.lon.toFixed(4)}`}
        </div>
        {loc && !loc.nearest_station.id ? (
          <div className="num">{elev(loc.elev_m, s.units)} · ERA5 reanalysis (about 25 km), no stations here. Not validated.</div>
        ) : loc ? (
          <div className="num">
            {elev(loc.elev_m, s.units)} · nearest station {loc.nearest_station.name}, {km(loc.nearest_station.dist_km, s.units)}
          </div>
        ) : (
          <div>Tap the map or drag the pin to move it</div>
        )}
      </div>
      <IconButton label="Clear pin" onClick={() => d({ type: "pin", pin: null })} className="h-7 w-7">
        <X size={15} aria-hidden />
      </IconButton>
    </div>
  );
}

export default function CropPicker() {
  const { s, d } = useStore();
  const { crops } = useData();
  const list = crops.data?.crops ?? [];
  const crop: Crop | undefined = list.find((c) => c.id === s.crop);
  const variety = crop?.varieties.find((v) => v.id === s.variety);

  if (crops.loading && !list.length) {
    return (
      <div className="flex gap-2">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} className="h-9 w-16" />
        ))}
      </div>
    );
  }

  return (
    <div data-coach="crop" className="space-y-2">
      <div role="radiogroup" aria-label="Crop" className="flex flex-wrap gap-1.5">
        {list.map((c) => {
          const Icon = CROP_ICONS[c.icon] ?? TreeDeciduous;
          const on = c.id === s.crop;
          return (
            <button
              key={c.id}
              role="radio"
              aria-checked={on}
              onClick={() => {
                d({ type: "crop", crop: c.id, variety: c.varieties[0].id });
              }}
              className={cn(
                "inline-flex h-9 items-center gap-1.5 rounded-[8px] border px-2.5 text-[14px]",
                on ? "border-brand bg-brand text-white" : "border-line bg-surface text-ink hover:bg-bg",
              )}
            >
              <Icon size={15} aria-hidden />
              {c.name}
            </button>
          );
        })}
      </div>
      {crop && (
        <div className="flex flex-wrap items-center gap-2">
          <label className="sr-only" htmlFor="variety">
            Variety
          </label>
          <select
            id="variety"
            value={s.variety ?? ""}
            onChange={(e) => d({ type: "variety", variety: e.target.value })}
            className="h-9 min-w-0 flex-1 rounded-[8px] border border-line bg-surface px-2 text-[14px]"
          >
            {crop.varieties.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name} · needs {v.need_low === v.need_high ? v.need_low : `${v.need_low} to ${v.need_high}`} CP
              </option>
            ))}
          </select>
          {variety && <SeasonSettings byDefault={variety.by_date_default} />}
        </div>
      )}
      {!crop && list.length > 0 && <p className="text-[12px] text-muted">Pick your crop to see the verdict.</p>}
    </div>
  );
}

function SeasonSettings({ byDefault }: { byDefault: string }) {
  const { s, d } = useStore();
  const { validation } = useData();
  const climate = s.climate ?? validation.data?.default_ids?.climate ?? "today";
  const by = s.byOverride ?? byDefault;
  const [bm, bd] = by.split("-");
  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <Button>
          <CalendarClock size={15} aria-hidden />
          <span className="sr-only">Season settings: </span>
          <span className="num">By {mmddLabel(by)}</span>
        </Button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align="end" sideOffset={6} collisionPadding={12} className="z-[60] w-72 space-y-3 rounded-[8px] border border-line bg-surface p-3 text-[14px] shadow-lg">
          <div>
            <div className="mb-1 flex items-center gap-1 text-[12px] font-semibold text-muted">
              Need it by
              <InfoTip label="by date">Default dates are placeholders until FNRIC confirms them. Change it to match your block.</InfoTip>
            </div>
            <div className="flex gap-2">
              <select
                aria-label="Month"
                value={bm}
                onChange={(e) => d({ type: "by", by: `${e.target.value}-${bd}` })}
                className="h-9 flex-1 rounded-[8px] border border-line px-2"
              >
                {MONTHS.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
              <input
                aria-label="Day"
                type="number"
                min={1}
                max={31}
                value={Number(bd)}
                onChange={(e) => {
                  const n = Math.max(1, Math.min(31, Number(e.target.value) || 1));
                  d({ type: "by", by: `${bm}-${String(n).padStart(2, "0")}` });
                }}
                className="num h-9 w-16 rounded-[8px] border border-line px-2"
              />
            </div>
            {s.byOverride && (
              <button className="mt-1 text-[12px] text-chill underline" onClick={() => d({ type: "by", by: null })}>
                Reset to {mmddLabel(byDefault)}
              </button>
            )}
          </div>
          <div>
            <div className="mb-1 text-[12px] font-semibold text-muted">Count chill from</div>
            <div role="radiogroup" className="flex rounded-[8px] border border-line p-0.5">
              {(["sep1", "nov1"] as const).map((v) => (
                <button
                  key={v}
                  role="radio"
                  aria-checked={s.start === v}
                  onClick={() => d({ type: "start", start: v })}
                  className={cn("h-8 flex-1 rounded-[6px] text-[12px] font-semibold", s.start === v ? "bg-brand text-white" : "text-muted")}
                >
                  {v === "sep1" ? "Sep 1 (FNRIC)" : "Nov 1"}
                </button>
              ))}
            </div>
          </div>
          <div>
            <div className="mb-1 flex items-center gap-1 text-[12px] font-semibold text-muted">
              Past winters
              <InfoTip label="today's climate">
                Today&apos;s climate shifts each past winter by the local warming trend before using it in the odds. As recorded uses the winters unchanged.
              </InfoTip>
            </div>
            <div role="radiogroup" className="flex rounded-[8px] border border-line p-0.5">
              {(["today", "recorded"] as const).map((v) => (
                <button
                  key={v}
                  role="radio"
                  aria-checked={climate === v}
                  onClick={() => d({ type: "climate", climate: v })}
                  className={cn("h-8 flex-1 rounded-[6px] text-[12px] font-semibold", climate === v ? "bg-brand text-white" : "text-muted")}
                >
                  {v === "today" ? "Today's climate" : "As recorded"}
                </button>
              ))}
            </div>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
