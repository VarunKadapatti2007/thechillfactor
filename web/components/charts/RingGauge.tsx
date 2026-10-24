"use client";

import { motion, useReducedMotion } from "framer-motion";
import { CountUp } from "../ui";

// CP so far against the need band. Arc length is proportional to CP on a scale up to 1.25x the high need.
export default function RingGauge({ value, low, high, size = 120, instant = false }: { value: number; low: number; high: number; size?: number; instant?: boolean }) {
  const reduce = useReducedMotion() || instant;
  const max = Math.max(high * 1.25, value * 1.05, 1);
  const r = size / 2 - 10;
  const c = 2 * Math.PI * r;
  const frac = (v: number) => Math.max(0, Math.min(1, v / max));
  const arc = (a: number, b: number) => ({ strokeDasharray: `${(b - a) * c} ${c}`, strokeDashoffset: -a * c });
  const met = value >= low;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`${value.toFixed(0)} chill portions so far; need ${low === high ? low : `${low} to ${high}`}`}>
        <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#ecebe5" strokeWidth={10} />
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#3b7ea1" strokeOpacity={0.22} strokeWidth={14} style={arc(frac(low), Math.max(frac(high), frac(low) + 0.012))} />
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={met ? "#2f855a" : "#3b7ea1"}
            strokeWidth={10}
            strokeLinecap="round"
            strokeDasharray={c}
            initial={reduce ? false : { strokeDashoffset: c }}
            animate={{ strokeDashoffset: c * (1 - frac(value)) }}
            transition={{ duration: reduce ? 0 : 0.6, ease: "easeOut" }}
          />
        </g>
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-[28px] font-semibold leading-none">
          {reduce ? <span className="num">{value.toFixed(0)}</span> : <CountUp value={value} />}
        </span>
        <span className="mt-1 text-center text-[11px] leading-tight text-muted">chill portions<br />so far</span>
      </div>
    </div>
  );
}
