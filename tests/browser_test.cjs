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
 *
 * Every expectation is read out of the page under test, so the suite is a
 * test of the template rather than of a station, and one run can sweep the
 * pages a build wrote: each path gets its own context and its own result,
 * and the run fails if any page fails.
 *
 * Exit codes: 0 every page behaves, 1 one does not, 2 playwright is
 * unavailable. A skip is reported loudly and exits 2, because a test that
 * passes quietly on a machine where it never ran is the thing this project
 * keeps refusing to do.
 */

const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");

const PAGES = process.argv.length > 2 ? process.argv.slice(2) : ["demo.html"];
const SELLER = /^https:\/\/www\.(nationalrail\.co\.uk|thetrainline\.com)\//;

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

async function runPage(browser, index, given, file, body, base) {
  // One context per page. The seller's stub route and the clipboard grant are
  // both context-scoped, and a page that failed a step must not hand the next
  // one a reader still carrying its budget, its filters, or its mode.
  const checks = [];
  const check = (name, condition, detail) => {
    checks.push({ name, ok: Boolean(condition), detail });
  };
  // One result per page, printed the same way whether the page ran or was
  // missing, so several pages in one log are read the same way.
  const printPage = () => {
    console.log("\n== " + given);
    for (const { name, ok, detail } of checks) {
      console.log((ok ? "  ok    " : "  FAIL  ") + name + (!ok && detail ? "  <- " + detail : ""));
    }
    const failed = checks.filter((entry) => !entry.ok).length;
    console.log(`${checks.length - failed}/${checks.length} browser checks passed against ${given}`);
  };
  let stopped = false;
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
      check("a heritage row links the UNESCO property the payload names", false, "no destination on this page carries a UNESCO property");
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
      check("a small town is its own class, not a town", false, "this page has no small town in return mode");
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
        false,
        `this page offers ${pair.length} specific chip(s), so multi-select cannot be exercised`
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
    const partyBudget = await page.evaluate(() =>
      Math.max(1, Math.ceil(DATA.destinations.reduce((low, d) => Math.min(low, d.partyPence), Infinity) / 100))
    );
    await page.fill("#budgetNumber", String(partyBudget));
    await page.check('input[name="unit"][value="party"]');
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
      const href = await page.locator("#originPicks a").first().getAttribute("href");
      check("options are links to station pages", /^\/from\/.+\/$/.test(href), href);
      // The query comes from the picker's own first option, so the check is
      // about narrowing rather than about a station name the fixture happened
      // to carry.
      const firstWord = (((await page.locator("#originPicks a").first().textContent()) || "").trim().split(/[\s(]+/)[0] || "");
      const query = firstWord.slice(0, 4);
      await page.fill("#originSearch", query);
      const narrowed = await page.locator("#originPicks a").count();
      const narrowedText = await page.locator("#originPicks").textContent();
      check("typing narrows the picker", narrowed > 0 && narrowed < pickCount && narrowedText.includes(firstWord), `${query} -> ${narrowed} of ${pickCount} options`);
      await page.fill("#originSearch", "zzzz");
      check(
        "a no-match says so and names the code route",
        (await page.locator("#originNomatch").isVisible()) && /three-letter code/.test(await page.textContent("#originNomatch"))
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
      check("picker options are keyboard-focusable links", await firstOption.evaluate((el) => el.tagName === "A" && el.href.endsWith("/")));
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
  const total = results.reduce((sum, result) => sum + result.checks.length, 0);
  const failed = results.reduce(
    (sum, result) => sum + result.checks.filter((entry) => !entry.ok).length,
    0
  );
  const broken = results.filter(
    (result) => result.stopped || result.checks.some((entry) => !entry.ok)
  );
  // One line for the run as well as one per page, so a log with several pages
  // in it ends with something that can be read without counting back.
  console.log(
    broken.length
      ? `\n${broken.length} of ${results.length} page(s) failed: ${total - failed}/${total} checks passed (${broken.map((result) => result.given).join(", ")})`
      : `\n${results.length} page(s), ${total}/${total} browser checks passed`
  );
  process.exit(failed || broken.length ? 1 : 0);
}

async function main() {
  const playwright = requirePlaywright();
  if (!playwright) process.exit(2);

  const pages = PAGES.map((given) => {
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
        console.error("  python make_synthetic_feed.py _demo_feed --unserved-station");
        console.error("  python build_demo_page.py --feed _demo_feed --timetable _demo_feed --origin GRN --out demo.html");
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
