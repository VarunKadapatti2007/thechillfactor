"use client";

import { CalendarClock, Percent, Snowflake, Thermometer } from "lucide-react";
import type { ReactNode } from "react";
import { useData } from "@/lib/data";
import { EXPLAIN, plainVerdict } from "@/lib/explain";
import { inTen, longDate, shortDate } from "@/lib/format";
import { useStore } from "@/lib/store";
import type { OrchardInfo, OrchardResponse, PointResponse } from "@/lib/types";
import { InfoTip, LEVEL, Skeleton, StatusPill } from "../ui";

function Row({ icon, label, info, children }: { icon: ReactNode; label: string; info: string; children: ReactNode }) {
  return (
    <div className="flex gap-3 border-t border-line py-3 first:border-t-0">
      <span className="mt-0.5 shrink-0 text-chill" aria-hidden>
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1 text-[12px] font-semibold text-muted">
          {label}
          <InfoTip label={label}>{info}</InfoTip>
        </div>
        <div className="text-[14px] leading-snug text-ink">{children}</div>
      </div>
    </div>
  );
}

function FlagNote({ o, unit }: { o: OrchardInfo; unit: string }) {
  const n = o.flagged_count ?? 0;
  if (!n) return null;
  return (
    <div className="mt-2 rounded-[8px] border border-amber-300 bg-amber-50 p-2.5 text-[12px] leading-relaxed text-amber-900" role="status">
      <p className="font-semibold">
        {n} reading{n > 1 ? "s" : ""} set aside (looked wrong):
      </p>
      <ul className="mt-1 list-disc pl-4">
        {(o.flagged ?? []).slice(0, 6).map((f) => (
          <li key={`${f.when}-${f.field}`}>
            {f.when}: {f.field} {f.value}°{unit}
            {f.expected !== null ? `, stations suggest about ${Math.round(f.expected)}°` : ""}
          </li>
        ))}
      </ul>
      {n > 6 && <p className="mt-1">... and {n - 6} more.</p>}
    </div>
  );
}

// One line; the details live in the info bubble.
function OrchardNote({ o, cp, asof, start }: { o: OrchardInfo; cp: number; asof: string; start: string }) {
  const st = o.station_estimate_cp;
  const vs = st ? Math.round(((cp - st) / st) * 100) : null;
  return (
    <p className="mt-2 flex items-center gap-1.5 text-[12px] text-muted">
      <Thermometer size={14} aria-hidden className="shrink-0 text-chill" />
      Temperature data from your orchard readings
      <InfoTip label="your readings">
        {o.kind === "daily" ? `${o.days} days of lows and highs` : "Logger readings"}, {longDate(o.first)} to {longDate(o.last)}; as of {longDate(asof)}, counting
        from {start === "sep1" ? "Sep 1" : "Nov 1"}.
        {st !== null && vs !== null ? ` Station-only estimate: ${st.toFixed(0)} chill portions; your readings ${vs === 0 ? "match it" : `are ${vs > 0 ? "+" : ""}${vs}% from it`}.` : ""}
        {o.gap_filled + o.gap_estimated > 0 ? ` ${o.gap_filled + o.gap_estimated} missing ${o.gap_unit} filled.` : ""}
        {o.error_source !== "not validated" ? ` Give-or-take from the ${o.error_source}.` : ""}
      </InfoTip>
    </p>
  );
}

function needText(low: number, high: number) {
  return low === high ? `${low}` : `${low} to ${high}`;
}

// Chill as a share of the minimum need: higher is better, 100% means the need is met.
const ofNeed = (cp: number, low: number) => Math.round((cp / low) * 100);

