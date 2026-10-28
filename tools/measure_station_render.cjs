/**
 * What one render of a built station page costs, and how much of that is the
 * same work done twice.
 *
 * The 28 October 2026 audit measured 12.47 ms of script and 57,996 `priceOf`
 * calls for one render of the real Grantham page, and 32.8-54.3 ms frames
 * through a ten-step budget drag. A figure without a command behind it is a
 * claim, so this is the command: it serves a built site, opens its station page
 * at a desktop's width, and reports
 *
 *   - the median cost of `render()` alone and of `render()` plus a forced
 *     layout, because they answer different questions: the first is the work
 *     this script does, the second is what a frame costs before paint;
 *   - how many times one render asks `priceOf`, `cheapestDestinations` and
 *     `standardPrice` for an answer (counted by wrapping the page's own
 *     functions, so the count is of the code as built rather than of a copy);
 *   - how many writes the count line takes during a ten-step drag and how many
 *     of them land on a live region, which is the pair that says whether a
 *     screen reader is handed one sentence per gesture or one per frame;
 *   - how far apart the drag's own frames are.
 *
 *   node tools/measure_station_render.cjs _real_site
 *
 * The site is selected the same way `measure_station_phone.cjs` selects one, and
 * for the same reason: a figure is only comparable to the last one if it is
 * taken on the same page.
 */
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");

const SITE = path.resolve(process.argv[2] || "_site");
const DESKTOP = { width: 1280, height: 900 };
const RENDER_RUNS = 21;
// The first renders pay the engine's own warm-up, which is not a figure about
// this page.
const WARMUP = 3;
const DRAG_STEPS = 10;

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json",
  ".svg": "image/svg+xml",
};

function stationPage() {
  if (!fs.existsSync(SITE) || !fs.statSync(SITE).isDirectory()) {
    console.error(`${SITE} is not a built site, so there is nothing to measure. Build one first.`);
    process.exit(2);
  }
  const found = [];
  const walk = (directory) => {
    for (const child of fs.readdirSync(directory, { withFileTypes: true })) {
      const full = path.join(directory, child.name);
      if (child.isDirectory()) walk(full);
      else if (child.name === "index.html" && /[\\/]from[\\/]/.test(full)) found.push(full);
    }
  };
  walk(SITE);
  if (!found.length) {
    console.error(`${SITE} holds no station page under from/, so there is nothing to measure.`);
    process.exit(2);
  }
  // Sorted, so a multi-station site is measured on the same page every time.
  return found.sort()[0];
}

function serve() {
  const server = http.createServer((request, response) => {
    const pathname = decodeURIComponent(new URL(request.url, "http://127.0.0.1").pathname);
    let file = path.join(SITE, pathname);
    if (pathname.endsWith("/")) file = path.join(file, "index.html");
    // Resolved rather than prefixed: "_site" is a prefix of "_site-old".
    const inside = path.relative(SITE, file);
    if (inside.startsWith("..") || path.isAbsolute(inside) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
      response.writeHead(404, { "content-type": "text/plain" });
      response.end("no");
      return;
    }
    response.writeHead(200, {
      "content-type": TYPES[path.extname(file)] || "application/octet-stream",
    });
    response.end(fs.readFileSync(file));
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(server)));
}

