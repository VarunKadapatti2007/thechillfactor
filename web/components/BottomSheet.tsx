"use client";

import { animate, motion, useMotionValue, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useStore, type SheetSnap } from "@/lib/store";

const PEEK = 168;

// Mobile results sheet over a full-screen map: peek, half, full.
export default function BottomSheet({ children }: { children: ReactNode }) {
  const { s, d } = useStore();
  const reduce = useReducedMotion();
  const box = useRef<HTMLDivElement>(null);
  const [H, setH] = useState(700);
  const y = useMotionValue(0);

  useEffect(() => {
    const el = box.current?.parentElement;
    if (!el) return;
    const ro = new ResizeObserver(() => setH(el.clientHeight));
    ro.observe(el);
    setH(el.clientHeight);
    return () => ro.disconnect();
  }, []);

  const snapY = (snap: SheetSnap) => (snap === "full" ? 8 : snap === "half" ? Math.round(H * 0.42) : H - PEEK);

  useEffect(() => {
    const c = animate(y, snapY(s.sheet), reduce ? { duration: 0 } : { type: "spring", stiffness: 380, damping: 38 });
    return () => c.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s.sheet, H, reduce]);

  function settle(velocity: number) {
    const cur = y.get() + velocity * 0.15;
    const opts: SheetSnap[] = ["full", "half", "peek"];
    let best: SheetSnap = "peek";
    let bd = Infinity;
    for (const o of opts) {
      const dd = Math.abs(snapY(o) - cur);
      if (dd < bd) {
        bd = dd;
        best = o;
      }
    }
    if (best === s.sheet) animate(y, snapY(best), { type: "spring", stiffness: 380, damping: 38 });
    d({ type: "sheet", sheet: best });
  }

  const next: Record<SheetSnap, SheetSnap> = { peek: "half", half: "full", full: "peek" };

  return (
    <motion.div
      ref={box}
      role="region"
      aria-label="Results"
      className="pointer-events-auto absolute inset-x-0 top-0 z-20 flex flex-col rounded-t-[16px] border border-line bg-surface shadow-[0_-6px_24px_rgba(31,42,36,0.12)]"
      style={{ y, height: H }}
      drag="y"
      dragConstraints={{ top: snapY("full"), bottom: snapY("peek") }}
      dragElastic={0.05}
      dragMomentum={false}
      onDragEnd={(_, info) => settle(info.velocity.y)}
    >
      <button
        className="mx-auto flex h-6 w-full shrink-0 cursor-grab items-center justify-center"
        aria-label={`Resize results panel (now ${s.sheet})`}
        onClick={() => d({ type: "sheet", sheet: next[s.sheet] })}
      >
        <span className="h-1.5 w-10 rounded-full bg-line" />
      </button>
      <div
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain"
        style={{ maxHeight: H - snapY(s.sheet) - 24 }}
        onPointerDownCapture={(e) => {
          // Let the content scroll without dragging the sheet once it is open.
          if (s.sheet !== "peek") e.stopPropagation();
        }}
      >
        {children}
      </div>
    </motion.div>
  );
}
