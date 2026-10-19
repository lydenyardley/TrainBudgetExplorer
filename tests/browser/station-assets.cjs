/**
 * ADR-0047: the station route fetches one stylesheet, and a fetch can fail.
 *
 * The page's own answer is in its own bytes, so the question is not whether the
 * page survives -- it does, because the rows travel inline -- but whether it is
 * left offering a switch that cannot change a palette it does not have. The
 * document is withheld on a second page in the same context, so the page under
 * test keeps the styling every other check reads.
 */
const { notExercised } = require("./harness.cjs");
async function checkWithoutTheScript(world) {
  const { page, url, check, notExercised, kind, context } = world;
  // T1: the station route fetches one script, and a fetch can fail. The rows
  // are listed by it, so unlike the stylesheet there is no page to preserve --
  // the table stays empty. What is proved instead is that the page says so:
  // the script tag's onerror reveals the note, rather than leaving an empty
  // table unexplained. The document is withheld on a second page in the same
  // context, so the page under test keeps the code every other check here is
  // driving.
  const WITHOUT_SCRIPT = [
    "a page whose script does not arrive says its list needs the code",
    "and the list it would have drawn stays empty",
    "and the controls that script opens arrive closed and out of the tab order",
  ];
  if (kind === "station" || kind === "chooser" || kind === "release") {
    const asset = kind === "station" ? "**/station-*.js" : "**/chooser-*.js";
    const bare = await context.newPage();
    await bare.route(asset, (route) =>
      route.fulfill({ status: 404, contentType: "text/plain", body: "no such script" })
    );
    await bare.goto(url);
    // The two folds the script owns: the refinements panel and the facet chips
    // behind the chip row's disclosure. A page whose code never ran cannot open
    // either, and a chip inside a fold nobody can open is a control a keyboard
    // reader must not be sent into -- which is what "no worse off without the
    // script" means when it is measured rather than argued.
    const without = await bare.evaluate(() => ({
      note: (document.getElementById("scriptNote") || {}).hidden,
      noteText: ((document.getElementById("scriptNote") || {}).textContent || "").trim(),
      rows: document.querySelectorAll("#rows tr[data-crs], #picks li").length,
      facetsFolded: (() => {
        const panel = document.getElementById("moreTypesPanel");
        return panel ? panel.hidden : null;
      })(),
      refinements: (() => {
        const filters = document.getElementById("moreFilters");
        return filters ? filters.dataset.open : null;
      })(),
    }));
    // The tab order, read by pressing Tab rather than by asking the DOM: a
    // control inside a closed fold must not be reached at all.
    const reached = [];
    for (let step = 0; step < 40; step += 1) {
      await bare.keyboard.press("Tab");
      reached.push(await bare.evaluate(() => {
        const el = document.activeElement;
        if (!el || el === document.body) return "body";
        return (el.closest("#moreTypesPanel") ? "folded:" : "reachable:") + (el.id || el.name || el.tagName);
      }));
      if (reached[reached.length - 1] === "body") break;
    }
    without.reached = reached;
    check(
      WITHOUT_SCRIPT[0],
      without.note === false && /did not load/.test(without.noteText),
      without.noteText || "(nothing said)"
    );
    check(
      WITHOUT_SCRIPT[1],
      without.rows === 0,
      `${without.rows} row(s) listed without the code`
    );
    // A route with no fold of its own (the chooser) answers null for both, and
    // is asked only what every route can answer: no folded control is reached.
    check(
      WITHOUT_SCRIPT[2],
      without.facetsFolded !== false &&
        (without.refinements === null || without.refinements === "false") &&
        !without.reached.some((entry) => entry.startsWith("folded:")),
      JSON.stringify({
        facetsFolded: without.facetsFolded,
        refinements: without.refinements,
        reached: without.reached.filter((entry) => entry.startsWith("folded:")),
      })
    );
    await bare.close();
  } else {
    for (const name of WITHOUT_SCRIPT) {
      check(name, notExercised("this route carries no fetched script, so no request can fail"));
    }
  }
}
module.exports = { checkWithoutTheStylesheet, checkWithoutTheScript };
async function checkWithoutTheStylesheet(world) {
  const { page, url, check, notExercised, kind, context } = world;
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
}
module.exports = { checkWithoutTheStylesheet, checkWithoutTheScript };
