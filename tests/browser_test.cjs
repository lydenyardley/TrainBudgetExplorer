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
 * read as a pass. A run in which too much of the suite had nothing to
 * exercise fails too: skips are reported, and a stated fraction of them is the
 * most a run may skip, so a fixture that has quietly stopped exercising the
 * page cannot look green. That fraction is the same in every mode, so a
 * single page and a sweep are held to one standard.
 *
 * Exit codes: 0 every page checked behaves, 1 one does not, nothing was
 * checked, or the run skipped more than its budget, 2 playwright is
 * unavailable. A skip is reported loudly and exits 2, because a test that
 * passes quietly on a machine where it never ran is the thing this project
 * keeps refusing to do.
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

/**
 * The chooser at the site root, which S01 made the departure picker: the page
 * a reader lands on, and the only page whose whole job is choosing where to
 * depart from. It carries no fares, so every fact is read out of its own
 * STATIONS array and the list it builds from that array -- the suite never
 * names a station here either.
 */
async function checkChooser(page, url, check) {
  const listed = await page.evaluate(() => STATIONS.map((s) => ({ name: s.name, crs: s.crs, href: s.href })));
  const budget = await page.inputValue("#budgetNumber");
  check("the chooser has stations to choose from", listed.length > 0, `${listed.length} stations`);
  // The heading is a station page's heading with a field where the station's
  // name goes: the same question, the same two slots, and the slot this route
  // has no answer for is a text field rather than a name to click. Read out of
  // the page rather than matched against a sentence written here, because the
  // point is that the two routes have not drifted apart. C15 and C21: the
  // figure in the heading is written from the same resolved budget as the
  // field, the tab title and every outgoing link, and the wording is the
  // inclusive one.
  const heading = await page.evaluate(() => {
    const el = document.getElementById("pageHeading");
    // The sentence a reader sees, which is not the heading's textContent: an
    // input carries no text, so reading textContent alone compares against a
    // sentence with both the budget and the station missing from it. Each
    // field's value is written where the field sits, and the hidden text that
    // exists only for a screen reader's name is left out.
    const seen = (node) => {
      let out = "";
      for (const child of node.childNodes) {
        if (child.nodeType === Node.TEXT_NODE) out += child.textContent;
        else if (child.nodeType === Node.ELEMENT_NODE && !child.classList.contains("sr-only")) {
          out += child.tagName === "INPUT" ? child.value : seen(child);
        }
      }
      return out;
    };
    return {
      text: seen(el).replace(/\u2060/g, "").replace(/\s+/g, " ").trim(),
      field: (document.getElementById("budgetNumber") || {}).value || "",
      slot: Boolean(el.querySelector(".origin-slot")),
      placeholder: (document.getElementById("originSearch") || {}).placeholder || "",
    };
  });
  check(
    "the heading is the sentence a station page carries, with a field where its name goes",
    new RegExp("^Train fares\\s*\\u00b7\\s*up to £" + heading.field + "\\s*\\u00b7\\s*from$").test(heading.text),
    JSON.stringify(heading)
  );
  check(
    "and the station it has no answer for is a field holding the word station",
    heading.slot && heading.placeholder === "station",
    JSON.stringify(heading)
  );
  // A placeholder is text a reader has to read, so it is measured like text:
  // muted is the design call, and still meeting AA is the floor under it. The
  // colour is painted onto a canvas over the page rather than parsed out of
  // the computed string, so whatever notation the browser reports it in, this
  // measures the pixels a reader sees.
  const placeholderInk = await page.evaluate(() => {
    const input = document.getElementById("originSearch");
    const probe = document.createElement("canvas");
    probe.width = probe.height = 1;
    const painter = probe.getContext("2d");
    const paint = (value, backdrop) => {
      painter.clearRect(0, 0, 1, 1);
      painter.fillStyle = "rgb(" + backdrop.join(", ") + ")";
      painter.fillRect(0, 0, 1, 1);
      painter.fillStyle = value;
      painter.fillRect(0, 0, 1, 1);
      const pixel = painter.getImageData(0, 0, 1, 1).data;
      return [pixel[0], pixel[1], pixel[2]];
    };
    const luminance = (rgb) =>
      rgb
        .map((channel) => {
          const c = channel / 255;
          return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
        })
        .reduce((sum, c, i) => sum + c * [0.2126, 0.7152, 0.0722][i], 0);
    const ratio = (a, b) => {
      const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
      return (hi + 0.05) / (lo + 0.05);
    };
    const behind = paint(getComputedStyle(document.body).backgroundColor, [255, 255, 255]);
    const placeholder = paint(getComputedStyle(input, "::placeholder").color, behind);
    return {
      ratio: ratio(placeholder, behind),
      ink: placeholder.join(","),
      behind: behind.join(","),
    };
  });
  check(
    "the placeholder is muted and still meets AA",
    placeholderInk.ratio >= 4.5,
    `${placeholderInk.ratio.toFixed(1)}:1, ${placeholderInk.ink} on ${placeholderInk.behind}`
  );
  // The reader's own answer belongs in the accent colour, and the caret in the
  // slot is what says the page is waiting for one.
  const slotState = await page.evaluate(() => ({
    focused: document.activeElement === document.getElementById("originSearch"),
    caret: getComputedStyle(document.getElementById("originSearch")).caretColor,
    empty: document.getElementById("originSearch").value === "",
  }));
  check(
    "the empty station slot holds the caret on arrival",
    slotState.focused && slotState.empty,
    JSON.stringify(slotState)
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
  await page.fill("#originSearch", query);
  const narrowed = await page.locator("#picks a").count();
  check(
    "typing narrows the list",
    // A chooser holding one station cannot be narrowed by typing: the query
    // that would exclude it is the reader's own spelling of it. A published
    // one-origin build is that page, so this is reported as not exercised
    // rather than failed, and the count is on the page's tally.
    options < 2
      ? notExercised(`this chooser lists ${options} station(s), so typing cannot narrow it`)
      : narrowed > 0 && narrowed < options && /Showing|list/i.test(await page.textContent("#pickStatus")),
    `${query} -> ${narrowed} of ${options}`
  );
  const code = listed[1] ? listed[1].crs : first.crs;
  await page.fill("#originSearch", code);
  check(
    "a three-letter code finds its station",
    (await page.locator("#picks a").count()) === 1 && (await page.textContent("#picks")).includes(code),
    code
  );
  await page.fill("#originSearch", "zzzz");
  const noMatch = await page.locator("#nomatch").isVisible();
  check("a query with no answer says so", noMatch && (await page.locator("#picks a").count()) === 0, await page.textContent("#nomatch"));
  check("and it names the code route", /three-letter code/.test(await page.textContent("#nomatch")));
  await page.fill("#originSearch", "");

  // The budget is the reader's, and it is the one thing the root page can carry
  // into the station page it opens (S05).
  const next = Math.min(500, Number(budget) + 7);
  await page.fill("#budgetNumber", String(next));
  check("changing the budget retitles the page", new RegExp("£" + next + "\?").test(await page.title()), await page.title());
  const carried = await page.evaluate(() => new URL(document.querySelector("#picks a").href).searchParams.get("budget"));
  check("and the station links carry it", carried === String(next), String(carried));

  // A shared link: the budget a reader was given is the budget they get back.
  await page.goto(url + "?budget=42");
  check("a budget in the link opens the page at that budget", (await page.inputValue("#budgetNumber")) === "42", await page.inputValue("#budgetNumber"));
  check(
    "and the station links carry it on",
    (await page.evaluate(() => new URL(document.querySelector("#picks a").href).searchParams.get("budget"))) === "42"
  );
  check("the station field takes focus on arrival", (await page.evaluate(() => document.activeElement && document.activeElement.id)) === "originSearch");
  // S10: a cold-start order that does not say what it is looks like a
  // recommendation. The page has to name the measure and deny the two things
  // a reader would otherwise assume it means.
  const ranking = await page.textContent("body");
  check(
    "the chooser says what its order is, and what it is not",
    /how many destinations/i.test(ranking) && /not by how busy/i.test(ranking),
    (await page.textContent("#orderingNote")) || ""
  );
  // The route has no filter bar, and that is a design decision rather than an
  // omission: the only two things a reader can change here are the two slots in
  // the heading, and this is what says so if one is ever added back.
  check(
    "the chooser carries no filter bar",
    (await page.locator(".filter-bar").count()) === 0 && (await page.locator("#moreFilters").count()) === 0
  );
  // S11: a code fragment is what somebody who knows the network types.
  // Lowercased to match the page, which lowercases what the reader typed
  // before comparing: a code in the address bar is upper case.
  const fragment = (listed[1] || first).crs.slice(0, 2).toLowerCase();
  await page.fill("#originSearch", fragment);
  const byFragment = await page.evaluate(() =>
    Array.from(document.querySelectorAll("#picks a")).map((a) => ({
      code: (a.querySelector(".code") || {}).textContent || "",
      name: (a.querySelector("span") || {}).textContent || "",
    }))
  );
  check(
    "a code fragment finds its station",
    byFragment.some((row) => row.code.toLowerCase().startsWith(fragment)) &&
      byFragment.every((row) => row.code.toLowerCase().startsWith(fragment) || row.name.toLowerCase().includes(fragment)),
    `${fragment} -> ${byFragment.map((row) => row.code).join(" ") || "nothing"}`
  );
  await page.fill("#originSearch", "");
  const privacy = await page.evaluate(() => (document.querySelector(".footnav a") || {}).getAttribute
    ? document.querySelector(".footnav a").getAttribute("href")
    : null);
  check("the chooser links to the privacy page", privacy !== null && /\/privacy\/$/.test(new URL(privacy, "http://x").pathname), String(privacy));

  // The list the field filters is what the field is for, so the key that means
  // "down into it" is the way in, and the keys that mean "leave" are the way
  // back. The options stay real anchors, so focus lands on the anchor itself.
  const optionCount = await page.locator("#picks a").count();
  await page.fill("#originSearch", "");
  await page.focus("#originSearch");
  await page.keyboard.press("ArrowDown");
  const entered = await page.evaluate(() => ({
    isFirst: document.activeElement === document.querySelector("#picks a"),
    tag: document.activeElement ? document.activeElement.tagName : "",
  }));
  check(
    "ArrowDown from the station field enters its list",
    optionCount ? entered.isFirst : notExercised("this chooser lists no station to enter"),
    JSON.stringify({ ...entered, options: optionCount })
  );
  await page.keyboard.press("ArrowUp");
  check(
    "ArrowUp from the first option returns to the field",
    optionCount
      ? await page.evaluate(() => document.activeElement && document.activeElement.id === "originSearch")
      : notExercised("see above")
  );
  if (optionCount > 1) {
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("ArrowDown");
    check(
      "and ArrowDown again reaches the second option",
      await page.evaluate(() => document.activeElement === document.querySelectorAll("#picks a")[1]),
      `${optionCount} options`
    );
    await page.keyboard.press("Escape");
    check(
      "Escape in the list returns to the field",
      await page.evaluate(() => document.activeElement && document.activeElement.id === "originSearch")
    );
  } else {
    check("and ArrowDown again reaches the second option", notExercised("this chooser lists one station"));
    check("Escape in the list returns to the field", notExercised("see above"));
  }

  // A station name can be pasted from anywhere, and the field sits inside the
  // heading's own line: an unbounded field takes the page sideways with it.
  // Sixty characters is longer than any station's name in the feed.
  const longQuery = "Z".repeat(60);
  await page.fill("#originSearch", longQuery);
  const wide = await page.evaluate(() => ({
    overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth,
    field: Math.round(document.getElementById("originSearch").getBoundingClientRect().width),
  }));
  check(
    "a sixty-character station name does not push the page sideways",
    wide.overflow <= 0,
    `${wide.field}px field, ${wide.overflow}px of sideways scroll`
  );
  await page.fill("#originSearch", "");

  await page.setViewportSize({ width: 390, height: 720 });
  const overflow = await page.evaluate(() => {
    const html = document.documentElement;
    return Math.max(html.scrollWidth, document.body.scrollWidth) - window.innerWidth;
  });
  check("at 390px nothing overflows horizontally", overflow <= 0, `${overflow}px`);
  await page.fill("#originSearch", longQuery);
  const narrowOverflow = await page.evaluate(() => ({
    overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth,
    field: Math.round(document.getElementById("originSearch").getBoundingClientRect().width),
  }));
  check(
    "and not at 390px either",
    narrowOverflow.overflow <= 0,
    `${narrowOverflow.field}px field, ${narrowOverflow.overflow}px of sideways scroll`
  );
}

async function runPage(browser, index, given, file, body, base) {
  // One context per page. The seller's stub route and the clipboard grant are
  // both context-scoped, and a page that failed a step must not hand the next
  // one a reader still carrying its budget, its filters, or its mode.
  const checks = [];
  const check = (name, condition, detail) => {
    // A check the page cannot exercise is a skip in every mode, reported and
    // counted wherever it happens. It used to be a failure outside a sweep,
    // which meant a legitimately small page could not be tested at all: a
    // one-station build has no second station to link to and no destination
    // without a journey, so five honest checks failed and the page could only
    // be left untested. The teeth are the budget, not the failure: a run that
    // skips more than SKIP_BUDGET of the checks on its station and chooser
    // pages fails for that reason, in every mode, and names the page.
    if (condition && condition.skip === NOT_EXERCISED) {
      checks.push({ name, ok: false, skipped: true, detail: condition.reason });
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
  // Which route is this, decided by what the page carries rather than by where
  // it sits: a single-station build writes the station page to the site root
  // and a full-network build writes a chooser there.
  const kind = await page.evaluate(() => {
    if (typeof DATA !== "undefined" && typeof PAGE_SIZE !== "undefined") return "station";
    if (typeof STATIONS !== "undefined" && document.getElementById("picks")) return "chooser";
    if (document.querySelector("h1")) return "privacy";
    return "other";
  });
  notStation = kind !== "station";
  // S41: the matrix runs first and on every route, including the privacy page,
  // which used to be reported as 0/0 because it carries no controls. It is a
  // published route a reader can land on from every footer on the site.
  try {
    await checkAccessibilityMatrix(page, url, check, kind);
  } catch (error) {
    console.error("the accessibility matrix stopped early on " + given + ": " + error.message);
    stopped = true;
  }
  if (kind === "privacy" || kind === "other") {
    // A route with no reader-facing controls has nothing else to drive, and
    // the matrix above is its whole check.
    notStation = kind === "other";
    printPage();
    await context.close();
    return { given, file, checks, stopped, notStation, kind };
  }
  if (kind === "chooser") {
    try {
      await checkChooser(page, url, check);
    } catch (error) {
      console.error("the browser test stopped early on " + given + ": " + error.message);
      stopped = true;
    }
    // A checked chooser is a tested page, so it is tallied like one rather
    // than reported as a path this suite could not read.
    notStation = false;
    printPage();
    await context.close();
    return { given, file, checks, stopped, notStation, kind };
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
  // The refinements are folded on every route and at every width, so a
  // navigation always arrives with them closed and every step that drives a
  // chip, a ticket mode or a party choice has to open them first. One place,
  // or a step that forgets is a step that fails on a control that is on the
  // page and merely closed -- and the reader opens it by pressing the control,
  // which is what this does rather than setting the state behind their back.
  const openFilters = async () => {
    const toggle = page.locator("#moreFiltersToggle");
    if (!(await toggle.count())) return;
    const open = await page.evaluate(
      () => (document.getElementById("moreFilters") || {}).dataset.open === "true"
    );
    if (!open) await toggle.click();
  };
    await openFilters();
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
      // C21: the filter includes a fare exactly at the budget (price <= cap),
      // so the sentence says "up to". "Under" would describe a page that
      // excludes a row it actually shows.
      /Train fares/.test(heading) && /up to/.test(heading) && heading.includes(facts.origin.toUpperCase()),
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

    // C04: the opening sentence has to be true of this build. A page with no
    // timetable must not promise a journey time, and a page with one should
    // say what the times are; both are read off the payload, not off a
    // hardcoded sentence.
    const opening = await page.evaluate(() => ({
      intro: (document.getElementById("pageIntro") || {}).textContent || "",
      hasJourneys: DATA.hasJourneys,
      timeColumns: document.querySelectorAll("thead th[data-label='Time']").length,
      headers: Array.from(document.querySelectorAll("thead th")).map((th) => th.textContent),
    }));
    check(
      "the opening sentence matches whether a timetable was loaded",
      opening.hasJourneys
        ? /fastest journey time/.test(opening.intro)
        : !/journey time/.test(opening.intro) && /no timetable/i.test(opening.intro),
      JSON.stringify(opening)
    );
    check(
      "the times columns exist exactly when the sentence promises times",
      opening.hasJourneys
        ? opening.headers.includes("Time") && opening.headers.includes("Changes")
        : !opening.headers.includes("Time") && !opening.headers.includes("Changes"),
      opening.headers.join(" ")
    );

    // Finding, 29 September 2026: on the real page the Price column measured
    // 56px and 13 of the first 20 prices painted as two lines -- £10.10 read as
    // "£10.1" over "0" -- while CHANGES wrapped mid-word in a 72px column. A
    // wrapped price is not a cramped column, it is a different number, and the
    // header word was deciding the width. So this is measured as painted line
    // boxes rather than read off the CSS: getClientRects() over a cell's own
    // contents returns one rect per line, and the distinct tops are the lines.
    const measure = await page.evaluate(() => {
      const lines = (el) => {
        const range = document.createRange();
        range.selectNodeContents(el);
        return new Set(Array.from(range.getClientRects()).map((rect) => Math.round(rect.top))).size;
      };
      const cells = [
        ...document.querySelectorAll("thead th"),
        ...document.querySelectorAll("#rows td.num, #rows .ticket-code"),
      ];
      const wrapped = [];
      for (const el of cells) {
        if (!el.getBoundingClientRect().height) continue;
        const count = lines(el);
        if (count > 1) {
          wrapped.push({
            text: el.textContent.trim(),
            lines: count,
            width: Math.round(el.getBoundingClientRect().width),
          });
        }
      }
      // The second half of the same finding: the count line sat 205px above the
      // first row, with six provenance paragraphs between them, so the first
      // fare was below the fold on a laptop. Measured as the distance itself,
      // because how tall the heading and the intro are is a fact about the
      // build and not about this.
      const summary = document.getElementById("summary");
      const table = document.querySelector("table");
      const first = document.querySelector("#rows tr:not(.detail)");
      const box = (el) => (el ? el.getBoundingClientRect() : null);
      const isBetween = (el, from, to) =>
        Boolean(
          from.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING &&
            el.compareDocumentPosition(to) & Node.DOCUMENT_POSITION_FOLLOWING
        );
      const between = (from) =>
        Array.from(document.querySelectorAll("main > *"))
          .filter((el) => isBetween(el, from, table))
          .map((el) => el.id || el.tagName.toLowerCase());
      return {
        cells: cells.length,
        wrapped,
        priceWidth: Math.round((box(document.querySelector("#rows td.num")) || { width: 0 }).width),
        countToTable: box(summary) && box(table) ? Math.round(box(table).top - box(summary).bottom) : null,
        countToFirstRow:
          box(summary) && box(first) ? Math.round(box(first).top - box(summary).top) : null,
        afterCount: summary ? between(summary) : [],
        afterProvenance: document.getElementById("freshness") ? between(document.getElementById("freshness")) : [],
        tabular: document.querySelector("#rows td.num")
          ? getComputedStyle(document.querySelector("#rows td.num")).fontVariantNumeric
          : "",
      };
    });
    check(
      "no price, number or column heading wraps onto a second line",
      measure.cells === 0
        ? notExercised("this page has no results table to measure")
        : measure.wrapped.length === 0,
      measure.wrapped.length
        ? JSON.stringify(measure.wrapped.slice(0, 6))
        : `${measure.cells} cells measured, price column ${measure.priceWidth}px, tabular-nums ${measure.tabular}`
    );
    check(
      "the count line sits on the table it counts",
      measure.countToTable === null
        ? notExercised("this page shows no count and no table")
        : measure.countToTable <= 12 && measure.afterCount.length === 0,
      `count to table ${measure.countToTable}px; between: ${measure.afterCount.join(", ") || "nothing"}`
    );
    check(
      "and nothing but the count and the fold stands between the provenance and the first row",
      measure.countToFirstRow === null
        ? notExercised("this page shows no count and no first row")
        : measure.countToFirstRow <= 100 &&
          measure.afterProvenance.every((id) => ["dateNote", "linkTerms", "summary"].includes(id)),
      `count to first row ${measure.countToFirstRow}px; after the provenance: ${measure.afterProvenance.join(", ") || "nothing"}`
    );

    // C03, as ADR-0040 leaves it: what the ticket action costs, and what the
    // link earns, are still in front of the first ticket action -- and the line
    // a reader meets before the table is the fold's own summary, so that is
    // what is measured as rendered. Only the wording waits behind it: those two
    // paragraphs plus the build line were 57px of the 205px between the count
    // and the table on the real page (finding, 29 September 2026), which is
    // what put the first fare below the fold on a laptop.
    //
    // Measuring the notes' position alone would pass with them folded and
    // unread, which is the defect this check exists for -- so each note has to
    // be inside the fold, and the rendered line has to name what is in it.
    const handoff = await page.evaluate(() => {
      const terms = document.getElementById("linkTerms");
      const note = (selector) => {
        const el = document.querySelector(selector);
        if (!el) return null;
        return {
          text: el.textContent.trim(),
          inTerms: Boolean(el.closest("#linkTerms")),
          inMethod: Boolean(el.closest(".method")),
          hidden: el.hidden,
        };
      };
      const summary = terms ? terms.querySelector("summary") : null;
      const box = summary ? summary.getBoundingClientRect() : null;
      return {
        linkNote: note("#linkNote"),
        disclosure: note("#disclosure"),
        wanted: {
          linkNote: Boolean(DATA.linkNote),
          disclosure: Boolean(DATA.tracked),
          build: Boolean(DATA.builtAt),
        },
        summary: summary
          ? { text: summary.textContent.trim(), rendered: Boolean(box.width && box.height) }
          : null,
        beforeTable: Boolean(
          terms &&
            terms.compareDocumentPosition(document.querySelector("table")) &
              Node.DOCUMENT_POSITION_FOLLOWING
        ),
        inMethod: Boolean(terms && terms.closest(".method")),
      };
    });
    for (const key of ["linkNote", "disclosure"]) {
      // Only a page that has the note is checked for it: a page whose links
      // fill the journey in has no handoff to explain, and an untracked page
      // has no commission to disclose.
      if (!handoff.wanted[key]) continue;
      const found = handoff[key];
      check(
        `${key === "linkNote" ? "the seller handoff" : "the commission disclosure"} is stated above the table`,
        Boolean(found) && found.text.length > 20 && found.inTerms && !found.inMethod,
        JSON.stringify(found)
      );
    }
    check(
      "the fold above the first ticket action says what it holds",
      !(handoff.wanted.linkNote || handoff.wanted.disclosure || handoff.wanted.build)
        ? notExercised("this page has no link terms and no build metadata to fold")
        : Boolean(handoff.summary) &&
            handoff.summary.rendered &&
            handoff.summary.text.length > 10 &&
            handoff.beforeTable &&
            !handoff.inMethod &&
            (!handoff.wanted.disclosure || /paid|earn|commission/i.test(handoff.summary.text)),
      `${JSON.stringify(handoff.summary)} beforeTable=${handoff.beforeTable} inMethod=${handoff.inMethod}`
    );

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
    check("the summary counts what is left", /No destinations for up to/.test(await page.textContent("#summary")));

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
    // flag is asserted against the rows the payload says are advance singles in
    // this mode, at this budget -- and against their absence when there are
    // none, so a page cannot pass by never showing one. Finding, 29 September
    // 2026: the sentence moved into the row's own disclosure and the row
    // carries the fare's code, so what is on the row is the word "advance" and
    // the sentence is read where a reader now reads it.
    const advance = await page.evaluate(() => {
      const wanted = TYPES.list().filter((d) => d.isAdvance && d.adultPence <= TYPES.cap()).length;
      const rows = Array.from(document.querySelectorAll("#rows tr:not(.detail)"));
      const flagged = rows.filter(
        (row) => ((row.querySelector(".condition-flag") || {}).textContent || "").trim() === "advance"
      );
      const sentences = flagged.map((row) => {
        const toggle = row.querySelector(".toggle[aria-expanded=false]");
        if (toggle) toggle.click();
        const detail =
          row.nextElementSibling && row.nextElementSibling.classList.contains("detail")
            ? row.nextElementSibling
            : null;
        const text = detail ? detail.textContent : "";
        if (toggle) toggle.click();
        return text;
      });
      return { wanted, rows: rows.length, flagged: flagged.length, sentences };
    });
    check(
      "an advance single is flagged on its row, and only when one is shown",
      advance.wanted === 0 ? advance.flagged === 0 : advance.flagged > 0,
      `${advance.wanted} advance singles in this mode at this budget, ${advance.flagged} flagged of ${advance.rows} rows`
    );
    check(
      "and every flagged row says train-specific, one disclosure away",
      advance.flagged === 0
        ? advance.wanted === 0
        : advance.sentences.every((text) => /Advance single/.test(text)),
      `${advance.flagged} flagged; ${(advance.sentences[0] || "").slice(0, 160)}`
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
    // 3d. The refinements fold away on every route and at every width, and
    // the reader is the only thing that opens them. Driven the way a reader
    // drives it -- press the control, narrow something, press it again --
    // because a disclosure that only works when it is forced open is not a
    // disclosure. The budget is deliberately outside it: that is the page's
    // question, and a reader should never have to open a drawer to answer it.
    // A fresh navigation, because this is about what the page arrives as.
    await page.goto(url);
    await installReader();
    await page.fill("#budgetNumber", String(facts.affordable));
    const folded = await page.evaluate(() => {
      const details = document.getElementById("moreFilters");
      const toggle = document.getElementById("moreFiltersToggle");
      const budget = document.getElementById("budget");
      const firstRow = document.querySelector("#rows tr");
      return {
        open: details ? details.dataset.open === "true" : null,
        expanded: toggle ? toggle.getAttribute("aria-expanded") : null,
        summaryVisible: toggle ? getComputedStyle(toggle).display !== "none" : false,
        budgetVisible: !!budget && budget.getBoundingClientRect().height > 0,
        resultsVisible: !!firstRow && firstRow.getBoundingClientRect().height > 0,
        state: (document.getElementById("filterState") || {}).textContent || "",
      };
    });
    check("the refinements arrive folded and the plate says so", folded.open === false, JSON.stringify(folded));
    check("and the folded plate says what is narrowed", /\bReturn\b/.test(folded.state) && /adult/.test(folded.state), folded.state);
    check("the budget stays out of the fold", folded.budgetVisible, JSON.stringify(folded));
    check("the results are on screen without opening anything", folded.resultsVisible, JSON.stringify(folded));
    check("the control that opens them is on screen", folded.summaryVisible, JSON.stringify(folded));
    check(
      "the toggle announces whether the refinements are open",
      folded.open === false ? folded.expanded === "false" : folded.expanded === "true",
      String(folded.expanded)
    );
    if (folded.open === false && folded.summaryVisible) {
      await page.click("#moreFiltersToggle");
      const opened = await page.evaluate(() => {
        const details = document.getElementById("moreFilters");
        const panel = document.getElementById("moreFiltersPanel");
        return {
          open: details.dataset.open === "true",
          expanded: document.getElementById("moreFiltersToggle").getAttribute("aria-expanded"),
          panelVisible: panel.getBoundingClientRect().height > 0,
        };
      });
      check(
        "one tap opens the refinements",
        opened.open === true && opened.expanded === "true" && opened.panelVisible,
        JSON.stringify(opened)
      );
      const chipValue = await page.evaluate(() => {
        // A chip whose count is zero inside the current budget empties the
        // list by design, and the page says so on the chip before the press.
        // This check is about the disclosure keeping whatever the reader
        // narrowed to, so it presses a chip that has something to narrow to;
        // a page where no chip does is reported rather than failed.
        const boxes = Array.from(document.querySelectorAll('#destinationTypes input[type="checkbox"]'));
        const withRows = boxes.filter((box) => {
          const count = document.querySelector(`[data-count-for="${box.value}"]`);
          return count && Number(count.textContent.replace(/\D/g, "")) > 0;
        });
        const input = withRows[0] || boxes[0] || null;
        if (!input) return { pressed: false, rows: 0, label: "", name: "", noneLeft: true };
        const name = input.parentElement.querySelector("span").textContent.trim();
        const before = document.querySelectorAll("#rows tr").length;
        input.click();
        return {
          pressed: input.checked,
          name,
          before,
          // A small page can press a chip and keep every row it had, so the
          // row count is reported rather than asserted: what has to change is
          // the state the reader can see.
          after: document.querySelectorAll("#rows tr").length,
          label: (document.getElementById("filterState") || {}).textContent || "",
        };
      });
      check(
        "a refinement pressed inside the disclosure is applied and says so",
        // The chip took the press, and the summary now names that chip rather
        // than the state it read before the tap.
        !chipValue.noneLeft && chipValue.pressed && chipValue.label.includes(chipValue.name) && chipValue.label !== folded.state,
        JSON.stringify(chipValue)
      );
      await page.click("#moreFiltersToggle");
      const closed = await page.evaluate(() => {
        const details = document.getElementById("moreFilters");
        const row = document.querySelector("#rows tr");
        return {
          open: details.dataset.open === "true",
          rows: document.querySelectorAll("#rows tr").length,
          rowVisible: !!row && row.getBoundingClientRect().height > 0,
          state: (document.getElementById("filterState") || {}).textContent || "",
        };
      });
      check(
        "closing it again keeps the narrowed results",
        closed.open === false && closed.rows > 0 && closed.rowVisible,
        JSON.stringify(closed)
      );
      check("and the summary still names what is narrowed", closed.state.trim().length > 0, closed.state);
      // Put the chips back, then hand the rest of the run a desktop viewport:
      // the checks below exercise every control, which on a phone means
      // opening the disclosure each time, and that is what section 7a is for.
      await page.evaluate(() => {
        for (const input of document.querySelectorAll('#destinationTypes input[type="checkbox"]')) {
          if (input.checked) input.click();
        }
      });
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
    }));    check("All is checked exclusively",
      exclusivity.all && exclusivity.also.length === 0,
      `all ${exclusivity.all}; also checked: ${exclusivity.also.join(", ") || "none"}`
    );
    check("clearing the type filter restores the list", (await rows()) === initial);

    // C20: a facet present in only one mode used to be silently unchecked when
    // the mode changed, and switching back showed "All" with no explanation.
    // The selection is now kept per mode, and a change is announced. Both are
    // checked here, on whatever modes this page actually carries chips for.
    // C17 and C20 each start from a fresh load: both drive the ticket-mode
    // radios, and leaving a mode or a party selected behind them would make a
    // later check read a page state it did not ask for.
    await open();
    const chipInMode = await page.evaluate(() => {
      // Which chips does each mode offer? A chip the reader can pick has to be
      // offered by the mode they pick it in; the mode it is then compared
      // against is one that cannot carry it, because that is the only situation
      // where it is dropped. A mode with fares is preferred for that second
      // role because it is the harder case -- an empty mode drops everything
      // anyway -- but a mode with no fares at all is what most real stations
      // actually have for Anytime Day Return, so it is used when nothing else
      // will do rather than reported as a check this page cannot make.
      const MODES = ["return", "single", "anytime"];
      const rowsFor = (mode) => {
        const list = { return: "destinations", single: "singleDestinations", anytime: "anytimeDestinations" }[mode];
        return (DATA[list] || []).length;
      };
      const switchable = MODES.filter((mode) => document.querySelector(`input[name="ticketMode"][value="${mode}"]`));
      if (switchable.length < 2) return [];
      const original = document.querySelector('input[name="ticketMode"]:checked').value;
      const offered = {};
      for (const mode of switchable) {
        document.querySelector(`input[name="ticketMode"][value="${mode}"]`).checked = true;
        render();
        offered[mode] = new Set(activeDestinations().flatMap((x) => x.destinationTypes || [x.destinationType]));
      }
      document.querySelector(`input[name="ticketMode"][value="${original}"]`).checked = true;
      render();
      const out = [];
      for (const input of document.querySelectorAll('input[name="destinationType"]')) {
        if (input.value === "all") continue;
        const home = switchable.find((m) => rowsFor(m) && offered[m].has(input.value));
        if (!home) continue;
        const away = switchable.find((m) => m !== home && rowsFor(m) && !offered[m].has(input.value)) ||
          switchable.find((m) => m !== home && !offered[m].has(input.value));
        if (away) out.push({ value: input.value, home, away });
      }
      return out;
    });
    if (chipInMode.length) {
      const chip = chipInMode[0];
      await page.locator(`input[name="ticketMode"][value="${chip.home}"]`).check({ force: true });
      await page.check(`input[name="destinationType"][value="${chip.value}"]`);
      await page.locator(`input[name="ticketMode"][value="${chip.away}"]`).check({ force: true });
      const notice = ((await page.textContent("#facetNotice").catch(() => "")) || "").trim();
      // The notice names the facet the way the reader knows it -- the chip's
      // own label, without its count -- so that is what is looked for.
      const chipLabel = ((await page.locator(`input[name="destinationType"][value="${chip.value}"]`)
        .evaluate((el) => el.closest("label")?.textContent || "")).replace(/\(\d+\)/, "")).trim();
      check(
        "switching ticket mode says a filter was cleared",
        notice.startsWith("Cleared ") && notice.includes(chipLabel),
        JSON.stringify({ notice, chipLabel, chip })
      );
      await page.locator(`input[name="ticketMode"][value="${chip.home}"]`).check({ force: true });
      check(
        "and switching back restores the filter the reader had",
        await page.isChecked(`input[name="destinationType"][value="${chip.value}"]`),
        `${chip.value} checked again in ${chip.home}`
      );
    } else {
      check("switching ticket mode says a filter was cleared",
        notExercised("every chip this page offers is offered by every mode it can switch to"));
      check("and switching back restores the filter the reader had", notExercised("see above"));
    }
    await page.check('input[name="destinationType"][value="all"]');

    // C17: the order follows the price actually on screen, which is not the
    // standard fare once the party or the railcard changes it. Read in both
    // states, because the defect was only visible in one of them. The order is
    // stated in the count line instead of by tinting a row: a page that will not
    // say which fare is best cannot say it with a colour either. The tint is
    // judged as paint rather than as a class name, so a row that is highlighted
    // by any rule at all is caught.
    await open();
    const orderState = () => page.evaluate(() => {
      const shown = Array.from(document.querySelectorAll("#rows tr[data-crs]"));
      return {
        prices: shown.map((r) => Number(r.querySelector("td.num").textContent.replace(/[^0-9.]/g, ""))),
        paints: Array.from(new Set(shown.map((r) => getComputedStyle(r.querySelector("td") || r).backgroundColor))),
        words: (document.getElementById("summary") || {}).textContent || "",
      };
    });
    const adultOrder = await orderState();
    await page.check('input[name="unit"][value="party"]');
    const partyOrder = await orderState();
    const sortedAscending = (xs) => xs.every((v, i) => i === 0 || xs[i - 1] <= v);
    check(
      "the rows are ordered by the price on screen, not by the feed's order",
      sortedAscending(adultOrder.prices) && sortedAscending(partyOrder.prices),
      `adult ${JSON.stringify(adultOrder.prices.slice(0, 4))}; party ${JSON.stringify(partyOrder.prices.slice(0, 4))}`
    );
    // No row carries a tint now, so the check is the absence: a page that
    // tints the cheapest row and says nothing is recommending with a colour.
    // The order is judged in the count line's own words, which is where it is
    // stated, and where an empty list has nothing to state.
    const onePaint = (s) => s.paints.length <= 1;
    const saysOrder = (s) => s.prices.length === 0 || /cheapest first/i.test(s.words);
    check(
      "no row is painted differently from the rest",
      onePaint(adultOrder) && onePaint(partyOrder),
      `adult rows painted ${JSON.stringify(adultOrder.paints)}, ` +
        `two adults ${JSON.stringify(partyOrder.paints)}`
    );
    check(
      "and the count line says the list is cheapest first",
      saysOrder(adultOrder) && saysOrder(partyOrder),
      JSON.stringify(adultOrder.words)
    );
    await page.check('input[name="unit"][value="adult"]');

    // C09: the copied journey carries the ticket mode, so a handoff to a
    // seller cannot silently become a different ticket. Read from the page's
    // own journeyText() rather than from a clipboard, which the context denies.
    // The counts come from the payload rather than from the page's modeCount(),
    // which is not a global: one list per mode is the same fact the page reads.
    await open();
    const modeHasRows = await page.evaluate(() => ({
      return: (DATA.destinations || []).length,
      single: (DATA.singleDestinations || []).length,
      anytime: (DATA.anytimeDestinations || []).length,
    }));
    const copyForMode = async (mode) => {
      await page.locator(`input[name="ticketMode"][value="${mode}"]`).check({ force: true });
      return page.evaluate(() => journeyText(TYPES.list()[0] || { name: "X", crs: "XXX" }));
    };
    // The default is read off the checked radio rather than written here, so a
    // change to which mode the page opens in cannot leave this block asserting
    // against a mode the page never opens in.
    const defaultMode = await page.evaluate(() => document.querySelector('input[name="ticketMode"]:checked').value);
    const secondMode = ["return", "single", "anytime"].find((m) => modeHasRows[m] && m !== defaultMode);
    if (secondMode) {
      const copied = await copyForMode(secondMode);
      // The expected name is read off the mode's own visible label, not from
      // the page's modeLabels() helper: journeyText() builds its line with that
      // same helper, so comparing the two would pass on any string at all --
      // including a label of "" or one carrying a row count.
      const visibleLabel = async (mode) =>
        (((await page.locator(`input[name="ticketMode"][value="${mode}"]`)
          .evaluate((el) => el.closest("label")?.textContent || "")) || "").trim());
      const expected = await visibleLabel(secondMode);
      const otherLabel = await visibleLabel(defaultMode);
      const ticketLine = (copied.split("\n").find((line) => line.startsWith("Ticket: ")) || "").trim();
      check(
        "the copied journey names the ticket type the reader chose",
        expected.length > 2 && ticketLine === "Ticket: " + expected && expected !== otherLabel,
        JSON.stringify({ ticketLine, expected, otherLabel, secondMode })
      );
    } else {
      check("the copied journey names the ticket type the reader chose", notExercised("no second mode on this page has a row"));
    }
    // The next section reads the ticket link off the first row, so the page is
    // handed back in the default state rather than in whatever ticket mode the
    // C09 check happened to be in.
    await open();
    await page
      .locator(`input[name="ticketMode"][value="${defaultMode}"]`)
      .check({ force: true })
      .catch(() => {});

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

    // 7a. A resize is not a fold. The refinements used to open and close with
    // the viewport -- a media query and a resize listener, two roads to one
    // state -- which meant a reader who rotated a phone could lose the fold
    // they had chosen. The fold is theirs now, so a resize has to leave it
    // exactly where they left it, in both directions.
    const beforeResize = await page.evaluate(
      () => (document.getElementById("moreFilters") || {}).dataset.open
    );
    await page.setViewportSize({ width: 1280, height: 800 });
    const afterResize = await page.evaluate(
      () => (document.getElementById("moreFilters") || {}).dataset.open
    );
    check(
      "a resize does not move the fold the reader chose",
      beforeResize === afterResize,
      `${beforeResize} -> ${afterResize}`
    );

    // 7b. The address is the search (S05). Every control the reader moves has
    // to survive a refresh, a shared link and Back, and the picker has to
    // carry the same search to the station they switch to (S06). The facts are
    // read out of the page's own controls, so nothing here names a budget or a
    // mode the page might not have.
    await open();
    // Read the address from the page, not from page.url(): a history change
    // made by the page's own script reaches the driver one round trip later,
    // so page.url() immediately after a click can still be the old address and
    // would make a control that works look broken.
    const address = () => page.evaluate(() => window.location.href);
    const stateful = await page.evaluate(() => ({
      chips: Array.from(document.querySelectorAll('input[name="destinationType"]'))
        .filter((input) => input.value !== "all")
        .filter((input) => !input.closest("label").hidden)
        .map((input) => input.value),
      hasParty: !!document.querySelector('input[name="unit"][value="party"]'),
    }));
    // One non-default mode, if this page has a second mode with fares in it.
    const otherMode = await page.evaluate(() => {
      // The radio the page opened with, put back after each probe. Unchecking
      // the radio that was chosen would leave a group with nothing selected,
      // which is a state no reader can reach and which the next click cannot
      // be judged from.
      const fallback = document.querySelector('input[name="ticketMode"]:checked');
      const mode = (wanted) => {
        const input = document.querySelector(`input[name="ticketMode"][value="${wanted}"]`);
        input.checked = true;
        render();
        const rows = document.querySelectorAll("#rows tr").length;
        fallback.checked = true;
        return rows;
      };
      // Only a mode that is not the page default, because a default is the one
      // value the address leaves out by design. The default is whatever the
      // page opened with, not a name written here, so changing which mode the
      // page opens in cannot make this probe pick the default and then assert
      // the address carries it.
      const defaultValue = fallback.value;
      for (const wanted of ["return", "single", "anytime"]) {
        if (wanted === defaultValue) continue;
        if (mode(wanted) > 0) return wanted;
      }
      return null;
    });
    const partyBudget = await page.evaluate(() => {
      // The budget the party mode can actually show, or null when this page
      // has nothing a pair could buy. The same restore as above.
      const fallback = document.querySelector('input[name="unit"]:checked');
      const input = document.querySelector('input[name="unit"][value="party"]');
      input.checked = true;
      const ceiling = budgetCeiling();
      fallback.checked = true;
      return ceiling > 1 ? ceiling : null;
    });
    const aChip = stateful.chips[0] || null;
    if (otherMode) {
      // force: the radio itself is visually hidden inside its styled label,
      // which is the target a reader actually clicks.
      await page.locator(`input[name="ticketMode"][value="${otherMode}"]`).check({ force: true });
      check("the address carries the ticket mode", new RegExp("[?&]mode=" + otherMode + "(&|$)").test(await address()), await address());
    } else {
      check("the address carries the ticket mode", notExercised("no mode other than this page's default has a row"));
    }
    if (partyBudget && stateful.hasParty) {
      await page.check('input[name="unit"][value="party"]');
      check("the address carries the party", /[?&]party=2(&|$)/.test(await address()), await address());
      // Back to one adult, which is the other end of the same radio group.
      await page.check('input[name="unit"][value="adult"]');
    } else {
      check("the address carries the party", notExercised("this page has no party price a pair could be shown"));
    }
    if (aChip) {
      await page.check(`input[name="destinationType"][value="${aChip}"]`);
      check("the address carries the destination type", new RegExp("[?&]types=" + aChip + "(&|$)").test(await address()), await address());
    } else {
      check("the address carries the destination type", notExercised("this page offers no destination-type chip"));
    }
    // An absent mode parameter means the page's own default, read above from
    // the control rather than repeated here.
    const sharedUrl = await address();
    await page.reload();
    check(
      "a refresh keeps the search the address describes",
      (await page.inputValue("#budgetNumber")) === new URL(sharedUrl).searchParams.get("budget") &&
        (await page.evaluate(() => document.querySelector('input[name="ticketMode"]:checked').value)) === (new URL(sharedUrl).searchParams.get("mode") || defaultMode) &&
        (await page.evaluate(() => document.querySelectorAll('input[name="destinationType"]:checked').length)) ===
          new URL(sharedUrl).searchParams.getAll("types").length,
      sharedUrl
    );
    check("and the title still names that budget", new RegExp("up to £" + new URL(sharedUrl).searchParams.get("budget") + "\\b").test(await page.title()), await page.title());
    // Back is one decision, not a direction the page can only go forwards in.
    await page.goBack();
    const backUrl = await address();
    const afterBack = await page.evaluate(() => ({
      mode: document.querySelector('input[name="ticketMode"]:checked').value,
      budget: document.getElementById("budgetNumber").value,
    }));
    check(
      "Back returns to the previous search",
      (new URL(backUrl).searchParams.get("mode") || defaultMode) === afterBack.mode,
      `${afterBack.mode} at £${afterBack.budget} on ${backUrl}`
    );
    // The budget is the one thing every reader has, so it is the one thing the
    // heading and the tab must both be saying.
    await open(3);
    check("the tab title follows the budget", /up to £3\b/.test(await page.title()), await page.title());

    // 7c. The party, the fare's conditions, the facets, and what an empty
    // list offers. Every fact is read out of this page's own payload and
    // controls, so one run of this section is a test of the page rather than
    // of the station it was pointed at.
    await open(facts.affordable);

    // S15: a railcard for two adults is a constraint on the party, so the
    // cheapest number on screen is a fare the party could actually buy.
    const cardChoice = await page.locator("#railcardChoice").isVisible();
    const solo = cardChoice
      ? await page.evaluate(() => {
        document.querySelector('input[name="unit"][value="adult"]').checked = true;
        render();
        return {
          disabled: document.getElementById("railcard").disabled,
          checked: document.getElementById("railcard").checked,
          help: document.getElementById("railcardHelp").textContent,
          party: DATA.railcardParty,
        };
      })
      : null;
    check(
      "one adult cannot price a journey with a two-adult railcard",
      cardChoice ? solo.disabled && !solo.checked : notExercised("no destination on this page is railcard-eligible"),
      cardChoice ? `disabled=${solo.disabled} checked=${solo.checked}` : ""
    );
    check(
      "and the page says the card belongs to a party, not to a discount",
      cardChoice
        ? /covers \d+ to \d+ adults/.test(solo.help) && /Two adults/.test(solo.help)
        : notExercised("no destination on this page is railcard-eligible"),
      cardChoice ? solo.help : ""
    );
    const cardPair = cardChoice
      ? await page.evaluate(() => {
        document.querySelector('input[name="unit"][value="party"]').checked = true;
        render();
        return {
          disabled: document.getElementById("railcard").disabled,
          help: document.getElementById("railcardHelp").textContent,
          min: DATA.railcardParty ? DATA.railcardParty.minAdults : null,
        };
      })
      : null;
    check(
      "two adults can use it",
      cardChoice ? !cardPair.disabled : notExercised("no destination on this page is railcard-eligible"),
      cardChoice ? `disabled=${cardPair.disabled}` : ""
    );
    check(
      "and the help then names what it would discount",
      cardChoice
        ? new RegExp(String(cardPair.min || 0)).test(cardPair.help) && /Card details/.test(cardPair.help)
        : notExercised("no destination on this page is railcard-eligible"),
      cardChoice ? cardPair.help : ""
    );
    if (cardChoice) {
      await page.evaluate(() => {
        document.querySelector('input[name="unit"][value="adult"]').checked = true;
        render();
      });
    }

    // S19, with the finding of 29 September 2026 on top: the condition is
    // still a sentence rather than a bare code, and the feed's own vocabulary
    // is still folded away -- but on the real page that same sentence stood in
    // all 20 rows, 40 cells restating the mode the mode control had already
    // named. The row carries the fare's code now and the sentence is one
    // disclosure away on the row the reader is reading. Measured by opening
    // every row, because a panel that never opens is not a disclosure.
    const conditions = await page.evaluate(() => {
      const toggles = Array.from(
        document.querySelectorAll("#rows tr:not(.detail) .toggle[aria-expanded=false]")
      );
      for (const toggle of toggles) toggle.click();
      const found = Array.from(document.querySelectorAll("#rows .restriction")).map((cell) => {
        const row = cell.closest("tr.detail").previousElementSibling;
        return {
          readable: (cell.querySelector(".condition") || {}).textContent || "",
          validity: (cell.querySelector(".validity") || {}).textContent || "",
          restricted: cell.dataset.status === "restricted",
          record: Array.from(cell.querySelectorAll(".feed-record dd")).map((dd) => dd.textContent),
          summary: (cell.querySelector(".feed-record summary") || {}).textContent || "",
          code: (row.querySelector(".ticket-code") || {}).textContent || "",
        };
      });
      // Put the rows back: a later check that found twenty panels open would be
      // measuring a page nobody is looking at.
      for (const toggle of toggles) toggle.click();
      return { found, rows: document.querySelectorAll("#rows tr:not(.detail)").length, toggles: toggles.length };
    });
    check(
      "every row states its fare conditions in a sentence, one disclosure away",
      conditions.rows > 0 &&
        conditions.toggles === conditions.rows &&
        conditions.found.length === conditions.rows &&
        conditions.found.every((cell) => cell.readable.length > 10 && !/^[A-Z0-9]{1,4}\b/.test(cell.readable)),
      JSON.stringify(conditions.found[0] || null) +
        ` rows=${conditions.rows} toggles=${conditions.toggles}`
    );
    check(
      "and the row carries the fare's code while the feed's codes stay folded",
      conditions.found.length > 0 &&
        conditions.found.every((cell) => cell.summary && cell.record.length >= 2 && cell.code.length > 0),
      JSON.stringify(conditions.found[0] || null)
    );
    // C08: where the feed states what a restriction permits, the row prints it
    // beside the condition rather than leaving the reader with a code. Judged
    // against the payload, so a page whose feed has nothing to decode is not
    // failed for not inventing it -- but a page whose feed has the text and
    // does not print it is.
    //
    // The mode is found rather than assumed: the reviewed set the page opens in
    // drops restricted fares by design, so the row that carries the validity is
    // in a mode the reader has to switch to. The page is put back the way it
    // was, or every later check on this page runs against a mode nobody asked
    // for.
    const restrictedMode = await page.evaluate(() => {
      const fallback = document.querySelector('input[name="ticketMode"]:checked');
      // Every priced row, at the page's own ceiling: the restricted fare is
      // often the dearest one on the page, and a check that only looked at
      // what the current budget happened to leave on screen would report
      // nothing to check on a page that carries the row.
      const budgetBefore = budget.value;
      setBudget(budgetCeiling());
      currentPage = 1;
      const codes = Object.entries(DATA.restrictionValidity || {}).filter(
        ([, value]) => value && (value.outwardText || value.returnText)
      ).map(([code]) => code);
      if (!codes.length) return null;
      for (const wanted of [fallback.value, "return", "single", "anytime"]) {
        const input = document.querySelector(`input[name="ticketMode"][value="${wanted}"]`);
        if (!input) continue;
        input.checked = true;
        render();
        // The condition, its validity and the record are one disclosure away on
        // the row, so every row is opened before it is read. The render() that
        // restores the reader's mode below clears them again.
        for (const toggle of document.querySelectorAll("#rows tr:not(.detail) .toggle[aria-expanded=false]")) {
          toggle.click();
        }
        const shown = Array.from(document.querySelectorAll("#rows .restriction"))
          .filter((cell) => cell.dataset.status === "restricted")
          .map((cell) => ({
            // The record is Ticket, Restriction, Route -- so the code is the
            // second value in it.
            code: Array.from(cell.querySelectorAll(".feed-record dd")).map((dd) => dd.textContent)[1],
            text: (cell.querySelector(".validity") || {}).textContent || "",
          }));
        fallback.checked = true;
        render();
        if (shown.some((cell) => codes.includes(cell.code))) {
          const found = { mode: wanted, cells: shown };
          setBudget(budgetBefore);
          return found;
        }
      }
      fallback.checked = true;
      render();
      setBudget(budgetBefore);
      currentPage = 1;
      render();
      return { mode: null, cells: [] };
    });
    check(
      "a restricted row prints the validity the feed states for its code",
      !restrictedMode || restrictedMode.mode === null
        ? notExercised(
            restrictedMode ? "no mode on this page lists a fare whose restriction code has validity text" : "this page's feed states no restriction validity"
          )
        : restrictedMode.cells.some((cell) => cell.text.length > 20 && /valid/i.test(cell.text)),
      JSON.stringify(restrictedMode)
    );

    // S23: an absence the feed can name is not a dash.
    const typed = await page.evaluate(() => {
      // Every priced row, not just the ones this budget happens to show: a
      // destination with a fare and no service is the case under test, and it
      // is usually outside a budget set to the cheapest affordable fare.
      setBudget(budgetCeiling());
      currentPage = 1;
      render();
      const row = Array.from(document.querySelectorAll("#rows tr")).find((candidate) => {
        const cell = candidate.querySelector("td.missing");
        return cell && cell.dataset.label === "Time";
      });
      if (!row) return null;
      // The feed's record is in the row's disclosure, and this is the row whose
      // toggle has no times to count: it reads "Fare details", and it exists on
      // every row precisely so that this one has somewhere to put its record.
      const toggle = row.querySelector(".toggle[aria-expanded=false]");
      if (toggle) toggle.click();
      const detail =
        row.nextElementSibling && row.nextElementSibling.classList.contains("detail")
          ? row.nextElementSibling
          : null;
      return {
        cells: Array.from(row.querySelectorAll("td.missing")).map((cell) => cell.textContent),
        record: detail
          ? Array.from(detail.querySelectorAll(".feed-record dd")).map((dd) => dd.textContent)
          : [],
        label: toggle ? toggle.textContent : "",
      };
    });
    check(
      "a row with no journey says so, and says it is unknown rather than zero",
      typed
        ? typed.cells.includes("No service") && typed.cells.includes("Unknown") &&
          typed.record.some((value) => /no service|timetable/i.test(value))
        : notExercised("every destination on this page has a journey"),
      JSON.stringify(typed)
    );

    // S20: counts on the chips, the union stated, and a way back to All.
    const facets = await page.evaluate(() => {
      const cap = Number(document.getElementById("budgetNumber").value) * 100;
      const mode = document.querySelector('input[name="ticketMode"]:checked').value;
      const available = mode === "single" ? DATA.singleDestinations
        : mode === "anytime" ? DATA.anytimeDestinations : DATA.destinations;
      return Array.from(document.querySelectorAll(".chipcount")).map((slot) => {
        const value = slot.dataset.countFor;
        return {
          value,
          shown: slot.textContent,
          count: available.filter(
            (destination) => destination.adultPence <= cap &&
              (destination.destinationTypes || [destination.destinationType]).includes(value)
          ).length,
        };
      });
    });
    check(
      "every offered chip counts what it would show",
      facets.length > 0 && facets.every((facet) => facet.shown === `(${facet.count})`),
      JSON.stringify(facets)
    );
    check(
      "the chips say that more than one means any of them",
      /any of them/.test((await page.textContent("#typeRule")) || "")
    );
    const cleared = await page.evaluate(() => {
      const all = document.querySelector('input[name="destinationType"][value="all"]');
      const first = Array.from(document.querySelectorAll('input[name="destinationType"]')).find(
        (candidate) => candidate.value !== "all" && !candidate.closest("label").hidden
      );
      if (!first) return null;
      first.checked = true;
      all.checked = false;
      render();
      const offered = !document.getElementById("clearTypes").hidden;
      document.getElementById("clearTypes").click();
      return { offered, back: all.checked, specific: first.checked };
    });
    check(
      "a selected chip offers a clear-all that returns to All",
      cleared
        ? cleared.offered && cleared.back && !cleared.specific
        : notExercised("this page offers no specific chip"),
      JSON.stringify(cleared)
    );

    // S22: a narrowed search starts again at its first page. This page's own
    // result set is too short to paginate, so the page number is put where a
    // reader with a longer list would have left it and the control is judged on
    // what it does with it.
    const reset = await page.evaluate(() => {
      currentPage = 3;
      const before = currentPage;
      const field = document.getElementById("budgetNumber");
      field.value = String(Math.max(1, Number(field.value) - 1));
      field.dispatchEvent(new Event("input", { bubbles: true }));
      return { before, after: currentPage, status: document.getElementById("pageStatus").textContent };
    });
    check(
      "a narrowed search returns to the first page",
      reset.before === 3 && reset.after === 1,
      JSON.stringify(reset)
    );
    check(
      "and the status re-announces the page and the count",
      /Page 1 of \d+ of \d+ results?/.test(reset.status),
      reset.status
    );

    // S28: an empty list offers the moves that would fill it, and the first
    // move works when it is taken.
    const recovery = await page.evaluate(() => {
      setBudget(1);
      currentPage = 1;
      render();
      if (document.getElementById("empty").hidden) return { actions: [] };
      const actions = Array.from(document.querySelectorAll("#empty .toggle")).map((button) => button.textContent);
      const first = document.querySelector("#empty .toggle");
      if (first) first.click();
      return {
        actions,
        rows: document.querySelectorAll("#rows tr").length,
        budget: document.getElementById("budgetNumber").value,
      };
    });
    check("an empty list says what would fill it", recovery.actions.length > 0, JSON.stringify(recovery));
    check(
      "and the first move it offers changes the answer",
      recovery.actions.length > 0 && (recovery.rows > 0 || Number(recovery.budget) > 1),
      JSON.stringify(recovery)
    );
    await open(facts.affordable);

    // S29: the coverage claim is counted, and the count is on the page. The
    // lead sentence is per mode, so the expected shape is read from the mode
    // the page is actually in rather than pinned to one of them.
    const coverage = (await page.textContent("#feedCoverage")) || "";
    const coverageMode = await page.evaluate(() => document.querySelector('input[name="ticketMode"]:checked').value);
    const COVERAGE_LEAD = {
      anytime: /reviewed unrestricted Anytime Day Return fares are available in this mode/,
      single: /displayable outbound single fares are available in this mode/,
      return: /standard-return destinations were found in the feed/,
    };
    check(
      "the page states what it could not show",
      Boolean(COVERAGE_LEAD[coverageMode] && COVERAGE_LEAD[coverageMode].test(coverage)),
      `${coverageMode}: ${coverage}`
    );
    check(
      "including the destinations no type chip can select",
      await page.evaluate(() => {
        const text = document.getElementById("feedCoverage").textContent;
        return DATA.unclassifiedDestinationCount
          ? text.includes(String(DATA.unclassifiedDestinationCount)) &&
            /no reviewed destination type/.test(text)
          : /carries a reviewed type|carries no reviewed destination type/.test(text);
      }),
      coverage
    );

    // 7e. S33: the age of the numbers, beside the numbers. A synthetic feed has
    // no download to date, so the fares sentence is conditional; the timetable
    // sentence is not, and is what the check below judges.
    const fresh = await page.evaluate(() => {
      const line = document.getElementById("freshness");
      const now = new Date();
      const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
      const days = (iso) => Math.round((today - Date.parse(iso + "T00:00:00Z")) / 86400000);
      return {
        shown: !line.hidden,
        text: line.textContent,
        // The page reports what it believes; what it claims is judged out
        // here. A regex literal inside this callback is parsed twice -- once
        // by node and once again from the serialised source in the page --
        // and a doubled escape survives the second parse as a literal
        // backslash, so a word boundary arrives as a backslash and matches
        // nothing. That is not a hypothetical: it is how "downloaded 24
        // September 2026, 4 days old" stopped matching and left a check that
        // could only ever fail, on every real build, for a page that was
        // right. (A single escape is fine, and is used elsewhere in this
        // file; tests/test_build_demo_page.py refuses the doubled kind.)
        feedDate: DATA.feedDate || null,
        staleAfterDays: DATA.staleAfterDays,
        window: DATA.timetableFrom
          ? new RegExp(humanDate(DATA.timetableFrom) + " to " + humanDate(DATA.timetableTo)).test(line.textContent)
          : false,
        verdict: DATA.timetableFrom
          ? (days(DATA.timetableFrom) < 0
            ? /has not started yet/.test(line.textContent)
            : days(DATA.timetableTo) > 0
              ? /has ended/.test(line.textContent)
              : /includes today/.test(line.textContent))
          : /prices fares only/.test(line.textContent),
        // Finding, 29 September 2026: the count line now sits directly on its
        // table, so the age of the numbers is stated above the count rather
        // than below it. The promise is unchanged -- it is beside the numbers
        // and above the first row, not in the footer -- so what is measured is
        // the company it keeps.
        beforeSummary: Boolean(line.compareDocumentPosition(document.getElementById("summary")) &
          Node.DOCUMENT_POSITION_FOLLOWING),
        beforeTable: Boolean(line.compareDocumentPosition(document.querySelector("table")) &
          Node.DOCUMENT_POSITION_FOLLOWING),
        inFooter: Boolean(line.closest("footer") || line.closest(".method")),
      };
    });
    check("the page says how old its numbers are", fresh.shown && fresh.text.length > 20, fresh.text);
    check("the timetable sentence carries the feed's own service window", fresh.window, `${fresh.text} (${JSON.stringify(fresh.window)})`);
    check("and judges that window against the reader's today", fresh.verdict, fresh.text);

    // 7f. The conditions in the table are the fares feed's own wording; the
    // page says what the portal's own restriction feed was asked and answered,
    // and says it ABOVE the table, because a condition that has since changed is
    // what a reader needs before choosing between two prices, not after.
    //
    // The dangerous case is the one that reads best: a build that checked
    // nothing and reported the portal as still publishing every condition. So
    // each branch is judged against what the payload actually holds, and "all"
    // is only accepted when conditions were actually compared.
    const reference = await page.evaluate(() => {
      const line = document.getElementById("restrictionReference");
      const ref = DATA.restrictionReference;
      return {
        shown: line ? !line.hidden : false,
        text: line ? line.textContent : "",
        status: ref ? ref.status : null,
        compared: ref ? ref.compared : null,
        // Collected inside the page: DATA lives in the browser, and reading it
        // out here would be an undefined reference that aborts the whole run
        // rather than failing one check.
        unlisted: ref && ref.unlisted ? ref.unlisted.slice() : [],
        // The codes this page's own rows carry, collected from the page's own
        // data. The check reports on what is here, so the invariant can be
        // asserted here rather than compared against a number this suite would
        // have to be told.
        shownCodes: (() => {
          const codes = new Set();
          for (const key of ["destinations", "singleDestinations", "anytimeDestinations"]) {
            for (const row of DATA[key] || []) {
              const code = (row.restrictionCode || "").trim().toUpperCase();
              if (code) codes.add(code);
            }
          }
          return [...codes].sort();
        })(),
        above: line
          ? Boolean(line.compareDocumentPosition(document.getElementById("rows")) &
              Node.DOCUMENT_POSITION_FOLLOWING)
          : false,
      };
    });
    check(
      "the page says what the reference feed was asked and answered",
      reference.shown && reference.text.length > 20,
      reference.text
    );
    // A freshness claim is worse than no claim if the date in it is broken.
    // The first version sliced the reference feed's HTTP-date header as an ISO
    // timestamp and shipped "published undefined undefined NaN" to a real
    // reader, so the line is checked for the failure rather than for its exact
    // wording, which would break for the wrong reason whenever it improves.
    check(
      "no date in it is unrenderable",
      !/undefined|NaN|\[object|null/.test(reference.text),
      reference.text
    );
    // The portal sends no Last-Modified on these feeds, so the sentence has to
    // read properly with no publication date -- the usual case, not the edge
    // one. Joining a clause that is not there with a comma leaves "restriction
    // feed, still publishes", which is what a reader of the real page saw.
    check(
      "the sentence still reads when the portal gives no publication date",
      !/feed, (still|no longer)\b/.test(reference.text),
      reference.text
    );
    check(
      "and says it before the table it qualifies",
      reference.above,
      `${reference.text} (above: ${reference.above})`
    );
    // The invariant is about the WORDED claim, not the status value: a build
    // that compared nothing must not be allowed to read as confirmed. Tested
    // against the sentence a reader actually sees, because that is the thing
    // that can mislead. Deliberately not matched on exact wording -- pinning
    // the check to one phrasing would make it a test of this project's prose
    // rather than of the claim, and would break for the wrong reason whenever
    // the sentence is improved.
    //
    // The claim is publication, never agreement about wording. Run against the
    // real portal feed, comparing the two texts word for word reported 628 of
    // 628 conditions disagreeing on a feed where none did: the portal words a
    // condition in prose where the fares feed compresses it, so a page saying
    // the portal disagrees with everything it quotes is crying wolf, and a
    // reader who sees it once stops reading the rest of the line.
    const claimsAll = /still publishes all/i.test(reference.text);
    check(
      "the portal is only credited with publishing when conditions were compared",
      !claimsAll || reference.compared > 0,
      `${reference.text} (compared: ${reference.compared})`
    );
    // The count has to be the conditions on this page's own rows, not every
    // code the origin's flows could carry. Those differ on the real feed -- 32
    // against 10 -- and a page reporting on conditions it does not show is
    // asking a reader to take on trust the one claim they cannot look up.
    check(
      "the conditions it reports on are the ones this page's rows carry",
      reference.status !== "checked" && reference.status !== "unpublished"
        ? true
        : reference.compared === reference.shownCodes.length,
      `compared: ${reference.compared}, on the page: ${reference.shownCodes.join(", ")}`
    );
    // And when it names a condition the portal has retired, the reader has to
    // be able to find that condition here. A named code the page does not show
    // is an alarm about somebody else's paperwork.
    check(
      "and every condition it names is one the reader can find here",
      reference.unlisted.every((code) => reference.shownCodes.includes(code)),
      `unlisted: ${reference.unlisted.join(", ")}, on the page: ${reference.shownCodes.join(", ")}`
    );
    check(
      "an unchecked reference feed says so rather than reading as confirmation",
      reference.status === "absent" || reference.status === "unknown"
        ? !claimsAll && /not been checked|not checked|could not be checked|no .*feed was checked/i.test(reference.text)
        : true,
      `${reference.text} (status: ${reference.status})`
    );
    // The claim is about publication, so the page must never say the two feeds
    // agree about what a condition *says*. The portal words conditions in prose
    // and the fares feed compresses them; that is not a disagreement and must
    // not be printed as one.
    check(
      "it claims publication rather than agreement about wording",
      !/\bagrees\b|\bdisagrees\b|\bwording matches\b/i.test(reference.text),
      reference.text
    );
    if (reference.status === "unpublished") {
      check(
        "a condition the portal no longer lists is named",
        reference.unlisted.length > 0 &&
          reference.unlisted.every((code) => reference.text.includes(code)),
        `${reference.text} (unlisted: ${reference.unlisted.join(", ")})`
      );
    }
    check(
      "and it sits beside the result count, not in the footer",
      fresh.beforeSummary && fresh.beforeTable && !fresh.inFooter,
      `${fresh.text} beforeSummary=${fresh.beforeSummary} beforeTable=${fresh.beforeTable} inFooter=${fresh.inFooter}`
    );
    if (!fresh.feedDate) {
      // A synthetic feed has no download date, so there is nothing to measure.
      // The sentence that is missing is the honest one: the page does not
      // invent a download for a feed nobody downloaded.
      check("a feed with no download date claims no age for its prices", !/downloaded/.test(fresh.text), fresh.text);
    } else {
      // The number has to be the right number, and the threshold beside it has
      // to be the build's own. "Downloaded 24 September 2026" next to a stale
      // "0 days old" passes a presence test and misleads the reader deciding
      // whether to trust a fare, which is the only reason the sentence is here.
      // One day of slack: the page dates the download against its own clock
      // and so does this, and a run straddling midnight is not a defect.
      const expected = daysSince(fresh.feedDate);
      const stated = /downloaded .*?,\s*(\d+) days? old/.exec(fresh.text);
      const namesTheThreshold = new RegExp(String(fresh.staleAfterDays) + "-day freshness threshold").test(fresh.text);
      check(
        "a feed with a download date says how old its prices are",
        // A download dated after today is a clock or download fault, and the
        // page says so instead of counting negative days; the sentence for
        // that case carries no age and no threshold, so it is answered on its
        // own terms rather than failed for omitting a number it cannot have.
        expected < 0
          ? /dated after today/.test(fresh.text)
          : stated !== null &&
            Math.abs(Number(stated[1]) - expected) <= 1 &&
            namesTheThreshold,
        `${fresh.text} (downloaded: ${fresh.feedDate}, ${expected} day(s) ago, threshold: ${fresh.staleAfterDays})`
      );
    }

    // 7d. S26: a shortlist of candidate places that can be compared, shared
    // and copied, and that never reads as a booking.
    await open(facts.affordable);
    const shortlist = await page.evaluate(() => {
      // Every priced row, not the one a cheapest-affordable budget happens to
      // leave: comparing two places needs two places on screen.
      setBudget(budgetCeiling());
      currentPage = 1;
      render();
      const rows = Array.from(document.querySelectorAll("#rows tr[data-crs]"));
      if (rows.length < 2) return { rows: rows.length };
      const first = rows[0].querySelector(".shortlist-toggle");
      const second = rows[1].querySelector(".shortlist-toggle");
      const facts = () => Array.from(document.querySelectorAll("#shortlistList li")).map((li) => li.textContent);
      const saved = [];
      first.click();
      saved.push(facts());
      second.click();
      const both = facts();
      const address = window.location.href;
      // The party price is the price a pair would see, so the comparison has
      // to follow the party control.
      document.querySelector('input[name="unit"][value="party"]').checked = true;
      render();
      const asPair = facts();
      document.querySelector('input[name="unit"][value="adult"]').checked = true;
      render();
      const asSolo = facts();
      const share = document.getElementById("shortlistShare").textContent;
      const pressed = rows.map((row) => row.querySelector(".shortlist-toggle").getAttribute("aria-pressed"));
      return { both, asPair, asSolo, share, address, pressed, names: both.map((text) => text.slice(0, 24)) };
    });
    if (shortlist.rows !== undefined && shortlist.rows < 2) {
      for (const name of [
        "a shortlisted place is listed with its price, time and changes",
        "and the list is a list of places, not a booking",
        "the shortlist is in the address, so it can be shared",
        "a refresh brings the shortlist back",
        "and it follows the party the reader has chosen",
        "one control clears it",
      ]) {
        check(name, notExercised(`this page lists ${shortlist.rows} row(s) to choose from`));
      }
    } else {
      check(
        "a shortlisted place is listed with its price, time and changes",
        shortlist.both.length === 2 &&
          shortlist.both.every((text) => /£\d/.test(text) && /(no change|\d+ change\(s\)|changes unknown)/.test(text)),
        JSON.stringify(shortlist.both)
      );
      check(
        "and the list is a list of places, not a booking",
        /not a booking/i.test(await page.textContent("#shortlist")) &&
          /no train is chosen/i.test(await page.textContent("#shortlist")),
        (await page.textContent("#shortlistHeading")) || ""
      );
      const wanted = await page.evaluate(() => shortlistCodes);
      check(
        "the shortlist is in the address, so it can be shared",
        wanted.every((code) => shortlist.address.includes("short=" + code)),
        shortlist.address
      );
      check(
        "and it follows the party the reader has chosen",
        shortlist.asPair.length === 2 && shortlist.asPair.some((text, index) => text !== shortlist.asSolo[index]),
        JSON.stringify({ pair: shortlist.asPair, solo: shortlist.asSolo })
      );
      check("and the row control announces it is on", shortlist.pressed.filter((value) => value === "true").length === 2, shortlist.pressed.join(","));
      // A shared link is the whole point, so it is opened, not assumed.
      await page.goto(shortlist.address);
      const restored = await page.evaluate(() => Array.from(document.querySelectorAll("#shortlistList li")).length);
      check("a refresh brings the shortlist back", restored === 2, `${restored} of 2`);
      const copied = await page.evaluate(() => {
        document.getElementById("shortlistCopy").click();
        return null;
      });
      void copied;
      await page.waitForFunction(
        () => /copied|copy/i.test(document.getElementById("shortlistStatus").textContent || ""),
        null,
        { timeout: 3000 }
      ).catch(() => {});
      const text = await page.evaluate(() => navigator.clipboard.readText());
      check(
        "and the copied list names the origin, the prices and says it is not a booking",
        /Shortlist from /.test(text) && /Budget: /.test(text) && /not a booking/i.test(text) && text.includes("£"),
        text
      );
      await open(facts.affordable);
      await page.evaluate(() => { document.getElementById("shortlistClear").click(); });
      check(
        "one control clears it",
        (await page.evaluate(() => document.querySelectorAll("#shortlistList li").length)) === 0 &&
          !(await page.evaluate(() => window.location.search.includes("short="))),
        (await page.evaluate(() => document.getElementById("shortlistEmpty").textContent)) || ""
      );
    }

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

    // The change control exists exactly when the build wrote another station's
    // page, and both halves of that are asserted here. The block below drives
    // it, so a control that is present must work; and a page with nowhere to
    // change to must not carry an inert one, which is the bug this replaced.
    // Dropping the control everywhere would otherwise pass by testing less.
    const pickerState = await page.evaluate(() => ({
      others: (DATA.stations || []).length,
      control: Boolean(document.getElementById("changeOrigin")),
    }));
    check(
      "the change control appears exactly when the build has another station",
      pickerState.control === (pickerState.others > 0),
      `${pickerState.others} other station(s), control rendered: ${pickerState.control}`
    );

    const pickerButton = page.locator("#changeOrigin");
    if (await pickerButton.count()) {
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
      // The path is the route; the query is the reader's search state (S05),
      // so it is judged on the path alone and then checked separately below.
      const route = href === null ? null : new URL(href, "http://x").pathname;
      check(
        "options are links to station pages",
        route === null
          ? notExercised("this page lists no other station to link to")
          : route.startsWith(baseHref + "from/") && route.endsWith("/") && route.length > baseHref.length + 6,
        href === null ? "" : `${href} under base ${baseHref}`
      );
      // S06: choosing another station is a correction of where the reader is
      // leaving from, so the option carries the search they have already made.
      check(
        "the option carries the budget on screen",
        href === null
          ? notExercised("this page lists no other station to link to")
          : new URL(href, "http://x").searchParams.get("budget") === (await page.inputValue("#budgetNumber")),
        href === null ? "" : href
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
      // S11: the same tolerant match the chooser has, on the page that offers
      // thousands of stations rather than three.
      const listedCrses = await page.evaluate(() => DATA.stations.map((station) => station.crs));
      // Lowercased to match the page, which lowercases what the reader typed
      // before comparing: a code in the address bar is upper case.
      const fragment = (listedCrses[0] || "").slice(0, 2).toLowerCase();
      await page.fill("#originSearch", fragment);
      const byFragment = await page.evaluate(() =>
        Array.from(document.querySelectorAll("#originPicks a")).map((a) => ({
          code: (a.querySelector(".code") || {}).textContent || "",
          name: (a.querySelector("span") || {}).textContent || "",
        }))
      );
      check(
        "a code fragment finds its station in the picker",
        fragment && byFragment.length > 0 && byFragment.some((row) => row.code.toLowerCase().startsWith(fragment)) &&
          byFragment.every((row) => row.code.toLowerCase().startsWith(fragment) || row.name.toLowerCase().includes(fragment)),
        `${fragment} -> ${byFragment.map((row) => row.code).join(" ") || "nothing"}`
      );
      await page.fill("#originSearch", "");
      // S12: the one distinction a first-time reader cannot guess, said once,
      // in the page's own terms, and only on the page where it is true.
      const firstUse = (await page.textContent("#firstUse")) || "";
      check(
        "the page says the station name in the heading moves station and the rest filters",
        // The control is the station's own name with a chevron beside it, so the
        // sentence has to name the name rather than a button that is no longer
        // there: it said "Change" for exactly as long as that word was on the
        // page, which is the whole point of the check.
        /station name/i.test(firstUse) && /narrow/i.test(firstUse),
        JSON.stringify(firstUse)
      );
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
      check("pressing the station control again reopens the picker", await page.locator("#originPicker").isVisible());
      await pickerButton.click();
      check("and it closes it again", !(await page.locator("#originPicker").isVisible()));
      // Keyboard-only reachability of the picker's first option.
      await pickerButton.click();
      const firstOption = page.locator("#originPicks a").first();
      check(
        "picker options are keyboard-focusable links",
        pickCount
          ? await firstOption.evaluate((el) => el.tagName === "A" && new URL(el.href).pathname.endsWith("/"))
          : notExercised("this page lists no option to focus")
      );
      // The same key that enters the chooser's list enters this one: the picker
      // is that selector reached from the heading, so a reader who has met one
      // has met the other.
      await page.fill("#originSearch", "");
      await page.focus("#originSearch");
      await page.keyboard.press("ArrowDown");
      check(
        "ArrowDown from the picker field enters its list",
        pickCount
          ? await page.evaluate(() => document.activeElement === document.querySelector("#originPicks a"))
          : notExercised("this page lists no option to enter")
      );
      await page.keyboard.press("ArrowUp");
      check(
        "and ArrowUp comes back to the picker field",
        pickCount
          ? await page.evaluate(() => document.activeElement && document.activeElement.id === "originSearch")
          : notExercised("see above")
      );
      await page.keyboard.press("Escape");
    } else {
      // A build with one origin has nowhere to change to, so the heading
      // states the station as text and carries no control -- the inert button
      // this replaced was rendered, focusable, announced and did nothing. So
      // the absence is not the whole check: the origin still has to be named
      // in the heading, or a page could pass by dropping it altogether.
      const named = await page.evaluate(() => {
        const el = document.querySelector("#pageHeading .origin-name");
        return el ? el.textContent.trim() : "";
      });
      const heading = await page.textContent("#pageHeading");
      check(
        "the heading names the station as text when there is no Change control",
        Boolean(named) && (heading || "").includes(named),
        named ? `no control, heading says ${named}` : "no .origin-name in the heading"
      );
      // And the page does not spend its first-use note telling the reader what
      // a Change control does when there is no Change control. The note was
      // static text written for a page that has one, so a one-station build
      // pointed a reader at a button that was not there.
      const firstUse = (await page.textContent("#firstUse")) || "";
      check(
        "and the page does not tell the reader about a Change control it does not have",
        !/change/i.test(firstUse),
        JSON.stringify(firstUse)
      );
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
  return { given, file, checks, stopped, notStation, kind };
}

/**
 * The accessibility matrix (S41).
 *
 * The AA commitment was evidenced from one station-page happy path. This is
 * the other half of it: the same checks, run against every route in the run --
 * the chooser, a station page, the privacy page -- in both colour schemes, at
 * desktop and phone widths, and at the width a 200% zoom leaves behind.
 *
 * What it measures, and why each is a measurement rather than an assertion
 * about the source:
 *
 *   - names: the accessibility tree's own computed names, so a control with no
 *     label is caught even when its visible text comes from a ::before.
 *   - contrast: the rendered colours, composited over whatever is behind them
 *     and resolved through a canvas, so color-mix() and alpha are read as the
 *     reader sees them. The threshold follows the text: 4.5:1 for body copy,
 *     3:1 for large text, which is the AA rule rather than a number chosen here.
 *   - targets: the rendered box, plus a positioned ::after's slop, which is
 *     how the row actions reach 44px while staying small on screen.
 *   - zoom: a 320px viewport, which is what 200% zoom leaves of a 640px screen,
 *     with the two things zoom breaks checked directly -- sideways scrolling and
 *     text that shrinks below the base size.
 *   - keyboard: the focus ring, read off the focused element, and the fact that
 *     Tab reaches a control without a mouse.
 */
async function checkAccessibilityMatrix(page, url, check, routeKind) {
  // ------------------------------------------------------------- the names
  // Read from the browser's own accessibility tree rather than from the
  // markup, so a control whose name comes from a label, an aria-label or text
  // this suite has never heard of is counted, and one with no name at all is
  // caught however it was built.
  await page.goto(url);
  const CONTROL_ROLES = new Set([
    "button", "link", "textbox", "searchbox", "checkbox", "radio", "combobox",
    "slider", "spinbutton", "switch", "heading", "listbox", "option", "img",
  ]);
  const tree = await page.locator("body").ariaSnapshot();
  const unnamed = [];
  let named = 0;
  for (const line of String(tree).split("\n")) {
    // A line reads `- link "Name":`, `- heading "Name" [level=1]` or
    // `- button:` for a control with no name at all. The quoted string between
    // the role and the colon is the accessible name; anything in brackets is
    // state, not a name.
    const found = line.match(/^\s*-\s+([a-z]+)\s*(?:"([^"]*)")?\s*:?/);
    if (!found || !CONTROL_ROLES.has(found[1])) continue;
    if (found[2] && found[2].trim()) named += 1;
    else unnamed.push(found[1]);
  }
  check(
    `every control on the ${routeKind} has a name a screen reader reads`,
    unnamed.length === 0 && named > 0,
    `${named} named, ${unnamed.length} unnamed${unnamed.length ? " (" + unnamed.join(", ") + ")" : ""}`
  );

  // The heading is the one sentence a screen reader announces for the page, so
  // what it says is the page's own claim, not a detail. Its currency sign was
  // aria-hidden, so the name read "for up to 20" while the status line said
  // "£20.00" -- the reader was told a number and no unit. Read from the
  // browser's tree, not from the markup, so hiding the sign again fails here.
  if (routeKind === "station" || routeKind === "chooser") {
    const headingName = (String(await page.locator("h1").ariaSnapshot()).split("\n")[0].match(/"([^"]*)"/) || [])[1] || "";
    // The chooser's page data is STATIONS, not DATA, and its heading asks which
    // station rather than naming one, so the station is only read where it is
    // both in the payload and in the sentence.
    const origin = routeKind === "station" ? await page.evaluate(() => DATA.origin.name) : "";
    check(
      `the heading a screen reader reads states the budget in pounds${origin ? " and names the station" : ""}`,
      /up to £\s*\d+/.test(headingName) && (!origin || headingName.includes(origin)),
      headingName || "(no heading name)"
    );
  }

  // A placeholder is an accessible-name fallback, so the check above reports a
  // field that has only a placeholder as named -- and it names it with text the
  // reader cannot see once they start typing, which is the whole reason C12 was
  // a defect while the gate stayed green. A control counted as properly labelled
  // here has a real label element, an aria-label or an aria-labelledby; only a
  // placeholder is a failure.
  const placeholderOnly = await page.evaluate(() => {
    const namedProperly = (el) => {
      if (el.getAttribute("aria-label")?.trim()) return true;
      const by = el.getAttribute("aria-labelledby");
      if (by && by.split(/\s+/).some((id) => document.getElementById(id)?.textContent?.trim())) {
        return true;
      }
      if (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`)?.textContent?.trim()) {
        return true;
      }
      return el.closest("label")?.textContent?.trim() ? true : false;
    };
    const out = [];
    for (const el of document.querySelectorAll("input, select, textarea")) {
      if (el.closest("[hidden]") || el.type === "hidden") continue;
      if (!el.placeholder?.trim()) continue;
      if (!namedProperly(el)) {
        out.push((el.id || el.name || el.type) + ` (placeholder "${el.placeholder.trim().slice(0, 24)}")`);
      }
    }
    return out;
  });
  check(
    `no ${routeKind} field is named only by its placeholder`,
    placeholderOnly.length === 0,
    placeholderOnly.length ? placeholderOnly.join("; ") : "every placeholder field also has a real label"
  );
  // C29: one main landmark, and the back link and footer stay outside it as
  // the navigation landmarks they are. A route that omitted it made landmark
  // navigation the only way through a long page, and nothing above caught it.
  const landmarks = await page.evaluate(() => ({
    main: document.querySelectorAll("main").length,
    nav: document.querySelectorAll("nav").length,
    navsInMain: document.querySelectorAll("main nav").length,
    headingsInMain: document.querySelectorAll("main h1").length,
  }));
  check(
    `the ${routeKind} has exactly one main landmark around its own content`,
    landmarks.main === 1 && landmarks.headingsInMain === 1,
    JSON.stringify(landmarks)
  );

  // C13: a links list of identical "Tickets" entries cannot be scanned. Every
  // ticket link is named for its destination, and no two names collide, so a
  // reader choosing one from a list can tell them apart.
  const isStation = routeKind === "station";
  const ticketNames = await page.evaluate(() => {
    const names = Array.from(document.querySelectorAll("a.buy")).map(
      (a) => a.getAttribute("aria-label") || a.textContent.trim());
    return { total: names.length, distinct: new Set(names).size, sample: names.slice(0, 3) };
  });
  check(
    `the ${routeKind} names each ticket link for its destination`,
    !isStation || (ticketNames.total > 0 && ticketNames.distinct === ticketNames.total),
    `${ticketNames.distinct} distinct of ${ticketNames.total}` +
      (ticketNames.sample.length ? " -- " + JSON.stringify(ticketNames.sample) : "")
  );

  // One heading, and it is the page's own subject rather than a brand line.
  const headings = await page.evaluate(() =>
    Array.from(document.querySelectorAll("h1, h2")).map((el) => ({
      level: el.tagName,
      text: (el.textContent || "").trim(),
    }))
  );
  check(
    "the route has one first-level heading and it is not the brand",
    headings.filter((h) => h.level === "H1").length === 1 &&
      !/rail budget/i.test(headings[0].text),
    JSON.stringify(headings.slice(0, 3))
  );

  // ------------------------------------------------------------ the keyboard
  const focusStyle = () =>
    page.evaluate(() => {
      const el = document.activeElement;
      const described = (node) => {
        if (!node) return "";
        const style = getComputedStyle(node);
        // Everything a focus style is allowed to change. An indicator is a
        // visible difference, and WCAG does not require it to be an outline --
        // but it does require there to be one.
        return [
          style.outlineStyle, style.outlineWidth, style.outlineColor,
          style.backgroundColor, style.borderBottomStyle, style.borderBottomColor,
          style.borderBottomWidth, style.boxShadow, style.textDecorationLine,
        ].join("|");
      };
      return {
        reached: !!el && el !== document.body,
        tag: el ? el.tagName : null,
        self: described(el),
        parent: el ? described(el.parentElement) : "",
        name: el ? (el.getAttribute("aria-label") || el.textContent || el.value || "").trim().slice(0, 40) : "",
      };
    });
  const beforeFocus = await focusStyle();
  await page.keyboard.press("Tab");
  const focus = await focusStyle();
  const outlined = await page.evaluate(() => {
    const style = getComputedStyle(document.activeElement);
    return style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0;
  });
  check(
    "one Tab reaches a control",
    focus.reached && focus.tag !== "BODY",
    JSON.stringify(focus)
  );
  check(
    "the focused control shows where it is",
    focus.reached && (outlined || focus.self !== beforeFocus.self || focus.parent !== beforeFocus.parent),
    JSON.stringify({ outlined, before: beforeFocus.self.slice(0, 40), after: focus.self.slice(0, 40), parent: focus.parent.slice(0, 40) })
  );

  // The refinements fold away on every route and at every width, so they are
  // opened here, once, before anything is measured. A control inside a closed
  // panel has no box, and both readers below skip an element with no box: the
  // contrast reader and the target reader would each quietly stop covering the
  // filter families they exist to hold to AA and to 44px. Opening it is also a
  // state a reader reaches by pressing the control, so what is measured is a
  // state the page can really be in.
  if (await page.locator("#moreFiltersToggle").count()) {
    await page.evaluate(() => {
      const details = document.getElementById("moreFilters");
      const toggle = document.getElementById("moreFiltersToggle");
      if (details && toggle && details.dataset.open !== "true") toggle.click();
    });
  }

  // ------------------------------------------- contrast, targets, reflow, per scheme
  for (const scheme of ["light", "dark"]) {
    // The page's own control decides the palette now, not the OS preference, so
    // the scheme is set the way a reader sets it: by pressing the switch. The
    // media query is still emulated, because a reader whose system says light
    // and who has chosen dark must get dark, and the system default is only
    // the default.
    await page.emulateMedia({ colorScheme: scheme });
    const theme = await setTheme(page, scheme);
    check(
      `the switch takes the page to the ${scheme} palette`,
      theme === scheme,
      `switch says ${theme}, asked for ${scheme}`
    );
    // The scheme has to change the page, or the dark pass is the light pass
    // wearing a different name and every check below it proves nothing.
    const painted = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    check(
      `the ${scheme} palette is the one the page paints`,
      scheme === "light" ? isLight(painted) : !isLight(painted),
      painted
    );

    // The credit is NRE's mark reversed onto a dark plate, painted by the
    // page's own stylesheet rather than by editing the artwork, and the plate is
    // the same in both palettes. Legibility is therefore not a thing to argue
    // from the CSS: the guidelines require the logo to be legible, so the
    // painted ink is measured against the plate it is painted on, in each
    // scheme, and the plate is measured against the page it sits on. Reading it
    // off the computed style is what makes this a check of the page: drop the
    // rule that reverses the mark and the ink falls back to the file's own
    // #2E2D7F, which on a dark plate is 1.4:1 and fails here.
    // Read from the page rather than from the credit read further down, so
    // this does not depend on which half of the matrix runs first.
    if (await page.locator(".nre-credit").count()) {
      const legibility = await page.evaluate(() => {
        const plate = document.querySelector(".nre-logo");
        // A colour, as the pixels a reader would see: painted onto a canvas over
        // whatever is behind it. Not a regex over the computed string, because
        // the border here is a color-mix() with an alpha in it, and the browser
        // reports such a colour in a notation whose numbers are not channels --
        // color(srgb .8 .84 1 / .22) rather than rgba(205, 214, 255, .22). A
        // checker that reads the numbers out of that string reads 0.8 as a
        // channel and measures a colour nobody is looking at.
        const probe = document.createElement("canvas");
        probe.width = probe.height = 1;
        const painter = probe.getContext("2d");
        const asColour = (rgb) => "rgb(" + rgb.join(", ") + ")";
        const paint = (value, backdrop) => {
          // Both arguments have to be colours the canvas understands. A
          // [r, g, b] array assigned to fillStyle is not one: the assignment is
          // ignored and the previous fillStyle survives, so an earlier call in
          // this same function left the backdrop as whatever it last painted.
          // That is not a hypothetical -- it is what made this check pass a
          // plate whose border was transparent, because the "edge" it measured
          // was the ink from the shape before it.
          painter.clearRect(0, 0, 1, 1);
          painter.fillStyle = typeof backdrop === "string" ? backdrop : asColour(backdrop);
          painter.fillRect(0, 0, 1, 1);
          painter.fillStyle = value;
          painter.fillRect(0, 0, 1, 1);
          const pixel = painter.getImageData(0, 0, 1, 1).data;
          return [pixel[0], pixel[1], pixel[2]];
        };
        const luminance = (rgb) =>
          rgb
            .map((channel) => {
              const c = channel / 255;
              return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
            })
            .reduce((sum, c, i) => sum + c * [0.2126, 0.7152, 0.0722][i], 0);
        const ratio = (a, b) => {
          const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
          return (hi + 0.05) / (lo + 0.05);
        };
        const painted = plate ? getComputedStyle(plate) : null;
        const bodyColour = paint(getComputedStyle(document.body).backgroundColor, "#fff");
        const plateColour = painted ? paint(painted.backgroundColor, bodyColour) : bodyColour;
        // Every shape the mark is drawn from, and the worst of them rather than
        // the first: 20 of the mark's 22 shapes are paths and two are rects, so
        // a rule that caught the paths alone would leave two rectangles in
        // NRE's blue, and a checker that read one path would not notice. The
        // clip-path rect in <defs> is filtered out because it is never painted,
        // and it is black by default, so counting it would fail every page.
        const shapes = plate
          ? Array.from(plate.querySelectorAll("svg path, svg rect, svg polygon, svg circle, svg ellipse"))
              .filter((shape) => {
                const box = shape.getBoundingClientRect();
                return box.width > 0 && box.height > 0;
              })
          : [];
        const inks = shapes.map((shape) => paint(getComputedStyle(shape).fill, plateColour));
        // The plate has to be findable: a dark chip on a dark page is a plate
        // only because of the line round it. An earlier version compared the
        // border's colour string to the plate's, which every border passed,
        // visible or not -- "rgba(0, 0, 0, 0)" differs from everything by
        // string alone. This composites the border over the plate it is drawn
        // on and measures what is left, so 1.5:1 is the line.
        const edgeInk = painted ? paint(painted.borderTopColor, plateColour) : plateColour;
        const borderWide = painted ? parseFloat(painted.borderTopWidth) >= 1 : false;
        return {
          plate: plateColour.join(","),
          shapes: inks.length,
          markOnPlate: inks.length ? Math.min(...inks.map((ink) => ratio(ink, plateColour))) : 0,
          plateOnPage: ratio(plateColour, bodyColour),
          edge: borderWide ? ratio(edgeInk, plateColour) : 0,
        };
      });
      // 3:1 is the non-text contrast floor for the mark itself. The plate has
      // to be findable, which in the dark palette means the edge rather than a
      // fill that differs from the page: #141b3d on #14181d is 1.06:1.
      check(
        `the NRE mark stays legible in ${scheme}`,
        legibility.markOnPlate >= 3 && (legibility.plateOnPage >= 1.05 || legibility.edge >= 1.5),
        `${legibility.shapes} shapes, ink on plate ${legibility.plate}: ${legibility.markOnPlate.toFixed(1)}:1, plate on page ${legibility.plateOnPage.toFixed(2)}:1, edge ${legibility.edge.toFixed(2)}:1`
      );
    }

    const contrast = await page.evaluate(() => {
      // Any CSS colour the browser understands, read as pixels: color-mix(),
      // oklab, currentColor and alpha all resolve, and a contrast ratio
      // computed from a string would be a guess about the string.
      const probe = document.createElement("canvas");
      probe.width = probe.height = 1;
      const ctx = probe.getContext("2d", { willReadFrequently: true });
      const toRgba = (value) => {
        ctx.clearRect(0, 0, 1, 1);
        ctx.fillStyle = "#000";
        ctx.fillStyle = value;
        ctx.fillRect(0, 0, 1, 1);
        const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data;
        return [r, g, b, a / 255];
      };
      // What is behind the text, composited: a transparent background is not a
      // background, it is whatever is behind it.
      const behind = (el) => {
        const layers = [];
        for (let node = el; node; node = node.parentElement) {
          const [r, g, b, a] = toRgba(getComputedStyle(node).backgroundColor);
          if (a > 0) {
            layers.push([r, g, b, a]);
            if (a === 1) break;
          }
        }
        let out = [255, 255, 255, 1];
        for (const [r, g, b, a] of layers.reverse()) {
          out = [r * a + out[0] * (1 - a), g * a + out[1] * (1 - a), b * a + out[2] * (1 - a), 1];
        }
        return out;
      };
      const channel = (value) => {
        const c = value / 255;
        return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
      };
      const luminance = ([r, g, b]) =>
        0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
      const ratio = (a, b) => {
        const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
        return (light + 0.05) / (dark + 0.05);
      };
      const SELECTORS = [
        ["body", "the page's own text"],
        [".sub", "the intro"],
        [".tag", "a hint under a control"],
        ["a", "a link"],
        [".footnav a", "a footer link"],
        ["th", "a column heading"],
        ["#summary", "the result count"],
        ["td", "a cell"],
        [".restriction", "a travel condition"],
        [".restriction[data-status=restricted]", "a restricted-fare condition"],
        ["h1", "the page heading"],
        ["h2", "a section heading"],
        [".condition", "the condition in words"],
        [".origin-picker-label", "the change-station field label"],
        [".chipcount", "a chip's count"],
        [".condition", "the readable condition"],
        [".validity", "the fare validity"],
        ["#facetNotice", "a filter-change notice"],
        [".synthetic-banner", "the synthetic-data banner"],
        [".synthetic-banner strong", "the banner's label"],
        [".origin-slot", "the station slot in the heading"],
        ["#orderingNote", "the chooser's ordering note"],
        ["legend", "a group label"],
        [".choice-chip", "a destination chip"],
        [".segmented label", "a ticket type"],
        [".railcard-choice", "a party choice"],
        [".toggle", "a button"],
        [".buy", "a ticket link"],
        ["#moreFiltersToggle", "the refinements control"],
        ["#nomatch", "a no-match message"],
        [".method summary", "the method disclosure"],
        ["#empty", "an empty result"],
      ];
      // The condition and its validity are one disclosure away on the row, so
      // the first row is opened for the measuring and closed again afterwards.
      // A contrast check that only measured what happened to be unfolded is how
      // the warn token regressed before (C14): the sentence a reader must not
      // misread would simply have stopped being measured.
      const rowToggle = document.querySelector("#rows tr:not(.detail) .toggle[aria-expanded=false]");
      if (rowToggle) rowToggle.click();
      const measured = [];
      for (const [selector, what] of SELECTORS) {
        const el = document.querySelector(selector);
        if (!el) continue;
        const style = getComputedStyle(el);
        const box = el.getBoundingClientRect();
        if (box.width === 0 || box.height === 0) continue;
        const size = parseFloat(style.fontSize);
        const bold = parseInt(style.fontWeight, 10) >= 700;
        // WCAG's own split: large text is 24px, or 18.66px when bold.
        const needed = size >= 24 || (bold && size >= 18.66) ? 3 : 4.5;
        const value = ratio(toRgba(style.color).slice(0, 3), behind(el).slice(0, 3));
        measured.push({ what, selector, value: Math.round(value * 100) / 100, needed, size });
      }
      if (rowToggle) rowToggle.click();
      return measured;
    });
    const failures = contrast.filter((entry) => entry.value < entry.needed);
    check(
      `every kind of text meets AA contrast in ${scheme}`,
      contrast.length >= 4 && failures.length === 0,
      `${contrast.length} measured, worst ${contrast.reduce((low, e) => Math.min(low, e.value / e.needed), 99).toFixed(2)}x of what it needs` +
        (failures.length ? " -- " + failures.map((f) => `${f.what} ${f.value}:1 needs ${f.needed}:1`).join("; ") : "")
    );

    // The condition a reader must not misread is now one disclosure away, so
    // the probe above opens the first row before it measures. That is the whole
    // of the C14 regression cover, and a probe that stopped opening it would
    // report every condition as 0x0 and skip it in silence -- so the measurement
    // is a check in its own right on every route that has rows.
    check(
      `the row's fare condition is measured for contrast in ${scheme}`,
      contrast.some((entry) => entry.selector === ".condition") ||
        (await page.locator("#rows .toggle").count()) === 0,
      contrast.map((entry) => entry.selector).join(" ")
    );

    // ------------------------------------------------------------- the targets
    const targets = await page.evaluate(() => {
      // The rendered box, plus a positioned ::after's slop: the row actions
      // are small marks that reach 44px through it, and measuring the mark
      // alone would fail a target that is really 44px.
      const hitBox = (el) => {
        const rect = el.getBoundingClientRect();
        const after = getComputedStyle(el, "::after");
        if (after.content === "none" || after.position !== "absolute") {
          return { w: rect.width, h: rect.height, rawW: rect.width, rawH: rect.height };
        }
        // The slop is written as a negative inset and reaches outwards, so its
        // magnitude is what adds to the box.
        const inset = (name) => {
          const raw = parseFloat(after[name]);
          return Number.isFinite(raw) ? Math.abs(raw) : 0;
        };
        return {
          w: rect.width + inset("left") + inset("right"),
          h: rect.height + inset("top") + inset("bottom"),
          rawW: rect.width,
          rawH: rect.height,
        };
      };
      // WCAG 2.5.8 is 24px for any pointer target; the row actions and the
      // phone control are promised at 44px, so both are measured and named.
      const MINIMUM = 24;
      const PROMISED = 44;
      const small = [];
      const underPromised = [];
      const inlineInText = [];
      const seen = [];
      for (const el of document.querySelectorAll(
        "button, a[href], input, select, textarea, summary, [role=button]"
      )) {
        if (el.closest("[hidden]")) continue;
        const style = getComputedStyle(el);
        if (style.display === "none" || style.visibility === "hidden") continue;
        // A control that is optically hidden inside its own label is measured
        // through that label: the label is what a finger touches.
        const measured = el.type && el.closest("label") ? el.closest("label") : el;
        if (measured.getBoundingClientRect().width === 0 || measured.getBoundingClientRect().height === 0) continue;
        // WCAG 2.5.8 exempts a target that sits in a sentence or a block of
        // text -- a link inside a fare's description is read, not aimed at. The
        // exemption is counted and reported rather than applied silently.
        if (el.tagName === "A" && getComputedStyle(el).display === "inline") {
          const surrounding = (el.parentElement ? el.parentElement.textContent : "").trim();
          if (surrounding.length > el.textContent.trim().length) {
            inlineInText.push(el.getAttribute("href") || el.textContent.trim().slice(0, 30));
            continue;
          }
        }
        const box = hitBox(measured);
        const record = {
          what: el.id || el.getAttribute("aria-label") || el.tagName.toLowerCase(),
          w: Math.round(box.w),
          h: Math.round(box.h),
          raw: `${Math.round(box.rawW || box.w)}x${Math.round(box.rawH || box.h)}`,
          html: el.outerHTML.slice(0, 70),
        };
        seen.push(record);
        if (Math.min(box.w, box.h) + 0.5 < MINIMUM) small.push(record);
        // The filter families were 36px and outside the gate entirely, because
        // the control a finger touches is a <label> wrapping a hidden input and
        // the selector below only ever asked for buttons, links and inputs.
        // C23 holds the segmented ticket types, the destination chips and the
        // party choices to the same 44px the row actions are held to, and the
        // label is what is measured.
        const filterControl = el.closest(".segmented label, .choice-chip, .railcard-choice, input[type=range]");
        const promised = el.classList.contains("toggle") || el.classList.contains("buy") ||
          el.id === "moreFiltersToggle" || !!filterControl;
        if (promised && Math.min(box.w, box.h) + 0.5 < PROMISED) underPromised.push(record);
      }
      return { small, underPromised, inlineInText, seen };
    });
    check(
      `every pointer target is at least 24px in ${scheme}`,
      targets.small.length === 0,
      targets.small.length
        ? JSON.stringify(targets.small.slice(0, 5))
        : `${targets.seen.length} targets measured, ${targets.inlineInText.length} inline in a sentence and exempt`
    );
    check(
      `the controls promised at 44px are at least 44px in ${scheme}`,
      targets.underPromised.length === 0,
      targets.underPromised.length ? JSON.stringify(targets.underPromised.slice(0, 5)) : "row actions and the phone control"
    );

    // ------------------------------------------------------------------ zoom
    // 320px is what 200% zoom leaves of a 640px screen: the width at which a
    // layout that only works at desktop stops working.
    await page.setViewportSize({ width: 320, height: 720 });
    const zoomed = await page.evaluate(() => {
      const html = document.documentElement;
      return {
        overflow: Math.max(html.scrollWidth, document.body.scrollWidth) - window.innerWidth,
        body: parseFloat(getComputedStyle(document.body).fontSize),
      };
    });
    check(
      `at 320px -- a 200% zoom -- nothing scrolls sideways in ${scheme}`,
      zoomed.overflow <= 0,
      `${zoomed.overflow}px`
    );
    check(
      `at 320px the text is still the base size in ${scheme}`,
      zoomed.body >= 16,
      `${zoomed.body}px`
    );

    // The width check above can only judge the text a fixture happens to
    // contain, and that is how a 36px sideways scroll shipped: the demo
    // privacy page names a contact made of ordinary words, while the real one
    // carries an address whose 40 unbroken characters were wider than the
    // column. The demo page passed and the real page did not.
    //
    // So the contract is tested directly rather than waited for: put a run
    // that cannot break in the page's own text and prove the page still does
    // not scroll sideways. No fixture can hide it, because the fixture supplies
    // nothing -- the check brings its own worst case.
    const injected = await page.evaluate(() => {
      const long = "A".repeat(160) + "@example.invalid";
      // The narrowest real container on the page, not the document, because
      // the document can always look fine while a column inside it is the
      // thing that actually widened.
      const targets = [
        ...document.querySelectorAll("main p, main li, main td, main dd, main h2, p.muted, .tag"),
      ];
      if (!targets.length) return { skipped: true };
      const probe = document.createElement("p");
      probe.className = "muted";
      probe.id = "overflow-probe";
      probe.textContent = long;
      const host = targets[Math.min(2, targets.length - 1)];
      host.parentElement.insertBefore(probe, host);
      // Two ways a reader actually loses text, and only two.
      //
      // A column is a fault when it CLIPS: its computed overflow-x is not
      // visible, so the excess is gone rather than painted outside. The
      // opposite case is not a fault and was measured here first: a small
      // button reports a few pixels of scrollWidth past its own box while its
      // text sits ten pixels inside it on both sides. That is box arithmetic,
      // and calling it a defect would have sent someone to fix a rendering
      // that is correct.
      //
      // `.sr-only` is excluded by width: a 1px box holding nowrap text is
      // what that class is FOR -- read by assistive technology, not seen -- so
      // its scrollWidth says nothing about layout. A real column is hundreds
      // of pixels wide, so nothing else is skipped by this.
      const clipped = Math.max(
        0,
        ...[...document.querySelectorAll("main *")]
          .filter((el) => el.clientWidth > 2)
          .filter((el) => getComputedStyle(el).overflowX !== "visible")
          .map((el) => el.scrollWidth - el.clientWidth)
      );
      const scroll =
        Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) -
        window.innerWidth;
      probe.remove();
      return { skipped: false, scroll, clipped, tagged: targets.length };
    });
    check(
      `at 320px an unbreakable run does not widen the page in ${scheme}`,
      injected.skipped || (injected.scroll <= 0 && injected.clipped <= 1),
      injected.skipped
        ? "the page has no prose container to measure, so this proves nothing"
        : `document ${injected.scroll}px, worst clipped column ${injected.clipped}px, from ${injected.tagged} candidate(s)`
    );
  }

  // The theme switch. A reader who cannot change the palette has a page built
  // for one person, so the control is read from the page: it is there, it is a
  // switch with a name, and the state it holds is the palette the page is
  // actually painting. The default is checked on a first visit with the
  // storage emptied, because "dark unless the reader says otherwise" is a claim
  // about a reader who has never pressed anything.
  await page.evaluate(() => { try { localStorage.clear(); } catch (e) { /* nothing stored */ } });
  await page.reload();
  const themeControl = await page.evaluate(() => {
    const toggle = document.getElementById("themeToggle");
    if (!toggle) return { present: false };
    return {
      present: true,
      role: toggle.getAttribute("role"),
      checked: toggle.getAttribute("aria-checked"),
      theme: document.documentElement.dataset.theme,
      name: (toggle.textContent || "").trim(),
      hidden: toggle.hidden,
      box: (() => {
        const r = toggle.getBoundingClientRect();
        return { w: Math.round(r.width), h: Math.round(r.height) };
      })(),
    };
  });
  check(
    "the page offers a theme switch",
    themeControl.present && !themeControl.hidden,
    themeControl.present ? (themeControl.hidden ? "rendered but hidden" : "shown") : "no #themeToggle"
  );
  if (themeControl.present) {
    check(
      "the theme switch is a named switch whose state is the page's palette",
      themeControl.role === "switch" &&
        Boolean(themeControl.name) &&
        themeControl.checked === String(themeControl.theme === "dark"),
      `role ${themeControl.role}, name "${themeControl.name}", checked ${themeControl.checked}, theme ${themeControl.theme}`
    );
    check(
      "and a reader with no stored choice gets the dark palette",
      themeControl.theme === "dark" && themeControl.checked === "true",
      `first visit painted ${themeControl.theme}`
    );
    check(
      "and the switch is a pointer target of at least 44px",
      themeControl.box.w >= 44 && themeControl.box.h >= 44,
      `${themeControl.box.w}x${themeControl.box.h}px`
    );
    // The choice has to outlive the visit, or it is not a choice.
    await page.locator("#themeToggle").click();
    const chosen = await page.evaluate(() => document.documentElement.dataset.theme);
    await page.reload();
    const afterReload = await page.evaluate(() => document.documentElement.dataset.theme);
    check(
      "and the reader's choice survives a reload",
      chosen === "light" && afterReload === "light",
      `pressed to ${chosen}, reloaded as ${afterReload}`
    );
  }

  // The NRE source credit, on a page that composes the NRE notice and on no
  // other page. The Developer Brand Guidelines require the "Powered by National
  // Rail Enquiries" logo and a link to NRE's site, placed underneath the
  // information the feed supplied, so all three are read here rather than
  // assumed from the markup: the mark must be visible, must be legible (it is
  // dark blue on a fixed fill, so the dark palette could swallow it), and must
  // carry a name a screen reader reads, because the mark is paths.
  const credit = await page.evaluate(() => {
    const node = document.querySelector(".nre-credit");
    if (!node) return { present: false };
    const img = node.querySelector('[role="img"]');
    const link = node.querySelector("a");
    const mark = node.querySelector("svg");
    const plate = node.querySelector(".nre-logo");
    const box = plate ? plate.getBoundingClientRect() : { width: 0, height: 0 };
    return {
      present: true,
      name: img ? img.getAttribute("aria-label") : "",
      href: link ? link.getAttribute("href") : "",
      markPaths: mark ? mark.querySelectorAll("path").length : 0,
      width: Math.round(box.width),
      height: Math.round(box.height),
      // Underneath the results, which is the placement the guidelines name for
      // a feed that is the page's predominant information.
      belowTable: (() => {
        const table = document.querySelector("table");
        if (!table) return true;
        return table.getBoundingClientRect().top < node.getBoundingClientRect().top;
      })(),
    };
  });
  const nreNotice = await page.evaluate(() =>
    [].concat((typeof DATA !== "undefined" && DATA.attribution) || []).some(
      (notice) => /National Rail Enquiries/.test(notice)
    )
  );
  check(
    "the NRE credit appears exactly when the page acknowledges NRE as the source",
    credit.present === nreNotice,
    `credit: ${credit.present}, NRE notice: ${nreNotice}`
  );
  if (credit.present) {
    check(
      "the credit shows the Powered by National Rail Enquiries mark",
      credit.markPaths > 0 && credit.name === "Powered by National Rail Enquiries",
      `${credit.markPaths} path(s), name "${credit.name}"`
    );
    check(
      "and it links to NRE, as the guidelines ask",
      /nationalrail\.co\.uk/.test(credit.href),
      credit.href
    );
    check(
      "and it is legible, sitting on its own plate underneath the information",
      credit.width > 100 && credit.height >= 24 && credit.belowTable,
      `${credit.width}x${credit.height}px, below the table: ${credit.belowTable}`
    );
  }

  // The matrix leaves the page as it found it: the next section drives controls.
  await page.emulateMedia({ colorScheme: "light" });
  await setTheme(page, "light");
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto(url);
}

/**
 * Press the page's theme switch until it holds the asked-for scheme, and report
 * what it holds afterwards. Driving the real control rather than setting the
 * attribute is the point: a switch that reads right and does nothing is the
 * defect this suite exists to catch, and setting the attribute by hand would
 * never notice.
 */
async function setTheme(page, scheme) {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const now = await page.evaluate(() => document.documentElement.dataset.theme);
    if (now === scheme) return now;
    const toggle = page.locator("#themeToggle");
    if (!(await toggle.count()) || (await toggle.isHidden())) return now || "no control";
    await toggle.click();
  }
  return page.evaluate(() => document.documentElement.dataset.theme);
}

/** Is a painted background the light one? Used only to prove the scheme landed. */
function isLight(colour) {
  const parts = String(colour).match(/[\d.]+/g);
  if (!parts) return true;
  const [r, g, b] = parts.map(Number);
  // Rec. 601 luma: the same split the eye makes, and enough to tell #fff from
  // #14181d without a colour library.
  return 0.299 * r + 0.587 * g + 0.114 * b > 128;
}

function report(results) {
  const counted = (predicate) =>
    results.reduce((sum, result) => sum + result.checks.filter(predicate).length, 0);
  const total = counted(() => true);
  const failed = counted((entry) => !entry.ok && !entry.skipped);
  const skipped = counted((entry) => entry.skipped);
  // The budget is measured over the pages whose checks can be skipped, so the
  // pages that cannot skip do not make an over-skipped sweep look within it.
  const skippable = results.filter(
    (result) => result.kind === "station" || result.kind === "chooser"
  );
  const skipTotal = skippable.reduce(
    (sum, result) => sum + result.checks.length,
    0
  );
  const skipCount = skippable.reduce(
    (sum, result) => sum + result.checks.filter((entry) => entry.skipped).length,
    0
  );
  const overSkipBudget = skipCount > skipTotal * SKIP_BUDGET;
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
  console.log(`\n${summary}${skipped ? `, ${skipped} check(s) not exercised by the pages swept` : ""}`);
  // The budget is stated in the failure as a number, because "too many checks
  // were skipped" without the fraction and the count is a claim a reader has to
  // take on trust -- and the whole reason for the budget is that a run which
  // printed a skip count could still be green.
  if (overSkipBudget) {
    // Named per page, because "too many checks were skipped" is only
    // actionable if it says which page has too little in it.
    const worst = skippable
      .map((result) => ({
        given: result.given,
        count: result.checks.filter((entry) => entry.skipped).length,
        of: result.checks.length,
      }))
      .filter((entry) => entry.count > 0)
      .sort((left, right) => right.count - left.count)
      .map((entry) => `${entry.given} (${entry.count}/${entry.of})`);
    console.error(
      `\nOver the skip budget: ${skipCount} of ${skipTotal} checks on the station and ` +
        `chooser pages were not exercised, which is more than ${Math.round(
          SKIP_BUDGET * 100
        )}%.\nThe pages under test have too little in them for the suite to say much ` +
        `about them; give them destinations, or accept a smaller claim about what the run ` +
        `proved.\nSkipped by page: ${worst.join(", ")}`
    );
  }
  process.exit(failed || broken.length || nothingTested || overSkipBudget ? 1 : 0);
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
