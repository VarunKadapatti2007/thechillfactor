"use client";

import { useEffect, useRef } from "react";
import { useStore, type Tab } from "./store";

const TABS: Tab[] = ["winter", "history", "heat", "accuracy"];

// Shareable links: ?lat=..&lon=..&crop=..&variety=..&tab=..&replay=2014-2015
export function useUrlState() {
  const { s, d } = useStore();
  const booted = useRef(false);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const lat = Number(q.get("lat"));
    const lon = Number(q.get("lon"));
    if (q.get("lat") && q.get("lon") && Number.isFinite(lat) && Number.isFinite(lon)) {
      d({ type: "pin", pin: { lat, lon, label: q.get("label") ?? undefined }, fly: true });
      d({ type: "coach", step: null });
    }
    const crop = q.get("crop");
    const variety = q.get("variety");
    if (crop && variety) d({ type: "crop", crop, variety });
    // A shared link with a place and a crop runs the analysis straight away.
    if (q.get("lat") && q.get("lon") && Number.isFinite(lat) && Number.isFinite(lon) && crop && variety) {
      d({ type: "run", spec: { lat, lon, label: q.get("label") ?? undefined, crop, variety, by: null, start: "sep1", climate: null, samplePts: null, areaLabel: null } });
    }
    const tab = q.get("tab") as Tab | null;
    if (tab && TABS.includes(tab)) d({ type: "tab", tab });
    const replay = q.get("replay");
    if (replay && /^\d{4}-\d{4}$/.test(replay)) d({ type: "replay", season: replay });
    if (q.get("units") === "C") d({ type: "units", units: "C" });
    booted.current = true;
  }, [d]);

  useEffect(() => {
    if (!booted.current) return;
    const q = new URLSearchParams();
    // The link describes the last analysis that was run.
    if (s.run) {
      q.set("lat", s.run.lat.toFixed(4));
      q.set("lon", s.run.lon.toFixed(4));
      if (s.run.label) q.set("label", s.run.label);
      q.set("crop", s.run.crop);
      q.set("variety", s.run.variety);
    }
    if (s.tab !== "winter") q.set("tab", s.tab);
    if (s.replaySeason) q.set("replay", s.replaySeason);
    if (s.units === "C") q.set("units", "C");
    const url = q.toString() ? `?${q}` : window.location.pathname;
    window.history.replaceState(null, "", url);
  }, [s.run, s.tab, s.replaySeason, s.units]);
}
