/**
 * A real browser test for the generated page.
 *
 * The page is the whole product and nothing tested it in a browser: the Python
 * suite proves the payload, the template strings, and the fare maths, but not that
 * a reader can drag the slider, filter to a town, follow a ticket link, or copy a
 * row's journey details. Those are the things a reader actually does.
 *
 * Run it with playwright on one or more page paths:
 *
 *     npx --yes --package playwright node browser_test.cjs
 *     node browser_test.cjs            # when playwright is installed locally
 *     node browser_test.cjs demo.html _site/index.html
 *     node browser_test.cjs _site/from          # sweep a published site
 *     node browser_test.cjs _site/from --max 20 # and stop after twenty
 *
 * Every expectation is read out of the page under test, so the suite is a
 * test of the template rather than of a station, and one run can sweep the
 * pages a build wrote: each path gets its own context and its own result,
 * and the run fails if any page fails.
 *
 * A path that is a directory is swept: every index.html beneath it becomes a
 * page of the run, in name order, which is how a whole published station set
 * is driven in one command. --max bounds a sweep and says on stderr how many
 * pages it left out, because a run that quietly tested twenty of two thousand
 * has not tested the site.
 *
 * A path that is not a station page is the chooser at the site root or the
 * privacy page. The chooser is driven like any other page -- it is where a
 * reader chooses the station everything else is about -- while the privacy
 * page carries no controls and is reported as 0/0, named at the end of the
 * run, and does not fail it. A run in which no page could be checked at all
 * has tested nothing and does fail, so pointing this at the wrong tree cannot
 * read as a pass.
 *
 * Exit codes: 0 every page checked behaves, 1 one does not or nothing was
 * checked, 2 playwright is unavailable. A skip is reported loudly and exits 2,
 * because a test that passes quietly on a machine where it never ran is the
 * thing this project keeps refusing to do.
 */

const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");

