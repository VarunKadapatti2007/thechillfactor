"use client";

import * as Slider from "@radix-ui/react-slider";
import { motion } from "framer-motion";
import { ArrowLeft, History, Pause, Play, Snowflake, Sun } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useData } from "@/lib/data";
import { daysBetween, inTen, longDate, range, seasonShort, shortDate } from "@/lib/format";
import { plainVerdict } from "@/lib/explain";
import { seasonStartYear } from "@/lib/season";
import { useStore } from "@/lib/store";
import type { Frame, Level, PointResponse } from "@/lib/types";
import RingGauge from "../charts/RingGauge";
import SeasonChart from "../charts/SeasonChart";
import { Button, ErrorLine, InfoTip, Section, Skeleton, StatusPill } from "../ui";

const CP_INFO = "A chill unit that counts cool hours and discounts warm spells. UC recommends it for California.";

function useVarietyInfo() {
  const { s } = useStore();
  const { crops } = useData();
  const cropId = s.run?.crop ?? s.crop;
  const varId = s.run?.variety ?? s.variety;
  const crop = crops.data?.crops.find((c) => c.id === cropId);
  const v = crop?.varieties.find((x) => x.id === varId);
  return { crop, v };
}

function byForSeason(season: string, mmdd: string): string {
  const y = seasonStartYear(season);
  const m = Number(mmdd.split("-")[0]);
  return `${m >= 9 ? y : y + 1}-${mmdd}`;
}

export default function WinterTab() {
  const { s } = useStore();
  const { point } = useData();
  if (point.error && !point.data) return <ErrorLine message="Could not load this pin." onRetry={point.retry} />;
  if (!point.data) return <WinterSkeleton />;
  return s.replaySeason ? <ReplayView p={point.data} /> : <LiveView p={point.data} />;
}

function WinterSkeleton() {
  return (
    <div className="space-y-4 py-2" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-8 w-32" />
      <Skeleton className="h-4 w-full" />
      <div className="flex gap-3">
        <Skeleton className="h-[120px] w-[120px] rounded-full" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-11" />
          <Skeleton className="h-11" />
          <Skeleton className="h-11" />
        </div>
      </div>
      <Skeleton className="h-[240px]" />
    </div>
  );
}

function Hero({ level, sentence, early, sub }: { level: Level; sentence: string; early: boolean; sub: string }) {
  return (
    <motion.div key={level} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25, ease: "easeOut" }} className="space-y-2" data-coach="verdict">
      <StatusPill level={level} size="lg" />
      <p className="text-[16px] leading-snug text-ink">{sentence}</p>
      {early && <p className="text-[12px] font-medium text-watch-ink">Early in the winter: this leans mostly on past winters.</p>}
      <p className="text-[12px] text-muted">{sub}</p>
    </motion.div>
  );
}

function Tile({ label, value, sub, info }: { label: string; value: React.ReactNode; sub?: React.ReactNode; info?: React.ReactNode }) {
  return (
    <div className="rounded-[12px] border border-line bg-surface px-3 py-2">
      <div className="flex items-center gap-1 text-[11px] text-muted">
        {label}
        {info && <InfoTip label={label}>{info}</InfoTip>}
      </div>
      <div className="num text-[16px] font-semibold leading-tight">{value}</div>
      {sub && <div className="num text-[11px] text-muted">{sub}</div>}
    </div>
  );
}

