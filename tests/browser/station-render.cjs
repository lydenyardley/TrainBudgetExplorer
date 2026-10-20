/**
 * 1. The page renders: rows, a heading that names the origin, a budget field
 * that is the editable source of truth, a count line that agrees with its own
 * arithmetic, an opening sentence that is true of this build, and prices that
 * paint on one line each.
 *
 * What it reads out of the payload -- the origin, the affordable budget and
 * the row count -- is left on the world object, because every section below
 * starts from the budget this one found.
 */
const { notExercised } = require("./harness.cjs");
async function renderThePage(world) {
  const { page, check, notExercised, open, rows } = world;
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
    // Left for the sections after this one, which all start from the budget
    // this section found affordable.
    world.facts = facts;
    const heading = (await page.textContent("h1")) || "";
    check(
      "renders the continuous budget-and-origin heading",
      // C21: the filter includes a fare exactly at the budget (price <= cap),
      // so the sentence says "up to". "Under" would describe a page that
      // excludes a row it actually shows.
      /Train fares/.test(heading) && /up to/.test(heading) && heading.includes(facts.origin.toUpperCase()),
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
    // Both amounts are ones the field can hold. The field clamps to the
    // page's ceiling, so on a page whose dearest fare is £7 "126" became "7"
    // and the check compared one digit with one digit.
    const ceiling = await page.locator("#budget").evaluate((el) => Number(el.max));
    if (String(ceiling).length > 1) {
      const budgetWidthAt1 = await widthAt("1");
      const budgetWidthAtTop = await widthAt(String(ceiling));
      check("the heading budget width follows its character count", budgetWidthAt1 < budgetWidthAtTop, `${budgetWidthAt1} / ${budgetWidthAtTop} (1 / ${ceiling})`);
    } else {
      check("the heading budget width follows its character count", notExercised(`this page's budget stops at £${ceiling}, one digit`));
    }
    await page.locator(".budget-prefix").click();
    await page.keyboard.type("7");
    const replacedAmount = (await page.inputValue("#budgetNumber")).trim();
    check("clicking the £ selects the whole editable amount", replacedAmount === "7", replacedAmount);
    await page.fill("#budgetNumber", String(facts.affordable));
    const initial = await rows();
    world.initial = initial;
    check("renders priced rows", initial > 0, `${initial} rows; ${facts.destinations} destinations in the feed`);
    // Q4: the list that opens is the cheapest fare of any ticket type to each
    // destination, and the fare it chose is the fare the row names. The
    // expectation is composed from the payload by the reader above; the page's
    // own composition is compared against it rather than used as the answer.
    const headline = await page.evaluate(() => {
      const cheapest = window.cheapestOfEveryList();
      const shown = Array.from(document.querySelectorAll("#rows tr[data-crs]")).map((row) => {
        const wanted = cheapest.get(row.dataset.crs) || null;
        // The row names its fare in one of the reader's own three words, and
        // the word has to be the one this row's fare earns. The code the feed
        // used is one disclosure away and no longer on the row at all.
        const row1 = activeDestinations().find((d) => d.crs === row.dataset.crs) || {};
        return {
          crs: row.dataset.crs,
          price: (row.querySelector("td.num .price") || {}).textContent || "",
          wanted: wanted
            ? {
              price: String(
                (document.querySelector('input[name="unit"]:checked').value === "party"
                  ? wanted.partyPence : wanted.adultPence) / 100
              ),
              code: wanted.ticket || "",
            }
            : null,
          // S4 of the 19 October 2026 critique: the cell carries its noun, so
          // the word a reader sees is a fare type rather than a third fact
          // about the journey. The expectation is the page's own three phrases,
          // not a looser match that would accept both shapes.
          code: row1.isAdvance ? "Advance fare" : row1.restrictionCode ? "Restricted fare" : "Regular fare",
          word: (row.querySelector(".fare-kind") || {}).textContent || "",
        };
      });
      // The mix among the rows on screen, kept for the second half of the check:
      // every kind of fare a reader can see must be one the line names.
      const kinds = {};
      for (const crs of shown.map((row) => row.crs)) {
        const wanted = cheapest.get(crs);
        if (!wanted) continue;
        const word = wanted.quality === "outbound single"
          ? "single" : wanted.quality === "unrestricted Anytime Day Return" ? "Anytime Day Return" : "return";
        kinds[word] = (kinds[word] || 0) + 1;
      }
      // The counts the line states for itself. It describes every destination
      // the budget admits, which is not the twenty rows on screen and not the
      // page's private list either -- `available` is local to render(). So the
      // line is asked to agree with itself, which is the guarantee that matters
      // and the only one that can be read off it.
      const line = document.getElementById("summary").textContent;
      const total = Number((/([0-9,]+) destinations?/.exec(line) || [0, "0"])[1].replace(/,/g, ""));
      const named = [];
      for (const m of line.matchAll(/([0-9,]+) (Anytime Day Returns?|singles?|returns?)\b/g)) {
        named.push({ word: m[2], count: Number(m[1].replace(/,/g, "")) });
      }
      return {
        mode: document.querySelector('input[name="ticketMode"]:checked').value,
        expected: cheapest.size,
        pageCount: typeof cheapestDestinations === "function" ? cheapestDestinations().length : null,
        shown,
        kinds,
        total,
        named,
        summary: document.getElementById("summary").textContent,
      };
    });
    const amount = (text) => Number(String(text).replace(/[^0-9.]/g, ""));
    check(
      "the page opens on the cheapest fare of any ticket type",
      headline.expected
        ? headline.mode === "cheapest" &&
          headline.pageCount === headline.expected &&
          headline.shown.length > 0 &&
          headline.shown.every(
            (row) => row.wanted && amount(row.price) === amount(row.wanted.price) && row.code === row.word
          )
        : notExercised("this page's feed prices nothing"),
      JSON.stringify({ mode: headline.mode, expected: headline.expected, pageCount: headline.pageCount, first: headline.shown[0] || null })
    );
    check(
      "one row per destination, whatever the list is priced from",
      headline.expected
        ? new Set(headline.shown.map((row) => row.crs)).size === headline.shown.length
        : notExercised("this page's feed prices nothing"),
      JSON.stringify(headline.shown.map((row) => row.crs))
    );
    const kinds = Object.entries(headline.kinds);
    // Every kind of fare among the rows on screen is named by the line, and the
    // line's own counts add up to the total it states. The second half is the
    // one that cannot be satisfied by a coincidence of a small fixture: a line
    // that says "266 destinations ... 2 singles, 264 returns" is either right
    // about its own arithmetic or it is not.
    const namedSum = headline.named.reduce((total, entry) => total + entry.count, 0);
    const unseen = kinds.filter(([word]) => !headline.named.some(
      (entry) => entry.word.replace(/s$/, "").toLowerCase() === word.toLowerCase()
    ));
    check(
      "and the count line names the mix of ticket types it is showing",
      headline.shown.length === 0
        ? notExercised("this page shows no row to count")
        : unseen.length === 0 &&
          headline.named.length > 0 &&
          namedSum === headline.total,
      JSON.stringify({ kinds: headline.kinds, total: headline.total, named: headline.named, summary: headline.summary })
    );
    const partyBasis = await page.evaluate(() => {
      applyState({ unit: "party" });
      render();
      const summary = document.getElementById("summary").textContent;
      applyState({ unit: "adult" });
      render();
      return summary;
    });
    check(
      "and the party figure says it is two of the fare each row names",
      /two of the fare each row names/.test(partyBasis),
      partyBasis
    );
    // C04: the opening sentence has to be true of this build. A page with no
    // timetable must not promise a journey time, and a page with one should
    // say what the times are; both are read off the payload, not off a
    // hardcoded sentence.
    const opening = await page.evaluate(() => ({
      // D1 of the 17 October 2026 critique: the paragraph that promised a time
      // is gone, so what is asserted is that the page no longer makes a promise
      // its columns have to keep.
      promises: /fastest time/i.test(document.body.textContent || ""),
      firstUse: (document.getElementById("firstUse") || {}).textContent || "",
      heading: (document.getElementById("pageHeading") || {}).getAttribute("aria-label") || "",
      title: document.title,
      hasJourneys: DATA.hasJourneys,
      timeColumns: document.querySelectorAll("thead th[data-label='Time']").length,
      // The results table only. The shortlist dock is a second table with its
      // own headings, and it keeps a Time column on a prices-only build on
      // purpose: a shortlisted row names the journey time it was shortlisted
      // for, and that column standing down is the dock's own business. Asking
      // every th on the page made this read the dock's Time as the results
      // table promising a time the page had just said it had no source for.
      headers: Array.from(
        document.querySelectorAll("table:has(#rows) thead th")
      ).map((th) => th.textContent),
    }));
    check(
      "the page promises no time it cannot show",
      // The heading states the budget and the station, the count line states
      // the destinations, and the columns state time and changes. Nothing above
      // the table makes a claim about a journey any more, so there is no
      // sentence left to go stale on a prices-only build.
      opening.promises === false && opening.firstUse.length > 0,
      JSON.stringify(opening)
    );
    check(
      "the times columns exist exactly when this build has times",
      opening.hasJourneys
        ? opening.headers.includes("Time") && opening.headers.includes("Changes")
        : !opening.headers.includes("Time") && !opening.headers.includes("Changes"),
      opening.headers.join(" ")
    );
    check(
      "the heading's own name is the whole sentence, and the same one as the tab title",
      // Items 9 and 13, 14 October 2026: the heading holds the budget field and
      // the station control, so a name computed from its contents was those
      // controls run together in reading order. It is written as the sentence
      // the title already carries, on every render.
      opening.heading === opening.title && /^Train fares up to £/.test(opening.heading),
      JSON.stringify({ heading: opening.heading, title: opening.title })
    );
    // Finding, 29 September 2026: on the real page the Price column measured
    // 56px and 13 of the first 20 prices painted as two lines -- £10.10 read as
    // "£10.1" over "0" -- while CHANGES wrapped mid-word in a 72px column. A
    // wrapped price is not a cramped column, it is a different number, and the
    // header word was deciding the width. So this is measured as painted line
    // boxes rather than read off the CSS: getClientRects() over a run of text
    // returns one rect per line, and the distinct tops are the lines.
    //
    // A cell prints one or more runs -- a station's name and its site proof, a
    // change count and the station it changes at, the ticket link and the
    // chevron -- and each run is what is measured. The deliberate second line
    // is a run of its own: the station a journey changes at sits under the
    // count on purpose (ADR-0045), so counting a whole cell's lines as a wrap
    // was the check measuring the design. That is E15 of the 17 October 2026
    // audit, where the detector existed and left the station and tickets cells
    // out rather than learning to read them as runs.
    const measure = await page.evaluate(() => {
      const prose = new Set(["site-proof", "interchange", "split"]);
      const runsOf = (el) => (el.children.length ? Array.from(el.children) : [el]);
      const cells = [
        ...document.querySelectorAll("thead th"),
        ...document.querySelectorAll("#rows td"),
      ];
      let runs = 0;
      const wrapped = [];
      for (const el of cells) {
        if (!el.getBoundingClientRect().height) continue;
        for (const run of runsOf(el)) {
          // A site proof, an interchange and a split note are prose and wrap
          // as prose does; every other run is one fact in one column.
          if (Array.from(run.classList).some((name) => prose.has(name))) continue;
          runs += 1;
          if (window.valueLines(run) > 1) {
            wrapped.push({
              cell: el.dataset.label || el.tagName.toLowerCase(),
              text: run.textContent.trim().slice(0, 40),
              lines: window.valueLines(run),
              width: Math.round(run.getBoundingClientRect().width),
            });
          }
        }
      }
      // The second half of the same finding: the count line sat 205px above the
      // first row, with six provenance paragraphs between them, so the first
      // fare was below the fold on a laptop. Measured as the distance itself,
      // because how tall the heading and the intro are is a fact about the
      // build and not about this.
      const summary = document.getElementById("summary");
      const table = document.querySelector("table");
      const first = document.querySelector("#rows tr:not(.detail)");
      const box = (el) => (el ? el.getBoundingClientRect() : null);
      const isBetween = (el, from, to) =>
        Boolean(
          from.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING &&
            el.compareDocumentPosition(to) & Node.DOCUMENT_POSITION_FOLLOWING
        );
      const between = (from) =>
        Array.from(document.querySelectorAll("main > *"))
          .filter((el) => isBetween(el, from, table))
          .map((el) => el.id || el.tagName.toLowerCase());
      return {
        cells: cells.length,
        runs,
        wrapped,
        priceWidth: Math.round((box(document.querySelector("#rows td.num")) || { width: 0 }).width),
        countToTable: box(summary) && box(table) ? Math.round(box(table).top - box(summary).bottom) : null,
        countToFirstRow:
          box(summary) && box(first) ? Math.round(box(first).top - box(summary).top) : null,
        afterCount: summary ? between(summary) : [],
        afterProvenance: document.getElementById("freshness") ? between(document.getElementById("freshness")) : [],
        tabular: document.querySelector("#rows td.num")
          ? getComputedStyle(document.querySelector("#rows td.num")).fontVariantNumeric
          : "",
      };
    });
    check(
      "no price, number, name or column heading wraps onto a second line",
      measure.cells === 0
        ? notExercised("this page has no results table to measure")
        : measure.wrapped.length === 0,
      measure.wrapped.length
        ? JSON.stringify(measure.wrapped.slice(0, 6))
        : `${measure.runs} runs in ${measure.cells} cells measured, price column ${measure.priceWidth}px, tabular-nums ${measure.tabular}`
    );
    check(
      "the count line sits on the table it counts",
      measure.countToTable === null
        ? notExercised("this page shows no count and no table")
        // The budget's next-place line (DL1 of the 19 October 2026 delight
        // pass) sits between the count and the table on purpose: it is the
        // count's own answer in places. It is empty and collapsed at rest, so
        // the count still sits on its table; a third element would be a paragraph
        // between the answer and the list it answers for.
        : measure.countToTable <= 12 &&
          measure.afterCount.every((id) => id === "budgetNext"),
      `count to table ${measure.countToTable}px; between: ${measure.afterCount.join(", ") || "nothing"}`
    );
    check(
      "and nothing but the count and the fold stands between the provenance and the first row",
      measure.countToFirstRow === null
        ? notExercised("this page shows no count and no first row")
        : measure.countToFirstRow <= 100 &&
          measure.afterProvenance.every((id) =>
            ["dateNote", "linkTerms", "summary", "budgetNext"].includes(id)
          ),
      `count to first row ${measure.countToFirstRow}px; after the provenance: ${measure.afterProvenance.join(", ") || "nothing"}`
    );
    // C03, as ADR-0040 leaves it: what the ticket action costs, and what the
    // link earns, are still in front of the first ticket action -- and the line
    // a reader meets before the table is the fold's own summary, so that is
    // what is measured as rendered. Only the wording waits behind it: those two
    // paragraphs plus the build line were 57px of the 205px between the count
    // and the table on the real page (finding, 29 September 2026), which is
    // what put the first fare below the fold on a laptop.
    //
    // Measuring the notes' position alone would pass with them folded and
    // unread, which is the defect this check exists for -- so each note has to
    // be inside the fold, and the rendered line has to name what is in it.
    const handoff = await page.evaluate(() => {
      const terms = document.getElementById("linkTerms");
      const note = (selector) => {
        const el = document.querySelector(selector);
        if (!el) return null;
        return {
          text: el.textContent.trim(),
          inTerms: Boolean(el.closest("#linkTerms")),
          inMethod: Boolean(el.closest(".method")),
          hidden: el.hidden,
        };
      };
      const summary = terms ? terms.querySelector("summary") : null;
      const box = summary ? summary.getBoundingClientRect() : null;
      return {
        linkNote: note("#linkNote"),
        disclosure: note("#disclosure"),
        wanted: {
          linkNote: Boolean(DATA.linkNote),
          disclosure: Boolean(DATA.tracked),
          build: Boolean(DATA.builtAt),
        },
        summary: summary
          ? { text: summary.textContent.trim(), rendered: Boolean(box.width && box.height) }
          : null,
        beforeTable: Boolean(
          terms &&
            terms.compareDocumentPosition(document.querySelector("table")) &
              Node.DOCUMENT_POSITION_FOLLOWING
        ),
        inMethod: Boolean(terms && terms.closest(".method")),
      };
    });
    for (const key of ["linkNote", "disclosure"]) {
      // Only a page that has the note is checked for it: a page whose links
      // fill the journey in has no handoff to explain, and an untracked page
      // has no commission to disclose.
      if (!handoff.wanted[key]) continue;
      const found = handoff[key];
      check(
        `${key === "linkNote" ? "the seller handoff" : "the commission disclosure"} is stated above the table`,
        Boolean(found) && found.text.length > 20 && found.inTerms && !found.inMethod,
        JSON.stringify(found)
      );
    }
    check(
      "the fold above the first ticket action says what it holds",
      !(handoff.wanted.linkNote || handoff.wanted.disclosure || handoff.wanted.build)
        ? notExercised("this page has no link terms and no build metadata to fold")
        : Boolean(handoff.summary) &&
            handoff.summary.rendered &&
            handoff.summary.text.length > 10 &&
            handoff.beforeTable &&
            !handoff.inMethod &&
            (!handoff.wanted.disclosure || /paid|earn|commission/i.test(handoff.summary.text)),
      `${JSON.stringify(handoff.summary)} beforeTable=${handoff.beforeTable} inMethod=${handoff.inMethod}`
    );
    // Item 44 of the 14 October 2026 clarity audit, answered "the glossary
    // only": the trade words the lines above quote are defined once, inside
    // the method disclosure, and nowhere else. The definitions are written by
    // the route's shared script rather than shipped in each page's markup, so
    // the check reads what a reader sees with the accordion closed and open.
    const words = await page.evaluate(() => {
      const list = document.getElementById("wordList");
      const details = list && list.closest("details");
      const inMethod = Boolean(list && list.closest(".method"));
      // D7 of the 17 October 2026 critique: one disclosure for the page's
      // trust content, not a second one nested inside the first.
      const nested = Boolean(list && list.closest("details.words"));
      const terms = list ? Array.from(list.querySelectorAll("dt")).map((dt) => dt.textContent.trim()) : [];
      const meanings = list ? Array.from(list.querySelectorAll("dd")).map((dd) => dd.textContent.trim()) : [];
      // The page's own text with the glossary taken out of it. A definition
      // counted as its own quotation would make this check pass for a word the
      // page never says, which is the shape this suite exists to refuse.
      const copy = document.body.cloneNode(true);
      const copyOfList = copy.querySelector("#wordList");
      if (copyOfList) copyOfList.remove();
      const outside = copy.textContent;
      // NRE arrives with the acknowledgement, and a build without notices has
      // none, so that term is held to the page only when the credit is there.
      const credited = outside.includes("National Rail Enquiries");
      return {
        inMethod,
        nested,
        summary: details ? details.querySelector("summary").textContent.trim() : null,
        terms,
        // Every definition says something: a term with an empty or one-word
        // gloss is a term the page still has not explained.
        defined: terms.length > 0 && meanings.length === terms.length && meanings.every((m) => m.split(/\s+/).length >= 6),
        // The words it defines are the words the page actually quotes. "Flow"
        // is met lower-cased in the feed's own count.
        quoted:
          [/ITX/, /DTD/, /\bRR\b/, /flow/i].every((pattern) => pattern.test(outside)) &&
          (!credited || /\bNRE\b/.test(outside)),
        credited,
      };
    });
    check(
      "the trade words the page quotes are defined together, in the method disclosure",
      words.inMethod && !words.nested && words.defined && words.quoted && words.terms.length >= 5,
      JSON.stringify(words)
    );
}
module.exports = { renderThePage };
