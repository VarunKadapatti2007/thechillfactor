"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { MapPin, Pencil } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useData } from "@/lib/data";
import { useStore } from "@/lib/store";
import ErrorBoundary from "./ErrorBoundary";
import Sections from "./results/Sections";
import Summary, { BlockCard } from "./results/Summary";
import { Button, ErrorLine } from "./ui";
import AnalysisProgress from "./wizard/AnalysisProgress";
import RunBar from "./wizard/RunBar";
import StepCrop from "./wizard/StepCrop";
import StepLocation from "./wizard/StepLocation";

const MIN_PROGRESS_MS = 900; // long enough to read, short enough not to stall cached results

function InputsSummary({ onEdit }: { onEdit: () => void }) {
  const { s } = useStore();
  const { crops } = useData();
  const r = s.run!;
  const crop = crops.data?.crops.find((c) => c.id === r.crop);
  const v = crop?.varieties.find((x) => x.id === r.variety);
  return (
    <div className="flex items-center gap-2 rounded-[12px] border border-line bg-surface p-3">
      <MapPin size={16} aria-hidden className="shrink-0 text-brand" />
      <div className="min-w-0 flex-1 text-[13px] leading-snug">
        <div className="truncate font-medium">
          {r.label ?? `${r.lat.toFixed(4)}, ${r.lon.toFixed(4)}`}
          {r.areaLabel && r.areaLabel.toLowerCase() !== (r.label ?? "").toLowerCase() ? ` · ${r.areaLabel}` : ""}
        </div>
        <div className="text-muted">{v && crop ? `${crop.name}, ${v.name}` : ""}</div>
      </div>
      <Button className="h-8 min-h-8 px-2.5 text-[12px]" onClick={onEdit}>
        <Pencil size={13} aria-hidden /> Change
      </Button>
    </div>
  );
}

export default function PanelBody() {
  const { s } = useStore();
  const { point } = useData();
  const reduce = useReducedMotion();
  const [editing, setEditing] = useState(true);
  const [minUntil, setMinUntil] = useState(0);
  const [, force] = useState(0);
  const top = useRef<HTMLDivElement>(null);

  // Any new run (button or shared link) folds the inputs away so the answer gets the space.
  useEffect(() => {
    if (s.run) setEditing(false);
  }, [s.run?.n]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!minUntil) return;
    const t = setTimeout(() => force((n) => n + 1), Math.max(0, minUntil - Date.now()) + 10);
    return () => clearTimeout(t);
  }, [minUntil]);

  const showInputs = !s.run || editing;
  const waiting = !!s.run && (point.loading || Date.now() < minUntil || (!point.data && !point.error));

  return (
    <div ref={top} className="space-y-3 p-4">
      {showInputs ? (
        <>
          {!s.run && (
            <div>
              <h2 className="text-[20px] font-semibold leading-tight">Is this winter enough for your trees?</h2>
              <p className="mt-1 text-[13px] text-muted">Three quick steps: where your orchard is, what you grow, then run the analysis.</p>
            </div>
          )}
          <StepLocation />
          <StepCrop />
          <div className="rounded-[12px] border border-line bg-surface p-3">
            <h2 className="mb-2 flex items-center gap-2 text-[16px] font-semibold">
              <span aria-hidden className="flex h-6 w-6 items-center justify-center rounded-full bg-bg text-[12px]">3</span>
              Run the analysis
            </h2>
            <RunBar
              onRun={() => {
                setEditing(false);
                setMinUntil(Date.now() + MIN_PROGRESS_MS);
                top.current?.scrollIntoView({ block: "start" });
              }}
            />
          </div>
        </>
      ) : (
        <InputsSummary onEdit={() => setEditing(true)} />
      )}

      {s.run && (
        <AnimatePresence mode="wait">
          {waiting ? (
            <motion.div key="progress" initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} exit={reduce ? undefined : { opacity: 0 }}>
              <AnalysisProgress done={false} blockPoints={s.run.samplePts?.length ?? 0} />
            </motion.div>
          ) : point.error && !point.data ? (
            <motion.div key="error" initial={false} animate={{ opacity: 1 }}>
              <ErrorLine message="Couldn't analyze this spot. Check the connection or try a demo orchard." onRetry={point.retry} />
            </motion.div>
          ) : point.data ? (
            <motion.div
              key={`results-${s.run.n}`}
              initial={reduce ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, ease: "easeOut" }}
              className="space-y-3"
            >
              <ErrorBoundary label="The summary could not be shown.">
                <Summary p={point.data} />
              </ErrorBoundary>
              <BlockCard />
              <Sections p={point.data} />
            </motion.div>
          ) : null}
        </AnimatePresence>
      )}
    </div>
  );
}
