"use client";

import { CalendarRange, Check, FileUp, Loader2, NotebookPen, Sparkles, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { longDate } from "@/lib/format";
import { fileReadings, loadLog, logReadings, parseFile, type ParsedFile } from "@/lib/orchardLog";
import { withUnit } from "@/lib/readings";
import { useStore } from "@/lib/store";
import type { Readings } from "@/lib/types";
import { Button, cn } from "../ui";
import StepCard from "./StepCard";

const STEP_MS = 450; // the server's steps are shown one by one so a watcher can follow them

type Phase = { kind: "idle" } | { kind: "reading"; file: File; shown: string[] } | { kind: "read"; file: File; parsed: ParsedFile; shown: number } | { kind: "error"; message: string };

function fmtBytes(n: number) {
  return n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`;
}

// The readings decide the winter and the "as of" date for everything that follows.
export function readingsPeriod(r: Readings): { winter: string; asof: string } {
  const [y, m] = r.last.split("-").map(Number);
  const start = m >= 9 ? y : y - 1;
  const yesterday = new Date(Date.now() - 86400000);
  const yIso = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, "0")}-${String(yesterday.getDate()).padStart(2, "0")}`;
  return { winter: `${start}-${String((start + 1) % 100).padStart(2, "0")}`, asof: r.last < yIso ? r.last : yIso };
}

export function readingsSummary(r: Readings | null): string {
  if (!r) return "";
  const { winter } = readingsPeriod(r);
  return `${r.kind === "daily" ? `${r.rows} days` : `${r.rows.toLocaleString()} readings`} · ${longDate(r.first)} to ${longDate(r.last)} · winter ${winter}`;
}

function Steps({ lines, busy }: { lines: string[]; busy: string | null }) {
  return (
    <ol className="space-y-1.5 text-[13px]" aria-live="polite">
      {lines.map((l, i) => (
        <li key={i} className="flex gap-2">
          <Check size={15} aria-hidden className="mt-0.5 shrink-0 text-brand" />
          <span>{l}</span>
        </li>
      ))}
      {busy && (
        <li className="flex gap-2 text-muted">
          <Loader2 size={15} aria-hidden className="mt-0.5 shrink-0 animate-spin" />
          <span>{busy}</span>
        </li>
      )}
    </ol>
  );
}

function Preview({ p }: { p: ParsedFile }) {
  const daily = p.kind === "daily";
  return (
    <table className="num mt-2 w-full text-left text-[12px]">
      <thead>
        <tr className="text-muted">
          <th className="py-1 font-medium">{daily ? "Date" : "Date and time"}</th>
          {daily ? (
            <>
              <th className="py-1 text-right font-medium">Low °{p.unit}</th>
              <th className="py-1 text-right font-medium">High °{p.unit}</th>
            </>
          ) : (
            <th className="py-1 text-right font-medium">Temp °{p.unit}</th>
          )}
        </tr>
      </thead>
      <tbody>
        {p.preview.map((r) => (
          <tr key={r.when} className="border-t border-line">
            <td className="py-1">{r.when}</td>
            {daily ? (
              <>
                <td className="py-1 text-right">{r.low}</td>
                <td className="py-1 text-right">{r.high}</td>
              </>
            ) : (
              <td className="py-1 text-right">{r.temp}</td>
            )}
          </tr>
        ))}
        <tr className="border-t border-line text-muted">
          <td className="py-1" colSpan={3}>
            ... and {Math.max(0, p.rows - p.preview.length).toLocaleString()} more
          </td>
        </tr>
      </tbody>
    </table>
  );
}

export default function StepReadings({ n, collapsed, onEdit }: { n: number; collapsed?: boolean; onEdit?: () => void }) {
  const { s, d } = useStore();
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [drag, setDrag] = useState(false);
  const [log, setLog] = useState<Readings | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const rd = s.readings;

  useEffect(() => {
    setLog(logReadings(loadLog()));
  }, []);

  // Reveal the server's steps one at a time.
  useEffect(() => {
    if (phase.kind !== "read" || phase.shown >= phase.parsed.steps.length) return;
    const t = setTimeout(() => setPhase({ ...phase, shown: phase.shown + 1 }), STEP_MS);
    return () => clearTimeout(t);
  }, [phase]);

  async function onFile(f: File | undefined) {
    if (!f) return;
    if (f.size > 8_000_000) {
      setPhase({ kind: "error", message: "That file is over 8 MB. Export daily lows and highs, or hourly logger data." });
      return;
    }
    setPhase({ kind: "reading", file: f, shown: [`Uploaded ${f.name} (${fmtBytes(f.size)}).`] });
    try {
      const parsed = await parseFile(f);
      setPhase({ kind: "read", file: f, parsed, shown: 0 });
    } catch (e) {
      setPhase({ kind: "error", message: e instanceof Error ? e.message : "Couldn't read that file." });
    }
  }

  const read = phase.kind === "read" ? phase : null;
  const allShown = read ? read.shown >= read.parsed.steps.length : false;
  const period = rd ? readingsPeriod(rd) : null;

  return (
    <StepCard n={n} title="Your daily temperatures" done={!!rd} collapsed={collapsed} summary={readingsSummary(rd)} onEdit={onEdit}>
      {!rd && phase.kind === "idle" && (
        <p className="mb-3 text-[13px] text-muted">Your orchard&apos;s daily low and high. Their dates set the winter we analyze.</p>
      )}

      {rd ? (
        <div className="space-y-2">
          <div className="rounded-[10px] border border-line bg-bg p-3 text-[14px]" role="status">
            <div className="flex items-start gap-2">
              <CalendarRange size={18} aria-hidden className="mt-0.5 shrink-0 text-brand" />
              <div className="min-w-0 flex-1">
                <div className="font-semibold">
                  Winter {period!.winter}, as of {longDate(period!.asof)}
                </div>
                <div className="text-[13px] text-muted">
                  {rd.kind === "daily" ? `${rd.rows} days` : `${rd.rows.toLocaleString()} readings`}, {longDate(rd.first)} to {longDate(rd.last)} · {rd.source}
                </div>
              </div>
              <button
                aria-label="Use different readings"
                className="rounded p-1 text-muted hover:bg-surface"
                onClick={() => {
                  d({ type: "readings", readings: null });
                  setPhase({ kind: "idle" });
                }}
              >
                <X size={16} />
              </button>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[12px] text-muted">Degrees</span>
            <div role="radiogroup" aria-label="Temperature unit" className="flex gap-1">
              {(["F", "C"] as const).map((u) => (
                <button
                  key={u}
                  role="radio"
                  aria-checked={rd.unit === u}
                  onClick={() => d({ type: "readings", readings: withUnit(rd, u) })}
                  className={cn("h-7 rounded-[6px] border px-2 text-[12px]", rd.unit === u ? "border-brand bg-brand text-white" : "border-line bg-surface")}
                >
                  °{u}
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : read || phase.kind === "reading" ? (
        <div className="rounded-[10px] border border-line bg-bg p-3">
          <Steps
            lines={phase.kind === "reading" ? phase.shown : [`Uploaded ${read!.file.name} (${fmtBytes(read!.file.size)}).`, ...read!.parsed.steps.slice(0, read!.shown)]}
            busy={phase.kind === "reading" ? "Reading the file..." : allShown ? null : "Checking..."}
          />
          {read && allShown && (
            <>
              {read.parsed.method === "ai" && (
                <p className="mt-2 flex gap-1.5 text-[12px] text-muted">
                  <Sparkles size={14} aria-hidden className="mt-0.5 shrink-0" />
                  AI file reader: {read.parsed.explanation} Every number below comes straight from your file.
                </p>
              )}
              <Preview p={read.parsed} />
              {(read.parsed.suspect ?? []).length > 0 && (
                <div className="mt-2 rounded-[8px] border border-amber-300 bg-amber-50 p-2.5 text-[12px] leading-relaxed text-amber-900" role="status">
                  <p className="font-semibold">
                    {(read.parsed.suspect ?? []).length} reading{(read.parsed.suspect ?? []).length > 1 ? "s look" : " looks"} wrong. They will be set aside, and those days
                    filled from the days around them:
                  </p>
                  <ul className="mt-1 list-disc pl-4">
                    {(read.parsed.suspect ?? []).slice(0, 5).map((f) => (
                      <li key={`${f.when}-${f.field}`}>
                        <strong>
                          {f.when}: {f.field} {f.value}°{read.parsed.unit}
                        </strong>
                        . {f.reason.charAt(0).toUpperCase() + f.reason.slice(1)}.
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                <Button variant="primary" className="h-10 text-[14px]" onClick={() => d({ type: "readings", readings: fileReadings(read.parsed, read.file.name) })}>
                  <Check size={16} aria-hidden /> Use these readings
                </Button>
                <Button className="h-10 text-[14px]" onClick={() => setPhase({ kind: "idle" })}>
                  Choose a different file
                </Button>
              </div>
            </>
          )}
        </div>
      ) : (
        <div className="grid gap-2 sm:grid-cols-2">
          <button
            onClick={() => fileRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              onFile(e.dataTransfer.files?.[0]);
            }}
            className={cn(
              "flex min-h-[104px] flex-col items-center justify-center gap-1.5 rounded-[12px] border-2 border-dashed p-4 text-center",
              drag ? "border-brand bg-brand/5" : "border-line hover:border-brand hover:bg-bg",
            )}
          >
            <FileUp size={24} aria-hidden className="text-brand" />
            <span className="text-[15px] font-semibold">Upload a file</span>
            <span className="text-[12px] text-muted">Excel, CSV, text, Word or PDF</span>
          </button>
          {log ? (
            <button
              onClick={() => d({ type: "readings", readings: log })}
              className="flex min-h-[104px] flex-col items-center justify-center gap-1.5 rounded-[12px] border-2 border-line p-4 text-center hover:border-brand hover:bg-bg"
            >
              <NotebookPen size={24} aria-hidden className="text-brand" />
              <span className="text-[15px] font-semibold">Use existing log of temps</span>
              <span className="text-[12px] text-muted">
                {log.rows} days, {longDate(log.first)} to {longDate(log.last)}
              </span>
            </button>
          ) : (
            <a
              href="/log"
              className="flex min-h-[104px] flex-col items-center justify-center gap-1.5 rounded-[12px] border-2 border-line p-4 text-center hover:border-brand hover:bg-bg"
            >
              <NotebookPen size={24} aria-hidden className="text-brand" />
              <span className="text-[15px] font-semibold">Type them in</span>
              <span className="text-[12px] text-muted">Keep a daily log of lows and highs</span>
            </a>
          )}
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.txt,.tsv,.dat,.log,.xlsx,.xlsm,.xls,.docx,.pdf"
            className="sr-only"
            aria-label="Thermometer or logger file"
            onChange={(e) => {
              onFile(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
        </div>
      )}

      {phase.kind === "error" && (
        <div className="mt-2 flex items-start justify-between gap-2 rounded-[8px] bg-red-50 p-2.5 text-[12px] text-red-800" role="alert">
          <span>{phase.message}</span>
          <button className="shrink-0 underline" onClick={() => setPhase({ kind: "idle" })}>
            Try again
          </button>
        </div>
      )}
    </StepCard>
  );
}
