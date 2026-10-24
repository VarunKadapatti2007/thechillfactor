// Headless Edge/Chrome check over the DevTools protocol (no extra deps; Node 22+).
//
// Usage: node scripts/browser_check.mjs <url> <out.png> [--w 1440] [--h 900] [--wait 8000]
//        [--steps steps.json] [--offline]
// steps.json: [{"click": "css selector"} | {"eval": "js"} | {"wait": ms} | {"shot": "file.png"}]
// Prints console errors, page exceptions, failed requests, and eval results.
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const args = process.argv.slice(2);
const url = args[0];
const out = args[1];
const opt = (k, d) => {
  const i = args.indexOf(`--${k}`);
  return i >= 0 ? args[i + 1] : d;
};
const W = +opt("w", 1440), H = +opt("h", 900), WAIT = +opt("wait", 8000);
const stepsFile = opt("steps", null);
const offline = args.includes("--offline");
const mobile = args.includes("--mobile");
const block = opt("block", "");  // comma-separated URL patterns to fail, e.g. "*openfreemap*,*:8000*"

const candidates = [
  process.env.BROWSER,
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
].filter(Boolean);
const exe = candidates.find((p) => existsSync(p));
const port = 9300 + Math.floor(Math.random() * 500);
const profile = mkdtempSync(join(tmpdir(), "cp-browser-"));
const proc = spawn(exe, [
  "--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
  `--window-size=${W},${H}`, "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
  "--enable-unsafe-swiftshader", "--use-angle=swiftshader", "about:blank",
], { stdio: "ignore" });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let wsUrl;
for (let i = 0; i < 50 && !wsUrl; i++) {
  await sleep(200);
  try {
    const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
    wsUrl = list.find((t) => t.type === "page")?.webSocketDebuggerUrl;
  } catch {}
}
if (!wsUrl) { console.error("browser did not start"); proc.kill(); process.exit(2); }

const ws = new WebSocket(wsUrl);
await new Promise((r) => ws.addEventListener("open", r));
let id = 0;
const pending = new Map();
const logs = [];
ws.addEventListener("message", (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === "Runtime.consoleAPICalled" && ["error", "warning"].includes(m.params.type)) {
    logs.push(`[console.${m.params.type}] ` + m.params.args.map((a) => a.value ?? a.description ?? "").join(" ").slice(0, 400));
  }
  if (m.method === "Runtime.exceptionThrown") logs.push("[exception] " + (m.params.exceptionDetails.exception?.description ?? m.params.exceptionDetails.text).slice(0, 600));
  if (m.method === "Network.loadingFailed" && !m.params.canceled) logs.push(`[netfail] ${m.params.errorText} ${m.params.requestId}`);
  if (m.method === "Network.responseReceived" && m.params.response.status >= 400) logs.push(`[http ${m.params.response.status}] ${m.params.response.url.slice(0, 200)}`);
});
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });

await send("Runtime.enable");
await send("Network.enable");
await send("Page.enable");
if (mobile) await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 2, mobile: true });
if (offline) await send("Network.emulateNetworkConditions", { offline: true, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
if (block) await send("Network.setBlockedURLs", { urls: block.split(",") });
await send("Page.navigate", { url });
await sleep(WAIT);

async function shot(file) {
  const r = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(file, Buffer.from(r.result.data, "base64"));
  console.log("screenshot", file);
}
async function evaluate(expr) {
  const r = await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true });
  return r.result?.result?.value ?? r.result?.exceptionDetails?.exception?.description;
}

if (stepsFile) {
  const steps = JSON.parse(readFileSync(stepsFile, "utf8"));
  for (const s of steps) {
    if (s.click) {
      const ok = await evaluate(`(() => { const el = document.querySelector(${JSON.stringify(s.click)}); if (!el) return "missing: ${s.click.replace(/"/g, "'")}"; el.click(); return "clicked"; })()`);
      console.log("click", s.click, "->", ok);
    }
    if (s.waitFor) {
      const t0 = Date.now();
      let ok = false;
      while (Date.now() - t0 < (s.timeout ?? 60000)) {
        if (await evaluate(`!!(${s.waitFor})`) === true) { ok = true; break; }
        await sleep(250);
      }
      console.log("waitFor", s.waitFor.slice(0, 80), ok ? `ok ${Date.now() - t0}ms` : "TIMEOUT");
    }
    if (s.mouse) {
      const [x, y] = s.mouse;
      for (const type of ["mouseMoved", "mousePressed", "mouseReleased"]) {
        await send("Input.dispatchMouseEvent", { type, x, y, button: "left", clickCount: 1 });
      }
      await sleep(250);
    }
    if (s.eval) console.log("eval ->", JSON.stringify(await evaluate(s.eval)).slice(0, 2000));
    if (s.wait) await sleep(s.wait);
    if (s.shot) await shot(s.shot);
  }
}
if (out) await shot(out);
console.log(logs.length ? logs.join("\n") : "no console errors");
ws.close();
proc.kill();
process.exit(0);
