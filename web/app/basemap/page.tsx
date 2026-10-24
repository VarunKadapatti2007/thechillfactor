"use client";

// Utility page used once by scripts/render_basemap.mjs to capture the offline
// basemap image (public/demo/basemap.png). The viewport's aspect matches the
// Mercator aspect of the bounds, so the capture covers them exactly.
import dynamic from "next/dynamic";

const Capture = dynamic(() => import("./Capture"), { ssr: false });

export default function Page() {
  return <Capture />;
}
