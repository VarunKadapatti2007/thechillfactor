// Capture the offline basemap (web/public/demo/basemap.png) from the /basemap page.
// The viewport aspect equals the Mercator aspect of the bounds in app/basemap/Capture.tsx,
// so MapLibre can place the image back on exactly those corners when offline.
// Usage: node scripts/render_basemap.mjs [http://localhost:3000]
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const base = process.argv[2] ?? "http://localhost:3000";
const W = 1400;
const y = (l) => Math.log(Math.tan(Math.PI / 4 + (l * Math.PI) / 360));
const H = Math.round((W * (y(41.0) - y(34.4))) / ((6.0 * Math.PI) / 180));
const out = join(root, "web", "public", "demo", "basemap.png");
const steps = join(root, "web", ".basemap-steps.json");
import { writeFileSync, rmSync } from "node:fs";
writeFileSync(steps, JSON.stringify([{ waitFor: "window.__mapIdle === true", timeout: 120000 }, { wait: 2500 }]));
const r = spawnSync(process.execPath, [join(root, "scripts", "browser_check.mjs"), `${base}/basemap`, out, "--w", String(W), "--h", String(H), "--wait", "4000", "--steps", steps], { stdio: "inherit" });
rmSync(steps, { force: true });
console.log(`basemap ${W}x${H} -> ${out}`);
process.exit(r.status ?? 0);
