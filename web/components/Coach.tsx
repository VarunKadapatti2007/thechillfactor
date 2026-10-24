"use client";

import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { useEffect } from "react";
import { useStore } from "@/lib/store";
import { cn } from "./ui";

export const COACH_TEXT = ["Drop a pin on your orchard", "Pick your crop and variety", "Read your verdict here"];

const KEY = "cp-coach-done";

function markDone() {
  try {
    window.localStorage.setItem(KEY, "1");
  } catch {}
}

// Shows the three coach marks on first run (call once); the help button replays them.
export function useCoachBoot() {
  const { d } = useStore();
  useEffect(() => {
    let seen = "";
    try {
      seen = window.localStorage.getItem(KEY) ?? "";
    } catch {}
    if (!seen) d({ type: "coach", step: 0 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}

export function CoachMark({ step, className, arrow = "down" }: { step: number; className?: string; arrow?: "down" | "up" | "left" | "right" }) {
  const { s, d } = useStore();
  const show = s.coach === step;
  const last = step === COACH_TEXT.length - 1;
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          role="dialog"
          aria-label={`Tip ${step + 1} of 3`}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className={cn("pointer-events-auto absolute z-40 w-[250px] rounded-[12px] bg-ink p-3 text-white shadow-xl", className)}
        >
          <span
            aria-hidden
            className={cn(
              "absolute h-3 w-3 rotate-45 bg-ink",
              arrow === "down" && "-bottom-1.5 left-1/2 -ml-1.5",
              arrow === "up" && "-top-1.5 left-1/2 -ml-1.5",
              arrow === "left" && "-left-1.5 top-1/2 -mt-1.5",
              arrow === "right" && "-right-1.5 top-1/2 -mt-1.5",
            )}
          />
          <div className="flex items-start gap-2">
            <span className="num text-[11px] text-white/70">{step + 1}/3</span>
            <p className="flex-1 text-[14px] font-semibold leading-snug">{COACH_TEXT[step]}</p>
            <button
              aria-label="Dismiss tips"
              className="-mr-1 -mt-1 rounded p-1 text-white/80 hover:text-white"
              onClick={() => {
                d({ type: "coach", step: null });
                markDone();
              }}
            >
              <X size={14} aria-hidden />
            </button>
          </div>
          <div className="mt-2 flex justify-end">
            <button
              className="rounded-[8px] bg-white px-2.5 py-1 text-[12px] font-semibold text-ink"
              onClick={() => {
                if (last) {
                  d({ type: "coach", step: null });
                  markDone();
                } else d({ type: "coach", step: step + 1 });
              }}
            >
              {last ? "Got it" : "Next"}
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
