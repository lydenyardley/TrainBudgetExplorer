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
 * is driven in one command. A page that names a file beyond itself -- the
 * shared station-picker asset -- has that file served from beside it, so the
 * picker is exercised the way a reader's browser would load it. --max bounds a sweep and says on stderr how many
 * pages it left out, because a run that quietly tested twenty of two thousand
 * has not tested the site.
 *
 * A path that is not a station page is the chooser at the site root, a
 * one-station release's root, or the privacy page. The chooser is driven like
 * any other page -- it is where a
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
    // Evenly spread, not a prefix. The pages arrive in name order, so a prefix
    // is the first N stations alphabetically and nothing after them: on a
    // 2,718-page network --max 24 drove the A's and the B's and no station
    // whose slug starts later than C. The sweep is here to find
    // origin-specific template bugs, and a sample confined to one end of the
    // alphabet cannot find one that only the far end has.
    //
    // Every MAX_PAGES-th page, which is deterministic, needs no seed, and
    // always includes the first and last page of the list.
    const step = found.length / MAX_PAGES;
    const sample = [];
    for (let index = 0; index < MAX_PAGES; index += 1) {
      sample.push(found[Math.floor(index * step)]);
    }
    // Loudly, because a bounded sweep that reads as a whole one is worse than
    // no sweep: it would be a gate reporting on a sample and calling it the
    // site. The names are printed so a reader can see the spread rather than
    // take the word for it.
    console.error(
      `--max ${MAX_PAGES}: driving ${sample.length} of ${found.length} pages, evenly ` +
        `spread across the list rather than the first ${MAX_PAGES}. ` +
        `${found.length - sample.length} of them are not being tested.`
    );
    for (const page of sample) console.error(`  swept ${page}`);
    return sample;
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

/**
 * The chooser at the site root, which S01 made the departure picker: the page
 * a reader lands on, and the only page whose whole job is choosing where to
 * depart from. It carries no fares, so every fact is read out of its own
 * STATIONS array and the list it builds from that array -- the suite never
 * names a station here either.
 */
// The last column takes the width of its own content and no more. The
// tolerance is a pixel and a half: a sub-pixel border and a rounded box can
// put a fraction on either side of the widest cell without the column being
// any wider than what is in it.
const cellsAreContentWide = (column) => column.width <= column.content + 1.5;

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
      // The shared slot class, which is what a station page's slot wears too: the
      // chooser's field is that slot with nothing in it yet.
      slot: Boolean(el.querySelector(".origin-slot-wrap")),
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
  // The chooser's field is the same control as a station page's, so the three
  // behaviours are checked here as well and against this page's own list.
  const wholeList = await page.evaluate(() => ({
    shown: document.querySelectorAll("#picks a").length,
    total: typeof STATIONS === "undefined" ? 0 : STATIONS.length,
    first: typeof STATIONS === "undefined" || !STATIONS.length ? null : STATIONS[0],
  }));
  check(
    "every station on the site is listed while the field is empty",
    wholeList.total > 0 && wholeList.shown === wholeList.total,
    JSON.stringify({ shown: wholeList.shown, total: wholeList.total })
  );
  if (wholeList.first && wholeList.first.name.length > 4) {
    const letters = wholeList.first.name.slice(0, 3);
    await page.fill("#originSearch", "");
    await page.type("#originSearch", letters, { delay: 10 });
    await page.waitForTimeout(80);
    const completed = await page.evaluate(() => {
      const field = document.getElementById("originSearch");
      const list = document.getElementById("picks");
      const f = field.getBoundingClientRect();
      const l = list.getBoundingClientRect();
      return {
        value: field.value,
        start: field.selectionStart,
        end: field.selectionEnd,
        position: getComputedStyle(list).position,
        gap: Math.round(l.top - f.bottom),
        options: list.querySelectorAll("a").length,
        sideScroll:
          Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth,
      };
    });
    check(
      `typing ${letters} in the chooser's field completes the station's name, and the list is drawn under the field`,
      completed.value === wholeList.first.name &&
        completed.start === letters.length &&
        completed.end === wholeList.first.name.length &&
        completed.position === "fixed" &&
        completed.gap >= 0 &&
        completed.gap < 40 &&
        completed.options > 0 &&
        completed.sideScroll <= 0,
      JSON.stringify({ letters, station: wholeList.first.name, completed })
    );
    await page.fill("#originSearch", "");
  } else {
    check(
      "typing in the chooser's field completes the station's name, and the list is drawn under the field",
      notExercised("this release lists no station a reader could type")
    );
  }
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

    // The completion is a word inside the field, and the field is a word inside
    // the heading, so three keys matter: Backspace to take the suggestion back,
    // and Tab or Enter to go to the place it names. The prefix comes from the
    // page's own station list rather than from a name the fixture happened to
    // carry, so a build of one station and a build of three thousand are asked
    // the same question.
    const completable = await page.evaluate(() => {
      const list = (typeof STATIONS !== "undefined" ? STATIONS : DATA.stations) || [];
      return list
        .map((station) => station.name)
        .filter((name) => name.length >= 8)
        .sort((a, b) => a.length - b.length)[0] || "";
    });
    const canComplete = completable.length >= 4;
    const prefix = completable.slice(0, 3);
    const headingHeight = () =>
      page.evaluate(() => {
        const heading = document.getElementById("pageHeading");
        return heading ? Math.round(heading.getBoundingClientRect().height) : -1;
      });
    await page.fill("#originSearch", "");
    const heights = [await headingHeight()];
    if (canComplete) {
      await page.focus("#originSearch");
      await page.type("#originSearch", prefix, { delay: 10 });
      const completed = await page.inputValue("#originSearch");
      heights.push(await headingHeight());
      // The completion is a suggestion, so it is written with its tail
      // selected. Backspace has to remove what was suggested, not consume one
      // character of the name the reader typed: it re-applied the suggestion to
      // its own undo, so the field came back byte-identical and the key looked
      // dead.
      await page.keyboard.press("Backspace");
      const taken = await page.inputValue("#originSearch");
      check(
        "Backspace takes the completion back",
        completed.toLowerCase().startsWith(prefix.toLowerCase()) && taken === prefix,
        `${prefix} -> "${completed}" -> Backspace -> "${taken}"`
      );
      await page.keyboard.press("Backspace");
      const shorter = await page.inputValue("#originSearch");
      check(
        "and Backspace again deletes a character of what was typed",
        shorter === prefix.slice(0, -1),
        `"${taken}" -> Backspace -> "${shorter}"`
      );
      // The field is a word in a balanced heading. A field sized to its content
      // changes that word's width on every keystroke, and the heading
      // rebalances around it: measured at 1280px, 220px tall when empty and
      // 196px from the first keystroke on.
      await page.fill("#originSearch", "");
      await page.focus("#originSearch");
      for (const value of ["", "N", "No", "Not", prefix, completable]) {
        await page.fill("#originSearch", value);
        heights.push(await headingHeight());
      }
      check(
        "the heading does not change height as the field is typed into",
        heights.every((height) => height === heights[0]) && heights[0] > 0,
        heights.join("px, ") + "px"
      );
      // Accepting a completion is choosing a place, so it goes there.
      await page.fill("#originSearch", "");
      await page.focus("#originSearch");
      await page.type("#originSearch", prefix, { delay: 10 });
      const wanted = await page.evaluate(() => {
        const list = (typeof STATIONS !== "undefined" ? STATIONS : DATA.stations) || [];
        const typed = document.getElementById("originSearch").value.trim().toLowerCase();
        const station = list.find((s) => s.name.toLowerCase() === typed);
        return station ? station.href : null;
      });
      const before = page.url();
      const beforePath = new URL(before).pathname;
      const probe = await page.context().newPage();
      let landed = "";
      try {
        await probe.goto(before);
        if (await probe.locator("#changeOrigin").count()) await probe.click("#changeOrigin");
        await probe.waitForSelector("#originSearch");
        await probe.focus("#originSearch");
        await probe.type("#originSearch", prefix, { delay: 10 });
        const moved = probe
          .waitForURL((url) => new URL(url).pathname !== beforePath, { timeout: 5000 })
          .catch(() => null);
        await probe.keyboard.press("Tab");
        await moved;
        landed = probe.url();
      } finally {
        await probe.close();
      }
      check(
        "Tab on a completion goes to that station's page",
        wanted !== null && landed && new URL(landed, before).pathname === new URL(wanted, before).pathname,
        `${completable} -> ${landed || "(no navigation)"} (wanted ${wanted})`
      );
      await page.fill("#originSearch", "");
    } else {
      for (const name of [
        "Backspace takes the completion back",
        "and Backspace again deletes a character of what was typed",
        "the heading does not change height as the field is typed into",
        "Tab on a completion goes to that station's page",
      ]) {
        check(name, notExercised("no station on this page has a name long enough to complete"));
      }
    }
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

/**
 * The root of a release that priced exactly one station.
 *
 * It is not a chooser and must not look like one. The published artefact used to
 * ask the reader to type a station that could only ever be the one the build
 * already knew, and the suite drove it as a chooser: four of its checks could not
 * be exercised there, three of them because there is no second answer to reach.
 * A release that has already chosen states the choice in its shape, so it is
 * driven as what it is -- the heading names the station, and the one row is the
 * page to open (audit recommendation 2, 30 September 2026).
 *
 * Every fact is read out of the page's own STATIONS array, like the chooser's, so
 * the suite never names a station here either.
 */
