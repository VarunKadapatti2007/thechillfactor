"use client";

import { MapPin, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useStore } from "@/lib/store";

interface Hit {
  label: string;
  lat: number;
  lon: number;
}

const LATLON = /^\s*(-?\d{1,2}(?:\.\d+)?)\s*[,\s]\s*(-?\d{1,3}(?:\.\d+)?)\s*$/;

export function parseLatLon(q: string): Hit | null {
  const m = q.match(LATLON);
  if (!m) return null;
  const lat = Number(m[1]);
  const lon = Number(m[2]);
  if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
  return { label: `${lat.toFixed(4)}, ${lon.toFixed(4)}`, lat, lon };
}

export default function SearchBox() {
  const { d } = useStore();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    const ll = parseLatLon(q);
    if (ll) {
      setHits([ll]);
      return;
    }
    if (q.trim().length < 3) {
      setHits([]);
      return;
    }
    timer.current = setTimeout(async () => {
      try {
        const u = `https://photon.komoot.io/api/?q=${encodeURIComponent(q)}&limit=5&lang=en&bbox=-124.6,32.4,-114.0,42.1`;
        const r = await fetch(u);
        const js = await r.json();
        setHits(
          (js.features ?? []).map((f: { geometry: { coordinates: [number, number] }; properties: Record<string, string> }) => ({
            label: [f.properties.name, f.properties.city, f.properties.county, f.properties.state].filter(Boolean).filter((v, i, a) => a.indexOf(v) === i).join(", "),
            lon: f.geometry.coordinates[0],
            lat: f.geometry.coordinates[1],
          })),
        );
      } catch {
        setHits([]);
      }
    }, 300);
  }, [q]);

  function choose(h: Hit) {
    d({ type: "pin", pin: { lat: h.lat, lon: h.lon, label: h.label }, fly: true });
    setOpen(false);
    setQ(h.label);
  }

  return (
    <div className="relative w-full max-w-[320px]">
      <label htmlFor="place-search" className="sr-only">
        Search a place or paste lat, lon
      </label>
      <Search size={16} aria-hidden className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
      <input
        id="place-search"
        role="combobox"
        aria-expanded={open && hits.length > 0}
        aria-controls="place-results"
        aria-autocomplete="list"
        autoComplete="off"
        value={q}
        placeholder="Search a place or paste lat, lon"
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
          setActive(0);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") setActive((a) => Math.min(a + 1, hits.length - 1));
          if (e.key === "ArrowUp") setActive((a) => Math.max(a - 1, 0));
          if (e.key === "Enter" && hits[active]) choose(hits[active]);
          if (e.key === "Escape") setOpen(false);
        }}
        className="h-9 w-full rounded-[8px] border border-line bg-bg pl-8 pr-2 text-[14px] text-ink placeholder:text-muted focus:bg-surface"
      />
      {open && hits.length > 0 && (
        <ul
          id="place-results"
          role="listbox"
          className="absolute left-0 right-0 top-10 z-50 overflow-hidden rounded-[8px] border border-line bg-surface shadow-lg"
        >
          {hits.map((h, i) => (
            <li key={`${h.lat},${h.lon},${i}`} role="option" aria-selected={i === active}>
              <button
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => choose(h)}
                className={`flex w-full items-center gap-2 px-3 py-2 text-left text-[14px] ${i === active ? "bg-bg" : ""}`}
              >
                <MapPin size={14} aria-hidden className="shrink-0 text-muted" />
                <span className="truncate">{h.label}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
