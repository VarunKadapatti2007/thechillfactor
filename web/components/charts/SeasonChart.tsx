"use client";

import { useReducedMotion } from "framer-motion";
import { useMemo } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { addDays, seasonShort, shortDate } from "@/lib/format";
import { dayOfSeason } from "@/lib/season";
import type { CpPoint, FanPoint } from "@/lib/types";

export const SERIES = {
  current: "#3b7ea1",
  past: "#c4c9c3",
  highlight: "#eb6834",
  fan: "#3b7ea1",
  need: "#3b7ea1",
};

interface Props {
  season: string; // x axis is this season's dates
  current: CpPoint[];
  fan?: FanPoint[];
  past: { season: string; series: CpPoint[] }[];
  need: { low: number; high: number; by: string };
  marker?: string | null; // "today" or replay frame date
  markerLabel?: string;
  highlight?: string | null;
  rangeBar?: { p10: number; p50: number; p90: number } | null;
  startDos?: number;
  height?: number;
  animate?: boolean;
}

type Row = Record<string, number | [number, number] | null>;

export default function SeasonChart({
  season, current, fan, past, need, marker, markerLabel = "Today", highlight, rangeBar, startDos = 0, height = 240, animate = true,
}: Props) {
  const reduce = useReducedMotion() || !animate;
  const base = `${season.split("-")[0]}-09-01`;
  const byDos = dayOfSeason(season, need.by);
  const endDos = Math.max(byDos + 14, 181);

  const { rows, pastKeys } = useMemo(() => {
    const m = new Map<number, Row>();
    const row = (dos: number) => {
      let r = m.get(dos);
      if (!r) {
        r = { dos };
        m.set(dos, r);
      }
      return r;
    };
    const keys: string[] = [];
    for (const p of past) {
      const k = `s_${p.season}`;
      keys.push(k);
      for (const pt of p.series) {
        const dos = dayOfSeason(p.season, pt.date);
        if (dos >= startDos && dos <= endDos) row(dos)[k] = pt.cp;
      }
    }
    for (const pt of current) {
      const dos = dayOfSeason(season, pt.date);
      if (dos >= startDos && dos <= endDos) row(dos).cur = pt.cp;
    }
    for (const f of fan ?? []) {
      const dos = dayOfSeason(season, f.date);
      if (dos <= endDos) {
        row(dos).fan = [f.p10, f.p90];
        row(dos).p50 = f.p50;
      }
    }
    if (rangeBar) {
      row(byDos).rb = [rangeBar.p10, rangeBar.p90];
      row(byDos).rb50 = rangeBar.p50;
    }
    return { rows: [...m.values()].sort((a, b) => (a.dos as number) - (b.dos as number)), pastKeys: keys };
  }, [past, current, fan, season, startDos, endDos, rangeBar, byDos]);

  const yMax = Math.max(
    need.high * 1.2,
    ...rows.map((r) => Math.max((r.cur as number) ?? 0, Array.isArray(r.fan) ? r.fan[1] : 0, Array.isArray(r.rb) ? r.rb[1] : 0)),
  );
  const monthTicks = [0, 30, 61, 91, 122, 153, 181].filter((t) => t >= startDos && t <= endDos);
  const markerDos = marker ? dayOfSeason(season, marker) : null;
  const label = (dos: number) => shortDate(addDays(base, dos));

  return (
    <div role="img" aria-label={`Season chart: chill portions since ${shortDate(addDays(base, startDos))}, with past winters and the need band`}>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
          <CartesianGrid stroke="#ecebe5" vertical={false} />
          <XAxis
            dataKey="dos"
            type="number"
            domain={[startDos, endDos]}
            ticks={monthTicks}
            tickFormatter={(v) => label(v).split(" ")[0]}
            tick={{ fontSize: 11, fill: "#5b6660" }}
            axisLine={{ stroke: "#e3e1da" }}
            tickLine={false}
          />
          <YAxis
            domain={[0, Math.ceil(yMax / 10) * 10]}
            tick={{ fontSize: 11, fill: "#5b6660" }}
            axisLine={false}
            tickLine={false}
            width={44}
          />
          <ReferenceArea y1={need.low} y2={need.high === need.low ? need.low + 0.6 : need.high} fill={SERIES.need} fillOpacity={0.12} stroke="none" ifOverflow="extendDomain" />
          <ReferenceLine
            x={byDos}
            stroke="#5b6660"
            strokeDasharray="3 3"
            label={{ value: `by ${shortDate(need.by)}`, position: "insideTopRight", fontSize: 11, fill: "#5b6660" }}
          />
          {pastKeys.map((k) => (
            <Line
              key={k}
              dataKey={k}
              stroke={highlight && k === `s_${highlight}` ? SERIES.highlight : SERIES.past}
              strokeWidth={highlight && k === `s_${highlight}` ? 2.5 : 1}
              strokeOpacity={highlight && k === `s_${highlight}` ? 1 : 0.7}
              dot={false}
              connectNulls
              isAnimationActive={false}
              activeDot={false}
            />
          ))}
          {fan && fan.length > 0 && (
            <>
              <Area dataKey="fan" stroke="none" fill={SERIES.fan} fillOpacity={0.18} connectNulls isAnimationActive={!reduce} animationDuration={800} />
              <Line dataKey="p50" stroke={SERIES.current} strokeDasharray="4 3" strokeWidth={2} dot={false} connectNulls isAnimationActive={!reduce} animationDuration={800} />
            </>
          )}
          <Line
            dataKey="cur"
            stroke={SERIES.current}
            strokeWidth={3}
            dot={false}
            connectNulls
            isAnimationActive={!reduce}
            animationDuration={800}
          />
          {rangeBar && (
            <>
              <ReferenceLine
                segment={[{ x: byDos, y: rangeBar.p10 }, { x: byDos, y: rangeBar.p90 }]}
                stroke={SERIES.current}
                strokeOpacity={0.45}
                strokeWidth={10}
                strokeLinecap="round"
                ifOverflow="extendDomain"
              />
              <ReferenceDot x={byDos} y={rangeBar.p50} r={5} fill={SERIES.current} stroke="#fff" strokeWidth={2} ifOverflow="extendDomain" />
            </>
          )}
          {markerDos !== null && (
            <ReferenceLine x={markerDos} stroke="#1f2a24" strokeWidth={1} label={{ value: markerLabel, position: "insideTopLeft", fontSize: 11, fill: "#1f2a24" }} />
          )}
          <Tooltip
            cursor={{ stroke: "#5b6660", strokeWidth: 1 }}
            content={({ active, label: l, payload }) => {
              if (!active || l === undefined) return null;
              const r = rows.find((x) => x.dos === l) ?? (payload?.[0]?.payload as Row | undefined);
              if (!r) return null;
              const hl = highlight ? (r[`s_${highlight}`] as number | undefined) : undefined;
              return (
                <div className="rounded-[8px] border border-line bg-surface px-2.5 py-1.5 text-[12px] shadow-md">
                  <div className="font-semibold">{label(l as number)}</div>
                  {typeof r.cur === "number" && <div className="num">This winter: {r.cur.toFixed(1)} CP</div>}
                  {Array.isArray(r.fan) && (
                    <div className="num">
                      Outlook: {r.fan[0].toFixed(0)} to {r.fan[1].toFixed(0)} CP
                    </div>
                  )}
                  {Array.isArray(r.rb) && (
                    <div className="num">
                      Likely by {shortDate(need.by)}: {r.rb[0].toFixed(0)} to {r.rb[1].toFixed(0)} CP
                    </div>
                  )}
                  {highlight && typeof hl === "number" && (
                    <div className="num">
                      {seasonShort(highlight)}: {hl.toFixed(1)} CP
                    </div>
                  )}
                </div>
              );
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
      <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted">
        <li className="flex items-center gap-1">
          <span className="inline-block h-[3px] w-4 rounded" style={{ background: SERIES.current }} /> This winter
        </li>
        <li className="flex items-center gap-1">
          <span className="inline-block h-[2px] w-4 rounded" style={{ background: SERIES.past }} /> Past winters
        </li>
        {highlight && (
          <li className="flex items-center gap-1">
            <span className="inline-block h-[3px] w-4 rounded" style={{ background: SERIES.highlight }} /> {seasonShort(highlight)}
          </li>
        )}
        {fan && fan.length > 0 && (
          <li className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-4 rounded-sm" style={{ background: SERIES.fan, opacity: 0.25 }} /> Outlook, 8 in 10 range
          </li>
        )}
        <li className="flex items-center gap-1">
          <span className="inline-block h-2.5 w-4 rounded-sm" style={{ background: SERIES.need, opacity: 0.15 }} /> Need
        </li>
      </ul>
    </div>
  );
}
