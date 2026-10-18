/**
 * What every route's checks share: the page list, the server the pages are
 * served from, the two helpers a message written here needs, and the report
 * the run ends with.
 *
 * A check the page cannot exercise is a skip in every mode. The budget is what
 * stops a page that has nothing to exercise from reading as a pass, and it is
 * measured against the station and chooser pages only, because a privacy page
 * has no controls to skip and its matrix checks would otherwise dilute the
 * denominator.
 *
 * The station-list probes live here rather than beside the chooser because the
 * station page's picker asks the same question about the same list, and a copy
 * of the probe would be a second answer that can drift from the first.
 */
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
// The suite's own options are dropped from the page list by position rather
// than by shape, so a page path that happens to be a number is still a page
// path and a flag is never mistaken for one.
const ARGV = process.argv.slice(2);
// --sweep is still accepted, and still stripped from the page list below, so
// every command that passes it keeps working. It no longer changes anything:
// what a check the page cannot exercise means is the same in every mode (see
// NOT_EXERCISED), and the skip budget is enforced in all of them. It used to
// decide, and the difference was a published one-origin site failing five
// honest checks and so going untested.
const MAX_FLAG = ARGV.indexOf("--max");
const MAX_PAGES = MAX_FLAG === -1 ? Infinity : (() => {
  const value = Number(ARGV[MAX_FLAG + 1]);
  if (!Number.isInteger(value) || value < 1) {
    console.error("--max needs a whole number of pages, not " + ARGV[MAX_FLAG + 1]);
    process.exit(2);
  }
  return value;
})();
const PAGES = ARGV.filter((argument, index) => {
  if (argument === "--sweep") return false;
  // MAX_FLAG + 1 is index 0 when --max was not given, so the -1 case has to
  // be excluded first or the first page argument is dropped as the flag's
  // value.
  if (MAX_FLAG !== -1 && (index === MAX_FLAG || index === MAX_FLAG + 1)) return false;
  return true;
});
const SELLER = /^https:\/\/www\.(nationalrail\.co\.uk|thetrainline\.com)\//;
// A third outcome, for a check a page has nothing to exercise: no destination
// carrying a UNESCO property, one option in the picker, one destination-type
// chip, no second station to change to. "The suite never ran that assertion"
// is the thing this project keeps refusing to let pass quietly -- but neither
// is failing a page for being small, and a published one-origin build is the
// smallest page there is: it has no second station and no destination without a
// journey, so five checks it honestly cannot run used to be five failures and
// the page went untested. So a check with nothing to exercise is a skip in
// every mode, the run says how many it skipped, and the budget below is what
// stops a page that has nothing to exercise from reading as a pass.
const NOT_EXERCISED = Symbol("not exercised");
// The skip budget, as a fraction of the checks run on the pages that can
// produce a skip at all (station and chooser pages).
//
// Reporting a skip was never enough on its own. Two station pages in a sweep
// were once so small that twenty-two checks never ran, the run printed the
// count, and it read as a pass: the fixture had quietly stopped testing the
// thing the suite is for. A stated fraction is what stops that -- enough
// tolerance for a small station to have no UNESCO destination, not enough for
// a sweep whose pages have nothing to exercise. Exceeding it fails the run.
//
// The budget is measured against the station and chooser pages only, because a
// privacy page has no controls to skip and its accessibility-matrix checks
// would otherwise dilute the denominator.
const SKIP_BUDGET = 0.05;
// The budget for a page that carries no timetable, measured separately from the
// one above and never against the same denominator.
//
// A prices-only page cannot run the checks about times, days and the journeys
// they describe -- a service window, the day control, a changed journey, a
// split ticket. Those checks have no subject on it, which is a smaller claim
// about the page rather than a page with nothing in it, and holding it to the
// timetable's 5% made a gate that a licence decision could not keep green: the
// published site went prices-only on 16 October 2026 to clear the fares
// licence, and 467 of 6401 checks (7.3%) had no subject on pages that were
// otherwise full. Measured the same day: the 23 prices-only station pages in
// that sweep skipped 464 of 6138 checks, 7.6%, so 10% is that floor with room
// for a sample drawn from the small end of the network rather than a number
// picked to make the red run green. The workflow already states the same figure
// for one prices-only page.
//
// The two are counted apart rather than pooled, because pooling is what would
// let a prices-only sweep hide a page that has too little in it: a bucket is
// only ever compared with the pages of its own shape.
const SKIP_BUDGET_WITHOUT_TIMES = 0.1;
/** A check this page cannot exercise, and why. */
function notExercised(reason) {
  return { skip: NOT_EXERCISED, reason };
}
/** Every index.html beneath a directory, in name order, at any depth. */
function pagesBeneath(root) {
  const found = [];
  const walk = (directory) => {
    const children = fs
      .readdirSync(directory, { withFileTypes: true })
      .sort((left, right) => left.name.localeCompare(right.name));
    for (const child of children) {
      const full = path.join(directory, child.name);
      if (child.isDirectory()) walk(full);
      else if (child.name === "index.html") found.push(full);
    }
  };
  walk(root);
  return found;
}
/**
 * Turn what was asked for into the pages to drive.
 *
 * A directory becomes every index.html beneath it, in name order, so a sweep
 * is the same command as a single page and a whole station set can be checked
 * in one run. A directory holding no pages is left as itself, so it is
 * reported as a missing page rather than as a sweep of nothing that passed.
 */
