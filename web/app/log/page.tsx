"use client";

import dynamic from "next/dynamic";

// The log is saved in this browser's storage, so render it client-side only.
const OrchardLogPage = dynamic(() => import("@/components/OrchardLog"), { ssr: false });

export default function LogPage() {
  return <OrchardLogPage />;
}
