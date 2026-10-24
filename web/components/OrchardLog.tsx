"use client";

import { ArrowLeft, ArrowRight, Download, FileUp, Loader2, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { longDate } from "@/lib/format";
import { loadLog, logToCsv, parseFile, saveLog, type OrchardLog } from "@/lib/orchardLog";
import { Button, cn } from "./ui";

function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function shiftIso(iso: string, days: number) {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const input = "h-14 w-full rounded-[10px] border border-line bg-surface px-3 text-[22px] font-semibold num focus:border-brand focus:outline-none";

export default function OrchardLogPage() {
  const [log, setLog] = useState<OrchardLog>({ unit: "F", entries: {} });
  const [day, setDay] = useState(todayIso());
  const [low, setLow] = useState("");
  const [high, setHigh] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [importing, setImporting] = useState(false);
  const [stored, setStored] = useState(true);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => setLog(loadLog()), []);

  // Show what is already saved for the chosen day.
  useEffect(() => {
    const e = log.entries[day];
    setLow(e ? String(e.low) : "");
    setHigh(e ? String(e.high) : "");
  }, [day, log.entries]);

  function commit(next: OrchardLog) {
    setLog(next);
    setStored(saveLog(next));
  }

  function save() {
    const lo = Number(low), hi = Number(high);
    if (low === "" || high === "" || !isFinite(lo) || !isFinite(hi)) {
      setMsg({ ok: false, text: "Enter both the low and the high." });
      return;
    }
    const [a, b] = lo <= hi ? [lo, hi] : [hi, lo];
    const lim = log.unit === "F" ? [-20, 120] : [-30, 50];
    if (a < lim[0] || b > lim[1]) {
      setMsg({ ok: false, text: `Those look out of range for °${log.unit}. Check the unit at the top.` });
      return;
    }
    commit({ ...log, entries: { ...log.entries, [day]: { low: a, high: b } } });
    setMsg({ ok: true, text: `Saved ${longDate(day)}: low ${a}°, high ${b}°.` });
    if (day !== todayIso() && !log.entries[shiftIso(day, 1)] && shiftIso(day, 1) <= todayIso()) setDay(shiftIso(day, 1));
  }

  async function importFile(f: File | undefined) {
    if (!f) return;
    setImporting(true);
    setMsg(null);
    try {
      const p = await parseFile(f);
      if (p.kind !== "daily" || !p.dates || !p.lows || !p.highs) {
        setMsg({ ok: false, text: "That file has logger readings, not daily lows and highs. Upload it on the main page instead." });
        return;
      }
      const conv = (v: number) => (p.unit === log.unit ? v : log.unit === "F" ? Math.round((v * 9) / 5 + 32) : Math.round(((v - 32) * 5) / 9 * 10) / 10);
      const entries = { ...log.entries };
      p.dates.forEach((d, i) => (entries[d] = { low: conv(p.lows![i]), high: conv(p.highs![i]) }));
      commit({ ...log, entries });
      setMsg({ ok: true, text: `Added ${p.rows} days from ${f.name} (${p.first} to ${p.last}).` });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Couldn't read that file." });
    } finally {
      setImporting(false);
    }
  }

  function download() {
    const blob = new Blob([logToCsv(log)], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "orchard-log.csv";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  const days = Object.keys(log.entries).sort().reverse();

  return (
    <div className="min-h-dvh bg-bg">
      <header className="flex h-14 items-center gap-3 border-b border-line bg-surface px-4">
        <Link href="/" className="flex items-center gap-1.5 text-[14px] text-brand hover:underline">
          <ArrowLeft size={16} aria-hidden /> ChillPrint
        </Link>
        <div className="ml-auto flex rounded-[8px] border border-line p-0.5" role="group" aria-label="Temperature units">
          {(["F", "C"] as const).map((u) => (
            <button
              key={u}
              aria-pressed={log.unit === u}
              onClick={() => commit({ ...log, unit: u })}
              className={cn("h-8 rounded-[6px] px-3 text-[14px] font-semibold", log.unit === u ? "bg-brand text-white" : "text-muted")}
            >
              °{u}
            </button>
          ))}
        </div>
      </header>

      <main className="mx-auto max-w-[720px] space-y-4 p-4 sm:p-6">
        <div>
          <h1 className="text-[26px] font-semibold leading-tight">My orchard log</h1>
          <p className="mt-1 text-[15px] leading-relaxed text-muted">
            Each day, write down the lowest and highest temperature your orchard thermometer showed. ChillPrint counts chill from these instead of a station
            miles away. Your log is saved on this device.
          </p>
        </div>

        <section className="rounded-[14px] border border-line bg-surface p-4 sm:p-5">
          <label className="block text-[14px] font-semibold" htmlFor="log-day">
            Day
          </label>
          <div className="mt-1 flex gap-2">
            <Button className="h-12 px-3" onClick={() => setDay(shiftIso(day, -1))} aria-label="Previous day">
              <ArrowLeft size={18} />
            </Button>
            <input id="log-day" type="date" value={day} max={todayIso()} onChange={(e) => e.target.value && setDay(e.target.value)} className="h-12 flex-1 rounded-[10px] border border-line px-3 text-[16px]" />
            <Button className="h-12 px-3" onClick={() => day < todayIso() && setDay(shiftIso(day, 1))} aria-label="Next day" disabled={day >= todayIso()}>
              <ArrowRight size={18} />
            </Button>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[14px] font-semibold" htmlFor="log-low">
                Low (°{log.unit})
              </label>
              <input id="log-low" inputMode="decimal" className={cn(input, "mt-1")} value={low} onChange={(e) => setLow(e.target.value)} placeholder="e.g. 36" />
            </div>
            <div>
              <label className="block text-[14px] font-semibold" htmlFor="log-high">
                High (°{log.unit})
              </label>
              <input
                id="log-high"
                inputMode="decimal"
                className={cn(input, "mt-1")}
                value={high}
                onChange={(e) => setHigh(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && save()}
                placeholder="e.g. 58"
              />
            </div>
          </div>
          <Button variant="primary" className="mt-4 h-12 w-full text-[16px]" onClick={save}>
            Save {day === todayIso() ? "today" : longDate(day)}
          </Button>
          {msg && (
            <p className={cn("mt-2 text-[14px]", msg.ok ? "text-brand" : "text-red-700")} role="status">
              {msg.text}
            </p>
          )}
          {!stored && <p className="mt-2 text-[13px] text-red-700">This browser isn&apos;t saving data (private mode?). Download your log so you don&apos;t lose it.</p>}
        </section>

        <Link
          href="/?log=1"
          className={cn(
            "flex h-14 items-center justify-center gap-2 rounded-[12px] text-[16px] font-semibold text-white",
            days.length >= 3 ? "bg-brand hover:opacity-95" : "pointer-events-none bg-line text-muted",
          )}
          aria-disabled={days.length < 3}
        >
          Check my chill with this log <ArrowRight size={18} aria-hidden />
        </Link>
        {days.length < 3 && <p className="-mt-2 text-center text-[13px] text-muted">Log at least 3 days to check your chill.</p>}

        <section className="rounded-[14px] border border-line bg-surface p-4 sm:p-5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="flex-1 text-[17px] font-semibold">
              {days.length} day{days.length === 1 ? "" : "s"} logged
            </h2>
            <Button className="h-9 text-[13px]" onClick={() => fileRef.current?.click()} disabled={importing}>
              {importing ? <Loader2 size={15} className="animate-spin" aria-hidden /> : <FileUp size={15} aria-hidden />} Add from a file
            </Button>
            <Button className="h-9 text-[13px]" onClick={download} disabled={!days.length}>
              <Download size={15} aria-hidden /> Download
            </Button>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.txt,.tsv,.xlsx,.xlsm,.xls,.docx,.pdf"
              className="sr-only"
              aria-label="Add days from a file"
              onChange={(e) => {
                importFile(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
          </div>
          {days.length ? (
            <table className="num mt-3 w-full text-left text-[15px]">
              <thead>
                <tr className="text-[13px] text-muted">
                  <th className="py-1.5 font-medium">Day</th>
                  <th className="py-1.5 text-right font-medium">Low</th>
                  <th className="py-1.5 text-right font-medium">High</th>
                  <th className="w-10" />
                </tr>
              </thead>
              <tbody>
                {days.slice(0, 120).map((d) => (
                  <tr key={d} className={cn("border-t border-line", d === day && "bg-bg")}>
                    <td className="py-1.5">
                      <button className="hover:underline" onClick={() => setDay(d)}>
                        {longDate(d)}
                      </button>
                    </td>
                    <td className="py-1.5 text-right">{log.entries[d].low}°</td>
                    <td className="py-1.5 text-right">{log.entries[d].high}°</td>
                    <td className="py-1.5 text-right">
                      <button
                        aria-label={`Delete ${longDate(d)}`}
                        className="rounded p-1 text-muted hover:text-red-700"
                        onClick={() => {
                          const entries = { ...log.entries };
                          delete entries[d];
                          commit({ ...log, entries });
                        }}
                      >
                        <Trash2 size={15} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="mt-2 text-[14px] text-muted">Nothing logged yet. Start with today, or add earlier days from a file.</p>
          )}
        </section>
        <p className="text-[13px] leading-relaxed text-muted">
          Tip: a min/max thermometer shows the lowest and highest temperature since you last reset it. Read it at the same time each day, write the numbers
          here, then press reset. Keep it in shade about 5 ft up with air moving past it.
        </p>
      </main>
    </div>
  );
}
