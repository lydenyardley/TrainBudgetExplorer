/**
 * The layout: the space above the table, the filter panel's own shape, the
 * three rules a reader scrolling ninety rows relies on, and the width the
 * content asks for rather than the width it was given.
 *
 * Measured rather than asserted, because every one of them is a claim about
 * geometry that a template string cannot settle.
 */
const { cellsAreContentWide, notExercised } = require("./harness.cjs");
async function measureTheLayout(world) {
  const { page, check, notExercised, open, facts } = world;
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
    // The toggle and the panel it opens are one card, not a button with a
    // second card under it: the open toggle keeps the accent border and squares
    // off its bottom corners, and the panel takes the accent border on its
    // other three sides with the field colour and its own bottom margin taken
    // away, so the two join into one outlined shape.
    const joined = await page.evaluate(() => {
      const toggle = document.getElementById("moreFiltersToggle");
      const panel = document.getElementById("moreFiltersPanel");
      const t = getComputedStyle(toggle);
      const p = getComputedStyle(panel);
      const bar = getComputedStyle(document.querySelector(".filter-bar"));
      const accent = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim();
      return {
        toggleRadius: t.borderRadius,
        toggleBorder: t.borderTopColor,
        panelBorder: p.borderLeftColor,
        panelSides: p.borderLeftWidth + " " + p.borderTopWidth + " " + p.borderRightWidth + " " + p.borderBottomWidth,
        panelRadius: p.borderRadius,
        panelBackground: p.backgroundColor,
        panelMarginBottom: p.marginBottom,
        accent,
        quarterRem: parseFloat(getComputedStyle(document.documentElement).fontSize) * 0.45,
        barGap: bar.rowGap,
        barMargin: bar.marginTop,
        touching: Math.round(toggle.getBoundingClientRect().bottom - panel.getBoundingClientRect().top),
      };
    });
    check(
      "the open toggle and its panel join into one outlined shape",
      joined.toggleRadius === `${joined.quarterRem}px ${joined.quarterRem}px 0px 0px` &&
        joined.toggleBorder === joined.panelBorder &&
        joined.panelSides === "1px 0px 1px 1px" &&
        joined.panelRadius === `0px 0px ${joined.quarterRem}px ${joined.quarterRem}px` &&
        joined.panelBackground === "rgba(0, 0, 0, 0)" &&
        joined.panelMarginBottom === "0px" &&
        Math.abs(joined.touching) <= 1,
      JSON.stringify(joined)
    );
    check(
      "the filter bar carries a rem of space above it and a rem between its rows",
      joined.barGap === "16px" && joined.barMargin === "16px",
      `gap ${joined.barGap}, margin-top ${joined.barMargin}`
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
    // is of the results table; a page whose whole list fits on one page -- the
    // shape feed's builds, six and eight rows -- shows no nav#pagination, so
    // its margin is nothing to measure; and only a page tall enough to scroll
    // its table to the top of the screen can put its headings there, which the
    // dated shape builds now are (measured: the table starts 724px down a page
    // with 827px to scroll).
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
      const th = table.querySelector("thead th");
      // The declared rule, read whether or not the page is long enough to
      // scroll. A page whose table starts below the fold cannot scroll to it,
      // and the behaviour that scrolling proves is declared in exactly the same
      // place on every page.
      const style = getComputedStyle(th);
      const declared = {
        position: style.position,
        background: style.backgroundColor,
      };
      const tableTop = table.getBoundingClientRect().top + window.scrollY;
      const furthest = document.documentElement.scrollHeight - window.innerHeight;
      if (tableTop > furthest) {
        return { reachable: false, tableTop: Math.round(tableTop), furthest, ...declared };
      }
      window.scrollTo(0, tableTop);
      return {
        reachable: true,
        scrolled: window.scrollY,
        top: Math.round(th.getBoundingClientRect().top),
        ...declared,
      };
    });
    // Sticky and opaque on every page, because that is what the rule says.
    // Landed at the top of the viewport only where the page is long enough to
    // scroll the headings there, which a page that fits on one screen is not.
    check(
      "the column headings stay at the top of the screen once the table is scrolled",
      stuckHeadings.position === "sticky" &&
        !/rgba\(0, 0, 0, 0\)|transparent/.test(stuckHeadings.background) &&
        (!stuckHeadings.reachable ||
          (stuckHeadings.scrolled > 0 && stuckHeadings.top === 0)),
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
      // Whether there is more than one page at all, read off the page's own
      // count rather than off the nav's visibility. A list that fits on one
      // page stands the nav down on purpose (ADR-0043), and a check that
      // demanded a visible nav was demanding a control with nothing to do.
      const pages = (document.getElementById("pageStatus").textContent || "").match(/of (\d+)/);
      return {
        hidden: nav.hidden,
        pageCount: pages ? Number(pages[1]) : 1,
        pages: document.getElementById("pageStatus").textContent,
        margin: getComputedStyle(nav).marginTop,
        gap: Math.round(nav.getBoundingClientRect().top - table.getBoundingClientRect().bottom),
      };
    });
    check(
      "nav#pagination has room between it and the table",
      // One page means no nav to space; more than one means the nav shows and
      // the margin it declares is the gap it actually has.
      spacing.pageCount > 1
        ? spacing.hidden === false &&
          parseFloat(spacing.margin) > 0 &&
          spacing.gap >= parseFloat(spacing.margin) - 1
        : spacing.hidden === true,
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
}
module.exports = { measureTheLayout };
