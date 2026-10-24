"use client";

import * as Slider from "@radix-ui/react-slider";
import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { useData } from "@/lib/data";
import { seasonShort } from "@/lib/format";
import type { ValidationResponse } from "@/lib/types";
import { Sources } from "./WinterTab";
import { ErrorLine, Section, Skeleton, cn } from "../ui";

// Validated categorical order (dataviz palette, adjacent pairs pass; contrast WARN -> legend + table view).
const DURHAM = { truth: "#2a78d6", e0: "#eb6834", e3: "#1baf7a", e4: "#eda100" };

const READING_ROWS: [string, string][] = [
  ["station_only", "No readings (station estimate)"],
  ["readings_from_sep1", "Readings from Sep 1"],
  ["readings_from_nov1", "Readings from Nov 1"],
  ["readings_from_dec1", "Readings from Dec 1"],
  ["readings_from_jan1", "Readings from Jan 1"],
];

function ReadingsTable({ o }: { o: NonNullable<ValidationResponse["orchard_readings"]> }) {
  const we = o.tests.wildeye_orchard;
  const hs = o.tests.hidden_station;
  const fmt = (x: number | undefined) => (x === undefined ? "Not available" : `${x.toFixed(1)}%`);
  const sentence =
    we && we.scenarios.station_only?.mape_mar1 !== undefined && we.scenarios.readings_from_sep1?.mape_mar1 !== undefined
      ? `At ${we.n_sites} pistachio orchards, a min/max thermometer cut the typical error from ${fmt(we.scenarios.station_only.mape_mar1)} to ${fmt(we.scenarios.readings_from_sep1.mape_mar1)} (lower is better).`
      : "Typical error when the grower adds daily lows and highs (lower is better).";
  return (
    <Section
      title="Your own readings"
      sentence={sentence}
      info="Error is the miss as a percent of the chill each site actually measured by Mar 1. We gave the method each site's own daily low and high from the start date on, used the station estimate before that, and compared with the site's hourly truth."
    >
      <table className="num w-full text-left text-[12px]">
        <thead>
          <tr className="text-muted">
            <th className="py-1 font-medium">Typical error (lower is better)</th>
            {we && <th className="py-1 text-right font-medium">In orchards ({we.n_station_winters} winters)</th>}
            {hs && <th className="py-1 text-right font-medium">Hidden stations ({hs.n_station_winters})</th>}
          </tr>
        </thead>
        <tbody>
          {READING_ROWS.map(([k, label]) => (
            <tr key={k} className="border-t border-line">
              <td className="py-1">{label}</td>
              {we && <td className="py-1 text-right">{fmt(we.scenarios[k]?.mape_mar1)}</td>}
              {hs && <td className="py-1 text-right">{fmt(hs.scenarios[k]?.mape_mar1)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-1 text-[11px] text-muted">Starting late still helps. The thermometer must be shaded and ventilated, like a weather station.</p>
    </Section>
  );
}

function Bars({ items, highlight, max }: { items: { id: string; name: string; mae: number | null; p80?: number | null }[]; highlight: string[]; max: number }) {
  return (
    <ul className="space-y-1.5">
      {items.map((e) => (
        <li key={e.id} className="grid grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_auto] items-center gap-2 text-[12px]">
          <span title={`${e.id} · ${e.name}`} className={cn("truncate", highlight.includes(e.id) && "font-semibold")}>
            {e.id} · {e.name}
          </span>
          <span className="relative h-3 rounded-[2px] bg-bg">
            {e.mae !== null && (
              <span
                className="absolute inset-y-0 left-0 rounded-r-[4px]"
                style={{ width: `${Math.min(100, (e.mae / max) * 100)}%`, background: highlight.includes(e.id) ? "#2e6a4f" : "#8f9993" }}
              />
            )}
            {e.p80 !== null && e.p80 !== undefined && (
              <span className="absolute -top-0.5 h-4 w-[2px] bg-ink" style={{ left: `${Math.min(100, (e.p80 / max) * 100)}%` }} title={`8 in 10 within ${e.p80.toFixed(1)} CP`} />
            )}
          </span>
          <span className="num w-16 text-right">{e.mae === null ? "Not available" : `${e.mae.toFixed(1)} CP`}</span>
        </li>
      ))}
    </ul>
  );
}

function interp(xs: number[], ys: number[], x: number): number {
  if (x <= xs[0]) return ys[0];
  for (let i = 1; i < xs.length; i++) if (x <= xs[i]) return ys[i - 1] + ((ys[i] - ys[i - 1]) * (x - xs[i - 1])) / (xs[i] - xs[i - 1]);
  return ys[ys.length - 1];
}

export default function AccuracyTab() {
  const { validation } = useData();
  if (validation.error && !validation.data) return <ErrorLine message="Could not load validation results." onRetry={validation.retry} />;
  if (!validation.data) {
    return (
      <div className="space-y-3 py-2" aria-busy="true">
        <Skeleton className="h-6 w-full" />
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
      </div>
    );
  }
  return <SimpleAccuracy v={validation.data} />;
}

function Headline({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-[10px] bg-bg p-3">
      <div className="num text-[22px] font-semibold leading-none text-ink">{value}</div>
      <div className="mt-1 text-[12px] leading-snug text-muted">{label}</div>
    </div>
  );
}

// Errors as a percent of the chill actually measured by Mar 1 (lower is better).
const pctOf = (x: number | null | undefined) => (x === null || x === undefined ? "Not available" : `${x.toFixed(1)}%`);

// The default view: how we tested, in plain words, with three headline numbers. Details on request.
function SimpleAccuracy({ v }: { v: ValidationResponse }) {
  const [more, setMore] = useState(false);
  const est = Object.fromEntries(v.estimators.map((e) => [e.id, e]));
  const ours = est[v.default_ids?.history ?? "E4"]?.mape_mar1;
  const nearest = est["E0"]?.mape_mar1;
  const we = v.orchard_readings?.tests?.wildeye_orchard;
  const hs = v.orchard_readings?.tests?.hidden_station;
  const withReadings = we?.scenarios?.readings_from_sep1?.mape_mar1;
  const atOrchards = we?.scenarios?.station_only?.mape_mar1;
  const bt = v.backtest;
  return (
    <div>
      <div className="grid gap-2 sm:grid-cols-3">
        <Headline value={pctOf(atOrchards)} label="typical error from weather stations alone (lower is better)" />
        <Headline value={pctOf(withReadings)} label="typical error with the orchard's own daily highs and lows (lower is better)" />
        <Headline value={`${v.n_station_seasons.toLocaleString()}`} label="real winters used to test it" />
      </div>
      <p className="mt-3 text-[14px] font-semibold">How we tested it, in plain terms</p>
      <ul className="mt-1.5 list-disc space-y-1.5 pl-5 text-[13px] leading-relaxed">
        <li>
          <strong>We hid real weather stations, one at a time,</strong> estimated each from all the others the way the app estimates your orchard, and compared
          with what it really measured. {v.n_stations} stations, {v.n_station_seasons} winters.
        </li>
        <li>
          <strong>Our method beat using the nearest station:</strong> {pctOf(ours)} typical error against {pctOf(nearest)} (lower is better).
        </li>
        {we && (
          <li>
            <strong>We repeated the test inside {we.n_sites} real pistachio orchards</strong> with their own weather stations (Wildeye in-orchard sensors, data from
            the UC Fruit &amp; Nut Research and Information Center; not CIMIS stations). Stations alone: {pctOf(atOrchards)} error; with the orchard&apos;s daily highs
            and lows: {pctOf(withReadings)}
            {hs ? ` (${pctOf(hs.scenarios.readings_from_sep1?.mape_mar1)} at the hidden stations)` : ""}. Lower is better.
          </li>
        )}
        {bt.brier !== null && bt.brier_climatology !== null && (
          <li>
            <strong>We checked the odds against what really happened.</strong> Replaying every past winter, our chances were{" "}
            {Math.round((1 - bt.brier / bt.brier_climatology) * 100)}% more accurate than simply counting how often past winters made it (higher is better).
          </li>
        )}
        {v.diet_rule && (
          <li>
            <strong>We tested missing days</strong> by deleting days from real records: up to 30% of days missing, or gaps up to 4 days, keeps the error small.
          </li>
        )}
        <li>
          <strong>The chill math matches UC&apos;s calculator</strong> to three decimal places on the same weather data.
        </li>
        <li>
          <strong>Every &quot;give or take&quot; in the app comes from these tests:</strong> 8 in 10 test cases landed within it.
        </li>
      </ul>
      <button className="mt-3 flex items-center gap-1 text-[13px] font-medium text-brand hover:underline" onClick={() => setMore((m) => !m)} aria-expanded={more}>
        {more ? "Hide the full test results" : "See the full test results"}
      </button>
      {more && (
        <div className="mt-3 border-t border-line pt-3">
          <Accuracy v={v} />
        </div>
      )}
    </div>
  );
}

function Accuracy({ v }: { v: ValidationResponse }) {
  const [table, setTable] = useState(false);
  const [blk, setBlk] = useState(1);
  const [pct, setPct] = useState(10);
  const est = Object.fromEntries(v.estimators.map((e) => [e.id, e]));
  const histId = v.default_ids?.history ?? "E3";
  const liveId = v.default_ids?.live ?? "E4";
  const ours = est[histId];
  const nearest = est["E0"];
  const max = Math.max(...v.estimators.map((e) => e.p80_cp ?? e.mae_cp ?? 0), 1) * 1.08;

  const diet = useMemo(() => {
    const rows = v.data_diet.filter((r) => r.gap_days === blk).sort((a, b) => a.missing_pct - b.missing_pct);
    return { xs: rows.map((r) => r.missing_pct), ys: rows.map((r) => r.mae_cp) };
  }, [v.data_diet, blk]);
  const blocks = [...new Set(v.data_diet.map((r) => r.gap_days))].sort((a, b) => a - b);
  const expected = diet.xs.length ? interp(diet.xs, diet.ys, pct) : null;

  return (
    <div>
      <Section title="How good is it?" sentence={null} info="We hide one station at a time, estimate it from everything else, then compare with what the station measured.">
        <p className="text-[16px] leading-snug">
          We hid <strong className="num">{v.n_stations}</strong> stations and predicted them. Typical miss:{" "}
          <strong className="num">{ours?.mae_cp?.toFixed(1) ?? "Not available"} CP</strong>. Nearest station:{" "}
          <strong className="num">{nearest?.mae_cp?.toFixed(1) ?? "Not available"} CP</strong>.
        </p>
        <p className="mt-1 text-[12px] text-muted">
          {v.n_station_seasons} station-winters, chill by Mar 1. Bar = typical miss; tick = 8 in 10 within.
        </p>
        <div className="mt-3">
          <Bars
            items={v.estimators.filter((e) => e.id !== "E7" || e.mae_cp !== null).map((e) => ({ id: e.id, name: e.name, mae: e.mae_cp, p80: e.p80_cp }))}
            highlight={[histId, liveId]}
            max={max}
          />
        </div>
        <p className="mt-2 text-[11px] text-muted">
          Bold: ChillPrint defaults ({histId} for past winters, {liveId} for this winter). The map shows each hidden station&apos;s miss.
        </p>
      </Section>

      <Section title="At the orchard" sentence={`${v.wildeye.n_stations} in-orchard Wildeye stations that gridded data never sees.`} info="Private pistachio-orchard sensors are an independent test: no gridded product ingests them, so there is no leakage.">
        <Bars
          items={v.wildeye.estimators.map((e) => ({ id: e.id, name: est[e.id]?.name ?? e.id, mae: e.mae_cp }))}
          highlight={[histId, liveId]}
          max={Math.max(...v.wildeye.estimators.map((e) => e.mae_cp ?? 0), 1) * 1.1}
        />
      </Section>

      {v.durham.winters.length > 0 && (
        <Section title="Durham after the station closed" sentence="What Butte County growers get now, against what Durham measured." info="Durham (CIMIS 12) stopped reporting in July 2025. Each line estimates Durham without its own data.">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={v.durham.winters.map((w) => ({ ...w, label: seasonShort(w.season) }))} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
              <CartesianGrid stroke="#ecebe5" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 10, fill: "#5b6660" }} interval={2} tickLine={false} axisLine={{ stroke: "#e3e1da" }} />
              <YAxis tick={{ fontSize: 11, fill: "#5b6660" }} axisLine={false} tickLine={false} width={44} domain={["auto", "auto"]} />
              <Line dataKey="truth" name="Durham measured" stroke={DURHAM.truth} strokeWidth={2.5} dot={{ r: 3 }} isAnimationActive={false} />
              <Line dataKey="e0" name="Nearest station" stroke={DURHAM.e0} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line dataKey="e3" name={`E3 · ${est.E3?.name ?? ""}`} stroke={DURHAM.e3} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line dataKey="e4" name={`E4 · ${est.E4?.name ?? ""}`} stroke={DURHAM.e4} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Tooltip
                content={({ active, payload, label }) =>
                  active && payload?.length ? (
                    <div className="rounded-[8px] border border-line bg-surface px-2.5 py-1.5 text-[12px] shadow-md">
                      <div className="font-semibold">Winter {label}</div>
                      {payload.map((p) => (
                        <div key={String(p.dataKey)} className="num">
                          {p.name}: {typeof p.value === "number" ? p.value.toFixed(1) : "Not available"} CP
                        </div>
                      ))}
                    </div>
                  ) : null
                }
              />
            </LineChart>
          </ResponsiveContainer>
          <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted">
            {[["truth", "Durham measured"], ["e0", "Nearest station (E0)"], ["e3", "E3"], ["e4", "E4"]].map(([k, l]) => (
              <li key={k} className="flex items-center gap-1">
                <span className="inline-block h-[3px] w-4 rounded" style={{ background: DURHAM[k as keyof typeof DURHAM] }} /> {l}
              </li>
            ))}
          </ul>
          <button className="mt-2 text-[12px] text-chill underline" onClick={() => setTable(!table)}>
            {table ? "Hide table" : "Show table"}
          </button>
          {table && (
            <table className="num mt-2 w-full text-[12px]">
              <thead className="bg-bg text-left">
                <tr>
                  {["Winter", "Measured", "E0", "E3", "E4"].map((h) => (
                    <th key={h} className="px-2 py-1">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {v.durham.winters.map((w) => (
                  <tr key={w.season} className="border-t border-line">
                    <td className="px-2 py-1">{seasonShort(w.season)}</td>
                    {[w.truth, w.e0, w.e3, w.e4].map((x, i) => (
                      <td key={i} className="px-2 py-1">
                        {x === null ? "Not available" : x.toFixed(1)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Section>
      )}

      <Section title="Data gaps" sentence={v.diet_rule ?? "Drag to see the expected miss when days are missing."} info="We deleted days from complete station records, filled them by straight lines, rebuilt the hours and counted chill again.">
        <div className="mb-2 flex flex-wrap gap-1.5" role="radiogroup" aria-label="Gap pattern">
          {blocks.map((b) => (
            <button key={b} role="radio" aria-checked={blk === b} onClick={() => setBlk(b)} className={cn("h-7 rounded-[8px] border px-2 text-[12px]", blk === b ? "border-brand bg-brand text-white" : "border-line")}>
              {b === 1 ? "Scattered days" : `${b}-day gaps`}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <Slider.Root className="relative flex h-5 flex-1 touch-none select-none items-center" min={0} max={50} step={1} value={[pct]} onValueChange={([x]) => setPct(x)} aria-label="Missing days, percent">
            <Slider.Track className="relative h-1.5 grow rounded-full bg-line">
              <Slider.Range className="absolute h-full rounded-full bg-chill" />
            </Slider.Track>
            <Slider.Thumb className="block h-5 w-5 rounded-full border-2 border-chill bg-surface shadow" aria-label={`${pct}% of days missing`} />
          </Slider.Root>
          <span className="num w-24 text-right text-[12px]">{pct}% missing</span>
        </div>
        <p className="num mt-2 text-[14px]">
          Expected miss: <strong>{expected === null ? "Not available" : `${expected.toFixed(1)} CP`}</strong>
        </p>
      </Section>

      {v.e5_note && (
        <Section title="One reading a day" sentence={v.e5_note} info="E5 uses the orchard's own daily low and high plus the nearest station's hourly shape. A simple min/max thermometer gives this." />
      )}

      {v.orchard_readings && <ReadingsTable o={v.orchard_readings} />}

      <Section title="Are the odds honest?" sentence={v.backtest.brier !== null && v.backtest.brier_climatology !== null ? `Outlook score ${v.backtest.brier.toFixed(3)} vs ${v.backtest.brier_climatology.toFixed(3)} for past-winter shares alone (lower is better).` : "Not available"} info="Brier score from replaying every station-winter on Dec 1, Jan 1 and Feb 1, never using the winter being tested.">
        {v.backtest.reliability.length > 0 && (
          <ResponsiveContainer width="100%" height={180}>
            <ScatterChart margin={{ top: 8, right: 8, bottom: 4, left: -18 }}>
              <CartesianGrid stroke="#ecebe5" />
              <XAxis type="number" dataKey="predicted" domain={[0, 1]} ticks={[0, 0.5, 1]} tickFormatter={(x) => `${Math.round(x * 10)} in 10`} tick={{ fontSize: 10, fill: "#5b6660" }} name="Predicted" />
              <YAxis type="number" dataKey="observed" domain={[0, 1]} ticks={[0, 0.5, 1]} tickFormatter={(x) => `${Math.round(x * 10)} in 10`} tick={{ fontSize: 10, fill: "#5b6660" }} width={56} name="Happened" />
              <ZAxis type="number" dataKey="n" range={[40, 200]} />
              <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="#5b6660" strokeDasharray="3 3" />
              <Scatter data={v.backtest.reliability} fill="#3b7ea1" stroke="#fff" strokeWidth={2} isAnimationActive={false} />
              <Tooltip
                content={({ active, payload }) => {
                  const r = payload?.[0]?.payload as ValidationResponse["backtest"]["reliability"][number] | undefined;
                  return active && r ? (
                    <div className="num rounded-[8px] border border-line bg-surface px-2.5 py-1.5 text-[12px] shadow-md">
                      Said {Math.round(r.predicted * 100) / 10} in 10, happened {Math.round(r.observed * 100) / 10} in 10 ({r.n} cases)
                    </div>
                  ) : null;
                }}
              />
            </ScatterChart>
          </ResponsiveContainer>
        )}
        <p className="text-[11px] text-muted">Dots on the dashed line mean the stated odds came true as often as stated.</p>
      </Section>

      {v.findings && v.findings.length > 0 && (
        <Section title="What we found">
          <ul className="list-disc space-y-1 pl-4 text-[12px]">
            {v.findings.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </Section>
      )}
      <p className="pt-2 text-[12px] text-muted">{v.leakage_note}</p>
      <Sources list={v.sources} method={v.method} />
    </div>
  );
}