export default function Summary({ p }: { p: PointResponse }) {
  const { s } = useStore();
  const { crops, point } = useData();
  const r = s.run!;
  const crop = crops.data?.crops.find((c) => c.id === r.crop);
  const variety = crop?.varieties.find((v) => v.id === r.variety);
  const name = variety ? `${variety.name} ${crop!.name.toLowerCase()}` : "your trees";
  const { low, high } = p.need;
  const by = shortDate(p.need.by);
  const pct = Math.min(100, (p.chill.to_date / (high * 1.15)) * 100);
  const L = LEVEL[p.verdict.level];
  const orchard = (p as OrchardResponse).orchard;
  // A winter already past its need date: the count is final, so there are no odds to show.
  const finished = p.asof >= p.need.by;
  const station = orchard ? "your orchard's readings" : p.method.replace(/^E4 from /, "").replace(/ \(.*\)$/, "");

  return (
    <div className="rounded-[12px] border border-line bg-surface p-4" data-coach="verdict">
      {point.origin === "demo" && (
        <p className="mb-2 rounded-full bg-bg px-2.5 py-1 text-[11px] text-muted" role="status">
          Offline: showing saved results
        </p>
      )}
      <StatusPill level={p.verdict.level} size="lg" />
      <p className="mt-2 text-[18px] font-semibold leading-snug">{plainVerdict(p.verdict.level, p.outlook.chance_low, low, high)}</p>
      <p className="mt-1 text-[13px] text-muted">
        {name} needs {needText(low, high)} chill portions by {by}.
      </p>

      <div className="mt-3">
        <Row icon={<Snowflake size={18} />} label="Chill collected so far" info={`${EXPLAIN.chillPortion} ${p.chill.error_cp !== null ? EXPLAIN.errorBar : ""}`}>
          <span className="num font-semibold">{ofNeed(p.chill.to_date, low)}%</span> of the minimum need{" "}
          <span className="text-muted">
            ({p.chill.to_date.toFixed(0)} of {low} chill portions{p.chill.error_cp !== null ? `, give or take ${ofNeed(p.chill.error_cp, low)}%` : ""}; higher is
            better)
          </span>
          <div className="relative mt-2 h-2.5 rounded-full bg-bg" aria-hidden>
            <div className="absolute inset-y-0 rounded-full" style={{ left: `${(low / (high * 1.15)) * 100}%`, width: `${Math.max(1.5, ((high - low) / (high * 1.15)) * 100)}%`, background: "#3b7ea122" }} />
            <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${pct}%`, background: L.color }} />
          </div>
        </Row>
        {finished ? (
          <Row icon={<CalendarClock size={18} />} label={`By ${by}`} info={EXPLAIN.odds}>
            Reached <span className="num font-semibold">{ofNeed(p.outlook.p50, low)}%</span> of the minimum need by {by}
            {p.outlook.p50 >= high ? ", the full need." : p.outlook.p50 >= low ? ", inside the need range." : ", short of the need."}
          </Row>
        ) : (
          <Row icon={<CalendarClock size={18} />} label={`Expected by ${by}`} info={EXPLAIN.odds}>
            Most likely <span className="num font-semibold">{ofNeed(p.outlook.p50, low)}%</span> of the minimum need, probably between{" "}
            <span className="num">{ofNeed(p.outlook.p10, low)}%</span> and <span className="num">{ofNeed(p.outlook.p90, low)}%</span> (100% = need met).
          </Row>
        )}
        {!finished && <Row icon={<Percent size={18} />} label="Chance of enough chill" info={EXPLAIN.odds}>
          In <span className="num font-semibold">{inTen(p.outlook.chance_low)}</span> past winters your trees would reach {low} by {by}
          {high > low && (
            <>
              , and in <span className="num font-semibold">{inTen(p.outlook.chance_high)}</span> they would reach the full {high}
            </>
          )}
          .
        </Row>}
      </div>

      {orchard && <OrchardNote o={orchard} cp={p.chill.to_date} asof={p.asof} start={p.start} />}
      {orchard && <FlagNote o={orchard} unit={r.readings?.unit ?? "F"} />}

      {p.verdict.early && <p className="mt-1 rounded-[8px] bg-bg p-2.5 text-[12px] leading-relaxed">{EXPLAIN.early}</p>}

      {!orchard && (
        <p className="mt-3 flex flex-wrap items-center gap-1 text-[11px] text-muted">
          As of {longDate(p.asof)} · weather from {station}
          <InfoTip label="how we estimate">{EXPLAIN.method}</InfoTip>
        </p>
      )}
    </div>
  );
}

export function BlockCard() {
  const { s } = useStore();
  const { area } = useData();
  const r = s.run;
  if (!r?.samplePts) return null;
  const n = r.samplePts.length;
  return (
    <div className="rounded-[12px] border border-line bg-surface p-4">
      <div className="mb-1 flex items-center gap-1 text-[12px] font-semibold text-muted">
        Across {r.areaLabel}
        <InfoTip label="the block check">{EXPLAIN.block}</InfoTip>
      </div>
      {area.loading && (
        <div className="space-y-2" aria-busy="true">
          <p className="text-[13px]">Checking {n} spots across your block...</p>
          <Skeleton className="h-4 w-3/4" />
        </div>
      )}
      {area.error && <p className="text-[13px]">Couldn&apos;t check the whole block (this needs the live server). The results below are for the center.</p>}
      {area.data && (
        <p className="text-[14px] leading-snug">
          Checked {area.data.points.length} spots ({area.data.n_distinct_cells} different 1 km climate cells). Most likely chill by the need date ranges from{" "}
          <span className="num font-semibold">{area.data.p50_range[0].toFixed(0)}</span> to{" "}
          <span className="num font-semibold">{area.data.p50_range[1].toFixed(0)}</span> chill portions.{" "}
          {area.data.same_verdict ? "The verdict is the same across the whole block." : `The verdict differs across the block (${area.data.levels.map((l) => LEVEL[l].word).join(", ")}).`}
        </p>
      )}
    </div>
  );
}