function expand(wanted) {
  const named = [];
  const swept = [];
  for (const argument of wanted) {
    let directory = null;
    try {
      if (fs.statSync(argument).isDirectory()) directory = argument;
    } catch (error) {
      // Not there. Left as itself, and reported as a page that does not exist.
    }
    if (directory === null) {
      named.push(argument);
      continue;
    }
    const pages = pagesBeneath(directory);
    if (pages.length) swept.push(...pages);
    else named.push(argument);
  }
  const found = [...named, ...swept];
  // --max bounds the sweep, which is the directory. A page named on the command
  // line is not part of it: it was named for a reason, and on 16 October 2026
  // the reason was that the two page shapes the deploy workflow builds for the
  // suite -- a prices-only page and a one-page page -- are otherwise never met.
  // Capping the whole list sampled them away instead: with a network of ~2,700
  // station pages, the spread took 24 of everything and the shape pages, which
  // sit at the end of the list, were in every run's untested remainder. The
  // comment below used to claim the spread "always includes the first and last
  // page", which was untrue for any list longer than MAX_PAGES -- the last
  // index it reaches is floor((MAX_PAGES-1) * length / MAX_PAGES).
  if (swept.length > MAX_PAGES) {
    // Evenly spread, not a prefix. The pages arrive in name order, so a prefix
    // is the first N stations alphabetically and nothing after them: on a
    // 2,718-page network --max 24 drove the A's and the B's and no station
    // whose slug starts later than C. The sweep is here to find
    // origin-specific template bugs, and a sample confined to one end of the
    // alphabet cannot find one that only the far end has.
    //
    // Every MAX_PAGES-th page, which is deterministic and needs no seed.
    const step = swept.length / MAX_PAGES;
    const sample = [];
    for (let index = 0; index < MAX_PAGES; index += 1) {
      sample.push(swept[Math.floor(index * step)]);
    }
    // Loudly, because a bounded sweep that reads as a whole one is worse than
    // no sweep: it would be a gate reporting on a sample and calling it the
    // site. The names are printed so a reader can see the spread rather than
    // take the word for it.
    console.error(
      `--max ${MAX_PAGES}: driving ${sample.length} of the ${swept.length} pages under the ` +
        `swept director${swept.length === 1 ? "y" : "ies"}, evenly spread rather than the ` +
        `first ${MAX_PAGES}. ${swept.length - sample.length} of them are not being tested.` +
        (named.length
          ? ` Every page named on the command line is driven too (${named.length}).`
          : "")
    );
    for (const page of sample) console.error(`  swept ${page}`);
    return [...named, ...sample];
  }
  return found;
}
function requirePlaywright() {
  try {
    return require("playwright");
  } catch (error) {
    console.error("SKIPPED: playwright is not available to node, so nothing was tested.");
    console.error("");
    console.error("Borrow it, then run again:");
    console.error("  npx --yes --package playwright node browser_test.cjs");
    console.error("  npm install --no-save playwright && node browser_test.cjs");
    console.error("");
    console.error("reason: " + String(error.message).split("\n")[0]);
    return null;
  }
}
/**
 * The files a page asks for beyond itself, read from beside the page on disk.
 *
 * A page is served from memory, so a request it makes for anything else -- the
 * shared station-picker asset and the shared station stylesheet -- has no
 * directory to
 * resolve against. The page names the asset in its own markup and the asset sits
 * beside the page's site root, so the reference is followed from the page rather
 * than guessed: whatever a page asks for by name is looked for up its own tree.
 * An asset a page asks for and the suite cannot find is a stopped run, because a
 * page whose picker quietly went missing would otherwise pass by testing less.
 */
