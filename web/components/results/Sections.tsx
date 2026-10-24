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

function Swatch({ className }: { className: string }) {
  return <span aria-hidden className={`inline-block align-middle ${className}`} />;
}

// A compact key, then the takeaway.
function ChartKey({ p }: { p: PointResponse }) {
  const { low } = p.need;
  const by = shortDate(p.need.by);
  const finished = p.asof >= p.need.by;
  const pct = Math.round((p.outlook.p50 / low) * 100);
  const where = p.outlook.p50 >= p.need.high ? "above" : p.outlook.p50 >= low ? "inside" : "below";
  return (
    <div className="mt-3 space-y-1.5 text-[12px] leading-relaxed">
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-muted">
        <span className="font-semibold text-ink">Key:</span>
        <span>
          <Swatch className="mr-1 h-[3px] w-5 rounded bg-[#3b7ea1]" /> this winter
        </span>
        {!finished && (
          <span>
            <Swatch className="mr-1 h-2.5 w-5 rounded-sm bg-[#3b7ea1]/20" /> likely path
          </span>
        )}
        <span>
          <Swatch className="mr-1 h-[2px] w-5 rounded bg-[#c4c9c3]" /> past winters
        </span>
        <span>
          <Swatch className="mr-1 h-2.5 w-5 rounded-sm bg-[#3b7ea1]/10 ring-1 ring-[#3b7ea1]/30" /> need by {by}
        </span>
      </p>
      <p>
        <strong>The takeaway:</strong>{" "}
        {finished
          ? `this winter reached ${pct}% of the minimum need by ${by}, ${where} the need.`
          : `if the blue line ends inside or above the band by ${by}, the trees get enough chill. Most likely finish: ${pct}% of the minimum need, ${where} the band.`}
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
