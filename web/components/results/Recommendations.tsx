"use client";

import { motion, useReducedMotion } from "framer-motion";
import { AlertTriangle, CalendarClock, Eye, Flower2, RefreshCw, Snowflake, Sparkles, Sprout, Thermometer } from "lucide-react";
import { useEffect, useState } from "react";
import { useData } from "@/lib/data";
import { longDate } from "@/lib/format";
import { useStore } from "@/lib/store";
import type { AdviceAction } from "@/lib/types";
import { cn } from "../ui";

const CATEGORY: Record<AdviceAction["category"], { icon: typeof Eye; label: string }> = {
  monitor: { icon: Eye, label: "Monitor" },
  protect_chill: { icon: Snowflake, label: "Protect chill" },
  bloom: { icon: Flower2, label: "Bloom" },
  data: { icon: Thermometer, label: "Your readings" },
  planning: { icon: Sprout, label: "Planning" },
};

const PRIORITY: Record<AdviceAction["priority"], { color: string; label: string }> = {
  high: { color: "#c2410c", label: "High priority" },
  medium: { color: "#2e6a4f", label: "Medium" },
  low: { color: "#8f9993", label: "Low" },
};

function Loading({ days }: { days: number }) {
  const lines = [
    `Reading your ${days} days of temperatures`,
    "Checking this winter's chill against your trees' need",
    "Comparing with every past winter at your farm",
    "Writing your next steps",
  ];
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((x) => Math.min(x + 1, lines.length - 1)), 2600);
    return () => clearInterval(t);
  }, [lines.length]);
  return (
    <div aria-busy="true" className="space-y-3">
      <motion.p key={i} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="flex items-center gap-2 text-[13px] text-muted">
        <Sparkles size={14} aria-hidden className="animate-pulse text-brand" />
        {lines[i]}...
      </motion.p>
      {[0, 1, 2].map((k) => (
        <div key={k} className="relative h-[68px] overflow-hidden rounded-[10px] bg-bg">
          <motion.div
            className="absolute inset-y-0 w-1/2 bg-gradient-to-r from-transparent via-white/70 to-transparent"
            initial={{ x: "-100%" }}
            animate={{ x: "220%" }}
            transition={{ repeat: Infinity, duration: 1.6, delay: k * 0.2, ease: "easeInOut" }}
          />
        </div>
      ))}
    </div>
  );
}

export default function Recommendations() {
  const { s } = useStore();
  const { advice } = useData();
  const reduce = useReducedMotion();
  const r = s.run;
  if (!r?.readings) return null;

  return (
    <section className="overflow-hidden rounded-[12px] border border-brand/30 bg-surface" aria-labelledby="advice-title">
      <div className="flex items-center gap-2 border-b border-line bg-brand/5 px-4 py-3">
        <motion.span
          aria-hidden
          className="flex h-8 w-8 items-center justify-center rounded-full bg-brand text-white"
          animate={advice.loading && !reduce ? { rotate: [0, 12, -12, 0] } : { rotate: 0 }}
          transition={{ repeat: advice.loading ? Infinity : 0, duration: 1.8 }}
        >
          <Sparkles size={16} />
        </motion.span>
        <div className="min-w-0 flex-1">
          <h2 id="advice-title" className="text-[17px] font-semibold leading-tight">
            What to do next
          </h2>
          <p className="truncate text-[12px] text-muted">
            For this farm and these readings{advice.data ? ` · winter ${advice.data.context.season}, as of ${longDate(advice.data.context.as_of)}` : ""}
          </p>
        </div>
        {advice.data && (
          <button onClick={advice.retry} aria-label="Refresh recommendations" className="rounded-[8px] p-1.5 text-muted hover:bg-bg">
            <RefreshCw size={15} />
          </button>
        )}
      </div>

      <div className="p-4">
        {advice.loading && <Loading days={r.readings.rows} />}
        {advice.error && !advice.loading && (
          <div className="flex items-center justify-between gap-2 text-[13px]">
            <span className="text-muted">{advice.error}</span>
            <button onClick={advice.retry} className="shrink-0 text-brand underline">
              Try again
            </button>
          </div>
        )}
        {advice.data && !advice.loading && (
          <div className="space-y-4">
            <motion.div initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
              <p className="text-[18px] font-semibold leading-snug">{advice.data.headline}</p>
              <p className="mt-1.5 text-[14px] leading-relaxed text-ink/90">{advice.data.summary}</p>
            </motion.div>

            <ol className="space-y-2">
              {advice.data.actions.map((a, i) => {
                const C = CATEGORY[a.category] ?? CATEGORY.monitor;
                const P = PRIORITY[a.priority] ?? PRIORITY.medium;
                const Icon = C.icon;
                return (
                  <motion.li
                    key={`${a.title}-${i}`}
                    initial={reduce ? false : { opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.15 + i * 0.09, duration: 0.3, ease: "easeOut" }}
                    className="relative flex gap-3 overflow-hidden rounded-[10px] border border-line bg-surface p-3 pl-4"
                  >
                    <span aria-hidden className="absolute inset-y-0 left-0 w-1" style={{ background: P.color }} />
                    <span aria-hidden className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-bg" style={{ color: P.color }}>
                      <Icon size={16} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                        <span className="text-[15px] font-semibold leading-snug">{a.title}</span>
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px]">
                        <span className="inline-flex items-center gap-1 rounded-full bg-bg px-2 py-0.5 font-medium">
                          <CalendarClock size={11} aria-hidden /> {a.when}
                        </span>
                        <span className="rounded-full px-2 py-0.5 font-medium text-white" style={{ background: P.color }}>
                          {P.label}
                        </span>
                        <span className="text-muted">{C.label}</span>
                      </div>
                      <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{a.why}</p>
                    </div>
                  </motion.li>
                );
              })}
            </ol>

            {advice.data.watch_for.length > 0 && (
              <motion.div
                initial={reduce ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.25 + advice.data.actions.length * 0.09 }}
                className="rounded-[10px] bg-amber-50 p-3"
              >
                <p className="text-[13px] font-semibold text-amber-900">Watch for</p>
                <ul className="mt-1 space-y-1">
                  {advice.data.watch_for.map((w, i) => (
                    <li key={i} className="flex gap-2 text-[13px] leading-relaxed text-amber-900">
                      <AlertTriangle size={14} aria-hidden className="mt-0.5 shrink-0" />
                      {w}
                    </li>
                  ))}
                </ul>
              </motion.div>
            )}

            {advice.data.data_notes.length > 0 && (
              <div className="rounded-[10px] bg-bg p-3">
                <p className="text-[13px] font-semibold">About your readings</p>
                <ul className="mt-1 space-y-1">
                  {advice.data.data_notes.map((w, i) => (
                    <li key={i} className="flex gap-2 text-[13px] leading-relaxed text-muted">
                      <Thermometer size={14} aria-hidden className="mt-0.5 shrink-0 text-chill" />
                      {w}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {advice.data.longer_term && (
              <div className={cn("flex gap-2 rounded-[10px] border border-line p-3 text-[13px] leading-relaxed")}>
                <Sprout size={16} aria-hidden className="mt-0.5 shrink-0 text-brand" />
                <span>
                  <span className="font-semibold">Longer term: </span>
                  {advice.data.longer_term}
                </span>
              </div>
            )}

            <p className="text-[11px] leading-relaxed text-muted">
              Written by AI (Claude) from this farm&apos;s numbers above. Talk with your UC farm advisor or PCA before any spray or treatment decision.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
