/**
 * When a station page paints its first row on a slow phone, measured.
 *
 * The question and the figures are in `docs/build-performance-findings.md`,
 * under "A station page's first paint on a slow phone". O2 of
 * `docs/open-work.md`, closed on 21 October 2026, asked for a first paint on a
 * throttled connection before anyone decided whether the payload is the thing
 * to split, and this is the harness that took it.
 *
 *   python build_demo_page.py --feed feeds/fares --timetable feeds/timetable \
 *       --origin GRA --date 2026-10-05 --notices nre,rdg,ogl,accuracy \
 *       --out _real_site/index.html
 *   node tools/measure_station_paint.cjs _real_site
 *
 * What "4x" means here is named rather than implied: Lighthouse's mobile
 * profile, which is 1.6 Mbps down, 750 kbps up, 150 ms RTT and a 4x CPU
 * slowdown. It is the same network shaping `measure_station_defer.cjs` uses, so
 * the two figures are taken on one connection rather than on two that happen to
 * be described as slow.
 *
 * The server gzips what it sends, because GitHub Pages does. A page measured
 * over an uncompressed local socket would state a first paint nobody's reader
 * would see, which is the failure this repo keeps paying for: a number that
 * describes the harness instead of the site.
 *
 * The unthrottled control is part of the measurement, not a nicety: it says how
 * much of the figure is the page and how much is the connection.
 */
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const zlib = require("node:zlib");
const { chromium } = require("playwright");

const SITE = path.resolve(process.argv[2] || "_real_site");
const RUNS = 5;
const CONTROLS = 3;
// Lighthouse mobile. Named in the findings file beside every figure from here.
const SLOW = {
  latency: 150,
  downloadThroughput: (1.6 * 1024 * 1024) / 8,
  uploadThroughput: (750 * 1024) / 8,
};
const CPU_SLOWDOWN = 4;

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json",
  ".svg": "image/svg+xml",
};

// The first row's own paint, recorded by polling for a row with a height rather
// than by listening for load: a load event says the page finished, not that a
// reader saw a fare. Installed before any page script, so the time is the row's.
const FIRST_ROW = `
  window.__firstRow = null;
  const look = () => {
    const row = document.querySelector("#rows tr[data-crs]");
    if (row && row.getBoundingClientRect().height > 0 && window.__firstRow === null) {
      window.__firstRow = performance.now();
      return;
    }
    requestAnimationFrame(look);
  };
  requestAnimationFrame(look);
`;

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
  // Sorted, so a multi-station site is measured on the same page every time
  // rather than on whichever folder the filesystem happened to list first.
  return found.sort()[0];
}

function serve() {
  const server = http.createServer((request, response) => {
    const pathname = decodeURIComponent(new URL(request.url, "http://127.0.0.1").pathname);
    let file = path.join(SITE, pathname);
    if (pathname.endsWith("/")) file = path.join(file, "index.html");
    // Resolved rather than prefixed: "_site" is a prefix of "_site-old", and a
    // sibling folder is not a page this site may serve.
    const inside = path.relative(SITE, file);
    if (inside.startsWith("..") || path.isAbsolute(inside) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
      response.writeHead(404, { "content-type": "text/plain" });
      response.end("no");
      return;
    }
    const body = fs.readFileSync(file);
    const type = TYPES[path.extname(file)] || "application/octet-stream";
    const wantsGzip = /\bgzip\b/.test(request.headers["accept-encoding"] || "");
    if (wantsGzip && /^(text|application)\//.test(type)) {
      const packed = zlib.gzipSync(body, { level: 9 });
      response.writeHead(200, {
        "content-type": type,
        "content-encoding": "gzip",
        "content-length": packed.length,
      });
      response.end(packed);
      return;
    }
    response.writeHead(200, { "content-type": type, "content-length": body.length });
    response.end(body);
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(server)));
}

// A run with no paint entry is left out rather than read as a zero: the first
// unthrottled run once returned no FCP, and a zero in the sample would have
// pulled the median toward a paint that never happened.
const median = (values) => {
  const known = values.filter((value) => value !== null);
  return known.length ? [...known].sort((a, b) => a - b)[Math.floor(known.length / 2)] : null;
};
const round = (value) => (value === null ? null : Math.round(value));

