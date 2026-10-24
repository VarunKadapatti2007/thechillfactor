"use client";

import * as Popover from "@radix-ui/react-popover";
import { motion, useReducedMotion } from "framer-motion";
import { Layers } from "lucide-react";
import { setWorkerUrl, type StyleSpecification } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import Map, { Layer, Marker, NavigationControl, Popup, Source, type MapLayerMouseEvent, type MapRef } from "react-map-gl/maplibre";
import { useData } from "@/lib/data";
import { useStore, type GridLayer } from "@/lib/store";
import { cn } from "./ui";

const AERIAL_TILES = "https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}";

// The bundled worker URL breaks under Turbopack; serve the worker from public/ (copied on postinstall).
setWorkerUrl("/maplibre-gl-worker.mjs");

const ONLINE_STYLE = "https://tiles.openfreemap.org/styles/positron";
// Offline fallback: a pre-rendered Central Valley image (scripts/render_basemap.mjs).
const OFFLINE_BOUNDS: [[number, number], [number, number], [number, number], [number, number]] = [
  [-123.6, 41.0], [-117.6, 41.0], [-117.6, 34.4], [-123.6, 34.4],
];
const OFFLINE_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    base: { type: "image", url: "/demo/basemap.png", coordinates: OFFLINE_BOUNDS },
    credit: { type: "geojson", data: { type: "FeatureCollection", features: [] }, attribution: "Offline map: OpenFreeMap © OpenMapTiles © OpenStreetMap contributors" },
  },
  layers: [
    { id: "bg", type: "background", paint: { "background-color": "#f2f1ed" } },
    { id: "base", type: "raster", source: "base", paint: { "raster-opacity": 1 } },
  ],
};

const GRID_STOPS: [number, string][] = [
  [20, "#c8742b"],
  [35, "#e3b26b"],
  [50, "#d9e4dd"],
  [65, "#7fb0c9"],
  [80, "#3b7ea1"],
];

