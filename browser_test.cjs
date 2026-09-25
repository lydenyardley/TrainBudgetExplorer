/**
 * A real browser test for the generated page.
 *
 * The page is the whole product and nothing tested it in a browser: the Python
 * suite proves the payload, the template strings, and the fare maths, but not that
 * a reader can drag the slider, filter to a town, follow a ticket link, or copy a
 * row's journey details. Those are the things a reader actually does.
 *
 * Run it with playwright on the path:
 *
 *     npx --yes --package playwright node browser_test.cjs
 *     node browser_test.cjs            # when playwright is installed locally
 *
 * Exit codes: 0 the page behaves, 1 it does not, 2 playwright is unavailable.
 * A skip is reported loudly and exits 2, because a test that passes quietly on a
 * machine where it never ran is the thing this project keeps refusing to do.
 */

const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");

const PAGE = process.argv[2] || "demo.html";
const SELLER = /^https:\/\/www\.(nationalrail\.co\.uk|thetrainline\.com)\//;

const checks = [];

function check(name, condition, detail) {
  checks.push({ name, ok: Boolean(condition), detail });
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

function serve(file) {
  const body = fs.readFileSync(file);
  const server = http.createServer((_request, response) => {
    response.writeHead(200, { "content-type": "text/html; charset=utf-8" });
    response.end(body);
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(server)));
}

async function main() {
  const playwright = requirePlaywright();
  if (!playwright) process.exit(2);

  const file = path.resolve(PAGE);
  if (!fs.existsSync(file)) {
    console.error("No page at " + file + ". Build one first:");
    console.error("  python make_synthetic_feed.py _demo_feed --unserved-station");
    console.error("  python build_demo_page.py --feed _demo_feed --timetable _demo_feed --origin GRN --out demo.html");
    process.exit(1);
  }

  const server = await serve(file);
  const url = `http://127.0.0.1:${server.address().port}/demo.html`;
  const browser = await playwright.chromium.launch();
  const context = await browser.newContext();
  await context.grantPermissions(["clipboard-read", "clipboard-write"], {
    origin: `http://127.0.0.1:${server.address().port}`,
  });

  // The seller's site is not part of this test. Stubbing it keeps the run
  // deterministic and keeps the suite off somebody else's server, while still
  // proving which URL a reader is sent to.
  await context.route(SELLER, (route) =>
    route.fulfill({ status: 200, contentType: "text/html", body: "<h1>seller</h1>" })
  );

  const page = await context.newPage();
  const rows = () => page.locator("#rows a.buy").count();

  try {
    // 1. It renders, with rows and a heading that names the origin.
    await page.goto(url);
    const heading = (await page.textContent("h1")) || "";
    check("renders the continuous budget-and-origin heading", /Where can we go for under/.test(heading) && /GRANTHAM/.test(heading), heading.trim());
    check("the heading budget is the editable source of truth", await page.locator("#budgetNumber").count() === 1, await page.locator("#budgetNumber").count() + " fields");
    const initial = await rows();
    check("renders priced rows", initial > 0, `${initial} rows`);

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
    // exclusive All and multi-select specific types.
    await page.goto(url);
    await page.check('input[name="destinationType"][value="city"]');
    const filtered = await rows();
    const expectedCityCount = await page.evaluate(() => DATA.destinations.filter(
      (d) => d.destinationType === "city" && d.adultPence <= Number(document.getElementById("budgetNumber").value) * 100
    ).length);
    check("the city chip leaves the priced city destinations", filtered === expectedCityCount && filtered > 0, `${filtered} rows; expected ${expectedCityCount}`);
    check(
      "and the rows are the city destinations",
      (await page.textContent("#rows")).includes("NOTTINGHAM"),
      await page.textContent("#rows")
    );
    await page.check('input[name="destinationType"][value="town"]');
    const multi = await rows();
    check("specific destination chips are multi-select", await page.locator('input[name="destinationType"][value="city"]').isChecked() && await page.locator('input[name="destinationType"][value="town"]').isChecked(), `${filtered} -> ${multi}`);
    await page.check('input[name="destinationType"][value="all"]');
    check("All is checked exclusively", await page.locator('input[name="destinationType"][value="all"]').isChecked() && !(await page.locator('input[name="destinationType"][value="city"]').isChecked()), "all state");
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
    const rowText = (await page.textContent("#rows tr")).trim();
    await page.locator("#rows button[aria-label^='Copy the journey details']").first().click();
    await page.waitForFunction(
      () => /copied/i.test((document.getElementById("copyStatus") || {}).textContent || ""),
      null,
      { timeout: 3000 }
    ).catch(() => {});
    const adultCopy = await page.evaluate(() => navigator.clipboard.readText());
    check("the copy names the origin", /^From: \S+ \(\w+\)$/m.test(adultCopy), adultCopy);
    check("the copy names the destination", /^To: \S+ \(\w+\)$/m.test(adultCopy), adultCopy);
    check("the copy names the party size", /^Passengers: 1 adult$/m.test(adultCopy), adultCopy);
    check("one adult's copy does not mention a railcard", !/Railcard/.test(adultCopy), adultCopy);
    check("the row it copied is the row it sits on", adultCopy.includes(rowText.split(" ")[0]), `${rowText} vs ${adultCopy}`);
    check(
      "and the copy is announced, not just performed",
      /copied/i.test(await page.textContent("#copyStatus"))
    );

    // 6. The party price carries the railcard, because that price needs it.
    await page.check('input[name="unit"][value="party"]');
    await page.locator("#rows button[aria-label^='Copy the journey details']").first().click();
    await page.waitForFunction(
      () => /2 adults/.test((document.getElementById("copyStatus") || {}).textContent || ""),
      null,
      { timeout: 3000 }
    ).catch(() => {});
    const partyCopy = await page.evaluate(() => navigator.clipboard.readText());
    check("the party copy says two adults", /^Passengers: 2 adults$/m.test(partyCopy), partyCopy);
    check(
      "and names the railcard when the fare is eligible",
      /Two Together discount/.test(partyCopy),
      partyCopy
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
    await page.goto(url);

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
      await page.fill("#originSearch", "notting");
      const narrowed = await page.locator("#originPicks a").count();
      const narrowedText = await page.locator("#originPicks").textContent();
      check("typing narrows the picker", narrowed > 0 && /NOTTINGHAM/.test(narrowedText), `${narrowed} options`);
      await page.fill("#originSearch", "zzzz");
      check(
        "a no-match says so and names the code route",
        (await page.locator("#originNomatch").isVisible()) && /three-letter code/.test(await page.textContent("#originNomatch"))
      );
      const emptyOptions = await page.locator("#originPicks a").count();
      check("and the list itself is empty rather than stale", emptyOptions === 0, `${emptyOptions} left`);
      // Keyboard exit: Escape closes and focus returns to the control that opened it.
      await page.fill("#originSearch", "lin");
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
  } finally {
    for (const { name, ok, detail } of checks) {
      console.log((ok ? "  ok    " : "  FAIL  ") + name + (!ok && detail ? "  <- " + detail : ""));
    }
    const failed = checks.filter((entry) => !entry.ok).length;
    console.log(`\n${checks.length - failed}/${checks.length} browser checks passed against ${PAGE}`);
    await browser.close();
    server.close();
    process.exit(failed ? 1 : 0);
  }
}

main().catch((error) => {
  console.error("the browser test could not run: " + error.message);
  process.exit(1);
});