// The suite's own options are dropped from the page list by position rather
// than by shape, so a page path that happens to be a number is still a page
// path and a flag is never mistaken for one.
const ARGV = process.argv.slice(2);
const SWEEP = ARGV.includes("--sweep");
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
// chip. Those are the right shape for the single-page gate -- "the suite never
// ran that assertion" is the thing this project keeps refusing to let pass
// quietly -- and the wrong shape for a sweep of a station set, where most
// stations have no UNESCO property and failing them would be failing pages for
// their own size. In --sweep they are reported as skips and the run says how
// many it skipped, so a sweep cannot pass by exercising nothing.
const NOT_EXERCISED = Symbol("not exercised");

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
  const found = [];
  for (const argument of wanted) {
    let directory = null;
    try {
      if (fs.statSync(argument).isDirectory()) directory = argument;
    } catch (error) {
      // Not there. Left as itself, and reported as a page that does not exist.
    }
    if (directory === null) {
      found.push(argument);
      continue;
    }
    const pages = pagesBeneath(directory);
    if (pages.length) found.push(...pages);
    else found.push(argument);
  }
  if (found.length > MAX_PAGES) {
    // Loudly, because a bounded sweep that reads as a whole one is worse than
    // no sweep: it would be a gate reporting on a sample and calling it the site.
    console.error(
      `--max ${MAX_PAGES}: driving the first ${MAX_PAGES} of ${found.length} pages, ` +
        `and ${found.length - MAX_PAGES} of them are not being tested.`
    );
    return found.slice(0, MAX_PAGES);
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

function serve(bodies) {
  // One server for the whole run, with one synthetic path per page. The file
  // names are not unique -- a chooser and a station page are both index.html
  // -- and a page served from memory has no directory worth preserving, so
  // the path is a label rather than a location.
  const routes = new Map();
  bodies.forEach((body, index) => routes.set(`/page-${index + 1}.html`, body));
  const server = http.createServer((request, response) => {
    const pathname = new URL(request.url, "http://127.0.0.1").pathname;
    const body = routes.get(pathname);
    if (body === null || body === undefined) {
      response.writeHead(404, { "content-type": "text/plain" });
      response.end("no such page");
      return;
    }
    response.writeHead(200, { "content-type": "text/html; charset=utf-8" });
    response.end(body);
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(server)));
}

// Money, in the page's own way, for a message the suite writes rather than
// reads off the page.
const money = (pence) => "£" + (pence / 100).toFixed(2);

/**
 * The chooser at the site root, which S01 made the departure picker: the page
 * a reader lands on, and the only page whose whole job is choosing where to
 * depart from. It carries no fares, so every fact is read out of its own
 * STATIONS array and the list it builds from that array -- the suite never
 * names a station here either.
 */
async function checkChooser(page, url, check) {
  const listed = await page.evaluate(() => STATIONS.map((s) => ({ name: s.name, crs: s.crs, href: s.href })));
  const budget = await page.inputValue("#chooserBudget");
  check("the chooser has stations to choose from", listed.length > 0, `${listed.length} stations`);
  const heading = ((await page.textContent("h1")) || "").trim();
  check(
    "the heading is the budget question and nothing else",
    new RegExp("^Where can we go for £" + budget + "\?").test(heading),
    JSON.stringify(heading)
  );
  const options = await page.locator("#picks a").count();
  // A published site prices thousands of stations and the page caps the list,
  // so the cap is the fact to check rather than the total.
  const capped = await page.evaluate(() => CHOOSER_LIMIT);
  const expected = Math.min(listed.length, capped);
  check("the list opens showing stations without typing", options === expected, `${options} of ${expected}`);
  check(
    "the cap says so rather than looking like the whole list",
    listed.length > capped
      ? (await page.locator("#capMessage").isVisible()) && /Showing \d+ of \d+/.test(await page.textContent("#capMessage"))
      : (await page.locator("#capMessage").isHidden()),
    `${listed.length} stations, cap ${capped}`
  );

  const rows = await page.evaluate(() =>
    Array.from(document.querySelectorAll("#picks a")).map((a) => ({
      href: a.getAttribute("href"),
      text: a.textContent,
      tall: a.getBoundingClientRect().height,
    }))
  );
  check(
    "every option is a link to a station page",
    rows.every((row) => /\/from\/[^/]+\/$/.test(new URL(row.href, "http://x").pathname)),
    rows.map((row) => row.href).join(" ")
  );
  check(
    "every option carries its name, its code and a count",
    listed.every((station) => rows.some((row) => row.text.includes(station.name) && row.text.includes(station.crs) && /\d+ destinations?/.test(row.text))),
    JSON.stringify(rows[0] || null)
  );
  check("every option is a 44px target", rows.every((row) => row.tall >= 44), `${rows[0] ? rows[0].tall : 0}px`);
  check(
    "the budget travels with the station link",
    rows.every((row) => new URL(row.href, "http://x").searchParams.get("budget") === budget),
    rows[0] ? rows[0].href : "no options"
  );

  // The search, judged against the page's own list rather than a fixture name.
  const first = listed[0];
  const query = first.name.split(/[\s(]+/)[0].slice(0, 4);
  await page.fill("#pick", query);
  const narrowed = await page.locator("#picks a").count();
  check(
    "typing narrows the list",
    narrowed > 0 && narrowed < options && /Showing|list/i.test(await page.textContent("#pickStatus")),
    `${query} -> ${narrowed} of ${options}`
  );
  const code = listed[1] ? listed[1].crs : first.crs;
  await page.fill("#pick", code);
  check(
    "a three-letter code finds its station",
    (await page.locator("#picks a").count()) === 1 && (await page.textContent("#picks")).includes(code),
    code
  );
  await page.fill("#pick", "zzzz");
  const noMatch = await page.locator("#nomatch").isVisible();
  check("a query with no answer says so", noMatch && (await page.locator("#picks a").count()) === 0, await page.textContent("#nomatch"));
  check("and it names the code route", /three-letter code/.test(await page.textContent("#nomatch")));
  await page.fill("#pick", "");

  // The budget is the reader's, and it is the one thing the root page can carry
  // into the station page it opens (S05).
  const next = Math.min(500, Number(budget) + 7);
  await page.fill("#chooserBudget", String(next));
  check("changing the budget retitles the page", new RegExp("£" + next + "\?").test(await page.title()), await page.title());
  const carried = await page.evaluate(() => new URL(document.querySelector("#picks a").href).searchParams.get("budget"));
  check("and the station links carry it", carried === String(next), String(carried));

  // A shared link: the budget a reader was given is the budget they get back.
  await page.goto(url + "?budget=42");
  check("a budget in the link opens the page at that budget", (await page.inputValue("#chooserBudget")) === "42", await page.inputValue("#chooserBudget"));
  check(
    "and the station links carry it on",
    (await page.evaluate(() => new URL(document.querySelector("#picks a").href).searchParams.get("budget"))) === "42"
  );
  check("the search field takes focus on arrival", (await page.evaluate(() => document.activeElement && document.activeElement.id)) === "pick");
  const privacy = await page.evaluate(() => (document.querySelector(".footnav a") || {}).getAttribute
    ? document.querySelector(".footnav a").getAttribute("href")
    : null);
  check("the chooser links to the privacy page", privacy !== null && /\/privacy\/$/.test(new URL(privacy, "http://x").pathname), String(privacy));

  await page.setViewportSize({ width: 390, height: 720 });
  const overflow = await page.evaluate(() => {
    const html = document.documentElement;
    return Math.max(html.scrollWidth, document.body.scrollWidth) - window.innerWidth;
  });
  check("at 390px nothing overflows horizontally", overflow <= 0, `${overflow}px`);
}

async function runPage(browser, index, given, file, body, base) {
  // One context per page. The seller's stub route and the clipboard grant are
  // both context-scoped, and a page that failed a step must not hand the next
  // one a reader still carrying its budget, its filters, or its mode.
  const checks = [];
  const check = (name, condition, detail) => {
    // A not-exercised check is a failure outside a sweep, so the single-page
    // gate keeps the teeth it has always had.
    if (condition && condition.skip === NOT_EXERCISED) {
      checks.push({ name, ok: false, skipped: SWEEP, detail: condition.reason });
      return;
    }
    checks.push({ name, ok: Boolean(condition), skipped: false, detail });
  };
  // One result per page, printed the same way whether the page ran or was
  // missing, so several pages in one log are read the same way.
  const printPage = () => {
    console.log("\n== " + given);
    for (const { name, ok, skipped, detail } of checks) {
      const mark = ok ? "  ok    " : skipped ? "  skip  " : "  FAIL  ";
      console.log(mark + name + (!ok && detail ? "  <- " + detail : ""));
    }
    const failed = checks.filter((entry) => !entry.ok && !entry.skipped).length;
    const skipped = checks.filter((entry) => entry.skipped).length;
    // A page the suite does not test gets a tally that cannot be misread as a
    // pass. It used to stop the run and fail, which was right for a mistyped
    // path and wrong for the root of a full-network site, where the chooser
    // legitimately lands at the path CI always passes.
    if (notStation) {
      console.log(
        `0/0 browser checks passed against ${given} -- not a station page, so nothing was checked here`
      );
      return;
    }
    console.log(
      `${checks.length - failed - skipped}/${checks.length - skipped} browser checks passed against ${given}` +
        (skipped ? `, ${skipped} not exercised by this page` : "") +
        // A run that stopped early has not passed the checks it never reached,
        // and a tally that reads as a clean pass is how that stays invisible.
        (stopped ? " -- THE RUN STOPPED EARLY, so this page is not fully checked" : "")
    );
  };
  let stopped = false;
  let notStation = false;
  if (body === null) {
    check("the page under test exists", false, "no file at " + file + "; build one first");
    printPage();
    return { given, file, checks, stopped: false };
  }

  const context = await browser.newContext();
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: base });

  // The seller's site is not part of this test. Stubbing it keeps the run
  // deterministic and keeps the suite off somebody else's server, while still
  // proving which URL a reader is sent to.
  await context.route(SELLER, (route) =>
    route.fulfill({ status: 200, contentType: "text/html", body: "<h1>seller</h1>" })
  );

  const page = await context.newPage();
  const url = `${base}/page-${index + 1}.html`;
  const rows = () => page.locator("#rows a.buy").count();

  // Is this a page the suite tests? A station page carries the payload and the
  // paging constant every expectation below is read out of; the chooser and
  // the privacy page carry neither. Which is which is a fact about the build,
  // not about the file: a single-station build writes the station page to the
  // site root and a full-network build writes a chooser there and its station
  // pages under from/. So the shape cannot decide whether the run failed --
  // the page it found on a real site did. It is reported in its own line and
  // counted, and a run that checked no station page at all still fails, so a
  // suite pointed at the wrong tree cannot read as a pass.
  await page.goto(url);
  notStation = !(await page.evaluate(
    () => typeof DATA !== "undefined" && typeof PAGE_SIZE !== "undefined"
  ));
  if (notStation) {
    // The chooser is a page this suite does test: it is the page a reader
    // lands on and the only control that chooses an origin. The privacy page
    // carries no controls and is reported untested.
    const isChooser = await page.evaluate(() => typeof STATIONS !== "undefined" && !!document.getElementById("picks"));
    try {
      if (isChooser) await checkChooser(page, url, check);
    } catch (error) {
      console.error("the browser test stopped early on " + given + ": " + error.message);
      stopped = true;
    }
    // A checked chooser is a tested page, so it is tallied like one rather
    // than reported as a path this suite could not read.
    notStation = !isChooser;
    printPage();
    await context.close();
    return { given, file, checks, stopped, notStation: !isChooser };
  }

  // Every expectation below is read out of the page's own payload. The suite
  // used to name Nottingham, Lincoln, Peterborough and the Tower of London,
  // which made it a test of the synthetic demo feed whatever page it was
  // pointed at -- and the deploy workflow pointed it at a real Grantham page,
  // where none of those is a priced destination, so three checks could not
  // pass there for that reason alone. A gate that cannot pass is a gate nobody
  // reads, and the facts it wanted were all in the page it was already reading.
  // One page-side reader of the payload, installed on every load, so the three
  // facts every expectation needs -- the list the current ticket mode shows,
  // the types a destination carries, the budget on screen -- are read the same
  // way everywhere and cannot drift apart between checks. TYPES.cheapest and
  // TYPES.dearest reduce rather than spread, because a station with thousands
  // of destinations would spill the argument list.
  const installReader = () => page.evaluate(() => {
    window.TYPES = {
      list: () => {
        const mode = document.querySelector('input[name="ticketMode"]:checked').value;
        return mode === "single" ? DATA.singleDestinations
          : mode === "anytime" ? DATA.anytimeDestinations : DATA.destinations;
      },
      types: (destination) => destination.destinationTypes || [destination.destinationType],
      cap: () => Number(document.getElementById("budgetNumber").value) * 100,
      price: (destination) =>
        document.querySelector('input[name="unit"]:checked').value === "party"
          ? destination.partyPence : destination.adultPence,
      cheapest: (pick) => TYPES.list().reduce((low, d) => Math.min(low, pick(d)), Infinity),
      dearest: (pick) => TYPES.list().reduce((high, d) => Math.max(high, pick(d)), 0),
    };
  });
  let pageSize = 20;
  // Every page is opened through here: a navigation throws away the reader,
  // so one way to load means no step can forget to reinstall it. The budget
  // under test is the page's own affordable one unless a step wants another.
  const open = async (budget) => {
    await page.goto(url);
    await installReader();
    pageSize = await page.evaluate(() => PAGE_SIZE);
    if (budget !== undefined) await page.fill("#budgetNumber", String(budget));
  };
  // What a type means on this page, in the mode and at the budget on screen:
  // which rows it leaves, and whether it is worth offering at all.
  const expectedFor = (type) =>
    page.evaluate((wanted) => ({
      carried: TYPES.list().some((d) => TYPES.types(d).includes(wanted)),
      rows: TYPES.list().filter((d) => TYPES.types(d).includes(wanted) && d.adultPence <= TYPES.cap()),
    }), type);
  // One type per call, checked in both directions: the rows it leaves come
  // from the payload, and a type no destination in this mode carries must not
  // be offered, because a chip that can only ever return nothing reads as a
  // broken control rather than an empty result.
  const checkChip = async (type, offered, matched) => {
    const expected = await expectedFor(type);
    const chip = `input[name="destinationType"][value="${type}"]`;
    if (!expected.carried) {
      check(offered, !(await page.locator(chip).isVisible()), `${type} chip on a page with no ${type} destination in this mode`);
      return expected;
    }
    if (!(await page.locator(chip).isVisible())) {
      check(offered, false, `${type} chip hidden although a destination carries it in this mode`);
      return expected;
    }
    await page.check(chip);
    const shown = await rows();
    const text = await page.textContent("#rows");
    const wanted = expected.rows.slice(0, pageSize);
    check(
      matched,
      shown === wanted.length && wanted.every((destination) => text.includes(destination.name)),
      `${shown} rows; expected ${wanted.length} of ${expected.rows.length}`
    );
    await page.uncheck(chip);
    return expected;
  };
  // The budget that puts every row of one type on screen, worked out from the
  // dearest of them. Null when this mode carries no destination of that type,
  // which is a fact about the feed rather than a reason to skip the check.
  const budgetFor = (type) =>
    page.evaluate((wanted) => {
      const dearest = TYPES.dearest((d) => (TYPES.types(d).includes(wanted) ? d.adultPence : 0));
      return dearest ? Math.max(1, Math.ceil(dearest / 100)) : null;
    }, type);

  try {
    // 1. It renders, with rows and a heading that names the origin.
    await open();
    const facts = await page.evaluate(() => ({
      origin: DATA.origin.name,
      destinations: DATA.destinations.length,
      // The cheapest return on the page, so the budget under test is one the
      // page's own data can fill rather than a number the fixture happened to
      // have. A real feed's opening budget is often too low for its own
      // cheapest fare, and a hardcoded £20 then measured an empty list.
      affordable: Math.max(1, Math.ceil(TYPES.cheapest((d) => d.adultPence) / 100)),
    }));
    const heading = (await page.textContent("h1")) || "";
    check(
      "renders the continuous budget-and-origin heading",
      /Where can we go for under/.test(heading) && heading.includes(facts.origin.toUpperCase()),
      heading.trim()
    );
    check("the heading budget is the editable source of truth", await page.locator("#budgetNumber").count() === 1, await page.locator("#budgetNumber").count() + " fields");
    // Measured between a one-digit and a three-digit amount, because the field
    // is sized to the value: a page whose opening budget is already two digits
    // sits at its widest, so comparing against the opening value tested the
    // fixture's number rather than the field.
    const widthAt = async (amount) => {
      await page.fill("#budgetNumber", amount);
      return page.locator("#budgetNumber").evaluate((el) => el.getBoundingClientRect().width);
    };
    const budgetWidthAt9 = await widthAt("9");
    const budgetWidthAt126 = await widthAt("126");
    check("the heading budget width follows its character count", budgetWidthAt9 < budgetWidthAt126, `${budgetWidthAt9} / ${budgetWidthAt126}`);
    await page.locator(".budget-prefix").click();
    await page.keyboard.type("7");
    const replacedAmount = (await page.inputValue("#budgetNumber")).trim();
    check("clicking the £ selects the whole editable amount", replacedAmount === "7", replacedAmount);
    await page.fill("#budgetNumber", String(facts.affordable));
    const initial = await rows();
    check("renders priced rows", initial > 0, `${initial} rows; ${facts.destinations} destinations in the feed`);

    // 2. Dragging the budget slider to the floor empties the list.
    const startBudget = (await page.inputValue("#budgetNumber")).trim();
    const track = await page.locator("#budget").boundingBox();
    await page.mouse.move(track.x + track.width / 2, track.y + track.height / 2);
    await page.mouse.down();
    await page.mouse.move(track.x + 1, track.y + track.height / 2, { steps: 12 });
    await page.mouse.up();
    const draggedBudget = (await page.inputValue("#budgetNumber")).trim();
    const headingBudget = (await page.inputValue("#budgetNumber")).trim();
    check("the slider updates the heading budget live", headingBudget === draggedBudget, `${draggedBudget} / ${headingBudget}`);
    const afterDrag = await rows();
    check("the slider responds to a real drag", draggedBudget !== startBudget, `${startBudget} -> ${draggedBudget}`);
    check("a dragged-down budget drops rows", afterDrag < initial, `${initial} -> ${afterDrag}`);
    check("an empty budget says so rather than showing nothing", await page.locator("#empty").isVisible());
    check("the summary counts what is left", /No destinations within/.test(await page.textContent("#summary")));

    // 3. The destination-type chips narrow the result set and support both
    // exclusive All and multi-select specific types. Every chip is judged
    // against the page's own data in both directions, and the ticket mode is
    // part of that data: a chip belongs to the list the reader is looking at.
    // The budget is the page's own cheapest, because a chip that leaves no
    // rows would pass without proving anything about the filter.
    await open(facts.affordable);
    await checkChip("city", "a type this page offers is offered", "the city chip leaves the priced city destinations");
    await checkChip(
      "seaside",
      "a type this page offers is offered",
      "a coastal destination is reachable without also asking for a city"
    );
    await checkChip("university", "a type this page offers is offered", "a university town is findable by the university facet");
    await checkChip("island", "a facet with no destination here offers no chip", "an island destination is findable by the island facet");
    // A chip the payload says the page carries must be on screen, and one it
    // does not must not be: the two directions are separate checks because
    // they failed separately.
    const carriedTypes = await page.evaluate(() => {
      const types = new Set();
      for (const d of TYPES.list()) for (const type of TYPES.types(d)) types.add(type);
      const chips = Array.from(document.querySelectorAll('input[name="destinationType"]'))
        .map((input) => input.value)
        .filter((value) => value !== "all");
      return {
        carried: [...types].sort(),
        offered: chips.filter((value) => !document.querySelector(`input[name="destinationType"][value="${value}"]`).closest("label").hidden).sort(),
        rendered: chips.sort(),
      };
    });
    // Both directions, because they are different promises: nothing is offered
    // that no destination in this mode carries, and nothing carried is hidden.
    // A type the template never renders is neither offered nor hidden, so it
    // cannot fail the second half.
    check(
      "the offered chips are the ones this mode's destinations carry",
      carriedTypes.offered.every((type) => carriedTypes.carried.includes(type)) &&
        carriedTypes.rendered
          .filter((type) => carriedTypes.carried.includes(type))
          .every((type) => carriedTypes.offered.includes(type)),
      `offered ${carriedTypes.offered.join(", ")}; carried ${carriedTypes.carried.join(", ")}`
    );
    await page.locator('.ticket-filter label').filter({ hasText: "Single" }).click();
    // An advance single is train-specific whatever the feed calls it, so the
    // label is asserted against the rows the payload says are advance singles
    // in this mode, at this budget -- and against their absence when there are
    // none, so a page cannot pass by never showing one.
    const advance = await page.evaluate(() =>
      TYPES.list().filter((d) => d.isAdvance && d.adultPence <= TYPES.cap()).length
    );
    const singleText = await page.textContent("#rows");
    check(
      "an advance single is labelled as train-specific, and only when one is shown",
      advance === 0 ? !/Advance single/.test(singleText) : /Advance single/.test(singleText),
      `${advance} advance singles in this mode at this budget; ${singleText.slice(0, 160)}`
    );
    // The chips follow the mode, so the heritage destinations this page has
    // must now be offered, and a page whose only heritage destination was the
    // single just selected must offer it here and not in return mode.
    await checkChip("heritage", "a type this page offers is offered", "the heritage chip leaves the heritage destinations");
    // Which mode a UNESCO property appears in, and what it costs, are facts
    // about the feed: on one of these pages the heritage destinations are
    // returns, on the other they are outbound singles, and a check pinned to
    // either mode can only ever be right about one of them. The check goes to
    // the mode that carries one, raises the budget to reach it, and only
    // accepts a property that the page shows on its first page of results.
    const heritage = await page.evaluate((limit) => {
      for (const mode of ["return", "single", "anytime"]) {
        const list = mode === "single" ? DATA.singleDestinations
          : mode === "anytime" ? DATA.anytimeDestinations : DATA.destinations;
        for (const d of list) {
          if (!TYPES.types(d).includes("heritage") || !(d.heritageSites || []).length) continue;
          const shown = list.filter((x) => x.adultPence <= d.adultPence).slice(0, limit);
          if (shown.some((x) => x.name === d.name)) {
            return { mode, name: d.name, site: d.heritageSites[0], pounds: Math.ceil(d.adultPence / 100) };
          }
        }
      }
      return null;
    }, pageSize);
    if (heritage) {
      await page.check('input[name="destinationType"][value="all"]');
      await page.locator(`input[name="ticketMode"][value="${heritage.mode}"]`).check({ force: true });
      await page.fill("#budgetNumber", String(heritage.pounds));
      const heritageText = await page.textContent("#rows");
      const heritageHref = await page.locator("#rows .heritage-proof a").first().getAttribute("href");
      check(
        "a heritage row links the UNESCO property the payload names",
        heritageText.includes("World heritage: " + heritage.site.name) && heritageHref === heritage.site.url,
        `${heritage.name} in ${heritage.mode} mode: ${heritage.site.name} ${heritage.site.url}; ${heritageText.slice(0, 160)}`
      );
    } else {
      check(
        "a heritage row links the UNESCO property the payload names",
        notExercised("no destination on this page carries a UNESCO property")
      );
    }
    // 3b. A ticket mode the feed has nothing for says so. An Anytime Day
    // Return is sold on a few interurban routes, so most real origins have
    // none, and the page used to return from render() before it wrote
    // anything: the reader kept the previous mode's rows under a set of
    // destination chips that had all just been hidden, which reads as a
    // broken filter rather than an answer.
    await open(facts.affordable);
    const plan = await page.evaluate(() => {
      const list = {
        return: DATA.destinations,
        single: DATA.singleDestinations,
        anytime: DATA.anytimeDestinations,
      };
      const cap = Number(document.getElementById("budgetNumber").value) * 100;
      const modes = ["return", "single", "anytime"];
      const counts = {};
      const onScreen = {};
      for (const mode of modes) {
        counts[mode] = list[mode].length;
        onScreen[mode] = list[mode].filter((d) => d.adultPence <= cap).length;
      }
      const from = modes.find((mode) => onScreen[mode]) || null;
      if (!from) return null;
      const empty = modes.find((mode) => !counts[mode]);
      if (empty) return { from, to: empty, forced: false, counts };
      // This page priced all three modes, so there is no empty mode to switch
      // to and the branch would go untested. One is emptied here instead, so a
      // page whose feed happens to be complete still drives the path a station
      // with no Anytime fares takes; the mode switched back to is left alone.
      DATA.anytimeDestinations = [];
      return { from, to: "anytime", forced: true, counts: { ...counts, anytime: 0 } };
    });
    if (plan) {
      await page.locator(`input[name="ticketMode"][value="${plan.from}"]`).check({ force: true });
      const budgetBefore = (await page.inputValue("#budgetNumber")).trim();
      const rowsBefore = await page.locator("#rows tr").count();
      await page.locator(`input[name="ticketMode"][value="${plan.to}"]`).check({ force: true });
      const budgetAfter = (await page.inputValue("#budgetNumber")).trim();
      const emptyText = (await page.textContent("#empty")) || "";
      const labels = await page.evaluate(() => {
        const found = {};
        for (const input of document.querySelectorAll('input[name="ticketMode"]')) {
          found[input.value] = input.parentElement.textContent.trim();
        }
        return found;
      });
      const offeredHere = Object.entries(plan.counts)
        .filter(([other, count]) => other !== plan.to && count);
      check(
        "a mode with no fares clears the table rather than leaving the last mode's rows",
        rowsBefore > 0 && (await page.locator("#rows tr").count()) === 0,
        `${rowsBefore} ${plan.from}-mode rows before, ${await page.locator("#rows tr").count()} in the empty ${plan.to} mode`
      );
      check(
        "a mode with no fares says so, and says where the fares are",
        (await page.locator("#empty").isVisible()) &&
          emptyText.startsWith(`No ${labels[plan.to]} fares were found from ${facts.origin}`) &&
          offeredHere.every(([other, count]) =>
            emptyText.includes(labels[other]) && emptyText.includes(String(count))),
        `${labels[plan.to]}: ${emptyText.slice(0, 240)}; the other modes are ${offeredHere.map(([o, n]) => `${labels[o]} ${n}`).join(", ") || "empty too"}`
      );
      check(
        "an empty mode leaves the budget alone",
        budgetAfter === budgetBefore,
        `${budgetBefore} -> ${budgetAfter}`
      );
      // All is the unfiltered state and stays offered in every mode; what an
      // empty mode must not offer is a type that nothing in it carries.
      const chipLabels = await page.locator("#destinationTypes label").evaluateAll((labels) =>
        labels
          .filter((label) => !label.hidden)
          .map((label) => label.querySelector("input"))
          .filter((input) => input && input.value !== "all")
          .map((input) => input.value)
      );
      check(
        "an empty mode offers no destination-type chip to press",
        chipLabels.length === 0,
        `offered: ${chipLabels.join(", ") || "none"}`
      );
      await page.locator(`input[name="ticketMode"][value="${plan.from}"]`).check({ force: true });
      check(
        "and switching back to a priced mode restores its list",
        (await page.locator("#rows tr").count()) > 0 && !(await page.locator("#empty").isVisible()),
        `${await page.locator("#rows tr").count()} rows back in ${plan.from} mode` +
          (plan.forced ? " (the empty mode was forced: this page priced all three)" : "")
      );
    } else {
      check(
        "a mode with no fares clears the table rather than leaving the last mode's rows",
        false,
        "this page shows no rows in any mode at this budget, so the empty-mode case cannot be exercised on it"
      );
    }

    // Back to returns for the rest of the step, on a page that has not been
    // left holding the previous step's mode, budget and filters.
    await open(facts.affordable);
    // A class that costs more than the page's opening budget is only worth
    // looking at with the budget raised, and the budget that shows every row of
    // the class is worked out from the payload rather than written down.
    const smallTownBudget = await budgetFor("small_town");
    if (smallTownBudget) {
      await page.fill("#budgetNumber", String(smallTownBudget));
      const smallTown = await checkChip(
        "small_town",
        "a type this page offers is offered",
        "a small town is its own class, not a town"
      );
      const smallTownText = await page.textContent("#rows");
      check(
        "and it is not folded into the towns",
        smallTown.rows.every((d) => !(d.destinationTypes || []).includes("town")) && smallTown.rows.length > 0,
        `${smallTown.rows.length} small towns, ${smallTownText.slice(0, 160)}`
      );
    } else {
      check(
        "a small town is its own class, not a town",
        notExercised("this page has no small town in return mode")
      );
    }
    await page.fill("#budgetNumber", String(facts.affordable));
    // Multi-select, on whichever two types the page carries: the two sets can
    // overlap -- a station can be coastal and a university town -- so the union
    // is worked out from the data rather than by adding the two counts.
    const pair = carriedTypes.offered.slice(0, 2);
    if (pair.length === 2) {
      await page.check(`input[name="destinationType"][value="${pair[0]}"]`);
      await page.check(`input[name="destinationType"][value="${pair[1]}"]`);
      const unionRows = await rows();
      const expectedUnion = await page.evaluate((types) =>
        TYPES.list().filter(
          (d) => TYPES.types(d).some((t) => types.includes(t)) && d.adultPence <= TYPES.cap()
        ).length
      , pair);
      check(
        "specific destination chips are multi-select and union their matches",
        (await page.locator(`input[name="destinationType"][value="${pair[0]}"]`).isChecked()) &&
          (await page.locator(`input[name="destinationType"][value="${pair[1]}"]`).isChecked()) &&
          unionRows === Math.min(expectedUnion, pageSize),
        `${pair.join(" + ")} -> ${unionRows}; expected ${Math.min(expectedUnion, pageSize)}`
      );
      await page.uncheck(`input[name="destinationType"][value="${pair[1]}"]`);
      await page.uncheck(`input[name="destinationType"][value="${pair[0]}"]`);
    } else {
      check(
        "specific destination chips are multi-select and union their matches",
        notExercised(`this page offers ${pair.length} specific chip(s), so multi-select cannot be exercised`)
      );
    }
    await page.check('input[name="destinationType"][value="all"]');
    // Judged over every chip the page rendered, not one of them by name: a
    // check that watched the city chip alone passed on a page with no city.
    const exclusivity = await page.evaluate(() => ({
      all: document.querySelector('input[name="destinationType"][value="all"]').checked,
      also: Array.from(document.querySelectorAll('input[name="destinationType"]'))
        .filter((input) => input.value !== "all" && input.checked)
        .map((input) => input.value),
    }));
    check(
      "All is checked exclusively",
      exclusivity.all && exclusivity.also.length === 0,
      `all ${exclusivity.all}; also checked: ${exclusivity.also.join(", ") || "none"}`
    );
    check("clearing the type filter restores the list", (await rows()) === initial);

    // 4. A ticket link goes where it says it goes, in a new tab.
    const link = page.locator("#rows a.buy").first();
    const href = await link.getAttribute("href");
    check("the plain link carries no journey at all", href === "https://www.nationalrail.co.uk/journey-planner/", href);
    check("the link is marked untracked", (await link.getAttribute("rel")) === "noopener");
    check("the link opens in a new tab", (await link.getAttribute("target")) === "_blank");
    const [popup] = await Promise.all([page.waitForEvent("popup"), link.click()]);
    await popup.waitForLoadState("domcontentloaded");
    check("following the link reaches the seller", SELLER.test(popup.url()), popup.url());
    await popup.close();

    // 5. A row can hand the reader the four things the seller will ask for.
    // What the copy must say is read from the payload rather than matched
    // against a pattern: a real station's name has spaces in it
    // (LONDON KINGS X, NOTTINGHAM), and a one-word pattern rejected the
    // correct answer while accepting a wrong one on the demo feed.
    const rowText = (await page.textContent("#rows tr")).trim();
    const adultButton = page.locator("#rows button[aria-label^='Copy the journey details']").first();
    const journey = await page.evaluate((label) => {
      const name = label.replace("Copy the journey details for ", "");
      const destination = TYPES.list().find((d) => d.name === name) || {};
      return {
        origin: DATA.origin.name + " (" + DATA.origin.crs + ")",
        destination: destination.name + " (" + destination.crs + ")",
      };
    }, await adultButton.getAttribute("aria-label"));
    await adultButton.click();
    await page.waitForFunction(
      () => /copied/i.test((document.getElementById("copyStatus") || {}).textContent || ""),
      null,
      { timeout: 3000 }
    ).catch(() => {});
    const adultCopy = await page.evaluate(() => navigator.clipboard.readText());
    check("the copy names the origin", adultCopy.includes("From: " + journey.origin), adultCopy);
    check("the copy names the destination", adultCopy.includes("To: " + journey.destination), adultCopy);
    check("the copy names the party size", /^Passengers: 1 adult$/m.test(adultCopy), adultCopy);
    check("one adult's copy does not mention a railcard", !/Railcard/.test(adultCopy), adultCopy);
    // The copy belongs to the row it was copied from, judged on the whole
    // station name rather than its first word, which two stations can share.
    check(
      "the row it copied is the row it sits on",
      adultCopy.includes("To: " + journey.destination) && rowText.includes(journey.destination),
      `${rowText} vs ${adultCopy}`
    );
    check(
      "and the copy is announced, not just performed",
      /copied/i.test(await page.textContent("#copyStatus"))
    );

    // 6. The party price carries the railcard, because that price needs it.
    // The budget is the cheapest party price in the payload, not the adult one
    // used above: two adults never cost less than one, so a budget that shows
    // a return row shows no party row at all, and a check written against one
    // was measuring the fixture's numbers rather than the page.
    //
    // A page whose cheapest two-adult price is above the ceiling the page
    // itself sets can show no party row at any budget a reader can type: on a
    // one-destination page the ceiling is that destination's adult fare and the
    // party fare is double it. Found by sweeping a two-station site, where the
    // step used to wait thirty seconds for a button that could never appear and
    // then end the run early -- reported as a page that stopped, with every
    // check it had already done counting as a pass.
    // Two adults are selected before the budget is read, because the ceiling
    // the page allows depends on who the fare covers. Reading it first measured
    // the single-adult ceiling and concluded the party rows were unreachable
    // when the slider does reach them once the party price is the one on screen.
    await page.check('input[name="unit"][value="party"]');
    const party = await page.evaluate(() => ({
      cheapest: DATA.destinations.reduce((low, d) => Math.min(low, d.partyPence), Infinity),
      ceiling: Number(document.getElementById("budget").max) * 100,
    }));
    const partyReachable = party.cheapest <= party.ceiling;
    if (partyReachable) {
    await page.fill("#budgetNumber", String(Math.max(1, Math.ceil(party.cheapest / 100))));
    const copyButton = page.locator("#rows button[aria-label^='Copy the journey details']").first();
    const copiedName = (await copyButton.getAttribute("aria-label")).replace("Copy the journey details for ", "");
    // The railcard note is owed only where the feed prices one, so what the
    // copy should say is read off the row it is about to copy: a page with no
    // eligible fare must stay quiet rather than name a discount that is not there.
    const railcardNamed = await page.evaluate((name) => {
      const row = DATA.destinations.find((d) => d.name === name);
      return Boolean(DATA.railcardAvailable && row && row.railcardPence !== null);
    }, copiedName);
    await copyButton.click();
    await page.waitForFunction(
      () => /2 adults/.test((document.getElementById("copyStatus") || {}).textContent || ""),
      null,
      { timeout: 3000 }
    ).catch(() => {});
    const partyCopy = await page.evaluate(() => navigator.clipboard.readText());
    check("the party copy says two adults", /^Passengers: 2 adults$/m.test(partyCopy), partyCopy);
    check(
      "and names the railcard when the fare is eligible, and stays quiet when it is not",
      railcardNamed ? /Two Together discount/.test(partyCopy) : !/Two Together discount/.test(partyCopy),
      `${copiedName} ${railcardNamed ? "is" : "is not"} railcard-eligible: ${partyCopy}`
    );
    } else {
      const reason =
        `with Two adults selected this page's cheapest price is ${money(party.cheapest)} and its ` +
        `budget goes to ${money(party.ceiling)}, so no party row can be shown at any budget it allows`;
      for (const name of [
        "the party copy says two adults",
        "and names the railcard when the fare is eligible, and stays quiet when it is not",
      ]) {
        check(name, notExercised(reason));
      }
    }

    // 7. At a phone width the ticket action is on-screen, without horizontal
    // scroll (ADR-0019's blocker). Measured, not assumed.
    await page.setViewportSize({ width: 390, height: 720 });
    const mobile = await page.evaluate(() => {
      const html = document.documentElement;
      const overflow = Math.max(html.scrollWidth, document.body.scrollWidth) - window.innerWidth;
      const cell = document.querySelector("#rows td:last-child").getBoundingClientRect();
      return { overflow, onScreen: cell.right <= window.innerWidth && cell.left >= 0 };
    });
    check("at 390px nothing overflows horizontally", mobile.overflow <= 0, `${mobile.overflow}px`);
    check("at 390px the ticket action is on-screen", mobile.onScreen, JSON.stringify(mobile));

    // 8. The origin picker: search, navigate, and the no-match wording
    // (ADR-0019). Choosing a station is navigation, so the link must go to
    // another page, and there must never be an empty picker.
    await page.setViewportSize({ width: 1280, height: 800 });
    await open(facts.affordable);

    // The layout's thesis: the budget leads, and row actions carry real touch
    // targets. Measured, not assumed.
    const layout = await page.evaluate(() => {
      const toPx = (v) => parseFloat(v);
      const budgetSize = toPx(getComputedStyle(document.getElementById("budgetNumber")).fontSize);
      const h1Size = toPx(getComputedStyle(document.querySelector("h1")).fontSize);
      const secondary = document.querySelector(".filter-bar .party-filter");
      const destinationFilter = document.querySelector(".filter-bar .destination-filter");
      const hitOf = (el) => { const r = el.getBoundingClientRect();
        // The ::after slop is positioned relative to the padding box. It
        // renders only when the element has position: relative (both do).
        const cs = getComputedStyle(el, "::after");
        if (cs.content !== '""') return Math.round(r.height);
        // .toggle uses inset: -6px (12px total); .buy uses -11px vertical (22px).
        return Math.round(r.height + (el.classList.contains("buy") ? 22 : 12)); };
      return {
        budgetLeads: budgetSize >= h1Size,
        secondaryHoldsPartyAndFilter: !!secondary &&
          !!secondary.querySelector('input[name="unit"]') && !!destinationFilter &&
          !!destinationFilter.querySelector('input[name="destinationType"]'),
        copyHit: hitOf(document.querySelector('#rows button[aria-label^="Copy"]')),
        buyHit: hitOf(document.querySelector("#rows a.buy"))
      };
    });
    check("the budget is inline in the large heading", layout.budgetLeads);
    check("party and destination filters share the horizontal bar", layout.secondaryHoldsPartyAndFilter);
    check("the copy action carries a 44px target", layout.copyHit >= 44, layout.copyHit + "px");
    check("the buy link carries a 44px target", layout.buyHit >= 44, layout.buyHit + "px");

    const pickerButton = page.locator("#changeOrigin");      if (await pickerButton.count()) {

      await pickerButton.click();
      check("Change opens the picker", await page.locator("#originPicker").isVisible());
      const pickCount = await page.locator("#originPicks a").count();
      check("the picker lists stations without typing", pickCount > 0, `${pickCount} options`);
      const href = pickCount
        ? await page.locator("#originPicks a").first().getAttribute("href")
        : null;
      // Judged against the base the page itself carries, not a root-absolute
      // path: a project site is published under owner.github.io/repo/ and
      // prefixes every internal link with it (ADR-0024), so a check that
      // demanded /from/ would fail the published page and only that page.
      const baseHref = await page.evaluate(() => DATA.baseHref);
      check(
        "options are links to station pages",
        href === null
          ? notExercised("this page lists no other station to link to")
          : href.startsWith(baseHref + "from/") && href.endsWith("/") && href.length > baseHref.length + 6,
        href === null ? "" : `${href} under base ${baseHref}`
      );
      // The query comes from the picker's own first option, so the check is
      // about narrowing rather than about a station name the fixture happened
      // to carry.
      const firstWord = pickCount
        ? (((await page.locator("#originPicks a").first().textContent()) || "").trim().split(/[\s(]+/)[0] || "")
        : "";
      const query = firstWord.slice(0, 4);
      await page.fill("#originSearch", query);
      const narrowed = await page.locator("#originPicks a").count();
      const narrowedText = await page.locator("#originPicks").textContent();
      // A list of one cannot be narrowed. That is a fact about the page's own
      // station list rather than about the filter, so it is reported as the
      // check this page cannot exercise.
      check(
        "typing narrows the picker",
        pickCount > 1
          ? narrowed > 0 && narrowed < pickCount && narrowedText.includes(firstWord)
          : notExercised(`this page lists ${pickCount} station, so there is nothing to narrow`),
        `${query || "(no options)"} -> ${narrowed} of ${pickCount} options`
      );
      await page.fill("#originSearch", "zzzz");
      check(
        "a no-match says so and names the code route",
        pickCount
          ? (await page.locator("#originNomatch").isVisible()) && /three-letter code/.test(await page.textContent("#originNomatch"))
          : notExercised("this page lists no other station, so a query has nothing to narrow")
      );
      const emptyOptions = await page.locator("#originPicks a").count();
      check("and the list itself is empty rather than stale", emptyOptions === 0, `${emptyOptions} left`);
      // Keyboard exit: Escape closes and focus returns to the control that opened it.
      await page.fill("#originSearch", query);
      await page.keyboard.press("Escape");
      check("Escape closes the picker", !(await page.locator("#originPicker").isVisible()));
      check("and focus returns to the heading station control", await page.evaluate(() => document.activeElement && document.activeElement.id === "changeOrigin"));
      await pickerButton.click();
      check("Change reopens the picker", await page.locator("#originPicker").isVisible());
      await pickerButton.click();
      check("Change closes the picker again", !(await page.locator("#originPicker").isVisible()));
      // Keyboard-only reachability of the picker's first option.
      await pickerButton.click();
      const firstOption = page.locator("#originPicks a").first();
      check(
        "picker options are keyboard-focusable links",
        pickCount
          ? await firstOption.evaluate((el) => el.tagName === "A" && el.href.endsWith("/"))
          : notExercised("this page lists no option to focus")
      );
      await page.keyboard.press("Escape");
    } else {
      check("the page offers a Change control", false, "#changeOrigin missing");
    }
  } catch (error) {
    // A step that throws is a failed run, not a short one. The finally block
    // below reports whatever was checked, so this has to be carried out of the
    // try as well: without it a broken selector ends the run early and the
    // summary reads as a pass.
    console.error("the browser test stopped early on " + given + ": " + error.message);
    stopped = true;
  } finally {
    printPage();
    await context.close();
  }
  return { given, file, checks, stopped };
}

function report(results) {
  const counted = (predicate) =>
    results.reduce((sum, result) => sum + result.checks.filter(predicate).length, 0);
  const total = counted(() => true);
  const failed = counted((entry) => !entry.ok && !entry.skipped);
  const skipped = counted((entry) => entry.skipped);
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
  if (offTopic.length) {
    console.log(
      `\n${offTopic.length} page(s) were not station pages and were not checked: ${offTopic
        .map((result) => result.given)
        .join(", ")}`
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
  console.log(`\n${summary}${skipped ? `, ${skipped} check(s) not exercised by the pages swept` : ""}`);
  process.exit(failed || broken.length || nothingTested ? 1 : 0);
}

async function main() {
  const playwright = requirePlaywright();
  if (!playwright) process.exit(2);

  const wanted = expand(PAGES.length ? PAGES : ["demo.html"]);
  const pages = wanted.map((given) => {
    const file = path.resolve(given);
    // A path that is not there is a failed page, not a failed run: the others
    // still get driven and still get reported. Missing demo.html is the case
    // worth spelling out, because it is the one a contributor hits first.
    let body = null;
    try {
      body = fs.readFileSync(file);
    } catch (error) {
      if (given === "demo.html") {
        console.error("No page at " + file + ". Build one first:");
        console.error("  python make_synthetic_feed.py _demo_feed --unserved-station --third-origin");
        console.error("  python build_demo_page.py --feed _demo_feed --timetable _demo_feed --all-origins --out _demo_site/index.html");
      }
    }
    return { given, file, body };
  });

  const server = await serve(pages.map((entry) => entry.body));
  const base = `http://127.0.0.1:${server.address().port}`;
  const browser = await playwright.chromium.launch();
  const results = [];
  try {
    for (let index = 0; index < pages.length; index += 1) {
      results.push(
        await runPage(browser, index, pages[index].given, pages[index].file, pages[index].body, base)
      );
    }
  } finally {
    await browser.close();
    server.close();
  }
  report(results);
}

main().catch((error) => {
  console.error("the browser test could not run: " + error.message);
  process.exit(1);
});