function sharedAssets(pages) {
  const files = new Map();
  const missing = [];
  for (const entry of pages) {
    if (!entry.file) continue;
    let html = "";
    try {
      html = fs.readFileSync(entry.file, "utf8");
    } catch (error) {
      continue;
    }
    for (const match of html.matchAll(/<(?:script|link)\b[^>]*(?:src|href)="([^"]+)"/g)) {
      const name = path.basename(new URL(match[1], "http://x").pathname);
      if (files.has(name)) continue;
      let directory = path.dirname(entry.file);
      let found = false;
      for (let up = 0; up < 5; up += 1) {
        const candidate = path.join(directory, name);
        if (fs.existsSync(candidate)) {
          files.set(name, fs.readFileSync(candidate));
          found = true;
          break;
        }
        const parent = path.dirname(directory);
        if (parent === directory) break;
        directory = parent;
      }
      if (!found && !missing.includes(name)) missing.push(name);
    }
  }
  return { files, missing };
}
function serve(bodies, assets = new Map()) {
  // One server for the whole run, with one synthetic path per page. The file
  // names are not unique -- a chooser and a station page are both index.html
  // -- and a page served from memory has no directory worth preserving, so
  // the path is a label rather than a location.
  const routes = new Map();
  bodies.forEach((body, index) => routes.set(`/page-${index + 1}.html`, body));
  const server = http.createServer((request, response) => {
    const pathname = new URL(request.url, "http://127.0.0.1").pathname;
    const body = routes.has(pathname) ? routes.get(pathname) : assets.get(path.basename(pathname));
    if (body === null || body === undefined) {
      response.writeHead(404, { "content-type": "text/plain" });
      response.end("no such page");
      return;
    }
    // The shared documents are not HTML: a script served as text/html is
    // refused outright by a browser that sees a nosniff header anywhere above
    // it, and a stylesheet served as anything but text/css is not applied at
    // all. This suite is about what the page does with the file, so the file
    // has to arrive as what it is.
    const type = pathname.endsWith(".js")
      ? "text/javascript; charset=utf-8"
      : pathname.endsWith(".css")
        ? "text/css; charset=utf-8"
        : "text/html; charset=utf-8";
    response.writeHead(200, { "content-type": type });
    response.end(body);
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(server)));
}
// Money, in the page's own way, for a message the suite writes rather than
// reads off the page.
const money = (pence) => "£" + (pence / 100).toFixed(2);
// Whole days from an ISO day to the reader's today, in the reader's own
// timezone: the same arithmetic the page does for itself, done here so the
// age the page printed can be held against the age it should have printed.
// It lives in node rather than in the page because node parses it once. A
// callback handed to page.evaluate is parsed again in the page, from the
// stringified source, and a doubled escape survives that trip as a literal
// backslash.
function daysSince(iso) {
  const now = new Date();
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((today - Date.parse(iso + "T00:00:00Z")) / 86400000);
}
// The last column takes the width of its own content and no more. The
// tolerance is a pixel and a half: a sub-pixel border and a rounded box can
// put a fraction on either side of the widest cell without the column being
// any wider than what is in it.
const cellsAreContentWide = (column) => column.width <= column.content + 1.5;
// How many lines a thing's own contents paint on, as painted line boxes rather
// than as CSS: getClientRects() over a range returns one rect per line, and the
// distinct tops are the lines. Line boxes a few pixels apart are one line, so a
// cell whose only child is an inline span does not report the span's line-height
// beside the row's strut as a second line. Both the desktop wrap check and the
// phone row's own checks measure with this, so "what counts as a line" is
// decided once (E15 of the 17 October 2026 audit).
function valueLines(el) {
  const range = document.createRange();
  range.selectNodeContents(el);
  const tops = Array.from(range.getClientRects())
    .map((rect) => rect.top)
    .sort((a, b) => a - b);
  let count = 0;
  let last = -Infinity;
  for (const top of tops) {
    if (top - last > 3) count += 1;
    last = top;
  }
  return count;
}
// The page is where line boxes exist, so the counter has to be installed
// there: page.evaluate stringifies its callback, which means a function defined
// here cannot be closed over from inside the page, and an init script is the
// one way to put it there that also survives every navigation open() performs.
// A section asks for it as window.valueLines.
async function installLineCounter(page) {
  await page.addInitScript({ content: `window.valueLines = ${valueLines};` });
}
// The probe a completion check should type, and the name it should then
// produce, read from the page's own station list rather than from the
// fixture: the shorter name wins over the one earlier in list order, which is
// the audit's trap (audit item 1, 9 October 2026). The probe prefers a prefix
// whose first station in list order is not the shortest candidate; a release
// with no such pair falls back to the first three letters of a name long
// enough to have them.
function completionProbe(stations) {
  const candidatesFor = (letters) =>
    stations.filter(
      (station) => station.name.toLowerCase().indexOf(letters.toLowerCase()) === 0
    );
  for (const station of stations) {
    for (let take = 1; take < station.name.length; take += 1) {
      const letters = station.name.slice(0, take);
      const matches = candidatesFor(letters);
      if (matches.length > 1 && matches.some((other) => other.name.length < station.name.length)) {
        return { letters, matches };
      }
    }
  }
  const first = stations.find((station) => station.name.length > 4);
  if (!first) return null;
  const letters = first.name.slice(0, 3);
  return { letters, matches: candidatesFor(letters) };
}
// The completion the probe should produce: an exact name wins, otherwise the
// shortest name that starts with the typed text, with destination count
// breaking a tie.
function expectedCompletion(probe) {
  const exact = probe.matches.find(
    (station) => station.name.toLowerCase() === probe.letters.toLowerCase()
  );
  if (exact) return exact.name;
  const ranked = probe.matches
    .slice()
    .sort((a, b) => a.name.length - b.name.length || (b.destinations || 0) - (a.destinations || 0));
  return ranked.length ? ranked[0].name : null;
}
function report(results) {
  const counted = (predicate) =>
    results.reduce((sum, result) => sum + result.checks.filter(predicate).length, 0);
  const total = counted(() => true);
  const failed = counted((entry) => !entry.ok && !entry.skipped);
  const skipped = counted((entry) => entry.skipped);
  // The budget is measured over the pages whose checks can be skipped, so the
  // pages that cannot skip do not make an over-skipped sweep look within it.
  // It is measured in two buckets, one per page shape: see
  // SKIP_BUDGET_WITHOUT_TIMES for why the shape of the page, rather than one
  // fraction for everything, is what the figure is stated against.
  const skippable = results.filter(
    (result) => result.kind === "station" || result.kind === "chooser"
  );
  const buckets = [
    { label: "page(s) with a timetable", budget: SKIP_BUDGET, times: true },
    { label: "page(s) without one", budget: SKIP_BUDGET_WITHOUT_TIMES, times: false },
  ].map((bucket) => {
    const pages = skippable.filter((result) => Boolean(result.times) === bucket.times);
    return {
      label: bucket.label,
      budget: bucket.budget,
      pages,
      checks: pages.reduce((sum, result) => sum + result.checks.length, 0),
      skipped: pages.reduce(
        (sum, result) => sum + result.checks.filter((entry) => entry.skipped).length,
        0
      ),
    };
  });
  const skipTotal = buckets.reduce((sum, bucket) => sum + bucket.checks, 0);
  const skipCount = buckets.reduce((sum, bucket) => sum + bucket.skipped, 0);
  const overBudget = buckets.filter((bucket) => bucket.skipped > bucket.checks * bucket.budget);
  const broken = results.filter(
    (result) => result.stopped || result.checks.some((entry) => !entry.ok && !entry.skipped)
  );
  // A page that is not a station page is neither a pass nor a failure -- it is
  // a path this suite cannot test. It does not fail the run on its own, but a
  // run in which no page at all was a station page has tested nothing, and it
  // fails for that reason instead of the 0/0 it would otherwise report.
  const offTopic = results.filter((result) => result.notStation);
  const tested = results.length - offTopic.length;
  const nothingTested = tested === 0;
  // A run with no page carrying a timetable has not exercised the times half of
  // the suite at all, however many pages it swept. The deploy workflow builds
  // that page (`_shape_site/one-page`) beside the prices-only one for exactly
  // this, and a run that quietly lost it would report every journey check as a
  // skip on a prices-only page and read as a pass.
  const noTimesAtAll = tested > 0 && buckets[0].pages.length === 0;
  if (offTopic.length) {
    console.log(
      `\n${offTopic.length} page(s) were not station pages and were not checked: ${offTopic
        .map((result) => result.given)
        .join(", ")}`
    );
  }
  // The routes the matrix drove are named, because a run that covered the
  // chooser and the privacy page is a different claim from one that covered
  // three station pages, and the tally alone cannot tell them apart.
  const routes = [...new Set(results.filter((r) => r.kind).map((r) => r.kind))].sort();
  if (routes.length) {
    console.log(
      `\nroutes in the accessibility matrix: ${routes.join(", ")} ` +
        `(${results.filter((r) => routes.includes(r.kind)).length} page(s) in light and dark, at desktop, phone and 200% zoom)`
    );
  }
  if (nothingTested) {
    console.error(
      `\nNo page in this run is a station page, so no check was made: ${offTopic
        .map((result) => result.given)
        .join(", ")}\n` +
        "Point the suite at a station page, or at a directory of them (a published site keeps them under from/)."
    );
  }
  // One line for the run as well as one per page, so a log with several pages
  // in it ends with something that can be read without counting back.
  const summary = broken.length
    ? `${broken.length} of ${results.length} page(s) failed: ${total - failed - skipped}/${total - skipped} checks passed (${broken.map((result) => result.given).join(", ")})`
    : `${tested} of ${results.length} page(s) checked, ${total - skipped - failed}/${total - skipped} browser checks passed`;
  console.log(
    `\n${summary}` +
      (skipped
        ? `, ${skipped} check(s) not exercised by the pages swept (` +
          buckets
            .filter((bucket) => bucket.pages.length)
            .map((bucket) => `${bucket.skipped} of ${bucket.checks} on the ${bucket.label}`)
            .join(", ") +
          ")"
        : "")
  );
  if (noTimesAtAll) {
    // Stated as a failure rather than a note: a run that swept twenty
    // prices-only pages has not tested the times half of the suite at all, and
    // "the count was printed" is the thing this budget exists because the
    // suite would not let pass.
    console.error(
      `\nNo page in this run carries a timetable, so the checks about times, days, ` +
        `journeys and splits were not exercised at all -- the ${skipCount} skip(s) above ` +
        `are how they would read on a prices-only page.\nAdd a page built with a ` +
        `timetable to the run; the deploy workflow's \`_shape_site/one-page\` is that page.`
    );
  }
  // The budget is stated in the failure as a number, because "too many checks
  // were skipped" without the fraction and the count is a claim a reader has to
  // take on trust -- and the whole reason for the budget is that a run which
  // printed a skip count could still be green. Each bucket names its own
  // fraction, because they are not the same question.
  for (const bucket of overBudget) {
    // Named per page, because "too many checks were skipped" is only
    // actionable if it says which page has too little in it.
    const worst = bucket.pages
      .map((result) => ({
        given: result.given,
        count: result.checks.filter((entry) => entry.skipped).length,
        of: result.checks.length,
      }))
      .filter((entry) => entry.count > 0)
      .sort((left, right) => right.count - left.count)
      .map((entry) => `${entry.given} (${entry.count}/${entry.of})`);
    console.error(
      `\nOver the skip budget: ${bucket.skipped} of ${bucket.checks} checks on the ${bucket.label} ` +
        `were not exercised, which is more than ${Math.round(bucket.budget * 100)}%.\n` +
        `The pages under test have too little in them for the suite to say much ` +
        `about them; give them destinations, or accept a smaller claim about what the run ` +
        `proved.\nSkipped by page: ${worst.join(", ")}`
    );
  }
  process.exit(
    failed || broken.length || nothingTested || noTimesAtAll || overBudget.length ? 1 : 0
  );
}
module.exports = { ARGV, MAX_PAGES, PAGES, SELLER, NOT_EXERCISED, SKIP_BUDGET, SKIP_BUDGET_WITHOUT_TIMES, notExercised, pagesBeneath, expand, requirePlaywright, sharedAssets, serve, money, daysSince, cellsAreContentWide, installLineCounter, completionProbe, expectedCompletion, report };