export default function MapView() {
  const { s, d } = useStore();
  const { stations, grid, point, validation } = useData();
  const ref = useRef<MapRef>(null);
  const reduce = useReducedMotion();
  const [style, setStyle] = useState<string | StyleSpecification | null>(null);
  const [hover, setHover] = useState<{ lon: number; lat: number; html: string } | null>(null);

  // Fall back to the offline image basemap if the online style can't load.
  useEffect(() => {
    let cancelled = false;
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), 8000);
    fetch(ONLINE_STYLE, { signal: ctl.signal })
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        if (!cancelled) setStyle(ONLINE_STYLE);
      })
      .catch(() => {
        if (!cancelled) setStyle(OFFLINE_STYLE);
      })
      .finally(() => clearTimeout(t));
    return () => {
      cancelled = true;
      ctl.abort();
    };
  }, []);

  useEffect(() => {
    if (s.flyTo && ref.current) {
      const z = style === OFFLINE_STYLE ? Math.min(s.flyTo.zoom, 9) : s.flyTo.zoom;
      ref.current.flyTo({ center: [s.flyTo.lon, s.flyTo.lat], zoom: z, duration: reduce ? 0 : 1600, essential: true });
    }
  }, [s.flyTo, reduce, style]);

  const stationGeo = useMemo(() => {
    const list = stations.data?.stations ?? [];
    return {
      type: "FeatureCollection" as const,
      features: list.map((st) => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [st.lon, st.lat] },
        properties: { id: st.id, name: st.name, network: st.network, active: st.active, closed: st.closed ?? "" },
      })),
    };
  }, [stations.data]);

  const durham = stations.data?.stations.find((x) => x.id === "CIMIS-12");

  const errGeo = useMemo(() => {
    const rows = validation.data?.by_station ?? [];
    return {
      type: "FeatureCollection" as const,
      features: rows
        .filter((r) => r.e4_mae !== null || r.e3_mae !== null)
        .map((r) => ({
          type: "Feature" as const,
          geometry: { type: "Point" as const, coordinates: [r.lon, r.lat] },
          properties: { name: r.name, err: r.e4_mae ?? r.e3_mae ?? 0, e0: r.e0_mae ?? 0 },
        })),
    };
  }, [validation.data]);

  const showErrors = s.tab === "accuracy" && errGeo.features.length > 0;

  function onClick(e: MapLayerMouseEvent) {
    if (s.drawMode === "outline") {
      if (!s.outlineClosed) d({ type: "outlineAdd", lon: e.lngLat.lng, lat: e.lngLat.lat });
      return;
    }
    // Zoom in to the farm, so the grower can see their fields to outline them.
    d({ type: "pin", pin: { lat: e.lngLat.lat, lon: e.lngLat.lng }, fly: true });
  }

  const shapeGeo = useMemo(() => {
    const features: GeoJSON.Feature[] = [];
    if (s.drawMode === "outline" && s.outline.length) {
      const ring = s.outlineClosed ? [...s.outline, s.outline[0]] : s.outline;
      if (s.outlineClosed) features.push({ type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [ring] } });
      else if (ring.length > 1) features.push({ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: ring } });
      for (const v of s.outline) features.push({ type: "Feature", properties: { vertex: 1 }, geometry: { type: "Point", coordinates: v } });
    }
    return { type: "FeatureCollection" as const, features };
  }, [s.drawMode, s.outline, s.outlineClosed]);
  const showPin = s.pin && (s.drawMode !== "outline" || s.outlineClosed);

  function onMove(e: MapLayerMouseEvent) {
    const f = e.features?.[0];
    if (!f) {
      setHover(null);
      return;
    }
    const p = f.properties as Record<string, string | boolean | number>;
    const coords = (f.geometry as GeoJSON.Point).coordinates;
    let html = "";
    if (f.layer.id.startsWith("st-")) {
      const status = p.active === true || p.active === "true" ? "Active" : p.closed ? `Closed ${p.closed}` : "Inactive";
      html = `${p.name} · ${p.network} · ${status}`;
    } else if (f.layer.id === "err") {
      html = `${p.name} · our miss ${Number(p.err).toFixed(1)} CP · nearest station ${Number(p.e0).toFixed(1)} CP`;
    } else if (f.layer.id === "grid") {
      html = `${Number(p.value).toFixed(0)} CP`;
    }
    setHover({ lon: coords[0], lat: coords[1], html });
  }

  const pointLoading = point.loading;

  if (!style) return <div className="skeleton h-full w-full rounded-none" aria-label="Loading map" />;

  return (
    <div className="relative h-full w-full">
      <Map
        ref={ref}
        initialViewState={{ latitude: 37.3, longitude: -120.3, zoom: 6.1 }}
        mapStyle={style}
        style={{ width: "100%", height: "100%" }}
        onClick={onClick}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
        interactiveLayerIds={["st-cimis", "st-wildeye", ...(showErrors ? ["err"] : []), ...(s.layers.grid !== "off" ? ["grid"] : [])]}
        cursor={s.drawMode === "outline" && !s.outlineClosed ? "copy" : "crosshair"}
        attributionControl={{ compact: true }}
        maxZoom={style === OFFLINE_STYLE ? 9 : 17}
        minZoom={4}
      >
        <NavigationControl position="bottom-right" showCompass={false} />

        {/* Aerial imagery when zoomed in, so a grower can see their fields to outline the farm (USGS, public domain). */}
        {style !== OFFLINE_STYLE && (
          <Source id="aerial" type="raster" tiles={[AERIAL_TILES]} tileSize={256} maxzoom={16} attribution="Imagery: USGS The National Map">
            <Layer id="aerial" type="raster" minzoom={11} paint={{ "raster-opacity": ["interpolate", ["linear"], ["zoom"], 11, 0, 12.5, 1] }} />
          </Source>
        )}

        {grid.data && s.layers.grid !== "off" && (
          <Source id="grid" type="geojson" data={grid.data as unknown as GeoJSON.FeatureCollection}>
            <Layer
              id="grid"
              type="circle"
              paint={{
                "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 3, 8, 7, 11, 16],
                "circle-color": ["interpolate", ["linear"], ["get", "value"], ...GRID_STOPS.flat()] as never,
                "circle-opacity": 0.75,
              }}
            />
          </Source>
        )}

        <Source id="stations" type="geojson" data={stationGeo}>
          <Layer
            id="st-cimis"
            type="circle"
            filter={["==", ["get", "network"], "CIMIS"]}
            layout={{ visibility: s.layers.cimis ? "visible" : "none" }}
            paint={{
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 3, 10, 6],
              "circle-color": ["case", ["get", "active"], "#3b7ea1", "#ffffff"],
              "circle-stroke-color": "#3b7ea1",
              "circle-stroke-width": 1.5,
            }}
          />
          <Layer
            id="st-wildeye"
            type="circle"
            filter={["==", ["get", "network"], "Wildeye"]}
            layout={{ visibility: s.layers.wildeye ? "visible" : "none" }}
            paint={{
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 3, 10, 6],
              "circle-color": "#2e6a4f",
              "circle-stroke-color": "#ffffff",
              "circle-stroke-width": 1,
            }}
          />
        </Source>

        {showErrors && (
          <Source id="err" type="geojson" data={errGeo}>
            <Layer
              id="err"
              type="circle"
              paint={{
                "circle-radius": ["interpolate", ["linear"], ["get", "err"], 0, 4, 4, 8, 10, 14],
                "circle-color": ["interpolate", ["linear"], ["get", "err"], 1, "#2f855a", 3, "#b7791f", 6, "#c53030"],
                "circle-opacity": 0.8,
                "circle-stroke-color": "#ffffff",
                "circle-stroke-width": 1,
              }}
            />
          </Source>
        )}

        <Source id="shape" type="geojson" data={shapeGeo}>
          <Layer id="shape-fill" type="fill" filter={["==", ["geometry-type"], "Polygon"]} paint={{ "fill-color": "#2e6a4f", "fill-opacity": 0.12 }} />
          <Layer id="shape-line" type="line" filter={["!=", ["geometry-type"], "Point"]} paint={{ "line-color": "#2e6a4f", "line-width": 2, "line-dasharray": [2, 1] }} />
          <Layer id="shape-vertex" type="circle" filter={["==", ["geometry-type"], "Point"]} paint={{ "circle-radius": 5, "circle-color": "#ffffff", "circle-stroke-color": "#2e6a4f", "circle-stroke-width": 2 }} />
        </Source>

        {durham && s.layers.cimis && (
          <Marker latitude={durham.lat} longitude={durham.lon} anchor="left" offset={[8, 0]}>
            <span className="pointer-events-none whitespace-nowrap rounded bg-surface/90 px-1.5 py-0.5 text-[11px] font-medium text-ink shadow-sm">
              Durham · Closed Jul 2025
            </span>
          </Marker>
        )}

        {showPin && s.pin && (
          <Marker
            latitude={s.pin.lat}
            longitude={s.pin.lon}
            anchor="bottom"
            draggable
            onDragEnd={(e) => d({ type: "pin", pin: { lat: e.lngLat.lat, lon: e.lngLat.lng } })}
          >
            <motion.div
              key={`${s.pin.lat},${s.pin.lon}`}
              initial={reduce ? false : { y: -36, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ type: "spring", stiffness: 420, damping: 18 }}
              className="relative flex flex-col items-center"
              role="img"
              aria-label="Orchard pin"
            >
              {pointLoading && <span className="pin-pulse absolute bottom-0 h-5 w-5 rounded-full bg-brand/40" />}
              <svg width="28" height="36" viewBox="0 0 28 36" aria-hidden>
                <path d="M14 35s11-11.2 11-20A11 11 0 0 0 3 15c0 8.8 11 20 11 20z" fill="#2e6a4f" stroke="#fff" strokeWidth="2" />
                <circle cx="14" cy="15" r="4.2" fill="#fff" />
              </svg>
            </motion.div>
          </Marker>
        )}

        {hover && (
          <Popup longitude={hover.lon} latitude={hover.lat} closeButton={false} closeOnClick={false} offset={10} className="cp-popup">
            <span className="text-[12px]">{hover.html}</span>
          </Popup>
        )}
      </Map>

      <LayerMenu />
      <Legend showErrors={showErrors} grid={s.layers.grid} />
    </div>
  );
}

