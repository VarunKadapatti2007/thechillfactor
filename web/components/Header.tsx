"use client";

import { useStore } from "@/lib/store";
import HowItWorks from "./HowItWorks";
import { cn } from "./ui";

export default function Header() {
  const { s, d } = useStore();
  return (
    <header className="relative z-30 flex h-14 shrink-0 items-center gap-3 border-b border-line bg-surface px-3 sm:px-4">
      <div className="min-w-0 shrink-0">
        <h1 className="text-[20px] leading-none text-brand">ChillPrint</h1>
        <p className="mt-0.5 hidden text-[12px] leading-none text-muted md:block">Chill for your orchard, not the nearest station</p>
      </div>
      <div className="ml-auto flex min-w-0 flex-1 items-center justify-end gap-2">
        <div role="group" aria-label="Temperature units" className="flex shrink-0 rounded-[8px] border border-line p-0.5">
          {(["F", "C"] as const).map((u) => (
            <button
              key={u}
              aria-pressed={s.units === u}
              onClick={() => d({ type: "units", units: u })}
              className={cn(
                "h-7 rounded-[6px] px-2 text-[12px] font-semibold",
                s.units === u ? "bg-brand text-white" : "text-muted hover:text-ink",
              )}
            >
              °{u}
            </button>
          ))}
        </div>
        <HowItWorks />
      </div>
    </header>
  );
}
