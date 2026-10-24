"use client";

import { ChevronDown, ExternalLink, TreeDeciduous } from "lucide-react";
import { useData } from "@/lib/data";
import { EXPLAIN } from "@/lib/explain";
import { mmddLabel } from "@/lib/format";
import { useStore } from "@/lib/store";
import { CROP_ICONS } from "../CropPicker";
import { InfoTip, Skeleton, cn } from "../ui";
import StepCard from "./StepCard";

const MONTHS: [string, string][] = [["11", "November"], ["12", "December"], ["01", "January"], ["02", "February"], ["03", "March"]];

function longDate(mmdd: string) {
  const [m, d] = mmdd.split("-");
  const name = MONTHS.find(([v]) => v === m)?.[1] ?? mmddLabel(mmdd);
  return `${name} ${Number(d)}`;
}

export default function StepCrop() {
  const { s, d } = useStore();
  const { crops, validation } = useData();
  const list = crops.data?.crops ?? [];
  const crop = list.find((c) => c.id === s.crop);
  const variety = crop?.varieties.find((v) => v.id === s.variety);
  const by = s.byOverride ?? variety?.by_date_default ?? "03-01";
  const [bm, bd] = by.split("-");
  const climate = s.climate ?? validation.data?.default_ids?.climate ?? "today";

  return (
    <StepCard n={2} title="What are you growing?" done={!!variety}>
      {crops.loading && !list.length ? (
        <div className="flex gap-2">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-9 w-20" />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          <div>
            <div className="mb-1 text-[12px] font-semibold text-muted">Crop</div>
            <div role="radiogroup" aria-label="Crop" className="flex flex-wrap gap-1.5">
              {list.map((c) => {
                const Icon = CROP_ICONS[c.icon] ?? TreeDeciduous;
                const on = c.id === s.crop;
                return (
                  <button
                    key={c.id}
                    role="radio"
                    aria-checked={on}
                    onClick={() => d({ type: "crop", crop: c.id, variety: c.varieties[0].id })}
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
          </div>

          {crop && (
            <div>
              <label htmlFor="variety-select" className="mb-1 block text-[12px] font-semibold text-muted">
                Variety
              </label>
              <select
                id="variety-select"
                value={s.variety ?? ""}
                onChange={(e) => d({ type: "variety", variety: e.target.value })}
                className="h-9 w-full rounded-[8px] border border-line bg-surface px-2 text-[14px]"
              >
                {crop.varieties.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {variety && crop && (
            <div className="rounded-[8px] bg-bg p-2.5 text-[13px] leading-relaxed">
              <p>
                <strong>{variety.name}</strong> {crop.name.toLowerCase()} needs about{" "}
                <strong className="num">
                  {variety.need_low === variety.need_high ? variety.need_low : `${variety.need_low} to ${variety.need_high}`} chill portions
                </strong>{" "}
                by <strong>{longDate(by)}</strong> to bloom well.
              </p>
              <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-muted">
                <span className="inline-flex items-center gap-1">
                  What&apos;s a chill portion? <InfoTip label="chill portions">{EXPLAIN.chillPortion}</InfoTip>
                </span>
                <span className="inline-flex items-center gap-1">
                  Why {longDate(by)}? <InfoTip label="the by date">{EXPLAIN.byDate}</InfoTip>
                </span>
                <a href={EXPLAIN.needSource} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-chill underline">
                  Source: UC Cooperative Extension <ExternalLink size={11} aria-hidden />
                </a>
              </div>
            </div>
          )}

          {variety && (
            <details className="group rounded-[8px] border border-line">
              <summary className="flex cursor-pointer list-none items-center justify-between px-2.5 py-2 text-[12px] font-semibold text-muted">
                Advanced options
                <ChevronDown size={14} aria-hidden className="transition-transform group-open:rotate-180" />
              </summary>
              <div className="space-y-3 border-t border-line p-2.5 text-[12px]">
                <div>
                  <div className="mb-1 font-semibold">Need the chill by</div>
                  <div className="flex gap-2">
                    <select aria-label="Month" value={bm} onChange={(e) => d({ type: "by", by: `${e.target.value}-${bd}` })} className="h-8 flex-1 rounded-[8px] border border-line px-2">
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
                      onChange={(e) => d({ type: "by", by: `${bm}-${String(Math.max(1, Math.min(31, Number(e.target.value) || 1))).padStart(2, "0")}` })}
                      className="num h-8 w-16 rounded-[8px] border border-line px-2"
                    />
                  </div>
                  <p className="mt-1 text-muted">Roughly when buds start to swell at your block. {s.byOverride && <button className="text-chill underline" onClick={() => d({ type: "by", by: null })}>Reset to {longDate(variety.by_date_default)}</button>}</p>
                </div>
                <div>
                  <div className="mb-1 font-semibold">Start counting chill on</div>
                  <div role="radiogroup" className="flex rounded-[8px] border border-line p-0.5">
                    {(["sep1", "nov1"] as const).map((v) => (
                      <button key={v} role="radio" aria-checked={s.start === v} onClick={() => d({ type: "start", start: v })} className={cn("h-7 flex-1 rounded-[6px] font-semibold", s.start === v ? "bg-brand text-white" : "text-muted")}>
                        {v === "sep1" ? "September 1" : "November 1"}
                      </button>
                    ))}
                  </div>
                  <p className="mt-1 text-muted">September 1 matches the UC Davis FNRIC chill calculator; many growers count from November 1.</p>
                </div>
                <div>
                  <div className="mb-1 font-semibold">Use past winters</div>
                  <div role="radiogroup" className="flex rounded-[8px] border border-line p-0.5">
                    {(["today", "recorded"] as const).map((v) => (
                      <button key={v} role="radio" aria-checked={climate === v} onClick={() => d({ type: "climate", climate: v })} className={cn("h-7 flex-1 rounded-[6px] font-semibold", climate === v ? "bg-brand text-white" : "text-muted")}>
                        {v === "today" ? "Adjusted to today's warmth" : "As they happened"}
                      </button>
                    ))}
                  </div>
                  <p className="mt-1 text-muted">Winters are warmer now than in the 1980s. &quot;Adjusted&quot; warms each past winter by your spot&apos;s measured trend before using it in the odds; it scored slightly better in our tests, so it is the default.</p>
                </div>
              </div>
            </details>
          )}
        </div>
      )}
    </StepCard>
  );
}
