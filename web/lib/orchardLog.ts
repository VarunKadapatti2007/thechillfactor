// The grower's own readings: a daily log kept on this device, and files read by the server.
//
// The log lives in this browser's storage (no account needed). Uploaded files of any layout go to
// POST /api/readings/parse, which reads every value in code (an AI reader only names the columns
// when the layout is unusual).

import { API_BASE } from "./api";
import type { Readings } from "./types";

export interface LogEntry {
  low: number;
  high: number;
}

export interface OrchardLog {
  unit: "F" | "C";
  entries: Record<string, LogEntry>; // YYYY-MM-DD -> low/high
}

const KEY = "chillprint.orchardLog.v1";

export function loadLog(): OrchardLog {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (raw) {
      const v = JSON.parse(raw) as OrchardLog;
      if (v && typeof v.entries === "object") return { unit: v.unit === "C" ? "C" : "F", entries: v.entries };
    }
  } catch {}
  return { unit: "F", entries: {} };
}

export function saveLog(log: OrchardLog): boolean {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(log));
    return true;
  } catch {
    return false;
  }
}

export function logReadings(log: OrchardLog): Readings | null {
  const dates = Object.keys(log.entries).sort();
  if (dates.length < 3) return null;
  const lows = dates.map((d) => log.entries[d].low);
  const highs = dates.map((d) => log.entries[d].high);
  const sum = lows.reduce((a, b) => a + b, 0) + highs.reduce((a, b) => a + b, 0);
  return {
    kind: "daily",
    unit: log.unit,
    dates,
    lows,
    highs,
    first: dates[0],
    last: dates[dates.length - 1],
    rows: dates.length,
    source: "My orchard log",
    sig: `log:${dates.length}:${dates[0]}:${dates[dates.length - 1]}:${sum.toFixed(1)}:${log.unit}`,
  };
}

export function logToCsv(log: OrchardLog): string {
  const u = log.unit;
  const rows = Object.keys(log.entries)
    .sort()
    .map((d) => `${d},${log.entries[d].low},${log.entries[d].high}`);
  return [`date,low_${u.toLowerCase()},high_${u.toLowerCase()}`, ...rows].join("\n") + "\n";
}

// --- files of any layout ---------------------------------------------------------------------

export interface ParsedFile {
  kind: "daily" | "hourly";
  unit: "F" | "C";
  dates?: string[];
  lows?: number[];
  highs?: number[];
  times?: string[];
  temps?: number[];
  first: string;
  last: string;
  rows: number;
  skipped_rows: number;
  method: "rules" | "ai";
  explanation: string;
  steps: string[];
  preview: { when: string; low?: number; high?: number; temp?: number }[];
  columns: Record<string, string | null>;
}

function toBase64(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

export async function parseFile(file: File): Promise<ParsedFile> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 120000);
  try {
    const r = await fetch(`${API_BASE}/api/readings/parse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: file.name, content_b64: toBase64(await file.arrayBuffer()) }),
      signal: ctl.signal,
    });
    if (!r.ok) {
      let msg = `${r.status}`;
      try {
        msg = ((await r.json()) as { detail?: string }).detail ?? msg;
      } catch {}
      throw new Error(msg);
    }
    return (await r.json()) as ParsedFile;
  } finally {
    clearTimeout(timer);
  }
}

export function fileReadings(p: ParsedFile, source: string): Readings {
  return {
    kind: p.kind,
    unit: p.unit,
    ...(p.kind === "daily" ? { dates: p.dates, lows: p.lows, highs: p.highs } : { times: p.times, temps: p.temps }),
    first: p.first,
    last: p.last,
    rows: p.rows,
    source,
    sig: `${p.kind}:${p.rows}:${p.first}:${p.last}:${source}:${p.unit}`,
  };
}
