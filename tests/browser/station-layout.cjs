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
      if (typeof STATE !== "undefined" && STATE.shortlist.length) {
        document.getElementById("shortlistClear").click();
      }
      setBudget(budgetCeiling());
      STATE.page = 1;
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
    // The stacked table, measured where the reader meets it: at 390px, on the
    // rows the page actually paints. The overflow checks in the fare section
    // ask whether the document is wider than the screen; these ask where the
    // text landed, which is the half a scrollbar cannot see. A cell measured at
    // 1px with its link painting 48px outside it passed every overflow check
    // (E14 of the 17 October 2026 audit).
    //
    // The design each check holds the page to: two tracks per cell, the label
    // in the first and every painted run of the value in the second; the value
    // track is what is left of the cell rather than a width of its own; a
    // number and the ticket link are one line each; and the headings are hidden
    // from sight rather than from a screen reader. Each of those was a string
    // assertion in tests/test_build_demo_page.py, and all five passed with the
    // defect in place (E16): a text assertion cannot see the interaction
    // between `td > *` and a bare text node.
    await page.setViewportSize({ width: 390, height: 720 });
    await open(facts.affordable);
    const stacked = await page.evaluate(() => {
      const rows = Array.from(document.querySelectorAll("#rows tr[data-crs]"));
      const root = parseFloat(getComputedStyle(document.documentElement).fontSize);
      const rectsOf = (node) => {
        const range = document.createRange();
        range.selectNodeContents(node);
        return Array.from(range.getClientRects()).map((rect) => ({
          left: rect.left,
          right: rect.right,
        }));
      };
      const cells = [];
      const numbers = [];
      for (const tr of rows) {
        for (const cell of tr.cells) {
          const style = getComputedStyle(cell);
          const box = cell.getBoundingClientRect();
          const tracks = (style.gridTemplateColumns || "")
            .split(" ")
            .map(parseFloat)
            .filter((size) => !Number.isNaN(size));
          const gap = parseFloat(style.columnGap) || 0;
          // The tracks are laid inside the cell's padding and border, and the
          // hold cell keeps a few pixels of padding from the desktop rule it
          // inherits, so the value track does not start at the cell's edge.
          const inset =
            (parseFloat(style.paddingLeft) || 0) + (parseFloat(style.borderLeftWidth) || 0);
          const start = box.left + inset + (tracks.length > 1 ? tracks[0] + gap : 0);
          const runs = cell.children.length ? Array.from(cell.children) : [cell];
          const measured = runs.map((run) => ({
            cls: String(run.className || run.tagName).slice(0, 30),
            lines: window.valueLines(run),
            rects: rectsOf(run),
          }));
          // Every line of text the cell paints, including the anonymous ones: a
          // bare text node in a grid container is an item with no element and
          // no class, so a detector that walked `children` could not see it --
          // which is how "NO" then "(" got under the label track with every
          // check green (C1 of the 17 October 2026 critique, E14 of the audit).
          const painted = rectsOf(cell);
          // Where each run starts against the value track, and whether any of
          // it paints outside the cell at all.
          const early = painted.filter((rect) => rect.left < start - 1);
          const outside = painted.filter(
            (rect) => rect.left < box.left - 1 || rect.right > box.right + 1
          );
          cells.push({
            label: cell.dataset.label || "",
            display: style.display,
            tracks: tracks.length,
            labelTrack: Math.round(tracks[0] || 0),
            valueTrack: Math.round(tracks[1] || 0),
            gap: Math.round(gap),
            // What the two tracks and the gap leave of the cell's own content
            // box: nothing, but for the sub-pixel rounding of three sizes.
            slack:
              Math.round(
                (box.width -
                  (parseFloat(style.paddingLeft) || 0) -
                  (parseFloat(style.paddingRight) || 0) -
                  (parseFloat(style.borderLeftWidth) || 0) -
                  (parseFloat(style.borderRightWidth) || 0) -
                  (tracks[0] + tracks[1] + gap)) *
                  10
              ) / 10,
            width: Math.round(box.width),
            row: Math.round(tr.getBoundingClientRect().width),
            early: early.length,
            worst: early.length ? Math.round(Math.min(...early.map((rect) => rect.left)) - start) : 0,
            outside: outside.length,
            painted: getComputedStyle(cell, "::before").content,
          });
          // The runs the design fixes at one line: every number, and the word
          // on the ticket link. `num missing` is the sentence a day with no
          // journey prints, which is prose in a number's column.
          for (const run of measured) {
            if (/^(num|price|changes-count|fare-kind|buy)$/.test(run.cls)) {
              numbers.push({ label: cell.dataset.label, cls: run.cls, lines: run.lines });
            }
          }
        }
      }
      const heads = Array.from(document.querySelectorAll("thead th"));
      const head = document.querySelector("thead");
      const headBox = head ? head.getBoundingClientRect() : null;
      const headStyle = head ? getComputedStyle(head) : null;
      return {
        rowCount: rows.length,
        root,
        cells,
        numbers,
        headers: heads.map((th) => ({
          label: th.textContent.trim(),
          display: getComputedStyle(th).display,
        })),
        // The headings are hidden by clipping the whole `thead` to a pixel, not
        // by taking each cell out of the layout, so the box to measure is the
        // one that carries the clip.
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
    const bad = (wanted) => stacked.cells.filter(wanted).slice(0, 4);
    const tracks = bad((cell) => cell.tracks !== 2 || Math.abs(cell.labelTrack - stacked.root * 5) > 1);
    check(
      "at 390px every cell stacks into a 5rem label track and a value track",
      stacked.cells.length === 0
        ? notExercised("this page shows no rows at a phone width")
        : tracks.length === 0,
      tracks.length
        ? JSON.stringify(tracks)
        : `${stacked.cells.length} cells, label track ${stacked.cells[0] ? stacked.cells[0].labelTrack : 0}px at a ${stacked.root}px root`
    );
    const narrow = bad((cell) => Math.abs(cell.slack) > 1.5);
    check(
      "and the value track is the rest of the cell rather than a width of its own",
      stacked.cells.length === 0
        ? notExercised("this page shows no rows at a phone width")
        : narrow.length === 0,
      narrow.length
        ? JSON.stringify(narrow.map((cell) => ({
            label: cell.label,
            width: cell.width,
            slack: cell.slack,
          })))
        : `${stacked.cells.length} cells measured`
    );
    const early = bad((cell) => cell.early > 0);
    check(
      "at 390px every value starts in the value track, never under its own label",
      stacked.cells.length === 0
        ? notExercised("this page shows no rows at a phone width")
        : early.length === 0,
      early.length
        ? JSON.stringify(early.map((cell) => ({ label: cell.label, runs: cell.early, worst: cell.worst + "px" })))
        : `${stacked.cells.length} cells measured`
    );
    const spilled = bad((cell) => cell.outside > 0 || cell.width < cell.row - 1);
    check(
      "at 390px no value paints outside the cell that holds it",
      stacked.cells.length === 0
        ? notExercised("this page shows no rows at a phone width")
        : spilled.length === 0,
      spilled.length
        ? JSON.stringify(spilled.map((cell) => ({ label: cell.label, width: cell.width, row: cell.row, outside: cell.outside })))
        : `${stacked.cells.length} cells measured, each the width of its row`
    );
    const wrappedNumbers = stacked.numbers.filter((run) => run.lines !== 1).slice(0, 6);
    check(
      "at 390px a price, a count, a time and the ticket link each paint one line",
      stacked.numbers.length === 0
        ? notExercised("this page shows no number and no ticket link to measure")
        : wrappedNumbers.length === 0,
      wrappedNumbers.length
        ? JSON.stringify(wrappedNumbers)
        : `${stacked.numbers.length} number runs and links measured`
    );
    const unlabelled = stacked.cells.filter((cell) => cell.painted !== `"${cell.label}"`).slice(0, 4);
    check(
      "at 390px each cell names itself where its column heading is hidden",
      stacked.cells.length === 0
        ? notExercised("this page shows no rows at a phone width")
        : unlabelled.length === 0,
      unlabelled.length
        ? JSON.stringify(unlabelled.map((cell) => ({ label: cell.label, painted: cell.painted })))
        : `${stacked.cells.length} cells paint their own label`
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
    await page.setViewportSize({ width: 1280, height: 800 });
}
module.exports = { measureTheLayout };
