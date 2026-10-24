"use client";

import { ChevronDown, History, LineChart, Play, ShieldCheck, Sun } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { useData } from "@/lib/data";
import { EXPLAIN } from "@/lib/explain";
import { seasonShort, shortDate } from "@/lib/format";
import { useStore, type Tab } from "@/lib/store";
import type { PointResponse } from "@/lib/types";
import SeasonChart from "../charts/SeasonChart";
import ErrorBoundary from "../ErrorBoundary";
import AccuracyTab from "../tabs/AccuracyTab";
import HeatTab from "../tabs/HeatTab";
import HistoryTab from "../tabs/HistoryTab";
import { ReplayView, Sources } from "../tabs/WinterTab";
import { Button } from "../ui";

function Block({ id, icon, title, why, open = false, children }: { id: Tab; icon: ReactNode; title: string; why: string; open?: boolean; children: ReactNode }) {
  const { s, d } = useStore();
  const startOpen = open || (s.tab === id && id !== "winter");
  const [isOpen, setOpen] = useState(startOpen);
  return (
    <details
      open={startOpen}
      onToggle={(e) => {
        const o = (e.currentTarget as HTMLDetailsElement).open;
        setOpen(o);
        if (o) d({ type: "tab", tab: id });
      }}
      className="group rounded-[12px] border border-line bg-surface"
    >
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3">
        <span aria-hidden className="text-chill">
          {icon}
        </span>
        <span className="flex-1 text-[15px] font-semibold">{title}</span>
        <ChevronDown size={16} aria-hidden className="text-muted transition-transform group-open:rotate-180" />
      </summary>
      <div className="border-t border-line px-4 pb-4 pt-3">
        <p className="mb-3 text-[12px] leading-relaxed text-muted">{why}</p>
        {isOpen && <ErrorBoundary label="This section could not be shown.">{children}</ErrorBoundary>}
      </div>
    </details>
  );
}

function KeyItem({ swatch, children }: { swatch: ReactNode; children: ReactNode }) {
  return (
    <li className="flex items-start gap-2.5">
      <span aria-hidden className="mt-1 flex h-3 w-7 shrink-0 items-center justify-center">
        {swatch}
      </span>
      <span>{children}</span>
    </li>
  );
}

// Plain-language key for the season chart: what each line and band means, then the takeaway.
function ChartKey({ p }: { p: PointResponse }) {
  const { low, high } = p.need;
  const by = shortDate(p.need.by);
  const need = low === high ? `${low}` : `${low} to ${high}`;
  const finished = p.asof >= p.need.by;
  const where = p.outlook.p50 >= high ? "above" : p.outlook.p50 >= low ? "inside" : "below";
  return (
    <div className="mt-3 rounded-[10px] bg-bg p-3 text-[13px] leading-relaxed">
      <p className="font-semibold">How to read this chart</p>
      <p className="mt-1 text-muted">
        Chill only adds up through the winter, so every line climbs from left (September) to right (March). Higher means more chill.
      </p>
      <ul className="mt-2 space-y-1.5">
        <KeyItem swatch={<span className="h-[3px] w-full rounded bg-[#3b7ea1]" />}>
          <strong>Blue line:</strong> this winter&apos;s chill so far ({p.chill.to_date.toFixed(0)} chill portions as of {shortDate(p.asof)}).
        </KeyItem>
        {!finished && (
          <KeyItem swatch={<span className="h-3 w-full rounded-sm bg-[#3b7ea1]/20" />}>
            <strong>Shaded area and dashed line:</strong> where this winter is heading. The dashed line is the most likely path; 8 in 10 times it ends inside the
            shading.
          </KeyItem>
        )}
        <KeyItem swatch={<span className="h-[2px] w-full rounded bg-[#c4c9c3]" />}>
          <strong>Grey lines:</strong> past winters at this same spot, one line per winter, for comparison.
        </KeyItem>
        <KeyItem swatch={<span className="h-3 w-full rounded-sm bg-[#3b7ea1]/10 ring-1 ring-[#3b7ea1]/30" />}>
          <strong>Light band across the chart:</strong> what your trees need, {need} chill portions by {by}.
        </KeyItem>
      </ul>
      <p className="mt-2">
        <strong>The takeaway:</strong>{" "}
        {finished
          ? `this winter reached ${p.outlook.p50.toFixed(0)} chill portions by ${by}, ${where} the need.`
          : `if the blue line ends inside or above the band by ${by}, the trees get enough chill. Right now the most likely finish is about ${p.outlook.p50.toFixed(0)}, ${where} the band.`}
      </p>
    </div>
  );
}

