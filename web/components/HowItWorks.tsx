"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { CircleHelp, X } from "lucide-react";
import { EXPLAIN } from "@/lib/explain";

const TERMS: [string, string][] = [
  ["Chill portions", EXPLAIN.chillPortion],
  ["Need", EXPLAIN.need],
  ["Need-by date", EXPLAIN.byDate],
  ["\"9 in 10\"", EXPLAIN.odds],
  ["\"Give or take\"", EXPLAIN.errorBar],
  ["Where the weather comes from", EXPLAIN.method],
];

export default function HowItWorks() {
  return (
    <Dialog.Root>
      <Dialog.Trigger aria-label="How ChillPrint works" title="How ChillPrint works" className="inline-flex h-9 w-9 items-center justify-center rounded-[8px] text-ink hover:bg-bg">
        <CircleHelp size={18} aria-hidden />
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[70] bg-black/30" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-[71] max-h-[85vh] w-[min(92vw,520px)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-[12px] bg-surface p-5 shadow-xl">
          <div className="mb-3 flex items-start">
            <Dialog.Title className="flex-1 text-[20px] font-semibold">How ChillPrint works</Dialog.Title>
            <Dialog.Close aria-label="Close" className="rounded p-1 text-muted hover:text-ink">
              <X size={18} aria-hidden />
            </Dialog.Close>
          </div>
          <Dialog.Description className="mb-3 text-[14px] text-muted">
            ChillPrint tells you whether this winter is giving your trees enough cold to bloom well, at your exact orchard.
          </Dialog.Description>
          <ol className="mb-4 list-decimal space-y-1 pl-5 text-[14px]">
            <li>Mark your orchard: tap the map, search, or use your location. You can outline a whole block.</li>
            <li>Choose your crop and variety.</li>
            <li>Press Run analysis and read the answer at the top. Open the sections below it for more detail.</li>
          </ol>
          <h3 className="mb-2 text-[14px] font-semibold">What the words mean</h3>
          <dl className="space-y-2 text-[13px] leading-relaxed">
            {TERMS.map(([t, d]) => (
              <div key={t}>
                <dt className="font-semibold">{t}</dt>
                <dd className="text-muted">{d}</dd>
              </div>
            ))}
          </dl>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
