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
  if (!(o.flagged_count ?? 0)) {
    return (
      <p className="mt-2 text-[12px] text-muted">
        Every reading was checked against the Central Valley&apos;s range and what nearby stations measured; none looked wrong.
      </p>
    );
  }
  return (
    <div className="mt-2 rounded-[8px] border border-amber-300 bg-amber-50 p-2.5 text-[12px] leading-relaxed text-amber-900" role="status">
      <p className="font-semibold">
        {(o.flagged_count ?? 0)} reading{(o.flagged_count ?? 0) > 1 ? "s were" : " was"} set aside because {(o.flagged_count ?? 0) > 1 ? "they don't" : "it doesn't"} look right. Those
        days were filled from the days around them. Check your thermometer or file:
      </p>
      <ul className="mt-1 list-disc pl-4">
        {(o.flagged ?? []).slice(0, 6).map((f) => (
          <li key={`${f.when}-${f.field}`}>
            <strong>
              {f.when}: {f.field} {f.value}°{unit}
            </strong>
            {f.expected !== null ? `, nearby stations suggest about ${Math.round(f.expected)}°` : ""}. {f.reason.charAt(0).toUpperCase() + f.reason.slice(1)}.
          </li>
        ))}
      </ul>
      {(o.flagged_count ?? 0) > 6 && <p className="mt-1">... and {(o.flagged_count ?? 0) - 6} more.</p>}
    </div>
  );
}

function OrchardNote({ o, cp, season }: { o: OrchardInfo; cp: number; season: string }) {
  const diff = o.difference_cp;
  return (
    <div className="mt-2 flex gap-2 rounded-[8px] bg-bg p-2.5 text-[12px] leading-relaxed">
      <Thermometer size={16} aria-hidden className="mt-0.5 shrink-0 text-chill" />
      <div>
        <span className="font-semibold">Counted from your orchard&apos;s readings</span> ({o.kind === "daily" ? `${o.days} days of lows and highs` : "logger readings"},{" "}
        {longDate(o.first)} to {longDate(o.last)}, the {season} winter).
        {o.station_estimate_cp !== null && diff !== null && (
          <>
            {" "}
            The station-only estimate for the same days was <span className="num">{o.station_estimate_cp.toFixed(0)}</span> chill portions; your readings give{" "}
            <span className="num">{cp.toFixed(0)}</span>
            {Math.abs(diff) >= 0.5 ? ` (${diff > 0 ? "+" : ""}${diff.toFixed(1)})` : " (about the same)"}.
          </>
        )}
        {o.before_start_from_station && " Days before your readings start use the station estimate."}
        {o.gap_filled > 0 && ` ${o.gap_filled} missing ${o.gap_unit} were filled in from the days around them.`}
        {o.gap_estimated > 0 && ` ${o.gap_estimated} ${o.gap_unit} in longer gaps use the station estimate.`}
        {o.error_source !== "not validated" && ` The give-or-take comes from the ${o.error_source}.`}
      </div>
    </div>
  );
}

function needText(low: number, high: number) {
  return low === high ? `${low}` : `${low} to ${high}`;
}

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
          <span className="num font-semibold">{p.chill.to_date.toFixed(0)}</span> of the {needText(low, high)} chill portions needed
          {p.chill.error_cp !== null && <span className="text-muted"> (give or take {p.chill.error_cp.toFixed(0)})</span>}
          <div className="relative mt-2 h-2.5 rounded-full bg-bg" aria-hidden>
            <div className="absolute inset-y-0 rounded-full" style={{ left: `${(low / (high * 1.15)) * 100}%`, width: `${Math.max(1.5, ((high - low) / (high * 1.15)) * 100)}%`, background: "#3b7ea122" }} />
            <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${pct}%`, background: L.color }} />
          </div>
        </Row>
        {finished ? (
          <Row icon={<CalendarClock size={18} />} label={`By ${by}`} info={EXPLAIN.odds}>
            This winter reached <span className="num font-semibold">{p.outlook.p50.toFixed(0)}</span> chill portions by {by}
            {p.outlook.p50 >= high ? ", the full need." : p.outlook.p50 >= low ? `, inside the ${needText(low, high)} range.` : `, short of the ${low} needed.`}
          </Row>
        ) : (
          <Row icon={<CalendarClock size={18} />} label={`Expected by ${by}`} info={EXPLAIN.odds}>
            Most likely about <span className="num font-semibold">{p.outlook.p50.toFixed(0)}</span> chill portions, probably between{" "}
            <span className="num">{p.outlook.p10.toFixed(0)}</span> and <span className="num">{p.outlook.p90.toFixed(0)}</span>.
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

      {orchard && <OrchardNote o={orchard} cp={p.chill.to_date} season={p.season} />}
      {orchard && <FlagNote o={orchard} unit={r.readings?.unit ?? "F"} />}

      {p.verdict.early && <p className="mt-1 rounded-[8px] bg-bg p-2.5 text-[12px] leading-relaxed">{EXPLAIN.early}</p>}

      <p className="mt-3 flex flex-wrap items-center gap-1 text-[11px] text-muted">
        As of {longDate(p.asof)} · counting from {p.start === "sep1" ? "Sep 1" : "Nov 1"} · weather from {station}
        <InfoTip label="how we estimate">{EXPLAIN.method}</InfoTip>
      </p>
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
