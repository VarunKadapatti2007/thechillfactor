"use client";

import * as Popover from "@radix-ui/react-popover";
import { animate, useReducedMotion } from "framer-motion";
import { CircleCheck, Info, OctagonAlert, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { clsx } from "clsx";
import type { Level } from "@/lib/types";

export function cn(...a: Parameters<typeof clsx>) {
  return clsx(...a);
}

type BtnVariant = "primary" | "secondary" | "ghost";

export function Button({
  variant = "secondary",
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: BtnVariant }) {
  return (
    <button
      {...rest}
      className={cn(
        "inline-flex min-h-9 items-center justify-center gap-1.5 rounded-[8px] px-3 text-[14px] font-medium transition-colors duration-150 disabled:opacity-50",
        variant === "primary" && "bg-brand text-white hover:bg-[#25573f]",
        variant === "secondary" && "border border-line bg-surface text-ink hover:bg-bg",
        variant === "ghost" && "text-ink hover:bg-bg",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function IconButton({
  label,
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      {...rest}
      aria-label={label}
      title={label}
      className={cn("inline-flex h-9 w-9 items-center justify-center rounded-[8px] text-ink hover:bg-bg", className)}
    >
      {children}
    </button>
  );
}

export function InfoTip({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Popover.Root>
      <Popover.Trigger
        aria-label={`About ${label}`}
        className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-muted hover:bg-bg hover:text-ink"
      >
        <Info size={15} aria-hidden />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          side="top"
          align="start"
          sideOffset={6}
          collisionPadding={12}
          className="z-[60] max-w-[300px] rounded-[8px] border border-line bg-surface p-3 text-[12px] leading-relaxed text-ink shadow-lg"
        >
          {children}
          <Popover.Arrow className="fill-surface" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

export function Section({ title, sentence, info, children, right }: {
  title: string;
  sentence?: ReactNode;
  info?: ReactNode;
  right?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <section className="border-t border-line py-4 first:border-t-0">
      <div className="mb-1 flex items-center gap-1">
        <h2 className="text-[16px] font-semibold">{title}</h2>
        {info && <InfoTip label={title}>{info}</InfoTip>}
        <div className="ml-auto">{right}</div>
      </div>
      {sentence && <p className="mb-3 text-[12px] text-muted">{sentence}</p>}
      {children}
    </section>
  );
}

export const LEVEL: Record<Level, { word: string; fg: string; bg: string; icon: typeof CircleCheck; color: string }> = {
  green: { word: "On track", fg: "#1f5e3e", bg: "#e7f2ec", icon: CircleCheck, color: "var(--good)" },
  amber: { word: "Watch", fg: "#74490c", bg: "#fbf0dc", icon: TriangleAlert, color: "var(--watch)" },
  red: { word: "At risk", fg: "#9b2424", bg: "#fbe8e8", icon: OctagonAlert, color: "var(--risk)" },
};

export function StatusPill({ level, size = "md" }: { level: Level; size?: "md" | "lg" }) {
  const L = LEVEL[level];
  const Icon = L.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-semibold",
        size === "lg" ? "px-3 py-1.5 text-[16px]" : "px-2.5 py-1 text-[12px]",
      )}
      style={{ background: L.bg, color: L.fg }}
    >
      <Icon size={size === "lg" ? 18 : 14} aria-hidden style={{ color: L.color }} />
      {L.word}
    </span>
  );
}

export function Skeleton({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return <div aria-hidden className={cn("skeleton", className)} style={style} />;
}

// Numbers count up over 600 ms; static under prefers-reduced-motion.
export function CountUp({ value, digits = 0 }: { value: number; digits?: number }) {
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(reduce ? value : 0);
  const prev = useRef(0);
  useEffect(() => {
    if (reduce) {
      setShown(value);
      return;
    }
    const c = animate(prev.current, value, {
      duration: 0.6,
      ease: "easeOut",
      onUpdate: (v) => setShown(v),
    });
    prev.current = value;
    return () => c.stop();
  }, [value, reduce]);
  return <span className="num">{shown.toFixed(digits)}</span>;
}

export function ErrorLine({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-center gap-3 rounded-[12px] border border-line bg-surface p-3 text-[14px]">
      <span className="text-ink">{message}</span>
      {onRetry && (
        <Button className="ml-auto" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