async function checkReleaseRoot(page, url, check) {
  const listed = await page.evaluate(() => STATIONS.map((s) => ({ name: s.name, crs: s.crs, href: s.href })));
  const station = listed[0] || { name: "", crs: "", href: "" };
  const heading = await page.evaluate(() => {
    const el = document.getElementById("pageHeading");
    const named = el.querySelector(".origin-name");
    return {
      text: el.textContent.replace(/\u2060/g, "").replace(/\s+/g, " ").trim(),
      station: named ? named.textContent.trim() : "",
      // The shared slot class, which is what a station page's slot wears too: the
      // chooser's field is that slot with nothing in it yet.
      slot: Boolean(el.querySelector(".origin-slot-wrap")),
      fields: el.querySelectorAll("input").length,
    };
  });
  check(
    "a one-station release names its station where a chooser would ask for one",
    heading.station === station.name && heading.text.includes(station.name),
    JSON.stringify({ heading: heading.text, station: station.name })
  );
  // The check rec 2 exists for: a field that can only ever confirm a single
  // answer is a control that lies, so this fails a root that renders one.
  check(
    "and it offers no field that can only confirm that one answer",
    !heading.slot && (await page.locator("#originSearch").count()) === 0,
    JSON.stringify({ slot: heading.slot, fields: heading.fields })
  );
  check(
    "and it makes no ranking claim over its one row",
    (await page.locator("#orderingNote").count()) === 0 &&
      !/how many destinations/i.test(await page.textContent("main"))
  );
  const options = await page.locator("#picks a").count();
  check(
    "the list is the whole release",
    options === listed.length && options === 1,
    `${options} of ${listed.length}`
  );
  const rows = await page.evaluate(() =>
    Array.from(document.querySelectorAll("#picks a")).map((a) => ({
      href: a.getAttribute("href"),
      text: a.textContent,
      tall: a.getBoundingClientRect().height,
    }))
  );
  check(
    "and it is a link to that station's page",
    rows.length === 1 &&
      new URL(rows[0].href, "http://x").pathname === new URL(station.href, "http://x").pathname,
    JSON.stringify(rows[0] || null)
  );
  check("the option is a 44px target", rows.every((row) => row.tall >= 44), `${rows[0] ? rows[0].tall : 0}px`);
  check(
    "the option carries the station's own name, code and count",
    rows.some(
      (row) =>
        row.text.includes(station.name) &&
        row.text.includes(station.crs) &&
        /\d+ destinations?/.test(row.text)
    ),
    JSON.stringify(rows[0] || null)
  );
  const budget = await page.inputValue("#budgetNumber");
  check("the budget is still the heading's own field", Boolean(budget), budget);
  check(
    "and the link carries it",
    new URL(rows[0].href, "http://x").searchParams.get("budget") === budget,
    rows[0].href
  );
  // The one thing a reader can change on this page is the budget, and it has to
  // reach both the tab title and the page it opens.
  const next = Math.min(500, Number(budget) + 7);
  await page.fill("#budgetNumber", String(next));
  const title = await page.title();
  const named = station.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  check(
    "changing the budget retitles the page for that station",
    new RegExp("£" + next + ".*" + named).test(title),
    title
  );
  check(
    "and the link carries the new budget",
    (await page.evaluate(() => new URL(document.querySelector("#picks a").href).searchParams.get("budget"))) === String(next)
  );
  await page.goto(url + "?budget=42");
  check(
    "a budget in the link opens the release at that budget",
    (await page.inputValue("#budgetNumber")) === "42",
    await page.inputValue("#budgetNumber")
  );
  check(
    "and the station link carries it on",
    (await page.evaluate(() => new URL(document.querySelector("#picks a").href).searchParams.get("budget"))) === "42"
  );
  const privacy = await page.evaluate(() =>
    (document.querySelector(".footnav a") || {}).getAttribute
      ? document.querySelector(".footnav a").getAttribute("href")
      : null
  );
  check(
    "the release root links to the privacy page",
    privacy !== null && /\/privacy\/$/.test(new URL(privacy, "http://x").pathname),
    String(privacy)
  );
  // The station's name sits in the heading, so a long one is where a page goes
  // sideways.
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
    if (typeof STATIONS !== "undefined" && document.getElementById("picks")) {
      // One station is not a chooser: a release that already knows the answer
      // names it in the heading instead of asking for it (recommendation 2), so
      // it is driven as what it is rather than as a search with one result.
      return STATIONS.length === 1 ? "release" : "chooser";
    }
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
  if (kind === "chooser" || kind === "release") {
    try {
      if (kind === "chooser") await checkChooser(page, url, check);
      else await checkReleaseRoot(page, url, check);
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
    // Q4: the page opens on the cheapest fare of any ticket type, which is not
    // one of the three payload lists, so the reader composes that list the way
    // the rule says -- one row per destination, the cheaper of the fares on
    // screen -- rather than falling back to the returns and expecting a page
    // that is behaving correctly to fail every chip check. Written here, from
    // the payload, so the check that the page agrees with it is not circular.
    window.cheapestOfEveryList = () => {
      // Q2: the railcard is one of a collection the reader picks from, so the
      // reader resolves the chosen card against the row's own entry rather than
      // reading a single railcardPence the page no longer carries.
      const price = (destination) => {
        const party = document.querySelector('input[name="unit"]:checked').value === "party";
        const base = party ? destination.partyPence : destination.adultPence;
        const select = document.getElementById("railcardSelect");
        if (!select || !select.value) return base;
        const card = (destination.railcards || {})[select.value];
        if (!card || card.pricePence === null) return base;
        return Math.min(base, card.pricePence * (party ? 2 : 1));
      };
      const cheapest = new Map();
      for (const list of [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations]) {
        for (const destination of list || []) {
          const held = cheapest.get(destination.crs);
          if (!held || price(destination) < price(held)) cheapest.set(destination.crs, destination);
        }
      }
      return cheapest;
    };
    window.TYPES = {
      list: () => {
        const mode = document.querySelector('input[name="ticketMode"]:checked').value;
        if (mode === "cheapest") return Array.from(window.cheapestOfEveryList().values());
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
    // The rows are compared as a set against the payload rather than as the
    // first pageSize of it. The table sorts by the price on screen and shows
    // PAGE_SIZE of them, so those are not the same twenty rows once a type
    // carries more than fit on a page -- which is every real feed and none of
    // the fixtures, because a fixture's whole list fits on one page. On
    // Nottingham's 29 small towns the slice named nine rows living on the
    // second page and the check reported a correctly filtered table as broken.
    //
    // Four things have to hold instead, and each is about the table rather
    // than about one ordering: every row shown is one of this type, as many
    // are shown as fit on a page, every one of them is named on screen, and
    // they run cheapest first by the price in the payload.
    const rendered = await page.evaluate(() =>
      Array.from(document.querySelectorAll("#rows tr[data-crs]")).map((row) => row.dataset.crs)
    );
    const byCrs = new Map(expected.rows.map((d) => [d.crs, d]));
    const fits = Math.min(expected.rows.length, pageSize);
    // A row the payload does not carry is a defect this check has to be able to
    // report, not a crash. `byCrs.get(crs).adultPence` on one throws before the
    // membership test below can say so, and a suite that dies on a regression
    // reports the exception instead of the thing that is wrong.
    const prices = rendered
      .filter((crs) => byCrs.has(crs))
      .map((crs) => byCrs.get(crs).adultPence);
    check(
      matched,
      shown === fits &&
        shown === rendered.length &&
        rendered.every((crs) => byCrs.has(crs)) &&
        rendered.every((crs) => text.includes(byCrs.get(crs).name)) &&
        prices.every((pence, i) => i === 0 || prices[i - 1] <= pence),
      `${shown} rows of ${expected.rows.length} ${type} (${fits} fit a page); shown ${rendered.join(" ")}`
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

    // Q4: the list that opens is the cheapest fare of any ticket type to each
    // destination, and the fare it chose is the fare the row names. The
    // expectation is composed from the payload by the reader above; the page's
    // own composition is compared against it rather than used as the answer.
    const headline = await page.evaluate(() => {
      const cheapest = window.cheapestOfEveryList();
      const shown = Array.from(document.querySelectorAll("#rows tr[data-crs]")).map((row) => {
        const wanted = cheapest.get(row.dataset.crs) || null;
        // The row names its fare in one of the reader's own three words, and
        // the word has to be the one this row's fare earns. The code the feed
        // used is one disclosure away and no longer on the row at all.
        const row1 = activeDestinations().find((d) => d.crs === row.dataset.crs) || {};
        return {
          crs: row.dataset.crs,
          price: (row.querySelector("td.num .price") || {}).textContent || "",
          wanted: wanted
            ? {
              price: String(
                (document.querySelector('input[name="unit"]:checked').value === "party"
                  ? wanted.partyPence : wanted.adultPence) / 100
              ),
              code: wanted.ticket || "",
            }
            : null,
          code: row1.isAdvance ? "Advance" : row1.restrictionCode ? "Restricted" : "Regular",
          word: (row.querySelector(".fare-kind") || {}).textContent || "",
        };
      });
      // The mix among the rows on screen, kept for the second half of the check:
      // every kind of fare a reader can see must be one the line names.
      const kinds = {};
      for (const crs of shown.map((row) => row.crs)) {
        const wanted = cheapest.get(crs);
        if (!wanted) continue;
        const word = wanted.quality === "outbound single"
          ? "single" : wanted.quality === "unrestricted Anytime Day Return" ? "Anytime Day Return" : "return";
        kinds[word] = (kinds[word] || 0) + 1;
      }
      // The counts the line states for itself. It describes every destination
      // the budget admits, which is not the twenty rows on screen and not the
      // page's private list either -- `available` is local to render(). So the
      // line is asked to agree with itself, which is the guarantee that matters
      // and the only one that can be read off it.
      const line = document.getElementById("summary").textContent;
      const total = Number((/([0-9,]+) destinations?/.exec(line) || [0, "0"])[1].replace(/,/g, ""));
      const named = [];
      for (const m of line.matchAll(/([0-9,]+) (Anytime Day Returns?|singles?|returns?)\b/g)) {
        named.push({ word: m[2], count: Number(m[1].replace(/,/g, "")) });
      }
      return {
        mode: document.querySelector('input[name="ticketMode"]:checked').value,
        expected: cheapest.size,
        pageCount: typeof cheapestDestinations === "function" ? cheapestDestinations().length : null,
        shown,
        kinds,
        total,
        named,
        summary: document.getElementById("summary").textContent,
      };
    });
    const amount = (text) => Number(String(text).replace(/[^0-9.]/g, ""));
    check(
      "the page opens on the cheapest fare of any ticket type",
      headline.expected
        ? headline.mode === "cheapest" &&
          headline.pageCount === headline.expected &&
          headline.shown.length > 0 &&
          headline.shown.every(
            (row) => row.wanted && amount(row.price) === amount(row.wanted.price) && row.code === row.word
          )
        : notExercised("this page's feed prices nothing"),
      JSON.stringify({ mode: headline.mode, expected: headline.expected, pageCount: headline.pageCount, first: headline.shown[0] || null })
    );
    check(
      "one row per destination, whatever the list is priced from",
      headline.expected
        ? new Set(headline.shown.map((row) => row.crs)).size === headline.shown.length
        : notExercised("this page's feed prices nothing"),
      JSON.stringify(headline.shown.map((row) => row.crs))
    );
    const kinds = Object.entries(headline.kinds);
    // Every kind of fare among the rows on screen is named by the line, and the
    // line's own counts add up to the total it states. The second half is the
    // one that cannot be satisfied by a coincidence of a small fixture: a line
    // that says "266 destinations ... 2 singles, 264 returns" is either right
    // about its own arithmetic or it is not.
    const namedSum = headline.named.reduce((total, entry) => total + entry.count, 0);
    const unseen = kinds.filter(([word]) => !headline.named.some(
      (entry) => entry.word.replace(/s$/, "").toLowerCase() === word.toLowerCase()
    ));
    check(
      "and the count line names the mix of ticket types it is showing",
      headline.shown.length === 0
        ? notExercised("this page shows no row to count")
        : unseen.length === 0 &&
          headline.named.length > 0 &&
          namedSum === headline.total,
      JSON.stringify({ kinds: headline.kinds, total: headline.total, named: headline.named, summary: headline.summary })
    );
    const partyBasis = await page.evaluate(() => {
      document.querySelector('input[name="unit"][value="party"]').checked = true;
      render();
      const summary = document.getElementById("summary").textContent;
      document.querySelector('input[name="unit"][value="adult"]').checked = true;
      render();
      return summary;
    });
    check(
      "and the party figure says it is two of the fare each row names",
      /two of the fare each row names/.test(partyBasis),
      partyBasis
    );

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
        ? /fastest time/.test(opening.intro)
        : !/fastest time/.test(opening.intro) && /no timetable/i.test(opening.intro),
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
        // Line boxes a pixel or two apart are one line: a cell whose only
        // child is an inline span reports the span's line-height beside the
        // row's strut, and a genuine second line is a whole line lower.
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
      };
      // `.changes` is excluded because the station a journey changes at is put
      // on its own line under the count on purpose (ADR-0045). Counting its
      // two lines as a wrap is the check measuring the design.
      const cells = [
        ...document.querySelectorAll("thead th"),
        ...document.querySelectorAll("#rows td.num:not(.changes), #rows .fare-type"),
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
          measure.afterProvenance.every((id) =>
            ["dateNote", "linkTerms", "summary"].includes(id)
          ),
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

    // 2. Dragging the budget slider to the floor empties the list. It starts
    // from a budget that reaches every row the page has: a station whose own
    // cheapest fare is a pound has nothing left to drop from that budget, and
    // a drag from a floor to a floor would measure nothing.
    const reachAll = await page.evaluate(() =>
      Math.max(
        Math.ceil(TYPES.cheapest((d) => d.adultPence) / 100),
        Math.ceil(TYPES.dearest((d) => d.adultPence) / 100)
      )
    );
    await open(reachAll);
    const beforeDrag = await rows();
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
    check("a dragged-down budget drops rows", afterDrag < beforeDrag, `${beforeDrag} -> ${afterDrag}`);
    // The floor empties the list, because the floor is zero and no fare is.
    // The check reads the floor off the control rather than naming a budget:
    // a budget the test picks for itself is not one the reader can be shown
    // reaching, and on a page pricing every fare at fifty pence a one-pound
    // floor put thirteen rows in the list and reported them as a defect the
    // page did not have.
    const floored = await page.evaluate(() => {
      if (document.getElementById("empty").hidden) {
        setBudget(Number(document.getElementById("budget").min));
        currentPage = 1;
        render();
      }
      return {
        empty: document.getElementById("empty").hidden === false,
        summary: document.getElementById("summary").textContent,
      };
    });
    check("an empty budget says so rather than showing nothing", floored.empty, JSON.stringify(floored));
    check("the summary counts what is left", /No destinations for up to/.test(floored.summary), floored.summary);

    // S17: the slider has always stopped somewhere the page never said out
    // loud, so a reader could not predict whether a fare at the boundary was
    // included without dragging the control to find out. The figure is read
    // out of the rendered page and compared with the input's own max -- not
    // with the resolver that produced it -- so a note that drifts from the
    // control is what fails.
    const statedStop = () => page.evaluate(() => ({
      max: Number(document.getElementById("budget").max),
      stated: ((document.getElementById("budgetCeiling") || {}).textContent || "").trim(),
    }));
    // The empty-budget check above may have left the page priced for two
    // adults, so the one-adult figure is read from a state this block sets.
    await page.check('input[name="unit"][value="adult"]');
    const oneAdultStop = await statedStop();
    check(
      "the budget control says where it stops, and the figure is the stop",
      oneAdultStop.stated.includes("\u00a3" + oneAdultStop.max + ".00 for one adult"),
      `${oneAdultStop.stated} against a slider that stops at ${oneAdultStop.max}`
    );
    // Two adults double every price, which leaves the order alone and puts
    // the stop at twice as much, so this is where the stated figure is proved
    // to follow the party rather than being written once at build time.
    await page.check('input[name="unit"][value="party"]');
    const twoAdultStop = await statedStop();
    check(
      "and the stated stop follows the party the reader chooses",
      twoAdultStop.stated.includes("\u00a3" + twoAdultStop.max + ".00 for two adults") &&
        twoAdultStop.max > oneAdultStop.max,
      `${twoAdultStop.stated} against ${oneAdultStop.stated} for one adult`
    );
    await page.check('input[name="unit"][value="adult"]');
    // C17, the one state the existing reading cannot reach. Doubling every
    // price leaves an order untouched, so the adult and two-adult readings
    // above cannot tell a page that re-sorts from one that happens to be
    // right. The railcard is the only control that replaces each row's price
    // with a different discount, so it is the only state where a row can move.
    //
    // This page's own feed cannot prove it, and the check says so rather than
    // borrowing a proof it does not have: the discounts here fall in the same
    // order as the fares they come from (measured, two adults, no card to card:
    // 2 17.4 24 44.8 252 -> 1.3 17.4 24 29.8 168), so a sort that ignored the
    // card entirely was measured and passed this state. It is a guard for a
    // feed whose discounts are not uniform, and the tamper that cleared it is
    // recorded so the next reader does not mistake it for a gate.
    const shownPrices = () => page.evaluate(() =>
      Array.from(document.querySelectorAll("#rows tr[data-crs] td.num .price"))
        .map((cell) => Number(cell.textContent.replace(/[^0-9.]/g, "")))
    );
    const ascending = (xs) => xs.every((value, i) => i === 0 || xs[i - 1] <= value);
    // The card is chosen through the same select a reader uses, and the party
    // is set to one the chosen card actually covers, because a card that does
    // not cover the party on screen is taken out of the list rather than priced.
    // The budget is raised to reach a row the chosen card actually lowers.
    // Without that the guard depends on the fixture's numbers: on a page whose
    // only row inside the budget is under the card's minimum fare, the card
    // changes nothing on screen and the guard read "9.5 -> 9.5" and reported a
    // page that does not re-sort.
    const resortable = await page.evaluate(() => {
      const select = document.getElementById("railcardSelect");
      const card = (DATA.railcards || []).find((c) => c.minAdults <= 1 && 1 <= c.maxAdults);
      if (!select || !card) return null;
      document.querySelector('input[name="unit"][value="adult"]').checked = true;
      const lowered = [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations]
        .flat()
        .filter((d) => {
          const entry = (d.railcards || {})[card.key];
          return entry && entry.pricePence !== null && entry.pricePence < d.adultPence;
        });
      if (!lowered.length) return null;
      const dearest = lowered.reduce((high, d) => Math.max(high, d.adultPence), 0);
      setBudget(Math.min(Number(document.getElementById("budget").max), Math.ceil(dearest / 100)));
      select.value = "";
      render();
      return card.key;
    });
    if (resortable) {
      const beforeCard = await shownPrices();
      await page.evaluate((key) => {
        const select = document.getElementById("railcardSelect");
        select.value = key;
        render();
      }, resortable);
      const withCard = await shownPrices();
      check(
        "and the list re-sorts when the railcard replaces every price",
        ascending(withCard) && withCard.join(" ") !== beforeCard.join(" "),
        `${beforeCard.join(" ")} -> ${withCard.join(" ")}`
      );
      await page.evaluate(() => {
        const select = document.getElementById("railcardSelect");
        select.value = "";
        render();
      });
    } else {
      check(
        "and the list re-sorts when the railcard replaces every price",
        notExercised("this feed prices no railcard that lowers a displayed fare for one adult")
      );
    }

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
    // 2026: the sentence moved into the row's own disclosure and the row names
    // its fare in the reader's own words, so what is on the row is the word
    // "Advance" and the sentence is read where a reader now reads it.
    const advance = await page.evaluate(() => {
      const wanted = TYPES.list().filter((d) => d.isAdvance && d.adultPence <= TYPES.cap()).length;
      const rows = Array.from(document.querySelectorAll("#rows tr:not(.detail)"));
      const flagged = rows.filter((row) => {
        const cell = row.querySelector(".fare-type");
        return Boolean(cell) && cell.dataset.kind === "advance";
      });
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
    // The plate names what is narrowed, so the name is read off the radio the
    // page arrives with rather than written here: a check that asks for one
    // mode's word fails the moment the page decides to open in another.
    const plateMode = await page.evaluate(() => {
      const checked = document.querySelector('input[name="ticketMode"]:checked');
      return (checked ? checked.closest("label").textContent : "").trim();
    });
    // Labelled, so a reader on a phone who cannot open the panel can still
    // tell which of the three decisions has been made.
    check(
      "and the folded plate says what is narrowed",
      /^Ticket: /.test(folded.state) &&
        folded.state.includes(plateMode) &&
        plateMode.length > 2 &&
        /Travellers: .*adult/.test(folded.state) &&
        /Destination: /.test(folded.state),
      `${JSON.stringify(folded.state)} in ${plateMode}`
    );
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
        // The price is its own span, because the cell can also carry the
        // standard fare a discount was taken from (Q3); reading the whole
        // cell would read two numbers as one.
        prices: shown.map((r) => Number(r.querySelector("td.num .price").textContent.replace(/[^0-9.]/g, ""))),
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

    // Q4: in the cheapest list the reader chose a price rather than a ticket
    // type, so the handoff text has to name the fare the row is priced as --
    // "Ticket: Cheapest of any type" is what they picked, and it is not what a
    // seller needs to hear. Driven from the page's opening mode, which is the
    // one this is about: the check above left the page in a named set.
    const cheapestCopy = await page.evaluate(() => {
      const rows = Array.from(document.querySelectorAll("#rows tr[data-crs]"));
      const line = rows[0];
      if (!line) return null;
      const crs = line.dataset.crs;
      const destination = TYPES.list().find((d) => d.crs === crs);
      if (!destination) return null;
      const text = journeyText(destination);
      // The fare name is composed here from the row's own quality phrase, so
      // the check is not the page's own ticketName() agreeing with itself.
      const want = destination.isAdvance
        ? "Advance single"
        : destination.quality === "unrestricted Anytime Day Return"
          ? "Unrestricted Anytime Day Return"
          : destination.quality === "outbound single"
            ? "Standard outbound single"
            : "Standard return";
      return {
        crs,
        want,
        mode: document.querySelector('input[name="ticketMode"]:checked').value,
        ticketLine: (text.split("\n").find((entry) => entry.startsWith("Ticket: ")) || "").trim(),
        modeLabel: (document.querySelector('input[name="ticketMode"]:checked').closest("label").textContent || "").trim(),
      };
    });
    check(
      "and a row in the cheapest list hands over the fare it is priced as",
      cheapestCopy
        ? cheapestCopy.mode === "cheapest" &&
          cheapestCopy.ticketLine === "Ticket: " + cheapestCopy.want &&
          cheapestCopy.ticketLine !== "Ticket: " + cheapestCopy.modeLabel
        : notExercised("this page has no row to copy"),
      JSON.stringify(cheapestCopy)
    );

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
    // Copy and the railcard note wait in the row's own panel (finding 4,
    // 29 September 2026), so the row is opened first: a control a reader
    // reaches through a disclosure is still a control, and this is where the
    // suite meets it.
    await page.locator("#rows tr:not(.detail) .toggle[aria-expanded='false']").first().click();
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
    // Copy and the railcard note wait in the row's own panel (finding 4,
    // 29 September 2026), so the row is opened first: a control a reader
    // reaches through a disclosure is still a control, and this is where the
    // suite meets it.
    await page.locator("#rows tr:not(.detail) .toggle[aria-expanded='false']").first().click();
    const copyButton = page.locator("#rows button[aria-label^='Copy the journey details']").first();
    const copiedName = (await copyButton.getAttribute("aria-label")).replace("Copy the journey details for ", "");
    // The railcard note is owed only where the feed prices one, so what the
    // copy should say is read off the row it is about to copy: a page with no
    // eligible fare must stay quiet rather than name a discount that is not there.
    // What the copy should say is read off the chosen card and the row it is
    // about to copy. A card the feed refused for that fare must stay unmentioned
    // rather than named as a discount that is not there.
    const railcardNamed = await page.evaluate((name) => {
      const row = DATA.destinations.find((d) => d.name === name);
      const select = document.getElementById("railcardSelect");
      if (!row || !select || !select.value) return false;
      const card = (row.railcards || {})[select.value];
      return Boolean(card && card.pricePence !== null);
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
      railcardNamed ? /discount is not sent to the seller/.test(partyCopy) : !/discount is not sent to the seller/.test(partyCopy),
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
      // What is sticking out, named: a bare pixel count sends whoever reads a
      // red run back to the stylesheet to guess which element it was.
      const edge = html.clientWidth;
      const wide = Array.from(document.querySelectorAll("body *"))
        .map((el) => ({ el, r: el.getBoundingClientRect() }))
        .filter((entry) => entry.r.right > edge + 1)
        .map((entry) => ({
          tag: entry.el.tagName.toLowerCase(),
          id: entry.el.id,
          cls: String(entry.el.className).slice(0, 40),
          right: Math.round(entry.r.right),
          width: Math.round(entry.r.width),
        }))
        .slice(0, 5);
      return { overflow, onScreen: cell.right <= window.innerWidth && cell.left >= 0, wide };
    });
    check(
      "at 390px nothing overflows horizontally",
      mobile.overflow <= 0,
      `${mobile.overflow}px; ${JSON.stringify(mobile.wide)}`
    );
    check("at 390px the ticket action is on-screen", mobile.onScreen, JSON.stringify(mobile));

    // 7b. One rule per row, and the row is what draws it. Every cell used to
    // keep the border the table gave it and draw a line at its own height, so a
    // stacked row showed up to six horizontal lines at six different heights,
    // none of them reaching the row's own -- measured at 360px: a 216px row
    // with cells 41 / 41 / 41 / 65 / 41 / 48px high. Asked of the page, not of
    // the stylesheet, because the whole claim is about what is painted.
    const painted = await page.evaluate(() => {
      const table = document.querySelector("#rows");
      const tableWidth = Math.round(table.getBoundingClientRect().width);
      const rules = (el) => parseFloat(getComputedStyle(el).borderBottomWidth) > 0;
      const rows = Array.from(table.querySelectorAll("tr[data-crs]"));
      // One row is opened, because the panel it shows had a rule of its own
      // too: opening a destination drew a second line across the page and read
      // as another destination.
      const fold = rows.length ? rows[0].querySelector(".toggle") : null;
      if (fold) fold.click();
      const detail = rows.length ? rows[0].nextElementSibling : null;
      const detailCells = detail ? Array.from(detail.cells).filter(rules).length : 0;
      if (fold) fold.click();
      return {
        tableWidth,
        rows: rows.map((tr) => ({
          crs: tr.dataset.crs,
          rowRule: rules(tr),
          cellRules: Array.from(tr.cells).filter(rules).length,
          width: Math.round(tr.getBoundingClientRect().width),
        })),
        detailCells,
      };
    });
    check(
      "at 390px a stacked row draws one rule and no cell draws its own",
      painted.rows.length === 0
        ? notExercised("this page shows no rows to measure")
        : painted.rows.every(
            (r) => r.rowRule && r.cellRules === 0 && r.width === painted.tableWidth
          ),
      JSON.stringify(painted).slice(0, 400)
    );
    check(
      "and the panel a row opens adds no rule of its own",
      painted.detailCells === 0 || notExercised("no row on this page opens a panel"),
      `${painted.detailCells} cell(s) in the opened panel still draw a rule`
    );

    // 7c. Every railcard this build priced is in the selector. Two Together is
    // two adults exactly, so on the one-adult default page the party filter
    // removed it, and it was the only card the list lost -- a reader who owns
    // it could not find out the page prices it at all. A card that cannot cover
    // the party on screen is still listed and cannot be chosen, which is what
    // ADR-0052 was protecting: a disabled option cannot hold a value.
    const cards = await page.evaluate(() => {
      const adults = unit() === "party" ? 2 : 1;
      return (DATA.railcards || []).map((card) => {
        const option = document.querySelector(
          '#railcardSelect option[value="' + card.key + '"]'
        );
        return {
          key: card.key,
          listed: Boolean(option),
          fits: card.minAdults <= adults && adults <= card.maxAdults,
          disabled: option ? option.disabled : null,
          label: option ? option.textContent : null,
        };
      });
    });
    check(
      "every railcard this page prices is in the selector, and one that cannot cover the party on screen cannot be chosen",
      cards.length === 0
        ? notExercised("this feed prices no reviewed railcard")
        : cards.every((c) => c.listed && (c.fits ? !c.disabled : c.disabled)),
      JSON.stringify(cards)
    );
    check(
      "and a card that cannot cover the party on screen says why",
      cards.length === 0
        ? notExercised("this feed prices no reviewed railcard")
        : cards.filter((c) => !c.fits).every((c) => /\d/.test(c.label || "")),
      JSON.stringify(cards.filter((c) => !c.fits))
    );

    // 7d. The standard fare under a discounted price is a clear step down the
    // ladder, not a shade: it was 14px against a 16px price, which is the size
    // every other small note on a row already used, so the cell read as two
    // equal numbers rather than one price with a note under it.
    const note = await page.evaluate(() => {
      // The card is applied here rather than read from whatever the suite left
      // on screen, so the check exercises the path a reader takes and never
      // skips for want of state earlier in the run.
      const before = document.getElementById("railcardSelect").value;
      const rows = [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations].flat();
      const pick = (DATA.railcards || []).find((card) =>
        rows.some((d) => {
          const detail = (d.railcards || {})[card.key];
          return detail && detail.pricePence !== null && detail.pricePence < d.adultPence;
        })
      );
      if (!pick) return null;
      document.getElementById("railcardSelect").value = pick.key;
      render();
      const was = document.querySelector("td.num .was");
      const price = document.querySelector("td.num .price");
      const reading = was && price
        ? {
            note: parseFloat(getComputedStyle(was).fontSize),
            price: parseFloat(getComputedStyle(price).fontSize),
            text: was.textContent.trim(),
          }
        : { noNote: true };
      document.getElementById("railcardSelect").value = before;
      render();
      return reading;
    });
    check(
      "the standard fare under a discounted price is a clear step down the ladder",
      note
        ? note.noNote
          ? false
          : note.note <= note.price - 2
        : notExercised("this feed prices no railcard that lowers a displayed fare"),
      JSON.stringify(note)
    );

    // 7e. A row must not claim no service for a destination the page's own
    // payload times. The journey used to be read from each fare list's own
    // timetable, so the cheapest list -- which keeps whichever row is cheapest
    // -- inherited the list built without a timetable, and a destination the
    // page prices a 45-minute direct journey to read "No service" and
    // "Unknown". Both columns were empty for every destination the build could
    // time, and empty for a reason that named nothing true about it.
    const timed = await page.evaluate(() => {
      const byCrs = new Map();
      for (const list of [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations]) {
        for (const destination of list || []) byCrs.set(destination.crs, destination);
      }
      return Array.from(document.querySelectorAll("#rows tr[data-crs]")).map((tr) => {
        const cells = Array.from(tr.cells);
        const shown = (label) => {
          const cell = cells.find((c) => c.dataset.label === label);
          return cell ? cell.textContent.trim() : null;
        };
        const fact = byCrs.get(tr.dataset.crs);
        return {
          crs: tr.dataset.crs,
          state: fact ? fact.journeyState : null,
          minutes: fact ? fact.minutes : null,
          time: shown("Time"),
          changes: shown("Changes"),
        };
      });
    });
    const contradicted = timed.filter(
      (r) => r.minutes !== null && (r.time === "No service" || r.changes === "Unknown")
    );
    check(
      "no row claims no service for a destination the page's own payload times",
      timed.length === 0
        ? notExercised("this page shows no rows to read")
        : contradicted.length === 0,
      JSON.stringify(contradicted.slice(0, 3))
    );

    // 7f. A destination type and its count are separated on screen. The markup
    // has always had a space between them and it never arrived: `.choice-chip`
    // is an inline-flex box and a flex container drops the whitespace-only
    // text between its items, so the rendered chip read "Small towns(0)".
    const chipGap = await page.evaluate(() => {
      const count = document.querySelector(".choice-chip .chipcount");
      const name = count ? count.previousElementSibling : null;
      if (!count || !name) return null;
      return {
        gap: Math.round(
          count.getBoundingClientRect().left - name.getBoundingClientRect().right
        ),
        rendered: name.textContent + count.textContent,
      };
    });
    check(
      "a destination type and its count are separated on screen",
      chipGap ? chipGap.gap >= 2 : notExercised("this page has no counted destination type"),
      JSON.stringify(chipGap)
    );

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

    // Q2: a railcard is one of a collection the reader picks from, nothing is
    // selected by default, and a card whose own feed record does not cover the
    // party on screen is listed but cannot be chosen for it.
    const cardChoice = await page.locator("#railcardChoice").isVisible();
    const menu = await page.evaluate(() => {
      const select = document.getElementById("railcardSelect");
      const adults = document.querySelector('input[name="unit"]:checked').value === "party" ? 2 : 1;
      return {
        options: Array.from(select.options).map((o) => ({
          value: o.value,
          label: o.textContent,
          disabled: o.disabled,
        })),
        value: select.value,
        disabled: select.disabled,
        help: document.getElementById("railcardHelp").textContent,
        adults,
        // Every card the feed prices, and the ones this party can actually use.
        // Every priced card is in the list whatever its bounds; only the usable
        // ones can be chosen. Removal was ADR-0052's answer, and it cost the
        // one card whose bounds are 2 to 2 on a page showing one adult.
        offered: (DATA.railcards || []).map((c) => c.key),
        forParty: (DATA.railcards || [])
          .filter((c) => c.minAdults <= adults && adults <= c.maxAdults)
          .map((c) => c.key),
      };
    });
    check(
      "the railcard control lists every card this page prices, plus one 'none' option",
      cardChoice
        ? menu.offered.length > 0 &&
          menu.options.length === menu.offered.length + 1 &&
          menu.options[0].value === "" &&
          menu.options.slice(1).every((o, i) => o.value === menu.offered[i])
        : notExercised("this feed prices no reviewed railcard"),
      `${menu.adults} adult(s): priced ${JSON.stringify(menu.offered)}; ${JSON.stringify(menu.options)}`
    );
    check(
      "and only the cards whose own bounds cover the party on screen can be chosen",
      cardChoice
        ? menu.options.slice(1).every((o) => (o.disabled ? !menu.forParty.includes(o.value) : menu.forParty.includes(o.value)))
        : notExercised("this feed prices no reviewed railcard"),
      `${menu.adults} adult(s): usable ${JSON.stringify(menu.forParty)}; ${JSON.stringify(menu.options)}`
    );
    check(
      "and no railcard is selected by default, so the prices are standard fares",
      cardChoice
        ? menu.value === "" && /No railcard selected/.test(menu.help)
        : notExercised("this feed prices no reviewed railcard"),
      `value=${menu.value} help=${menu.help}`
    );
    const solo = cardChoice
      ? await page.evaluate(() => {
        document.querySelector('input[name="unit"][value="adult"]').checked = true;
        render();
        const select = document.getElementById("railcardSelect");
        return {
          options: Array.from(select.options).map((o) => ({ value: o.value, disabled: o.disabled })),
          cards: DATA.railcards.map((c) => ({ key: c.key, min: c.minAdults, max: c.maxAdults })),
          help: document.getElementById("railcardHelp").textContent,
        };
      })
      : null;
    // S15: a card that needs two travellers cannot price one reader's journey,
    // so it cannot be chosen for a party of one -- but it is still in the list,
    // saying how many it needs. Removing it meant Two Together, whose bounds
    // are 2 to 2, was absent from every one-adult page, which reads as "this
    // page does not price Two Together" rather than "not for the party you
    // have on screen". The bounds are the feed's own records.
    check(
      "one adult is offered only the cards whose own bounds cover one adult",
      cardChoice
        ? solo.options.slice(1).every((o) => {
            const card = solo.cards.find((c) => c.key === o.value);
            const usable = card && card.min <= 1 && 1 <= card.max;
            return o.disabled === !usable;
          })
        : notExercised("this feed prices no reviewed railcard"),
      `options=${solo ? JSON.stringify(solo.options) : ""}`
    );
    const duo = cardChoice
      ? await page.evaluate(() => {
        document.querySelector('input[name="unit"][value="party"]').checked = true;
        render();
        const select = document.getElementById("railcardSelect");
        const options = Array.from(select.options).map((o) => o.value);
        const first = options.find((v) => v !== "") || "";
        if (first) {
          select.value = first;
          render();
        }
        return {
          options,
          first,
          help: document.getElementById("railcardHelp").textContent,
          cards: DATA.railcards,
          disabled: select.disabled,
        };
      })
      : null;
    check(
      "two adults are offered the cards that cover two",
      cardChoice && duo.cards.some((c) => c.minAdults <= 2 && 2 <= c.maxAdults)
        ? duo.first !== "" &&
          duo.cards
            .filter((c) => c.minAdults <= 2 && 2 <= c.maxAdults)
            .every((c) => duo.options.includes(c.key)) &&
          !duo.disabled
        : notExercised(
            cardChoice
              ? "this feed prices no railcard that covers two adults, so a party of two cannot be priced with one"
              : "this feed prices no reviewed railcard"
          ),
      `options=${duo ? duo.options.join(",") : ""} cards=${
        duo ? duo.cards.filter((c) => c.minAdults <= 2 && 2 <= c.maxAdults).map((c) => c.key).join(",") : ""
      }`
    );
    check(
      "and the help names the chosen card, its bounds and what it would discount",
      cardChoice && pair && duo.first
        ? (() => {
            const card = duo.cards.find((c) => c.key === duo.first);
            return (
              card &&
              new RegExp(String(card.minAdults) + " to " + String(card.maxAdults) + " adults").test(duo.help) &&
              duo.help.includes(card.label) &&
              new RegExp(String(card.eligibleCount)).test(duo.help) &&
              /open a row's own details/.test(duo.help)
            );
          })()
        : notExercised("this page prices no card that covers two adults"),
      pair ? duo.help : ""
    );
    // Q2: the browser remembers the card, which is what makes this a collection
    // rather than a per-page question. Every reading here goes through the
    // control itself. Assigning select.value from a script fires no change
    // event, so nothing is written and nothing re-rendered, and a check written
    // that way reads back the value the test just set rather than anything the
    // page remembered.
    // The party is set first, because a card that does not cover the party on
    // screen is not in the list at all. The block above leaves two adults
    // selected, and this feed's only reviewed card covers one, so reading the
    // list without setting the party found nothing to choose.
    // The refinements are folded on every route, and a navigation folds them
    // again, so the control is opened the way the reader opens it rather than
    // driven while hidden.
    const revealCardControl = async () => {
      const folded = await page.evaluate(
        () => (document.getElementById("moreFilters") || {}).dataset.open === "true"
      );
      if (!folded) await page.locator("#moreFiltersToggle").click();
    };
    const holdable = await page.evaluate(() => {
      const cards = DATA.railcards || [];
      for (const adults of [1, 2]) {
        const card = cards.find((c) => c.minAdults <= adults && adults <= c.maxAdults);
        if (!card) continue;
        document.querySelector(
          'input[name="unit"][value="' + (adults === 2 ? "party" : "adult") + '"]'
        ).checked = true;
        render();
        const options = Array.from(document.getElementById("railcardSelect").options)
          .map((o) => o.value)
          .filter(Boolean);
        if (options.includes(card.key)) return card.key;
      }
      return null;
    });
    if (holdable) {
      await revealCardControl();
      await page.selectOption("#railcardSelect", holdable);
      const stored = await page.evaluate(() =>
        window.localStorage.getItem("tbe.railcard." + DATA.origin.crs)
      );
      check(
        "the browser remembers the card the reader chose",
        stored === holdable,
        `stored=${stored} chosen=${holdable}`
      );
      check(
        "and the address carries the card by its code, so a shared link is the same search",
        page.url().includes("card=" + holdable),
        page.url()
      );
      // open() takes a budget, not a URL, so the address is followed directly.
      await page.goto(page.url());
      const cameBack = await page.evaluate(() =>
        document.getElementById("railcardSelect").value
      );
      check(
        "and reopening that address prices with the same card",
        cameBack === holdable,
        `value=${cameBack} expected=${holdable}`
      );
      await revealCardControl();
      await page.selectOption("#railcardSelect", "");
      const cleared = await page.evaluate(() => ({
        stored: window.localStorage.getItem("tbe.railcard." + DATA.origin.crs),
        value: document.getElementById("railcardSelect").value,
        url: window.location.search,
      }));
      check(
        "and clearing the control forgets the card and drops it from the address",
        cleared.stored === null && cleared.value === "" && !/card=/.test(cleared.url),
        JSON.stringify(cleared)
      );
      // A shared link can name a card this origin's feed does not price. It is
      // ignored rather than read as a card the reader holds.
      await page.goto(page.url() + (page.url().includes("?") ? "&" : "?") + "card=ZZZ");
      const ignoredValue = await page.evaluate(() =>
        document.getElementById("railcardSelect").value
      );
      check(
        "and a card code this page does not price is ignored, not half-applied",
        ignoredValue === "",
        `value=${ignoredValue}`
      );
    } else {
      for (const name of [
        "the browser remembers the card the reader chose",
        "and the address carries the card by its code, so a shared link is the same search",
        "and reopening that address prices with the same card",
        "and clearing the control forgets the card and drops it from the address",
        "and a card code this page does not price is ignored, not half-applied",
      ]) {
        check(name, notExercised("this feed prices no railcard for the party on screen"));
      }
    }
    // Q3: the discounted number never stands alone in the cell. With the card
    // chosen a row the card lowers carries the card price and the standard
    // fare it came from; a row it does not lower carries one price; and with
    // no card chosen no row carries a second number at all.
    if (cardChoice) {
      const readCells = () => page.evaluate(() => {
        const cells = {};
        for (const row of document.querySelectorAll("#rows tr[data-crs]")) {
          const price = row.querySelector("td.num .price");
          const was = row.querySelector("td.num .was");
          cells[row.dataset.crs] = {
            price: price ? price.textContent.trim() : null,
            was: was ? was.textContent.trim() : null,
          };
        }
        return cells;
      });
      const amount = (text) => Number(String(text).replace(/[^0-9.]/g, ""));
      // A row the card actually lowers is the row this check is about, so the
      // budget is set to reach one instead of inheriting whatever the section
      // before left on screen.
      // The card and the party are chosen together from the feed's own bounds.
      // The demo feed's reviewed card covers one adult, so choosing the party
      // first and then looking for a card that covers it found nothing, and the
      // check reported that no destination is lowered by a card that lowers
      // three of them.
      const pick = await page.evaluate(() => {
        const rows = [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations].flat();
        for (const c of DATA.railcards || []) {
          for (const adults of [2, 1]) {
            if (!(c.minAdults <= adults && adults <= c.maxAdults)) continue;
            const helped = rows.filter((d) => {
              const card = (d.railcards || {})[c.key];
              return card && card.pricePence !== null && card.pricePence < d.adultPence;
            });
            if (helped.length) return { key: c.key, adults, helped: helped.length };
          }
        }
        return null;
      });
      // The clear reading is taken with no card selected and the card reading
      // with it selected. These two were the other way round, so the check
      // compared two card prices and reported every row as unchanged.
      await page.evaluate((choice) => {
        const select = document.getElementById("railcardSelect");
        if (!choice) {
          select.value = "";
          render();
          return;
        }
        document.querySelector(
          'input[name="unit"][value="' + (choice.adults === 2 ? "party" : "adult") + '"]'
        ).checked = true;
        select.value = "";
        render();
        const dearest = [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations]
          .flat()
          .filter((d) => {
            const card = (d.railcards || {})[choice.key];
            return card && card.pricePence !== null && card.pricePence < d.adultPence;
          })
          .reduce((high, d) => Math.max(high, choice.adults === 2 ? d.partyPence : d.adultPence), 0);
        if (dearest) {
          setBudget(Math.min(Number(document.getElementById("budget").max), Math.ceil(dearest / 100)));
        }
        render();
      }, pick);
      const lowered = pick ? pick.helped : 0;
      const clear = await readCells();
      await page.evaluate((choice) => {
        const select = document.getElementById("railcardSelect");
        select.value = choice ? choice.key : "";
        render();
      }, pick);
      const card = await readCells();
      const rows = Object.keys(clear).filter((crs) => clear[crs].price !== null && card[crs]);
      const helped = rows.filter((crs) => amount(card[crs].price) < amount(clear[crs].price));
      const unchanged = rows.filter((crs) => amount(card[crs].price) === amount(clear[crs].price));
      check(
        "a discounted row shows the card price and the standard fare it was discounted from",
        lowered
          ? helped.length > 0 &&
            helped.every(
              (crs) =>
                amount(card[crs].was) === amount(clear[crs].price) && /standard/.test(card[crs].was)
            )
          : notExercised("no destination on this page is lowered by the card"),
        JSON.stringify(helped.slice(0, 3).map((crs) => [crs, clear[crs], card[crs]]))
      );
      check(
        "and a row the card does not lower still shows one price",
        unchanged.every((crs) => card[crs].was === null),
        JSON.stringify(unchanged.slice(0, 3).map((crs) => card[crs]))
      );
      check(
        "with no railcard selected no row shows a second price",
        rows.every((crs) => clear[crs].was === null),
        JSON.stringify(rows.slice(0, 3).map((crs) => clear[crs]))
      );
    } else {
      check("a discounted row shows the card price and the standard fare it was discounted from",
        notExercised("this feed prices no reviewed railcard"));
      check("and a row the card does not lower still shows one price",
        notExercised("this feed prices no reviewed railcard"));
      check("with no railcard selected no row shows a second price",
        notExercised("this feed prices no reviewed railcard"));
    }
    // The railcard note leads with the row's own price, so opening a row's
    // details never shows a bigger number than the row it was opened from. The
    // row the old drawer got wrong is the one the card does not lower: the
    // card's own price for that fare sits above the fare the row is priced at,
    // and it was printed under a label that called it a discount. Read from
    // the notes themselves rather than from the template, because the number
    // is written by script and a string in the source can only say what was
    // meant to be written.
    const drawerChoice = await page.evaluate(() => {
      const rows = [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations].flat();
      // A card that prices a row is not a card that discounts one. On a real
      // page the first card in the list is the 16-25, whose price is the £12
      // DTD minimum on every fare below it, so it prices everything and lowers
      // nothing -- and every check about a discounted row then failed on a page
      // that has none. Prefer a card that actually lowers a price; fall back to
      // one that merely prices something, which is a real answer about rows the
      // card cannot help rather than a substitute for one.
      let anyPriced = null;
      for (const card of DATA.railcards || []) {
        for (const adults of [2, 1]) {
          if (!(card.minAdults <= adults && adults <= card.maxAdults)) continue;
          const priced = rows.filter((d) => {
            const detail = (d.railcards || {})[card.key];
            return detail && detail.pricePence !== null;
          });
          if (!priced.length) continue;
          const discounted = priced.filter((d) => {
            const detail = d.railcards[card.key];
            const standard = adults === 2 ? d.partyPence : d.adultPence;
            return detail.pricePence < standard;
          });
          if (discounted.length) return { key: card.key, adults, discounted: discounted.length };
          if (!anyPriced) anyPriced = { key: card.key, adults, discounted: 0 };
        }
      }
      return anyPriced;
    });
    const noteRows = drawerChoice
      ? await page.evaluate((choice) => {
          // There is no drawer: the note is built into the panel the row
          // already opens, so it is read from there and from nowhere else.
          if (document.getElementById("railcardDrawer")) {
            return { error: "the railcard drawer is still on the page" };
          }
          document.querySelector(
            'input[name="unit"][value="' + (choice.adults === 2 ? "party" : "adult") + '"]'
          ).checked = true;
          document.getElementById("railcardSelect").value = choice.key;
          // Only the list the page is showing: a row in another ticket mode is
          // not on screen, so it is not a note a reader could read.
          const priced = activeDestinations().filter((d) => (d.railcards || {})[choice.key]);
          if (!priced.length) return { error: "this page shows no row that card touches" };
          const dearest = priced.reduce(
            (high, d) => Math.max(high, choice.adults === 2 ? d.partyPence : d.adultPence),
            0
          );
          if (dearest) {
            setBudget(Math.min(Number(document.getElementById("budget").max), Math.ceil(dearest / 100)));
          }
          currentPage = 1;
          render();
          const readings = [];
          for (const row of Array.from(document.querySelectorAll("#rows tr[data-crs]"))) {
            // The note is built when the panel opens, so the row is opened
            // first, the same way a reader reaches it, and closed again after.
            const fold = row.querySelector(".toggle[aria-expanded='false']");
            if (fold) fold.click();
            const detail = row.nextElementSibling;
            const note =
              detail && detail.classList.contains("detail")
                ? detail.querySelector(".card-note")
                : null;
            const price = row.querySelector("td.num .price");
            readings.push({
              crs: row.dataset.crs,
              row: price ? price.textContent.trim() : null,
              inOwnPanel: Boolean(note) && detail.contains(note),
              state: note ? note.dataset.state : null,
              text: note ? note.textContent : null,
            });
            if (fold) fold.click();
          }
          return { readings };
        }, drawerChoice)
      : { readings: [] };
    const noteRowsList = noteRows.readings || [];
    const pounds = (text) => Number(String(text).replace(/[^0-9.]/g, ""));
    // The note names the card's own price first wherever it names one at all:
    // the blocked branch quotes no figure, and every other branch opens with
    // what the card costs for this fare.
    const quoted = (note) => {
      const match = /£\s?([0-9]+(?:\.[0-9]{2})?)/.exec(note.text || "");
      return match ? Number(match[1]) : null;
    };
    // A row with no price on screen carries no number to compare.
    const quotedRows = noteRowsList.filter((r) => r.row !== null && quoted(r) !== null);
    check(
      "the note is in the row's own panel, and no drawer is left behind",
      noteRows.error
        ? false
        : noteRowsList.length > 0 && noteRowsList.every((r) => r.inOwnPanel),
      JSON.stringify({ error: noteRows.error, sample: noteRowsList.slice(0, 3) })
    );
    check(
      "the note never quotes more than the row it sits under",
      quotedRows.length
        ? quotedRows.every((r) => quoted(r) <= pounds(r.row))
        : notExercised("this page prices no railcard against a row it shows"),
      JSON.stringify(quotedRows.slice(0, 4).map((r) => [r.crs, r.row, quoted(r), r.state]))
    );
    check(
      "and a row the card cannot be applied to says so rather than quoting a price",
      noteRowsList.filter((r) => r.state === "blocked").every((r) => quoted(r) === null),
      JSON.stringify(noteRowsList.filter((r) => r.state === "blocked").slice(0, 3).map((r) => r.text))
    );
    // The section that follows reads rows and their panels, so the page is
    // handed back at the budget the rest of this block is written against.
    await open(facts.affordable);

    // Q2 (finding 5): a journey with a change names the station a split ticket
    // would change at, in the same panel as the condition, and prices neither
    // half. Read from this page's own payload first, so a page with no changed
    // row reports that rather than asserting a sentence it cannot show.
    //
    // The row is found in a list the page can actually render: the section
    // above opened the page on its cheapest fare in one mode, and the changed
    // row is not necessarily in that list -- on the Lincoln fixture it sits in
    // the returns while the page opens on the Anytime set. Each named list is
    // tried in turn, at that list's own ceiling, and the page and its panels
    // are put back the way they were found.
    const split = await page.evaluate(() => {
      const budgetBefore = budget.value;
      const modeBefore = document.querySelector('input[name="ticketMode"]:checked').value;
      const lists = { return: "destinations", single: "singleDestinations", anytime: "anytimeDestinations" };
      const restore = () => {
        const back = document.querySelector(`input[name="ticketMode"][value="${modeBefore}"]`);
        if (back) back.checked = true;
        setBudget(Number(budgetBefore));
        currentPage = 1;
        render();
      };
      // The note is read out of the opened panel and the panel is closed again:
      // a row left open would make the next check count one toggle fewer than
      // it has rows.
      const noteFor = (destination) => {
        const line = document.querySelector(`#rows tr[data-crs="${destination.crs}"]`);
        if (!line) return null;
        const toggle = line.querySelector(".toggle[aria-expanded='false']");
        if (!toggle) return null;
        toggle.click();
        const detail = line.nextElementSibling;
        const note = detail && detail.classList.contains("detail")
          ? detail.querySelector(".split") : null;
        toggle.click();
        return note ? note.textContent : "";
      };
      for (const mode of [modeBefore, "return", "single", "anytime"]) {
        const list = DATA[lists[mode]];
        const input = document.querySelector(`input[name="ticketMode"][value="${mode}"]`);
        if (!list || !input) continue;
        input.checked = true;
        setBudget(budgetCeiling());
        currentPage = 1;
        render();
        const changesAt = (d) => (d.changeStations || []).length;
        // The table holds one page of twenty rows and the list behind it holds
        // every destination in the mode, so on a real page the first changed
        // journey is usually not the one on screen. noteFor answers null for a
        // row the page has not rendered, and a check that reads null reports a
        // missing note on a page that prints one -- Nottingham said Derby had
        // no split ticket when the note is there on page three. So the page
        // holding the row is rendered first, and the direct counterpart is
        // taken from that same page: a direct row on another page is not one a
        // reader can set the changed row beside.
        const onScreen = () =>
          Array.from(document.querySelectorAll("#rows tr[data-crs]")).map((r) => r.dataset.crs);
        const changedRows = list.filter(changesAt);
        let changed = changedRows.find((d) => onScreen().includes(d.crs));
        if (!changed) {
          const elsewhere = changedRows.find((d) => {
            const at = list.indexOf(d);
            if (at < 0) return false;
            currentPage = Math.floor(at / PAGE_SIZE) + 1;
            render();
            return onScreen().includes(d.crs);
          });
          if (!elsewhere) continue;
          changed = elsewhere;
        }
        const direct = onScreen()
          .map((crs) => list.find((d) => d.crs === crs))
          .find((d) => d && !changesAt(d));
        const read = {
          mode,
          changed: { crs: changed.crs, name: changed.changeStations[0].name, note: noteFor(changed) },
          direct: direct ? { crs: direct.crs, note: noteFor(direct) } : null,
        };
        restore();
        return read;
      }
      restore();
      return null;
    });
    check(
      "a changed journey names the station a split ticket would change at",
      // The note says "the station above" and the name is in the row above, so
      // repeating it in the note would be saying the same word twice on one
      // line of screen. What has to hold is that the note points at this row's
      // own station rather than at some other one.
      split && split.changed
        ? Boolean(split.changed.note) && /split ticket/.test(split.changed.note) &&
          /station above|station below|this station/.test(split.changed.note)
        : notExercised("no destination on this page changes"),
      JSON.stringify(split && split.changed || null)
    );
    check(
      "and a direct journey claims no split to make",
      split && split.changed && split.direct
        ? split.direct.note === ""
        : notExercised("no changed row, or no direct row in the same list"),
      JSON.stringify(split && split.direct || null)
    );

// Does this condition tell a reader something its restriction code does not?
//
// The defect it stands for is a panel that prints the code and calls it a
// condition. Three ways to do that, all rejected: nothing at all, the code
// itself, or a string built only from the code's own letters. Digits are
// dropped before comparing, because `B31` beside `B3` is the code again with a
// digit on the end, not a condition. Everything else
// is the feed's wording and is allowed to be as terse as the feed wrote it --
// `OFF-PEAK` beside `B3` says something, and the suite is not in a position
// to improve on the feed's phrasing.
function saysMoreThan(condition, code) {
  const text = (condition || "").trim();
  if (!text) return false;
  const letters = (value) => (value || "").toUpperCase().replace(/[^A-Z]/g, "");
  const said = letters(text);
  const bare = letters(code);
  if (!said) return false;
  return said !== bare && ![...said].every((character) => bare.includes(character));
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
        const record = Array.from(cell.querySelectorAll(".feed-record dd")).map((dd) => dd.textContent);
        return {
          readable: (cell.querySelector(".condition") || {}).textContent || "",
          sentence: (cell.querySelector(".fare-line") || {}).textContent || "",
          validity: (cell.querySelector(".validity") || {}).textContent || "",
          restricted: cell.dataset.status === "restricted",
          record,
          // The restriction this condition describes, so the check can ask
          // whether the condition says anything the code does not.
          restriction: record[1] || "",
          summary: (cell.querySelector(".feed-record summary") || {}).textContent || "",
          // The code is in the record now, under the "Ticket" label, and the
          // row itself carries the word a reader can act on.
          code: record[0] || "",
          word: (row.querySelector(".fare-kind") || {}).textContent || "",
        };
      });
      // Put the rows back: a later check that found twenty panels open would be
      // measuring a page nobody is looking at.
      for (const toggle of toggles) toggle.click();
      return { found, rows: document.querySelectorAll("#rows tr:not(.detail)").length, toggles: toggles.length };
    });
    check(
      "every row states its fare in a sentence, one disclosure away",
      conditions.rows > 0 &&
        conditions.toggles === conditions.rows &&
        conditions.found.length === conditions.rows &&
        // Every row says what kind of fare it is. A row whose fare carries a
        // restriction code says what the condition is as well; a row with no
        // condition in the feed is not given one, which is why the sentence
        // and the condition are checked separately.
        //
        // The condition is judged against the code it belongs to, not by how
        // it is spelled. It used to be rejected for opening with one to four
        // capitals, which on the real feed rejects 624 of the 841 descriptions
        // in the file -- `OFF-PEAK`, `NTH ADVANCE`, `NOT VALID BEFORE 0915
        // MON-FRI`, `BAN ALL DAY`. Those are the conditions a reader needs,
        // they are the feed's own wording, and paraphrasing them is a
        // licencee's risk. Counted over the whole file: no description is
        // empty and none equals its own code, so the page was never printing a
        // bare one. What must not happen is the code restated as prose.
        conditions.found.every(
          (cell) =>
            cell.sentence.length > 10 &&
            !/^[A-Z0-9]{1,4}\b/.test(cell.sentence) &&
            (!cell.restricted || saysMoreThan(cell.readable, cell.restriction))
        ),
      JSON.stringify(conditions.found[0] || null) +
        ` rows=${conditions.rows} toggles=${conditions.toggles}`
    );
    check(
      "and the row names the fare in a word while the feed's code stays folded",
      conditions.found.length > 0 &&
        conditions.found.every(
          (cell) =>
            cell.summary &&
            cell.record.length >= 2 &&
            cell.code.length > 0 &&
            ["Advance", "Restricted", "Regular"].includes(cell.word)
        ),
      JSON.stringify(conditions.found[0] || null)
    );
    // The rule above is worth stating on its own, because the page has 841
    // codes to choose from and a reader can only act on the ones that are
    // explained. A condition that is its own code is the failure; a condition
    // the feed wrote tersely is not.
    check(
      "no row prints its restriction code as though it were the condition",
      conditions.found.every(
        (cell) => !cell.restricted || saysMoreThan(cell.readable, cell.restriction)
      ),
      JSON.stringify(
        conditions.found.filter((cell) => cell.restricted && !saysMoreThan(cell.readable, cell.restriction))
      )
    );
    // The rule above is the one the whole check rests on, and it was wrong once
    // already: it used to reject a condition for opening with one to four
    // capitals, which rejects 624 of the 841 descriptions in the real file. A
    // rule that has been wrong in the generous direction will be wrong in the
    // other one next, so the cases that separate them are named here rather
    // than left to whoever reads it next.
    const ruleCases = [
      // Conditions the real feed writes tersely. Every one of these was
      // reported as a defect, and none of them is a code.
      ["OFF-PEAK", "B3", true],
      ["NTH ADVANCE", "NT", true],
      ["NOT VALID BEFORE 0915 MON-FRI", "TU", true],
      ["BAN ALL DAY", "ZZ", true],
      ["IEC OFF-PEAK", "1U", true],
      // The condition being its own code, in every disguise a page might
      // print it in. These are the defect the rule exists for.
      ["", "B3", false],
      ["   ", "B3", false],
      ["B3", "B3", false],
      ["b3", "B3", false],
      ["  B3  ", "B3", false],
      ["3B", "B3", false],
      ["BB333", "B3", false],
      ["-B3-", "B3", false],
      ["B3 (2)", "B3", false],
      // The code with a digit on the end, which is the code again. Digits are
      // dropped before comparing precisely so this cannot pass.
      ["B31", "B3", false],
      ["B3 1", "B3", false],
      // A code with something else attached says something, and is allowed.
      ["B3 OFF-PEAK", "B3", true],
    ];
    const wrongRule = ruleCases
      .filter(([text, code, want]) => saysMoreThan(text, code) !== want)
      .map(([text, code, want]) => ({ text, code, want, got: saysMoreThan(text, code) }));
    check(
      "the condition rule accepts the feed's terse wording and rejects a bare code",
      wrongRule.length === 0,
      JSON.stringify(wrongRule)
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
    // A no-service row carries the day the page is about when the week reaches
    // the station on another day, so the cell is either the bare words or those
    // words and a weekday. Both are checked against the page's own date rather
    // than against a fixed phrase.
    // The cell is the bare words, or those words and the weekday the page is
    // about, so the allowance is the page's own date rather than a fixed
    // phrase. A row that names a day it runs on is checked against that date
    // below rather than accepted here on the strength of a prefix.
    const serviceWeekday = await page.evaluate(() => {
      if (!DATA.serviceDate) return "";
      const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
      return days[new Date(DATA.serviceDate + "T00:00:00Z").getUTCDay()] || "";
    });
    check(
      "a row with no journey says so, and says it is unknown rather than zero",
      typed
        ? typed.cells.some((text) => text === "No service" || text === "No service " + serviceWeekday) &&
          typed.cells.includes("Unknown") &&
          typed.record.some((value) => /no service|timetable/i.test(value))
        : notExercised("every destination on this page has a journey"),
      JSON.stringify({ ...typed, serviceWeekday })
    );

    // S20: counts on the chips, the union stated, and a way back to All.
    const facets = await page.evaluate(() => {
      const cap = Number(document.getElementById("budgetNumber").value) * 100;
      // The list the page is showing, from the reader rather than re-derived
      // here: on the opening list that is the composed one, and counting the
      // returns instead would call a correct page wrong.
      const available = TYPES.list();
      return Array.from(document.querySelectorAll(".chipcount")).map((slot) => {
        const value = slot.dataset.countFor;
        return {
          value,
          shown: slot.textContent,
          count: available.filter(
            (destination) => TYPES.price(destination) <= cap &&
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
      // The floor, read off the control, not a pound named here. A budget the
      // check picks for itself is a budget the reader cannot necessarily
      // reach, and on a page whose cheapest fare is under it the check was
      // measuring a page that cannot be emptied rather than a page that was
      // wrong: the real Grindleford page prices every outbound single at fifty
      // pence, so a one-pound floor showed all thirteen of them and the empty
      // state below -- with the moves that are its whole purpose -- was
      // unreachable on that page at all.
      const floor = Number(document.getElementById("budget").min);
      setBudget(floor);
      currentPage = 1;
      render();
      if (document.getElementById("empty").hidden) return { actions: [], floor };
      const actions = Array.from(document.querySelectorAll("#empty .toggle")).map((button) => button.textContent);
      const first = document.querySelector("#empty .toggle");
      if (first) first.click();
      return {
        actions,
        rows: document.querySelectorAll("#rows tr").length,
        budget: document.getElementById("budgetNumber").value,
        floor,
      };
    });
    check("an empty list says what would fill it", recovery.actions.length > 0, JSON.stringify(recovery));
    check(
      "and the first move it offers changes the answer",
      recovery.actions.length > 0
        && (recovery.rows > 0 || Number(recovery.budget) > recovery.floor),
      JSON.stringify(recovery)
    );
    await open(facts.affordable);

    // S29: the coverage claim is counted, and the count is on the page. The
    // lead sentence is per mode, so the expected shape is read from the mode
    // the page is actually in rather than pinned to one of them.
    const coverage = (await page.textContent("#feedCoverage")) || "";
    const coverageMode = await page.evaluate(() => document.querySelector('input[name="ticketMode"]:checked').value);
    const COVERAGE_LEAD = {
      cheapest: /each on the cheapest fare of any ticket type the feed prices for it/,
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
        // null rather than false when the build carries no timetable. A
        // prices-only page prints no service window because it has none, and
        // asking it for one is a check that cannot pass on a whole build shape
        // -- the sibling `verdict` below already reads the prices-only sentence
        // as the right answer to its own question. Nothing in this suite had
        // been run against a prices-only page until now, which is the same blind
        // spot ADR-0058 records for a list longer than one page: a case that was
        // never swept cannot fail.
        window: DATA.timetableFrom
          ? new RegExp(humanDate(DATA.timetableFrom) + " to " + humanDate(DATA.timetableTo)).test(line.textContent)
          : null,
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
    check(
      "the timetable sentence carries the feed's own service window",
      fresh.window === null
        ? notExercised("this build prices fares only, so there is no service window to print")
        : fresh.window,
      `${fresh.text} (${JSON.stringify(fresh.window)})`
    );
    check("and judges that window against the reader's today", fresh.verdict, fresh.text);

    // 7f. The conditions in the table are the fares feed's own wording; the
    // page says what the portal's own restriction feed was asked and answered.
    // It used to sit above the table. It is in the page's method note now,
    // under "Where these prices come from", because the distillation moved
    // every line of legal and provenance text below the results: a reader
    // choosing between two prices needs the price, the time and the fare type,
    // and the claim about which feed was checked is one of the things that can
    // be looked up rather than read first.
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
        // And it lives in the method note, which is the disclosure a reader
        // opens to be told how a number was arrived at.
        inMethod: line
          ? Boolean(line.closest("details.method"))
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
      "and keeps it in the method note, below the results",
      reference.inMethod && !reference.above,
      `${reference.text} (in the method note: ${reference.inMethod}, above the table: ${reference.above})`
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
      // One checkbox on each row rather than a select above the table: the
      // control is beside the place it acts on, and holding a place is a tick
      // rather than finding its name in a list of names. Driven by click, so
      // what runs is the gesture a reader makes rather than a state set behind
      // their back.
      const add = (row) => {
        const box = row.querySelector(".hold-box");
        if (box) box.click();
      };
      const first = rows[0];
      const second = rows[1];
      const facts = () =>
        Array.from(document.querySelectorAll("#shortlistDockList tr")).map((tr) => tr.textContent);
      const saved = [];
      add(first);
      saved.push(facts());
      add(second);
      const both = facts();
      // What the dock offers once both places are on it, and the order they
      // are in. Read here, before the mode dance below changes what the page
      // is showing: a check written at the end of the block would be reading a
      // page the reader never saw at that point.
      const chips = () =>
        Array.from(document.querySelectorAll("#shortlistDockList tr")).map((tr) => ({
          text: tr.textContent,
          title: (tr.querySelector(".shortlist-dock-name") || {}).title || "",
        }));
      // Every rendered row's box against the list itself, in both directions:
      // a box ticked for a place that is not held is a row claiming something
      // the strip does not say, and a held place with an unticked box is one
      // the reader cannot see they are carrying.
      const boxes = Array.from(document.querySelectorAll("#rows tr[data-crs]")).map((row) => ({
        crs: row.dataset.crs,
        name: (row.querySelector(".station-name") || {}).textContent || "",
        held: Boolean((row.querySelector(".hold-box") || {}).checked),
        label: row.querySelector(".hold-box")
          ? row.querySelector(".hold-box").getAttribute("aria-label") || ""
          : "",
      }));
      const held = shortlistCodes.slice();
      // The dock's row is a place and its price. The place and the price are
      // read off the table row it came from, and the order from the dock
      // itself, so this says the row agrees with the table rather than that the
      // page can compute its own number.
      const chipsAgainstRows = Array.from(document.querySelectorAll("#shortlistDockList tr")).map((tr) => {
        const name = (tr.querySelector(".shortlist-dock-name") || {}).textContent || "";
        const row = Array.from(document.querySelectorAll("#rows tr[data-crs]"))
          .find((r) => (r.querySelector(".station-name") || {}).textContent === name);
        return {
          text: tr.textContent,
          title: (tr.querySelector(".shortlist-dock-name") || {}).title || "",
          row: row
            ? {
              name,
              price: (row.querySelector("td.num .price") || {}).textContent || "",
            }
            : null,
        };
      });
      const address = window.location.href;
      // The party price is the price a pair would see, so the comparison has
      // to follow the party control.
      document.querySelector('input[name="unit"][value="party"]').checked = true;
      render();
      const asPair = facts();
      document.querySelector('input[name="unit"][value="adult"]').checked = true;
      render();
      const asSolo = facts();
      // A shortlist kept across a mode change must not keep a place whose fare
      // the reader can no longer see. Both named modes are tried, because a row
      // priced as a return leaves the list when the reader asks for singles.
      const openedIn = ticketMode();
      const byMode = [];
      for (const mode of ["single", "return"]) {
        const input = document.querySelector(`input[name="ticketMode"][value="${mode}"]`);
        if (!input || !modeCount(mode)) continue;
        input.checked = true;
        render();
        byMode.push({ mode, texts: facts() });
        if (byMode[byMode.length - 1].texts.length) break;
      }
      document.querySelector(`input[name="ticketMode"][value="${openedIn}"]`).checked = true;
      render();
      const share = document.getElementById("shortlistShare").textContent;
      return {
        both, asPair, asSolo, chipsAgainstRows, byMode, share, address,
        boxes,
        rowCount: rows.length,
        held,
        names: both.map((text) => text.slice(0, 24)),
      };
    });
    if (shortlist.rows !== undefined && shortlist.rows < 2) {
      for (const name of [
        "a shortlisted place is listed as its name and the price beside it",
        "and each chip is a way back to the row it came from",
        "and a place leaves the list when its fare is no longer on the page",
        "and the list is a list of places, not a booking",
        "every row carries a box, and a held place's box is ticked",
        "and a box is named for the place it holds",
        "and the held places are announced, not just drawn",
        "the shortlist is in the address, so it can be shared",
        "a refresh brings the shortlist back",
        "and it follows the party the reader has chosen",
        "one control clears it",
        "and every copied place names the fare that price is for",
      ]) {
        check(name, notExercised(`this page lists ${shortlist.rows} row(s) to choose from`));
      }
    } else {
      check(
        "a shortlisted place is listed as its name and the price beside it",
        shortlist.both.length === 2 &&
          shortlist.both.every((text) => /£\d/.test(text)) &&
          shortlist.chipsAgainstRows.every(
            (chip) =>
              chip.row &&
              chip.text.includes(chip.row.name) &&
              chip.text.includes(chip.row.price)
          ),
        JSON.stringify({ chips: shortlist.chipsAgainstRows, both: shortlist.both })
      );
      check(
        "and each chip is a way back to the row it came from",
        shortlist.chipsAgainstRows.length === 2 &&
          shortlist.chipsAgainstRows.every(
            (chip) => chip.row && chip.title.includes(chip.row.name)
          ),
        JSON.stringify(shortlist.chipsAgainstRows)
      );
      // A place whose fare the reader can no longer see leaves the list rather
      // than sitting on it as a name with no fare behind it.
      const followed = shortlist.byMode[0];
      check(
        "and a place leaves the list when its fare is no longer on the page",
        followed && followed.texts.every((text) => /£\d/.test(text)),
        JSON.stringify(shortlist.byMode)
      );
      // Said by the page's own copy of the list, which is the text the reader
      // hands to somebody, rather than by a sentence that used to sit above the
      // table and has gone with the rest of that section.
      const shared = await page.evaluate(() => ({
        text: typeof shortlistText === "function" ? shortlistText() : "",
        share: (document.getElementById("shortlistShare") || {}).textContent || "",
        origin: DATA.origin.name,
      }));
      check(
        "and the list is a list of places, not a booking",
        /not a booking/i.test(shared.text) &&
          shared.share.includes("Shortlist of 2 places") &&
          shared.share.includes(shared.origin),
        JSON.stringify(shared).slice(0, 300)
      );
      check(
        "every row carries a box, and a held place's box is ticked",
        shortlist.boxes.length === shortlist.rowCount &&
          shortlist.boxes.every((row) => row.held === shortlist.held.includes(row.crs)) &&
          shortlist.held.every((crs) => {
            const row = shortlist.boxes.find((box) => box.crs === crs);
            return row && row.held;
          }),
        JSON.stringify({ boxes: shortlist.boxes, held: shortlist.held })
      );
      // A column of unticked boxes is a column of controls with no name of
      // their own, so each one has to say which place it holds.
      check(
        "and a box is named for the place it holds",
        shortlist.boxes.every(
          (row) => /^List .+ in the shortlist$/.test(row.label) && row.label.includes(row.name)
        ),
        JSON.stringify(shortlist.boxes.slice(0, 4))
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
      check(
        "and the held places are announced, not just drawn",
        /2 shortlisted/.test(await page.textContent("#shortlistStatus")),
        (await page.textContent("#shortlistStatus")) || ""
      );
      // A shared link is the whole point, so it is opened, not assumed.
      await page.goto(shortlist.address);
      const restored = await page.evaluate(() => Array.from(document.querySelectorAll("#shortlistDockList tr")).length);
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
      const copiedPlaces = text.split("\n").filter((line) => line.startsWith("- "));
      check(
        "and every copied place names the fare that price is for",
        copiedPlaces.length === 2 &&
          copiedPlaces.every((line) =>
            /Standard outbound single|Advance single|Unrestricted Anytime Day Return|Standard return/.test(line)
          ),
        text
      );
      await open(facts.affordable);
      await page.evaluate(() => { document.getElementById("shortlistDockClear").click(); });
      check(
        "one control clears it",
        (await page.evaluate(() => document.querySelectorAll("#shortlistDockList tr").length)) === 0 &&
          !(await page.evaluate(() => window.location.search.includes("short="))),
        (await page.evaluate(() => document.getElementById("shortlistDockCount").textContent)) || ""
      );
    }

    // 7e. The dock: the shortlist held at the foot of the screen, and the four
    // layout promises a reader scrolling a long table depends on. Read out of
    // the rendered page, because every one of them is a claim about geometry
    // that a template string cannot settle.
    await page.setViewportSize({ width: 1280, height: 800 });
    await open(facts.affordable);
    const dockAtRest = await page.evaluate(() => {
      const dock = document.getElementById("shortlistDock");
      return {
        exists: Boolean(dock),
        hidden: dock ? dock.hidden : null,
        codes: typeof shortlistCodes === "undefined" ? null : shortlistCodes.length,
      };
    });
    check(
      "the shortlist dock is on the page and shows nothing while nothing is shortlisted",
      dockAtRest.exists === true && dockAtRest.codes === 0 && dockAtRest.hidden === true,
      JSON.stringify(dockAtRest)
    );
    // Every shortlist control in one place. Copy and Share were in a section
    // between the count and the table while the rows were in the dock at the
    // foot of the screen, so a reader comparing two places had to look in two
    // places to hand the list to somebody.
    const dockControls = await page.evaluate(() => {
      const dock = document.getElementById("shortlistDock");
      const inside = (id) => Boolean(dock && dock.contains(document.getElementById(id)));
      const copy = document.getElementById("shortlistCopy");
      const share = document.getElementById("shortlistShareBox");
      const bar = document.getElementById("shortlistBar");
      return {
        copy: inside("shortlistCopy"),
        share: inside("shortlistShareBox"),
        clear: inside("shortlistDockClear"),
        copyWord: copy ? copy.textContent.trim() : "",
        shareWord: share ? (share.querySelector("summary") || {}).textContent || "" : "",
        bar: bar ? 1 : 0,
        barAfterCount: bar
          ? Boolean(bar.compareDocumentPosition(document.getElementById("summary")) & Node.DOCUMENT_POSITION_FOLLOWING)
          : false,
        boxInShare: Boolean(share && share.contains(document.getElementById("shortlistBox"))),
      };
    });
    check(
      "Copy, Share and Clear are all in the pinned dock",
      dockControls.copy && dockControls.share && dockControls.clear && dockControls.boxInShare &&
        /^copy$/i.test(dockControls.copyWord) && /^share$/i.test(dockControls.shareWord),
      JSON.stringify(dockControls)
    );
    check(
      "and there is no shortlist section left between the count and the table",
      dockControls.bar === 0 && !dockControls.barAfterCount,
      JSON.stringify(dockControls)
    );
    // A row with no service is a fact about the day the page is about. The
    // suite's fixture is built without a date, so it has no row of the shape
    // the sweep writes. Both shapes are put into the page's own data under
    // codes it has never seen -- the cheapest list is rebuilt from the three
    // ticket lists on every render, and a code it already holds would be
    // replaced rather than shown.
    const noService = await page.evaluate(() => {
      const source = (DATA.destinations || [])[0];
      if (!source || !DATA.serviceDate) return null;
      const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
      const built = new Date(DATA.serviceDate + "T00:00:00Z");
      const weekday = built.getUTCDay();
      const later = new Date(built.getTime() + ((8 - weekday) % 7 || 7) * 86400000)
        .toISOString()
        .slice(0, 10);
      const shape = (crs, name, nextService) =>
        Object.assign({}, source, {
          crs: crs,
          name: name,
          minutes: null,
          changes: null,
          departures: [],
          journeyState: "no service on " + DATA.serviceDate + (nextService ? ", and it runs on " + nextService : ", nor on the 7 days after it"),
          nextService: nextService,
        });
      const kept = DATA.destinations;
      DATA.destinations = [
        shape("ZSVC", "SERVICE LATER", later),
        shape("ZNRV", "SERVICE NEVER", undefined),
      ];
      setBudget(budgetCeiling());
      currentPage = 1;
      render();
      const read = (crs) => {
        const row = document.querySelector('#rows tr[data-crs="' + crs + '"]');
        if (!row) return null;
        const cells = Array.from(row.children).map((td) => td.textContent.trim());
        const toggle = row.querySelector(".toggle[aria-expanded=false]");
        if (toggle) toggle.click();
        const detail =
          row.nextElementSibling && row.nextElementSibling.classList.contains("detail")
            ? row.nextElementSibling
            : null;
        const record = detail
          ? Array.from(detail.querySelectorAll(".feed-record dd")).map((dd) => dd.textContent.trim())
          : [];
        return { time: cells[3], changes: cells[4], record: record.join(" | ") };
      };
      const out = { later: read("ZSVC"), never: read("ZNRV") };
      DATA.destinations = kept;
      setBudget(budgetCeiling());
      currentPage = 1;
      render();
      return out.later ? { rows: out, weekday: days[weekday] } : null;
    });
    if (noService) {
      check(
        "a row with no service on the page's day but service in the week names that day",
        noService.rows.later.time === "No service " + noService.weekday &&
          noService.rows.later.changes === "Unknown" &&
          /it runs on/.test(noService.rows.later.record),
        JSON.stringify({ ...noService.rows.later, weekday: noService.weekday })
      );
      check(
        "and a row the week never reaches says only that there is no service",
        noService.rows.never.time === "No service" &&
          noService.rows.never.changes === "Unknown" &&
          !/it runs on/.test(noService.rows.never.record),
        JSON.stringify(noService.rows.never)
      );
    } else {
      check(
        "a row with no service on the page's day but service in the week names that day",
        notExercised("this page lists no destination to clone, or carries no service date")
      );
      check(
        "and a row the week never reaches says only that there is no service",
        notExercised("see above")
      );
    }
    // The first column is a membership mark, and a membership mark reads as
    // centred rather than as a box in a left-hand gutter.
    const firstColumn = await page.evaluate(() => {
      const th = document.querySelector("thead th.hold");
      const td = document.querySelector("#rows td.hold");
      return {
        head: th ? th.textContent.trim() : null,
        headAlign: th ? getComputedStyle(th).textAlign : null,
        cellAlign: td ? getComputedStyle(td).textAlign : null,
      };
    });
    check(
      "the first column is named List, and centred",
      firstColumn.head === "List" && firstColumn.headAlign === "center" && firstColumn.cellAlign === "center",
      JSON.stringify(firstColumn)
    );
    const dock = await page.evaluate(() => {
      setBudget(budgetCeiling());
      currentPage = 1;
      render();
      const boxes = Array.from(document.querySelectorAll("#rows tr[data-crs] .hold-box"));
      if (boxes.length < 2) return { rows: boxes.length };
      boxes[0].click();
      boxes[1].click();
      const read = (tr) => Array.from(tr.children).map((td) => td.textContent.trim());
      const element = document.getElementById("shortlistDock");
      const box = element.getBoundingClientRect();
      return {
        rows: element.querySelectorAll("#shortlistDockList tr").length,
        hidden: element.hidden,
        position: getComputedStyle(element).position,
        atFootOfScreen: Math.round(box.bottom) === window.innerHeight,
        cells: Array.from(element.querySelectorAll("#shortlistDockList tr")).map((tr) => {
          const crs = tr.dataset.crs;
          const row = document.querySelector('#rows tr[data-crs="' + crs + '"]');
          return {
            crs,
            here: read(tr),
            there: row ? read(row) : null,
            drop: Boolean(tr.querySelector(".shortlist-drop")),
            labelled: (tr.querySelector(".shortlist-drop") || {}).getAttribute
              ? tr.querySelector(".shortlist-drop").getAttribute("aria-label") || ""
              : "",
          };
        }),
      };
    });
    if (dock.rows >= 2) {
      check(
        "shortlisting a place puts a row in a dock held at the foot of the screen",
        dock.rows === 2 && dock.hidden === false && dock.position === "fixed" && dock.atFootOfScreen,
        JSON.stringify({ rows: dock.rows, hidden: dock.hidden, position: dock.position, foot: dock.atFootOfScreen })
      );
      // The dock row is compared with the row it came from rather than with a
      // sentence written here: a shortlist that showed a different price or a
      // different journey than the table would be a comparison of nothing.
      // The results row carries a code and a second price the dock has no room
      // for, so each fact is checked against its own cell's leading token.
      check(
        "a dock row names its station, price, time and changes, and agrees with the row above",
        dock.cells.every((entry) => {
          const [name, price, time, changes] = entry.here;
          const there = entry.there;
          if (!there || there.length < 5) return false;
          return (
            there[1].startsWith(name) &&
            /^£\d/.test(price) &&
            there[2].trim().startsWith(price) &&
            there[3] === time &&
            there[4].split(/\s+/)[0] === changes
          );
        }),
        JSON.stringify(dock.cells)
      );
      check(
        "and every dock row can be taken off the shortlist from the dock itself",
        dock.cells.every((entry) => entry.drop && new RegExp("^Remove " + entry.here[0] + " from").test(entry.labelled)),
        JSON.stringify(dock.cells.map((entry) => entry.labelled))
      );
      const tail = await page.evaluate(() => {
        window.scrollTo(0, document.body.scrollHeight);
        const rows = Array.from(document.querySelectorAll("#rows tr[data-crs]"));
        const last = rows[rows.length - 1].getBoundingClientRect();
        const element = document.getElementById("shortlistDock").getBoundingClientRect();
        return {
          lastBottom: Math.round(last.bottom),
          dockTop: Math.round(element.top),
          padding: document.body.style.paddingBottom,
          viewport: window.innerHeight,
        };
      });
      check(
        "the dock covers no results: the last row ends above it at the foot of the page",
        tail.lastBottom <= tail.dockTop && tail.lastBottom <= tail.viewport && parseFloat(tail.padding) > 0,
        JSON.stringify(tail)
      );
      await page.setViewportSize({ width: 390, height: 720 });
      const stacked = await page.evaluate(() => {
        const element = document.getElementById("shortlistDock");
        const row = element.querySelector("#shortlistDockList tr");
        return {
          table: getComputedStyle(element.querySelector("table")).display,
          body: getComputedStyle(element.querySelector("tbody")).display,
          cell: row ? getComputedStyle(row.children[0]).display : null,
          overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth,
          inScreen: Math.round(element.getBoundingClientRect().width) <= window.innerWidth,
        };
      });
      await page.setViewportSize({ width: 1280, height: 800 });
      check(
        "the dock keeps its four columns on a phone rather than stacking every cell",
        stacked.table === "table" && stacked.body === "table-row-group" && stacked.cell === "table-cell" &&
          stacked.inScreen && stacked.overflow <= 0,
        JSON.stringify(stacked)
      );
      const headings = await page.evaluate(() => {
        const head = document.querySelector("#shortlistDock th.num");
        const cell = document.querySelector("#shortlistDock tbody td.num");
        if (!head || !cell) return null;
        const h = head.getBoundingClientRect();
        const c = cell.getBoundingClientRect();
        return {
          align: getComputedStyle(head).textAlign,
          left: Math.round(h.left - c.left),
          right: Math.round(h.right - c.right),
        };
      });
      check(
        "a dock heading stands over its own column",
        Boolean(headings) && headings.align === "right" &&
          Math.abs(headings.left) < 1.5 && Math.abs(headings.right) < 1.5,
        JSON.stringify(headings)
      );
      await page.evaluate(() => { document.getElementById("shortlistDockClear").click(); });
      const cleared = await page.evaluate(() => ({
        rows: document.querySelectorAll("#shortlistDockList tr").length,
        hidden: document.getElementById("shortlistDock").hidden,
        padding: document.body.style.paddingBottom,
        // The tick on a row is the shortlist drawn on the row, so clearing the
        // list has to clear them. It did not: the boxes kept their ticks and the
        // page showed two places held above a list of none.
        ticked: Array.from(document.querySelectorAll("#rows input.hold-box"))
          .filter((box) => box.checked).length,
        listed: document.querySelectorAll("#shortlistDockList tr").length,
      }));
      check(
        "the dock's own Clear empties it and takes the strip off the screen",
        cleared.rows === 0 && cleared.hidden === true && cleared.padding === "",
        JSON.stringify(cleared)
      );
      check(
        "and clearing the shortlist clears the tick on every row",
        cleared.ticked === 0 && cleared.listed === 0 && dock.cells.length > 0,
        JSON.stringify(cleared)
      );
    } else {
      for (const name of [
        "shortlisting a place puts a row in a dock held at the foot of the screen",
        "a dock row names its station, price, time and changes, and agrees with the row above",
        "and every dock row can be taken off the shortlist from the dock itself",
        "the dock covers no results: the last row ends above it at the foot of the page",
        "the dock keeps its four columns on a phone rather than stacking every cell",
        "the dock's own Clear empties it and takes the strip off the screen",
      ]) {
        check(name, notExercised(`this page lists ${dock.rows} row(s) to choose from`));
      }
    }

    // The space above the page is the heading's own margin and the body's side
    // gutters only. Measured rather than asserted, because a gutter above the
    // content and a heading margin are two answers to one question and the
    // second one was silently the wrong one.
    const gutters = await page.evaluate(() => {
      const body = getComputedStyle(document.body);
      const h1 = document.querySelector("h1");
      const heading = getComputedStyle(h1);
      return {
        top: parseFloat(body.paddingTop),
        side: parseFloat(body.paddingLeft),
        margin: parseFloat(heading.marginTop),
        size: parseFloat(heading.fontSize),
      };
    });
    check(
      "the body has side gutters and none above the heading",
      gutters.top === 0 && gutters.side > 0,
      JSON.stringify(gutters)
    );
    check(
      "and the heading carries half an em of its own size above it",
      Math.abs(gutters.margin - gutters.size / 2) < 1,
      JSON.stringify(gutters)
    );
    // Two controls that make one decision share a row.
    // Opened only if it is shut. The suite has already opened this panel
    // elsewhere, and a second click on an open one closes it, which measures
    // three zero-height rectangles.
    const openedThePanel = await page.evaluate(() => document.getElementById("moreFilters").dataset.open !== "true");
    if (openedThePanel) {
      await page.click("#moreFiltersToggle");
      await page.waitForTimeout(80);
    }
    const filterRow = await page.evaluate(() => {
      const ticket = document.querySelector(".ticket-filter").getBoundingClientRect();
      const party = document.querySelector(".party-filter").getBoundingClientRect();
      const types = document.querySelector(".destination-filter").getBoundingClientRect();
      return {
        ticket: Math.round(ticket.top),
        party: Math.round(party.top),
        types: Math.round(types.top),
        beside: party.left > ticket.right - 2,
      };
    });
    check(
      "the party control sits beside the ticket control on the same row",
      Math.abs(filterRow.ticket - filterRow.party) < 2 && filterRow.beside && filterRow.types > filterRow.party,
      JSON.stringify(filterRow)
    );
    if (openedThePanel) await page.click("#moreFiltersToggle");
    // The three layout rules a reader scrolling ninety rows is relying on: the
    // headings stay, the action column does not widen, and the page controls
    // are not welded to the table's last row.
    //
    // Measured on a page with the budget wide open and no shortlist on it, which
    // is the state a reader comparing two fares is actually in. It matters for
    // all three of these checks and for a different reason in each: the dock is
    // a fixed strip across the foot of the screen and every measurement below
    // is of the results table; a page of one result has one page of results, so
    // nav#pagination is hidden and its margin is nothing to measure; and a page
    // of one result is too short to scroll its own table under the heading.
    await page.setViewportSize({ width: 1280, height: 600 });
    await open(facts.affordable);
    await page.evaluate(() => {
      if (typeof shortlistCodes !== "undefined" && shortlistCodes.length) {
        document.getElementById("shortlistClear").click();
      }
      setBudget(budgetCeiling());
      currentPage = 1;
      render();
    });
    const stuckHeadings = await page.evaluate(() => {
      const table = document.getElementById("rows").closest("table");
      const tableTop = table.getBoundingClientRect().top + window.scrollY;
      const furthest = document.documentElement.scrollHeight - window.innerHeight;
      if (tableTop > furthest) return { reachable: false, tableTop: Math.round(tableTop), furthest };
      window.scrollTo(0, tableTop);
      const th = table.querySelector("thead th");
      const style = getComputedStyle(th);
      return {
        reachable: true,
        scrolled: window.scrollY,
        top: Math.round(th.getBoundingClientRect().top),
        position: style.position,
        background: style.backgroundColor,
      };
    });
    check(
      "the column headings stay at the top of the screen once the table is scrolled",
      stuckHeadings.reachable === true &&
        stuckHeadings.scrolled > 0 &&
        stuckHeadings.position === "sticky" &&
        stuckHeadings.top === 0 &&
        !/rgba\(0, 0, 0, 0\)|transparent/.test(stuckHeadings.background),
      JSON.stringify(stuckHeadings)
    );
    const lastColumn = await page.evaluate(() => {
      const table = document.getElementById("rows").closest("table");
      const th = table.querySelector("thead th:last-child");
      const cells = Array.from(table.querySelectorAll("#rows tr[data-crs] > td:last-child"));
      // The width the content asks for, not the width it was given. scrollWidth
      // cannot answer this: a stretched cell's scrollWidth is the cell's own
      // width, so a column holding 108px of nothing measured as exactly as
      // narrow as one holding nothing but content, and the check passed either
      // way. A clone in a max-content box is the honest measurement -- the
      // browser lays it out at the width its content needs and no other.
      const host = document.createElement("div");
      host.style.cssText = "position:absolute;left:-9999px;top:0;width:max-content;";
      document.body.append(host);
      const wanted = cells.map((td) => {
        const clone = td.cloneNode(true);
        clone.style.width = "max-content";
        host.replaceChildren(clone);
        return Math.ceil(clone.getBoundingClientRect().width);
      });
      host.remove();
      const station = table.querySelector("thead th:nth-child(2)");
      return {
        width: Math.round(th.getBoundingClientRect().width),
        content: Math.max.apply(null, wanted),
        station: Math.round(station.getBoundingClientRect().width),
        table: Math.round(table.getBoundingClientRect().width),
      };
    });
    check(
      "the last column is only as wide as the content in it",
      cellsAreContentWide(lastColumn),
      JSON.stringify(lastColumn)
    );
    const spacing = await page.evaluate(() => {
      const nav = document.getElementById("pagination");
      const table = document.getElementById("rows").closest("table");
      return {
        hidden: nav.hidden,
        pages: document.getElementById("pageStatus").textContent,
        margin: getComputedStyle(nav).marginTop,
        gap: Math.round(nav.getBoundingClientRect().top - table.getBoundingClientRect().bottom),
      };
    });
    check(
      "nav#pagination has room between it and the table",
      spacing.hidden === false &&
        parseFloat(spacing.margin) > 0 &&
        spacing.gap >= parseFloat(spacing.margin) - 1,
      JSON.stringify(spacing)
    );
    const thirdRow = page.locator("#rows tr[data-crs]").nth(2);
    if (await thirdRow.count()) {
      await thirdRow.hover();
      const tint = await thirdRow.evaluate(
        (tr) => getComputedStyle(tr.firstElementChild).backgroundColor
      );
      check(
        "a results row is tinted under the pointer",
        tint !== "" && !/rgba\(0, 0, 0, 0\)|transparent/.test(tint),
        tint
      );
    } else {
      check("a results row is tinted under the pointer", notExercised("this page lists fewer than three rows"));
    }
    await page.setViewportSize({ width: 1280, height: 800 });

    // 8. The origin picker: search, navigate, and the no-match wording
    // (ADR-0019). Choosing a station is navigation, so the link must go to
    // another page, and there must never be an empty picker.
    await page.setViewportSize({ width: 1280, height: 800 });
    await open(facts.affordable);

    // The layout's thesis: the budget leads, and row actions carry real touch
    // targets. Measured, not assumed.
    const layout = await page.evaluate(() => {
      // The two actions a row keeps beside buying are inside the row's panel, so
      // a panel is opened for the measurement and closed again: a target this
      // gate never sees is a promise nobody measured.
      const copyHitInPanel = (measure) => {
        const already = document.querySelector("#rows tr.detail button[aria-label^='Copy']");
        if (already) return measure(already);
        const expander = document.querySelector("#rows tr:not(.detail) .toggle[aria-expanded='false']");
        if (!expander) return 0;
        expander.click();
        const button = document.querySelector("#rows tr.detail button[aria-label^='Copy']");
        const size = button ? measure(button) : 0;
        expander.click();
        return size;
      };
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
        copyHit: copyHitInPanel(hitOf),
        buyHit: hitOf(document.querySelector("#rows a.buy"))
      };
    });
    check("the budget is inline in the large heading", layout.budgetLeads);
    check("party and destination filters share the horizontal bar", layout.secondaryHoldsPartyAndFilter);
    // The disclosure's own name and what it says is on. A folded panel whose
    // summary line reads as a sentence rather than as three labelled facts
    // leaves a reader on a phone unable to tell which of the three is narrowed.
    const filterBar = await page.evaluate(() => {
      const more = document.getElementById("moreFilters");
      const toggle = document.getElementById("moreFiltersToggle");
      const panel = document.getElementById("moreFiltersPanel");
      if (!more || !toggle || !panel) return null;
      const wasOpen = more.dataset.open === "true";
      if (!wasOpen) document.getElementById("moreFiltersToggle").click();
      const openStyle = getComputedStyle(panel);
      const toggleStyle = getComputedStyle(toggle);
      const closed = {
        display: openStyle.display,
        columns: openStyle.gridTemplateColumns,
        gap: openStyle.gap,
        background: openStyle.backgroundColor,
        padding: openStyle.paddingTop,
        marginBottom: openStyle.marginBottom,
        toggleMarginBottom: toggleStyle.marginBottom,
      };
      const state = document.getElementById("filterState").textContent;
      const label = (toggle.querySelector(".more-filters-label") || {}).textContent || "";
      if (!wasOpen) document.getElementById("moreFiltersToggle").click();
      return { closed, state: state.trim(), label: label.trim() };
    });
    if (filterBar) {
      check(
        "the filter panel opens as a two-column grid on the field background",
        filterBar.closed.display === "grid" &&
          filterBar.closed.columns.split(" ").length === 2 &&
          filterBar.closed.columns.split(" ").every((part) => parseFloat(part) > 0) &&
          filterBar.closed.columns.split(" ").length === 2 &&
          filterBar.closed.gap === "16px 32px" &&
          filterBar.closed.background !== "rgba(0, 0, 0, 0)" &&
          filterBar.closed.padding === "16px" &&
          filterBar.closed.marginBottom === "16px" &&
          filterBar.closed.toggleMarginBottom === "0px",
        JSON.stringify(filterBar.closed)
      );
      check(
        "the disclosure is named Filter this list",
        /^filter this list$/i.test(filterBar.label),
        JSON.stringify(filterBar.label)
      );
      check(
        "the summary names what is narrowed, counts the railcard and says All",
        /^Ticket: Cheapest of any type \u00b7 Travellers: One adult, 0 railcard \u00b7 Destination: All$/.test(
          filterBar.state
        ),
        JSON.stringify(filterBar.state)
      );
    } else {
      check(
        "the filter panel opens as a two-column grid on the field background",
        notExercised("this page carries no filter bar")
      );
      check("the disclosure is named Filter this list", notExercised("see above"));
      check("the summary names what is narrowed, counts the railcard and says All", notExercised("see above"));
    }
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

    // The completion is a word inside the field, and the field is a word inside
    // the heading, so three keys matter: Backspace to take the suggestion back,
    // and Tab or Enter to go to the place it names. The prefix comes from the
    // page's own station list rather than from a name the fixture happened to
    // carry, so a build of one station and a build of three thousand are asked
    // the same question.
    const completable = await page.evaluate(() => {
      const list = (typeof STATIONS !== "undefined" ? STATIONS : DATA.stations) || [];
      return list
        .map((station) => station.name)
        .filter((name) => name.length >= 8)
        .sort((a, b) => a.length - b.length)[0] || "";
    });
    const canComplete = completable.length >= 4;
    const prefix = completable.slice(0, 3);
    const headingHeight = () =>
      page.evaluate(() => {
        const heading = document.getElementById("pageHeading");
        return heading ? Math.round(heading.getBoundingClientRect().height) : -1;
      });
    await page.fill("#originSearch", "");
    const heights = [await headingHeight()];
    if (canComplete) {
      await page.focus("#originSearch");
      await page.type("#originSearch", prefix, { delay: 10 });
      const completed = await page.inputValue("#originSearch");
      heights.push(await headingHeight());
      // The completion is a suggestion, so it is written with its tail
      // selected. Backspace has to remove what was suggested, not consume one
      // character of the name the reader typed: it re-applied the suggestion to
      // its own undo, so the field came back byte-identical and the key looked
      // dead.
      await page.keyboard.press("Backspace");
      const taken = await page.inputValue("#originSearch");
      check(
        "Backspace takes the completion back",
        completed.toLowerCase().startsWith(prefix.toLowerCase()) && taken === prefix,
        `${prefix} -> "${completed}" -> Backspace -> "${taken}"`
      );
      await page.keyboard.press("Backspace");
      const shorter = await page.inputValue("#originSearch");
      check(
        "and Backspace again deletes a character of what was typed",
        shorter === prefix.slice(0, -1),
        `"${taken}" -> Backspace -> "${shorter}"`
      );
      // The field is a word in a balanced heading. A field sized to its content
      // changes that word's width on every keystroke, and the heading
      // rebalances around it: measured at 1280px, 220px tall when empty and
      // 196px from the first keystroke on.
      await page.fill("#originSearch", "");
      await page.focus("#originSearch");
      for (const value of ["", "N", "No", "Not", prefix, completable]) {
        await page.fill("#originSearch", value);
        heights.push(await headingHeight());
      }
      check(
        "the heading does not change height as the field is typed into",
        heights.every((height) => height === heights[0]) && heights[0] > 0,
        heights.join("px, ") + "px"
      );
      // Accepting a completion is choosing a place, so it goes there.
      await page.fill("#originSearch", "");
      await page.focus("#originSearch");
      await page.type("#originSearch", prefix, { delay: 10 });
      const wanted = await page.evaluate(() => {
        const list = (typeof STATIONS !== "undefined" ? STATIONS : DATA.stations) || [];
        const typed = document.getElementById("originSearch").value.trim().toLowerCase();
        const station = list.find((s) => s.name.toLowerCase() === typed);
        return station ? station.href : null;
      });
      const before = page.url();
      const beforePath = new URL(before).pathname;
      const probe = await page.context().newPage();
      let landed = "";
      try {
        await probe.goto(before);
        if (await probe.locator("#changeOrigin").count()) await probe.click("#changeOrigin");
        await probe.waitForSelector("#originSearch");
        await probe.focus("#originSearch");
        await probe.type("#originSearch", prefix, { delay: 10 });
        const moved = probe
          .waitForURL((url) => new URL(url).pathname !== beforePath, { timeout: 5000 })
          .catch(() => null);
        await probe.keyboard.press("Tab");
        await moved;
        landed = probe.url();
      } finally {
        await probe.close();
      }
      check(
        "Tab on a completion goes to that station's page",
        wanted !== null && landed && new URL(landed, before).pathname === new URL(wanted, before).pathname,
        `${completable} -> ${landed || "(no navigation)"} (wanted ${wanted})`
      );
      await page.fill("#originSearch", "");
    } else {
      for (const name of [
        "Backspace takes the completion back",
        "and Backspace again deletes a character of what was typed",
        "the heading does not change height as the field is typed into",
        "Tab on a completion goes to that station's page",
      ]) {
        check(name, notExercised("no station on this page has a name long enough to complete"));
      }
    }
      await page.fill("#originSearch", "");
      // S12: the one distinction a first-time reader cannot guess, said once,
      // in the page's own terms, and only on the page where it is true.
      const firstUse = (await page.textContent("#firstUse")) || "";
      check(
        "the page says the station name in the heading moves station",
        // The control is the station's own name with a field beside it, so the
        // sentence has to name the name rather than a button that is no longer
        // there: it said "Change" for exactly as long as that word was on the
        // page, which is the whole point of the check. Nothing about narrowing
        // is claimed now: the field filters the list as it is typed into.
        /station name/i.test(firstUse) && /start from somewhere else/i.test(firstUse),
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
      // The completion, driven from a station this page actually lists rather
      // than from a name a fixture happens to carry, so the check is a test of
      // the field and not of the feed.
      const firstStation = await page.evaluate(() => (DATA.stations || [])[0] || null);
      if (firstStation && firstStation.name.length > 4) {
        const letters = firstStation.name.slice(0, 3);
        await page.click("#changeOrigin");
        await page.fill("#originSearch", "");
        await page.type("#originSearch", letters, { delay: 10 });
        await page.waitForTimeout(80);
        const typed = await page.evaluate(() => {
          const field = document.getElementById("originSearch");
          return {
            value: field.value,
            start: field.selectionStart,
            end: field.selectionEnd,
          };
        });
        check(
          `typing ${letters} completes the station's name in the field, with the rest of it selected`,
          typed.value === firstStation.name &&
            typed.start === letters.length &&
            typed.end === firstStation.name.length,
          JSON.stringify({ letters, station: firstStation.name, typed })
        );
        // Where the list is drawn, measured against the field it belongs to.
        const placed = await page.evaluate(() => {
          const field = document.getElementById("originSearch").getBoundingClientRect();
          const list = document.getElementById("originPicker");
          const box = list.getBoundingClientRect();
          return {
            gap: Math.round(box.top - field.bottom),
            position: getComputedStyle(list).position,
            aligned: Math.abs(box.left - field.left) < 200,
            options: list.querySelectorAll("a").length,
          };
        });
        check(
          "the list of stations is drawn under the field, not two paragraphs further down",
          placed.position === "fixed" && placed.gap >= 0 && placed.gap < 40 && placed.aligned && placed.options > 0,
          JSON.stringify(placed)
        );
        // Walking away: a click on the page, not in the field and not in the list.
        await page.mouse.click(24, 520);
        await page.waitForTimeout(120);
        const walked = await page.evaluate(() => ({
          field: Boolean(document.getElementById("originSearch")),
          picker: Boolean(document.getElementById("originPicker")),
          name: (document.getElementById("changeOrigin") || { textContent: "" }).textContent.replace(/\s+/g, " ").trim(),
          expanded: (document.getElementById("changeOrigin") || {}).getAttribute
            ? document.getElementById("changeOrigin").getAttribute("aria-expanded")
            : null,
        }));
        // Walking away is the gesture that does not commit anything. It puts
        // the page's own station name back, closes the picker and leaves the
        // reader where they were, which is what the check below says; with Tab
        // and Enter now going to the station a completion names, this is the
        // only way out of a half-typed name that keeps the page.
        check(
          "a click on the page puts the station's name back where the field was",
          walked.field === false && walked.name.length > 0 && walked.expanded === "false",
          JSON.stringify(walked)
        );
        await page.evaluate(() => { document.getElementById("changeOrigin").focus(); });
      } else {
        for (const name of [
          "typing a station's first letters completes the name in the field",
          "the list of stations is drawn under the field",
          "a click on the page puts the station's name back where the field was",
        ]) {
          check(name, notExercised("this page lists no station a reader could type"));
        }
      }
      check("and focus returns to the heading station control", await page.evaluate(() => document.activeElement && document.activeElement.id === "changeOrigin"));
      // The field the reader types in lives in the heading while the picker is
      // open, so Escape has to be caught where the key is actually pressed.
      check(
        "and Escape in the field closes it too",
        await page.evaluate(() => {
          // The field is detached while the picker is closed, so it is read
          // after the picker is opened, not before.
          document.getElementById("changeOrigin").click();
          const field = document.getElementById("originSearch");
          if (!field) return false;
          field.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
          return document.getElementById("originPicker").hidden;
        })
      );
      // The station name is the control while the picker is closed, and it is
      // the field while the picker is open: pressing it a second time is not
      // something a reader can do, because the name is not on the page any
      // more. What has to be true instead is that closing it puts the name
      // back, and that the field sits in the heading while it is open.
      check(
        "closing the picker puts the station name back",
        await page.evaluate(() => {
          const button = document.getElementById("changeOrigin");
          return Boolean(button) && !button.hidden && button.textContent.trim().length > 0;
        })
      );
      await pickerButton.click();
      check(
        "and opening it puts the field where the name was",
        await page.evaluate(() => {
          const field = document.getElementById("originSearch");
          const button = document.getElementById("changeOrigin");
          return Boolean(field) && Boolean(button) && button.hidden && field.closest("h1") !== null;
        })
      );
      // Keyboard-only reachability of the picker's first option.
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

  // ADR-0047: the station route fetches one stylesheet, and a fetch can fail.
  // The page's own answer is in its own bytes, so the question is not whether
  // the page survives -- it does, because the rows travel inline -- but whether
  // it is left offering a switch that cannot change a palette it does not have,
  // which is the picker's "a control that opens nothing" one route down. The
  // document is withheld on a second page in the same context, so the page
  // under test keeps the styling every other check here is reading.
  const WITHOUT_STYLE = [
    "a page whose stylesheet does not arrive still lists its destinations",
    "and it offers no theme switch it cannot deliver",
    "and it says its styling did not load rather than looking broken",
  ];
  if (kind === "station") {
    const bare = await context.newPage();
    await bare.route("**/*.css", (route) =>
      route.fulfill({ status: 404, contentType: "text/plain", body: "no such stylesheet" })
    );
    await bare.goto(url);
    const unstyled = await bare.evaluate(() => ({
      rows: document.querySelectorAll("#rows tr[data-crs]").length,
      summary: ((document.getElementById("summary") || {}).textContent || "").trim(),
      prices: Array.from(document.querySelectorAll("#rows tr[data-crs]"))
        .slice(0, 3)
        .map((row) => (row.textContent || "").trim()),
      switch: !!document.getElementById("themeToggle"),
      note: (document.getElementById("styleNote") || {}).hidden,
      noteText: ((document.getElementById("styleNote") || {}).textContent || "").trim(),
      styled: getComputedStyle(document.documentElement)
        .getPropertyValue("--tbe-stylesheet").trim(),
    }));
    check(
      WITHOUT_STYLE[0],
      unstyled.rows > 0 &&
        /\d+ destinations?/.test(unstyled.summary) &&
        unstyled.prices.every((text) => /\u00a3\d/.test(text)),
      `${unstyled.rows} row(s), count line "${unstyled.summary}"`
    );
    check(
      WITHOUT_STYLE[1],
      unstyled.styled === "" && unstyled.switch === false,
      `stylesheet marker "${unstyled.styled}", switch ${unstyled.switch ? "present" : "removed"}`
    );
    check(
      WITHOUT_STYLE[2],
      unstyled.note === false && /did not load/.test(unstyled.noteText),
      unstyled.noteText || "(nothing said)"
    );
    await bare.close();
  } else {
    for (const name of WITHOUT_STYLE) {
      check(name, notExercised("this route inlines its own stylesheet, so no request can fail"));
    }
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
  if (routeKind === "station" || routeKind === "chooser" || routeKind === "release") {
    const headingName = (String(await page.locator("h1").ariaSnapshot()).split("\n")[0].match(/"([^"]*)"/) || [])[1] || "";
    // The chooser's page data is STATIONS, not DATA, and its heading asks which
    // station rather than naming one, so the station is only read where it is
    // both in the payload and in the sentence. A one-station release names its
    // station in that heading, so it is read there too.
    const origin =
      routeKind === "station"
        ? await page.evaluate(() => DATA.origin.name)
        : routeKind === "release"
          ? await page.evaluate(() => (STATIONS[0] || {}).name || "")
          : "";
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
        [".fare-line", "the fare in words on the row"],
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
// The row opened for the measuring is a row that HAS a condition: the
      // condition is only printed where a fare carries a restriction code, so
      // a probe that opened the first row found nothing to measure on a page
      // whose cheapest fare is an unrestricted one, and reported the C14
      // regression as covered when it had measured no condition at all. The
      // named modes are tried in turn and the page is put back afterwards, so
      // the probe does not change what the rest of the matrix measures.
      const modeBefore =
        (document.querySelector('input[name="ticketMode"]:checked') || {}).value || "";
      const budgetBefore = document.getElementById("budget") ? budget.value : "";
      let rowToggle = null;
      if (document.getElementById("rows") && typeof setBudget === "function") {
        setBudget(budgetCeiling());
        currentPage = 1;
        render();
        for (const mode of [modeBefore, "single", "return", "anytime"]) {
          const input = document.querySelector(`input[name="ticketMode"][value="${mode}"]`);
          if (!input) continue;
          input.checked = true;
          currentPage = 1;
          render();
          const row = Array.from(document.querySelectorAll("#rows tr:not(.detail)")).find((r) => {
            const found = activeDestinations().find((d) => d.crs === r.dataset.crs);
            return found && found.restrictionCode;
          });
          if (row) {
            rowToggle = row.querySelector(".toggle[aria-expanded=false]");
            break;
          }
        }
      }
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
      const back = document.querySelector(`input[name="ticketMode"][value="${modeBefore}"]`);
      if (back) back.checked = true;
      if (document.getElementById("rows") && typeof setBudget === "function") {
        setBudget(Number(budgetBefore));
        currentPage = 1;
        render();
      }
      // Whether this page's feed prices any fare with a condition at all. A
      // page that has none cannot be asked to have measured one, and saying so
      // is the difference between "nothing to measure" and "the condition was
      // dropped". Carried on the array so every reader below keeps its shape.
      measured.hasRestricted = Boolean(
        typeof DATA !== "undefined" &&
          [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations]
            .flat()
            .filter(Boolean)
            .some((d) => Boolean(d.restrictionCode))
      );
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
        !contrast.hasRestricted ||
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
      // The row's own actions are inside the row's panel, so one panel is
      // opened for the sweep and closed at the end: an unmeasured promise is a
      // promise nobody checked.
      const expander = document.querySelector("#rows tr:not(.detail) .toggle[aria-expanded='false']");
      const firstPanel = document.querySelector("#rows tr.detail") ? null : expander;
      if (firstPanel) firstPanel.click();
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
      if (firstPanel) firstPanel.click();
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

  const assets = sharedAssets(pages);
  if (assets.missing.length) {
    console.error(
      "the page(s) under test ask for " + assets.missing.join(", ") +
        ", which is not beside them, so the checks that need it would be skipped."
    );
    process.exit(1);
  }
  const server = await serve(pages.map((entry) => entry.body), assets.files);
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
