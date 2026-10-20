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
    // C3 of the 17 October 2026 critique: on a common laptop the answer started
    // below the fold. The fold is a budget, and this is it measured: at
    // 1366x768 -- with the demo's synthetic banner, which production does not
    // carry -- one whole destination row is on screen before any scrolling.
    // Measured on arrival, with the refinements folded, because that is the
    // state the finding was about: open() unfolds the panel and moves the table
    // 316px further down, so measuring after it tests the panel's height.
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto(world.url);
    const fold = await page.evaluate(() => {
      const first = document.querySelector("#rows tr[data-crs]");
      if (!first) return null;
      const box = first.getBoundingClientRect();
      return {
        top: Math.round(box.top + window.scrollY),
        height: Math.round(box.height),
        viewport: window.innerHeight,
      };
    });
    check(
      "at 1366x768 one whole destination row is above the fold",
      fold === null
        ? notExercised("this page shows no rows")
        : fold.top + fold.height <= fold.viewport,
      JSON.stringify(fold)
    );
    await page.setViewportSize({ width: 1280, height: 800 });
    await open(facts.affordable);
    // C4, C6 and C7 of the 17 October 2026 critique, each measured rather than
    // read off the stylesheet: the footer's measure, the two disclosures' drawn
    // marks, and which of the row's two actions carries the border.
    const chrome = await page.evaluate(() => {
      const footer = document.querySelector("footer");
      const style = getComputedStyle(footer);
      const sample = document.createElement("span");
      sample.style.cssText = "position:absolute;visibility:hidden;white-space:pre";
      sample.style.fontSize = style.fontSize;
      sample.style.fontFamily = style.fontFamily;
      sample.textContent = "0".repeat(20);
      document.body.append(sample);
      const ch = sample.getBoundingClientRect().width / 20;
      sample.remove();
      const box = (el) =>
        el ? { w: Math.round(el.getBoundingClientRect().width), h: Math.round(el.getBoundingClientRect().height) } : null;
      const buy = document.querySelector("#rows a.buy");
      const expand = document.querySelector("#rows .row-expand");
      return {
        footerWidth: Math.round(footer.getBoundingClientRect().width),
        measure: Math.ceil(ch * 80),
        summaries: [".link-terms", ".method"].map((selector) => {
          const summary = document.querySelector(selector + " summary");
          return summary
            ? { chevron: Boolean(summary.querySelector(".chevron")), text: summary.textContent.trim() }
            : null;
        }),
        buy: box(buy),
        buyBorder: buy ? getComputedStyle(buy).borderTopWidth : "",
        expand: box(expand),
        expandBorder: expand ? getComputedStyle(expand).borderTopWidth : "",
      };
    });
    check(
      "the footer is held to a readable measure rather than the whole page",
      chrome.footerWidth <= chrome.measure,
      `footer ${chrome.footerWidth}px, 80 characters ${chrome.measure}px`
    );
    check(
      "both disclosures wear the page's drawn mark",
      chrome.summaries.every((summary) => summary && summary.chevron && summary.text.length > 8),
      JSON.stringify(chrome.summaries)
    );
    check(
      "the ticket link is the bordered control and the expander the bare mark",
      Boolean(chrome.buy) && chrome.buy.h >= 44 && chrome.buyBorder !== "0px" &&
        Boolean(chrome.expand) && chrome.expand.h >= 44 && chrome.expandBorder === "0px",
      JSON.stringify({ buy: chrome.buy, buyBorder: chrome.buyBorder, expand: chrome.expand, expandBorder: chrome.expandBorder })
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
      if (typeof STATE !== "undefined" && STATE.shortlist.length) {
        document.getElementById("shortlistClear").click();
      }
      setBudget(budgetCeiling());
      STATE.page = 1;
      render();
    });
    // OV8 of the 19 October 2026 overdrive pass: the budget's re-render is the
    // page's one hot path -- the slider can fire several input events a frame --
    // so its cost is held to the input-to-paint budget rather than only described.
    // The read after render() is what forces layout, so the figure includes what
    // the browser has to lay out, not just the statements. The row count travels
    // with the figure, because the budget is about a list and the same page is
    // measured at whatever its own feed prices.
    const budgetCost = await page.evaluate(() => {
      const rows = document.querySelectorAll("#rows tr[data-crs]").length;
      const start = performance.now();
      render();
      document.getElementById("summary").getBoundingClientRect();
      return { ms: Math.round((performance.now() - start) * 10) / 10, rows };
    });
    check(
      "a budget change re-renders this page inside the input-to-paint budget",
      budgetCost.rows === 0
        ? notExercised("this page shows no rows to re-render")
        : budgetCost.ms < 50,
      `${budgetCost.ms}ms for ${budgetCost.rows} rows (budget 50ms)`
    );
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
    // The stacked table, measured where the reader meets it: at 390px, on the
    // rows the page actually paints. A phone row was a label track and a value
    // track per cell -- six lines, 275px, a page of twenty destinations in
    // 5,500px (C13/D8 of the 17 October 2026 critique). It is two lines now,
    // and these are the claims that make it one: the row's height, the line
    // each fact lands on, and the fact that no value paints outside the cell
    // that holds it.
    await page.setViewportSize({ width: 390, height: 720 });
    await open(facts.affordable);
    const stacked = await page.evaluate(() => {
      const rows = Array.from(document.querySelectorAll("#rows tr[data-crs]"));
      const rect = (node) => {
        const box = node.getBoundingClientRect();
        return { top: Math.round(box.top), bottom: Math.round(box.bottom),
                 left: box.left, right: box.right };
      };
      const cellOf = (tr, label) => tr.querySelector('td[data-label="' + label + '"]');
      const measured = rows.map((tr) => {
        const cells = Array.from(tr.cells);
        const station = cellOf(tr, "Station");
        const price = cellOf(tr, "Price");
        const time = cellOf(tr, "Time");
        const tickets = cellOf(tr, "Tickets");
        // Every painted line of a cell, including the anonymous text nodes: a
        // long name wraps inside its own cell rather than widening the row.
        const outside = [];
        for (const cell of cells) {
          const box = cell.getBoundingClientRect();
          const range = document.createRange();
          range.selectNodeContents(cell);
          for (const run of range.getClientRects()) {
            if (run.width === 0) continue;
            if (run.left < box.left - 1 || run.right > box.right + 1) {
              outside.push((cell.dataset.label || cell.tagName).slice(0, 24));
            }
          }
        }
        return {
          height: Math.round(tr.getBoundingClientRect().height),
          stationTop: station ? rect(station).top : 0,
          priceTop: price ? rect(price).top : 0,
          timeTop: time ? rect(time).top : null,
          ticketTop: tickets ? rect(tickets).top : 0,
          outside: outside.length,
          width: Math.round(tr.getBoundingClientRect().width),
          cells: cells.length,
          // What the stacked row says the fare is (S4 of the 19 October 2026
          // critique). Read off the cell the reader sees rather than off the
          // payload, so a cell that lost its noun is what fails.
          fareWord: ((cellOf(tr, "Fare type") || {}).textContent || "").trim(),
          // A row that names the station it changes at carries two lines in
          // that cell by design (`.changes`, row-cells.js). Its second line is
          // the tightest one on the page, and the line check below says so.
          via: Boolean(tr.querySelector("td.changes")),
        };
      });
      const heads = Array.from(document.querySelectorAll("thead th"));
      const head = document.querySelector("thead");
      const headBox = head ? head.getBoundingClientRect() : null;
      const headStyle = head ? getComputedStyle(head) : null;
      return {
        rowCount: rows.length,
        rows: measured,
        heights: measured.map((row) => row.height).sort((a, b) => a - b),
        headers: heads.map((th) => ({
          label: th.textContent.trim(),
          display: getComputedStyle(th).display,
        })),
        head: headBox
          ? {
              width: Math.round(headBox.width * 10) / 10,
              height: Math.round(headBox.height * 10) / 10,
              position: headStyle.position,
              overflow: headStyle.overflow,
            }
          : null,
      };
    });
    const median = stacked.heights.length
      ? stacked.heights[Math.floor(stacked.heights.length / 2)]
      : 0;
    check(
      "at 390px the typical row is two lines rather than six",
      // 120 rather than the audit's 90: the shortlist checkbox and the ticket
      // action are both 44px targets, and each one sets the height of a line.
      // Measured on this page, a row is 111px -- twenty of them in 2,220px,
      // against the 5,500px the six-line row cost.
      stacked.rows.length === 0
        ? notExercised("this page shows no rows at a phone width")
        : median <= 120,
      `${stacked.rows.length} rows, median ${median}px, tallest ${stacked.heights[stacked.heights.length - 1] || 0}px`
    );
    // A row that carries a via note is the one row the second line cannot hold
    // in four facts: measured at 390px on the demo page, such a row needs 397px
    // of content in 366 -- the ticket takes a third line and no shorter
    // spelling of the facts buys it back. The promise it keeps instead is the
    // one a reader needs: the time on the second line, and the ticket with the
    // facts it buys. Every other row is held to the full claim, and a page whose
    // rows all carry a via note reports not exercised rather than passing on
    // rows that were never measured.
    const offLine = stacked.rows
      .filter(
        (row) =>
          row.stationTop === 0 ||
          Math.abs(row.priceTop - row.stationTop) > 2 ||
          (row.timeTop !== null && row.timeTop <= row.stationTop) ||
          (row.timeTop !== null && !row.via && Math.abs(row.ticketTop - row.timeTop) > 4)
      )
      .slice(0, 4);
    const plain = stacked.rows.filter((row) => !row.via).length;
    check(
      "at 390px the place and its price share the first line, the time and the ticket the second",
      stacked.rows.length === 0
        ? notExercised("this page shows no rows at a phone width")
        : plain === 0
        ? notExercised(`every row names a change station (${stacked.rows.length})`)
        : offLine.length === 0,
      offLine.length
        ? JSON.stringify(offLine)
        : `${stacked.rows.length} rows measured, ${stacked.rows.length - plain} with a via note`
    );
    // S4 of the 19 October 2026 critique: the stacked layout clips the `<thead>`
    // for assistive technology, so nothing on the screen says that
    // "Restricted" is the fare rather than a third fact about the journey. The
    // cell carries its own noun now, and "Two tickets" already is one.
    const wordless = stacked.rows
      .filter((row) => row.fareWord && !/^(Advance|Restricted|Regular) fare$|^Two tickets$/.test(row.fareWord))
      .slice(0, 4);
    check(
      "at 390px the fare cell says what kind of thing it names",
      stacked.rows.length === 0
        ? notExercised("this page shows no rows at a phone width")
        // Every row has to carry one of the four phrases. A page that painted
        // no fare word at all is a broken cell, not a page with nothing to say.
        : wordless.length === 0 && stacked.rows.every((row) => row.fareWord),
      wordless.length
        ? JSON.stringify(wordless)
        : `${stacked.rows.length} rows: ${Array.from(new Set(stacked.rows.map((row) => row.fareWord))).join(", ")}`
    );
    const spilled = stacked.rows.filter((row) => row.outside > 0).slice(0, 4);
    check(
      "at 390px no value paints outside the cell that holds it",
      stacked.rows.length === 0
        ? notExercised("this page shows no rows at a phone width")
        : spilled.length === 0,
      spilled.length ? JSON.stringify(spilled) : `${stacked.rows.length} rows measured`
    );
    // The headings are hidden from sight rather than from a screen reader: the
    // `thead` is a clipped pixel, and the cells inside it are still table cells
    // rather than `display: none`, which would take the headings out of the
    // accessibility tree with them and leave a phone reader with no place the
    // column names are written.
    const head = stacked.head;
    check(
      "at 390px the column headings are hidden from sight and not from a screen reader",
      !head || stacked.headers.length === 0
        ? notExercised("this page shows no column headings")
        : head.width <= 1 && head.height <= 1 && head.position === "absolute" &&
          /hidden/.test(head.overflow) &&
          stacked.headers.every((th) => th.display !== "none"),
      JSON.stringify({ head, headers: stacked.headers.slice(0, 3) })
    );
    // DL5 and OV9 of the 19 October 2026 passes: the two surfaces that appear in
    // response to a reader -- a row's panel and the shortlist dock -- carry one
    // 120ms reveal, and a reader who asked for less motion gets none of it. The
    // panel's content is readable and focusable from its first frame either way;
    // this measures the motion, not the content.
    //
    // The positive half comes first, or the reduced-motion check below would
    // pass on a page with no motion rule at all: "none" is what a missing
    // animation also reports.
    await page.setViewportSize({ width: 1280, height: 800 });
    const moving = await page.evaluate(() => {
      const toggle = document.querySelector("#rows tr[data-crs] .row-expand")
        || document.querySelector("#rows tr[data-crs] .toggle");
      if (!toggle) return null;
      if (toggle.getAttribute("aria-expanded") === "true") toggle.click();
      toggle.click();
      const detail = document.querySelector("tr.detail");
      const dock = document.querySelector(".shortlist-dock-head");
      const read = {
        opened: Boolean(detail),
        detail: detail ? getComputedStyle(detail).animationName : "",
        dock: dock ? getComputedStyle(dock).animationName : null,
      };
      // Put the row back as it was found, so the block below opens it itself.
      if (toggle.getAttribute("aria-expanded") === "true") toggle.click();
      return read;
    });
    check(
      "and with motion allowed the panel arrives in one reveal",
      moving === null
        ? notExercised("this page shows no row to open")
        : moving.opened && moving.detail === "reveal-surface" &&
          (moving.dock === null || moving.dock === "reveal-surface"),
      JSON.stringify(moving)
    );
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.setViewportSize({ width: 1280, height: 800 });
    const quiet = await page.evaluate(() => {
      const toggle = document.querySelector("#rows tr[data-crs] .row-expand")
        || document.querySelector("#rows tr[data-crs] .toggle");
      if (!toggle) return null;
      toggle.click();
      const detail = document.querySelector("tr.detail");
      // The dock's box stays at the foot; what it holds is what animates.
      const dock = document.querySelector(".shortlist-dock-head");
      return {
        opened: Boolean(detail),
        detail: detail ? getComputedStyle(detail).animationName : "",
        dock: dock ? getComputedStyle(dock).animationName : "",
      };
    });
    check(
      "a reader who asked for less motion gets no reveal",
      quiet === null
        ? notExercised("this page shows no row to open")
        : quiet.opened && quiet.detail === "none" && quiet.dock === "none",
      JSON.stringify(quiet)
    );
    // DS6 of the 19 October 2026 distill pass: a census of the sizes a reader
    // actually meets, taken from the rendered page with a row open (so the
    // panel's prose is in it) and with the display heading and drawn glyphs
    // left out. Five steps are the hierarchy; six near-neighbours were drift.
    const sizes = await page.evaluate(() => {
      const seen = new Map();
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) {
        const node = walker.currentNode;
        if (!node.nodeValue.trim()) continue;
        const el = node.parentElement;
        if (!el || !el.getBoundingClientRect().height) continue;
        if (el.closest("h1") || el.closest('[aria-hidden="true"]') || el.closest(".sr-only")) continue;
        const size = getComputedStyle(el).fontSize;
        seen.set(size, (seen.get(size) || 0) + 1);
      }
      return Array.from(seen.keys()).sort((a, b) => parseFloat(a) - parseFloat(b));
    });
    check(
      "and the page keeps five type sizes below the display heading",
      sizes.length <= 5,
      sizes.join(", ")
    );
    await page.emulateMedia({ reducedMotion: null });
    await page.setViewportSize({ width: 1280, height: 800 });
}
module.exports = { measureTheLayout };
