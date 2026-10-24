"use client";

import { Check, FileUp, Loader2, NotebookPen, Sparkles, Thermometer, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useData } from "@/lib/data";
import { longDate } from "@/lib/format";
import { fileReadings, loadLog, logReadings, parseFile, type ParsedFile } from "@/lib/orchardLog";
import { withUnit } from "@/lib/readings";
import { useStore } from "@/lib/store";
import { Button, cn } from "../ui";
import StepCard from "./StepCard";

const STEP_MS = 450; // the server's steps are shown one by one so a watcher can follow them

type Phase = { kind: "idle" } | { kind: "reading"; file: File; shown: string[] } | { kind: "read"; file: File; parsed: ParsedFile; shown: number } | { kind: "error"; message: string };

function fmtBytes(n: number) {
  return n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`;
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

export default function StepReadings({ n }: { n: number }) {
  const { s, d } = useStore();
  const { validation } = useData();
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [drag, setDrag] = useState(false);
  const [logDays, setLogDays] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);
  const rd = s.readings;

  useEffect(() => {
    setLogDays(Object.keys(loadLog().entries).length);
  }, []);

  // Reveal the server's steps one at a time.
  useEffect(() => {
    if (phase.kind !== "read" || phase.shown >= phase.parsed.steps.length) return;
    const t = setTimeout(() => setPhase({ ...phase, shown: phase.shown + 1 }), STEP_MS);
    return () => clearTimeout(t);
  }, [phase]);

  const test = validation.data?.orchard_readings?.tests?.wildeye_orchard;
  const before = test?.scenarios?.station_only?.mae_cp;
  const after = test?.scenarios?.readings_from_sep1?.mae_cp;

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

  function applyLog() {
    const r = logReadings(loadLog());
    if (r) d({ type: "readings", readings: r });
  }

  const reading = phase.kind === "reading";
  const read = phase.kind === "read" ? phase : null;
  const allShown = read ? read.shown >= read.parsed.steps.length : false;

  return (
    <StepCard n={n} title="Your orchard's own readings (optional)" done={!!rd}>
      <p className="text-[13px] leading-relaxed">
        A weather station miles away can&apos;t see your orchard&apos;s cold pockets or warm afternoons. If you keep a min/max thermometer or a
        temperature logger in the orchard, add its readings and chill is counted from your own temperatures.
        {before !== undefined && after !== undefined && (
          <>
            {" "}
            In our tests at {test!.n_sites} pistachio orchards with their own sensors (Wildeye stations, data from UC FNRIC), this cut the typical miss from <span className="num font-semibold">{before.toFixed(1)}</span> to{" "}
            <span className="num font-semibold">{after.toFixed(1)}</span> chill portions.
          </>
        )}
      </p>

      {rd ? (
        <div className="mt-3 rounded-[10px] border border-line bg-bg p-3 text-[13px]" role="status">
          <div className="flex items-start gap-2">
            <Thermometer size={18} aria-hidden className="mt-0.5 shrink-0 text-chill" />
            <div className="min-w-0 flex-1">
              <div className="font-medium">
                Using {rd.kind === "daily" ? `${rd.rows} days of lows and highs` : `${rd.rows.toLocaleString()} logger readings`}
              </div>
              <div className="text-muted">
                {longDate(rd.first)} to {longDate(rd.last)} · {rd.source}
              </div>
            </div>
            <button
              aria-label="Stop using these readings"
              className="rounded p-1 text-muted hover:bg-surface"
              onClick={() => {
                d({ type: "readings", readings: null });
                setPhase({ kind: "idle" });
              }}
            >
              <X size={16} />
            </button>
          </div>
          <div className="mt-2 flex items-center gap-2">
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
      ) : read || reading ? (
        <div className="mt-3 rounded-[10px] border border-line bg-bg p-3">
          <Steps
            lines={phase.kind === "reading" ? phase.shown : [`Uploaded ${read!.file.name} (${fmtBytes(read!.file.size)}).`, ...read!.parsed.steps.slice(0, read!.shown)]}
            busy={reading ? "Reading the file..." : allShown ? null : "Checking..."}
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
              {read.parsed.suspect.length > 0 && (
                <div className="mt-2 rounded-[8px] border border-amber-300 bg-amber-50 p-2.5 text-[12px] leading-relaxed text-amber-900" role="status">
                  <p className="font-semibold">
                    {read.parsed.suspect.length} reading{read.parsed.suspect.length > 1 ? "s look" : " looks"} wrong. They will be set aside, and those days
                    filled from the days around them:
                  </p>
                  <ul className="mt-1 list-disc pl-4">
                    {read.parsed.suspect.slice(0, 5).map((f) => (
                      <li key={`${f.when}-${f.field}`}>
                        <strong>
                          {f.when}: {f.field} {f.value}°{read.parsed.unit}
                        </strong>
                        . {f.reason.charAt(0).toUpperCase() + f.reason.slice(1)}.
                      </li>
                    ))}
                  </ul>
                  <p className="mt-1">When you run the analysis, every reading is also checked against what nearby weather stations measured that day.</p>
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
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
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
              "flex min-h-[112px] flex-col items-center justify-center gap-1.5 rounded-[12px] border-2 border-dashed p-4 text-center",
              drag ? "border-brand bg-brand/5" : "border-line hover:border-brand hover:bg-bg",
            )}
          >
            <FileUp size={24} aria-hidden className="text-brand" />
            <span className="text-[15px] font-semibold">Upload a file</span>
            <span className="text-[12px] text-muted">Drop it here or click. Excel, CSV, text, Word or PDF, any layout.</span>
          </button>
          <a
            href="/log"
            className="flex min-h-[112px] flex-col items-center justify-center gap-1.5 rounded-[12px] border border-line p-4 text-center hover:border-brand hover:bg-bg"
          >
            <NotebookPen size={24} aria-hidden className="text-brand" />
            <span className="text-[15px] font-semibold">Type them in</span>
            <span className="text-[12px] text-muted">
              {logDays ? `Your orchard log has ${logDays} day${logDays === 1 ? "" : "s"}. Open it to add today.` : "Keep a simple daily log of each day's low and high."}
            </span>
          </a>
          {logDays >= 3 && (
            <Button className="h-10 text-[14px] sm:col-span-2" onClick={applyLog}>
              <NotebookPen size={16} aria-hidden /> Use my orchard log ({logDays} days)
            </Button>
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
      <p className="mt-2 text-[12px] leading-relaxed text-muted">
        Keep the thermometer in shade about 5 ft up with air moving past it, like a weather station. In the sun it reads too warm and undercounts chill.
      </p>
    </StepCard>
  );
}
