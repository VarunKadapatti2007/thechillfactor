"use client";

import { Check, Pencil } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "../ui";

// One step of the form. A finished step folds to a single line (its summary) with a Change button.
export default function StepCard({
  n,
  title,
  done,
  children,
  collapsed = false,
  summary,
  onEdit,
}: {
  n: number;
  title: string;
  done: boolean;
  children?: ReactNode;
  collapsed?: boolean;
  summary?: ReactNode;
  onEdit?: () => void;
}) {
  const badge = (
    <span
      aria-hidden
      className={cn(
        "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[13px] font-semibold",
        done ? "bg-brand text-white" : "bg-bg text-ink",
      )}
    >
      {done ? <Check size={15} /> : n}
    </span>
  );
  if (collapsed) {
    return (
      <section aria-labelledby={`step-${n}`} className="flex items-center gap-3 rounded-[12px] border border-line bg-surface px-3 py-2.5">
        {badge}
        <div className="min-w-0 flex-1">
          <h2 id={`step-${n}`} className="text-[12px] font-semibold text-muted">
            {title}
          </h2>
          <div className="truncate text-[14px] font-medium text-ink">{summary}</div>
        </div>
        {onEdit && (
          <button onClick={onEdit} className="flex h-8 shrink-0 items-center gap-1 rounded-[8px] border border-line px-2.5 text-[12px] font-medium hover:bg-bg">
            <Pencil size={13} aria-hidden /> Change
          </button>
        )}
      </section>
    );
  }
  return (
    <section aria-labelledby={`step-${n}`} className="rounded-[12px] border border-line bg-surface p-4">
      <h2 id={`step-${n}`} className="mb-3 flex items-center gap-2.5 text-[18px] font-semibold">
        {badge}
        {title}
        {done && <span className="sr-only">(done)</span>}
      </h2>
      {children}
    </section>
  );
}
