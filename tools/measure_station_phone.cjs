/**
 * The station page at a phone's width: the two pinned surfaces, and what a
 * budget drag costs on a phone's CPU.
 *
 * Two questions from `docs/open-work.md`, both measured on a real-feed page:
 *
 *   O4  with the budget rail pinned at the top and the shortlist dock pinned at
 *       the foot, how many rows are visible between them, and can the dock's
 *       own Copy be reached without covering the row above it?
 *   O8  what does one budget re-render cost when the CPU is a phone's? The
 *       desktop figure is 7.4 ms against a 50 ms budget, and the machine beside
 *       a figure is part of the figure (ADR-0032).
 *
 *   python build_demo_page.py --feed feeds/fares --timetable feeds/timetable \
 *       --origin GRA --date 2026-10-05 --notices nre,rdg,ogl,accuracy \
 *       --out _real_site/index.html
 *   node tools/measure_station_phone.cjs _real_site
 *
 * The phone is a proxy and is described as one: a 4x and a 6x CPU slowdown of
 * this machine, not a handset. No CPU throttle is a phone, so the figure says
 * which multiplier it was taken under and the desktop figure is re-taken in the
 * same process for comparison. The re-render probe is the one the suite holds
 * at 50 ms: `render()` followed by a forced layout read, with 101 destinations
 * in the payload, so the phone figure is comparable to the 7.4 ms desktop one
 * rather than merely nearby.
 */
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");

const SITE = path.resolve(process.argv[2] || "_real_site");
const PHONE = { width: 390, height: 844 };
const DRAG_RUNS = 7;

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
const round = (value, digits = 1) => Math.round(value * 10 ** digits) / 10 ** digits;

async function openPhone(browser, url, cpuRate) {
  const context = await browser.newContext({
    viewport: PHONE,
    deviceScaleFactor: 3,
    isMobile: true,
    hasTouch: true,
  });
  const page = await context.newPage();
  if (cpuRate) {
    const cdp = await context.newCDPSession(page);
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: cpuRate });
  }
  await page.goto(url, { waitUntil: "load" });
  return { context, page };
}

async function placesHeld(page, count) {
  return page.evaluate((wanted) => {
    setBudget(budgetCeiling());
    STATE.page = 1;
    render();
    const rows = Array.from(document.querySelectorAll("#rows tr[data-crs]"));
    for (const row of rows.slice(0, wanted)) {
      const box = row.querySelector(".hold-box");
      if (box && !box.checked) box.click();
    }
    return document.querySelectorAll("#shortlistDockList tr").length;
  }, count);
}

async function pinnedSurfaces(page) {
  // A page with no rows or no dock has no geometry to measure, and reading the
  // last row of an empty list threw instead of saying so. This is a measurement
  // of two surfaces, so a page without them is reported as unexercised.
  const ready = await page.evaluate(
    () =>
      document.querySelectorAll("#rows tr[data-crs]").length > 0 &&
      document.querySelectorAll("#shortlistDockList tr").length > 0
  );
  if (!ready) return null;
  // The rail is shown by an IntersectionObserver when the heading's budget
  // control leaves the viewport, and an observer's callback runs after the
  // scroll rather than during it. Reading `hidden` on the next statement
  // measured a rail that had not been told yet: the first run of this tool said
  // "hidden" at scrollY 2382, where the control is 2,000px above the screen.
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  try {
    await page.waitForFunction(
      () => !document.getElementById("budgetRail").hidden,
      undefined,
      { timeout: 2000 }
    );
  } catch (error) {
    // A page whose rail never appears is reported as that, not as a crash: it
    // is the answer to "is the rail up when the reader is at the foot of the
    // list", and the measurement below still reads the dock.
  }
  // Scrolled to the last row, not to the foot of the document: past the table
  // there is a footer, and a reader at the very bottom is looking at that. The
  // last row is put just clear of the dock, which is the state the question is
  // about -- the point where the two pinned surfaces both matter.
  await page.evaluate(() => {
    const rows = Array.from(document.querySelectorAll("#rows tr[data-crs]"));
    const dockTop = document.getElementById("shortlistDock").getBoundingClientRect().top;
    const last = rows[rows.length - 1];
    const absoluteBottom = last.getBoundingClientRect().bottom + window.scrollY;
    window.scrollTo(0, Math.max(0, absoluteBottom - dockTop));
  });
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
  return page.evaluate(() => {
    const rows = Array.from(document.querySelectorAll("#rows tr[data-crs]"));
    const last = rows[rows.length - 1];
    const rail = document.getElementById("budgetRail");
    const dock = document.getElementById("shortlistDock");
    const copy = document.getElementById("shortlistCopy");
    const railBox = rail.getBoundingClientRect();
    const dockBox = dock.getBoundingClientRect();
    const copyBox = copy.getBoundingClientRect();
    const lastBox = last.getBoundingClientRect();
    // With the rail hidden, "between the rail and the dock" is a count from the
    // top of the screen, which is not the question. The caller prints it as not
    // measured rather than as a number that would flatter the page.
    const visibleBetween = rail.hidden
      ? null
      : rows.filter((row) => {
          const box = row.getBoundingClientRect();
          return box.top >= railBox.bottom && box.bottom <= dockBox.top;
        }).length;
    const copyHit = document.elementFromPoint(
      copyBox.left + copyBox.width / 2,
      copyBox.top + copyBox.height / 2
    );
    return {
      rail: { hidden: rail.hidden, top: Math.round(railBox.top), bottom: Math.round(railBox.bottom) },
      dock: { top: Math.round(dockBox.top), height: Math.round(dockBox.height) },
      gap: Math.round(dockBox.top - railBox.bottom),
      dockRows: document.querySelectorAll("#shortlistDockList tr").length,
      visibleBetween,
      lastRow: { top: Math.round(lastBox.top), bottom: Math.round(lastBox.bottom) },
      lastRowClearsDock: lastBox.bottom <= dockBox.top,
      copy: {
        top: Math.round(copyBox.top),
        height: Math.round(copyBox.height),
        inViewport: copyBox.top >= 0 && copyBox.bottom <= window.innerHeight,
        reachable: copyHit === copy || copy.contains(copyHit),
      },
      scrolledTo: Math.round(window.scrollY),
      viewport: { width: window.innerWidth, height: window.innerHeight },
    };
  });
}