function LayerMenu() {
  const { s, d } = useStore();
  const opts: { v: GridLayer; label: string }[] = [
    { v: "off", label: "No grid" },
    { v: "safe_chill", label: "Safe winter chill" },
    { v: "chill_so_far", label: "Chill so far" },
  ];
  return (
    <Popover.Root>
      <Popover.Trigger
        aria-label="Map layers"
        className="absolute right-3 top-3 z-10 inline-flex h-9 items-center gap-1.5 rounded-[8px] border border-line bg-surface px-2.5 text-[14px] shadow-sm hover:bg-bg"
      >
        <Layers size={16} aria-hidden /> <span className="hidden sm:inline">Layers</span>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align="end" sideOffset={6} className="z-[60] w-56 rounded-[8px] border border-line bg-surface p-3 text-[14px] shadow-lg">
          <fieldset className="space-y-2">
            <legend className="mb-1 text-[12px] font-semibold text-muted">Stations</legend>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={s.layers.cimis} onChange={(e) => d({ type: "layers", layers: { cimis: e.target.checked } })} />
              CIMIS stations
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={s.layers.wildeye} onChange={(e) => d({ type: "layers", layers: { wildeye: e.target.checked } })} />
              Wildeye in-orchard stations
            </label>
          </fieldset>
          <fieldset className="mt-3 space-y-2">
            <legend className="mb-1 text-[12px] font-semibold text-muted">Grid</legend>
            {opts.map((o) => (
              <label key={o.v} className="flex items-center gap-2">
                <input type="radio" name="grid" checked={s.layers.grid === o.v} onChange={() => d({ type: "layers", layers: { grid: o.v } })} />
                {o.label}
              </label>
            ))}
          </fieldset>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

function Legend({ showErrors, grid }: { showErrors: boolean; grid: GridLayer }) {
  return (
    <div className="pointer-events-none absolute bottom-8 left-3 z-10 hidden space-y-1 rounded-[8px] border border-line bg-surface/95 px-2.5 py-2 text-[11px] text-ink shadow-sm sm:block">
      <div className="flex items-center gap-1.5">
        <span className="inline-block h-2.5 w-2.5 rounded-full border-[1.5px] border-chill bg-chill" /> CIMIS active
        <span className="ml-2 inline-block h-2.5 w-2.5 rounded-full border-[1.5px] border-chill bg-white" /> closed
        <span className="ml-2 inline-block h-2.5 w-2.5 rounded-full bg-brand" /> Wildeye
      </div>
      {grid !== "off" && (
        <div>
          <div className="mb-0.5 font-medium">{grid === "safe_chill" ? "Safe winter chill (CP)" : "Chill so far (CP)"}</div>
          <div className="flex items-center gap-1">
            {GRID_STOPS.map(([v, c]) => (
              <span key={v} className="flex flex-col items-center">
                <span className="h-2 w-6" style={{ background: c }} />
                <span className="num">{v}</span>
              </span>
            ))}
          </div>
        </div>
      )}
      {showErrors && (
        <div className="flex items-center gap-1.5">
          <span className="font-medium">Hidden-station miss:</span>
          <span className="inline-block h-2 w-2 rounded-full bg-good" /> 1
          <span className="inline-block h-3 w-3 rounded-full bg-watch" /> 3
          <span className={cn("inline-block h-4 w-4 rounded-full bg-risk")} /> 6+ CP
        </div>
      )}
    </div>
  );
}