function LiveView({ p }: { p: PointResponse }) {
  const { s, d } = useStore();
  const { point } = useData();
  const startLabel = p.start === "sep1" ? "Sep 1" : "Nov 1";
  const justStarted = p.chill.to_date < 2;
  const seasons = useMemo(() => p.past_seasons.map((x) => x.season).sort().reverse(), [p.past_seasons]);
  const [pick, setPick] = useState("2014-2015");

  return (
    <div>
      {point.origin === "demo" && <OfflineChip />}
      <Section title="This winter" sentence={null}>
        <Hero
          level={p.verdict.level}
          sentence={p.verdict.sentence}
          early={p.verdict.early}
          sub={`Season ${seasonShort(p.season)} · as of ${longDate(p.asof)} · counting from ${startLabel}`}
        />
        {p.flags.sunny_stretch && (
          <div className="mt-3 flex items-center gap-2 rounded-full bg-[#fbf0dc] px-3 py-1.5 text-[12px] text-[#74490c]">
            <Sun size={14} aria-hidden className="text-heat" />
            <span>Sunny stretch: tree chill likely lower than shown</span>
            <InfoTip label="sunny stretch">
              A heuristic: 7 or more clear days in the last 14 at the nearest station. Sunlit buds run warmer than the air (UC Davis TreeChill research).
            </InfoTip>
          </div>
        )}
        {justStarted && (
          <div className="mt-3 flex items-center gap-2 rounded-[12px] bg-bg px-3 py-2 text-[12px]">
            <Snowflake size={15} aria-hidden className="shrink-0 text-chill" />
            <span>Chill season just started. Explore a past winter meanwhile.</span>
            <Button className="ml-auto h-8 min-h-8 shrink-0 px-2 text-[12px]" onClick={() => d({ type: "replay", season: "2014-2015" })}>
              <Play size={13} aria-hidden /> Replay 2014-15
            </Button>
          </div>
        )}
        <div className="mt-4 flex items-center gap-3">
          <RingGauge value={p.chill.to_date} low={p.need.low} high={p.need.high} />
          <div className="grid min-w-0 flex-1 grid-cols-1 gap-2">
            <Tile
              label="Chill so far"
              value={
                <>
                  {p.chill.to_date.toFixed(0)} CP{p.chill.error_cp !== null ? ` ±${p.chill.error_cp.toFixed(0)}` : ""}
                </>
              }
              info={
                <>
                  {CP_INFO}
                  {p.chill.error_cp !== null && <> The ± range: 8 in 10 hidden-station tests landed within it.</>}
                </>
              }
            />
            <Tile label="Need" value={`${range(p.need.low, p.need.high)} by ${shortDate(p.need.by)}`} />
            <Tile
              label="Closest past winter"
              value={p.closest.season ? seasonShort(p.closest.season) : "Not available"}
              sub={p.closest.rmse_cp === null ? undefined : p.closest.rmse_cp < 0.05 && p.chill.to_date < 1 ? "no chill yet; matched on temperature" : `curves differ by ${p.closest.rmse_cp.toFixed(1)} CP`}
              info="The past winter whose chill curve over the last 30 days looks most like this one. Before any chill has built up, the match uses daily temperatures instead."
            />
          </div>
        </div>
        <p className="mt-3 text-[12px] text-muted">
          <span className="num">
            Likely by {shortDate(p.need.by)}: {range(Math.round(p.outlook.p10), Math.round(p.outlook.p90))} CP. Reaching {p.need.high}:{" "}
            {inTen(p.outlook.chance_high)}.
          </span>{" "}
          <InfoTip label="outlook">
            The range comes from {p.outlook.n_analogs} past winters played forward from today at this pin. It shows weather uncertainty; the ± on chill so far is estimation error.
          </InfoTip>
        </p>
      </Section>

      <Section title="Season so far" sentence={`Chill portions since ${startLabel}, against past winters at this pin.`} info={CP_INFO}>
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
        <div className="mt-3 flex items-center gap-2">
          <label htmlFor="year-pick" className="text-[12px] text-muted">
            Compare with a year you remember
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
      </Section>

      <Section title="Time machine" sentence="Replay a past winter day by day and watch the verdict change." info="Each day uses only what was known that day: chill so far, plus the other past winters played forward.">
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
      </Section>
      <Sources list={p.sources} method={p.method} />
    </div>
  );
}

