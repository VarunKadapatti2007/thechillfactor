"use client";

import { ExternalLink } from "lucide-react";
import { useMemo } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useData } from "@/lib/data";
import { degDayLabel, gddUnits, mmddLabel, seasonShort } from "@/lib/format";
import { useStore } from "@/lib/store";
import { Sources } from "./WinterTab";
import { ErrorLine, Section, Skeleton } from "../ui";

const HEAT = "#c8742b";
const PAST = "#d9d3c8";

export default function HeatTab() {
  const { s } = useStore();
  const { heat, bloom, setBloom } = useData();
  const [bm, bd] = bloom.split("-");

  const { rows, keys, latest, med90 } = useMemo(() => {
    const h = heat.data;
    if (!h) return { rows: [], keys: [] as string[], latest: null as string | null, med90: null as number | null };
    const n = Math.max(...h.seasons.map((x) => x.series.length));
    const rs: Record<string, number>[] = Array.from({ length: n }, (_, i) => ({ day: i }));
    for (const ss of h.seasons) ss.series.forEach((p, i) => (rs[i][ss.season] = gddUnits(p.gdd, s.units)));
    const finals = h.seasons.map((x) => x.series[x.series.length - 1]?.gdd).filter((v): v is number => v !== undefined).sort((a, b) => a - b);
    const m = finals.length ? finals[Math.floor(finals.length / 2)] : null;
    return { rows: rs, keys: h.seasons.map((x) => x.season), latest: h.latest, med90: m === null ? null : gddUnits(m, s.units) };
  }, [heat.data, s.units]);

  return (
    <div>
      <Section title="Heat since bloom" sentence="Growing degree days from your bloom date, against past seasons at this pin." info="FNRIC's single-sine method, lower 5 °C (41 °F), upper 35 °C (95 °F). Summed from bloom, GDD predicts events like almond hull split.">
        <div className="mb-3 flex items-center gap-2">
          <span className="text-[12px] text-muted">Bloom date</span>
          <select aria-label="Bloom month" value={bm} onChange={(e) => setBloom(`${e.target.value}-${bd}`)} className="h-8 rounded-[8px] border border-line px-2 text-[12px]">
            {[["02", "Feb"], ["03", "Mar"], ["04", "Apr"]].map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
          <select aria-label="Bloom day" value={bd} onChange={(e) => setBloom(`${bm}-${e.target.value}`)} className="num h-8 rounded-[8px] border border-line px-2 text-[12px]">
            {["01", "05", "10", "15", "20", "25"].map((v) => (
              <option key={v} value={v}>
                {Number(v)}
              </option>
            ))}
          </select>
        </div>
        {heat.error && !heat.data && <ErrorLine message="Could not load heat for this pin." onRetry={heat.retry} />}
        {!heat.data && !heat.error && <Skeleton className="h-[220px]" />}
        {heat.data && (
          <>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
                <CartesianGrid stroke="#ecebe5" vertical={false} />
                <XAxis dataKey="day" type="number" domain={[0, rows.length - 1]} ticks={[0, 30, 60, 90]} tickFormatter={(v) => `day ${v}`} tick={{ fontSize: 11, fill: "#5b6660" }} tickLine={false} axisLine={{ stroke: "#e3e1da" }} />
                <YAxis tick={{ fontSize: 11, fill: "#5b6660" }} axisLine={false} tickLine={false} width={50} />
                {keys.map((k) => (
                  <Line key={k} dataKey={k} stroke={k === latest ? HEAT : PAST} strokeWidth={k === latest ? 2.5 : 1} dot={false} isAnimationActive={false} activeDot={false} />
                ))}
                <Tooltip
                  content={({ active, label, payload }) => {
                    if (!active || label === undefined) return null;
                    const r = payload?.[0]?.payload as Record<string, number> | undefined;
                    const v = latest && r ? r[latest] : undefined;
                    return (
                      <div className="rounded-[8px] border border-line bg-surface px-2.5 py-1.5 text-[12px] shadow-md">
                        <div className="font-semibold">Day {label} after bloom</div>
                        {v !== undefined && latest && (
                          <div className="num">
                            {seasonShort(latest)}: {v.toFixed(0)} {degDayLabel(s.units)}
                          </div>
                        )}
                      </div>
                    );
                  }}
                />
              </LineChart>
            </ResponsiveContainer>
            <ul className="mt-1 flex flex-wrap gap-x-3 text-[11px] text-muted">
              {latest && (
                <li className="flex items-center gap-1">
                  <span className="inline-block h-[3px] w-4 rounded" style={{ background: HEAT }} /> {seasonShort(latest)}
                </li>
              )}
              <li className="flex items-center gap-1">
                <span className="inline-block h-[2px] w-4 rounded" style={{ background: PAST }} /> Past seasons
              </li>
            </ul>
            {med90 !== null && (
              <p className="num mt-3 text-[14px]">
                Typical heat 90 days after a {mmddLabel(bloom)} bloom: <strong>{med90.toFixed(0)} {degDayLabel(s.units)}</strong>
              </p>
            )}
          </>
        )}
        <a href="https://fruitsandnuts.ucdavis.edu/almond-hull-split-prediction-model" target="_blank" rel="noreferrer" className="mt-3 flex items-center justify-between rounded-[12px] border border-line px-3 py-2 text-[14px] hover:bg-bg">
          FNRIC almond hull split model
          <ExternalLink size={14} aria-hidden className="text-muted" />
        </a>
      </Section>
      {heat.data && <Sources list={heat.data.sources} method={heat.data.method} />}
    </div>
  );
}
