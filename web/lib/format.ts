// Display helpers. Copy rules (BUILD.md 6.8): ranges as "54 to 58", odds as "7 in 10".

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function parseISO(d: string): Date {
  const [y, m, day] = d.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, day));
}

export function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function addDays(iso: string, n: number): string {
  const d = parseISO(iso);
  d.setUTCDate(d.getUTCDate() + n);
  return isoDate(d);
}

export function daysBetween(a: string, b: string): number {
  return Math.round((parseISO(b).getTime() - parseISO(a).getTime()) / 86400000);
}

export function shortDate(iso: string): string {
  const d = parseISO(iso);
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}`;
}

export function longDate(iso: string): string {
  const d = parseISO(iso);
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}`;
}

export function mmddLabel(mmdd: string): string {
  const [m, d] = mmdd.split("-").map(Number);
  return `${MONTHS[m - 1]} ${d}`;
}

export function cp(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "Not available";
  return v.toFixed(digits);
}

export function range(lo: number, hi: number): string {
  return lo === hi ? `${fmtNum(lo)}` : `${fmtNum(lo)} to ${fmtNum(hi)}`;
}

export function fmtNum(v: number, digits = 0): string {
  return Number.isInteger(v) && digits === 0 ? String(v) : v.toFixed(digits);
}

// "7 in 10". Rounds the probability to the nearest tenth.
export function inTen(p: number | null | undefined): string {
  if (p === null || p === undefined || Number.isNaN(p)) return "Not available";
  return `${Math.round(p * 10)} in 10`;
}

export function seasonShort(label: string): string {
  // "2014-2015" -> "2014-15"
  const [a, b] = label.split("-");
  return b ? `${a}-${b.slice(2)}` : label;
}

export type Units = "F" | "C";

export function gddUnits(v: number, u: Units): number {
  return u === "F" ? v * 1.8 : v;
}

export function degDayLabel(u: Units): string {
  return u === "F" ? "°F-days" : "°C-days";
}

export function elev(m: number | null | undefined, u: Units): string {
  if (m === null || m === undefined) return "Not available";
  return u === "F" ? `${Math.round(m * 3.28084)} ft` : `${Math.round(m)} m`;
}

export function km(v: number | null | undefined, u: Units): string {
  if (v === null || v === undefined) return "Not available";
  return u === "F" ? `${(v * 0.621371).toFixed(v < 16 ? 1 : 0)} mi` : `${v.toFixed(v < 10 ? 1 : 0)} km`;
}
