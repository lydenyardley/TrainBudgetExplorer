/**
 * What `defer` on the shared station list's tag buys a reader, measured.
 *
 * The question, the method and the figure are in
 * `docs/build-performance-findings.md`, under "The shared station list,
 * deferred". This is the harness that produced them: it takes one built station
 * page, writes two copies that differ only in that one attribute, serves each at
 * the demo build's own list size and at a release-sized list, and reports First
 * Contentful Paint, the first results row, DOMContentLoaded, and when each of
 * the page's two scripts actually ran.
 *
 *   python -m trainbudget.feeds.make_synthetic_feed _demo_feed --unserved-station \
 *       --third-origin --return-network --knowledgebase _demo_kb
 *   python -m trainbudget.build.build_demo_page --feed _demo_feed --timetable _demo_feed \
 *       --knowledgebase _demo_kb --all-origins --date 2026-10-05 \
 *       --out _demo_site/index.html
 *   node measure_station_defer.cjs
 *
 * It writes the release-sized list itself, through the build's own writer, from
 * `feeds/knowledgebase/stations.xml`: a hand-made list of that size would not be
 * the file a release serves, and the whole answer depends on the file's size.
 */
const { execFileSync } = require("node:child_process");
const { chromium } = require("playwright");
const { createServer } = require("node:http");
const fs = require("node:fs");
const path = require("node:path");

const SITE = path.resolve("_demo_site");
const PAGE = path.join(SITE, "from", "nottingham", "index.html");
const RUNS = 7;
const SLOW = { latency: 150, downloadThroughput: (1.6 * 1024 * 1024) / 8, uploadThroughput: (750 * 1024) / 8 };

// The loop that records when the first results row has painted, installed
// before any page script runs, so the time is the row's own paint and not a
// load event that happens to be nearby.
// When the page's own inline payload ran and when the list's own script ran,
// taken by trapping the two globals each of them sets. This is the parse
// barrier itself: in the blocking page the payload cannot have run until the
// list has arrived, whatever the paint then does.
const TRAPS = `
  window.__at = {};
  for (const name of ["TBE_DATA", "TBE_STATIONS"]) {
    let held;
    Object.defineProperty(window, name, {
      configurable: true,
      get: () => held,
      set: (value) => {
        held = value;
        window.__at[name] = Math.round(performance.now());
      },
    });
  }
`;
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

const median = (values) => {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
};
const round = (values, digits = 2) => values.map((v) => Math.round(v * 10 ** digits) / 10 ** digits);
// The route's own script cannot be *requested* until the parser has passed the
// list's tag, so the gap between the two is what a parse barrier costs on its
// own -- apart from anything the page then paints.
const requestGap = (run) => {
  const list = run.resources.find((resource) => /^stations-.*\.js$/.test(resource.name));
  const route = run.resources.find((resource) => /^station-.*\.js$/.test(resource.name));
  return list && route ? route.start - list.end : null;
};

