/**
 * The station page: which route this is, and the state every section below
 * reads.
 *
 * One context per page, because the seller's stub route and the clipboard
 * grant are both context-scoped and a page that failed a step must not hand
 * the next one a reader still carrying its budget, its filters or its mode.
 * Which route a page is, is decided by what it carries rather than by where it
 * sits, so the root of a single-station build is driven as the station page it
 * is. One page-side reader of the payload is installed on every load, and
 * every page is opened through it, so a navigation throws away the reader and
 * no step can forget to reinstall it.
 *
 * The sections are functions in their own files, in the order the checks have
 * to run: a section that leaves a budget or a list behind is read by the one
 * after it. They are handed `world` -- the page, the helpers above, and
 * whatever an earlier section left on it.
 */
const { NOT_EXERCISED, SELLER, installLineCounter, notExercised } = require("./harness.cjs");
const { checkAccessibilityMatrix } = require("./a11y-matrix.cjs");
const { checkChooser } = require("./chooser.cjs");
const { checkReleaseRoot } = require("./release-root.cjs");
const { renderThePage } = require("./station-render.cjs");
const { driveTheFilters } = require("./station-filters.cjs");
const { checkTheRowActions, checkTheTwoTicketRow } = require("./station-rows.cjs");
const { checkTheFareDetails } = require("./station-fares.cjs");
const { checkTheShortlist, compareTheDockWithTheTable } = require("./station-shortlist.cjs");
const { measureTheLayout } = require("./station-layout.cjs");
const { checkTheOriginPicker } = require("./station-picker.cjs");
const { checkWithoutTheStylesheet, checkWithoutTheScript } = require("./station-assets.cjs");
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
    // skips more than the budget for the shape of its pages -- SKIP_BUDGET
    // with a timetable, SKIP_BUDGET_WITHOUT_TIMES without one -- fails for
    // that reason, in every mode, and names the page.
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
  // Installed before the first navigation, so every check that counts painted
  // lines measures them the one way (E15 of the 17 October 2026 audit).
  await installLineCounter(page);
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
  // Whether this page carries a timetable, for the two skip budgets in report().
  // A prices-only page cannot run the checks about times, days and the journeys
  // they describe, and that is a smaller claim about the page rather than a
  // page with nothing in it. Read off the payload, like every other fact about
  // this page, so a sentence in the template cannot decide it.
  const times =
    kind === "station" ? await page.evaluate(() => Boolean(DATA.hasJourneys)) : null;
  // Whether this page lists any place at all. ADR-0076 writes a page for a
  // station whose every priced place no journey reaches, and that page has no
  // rows, no chips and no ticket actions to drive: its own sentence is the
  // claim, and the checks about a list have nothing to read. Read off the
  // payload like every other fact here, and reported with the page because an
  // emptied page is a shape of its own rather than a page with too little in it
  // (harness.report, which exempts it from the skip budget for that reason).
  const lists =
    kind === "station"
      ? await page.evaluate(
          () =>
            (DATA.destinations || []).length +
              (DATA.singleDestinations || []).length +
              (DATA.anytimeDestinations || []).length > 0
        )
      : null;
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
    return { given, file, checks, stopped, notStation, kind, times, lists };
  }
  if (kind === "chooser" || kind === "release") {
    try {
      if (kind === "chooser") await checkChooser(page, url, check);
      else await checkReleaseRoot(page, url, check);
      await checkWithoutTheScript({ page, url, check, notExercised, kind, context });
    } catch (error) {
      console.error("the browser test stopped early on " + given + ": " + error.message);
      stopped = true;
    }
    // A checked chooser is a tested page, so it is tallied like one rather
    // than reported as a path this suite could not read.
    notStation = false;
    printPage();
    await context.close();
    return { given, file, checks, stopped, notStation, kind, times, lists };
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
    // The price the page shows for a row: the price for the party on screen, or
    // the chosen card's for it, whichever is less (page/station/railcards.js's
    // priceOf). One reader of it, because every expectation about a budget here
    // is about the number on screen -- reading adultPence instead reported a
    // correctly-offered chip as a broken control on eight pages, where an
    // outbound single was inside the budget the return was not (15 October
    // 2026). Q2: the card is resolved from the row's own entry, not from a
    // railcardPence the page no longer carries.
    const priceOfRow = (destination) => {
      const party = document.querySelector('input[name="unit"]:checked').value === "party";
      const base = party ? destination.partyPence : destination.adultPence;
      const select = document.getElementById("railcardSelect");
      if (!select || !select.value) return base;
      const card = (destination.railcards || {})[select.value];
      if (!card || card.pricePence === null) return base;
      return Math.min(base, card.pricePence * (party ? 2 : 1));
    };
    // Q4: the page opens on the cheapest fare of any ticket type, which is not
    // one of the three payload lists, so the reader composes that list the way
    // the rule says -- one row per destination, the cheaper of the fares on
    // screen -- rather than falling back to the returns and expecting a page
    // that is behaving correctly to fail every chip check. Written here, from
    // the payload, so the check that the page agrees with it is not circular.
    window.cheapestOfEveryList = () => {
      const cheapest = new Map();
      for (const list of [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations]) {
        for (const destination of list || []) {
          const held = cheapest.get(destination.crs);
          if (!held || priceOfRow(destination) < priceOfRow(held)) {
            cheapest.set(destination.crs, destination);
          }
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
      priceOf: priceOfRow,
      price: (destination) =>
        document.querySelector('input[name="unit"]:checked').value === "party"
          ? destination.partyPence : destination.adultPence,
      cheapest: (pick) => TYPES.list().reduce((low, d) => Math.min(low, pick(d)), Infinity),
      dearest: (pick) => TYPES.list().reduce((high, d) => Math.max(high, pick(d)), 0),
    };
  });
  // The rows a page holds, read from the page itself each time it is
  // opened. It lives on the world object because a section reads it
  // after open() has run, and a section is a function of its own.
  // Every page is opened through here: a navigation throws away the reader,
  // so one way to load means no step can forget to reinstall it. The budget
  // under test is the page's own affordable one unless a step wants another.
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
    // Visible as well as present: a page that lists nothing hides the whole
    // refinements bar (its list cannot be narrowed), and a press on a control
    // that is off screen waits thirty seconds and stops the run.
    if (!open && (await toggle.isVisible())) await toggle.click();
  };
  const open = async (budget) => {
    await page.goto(url);
    await installReader();
    world.pageSize = await page.evaluate(() => PAGE_SIZE);
    await openFilters();
    if (budget !== undefined) await page.fill("#budgetNumber", String(budget));
  };
  // What a type means on this page, in the mode and at the budget on screen:
  // which rows it leaves, whether the mode's list carries it at any price, and
  // whether it is worth offering at all -- the last is the second read against
  // the budget, and it is the one the page's own chip rule uses. The price is
  // the one the page shows, so a chip's own count and this expectation are the
  // same arithmetic.
  const expectedFor = (type) =>
    page.evaluate((wanted) => ({
      carried: TYPES.list().some((d) => TYPES.types(d).includes(wanted)),
      rows: TYPES.list().filter(
        (d) => TYPES.types(d).includes(wanted) && TYPES.priceOf(d) <= TYPES.cap()
      ),
    }), type);
  // One type per call, checked in both directions: the rows it leaves come
  // from the payload, and a chip must be offered exactly when this mode's list
  // has a destination of that type **inside the budget on screen**. A chip that
  // can only ever return nothing reads as a broken control rather than an empty
  // result, so the page does not offer one -- which makes the budget half of the
  // rule, the same half the count beside the chip is counting.
  // A facet chip is one press away: the ten thematic types live behind the
  // "More types" chip the settlement bands end their row with (critique item 3,
  // second half), so a step that presses one presses that disclosure first --
  // on the control the page offers, the way a reader reaches it, rather than by
  // un-hiding the group behind it. Nothing happens for a chip already in reach.
  const revealType = async (chip) => {
    if (!(await page.locator(chip).count())) return false;
    // A chip lives inside the refinements disclosure, and a check that closed
    // it leaves every chip on screen hidden: a press then waits thirty seconds
    // on an input that is offered and not visible (Reston, 21 October 2026).
    // Every press site asks this helper to make the chip reachable, so the
    // disclosure is opened here rather than at each of them.
    const shut = await page.evaluate(() => {
      const panel = document.getElementById("moreFilters");
      return !!panel && panel.dataset.open !== "true";
    });
    if (shut) await page.click("#moreFiltersToggle");
    const folded = await page.locator(chip).evaluate((el) => {
      const panel = document.getElementById("moreTypesPanel");
      return !!panel && panel.hidden && panel.contains(el);
    });
    if (!folded) return false;
    await page.click("#moreTypes");
    return true;
  };
  const checkChip = async (type, offered, matched) => {
    const expected = await expectedFor(type);
    const chip = `input[name="destinationType"][value="${type}"]`;
    // The page's own offer, read off the label the page hides rather than off
    // the screen: a chip behind the fold is off screen whether or not the page
    // offers it, so visibility alone cannot tell those two apart.
    const onOffer = (await page.locator(chip).count())
      ? await page.locator(chip).evaluate((el) => !el.closest("label").hidden)
      : false;
    if (!expected.rows.length) {
      check(
        offered,
        !onOffer,
        `${type} chip ${expected.carried ? "carried only above this budget" : "carried by nothing"} in this mode`
      );
      return expected;
    }
    if (!onOffer) {
      check(
        offered,
        false,
        `${type} chip hidden although ${expected.rows.length} destinations inside the budget carry it`
      );
      return expected;
    }
    // Offered, so it has to be reachable: for a facet that is one press, and a
    // chip the page offers and a press does not reach is the same broken
    // control as a chip that was never offered.
    await revealType(chip);
    if (!(await page.locator(chip).isVisible())) {
      check(offered, false, `${type} chip is offered but not on screen, disclosure and all`);
      return expected;
    }
    await page.check(chip);
    // The sentence a chip contributes to names the chip, not its count: the
    // count is a number about the chip, and "in cities (2)" reads as part of
    // the filter the reader asked for (E17 of the 17 October 2026 audit).
    const named = await page.evaluate((value) => {
      const input = document.querySelector(`input[name="destinationType"][value="${value}"]`);
      const span = input && input.parentElement ? input.parentElement.querySelector("span") : null;
      const count = document.querySelector(`[data-count-for="${value}"]`);
      return {
        sentence: typeLabel(),
        name: span ? span.textContent.trim().toLowerCase() : "",
        count: count ? count.textContent : "",
      };
    }, type);
    check(
      "a chip's count stays out of the sentence that names it",
      named.count
        ? named.sentence.includes(named.name) && !named.sentence.includes("(")
        : notExercised(`the ${type} chip carries no count on this page`),
      JSON.stringify(named)
    );
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
    const fits = Math.min(expected.rows.length, world.pageSize);
    // A row the payload does not carry is a defect this check has to be able to
    // report, not a crash. `byCrs.get(crs).price` on one would throw before the
    // membership test below can say so, and a suite that dies on a regression
    // reports the exception instead of the thing that is wrong. The prices are
    // read in the page, because that is where the reader of them lives -- the
    // number on screen is the party's and the chosen card's, not adultPence.
    const prices = await page.evaluate((crses) => {
      const carried = new Map(TYPES.list().map((d) => [d.crs, d]));
      return crses.map((crs) => (carried.has(crs) ? TYPES.priceOf(carried.get(crs)) : null));
    }, rendered);
    check(
      matched,
      shown === fits &&
        shown === rendered.length &&
        rendered.every((crs) => byCrs.has(crs)) &&
        rendered.every((crs) => text.includes(byCrs.get(crs).name)) &&
        prices.every((pence) => pence !== null) &&
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
      const dearest = TYPES.dearest((d) =>
        (TYPES.types(d).includes(wanted) ? TYPES.priceOf(d) : 0));
      return dearest ? Math.max(1, Math.ceil(dearest / 100)) : null;
    }, type);
  const world = {
    page,
    url,
    base,
    given,
    file,
    check,
    notExercised,
    open,
    installReader,
    rows,
    checkChip,
    revealType,
    budgetFor,
    kind,
    lists,
    context,
    pageSize: 20,
  };

  // A page ADR-0076 emptied has no row, no chip and no ticket action: it hides
  // the refinements bar its list cannot be narrowed by, and every section below
  // is about a list. Each is named here so the log says what this page could
  // not exercise rather than going quiet about it, and the sections that are
  // about the page rather than its rows -- the matrix above, the build's own
  // sentence, the two asset failures -- still run.
  const listSections = [
    ["the budget, the ticket modes and the type chips narrow the list", driveTheFilters],
    ["a row's ticket link and copy handoff go where they say", checkTheRowActions],
    ["a row's own disclosure says what its fare is", checkTheFareDetails],
    ["the shortlist holds the rows a reader chose", checkTheShortlist],
    ["a place priced in two parts is one row at both fares", checkTheTwoTicketRow],
    ["the dock and the table agree", compareTheDockWithTheTable],
    ["the layout holds at every width", measureTheLayout],
    ["the heading's station can be changed", checkTheOriginPicker],
  ];
  try {
    await renderThePage(world);
    for (const [what, section] of listSections) {
      if (lists === false) {
        check(
          what,
          notExercised("this page lists no destination, so it has no list to drive")
        );
        continue;
      }
      await section(world);
    }
    await checkWithoutTheStylesheet(world);
    await checkWithoutTheScript(world);
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
  return { given, file, checks, stopped, notStation, kind, times, lists };
}
module.exports = { runPage };
