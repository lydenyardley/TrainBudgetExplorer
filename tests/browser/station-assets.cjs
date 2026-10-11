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
module.exports = { checkWithoutTheStylesheet };
