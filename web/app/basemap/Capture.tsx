"use client";

import { setWorkerUrl } from "maplibre-gl";
import Map from "react-map-gl/maplibre";

setWorkerUrl("/maplibre-gl-worker.mjs");

export const BOUNDS: [[number, number], [number, number]] = [[-123.6, 34.4], [-117.6, 41.0]];

export default function Capture() {
  return (
    <div id="cap" style={{ width: "100vw", height: "100vh" }}>
      <Map
        initialViewState={{ bounds: BOUNDS, fitBoundsOptions: { padding: 0 } }}
        mapStyle="https://tiles.openfreemap.org/styles/positron"
        style={{ width: "100%", height: "100%" }}
        attributionControl={false}
        interactive={false}
        onIdle={() => {
          (window as unknown as { __mapIdle: boolean }).__mapIdle = true;
        }}
      />
    </div>
  );
}