async function measure(browser, base, pagePath, list, throttled) {
  const context = await browser.newContext();
  const page = await context.newPage();
  if (throttled) {
    const cdp = await context.newCDPSession(page);
    await cdp.send("Network.enable");
    await cdp.send("Network.emulateNetworkConditions", { offline: false, ...SLOW });
  }
  await page.addInitScript({ content: TRAPS + FIRST_ROW });
  await page.goto(`${base}${pagePath}?list=${list}`, { waitUntil: "load" });
  // What the picker does with the list once it has arrived: opened here so the
  // deferred tag is proven to have delivered its file rather than merely to
  // have stopped blocking. A 404 and a deferred script are the same paint.
  await page.click("h1 .origin-name, #changeOrigin");
  await page.waitForTimeout(60);
  const facts = await page.evaluate(() => {
    const paint = performance.getEntriesByType("paint").find((entry) => entry.name === "first-contentful-paint");
    const nav = performance.getEntriesByType("navigation")[0];
    const resources = performance.getEntriesByType("resource").map((entry) => ({
      name: entry.name.replace(/^.*\//, "").slice(0, 24),
      start: Math.round(entry.startTime),
      end: Math.round(entry.responseEnd),
      bytes: entry.transferSize || entry.encodedBodySize,
    }));
    return {
      fcp: paint ? paint.startTime : null,
      dcl: nav ? nav.domContentLoadedEventEnd : null,
      firstRow: window.__firstRow,
      at: window.__at,
      rows: document.querySelectorAll("#rows tr[data-crs]").length,
      stations: window.TBE_STATIONS ? window.TBE_STATIONS.length : 0,
      picks: document.querySelectorAll("#originPicks a").length,
      resources,
    };
  });
  await context.close();
  return facts;
}

(async () => {
  // The two pages, and the two lists, in one served folder.
  const served = path.resolve("_measure_site");
  fs.rmSync(served, { recursive: true, force: true });
  fs.mkdirSync(served, { recursive: true });
  const html = fs.readFileSync(PAGE, "utf8");
  const tag = '<script src="/stations.js" defer>';
  if (!html.includes(tag)) throw new Error("the built page no longer carries the deferred tag");
  // Four pages: each names its own list file, because a page cannot ask for a
  // list by size -- the tag is a plain URL -- and each variant differs from the
  // other only in that tag's attribute.
  for (const size of ["small", "full"]) {
    const named = html.replace('/stations.js"', `/stations-${size}.js"`);
    fs.writeFileSync(path.join(served, `defer-${size}.html`), named);
    // A is the tag as it was before E2: the same request, blocking the parser.
    fs.writeFileSync(
      path.join(served, `block-${size}.html`),
      named.replace(`/stations-${size}.js" defer`, `/stations-${size}.js"`)
    );
  }
  for (const file of fs.readdirSync(SITE)) {
    if (file.endsWith(".js") || file.endsWith(".css")) {
      fs.copyFileSync(path.join(SITE, file), path.join(served, file));
    }
  }
  const own = fs.readFileSync(path.join(SITE, "stations.js"));
  fs.writeFileSync(path.join(served, "stations-small.js"), own);
  const fullPath = path.resolve("_measure_stations_full.js");
  // The build's own writer, over the reference station file: the list is
  // whatever bytes a release would serve, not a stub of the same length.
  execFileSync(
    process.env.PYTHON || "python",
    [
      "-c",
      [
        "import types, xml.etree.ElementTree as ET",
        "from build_assets import render_station_asset, station_asset_rows, station_slugs_for",
        "ns = {'s': 'http://nationalrail.co.uk/xml/station'}",
        "rows = []",
        "for station in ET.parse('feeds/knowledgebase/stations.xml').getroot().findall('s:Station', ns):",
        "    crs = (station.findtext('s:CrsCode', default='', namespaces=ns) or '').strip()",
        "    name = (station.findtext('s:Name', default='', namespaces=ns) or '').strip()",
        "    if len(crs) == 3 and name:",
        "        rows.append((crs, name))",
        "locations = {crs: types.SimpleNamespace(name=name, crs=crs) for crs, name in rows}",
        "slugs = station_slugs_for(locations)",
        "index = [{'crs': crs, 'name': name, 'slug': slugs[crs]} for crs, name in sorted(rows)]",
        "open('_measure_stations_full.js', 'w', encoding='utf-8', newline='').write(",
        "    render_station_asset(station_asset_rows(index, '')))",
        "print(f'{len(index)} stations, {len(open(\"_measure_stations_full.js\", \"rb\").read())} bytes')",
      ].join("\n"),
    ],
    { stdio: "inherit" }
  );
  const full = fs.readFileSync(fullPath);
  fs.writeFileSync(path.join(served, "stations-full.js"), full);
  console.log(`small ${own.length} B; full ${full.length} B`);

  const server = createServer((req, res) => {
    const file = path.join(served, req.url.split("?")[0]);
    if (!fs.existsSync(file) || !fs.statSync(file).isFile()) {
      res.statusCode = 404;
      res.end("no");
      return;
    }
    const ext = path.extname(file);
    res.setHeader(
      "content-type",
      ext === ".js" ? "text/javascript" : ext === ".css" ? "text/css" : "text/html"
    );
    res.end(fs.readFileSync(file));
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch();

  const results = [];
  for (const list of ["small", "full"]) {
    const runs = { block: [], defer: [] };
    for (let i = 0; i < RUNS; i += 1) {
      // Alternating order within each repetition, so a machine that drifts
      // during the sweep does not pay one variant twice as often as the other.
      const order = i % 2 ? ["defer", "block"] : ["block", "defer"];
      for (const variant of order) {
        runs[variant].push(
          await measure(browser, base, `/${variant}-${list}.html`, list, true)
        );
      }
    }
    results.push({ list, throttled: true, bytes: list === "full" ? full.length : own.length, runs });
  }
  // The throttle's own control: the same two variants with no CDP shaping.
  const fast = { block: [], defer: [] };
  for (let i = 0; i < 3; i += 1) {
    for (const variant of i % 2 ? ["defer", "block"] : ["block", "defer"]) {
      fast[variant].push(await measure(browser, base, `/${variant}-full.html`, "full", false));
    }
  }
  results.push({ list: "full", throttled: false, bytes: full.length, runs: fast });

  for (const entry of results) {
    const label = `${entry.list === "full" ? "release-sized list" : "demo list"} (${entry.bytes} B), ${
      entry.throttled ? "150ms/1.6Mbps" : "unthrottled"
    }`;
    console.log(`\n== ${label}`);
    for (const variant of ["block", "defer"]) {
      const runs = entry.runs[variant];
      const fcp = runs.map((run) => run.fcp).filter((value) => value !== null);
      const row = runs.map((run) => run.firstRow).filter((value) => value !== null);
      const dcl = runs.map((run) => run.dcl);
      console.log(
        `${variant.padEnd(6)} FCP median ${Math.round(median(fcp))} ms [${round(fcp, 0).join(", ")}] | ` +
          `first row ${Math.round(median(row))} ms [${round(row, 0).join(", ")}] | ` +
          `DCL ${Math.round(median(dcl))} ms | rows ${runs.map((run) => run.rows).join("/")} | ` +
          `stations delivered ${runs.map((run) => run.stations).join("/")} | picker options ${runs
            .map((run) => run.picks)
            .join("/")}\n` +
          `       payload ran at ${Math.round(median(runs.map((run) => run.at.TBE_DATA)))} ms, ` +
          `list ran at ${Math.round(median(runs.map((run) => run.at.TBE_STATIONS)))} ms`
      );
      const list = runs[0].resources.filter((resource) => /^stations-.*\.js$/.test(resource.name));
      const route = runs[0].resources.filter((resource) => /^station-.*\.js$/.test(resource.name));
      const sheet = runs[0].resources.filter((resource) => /^station-.*\.css$/.test(resource.name));
      console.log(
        `       requests: stylesheet ${JSON.stringify(sheet[0] || null)} list ${JSON.stringify(
          list[0] || null
        )} route script ${JSON.stringify(route[0] || null)}`
      );
    }
    const gap = (variant) => {
      const values = entry.runs[variant].map(requestGap).filter((value) => value !== null);
      return values.length ? Math.round(median(values)) : null;
    };
    console.log(
      `difference (block - defer): FCP ${Math.round(
        median(entry.runs.block.map((r) => r.fcp)) - median(entry.runs.defer.map((r) => r.fcp))
      )} ms, first row ${Math.round(
        median(entry.runs.block.map((r) => r.firstRow)) - median(entry.runs.defer.map((r) => r.firstRow))
      )} ms`
    );
    console.log(
      `request gap, list end to route script start: block ${gap("block")} ms, defer ${gap("defer")} ms`
    );
  }

  await browser.close();
  server.close();
})();