export function ReplayView({ p }: { p: PointResponse }) {
  const { s, d } = useStore();
  const { replay } = useData();
  const { v } = useVarietyInfo();
  const frames = replay.data?.frames ?? [];
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const started = useRef<string | null>(null);

  // Autoplay once per loaded replay.
  useEffect(() => {
    const key = replay.data ? `${replay.data.season}:${frames.length}` : null;
    if (key && started.current !== key) {
      started.current = key;
      setIdx(0);
      setPlaying(true);
    }
  }, [replay.data, frames.length]);

  const step = frames.length > 1 ? Math.max(1, daysBetween(frames[0].date, frames[1].date)) : 1;
  // Advance by elapsed time (~10 days per second), skipping frames if rendering is slow.
  useEffect(() => {
    if (!playing || frames.length === 0) return;
    let raf = 0;
    const t0 = performance.now();
    const i0 = idx;
    const tick = (now: number) => {
      // rAF timestamps can precede t0 by a few ms: clamp so the index never goes below the start.
      const i = Math.max(0, Math.min(frames.length - 1, i0 + Math.floor(Math.max(0, now - t0) / (step * 100))));
      setIdx(i);
      if (i >= frames.length - 1) setPlaying(false);
      else raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, frames.length, step]);

  const season = s.replaySeason!;
  if (replay.error) return <ErrorLine message="Could not load that winter." onRetry={replay.retry} />;
  if (!replay.data || frames.length === 0) return <WinterSkeleton />;

  const f: Frame = frames[Math.max(0, Math.min(idx, frames.length - 1))];
  const low = p.need.low;
  const high = p.need.high;
  const mmdd = p.need.by.slice(5);
  const by = byForSeason(season, mmdd);
  const name = v?.name ?? "this variety";
  const sentence = `${plainVerdict(f.level, f.chance_low, low, high)} (${inTen(f.chance_low)} past winters reached ${low} by ${shortDate(by)}.)`;
  void name;
  const early = f.date.slice(5) < "11-15" && f.date.slice(5) >= "09-01";
  const own = p.past_seasons.find((x) => x.season === season)?.series ?? (p.season === season ? p.chill.series : []);
  const cut = own.filter((x) => x.date <= f.date);
  const done = idx >= frames.length - 1;

  return (
    <div>
      <div className="mb-2 flex items-center gap-2 rounded-[12px] bg-bg px-3 py-2 text-[12px]">
        <History size={15} aria-hidden className="text-brand" />
        <span className="font-medium">Replaying winter {seasonShort(season)}</span>
        <Button className="ml-auto h-8 min-h-8 px-2 text-[12px]" onClick={() => d({ type: "replay", season: null })}>
          <ArrowLeft size={13} aria-hidden /> Close replay
        </Button>
      </div>
      <Section title={`As of ${longDate(f.date)}`}>
        <Hero level={f.level} sentence={sentence} early={early} sub={`Expected by ${shortDate(by)}: probably ${range(Math.round(f.p10), Math.round(f.p90))} chill portions.`} />
        <div className="mt-4 flex items-center gap-3">
          <RingGauge value={f.cp} low={low} high={high} instant />
          <div className="grid min-w-0 flex-1 grid-cols-1 gap-2">
            <Tile label="Chill so far that day" value={`${f.cp.toFixed(0)} of ${range(low, high)}`} info={CP_INFO} />
            <Tile
              label={`What actually happened by ${shortDate(by)}`}
              value={!done ? "Shown when the replay ends" : replay.data.actual_final_cp !== null ? `${replay.data.actual_final_cp.toFixed(0)} chill portions` : "Not available"}
            />
          </div>
        </div>
      </Section>
      <Section title="How the season built up">
        <SeasonChart
          season={season}
          current={cut}
          past={p.past_seasons.filter((x) => x.season !== season)}
          need={{ low, high, by }}
          marker={f.date}
          markerLabel="As of"
          rangeBar={{ p10: f.p10, p50: f.p50, p90: f.p90 }}
          animate={false}
        />
        <div className="mt-3 flex items-center gap-3">
          <Button variant="primary" aria-label={playing ? "Pause" : "Play"} onClick={() => (done && !playing ? (setIdx(0), setPlaying(true)) : setPlaying(!playing))} className="w-11 px-0">
            {playing ? <Pause size={16} aria-hidden /> : <Play size={16} aria-hidden />}
          </Button>
          <Slider.Root
            className="relative flex h-5 flex-1 touch-none select-none items-center"
            min={0}
            max={frames.length - 1}
            step={1}
            value={[idx]}
            onValueChange={([i]) => {
              setPlaying(false);
              setIdx(i);
            }}
            aria-label="View as of date"
          >
            <Slider.Track className="relative h-1.5 grow rounded-full bg-line">
              <Slider.Range className="absolute h-full rounded-full bg-brand" />
            </Slider.Track>
            <Slider.Thumb className="block h-5 w-5 rounded-full border-2 border-brand bg-surface shadow" aria-label={`As of ${longDate(f.date)}`} />
          </Slider.Root>
          <span className="num w-14 text-right text-[12px] text-muted">{shortDate(f.date)}</span>
        </div>
      </Section>
      <Sources list={replay.data.sources ?? p.sources} method={replay.data.method ?? p.method} />
    </div>
  );
}

export function OfflineChip() {
  return (
    <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-bg px-2.5 py-1 text-[11px] text-muted" role="status">
      Offline: showing saved demo data
    </div>
  );
}

export function Sources({ list, method }: { list?: string[]; method?: string }) {
  if (!list || list.length === 0) return null;
  return (
    <p className="border-t border-line pt-3 text-[11px] leading-relaxed text-muted">
      Method {method}. Sources: {list.join("; ")}.
    </p>
  );
}
