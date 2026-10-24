"use client";

import { CircleCheck, ExternalLink, OctagonAlert, TrendingDown, TrendingUp, Minus } from "lucide-react";
import { useMemo, useState } from "react";
import { Bar, CartesianGrid, Cell, Line, ComposedChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useData } from "@/lib/data";
import { mmddLabel, seasonShort } from "@/lib/format";
import { useStore } from "@/lib/store";
import { Sources } from "./WinterTab";
import { ErrorLine, InfoTip, Section, Skeleton } from "../ui";

const MET = "#2f855a";
const MISS = "#c53030";

function median(a: number[]): number {
  const s = [...a].sort((x, y) => x - y);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

export default function HistoryTab() {
  const { s } = useStore();
  const { history, crops } = useData();
  const [table, setTable] = useState(false);
  const v = crops.data?.crops.find((c) => c.id === s.crop)?.varieties.find((x) => x.id === s.variety);

  const rows = useMemo(() => {
    const h = history.data;
    if (!h) return [];
    const xs = h.winters.map((w) => Number(w.season.slice(0, 4)));
    const slope = h.trend.cp_per_decade / 10;
    const icept = median(h.winters.flatMap((w, i) => (w.filled ? [] : [w.cp_by - slope * xs[i]])));
    return h.winters.map((w, i) => ({ ...w, x: xs[i], label: seasonShort(w.season), trend: icept + slope * xs[i] }));
  }, [history.data]);

  if (history.error && !history.data) return <ErrorLine message="Could not load land history." onRetry={history.retry} />;
  if (!history.data || !v) {
    return (
      <div className="space-y-3 py-2" aria-busy="true">
        <Skeleton className="h-6 w-3/4" />
        <Skeleton className="h-[220px]" />
        <div className="grid grid-cols-2 gap-2">
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
        </div>
      </div>
    );
  }
  const h = history.data;
  const complete = h.winters.filter((w) => !w.filled);
  const nMet = complete.filter((w) => w.met_low).length;
  const filled = h.winters.find((w) => w.filled);
  const TrendIcon = h.trend.label === "likely decline" ? TrendingDown : h.trend.label === "likely increase" ? TrendingUp : Minus;

  return (
    <div>
      <Section
        title={`Met ${v.name}'s need in ${nMet} of ${complete.length} winters`}
        sentence={`Chill portions by ${mmddLabel(s.byOverride ?? v.by_date_default)} at this pin, every winter since ${seasonShort(h.winters[0].season)}.`}
        info="Each winter uses the nearest station with a complete record, shifted to this pin by the Daymet 1 km monthly difference (the best method in our hidden-station test). Faded winters had no station record and are estimated from Daymet with a machine-learned daily curve (validated, 3.5 CP typical miss)."
      >
        <ResponsiveContainer width="100%" height={220}>
          <ComposedChart data={rows} margin={{ top: 8, right: 4, bottom: 0, left: -18 }} barCategoryGap={1}>
            <CartesianGrid stroke="#ecebe5" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 10, fill: "#5b6660" }} interval={9} tickLine={false} axisLine={{ stroke: "#e3e1da" }} />
            <YAxis tick={{ fontSize: 11, fill: "#5b6660" }} axisLine={false} tickLine={false} width={44} />
            <ReferenceLine y={v.need_low} stroke="#1f2a24" strokeDasharray="4 3" label={{ value: `need ${v.need_low}`, position: "insideTopLeft", fontSize: 10, fill: "#1f2a24" }} />
            <Bar dataKey="cp_by" radius={[3, 3, 0, 0]} isAnimationActive={false}>
              {rows.map((r) => (
                <Cell key={r.season} fill={r.met_low ? MET : MISS} fillOpacity={r.filled ? 0.45 : 0.9} />
              ))}
            </Bar>
            <Line dataKey="trend" stroke="#1f2a24" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Tooltip
              cursor={{ fill: "#00000008" }}
              content={({ active, payload }) => {
                const r = payload?.[0]?.payload as (typeof rows)[number] | undefined;
                if (!active || !r) return null;
                return (
                  <div className="rounded-[8px] border border-line bg-surface px-2.5 py-1.5 text-[12px] shadow-md">
                    <div className="font-semibold">Winter {r.label}</div>
                    <div className="num">{r.cp_by.toFixed(1)} CP</div>
                    <div>{r.met_low ? "Met need" : "Missed need"}</div>
                    {r.filled && <div className="text-muted">No station record that winter: estimated from Daymet</div>}
                  </div>
                );
              }}
            />
          </ComposedChart>
        </ResponsiveContainer>
        <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted">
          <li className="flex items-center gap-1">
            <CircleCheck size={12} aria-hidden style={{ color: MET }} /> Met need
          </li>
          <li className="flex items-center gap-1">
            <OctagonAlert size={12} aria-hidden style={{ color: MISS }} /> Missed need
          </li>
          <li className="flex items-center gap-1">
            <span className="inline-block h-[2px] w-4 bg-ink" /> Trend
          </li>
          {filled && <li>Faded: no station record that winter (estimated, not in the trend)</li>}
        </ul>
        <button className="mt-2 text-[12px] text-chill underline" onClick={() => setTable(!table)}>
          {table ? "Hide table" : "Show table"}
        </button>
        {table && (
          <div className="mt-2 max-h-48 overflow-auto rounded-[8px] border border-line">
            <table className="num w-full text-[12px]">
              <thead className="sticky top-0 bg-bg text-left">
                <tr>
                  <th className="px-2 py-1">Winter</th>
                  <th className="px-2 py-1">CP</th>
                  <th className="px-2 py-1">Need met</th>
                </tr>
              </thead>
              <tbody>
                {h.winters.map((w) => (
                  <tr key={w.season} className="border-t border-line">
                    <td className="px-2 py-1">{seasonShort(w.season)}{w.filled ? " (est.)" : ""}</td>
                    <td className="px-2 py-1">{w.cp_by.toFixed(1)}</td>
                    <td className="px-2 py-1">{w.met_low ? "Yes" : "No"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section title="Is it changing?" sentence="Safe winter chill is the amount reached in 9 of 10 winters." info="Safe winter chill is the 10th percentile (Luedeling's standard). Ranges come from resampling the winters; 20 winters make a noisy estimate. 45-year trends are indicative only.">
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-[12px] border border-line p-3">
            <div className="text-[11px] text-muted">Safe chill, {h.safe_chill.early.years}</div>
            <div className="num text-[20px] font-semibold">{h.safe_chill.early.p10.toFixed(0)} CP</div>
            <div className="num text-[11px] text-muted">
              {h.safe_chill.early.ci[0].toFixed(0)} to {h.safe_chill.early.ci[1].toFixed(0)}
            </div>
          </div>
          <div className="rounded-[12px] border border-line p-3">
            <div className="text-[11px] text-muted">Safe chill, {h.safe_chill.recent.years}</div>
            <div className="num text-[20px] font-semibold">{h.safe_chill.recent.p10.toFixed(0)} CP</div>
            <div className="num text-[11px] text-muted">
              {h.safe_chill.recent.ci[0].toFixed(0)} to {h.safe_chill.recent.ci[1].toFixed(0)}
            </div>
          </div>
          <div className="rounded-[12px] border border-line p-3">
            <div className="flex items-center gap-1 text-[11px] text-muted">
              Trend per decade
              <InfoTip label="trend">Theil-Sen slope with a 90% range; Mann-Kendall test. Above p = 0.1 we call it no clear trend.</InfoTip>
            </div>
            <div className="num flex items-center gap-1 text-[20px] font-semibold">
              <TrendIcon size={18} aria-hidden />
              {h.trend.cp_per_decade > 0 ? "+" : ""}
              {h.trend.cp_per_decade.toFixed(1)} CP
            </div>
            <div className="text-[11px] text-muted">{h.trend.label === "no clear trend" ? "No clear trend" : h.trend.label === "likely decline" ? "Likely decline" : "Likely increase"}</div>
          </div>
          <div className="rounded-[12px] border border-line p-3">
            <div className="flex items-center gap-1 text-[11px] text-muted">
              Today&apos;s climate
              <InfoTip label="today's climate">All past winters shifted to today&apos;s warmth, then counted again.</InfoTip>
            </div>
            <div className="num text-[20px] font-semibold">{h.safe_chill.today_replay.p10.toFixed(0)} CP</div>
            <div className="num text-[11px] text-muted">safe chill; typical {h.safe_chill.today_replay.p50.toFixed(0)}</div>
          </div>
        </div>
        <p className="mt-2 text-[12px] text-muted">
          Shares (complete winters): need met in {Math.round(h.share_met_low * 10)} in 10 winters at the low end, {Math.round(h.share_met_high * 10)} in 10 at the high end.
        </p>
      </Section>

      <Section title="Next 20 years" sentence="Projections live with the climate teams; we link out rather than rebuild them.">
        <div className="grid gap-2">
          {h.links.map((l) => (
            <a key={l.url} href={l.url} target="_blank" rel="noreferrer" className="flex items-center justify-between rounded-[12px] border border-line px-3 py-2 text-[14px] hover:bg-bg">
              {l.title}
              <ExternalLink size={14} aria-hidden className="text-muted" />
            </a>
          ))}
        </div>
      </Section>
      <Sources list={h.sources} method={h.method} />
    </div>
  );
}