async function dragCost(page, growTo, runs) {
  // Two probes. "own" is the page as built, which is the figure a reader pays.
  // "101" is the list the desktop figure of 7.4 ms was taken on, kept so the
  // phone figure can be read against that one rather than against a different
  // measurement. The payload is grown through the page's own structure and the
  // page still paints one page of rows, so the cost is the sort and the DOM.
  return page.evaluate(([target, runs]) => {
    const base = DATA.destinations.slice();
    if (!base.length) return null;
    let count = base.length;
    if (target) {
      const clones = [];
      for (let index = 0; index < target; index += 1) {
        const source = base[index % base.length];
        clones.push({
          ...source,
          crs: "Z" + String(index).padStart(2, "0"),
          name: source.name + " " + index,
        });
      }
      DATA.destinations = clones;
      count = clones.length;
    }
    setBudget(budgetCeiling());
    STATE.page = 1;
    const costs = [];
    for (let run = 0; run < runs; run += 1) {
      const start = performance.now();
      render();
      document.getElementById("summary").getBoundingClientRect();
      costs.push(performance.now() - start);
    }
    return {
      costs,
      destinations: count,
      rows: document.querySelectorAll("#rows tr[data-crs]").length,
    };
  }, [growTo || null, runs]);
}

(async () => {
  const pagePath = stationPage();
  const server = await serve();
  const base = `http://127.0.0.1:${server.address().port}`;
  const url = `${base}/${path.relative(SITE, pagePath).split(path.sep).join("/")}`;
  const browser = await chromium.launch();
  try {
    console.log(`page ${path.relative(process.cwd(), pagePath)} at ${PHONE.width}x${PHONE.height}`);

    console.log("\n== O4: two pinned surfaces at the last row");
    // Two places is the question's own state; four is the one the dock's own
    // 42vh maximum makes worth measuring, because the strip the reader loses is
    // the number of places they are comparing.
    for (const wanted of [2, 4]) {
      const surfaces = await openPhone(browser, url);
      const held = await placesHeld(surfaces.page, wanted);
      const pinned = await pinnedSurfaces(surfaces.page);
      await surfaces.context.close();
      if (!pinned) {
        console.log(`${held} places held: this page has no rows or no dock, so the two surfaces were not measured`);
        continue;
      }
      console.log(
        `${held} places held: rail ${pinned.rail.hidden ? "hidden" : "shown"}, bottom ${pinned.rail.bottom}px` +
          ` | dock top ${pinned.dock.top}px, height ${pinned.dock.height}px` +
          ` | ${pinned.gap}px between them`
      );
      console.log(
        `  rows fully visible between the rail and the dock: ${pinned.visibleBetween === null ? "not measured, no rail" : pinned.visibleBetween}` +
          ` | last row ${pinned.lastRow.top}-${pinned.lastRow.bottom}px, clears the dock: ${pinned.lastRowClearsDock}`
      );
      console.log(
        `  dock Copy at ${pinned.copy.top}px of ${pinned.viewport.height}px, height ${pinned.copy.height}px,` +
          ` in the viewport: ${pinned.copy.inViewport}, topmost at its centre: ${pinned.copy.reachable}`
      );
    }

    console.log("\n== O8: one budget re-render, render() plus forced layout");
    for (const [label, rate] of [
      ["no throttle", 0],
      ["4x CPU slowdown", 4],
      ["6x CPU slowdown", 6],
    ]) {
      for (const growTo of [0, 101]) {
        const run = await openPhone(browser, url, rate);
        const cost = await dragCost(run.page, growTo, DRAG_RUNS);
        await run.context.close();
        if (!cost) {
          console.log(`${label}: this page has no destinations to re-render`);
          break;
        }
        const costs = cost.costs.slice(0, DRAG_RUNS);
        console.log(
          `${label}, ${growTo ? "101-destination probe" : "the page's own list"}: ` +
            `median ${round(median(costs))} ms [${costs.map((value) => round(value)).join(", ")}]` +
            ` for ${cost.rows} rows painted of ${cost.destinations} destinations`
        );
      }
    }
  } finally {
    await browser.close();
    server.close();
  }
})();
