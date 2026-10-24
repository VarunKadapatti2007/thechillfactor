"use client";

import { ChevronDown, FileUp, Thermometer, X } from "lucide-react";
import { useRef, useState } from "react";
import { useData } from "@/lib/data";
import { longDate } from "@/lib/format";
import { parseReadings, withUnit } from "@/lib/readings";
import { useStore } from "@/lib/store";
import { Button, cn } from "../ui";
import StepCard from "./StepCard";

// A real in-orchard record: Wildeye "CA Pistachio # 5 - Terra Bella" via the FNRIC API, winter 2025-26.
const SAMPLE = {
  file: "/samples/terra-bella-pistachio-2025-26.csv",
  name: "Pistachio orchard sensor, Terra Bella (sample)",
  lat: 35.9599,
  lon: -119.0664,
};

export default function StepReadings({ n }: { n: number }) {
  const { s, d } = useStore();
  const { validation } = useData();
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const rd = s.readings;

  const test = validation.data?.orchard_readings?.tests?.wildeye_orchard;
  const before = test?.scenarios?.station_only?.mae_cp;
  const after = test?.scenarios?.readings_from_sep1?.mae_cp;
  const late = test?.scenarios?.readings_from_jan1?.mae_cp;

  async function load(text: string, source: string) {
    const r = parseReadings(text, source);
    if ("error" in r) {
      setErr(r.error);
      return null;
    }
    setErr(null);
    d({ type: "readings", readings: r });
    return r;
  }

  async function onFile(f: File | undefined) {
    if (!f) return;
    if (f.size > 8_000_000) {
      setErr("That file is too large. Export daily lows and highs, or hourly logger data.");
      return;
    }
    await load(await f.text(), f.name);
  }

  async function sample() {
    try {
      const text = await (await fetch(SAMPLE.file)).text();
      const r = await load(text, "sample");
      if (r) {
        d({ type: "pin", pin: { lat: SAMPLE.lat, lon: SAMPLE.lon, label: SAMPLE.name }, fly: true });
        d({ type: "crop", crop: "pistachio", variety: "kerman" });
      }
    } catch {
      setErr("Couldn't load the example.");
    }
  }

  return (
    <StepCard n={n} title="Your orchard's own readings (optional)" done={!!rd}>
      <p className="text-[13px] leading-relaxed">
        Have a min/max thermometer or a temperature logger in the orchard? Add its readings and chill is counted from your orchard&apos;s own
        temperatures.
        {before !== undefined && after !== undefined && (
          <>
            {" "}
            At {test!.n_sites} pistachio orchards, this cut the typical miss from <span className="num font-semibold">{before.toFixed(1)}</span> to{" "}
            <span className="num font-semibold">{after.toFixed(1)}</span> chill portions
            {late !== undefined && <> (readings starting Jan 1 still brought it to {late.toFixed(1)})</>}.
          </>
        )}
      </p>

      {rd ? (
        <div className="mt-3 rounded-[10px] border border-line bg-bg p-2.5 text-[13px]" role="status">
          <div className="flex items-start gap-2">
            <Thermometer size={16} aria-hidden className="mt-0.5 shrink-0 text-chill" />
            <div className="min-w-0 flex-1">
              <div className="font-medium">
                {rd.kind === "daily" ? `${rd.rows} days of lows and highs` : `${rd.rows.toLocaleString()} logger readings`}
              </div>
              <div className="text-muted">
                {longDate(rd.first)} to {longDate(rd.last)} · {rd.source === "sample" ? SAMPLE.name : rd.source}
              </div>
            </div>
            <button aria-label="Remove readings" className="rounded p-1 text-muted hover:bg-surface" onClick={() => d({ type: "readings", readings: null })}>
              <X size={15} />
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
            <span className="text-[11px] text-muted">(we guessed; fix it if wrong)</span>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button className="h-9 text-[13px]" onClick={() => fileRef.current?.click()}>
            <FileUp size={15} aria-hidden /> Add a file (CSV)
          </Button>
          <Button className="h-9 text-[13px]" onClick={sample}>
            Try a real example
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.txt,text/csv,text/plain"
            className="sr-only"
            aria-label="Thermometer or logger file"
            onChange={(e) => {
              onFile(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
        </div>
      )}
      {err && (
        <p className="mt-2 text-[12px] text-red-700" role="alert">
          {err}
        </p>
      )}

      <button className="mt-2 flex items-center gap-1 text-[12px] text-muted underline-offset-2 hover:underline" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        What file works?
        <ChevronDown size={13} aria-hidden className={cn("transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <ul className="mt-1.5 list-disc space-y-1 pl-5 text-[12px] leading-relaxed text-muted">
          <li>A min/max thermometer: one row per day with the date, the low and the high (columns: date, low, high).</li>
          <li>A temperature logger export: date and time, temperature, at any interval. We average to hours.</li>
          <li>°F or °C both work. Missing days are fine: gaps of up to 4 days are filled in, longer gaps and days before your readings start use the station estimate.</li>
          <li>
            Put the thermometer in shade about 5 ft up, with air moving past it (a radiation shield or a shaded box with vents). In the sun it reads too warm and
            undercounts chill.
          </li>
          <li>Your file is used only to compute this answer. We don&apos;t keep a copy of it.</li>
        </ul>
      )}
    </StepCard>
  );
}
