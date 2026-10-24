// Day-of-season helpers. Seasons are labeled "2014-2015" and start Sept 1 (or Nov 1).
import type { CpPoint, StartOpt } from "./types";
import { daysBetween } from "./format";

export function seasonStartYear(label: string): number {
  return Number(label.split("-")[0]);
}

export function seasonStartDate(label: string, start: StartOpt = "sep1"): string {
  const y = seasonStartYear(label);
  return start === "sep1" ? `${y}-09-01` : `${y}-11-01`;
}

export function dayOfSeason(label: string, iso: string): number {
  return daysBetween(`${seasonStartYear(label)}-09-01`, iso);
}

// Map a past season's series onto day-of-season indices.
export function byDos(label: string, series: CpPoint[]): Map<number, number> {
  const m = new Map<number, number>();
  for (const p of series) m.set(dayOfSeason(label, p.date), p.cp);
  return m;
}
