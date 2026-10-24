"use client";

import { Check } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "../ui";

export default function StepCard({ n, title, done, children, muted = false }: { n: number; title: string; done: boolean; children: ReactNode; muted?: boolean }) {
  return (
    <section aria-labelledby={`step-${n}`} className={cn("rounded-[12px] border border-line bg-surface p-3", muted && "opacity-60")}>
      <h2 id={`step-${n}`} className="mb-3 flex items-center gap-2 text-[16px] font-semibold">
        <span
          aria-hidden
          className={cn(
            "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[12px] font-semibold",
            done ? "bg-brand text-white" : "bg-bg text-ink",
          )}
        >
          {done ? <Check size={14} /> : n}
        </span>
        {title}
        {done && <span className="sr-only">(done)</span>}
      </h2>
      {children}
    </section>
  );
}
