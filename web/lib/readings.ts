// Parse a grower's thermometer or logger file into readings for POST /api/orchard.
//
// Two shapes are accepted:
// - daily: one row per day with a low and a high (a min/max thermometer, or a weather app export)
// - logger: date-time and temperature rows at any interval (the server averages them to hours)
// Dates may be ISO (2026-11-05 13:00) or US (11/5/2026 1:00 PM); a separate time column is joined.

import type { Readings } from "./types";

interface Stamp {
  date: string; // YYYY-MM-DD
  time: string | null; // HH:MM
}

const pad = (n: number) => String(n).padStart(2, "0");

export function parseStamp(raw: string): Stamp | null {
  const v = raw.trim().replace(/^"|"$/g, "");
  let m = v.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::\d{2}(?:\.\d+)?)?\s*(AM|PM)?)?/i);
  let y: number, mo: number, d: number, hh: number | null = null, mm = 0, ap: string | undefined;
  if (m) {
    [y, mo, d] = [+m[1], +m[2], +m[3]];
    if (m[4] !== undefined) [hh, mm, ap] = [+m[4], +m[5], m[6]];
  } else {
    m = v.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2,4})(?:[ T,]+(\d{1,2}):(\d{2})(?::\d{2})?\s*(AM|PM)?)?/i);
    if (!m) return null;
    [mo, d, y] = [+m[1], +m[2], +m[3]];
    if (y < 100) y += 2000;
    if (m[4] !== undefined) [hh, mm, ap] = [+m[4], +m[5], m[6]];
  }
  if (hh !== null && ap) {
    if (/pm/i.test(ap) && hh < 12) hh += 12;
    if (/am/i.test(ap) && hh === 12) hh = 0;
  }
  if (mo < 1 || mo > 12 || d < 1 || d > 31) return null;
  return { date: `${y}-${pad(mo)}-${pad(d)}`, time: hh === null ? null : `${pad(hh)}:${pad(mm)}` };
}

function joinTime(st: Stamp | null, t: string | undefined): Stamp | null {
  if (!st || !t) return st;
  const m = t.trim().match(/^(\d{1,2}):(\d{2})(?::\d{2})?\s*(AM|PM)?$/i);
  if (!m) return st;
  let hh = +m[1];
  if (m[3] && /pm/i.test(m[3]) && hh < 12) hh += 12;
  if (m[3] && /am/i.test(m[3]) && hh === 12) hh = 0;
  return { ...st, time: `${pad(hh)}:${m[2]}` };
}

const num = (s: string | undefined) => {
  if (s === undefined) return NaN;
  const v = s.trim().replace(/^"|"$/g, "").replace(/[°FfCc]+$/, "");
  return v === "" ? NaN : Number(v);
};

function guessUnit(header: string, values: number[]): "F" | "C" {
  if (/°\s*C|\(C\)|_c\b|celsius|degc/i.test(header)) return "C";
  if (/°\s*F|\(F\)|_f\b|fahrenheit|degf/i.test(header)) return "F";
  const v = [...values].sort((a, b) => a - b);
  const med = v[Math.floor(v.length / 2)] ?? 0;
  return med > 30 ? "F" : "C"; // Central Valley winter: lows/highs mostly 0-20 °C, 32-70 °F
}

export function parseReadings(text: string, source: string): Readings | { error: string } {
  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter((l) => l && !l.startsWith("#"));
  if (lines.length < 3) return { error: "The file has fewer than 3 rows." };
  const first = lines[0];
  const delim = [",", ";", "\t"].sort((a, b) => first.split(b).length - first.split(a).length)[0];
  const rows = lines.map((l) => l.split(delim).map((c) => c.trim().replace(/^"|"$/g, "")));
  const hasHeader = rows[0].some((c) => c !== "" && isNaN(Number(c)) && !parseStamp(c));
  const header = hasHeader ? rows[0].map((c) => c.toLowerCase()) : [];
  const body = hasHeader ? rows.slice(1) : rows;
  const headerText = hasHeader ? rows[0].join(" ") : "";

  // Column roles from the header, else by position.
  const find = (re: RegExp, not?: RegExp) => header.findIndex((h) => re.test(h) && !(not && not.test(h)));
  let iDate = hasHeader ? find(/date|day|timestamp|time/) : 0;
  const iTime = hasHeader ? header.findIndex((h, i) => i !== iDate && /^time\b|hour/.test(h)) : -1;
  let iLow = hasHeader ? find(/min|low/) : -1;
  let iHigh = hasHeader ? find(/max|high/) : -1;
  let iTemp = hasHeader ? find(/temp|air|°|deg|reading|value/, /min|max|low|high|dew|soil|leaf/) : -1;
  if (iDate < 0) iDate = 0;
  if (!hasHeader) {
    const ncol = body[0].length;
    if (ncol >= 3) [iLow, iHigh] = [1, 2];
    else if (ncol === 2) iTemp = 1;
  }

  const stamps = body.map((r) => joinTime(parseStamp(r[iDate] ?? ""), iTime >= 0 ? r[iTime] : undefined));
  const okRows = stamps.filter(Boolean).length;
  if (okRows < Math.max(3, body.length * 0.8)) return { error: "Couldn't read the dates. Use dates like 2026-11-05 or 11/5/2026." };

  if (iLow >= 0 && iHigh >= 0) {
    const byDay = new Map<string, [number, number]>();
    body.forEach((r, i) => {
      const st = stamps[i];
      const a = num(r[iLow]), b = num(r[iHigh]);
      if (!st || !isFinite(a) || !isFinite(b)) return;
      byDay.set(st.date, [Math.min(a, b), Math.max(a, b)]);
    });
    const dates = [...byDay.keys()].sort();
    if (dates.length < 3) return { error: "Need at least 3 days with both a low and a high." };
    const lows = dates.map((k) => byDay.get(k)![0]);
    const highs = dates.map((k) => byDay.get(k)![1]);
    const unit = guessUnit(headerText, [...lows, ...highs]);
    return {
      kind: "daily", unit, dates, lows, highs, first: dates[0], last: dates[dates.length - 1], rows: dates.length, source,
      sig: `daily:${dates.length}:${dates[0]}:${dates[dates.length - 1]}:${source}:${unit}`,
    };
  }
  if (iTemp >= 0) {
    const pts: [string, number][] = [];
    body.forEach((r, i) => {
      const st = stamps[i];
      const t = num(r[iTemp]);
      if (st && st.time && isFinite(t)) pts.push([`${st.date} ${st.time}`, t]);
    });
    if (pts.length < 72) {
      return { error: "A logger file needs a date-time and a temperature on each row (at least 3 days). For a min/max thermometer, use columns: date, low, high." };
    }
    pts.sort((a, b) => (a[0] < b[0] ? -1 : 1));
    const times = pts.map((p) => p[0]);
    const temps = pts.map((p) => p[1]);
    const unit = guessUnit(headerText, temps);
    return {
      kind: "hourly", unit, times, temps, first: times[0].slice(0, 10), last: times[times.length - 1].slice(0, 10), rows: pts.length, source,
      sig: `hourly:${pts.length}:${times[0]}:${times[times.length - 1]}:${source}:${unit}`,
    };
  }
  return { error: "Couldn't find the temperature columns. Use: date, low, high (one row per day) or date-time, temperature (a logger)." };
}

export function withUnit(r: Readings, unit: "F" | "C"): Readings {
  return { ...r, unit, sig: r.sig.replace(/:[FC]$/, `:${unit}`) };
}