function ThisWinter({ p }: { p: PointResponse }) {
  const { s, d } = useStore();
  const seasons = useMemo(() => p.past_seasons.map((x) => x.season).sort().reverse(), [p.past_seasons]);
  return (
    <div>
      <SeasonChart
        season={p.season}
        current={p.chill.series}
        fan={p.outlook.fan}
        past={p.past_seasons}
        need={p.need}
        marker={p.asof}
        highlight={s.highlight}
        startDos={p.start === "nov1" ? 61 : 0}
      />
      <ChartKey p={p} />
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <label htmlFor="year-pick" className="text-[12px] text-muted">
          Highlight a winter you remember
        </label>
        <select
          id="year-pick"
          value={s.highlight ?? ""}
          onChange={(e) => d({ type: "highlight", season: e.target.value || null })}
          className="h-8 rounded-[8px] border border-line bg-surface px-2 text-[12px]"
        >
          <option value="">None</option>
          {seasons.map((x) => (
            <option key={x} value={x}>
              {seasonShort(x)}
            </option>
          ))}
        </select>
      </div>
      {p.closest.season && (
        <p className="mt-2 text-[12px]">
          This winter so far looks most like <strong>{seasonShort(p.closest.season)}</strong>
          {p.chill.to_date < 1 ? " (no chill yet, so matched on temperatures)." : "."}
        </p>
      )}
    </div>
  );
}

function Replay({ p }: { p: PointResponse }) {
  const { s, d } = useStore();
  const seasons = useMemo(() => p.past_seasons.map((x) => x.season).sort().reverse(), [p.past_seasons]);
  const [pick, setPick] = useState("2014-2015");
  if (s.replaySeason) return <ReplayView p={p} />;
  return (
    <div className="flex items-center gap-2">
      <label htmlFor="replay-pick" className="sr-only">
        Winter to replay
      </label>
      <select id="replay-pick" value={pick} onChange={(e) => setPick(e.target.value)} className="h-9 flex-1 rounded-[8px] border border-line bg-surface px-2 text-[14px]">
        {seasons.map((x) => (
          <option key={x} value={x}>
            Winter {seasonShort(x)}
          </option>
        ))}
      </select>
      <Button variant="primary" onClick={() => d({ type: "replay", season: pick })}>
        <Play size={14} aria-hidden /> Play
      </Button>
    </div>
  );
}

export default function Sections({ p }: { p: PointResponse }) {
  const { point } = useData();
  return (
    <div className="space-y-2">
      <Block id="winter" icon={<LineChart size={18} />} title="How this winter's chill is building up" why="This winter's chill so far, where it is heading, and every past winter at your spot for comparison." open>
        <ThisWinter p={p} />
      </Block>
      <Block id="history" icon={<History size={18} />} title="Every winter here since 1980" why={EXPLAIN.history}>
        <HistoryTab />
      </Block>
      <Block id="winter" icon={<Play size={18} />} title="Replay a past winter" why={EXPLAIN.replay}>
        <Replay p={p} />
      </Block>
      <Block id="heat" icon={<Sun size={18} />} title="Heat after bloom" why={EXPLAIN.heat}>
        <HeatTab />
      </Block>
      <Block id="accuracy" icon={<ShieldCheck size={18} />} title="How accurate is this?" why={EXPLAIN.accuracy}>
        <AccuracyTab />
      </Block>
      {point.data && <Sources list={point.data.sources} method={point.data.method} />}
    </div>
  );
}