const median = (values) => [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
const round = (value, digits = 2) => Math.round(value * 10 ** digits) / 10 ** digits;
const mean = (values) => values.reduce((sum, value) => sum + value, 0) / values.length;

// The page is one classic script, so its top-level function declarations are
// properties of the window: replacing one here changes what every caller in the
// page reaches, which is the only way to count the page's own calls rather than
// a reimplementation's.
const COUNT_CALLS = (names) => {
  window.__counts = {};
  for (const name of names) {
    const original = window[name];
    if (typeof original !== "function") continue;
    window.__counts[name] = 0;
    window[name] = function (...args) {
      window.__counts[name] += 1;
      return original.apply(this, args);
    };
  }
};

async function renderCost(page, runs, warmup) {
  return page.evaluate(([runs, warmup]) => {
    const summary = document.getElementById("summary");
    const script = [];
    const laid = [];
    for (let run = 0; run < runs; run += 1) {
      const start = performance.now();
      render();
      const afterScript = performance.now();
      // The same forced layout read the browser suite uses for its 50 ms budget,
      // so a drag's frame cost can be read against that number rather than
      // against a different probe.
      summary.getBoundingClientRect();
      script.push(afterScript - start);
      laid.push(performance.now() - start);
    }
    for (const name of Object.keys(window.__counts)) window.__counts[name] = 0;
    render();
    return {
      script: script.slice(warmup),
      laid: laid.slice(warmup),
      counts: { ...window.__counts },
      rows: document.querySelectorAll("#rows tr[data-crs]").length,
    };
  }, [runs, warmup]);
}

async function drag(page, steps) {
  return page.evaluate(async (steps) => {
    const slider = document.getElementById("budget");
    const summary = document.getElementById("summary");
    // textContent replaces the text node, so a childList record is one write of
    // the count line. `announced` is how many of those reached a live region:
    // records are delivered after the task that made them, so a frame whose
    // render switched the region off arrives with it still off, and the render
    // that settles the gesture has already switched it back on.
    let writes = 0;
    let announced = 0;
    const observer = new MutationObserver((records) => {
      writes += records.length;
      if (summary.getAttribute("aria-live") !== "off") announced += records.length;
    });
    observer.observe(summary, { childList: true, characterData: true, subtree: true });
    const top = Number(slider.max) || 0;
    const spans = [];
    let last = performance.now();
    for (let step = 1; step <= steps; step += 1) {
      slider.value = String(Math.round((top * step) / steps));
      slider.dispatchEvent(new Event("input", { bubbles: true }));
      await new Promise((done) => requestAnimationFrame(done));
      const now = performance.now();
      spans.push(now - last);
      last = now;
    }
    slider.dispatchEvent(new Event("change", { bubbles: true }));
    // The settle writes the summary once more, on the release.
    await new Promise((done) => requestAnimationFrame(done));
    observer.disconnect();
    return { writes, announced, spans };
  }, steps);
}

(async () => {
  const pagePath = stationPage();
  const server = await serve();
  const base = `http://127.0.0.1:${server.address().port}`;
  const url = `${base}/${path.relative(SITE, pagePath).split(path.sep).join("/")}`;
  const browser = await chromium.launch();
  try {
    const context = await browser.newContext({ viewport: DESKTOP });
    const page = await context.newPage();
    const failures = [];
    page.on("pageerror", (error) => failures.push(error.message));
    await page.goto(url, { waitUntil: "load" });
    await page.evaluate(COUNT_CALLS, ["priceOf", "cheapestDestinations", "standardPrice"]);
    console.log(`page ${path.relative(process.cwd(), pagePath)} at ${DESKTOP.width}x${DESKTOP.height}`);

    const cost = await renderCost(page, RENDER_RUNS, WARMUP);
    console.log(
      `\n== one render, ${cost.rows} rows painted\n` +
        `script only:  median ${round(median(cost.script))} ms ` +
        `[${cost.script.map((value) => round(value)).join(", ")}]\n` +
        `with layout:  median ${round(median(cost.laid))} ms ` +
        `[${cost.laid.map((value) => round(value)).join(", ")}]`
    );
    const counts = Object.entries(cost.counts)
      .map(([name, count]) => `${name} ${count}`)
      .join(", ");
    console.log(`calls per render: ${counts || "not counted, the page names none of them"}`);

    const dragRun = await drag(page, DRAG_STEPS);
    console.log(
      `\n== a ${DRAG_STEPS}-step drag\n` +
        `count line writes: ${dragRun.writes}, of them announced: ${dragRun.announced}\n` +
        `frame spans: median ${round(median(dragRun.spans))} ms, mean ${round(mean(dragRun.spans))} ms` +
        ` [${dragRun.spans.map((value) => round(value)).join(", ")}]`
    );

    await context.close();
    if (failures.length) {
      console.log(`\npage errors: ${failures.join("; ")}`);
      process.exitCode = 1;
    }
  } finally {
    await browser.close();
    server.close();
  }
})();