async function once(browser, url, throttled) {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 3,
    isMobile: true,
    hasTouch: true,
  });
  const page = await context.newPage();
  if (throttled) {
    const cdp = await context.newCDPSession(page);
    await cdp.send("Network.enable");
    await cdp.send("Network.emulateNetworkConditions", { offline: false, ...SLOW });
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: CPU_SLOWDOWN });
  }
  // The cache is emptied per run, because a second visit is a different page:
  // the assets are hashed and cached for a year, and a warm run measures the
  // cache rather than the first paint a new reader gets on a new phone.
  await page.addInitScript({ content: FIRST_ROW });
  await page.goto(url, { waitUntil: "load" });
  // The row often paints after load, so the poll is given its moment before the
  // sample is read. Without this a fast connection recorded null and the run
  // silently left the median, which is a shorter sample rather than a figure.
  await page
    .waitForFunction(() => window.__firstRow !== null, undefined, { timeout: 15000 })
    .catch(() => {});
  const facts = await page.evaluate(() => {
    const paint = performance
      .getEntriesByType("paint")
      .find((entry) => entry.name === "first-contentful-paint");
    const nav = performance.getEntriesByType("navigation")[0];
    // The document is part of what a reader pays, and it is the largest part on
    // this page; a "transferred" line listing only the two hashed assets would
    // read as a cheaper page than the one measured.
    const resources = [
      { name: "document", transfer: nav ? nav.transferSize || nav.encodedBodySize : 0 },
      ...performance.getEntriesByType("resource").map((entry) => ({
        name: entry.name.replace(/^.*\//, ""),
        transfer: entry.transferSize || entry.encodedBodySize,
      })),
    ];
    const rows = document.querySelectorAll("#rows tr[data-crs]").length;
    return {
      fcp: paint ? paint.startTime : null,
      firstRow: window.__firstRow,
      dcl: nav ? nav.domContentLoadedEventEnd : null,
      load: nav ? nav.loadEventEnd : null,
      rows,
      resources,
    };
  });
  await context.close();
  return facts;
}

(async () => {
  const page = stationPage();
  const server = await serve();
  const base = `http://127.0.0.1:${server.address().port}`;
  const url = `${base}/${path.relative(SITE, page).split(path.sep).join("/")}`;
  const browser = await chromium.launch();
  const out = {};
  try {
    for (const [label, throttled, runs] of [
      ["slow", true, RUNS],
      ["control", false, CONTROLS],
    ]) {
      const measured = [];
      for (let index = 0; index < runs; index += 1) {
        measured.push(await once(browser, url, throttled));
      }
      out[label] = {
        runs: measured,
        fcp: round(median(measured.map((run) => run.fcp))),
        firstRow: round(median(measured.map((run) => run.firstRow))),
        dcl: round(median(measured.map((run) => run.dcl))),
        load: round(median(measured.map((run) => run.load))),
        rows: measured[0].rows,
        bytes: measured[0].resources,
      };
    }
  } finally {
    await browser.close();
    server.close();
  }
  console.log(`page ${path.relative(process.cwd(), page)} at 390x844, ${out.slow.rows} rows rendered`);
  for (const label of ["slow", "control"]) {
    const entry = out[label];
    console.log(
      `\n== ${label === "slow" ? "Lighthouse mobile (1.6Mbps, 150ms, 4x CPU)" : "unthrottled control"}` +
        `, median of ${entry.runs.length} runs`
    );
    // A missing paint entry prints as "--" rather than as a gap between two
    // commas, so a sample with a hole in it cannot read as a shorter list.
    const shown = (value) => (value === null ? "--" : round(value));
    console.log(
      `FCP ${entry.fcp} ms [${entry.runs.map((run) => shown(run.fcp)).join(", ")}]` +
        ` | first row ${entry.firstRow} ms [${entry.runs.map((run) => shown(run.firstRow)).join(", ")}]` +
        ` | DCL ${entry.dcl} ms | load ${entry.load} ms`
    );
    console.log(
      `transferred: ${entry.bytes
        .map((resource) => `${resource.name || "document"} ${Math.round(resource.transfer / 1024)} KB`)
        .join(", ")}`
    );
  }
})();
