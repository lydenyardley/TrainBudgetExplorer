"""N7: browser checks for the five fixes, measured rather than read.

Four of the five were found by looking at a page, so each gets a check that
reads the rendered result. The source assertions in `n6_tests.py` would all
still pass if the declarations were overridden or never applied; these would
not.

The narrow-row check is the one that matters most. Its claim is entirely about
what is painted -- a line at each cell's height, none of them meeting -- so it
asks the page which elements have a border-bottom and how wide they are, rather
than looking for a declaration.

The Time and Changes check compares the cell against the page's own payload,
which is the whole defect: the cell said no service about a destination the
same payload held a journey for.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from patch import patch  # noqa: E402

OLD = """    check("at 390px the ticket action is on-screen", mobile.onScreen, JSON.stringify(mobile));
"""

NEW = """    check("at 390px the ticket action is on-screen", mobile.onScreen, JSON.stringify(mobile));

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
        : cards.filter((c) => !c.fits).every((c) => /\\d/.test(c.label || "")),
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
"""

if __name__ == "__main__":
    patch("tests/browser_test.cjs", [(OLD, NEW)])