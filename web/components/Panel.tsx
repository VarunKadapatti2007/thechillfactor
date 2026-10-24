"use client";

import * as Tabs from "@radix-ui/react-tabs";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { History, ShieldCheck, Snowflake, Sun } from "lucide-react";
import { useStore, type Tab } from "@/lib/store";
import CropPicker, { PinSummary } from "./CropPicker";
import EmptyState from "./EmptyState";
import ErrorBoundary from "./ErrorBoundary";
import AccuracyTab from "./tabs/AccuracyTab";
import HeatTab from "./tabs/HeatTab";
import HistoryTab from "./tabs/HistoryTab";
import WinterTab from "./tabs/WinterTab";
import { cn } from "./ui";

const TABS: { id: Tab; label: string; icon: typeof Snowflake }[] = [
  { id: "winter", label: "This winter", icon: Snowflake },
  { id: "history", label: "Land history", icon: History },
  { id: "heat", label: "Heat", icon: Sun },
  { id: "accuracy", label: "Accuracy", icon: ShieldCheck },
];

export default function PanelBody() {
  const { s, d } = useStore();
  const reduce = useReducedMotion();
  if (!s.pin) {
    return (
      <div className="p-4">
        <EmptyState />
      </div>
    );
  }
  const needsCrop = !s.crop && (s.tab === "winter" || s.tab === "history");
  return (
    <div className="space-y-3 p-4">
      <PinSummary />
      <CropPicker />
      <Tabs.Root value={s.tab} onValueChange={(v) => d({ type: "tab", tab: v as Tab })}>
        <Tabs.List aria-label="Results" className="grid grid-cols-4 gap-1 rounded-[8px] bg-bg p-1">
          {TABS.map((t) => {
            const Icon = t.icon;
            return (
              <Tabs.Trigger
                key={t.id}
                value={t.id}
                className={cn(
                  "flex min-h-11 flex-col items-center justify-center gap-0.5 rounded-[6px] px-1 text-[11px] font-medium text-muted",
                  "data-[state=active]:bg-surface data-[state=active]:text-ink data-[state=active]:shadow-sm",
                )}
              >
                <Icon size={16} aria-hidden />
                {t.label}
              </Tabs.Trigger>
            );
          })}
        </Tabs.List>
        <AnimatePresence mode="wait">
          <motion.div
            key={s.tab + (s.replaySeason ?? "")}
            initial={reduce ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduce ? undefined : { opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="pt-2"
          >
            {needsCrop ? (
              <p className="py-6 text-center text-[14px] text-muted">Pick your crop and variety above.</p>
            ) : (
              <Tabs.Content value={s.tab} forceMount>
                <ErrorBoundary key={s.tab + (s.replaySeason ?? "")} label="This section could not be shown.">
                  {s.tab === "winter" && <WinterTab />}
                  {s.tab === "history" && <HistoryTab />}
                  {s.tab === "heat" && <HeatTab />}
                  {s.tab === "accuracy" && <AccuracyTab />}
                </ErrorBoundary>
              </Tabs.Content>
            )}
          </motion.div>
        </AnimatePresence>
      </Tabs.Root>
    </div>
  );
}
