"use client";

import dynamic from "next/dynamic";

// The app is fully interactive (map, media queries, local storage), so render it client-side only.
const App = dynamic(() => import("@/components/App"), {
  ssr: false,
  loading: () => (
    <div className="flex h-dvh flex-col">
      <div className="h-14 border-b border-line bg-surface px-4 py-3">
        <span className="text-[20px] font-semibold text-brand">ChillPrint</span>
      </div>
      <div className="skeleton flex-1 rounded-none" />
    </div>
  ),
});

export default function Home() {
  return <App />;
}
