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
module.exports = { checkReleaseRoot };
