"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Check, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

// What the engine actually does for a run, shown while it works.
const STEPS = [
  "Finding the weather stations nearest your orchard",
  "Reading every winter since 1980 at your spot",
  "Counting chill hour by hour with the UC Dynamic Model",
  "Playing this winter forward with each past winter",
  "Working out the odds for your variety",
];

export default function AnalysisProgress({ done, blockPoints }: { done: boolean; blockPoints: number }) {
  const reduce = useReducedMotion();
  const steps = blockPoints > 1 ? [...STEPS, `Checking ${blockPoints} spots across your block`] : STEPS;
  const [i, setI] = useState(0);
  useEffect(() => {
    if (done) {
      setI(steps.length);
      return;
    }
    const t = setInterval(() => setI((k) => Math.min(k + 1, steps.length - 1)), 1100);
    return () => clearInterval(t);
  }, [done, steps.length]);

  return (
    <div role="status" aria-live="polite" className="rounded-[12px] border border-line bg-surface p-4">
      <h2 className="mb-1 text-[16px] font-semibold">Analyzing your orchard</h2>
      <p className="mb-3 text-[12px] text-muted">A new location takes about 5 to 10 seconds; places you have checked before are instant.</p>
      <div className="mb-3 h-1.5 overflow-hidden rounded-full bg-bg">
        <motion.div
          className="h-full rounded-full bg-brand"
          initial={{ width: "8%" }}
          animate={{ width: `${Math.max(8, (Math.min(i + (done ? 0 : 0.5), steps.length) / steps.length) * 100)}%` }}
          transition={{ duration: reduce ? 0 : 0.6, ease: "easeOut" }}
        />
      </div>
      <ol className="space-y-2">
        {steps.map((t, k) => (
          <li key={t} className="flex items-center gap-2 text-[13px]">
            {k < i ? (
              <Check size={15} aria-hidden className="shrink-0 text-good" />
            ) : k === i ? (
              <Loader2 size={15} aria-hidden className={`shrink-0 text-brand ${reduce ? "" : "animate-spin"}`} />
            ) : (
              <span aria-hidden className="block h-[15px] w-[15px] shrink-0 rounded-full border border-line" />
            )}
            <span className={k <= i ? "text-ink" : "text-muted"}>{t}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
