/**
 * The fare detail: at a phone width the ticket action stays on screen, the
 * address carries the search, the railcard drawer explains the number, and the
 * feed's own condition, its validity, its coverage line and its freshness are
 * each judged against the build rather than against a sentence written here.
 *
 * The rest of this panel is the one thing a page of prices owes a reader: a
 * claim about how old the numbers are, next to the numbers.
 */
const { daysSince, notExercised } = require("./harness.cjs");
async function checkTheFareDetails(world) {
  const { page, check, notExercised, open, facts, pair } = world;
    // 7. At a phone width the ticket action is on-screen, without horizontal
    // scroll (ADR-0019's blocker). Measured, not assumed.
    await page.setViewportSize({ width: 390, height: 720 });
    const mobile = await page.evaluate(() => {
      const html = document.documentElement;
      const overflow = Math.max(html.scrollWidth, document.body.scrollWidth) - window.innerWidth;
      const cell = document.querySelector("#rows td:last-child").getBoundingClientRect();
      // What is sticking out, named: a bare pixel count sends whoever reads a
      // red run back to the stylesheet to guess which element it was.
      const edge = html.clientWidth;
      const wide = Array.from(document.querySelectorAll("body *"))
        .map((el) => ({ el, r: el.getBoundingClientRect() }))
        .filter((entry) => entry.r.right > edge + 1)
        .map((entry) => ({
          tag: entry.el.tagName.toLowerCase(),
          id: entry.el.id,
          cls: String(entry.el.className).slice(0, 40),
          right: Math.round(entry.r.right),
          width: Math.round(entry.r.width),
        }))
        .slice(0, 5);
      return { overflow, onScreen: cell.right <= window.innerWidth && cell.left >= 0, wide };
    });
    check(
      "at 390px nothing overflows horizontally",
      mobile.overflow <= 0,
      `${mobile.overflow}px; ${JSON.stringify(mobile.wide)}`
    );
    check("at 390px the ticket action is on-screen", mobile.onScreen, JSON.stringify(mobile));
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
        : cards.filter((c) => !c.fits).every((c) => /\d/.test(c.label || "")),
      JSON.stringify(cards.filter((c) => !c.fits))
    );
    // 7d. The standard fare under a discounted price is a clear step down the
    // ladder, not a shade: it was 14px against a 16px price, which is the size
    // every other small note on a row already used, so the cell read as two
    // equal numbers rather than one price with a note under it.
    const note = await page.evaluate(() => {
      // The card is applied here rather than read from whatever the suite left
      // on screen, so the check exercises the path a reader takes and never
      // skips for want of state earlier in the run. The party control moves
      // with the card, because a card that covers two adults is not priced
      // onto a journey for one.
      const before = document.getElementById("railcardSelect").value;
      const unitBefore = document.querySelector('input[name="unit"]:checked').value;
      // Whether the page under test actually shows a discounted fare is read
      // off the page, card by card, rather than predicted from the payload.
      // Predicting it was wrong in two ways at once. A card's price can equal
      // the standard fare on the row the reader is looking at, because of that
      // card's own minimum fare: a 16-25 railcard floors at £12.00, so on a
      // £9.50 row it buys nothing and the page correctly shows no note. And a
      // card can lower some row in some fare list while the row the table
      // opens on, cheapest first, is one it does not touch. Either way the
      // missing note was the page being right, and the check asking for
      // something the reader cannot have.
      //
      // So the search is over what is on screen: one traveller first, then
      // two, and within each every card this page priced.
      const readLadder = () => {
        const was = document.querySelector("td.num .was");
        const price = document.querySelector("td.num .price");
        return was && price ? { was, price } : null;
      };
      let chosen = null;
      let seen = [];
      for (const who of ["adult", "party"]) {
        for (const card of DATA.railcards || []) {
          const travellers = who === "party" ? 2 : 1;
          if (card.minAdults > travellers || travellers > card.maxAdults) continue;
          const radio = document.querySelector('input[name="unit"][value="' + who + '"]');
          if (!radio) continue;
          radio.checked = true;
          document.getElementById("railcardSelect").value = card.key;
          render();
          const hit = readLadder();
          seen.push(card.key + "/" + (who === "party" ? 2 : 1));
          if (hit) {
            chosen = card;
            break;
          }
        }
        if (chosen) break;
      }
      if (!chosen) {
        // Left off by the search rather than returned from: it checked every
        // radio on the way through, so the page has to be handed back the way
        // the suite found it or every later check reads someone else's search.
        document.getElementById("railcardSelect").value = before;
        document.querySelector(`input[name="unit"][value="${unitBefore}"]`).checked = true;
        render();
        return { noCardLowers: true, tried: seen };
      }
      const ladder = readLadder();
      const was = ladder.was;
      const price = ladder.price;
      const reading = {
        note: parseFloat(getComputedStyle(was).fontSize),
        price: parseFloat(getComputedStyle(price).fontSize),
        text: was.textContent.trim(),
        card: chosen.key,
        unit: unit(),
      };
      document.getElementById("railcardSelect").value = before;
      document.querySelector(`input[name="unit"][value="${unitBefore}"]`).checked = true;
      render();
      return reading;
    });
    check(
      "the standard fare under a discounted price is a clear step down the ladder",
      note && note.noCardLowers
        ? notExercised(
            "no railcard on this page lowers any fare the party it covers is " +
              "charged, tried " + JSON.stringify(note.tried)
          )
        : note
          ? note.note <= note.price - 2
          : false,
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
      (r) => r.minutes !== null && (r.time.startsWith("No service") || r.time.startsWith("No timetable") || r.changes === "Unknown")
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
    // 7a. A resize is not a fold. The refinements used to open and close with
    // the viewport -- a media query and a resize listener, two roads to one
    // state -- which meant a reader who rotated a phone could lose the fold
    // they had chosen. The fold is theirs now, so a resize has to leave it
    // exactly where they left it, in both directions.
    const beforeResize = await page.evaluate(
      () => (document.getElementById("moreFilters") || {}).dataset.open
    );
    await page.setViewportSize({ width: 1280, height: 800 });
    const afterResize = await page.evaluate(
      () => (document.getElementById("moreFilters") || {}).dataset.open
    );
    check(
      "a resize does not move the fold the reader chose",
      beforeResize === afterResize,
      `${beforeResize} -> ${afterResize}`
    );
    // 7b. The address is the search (S05). Every control the reader moves has
    // to survive a refresh, a shared link and Back, and the picker has to
    // carry the same search to the station they switch to (S06). The facts are
    // read out of the page's own controls, so nothing here names a budget or a
    // mode the page might not have.
    await open();
    // Read the address from the page, not from page.url(): a history change
    // made by the page's own script reaches the driver one round trip later,
    // so page.url() immediately after a click can still be the old address and
    // would make a control that works look broken.
    const address = () => page.evaluate(() => window.location.href);
    const stateful = await page.evaluate(() => ({
      chips: Array.from(document.querySelectorAll('input[name="destinationType"]'))
        .filter((input) => input.value !== "all")
        .filter((input) => !input.closest("label").hidden)
        .map((input) => input.value),
      hasParty: !!document.querySelector('input[name="unit"][value="party"]'),
    }));
    // One non-default mode, if this page has a second mode with fares in it.
    const otherMode = await page.evaluate(() => {
      // The radio the page opened with, put back after each probe. Unchecking
      // the radio that was chosen would leave a group with nothing selected,
      // which is a state no reader can reach and which the next click cannot
      // be judged from.
      const fallback = document.querySelector('input[name="ticketMode"]:checked');
      const mode = (wanted) => {
        const input = document.querySelector(`input[name="ticketMode"][value="${wanted}"]`);
        input.checked = true;
        render();
        const rows = document.querySelectorAll("#rows tr").length;
        fallback.checked = true;
        return rows;
      };
      // Only a mode that is not the page default, because a default is the one
      // value the address leaves out by design. The default is whatever the
      // page opened with, not a name written here, so changing which mode the
      // page opens in cannot make this probe pick the default and then assert
      // the address carries it.
      const defaultValue = fallback.value;
      for (const wanted of ["return", "single", "anytime"]) {
        if (wanted === defaultValue) continue;
        if (mode(wanted) > 0) return wanted;
      }
      return null;
    });
    const partyBudget = await page.evaluate(() => {
      // The budget the party mode can actually show, or null when this page
      // has nothing a pair could buy. The same restore as above.
      const fallback = document.querySelector('input[name="unit"]:checked');
      const input = document.querySelector('input[name="unit"][value="party"]');
      input.checked = true;
      const ceiling = budgetCeiling();
      fallback.checked = true;
      return ceiling > 1 ? ceiling : null;
    });
    const aChip = stateful.chips[0] || null;
    if (otherMode) {
      // force: the radio itself is visually hidden inside its styled label,
      // which is the target a reader actually clicks.
      await page.locator(`input[name="ticketMode"][value="${otherMode}"]`).check({ force: true });
      check("the address carries the ticket mode", new RegExp("[?&]mode=" + otherMode + "(&|$)").test(await address()), await address());
    } else {
      check("the address carries the ticket mode", notExercised("no mode other than this page's default has a row"));
    }
    if (partyBudget && stateful.hasParty) {
      await page.check('input[name="unit"][value="party"]');
      check("the address carries the party", /[?&]party=2(&|$)/.test(await address()), await address());
      // Back to one adult, which is the other end of the same radio group.
      await page.check('input[name="unit"][value="adult"]');
    } else {
      check("the address carries the party", notExercised("this page has no party price a pair could be shown"));
    }
    if (aChip) {
      await page.check(`input[name="destinationType"][value="${aChip}"]`);
      check("the address carries the destination type", new RegExp("[?&]types=" + aChip + "(&|$)").test(await address()), await address());
    } else {
      check("the address carries the destination type", notExercised("this page offers no destination-type chip"));
    }
    // An absent mode parameter means the page's own default, read above from
    // the control rather than repeated here.
    const sharedUrl = await address();
    await page.reload();
    check(
      "a refresh keeps the search the address describes",
      (await page.inputValue("#budgetNumber")) === new URL(sharedUrl).searchParams.get("budget") &&
        (await page.evaluate(() => document.querySelector('input[name="ticketMode"]:checked').value)) === (new URL(sharedUrl).searchParams.get("mode") || defaultMode) &&
        (await page.evaluate(() => document.querySelectorAll('input[name="destinationType"]:checked').length)) ===
          new URL(sharedUrl).searchParams.getAll("types").length,
      sharedUrl
    );
    check("and the title still names that budget", new RegExp("up to £" + new URL(sharedUrl).searchParams.get("budget") + "\\b").test(await page.title()), await page.title());
    // Back is one decision, not a direction the page can only go forwards in.
    await page.goBack();
    const backUrl = await address();
    const afterBack = await page.evaluate(() => ({
      mode: document.querySelector('input[name="ticketMode"]:checked').value,
      budget: document.getElementById("budgetNumber").value,
    }));
    check(
      "Back returns to the previous search",
      (new URL(backUrl).searchParams.get("mode") || defaultMode) === afterBack.mode,
      `${afterBack.mode} at £${afterBack.budget} on ${backUrl}`
    );
    // The budget is the one thing every reader has, so it is the one thing the
    // heading and the tab must both be saying.
    await open(3);
    check("the tab title follows the budget", /up to £3\b/.test(await page.title()), await page.title());
    // 7c. The party, the fare's conditions, the facets, and what an empty
    // list offers. Every fact is read out of this page's own payload and
    // controls, so one run of this section is a test of the page rather than
    // of the station it was pointed at.
    await open(facts.affordable);
    // Q2: a railcard is one of a collection the reader picks from, nothing is
    // selected by default, and a card whose own feed record does not cover the
    // party on screen is listed but cannot be chosen for it.
    const cardChoice = await page.locator("#railcardChoice").isVisible();
    const menu = await page.evaluate(() => {
      const select = document.getElementById("railcardSelect");
      const adults = document.querySelector('input[name="unit"]:checked').value === "party" ? 2 : 1;
      return {
        options: Array.from(select.options).map((o) => ({
          value: o.value,
          label: o.textContent,
          disabled: o.disabled,
        })),
        value: select.value,
        disabled: select.disabled,
        help: document.getElementById("railcardHelp").textContent,
        adults,
        // Every card the feed prices, and the ones this party can actually use.
        // Every priced card is in the list whatever its bounds; only the usable
        // ones can be chosen. Removal was ADR-0052's answer, and it cost the
        // one card whose bounds are 2 to 2 on a page showing one adult.
        offered: (DATA.railcards || []).map((c) => c.key),
        forParty: (DATA.railcards || [])
          .filter((c) => c.minAdults <= adults && adults <= c.maxAdults)
          .map((c) => c.key),
      };
    });
    check(
      "the railcard control lists every card this page prices, plus one 'none' option",
      cardChoice
        ? menu.offered.length > 0 &&
          menu.options.length === menu.offered.length + 1 &&
          menu.options[0].value === "" &&
          menu.options.slice(1).every((o, i) => o.value === menu.offered[i])
        : notExercised("this feed prices no reviewed railcard"),
      `${menu.adults} adult(s): priced ${JSON.stringify(menu.offered)}; ${JSON.stringify(menu.options)}`
    );
    check(
      "and only the cards whose own bounds cover the party on screen can be chosen",
      cardChoice
        ? menu.options.slice(1).every((o) => (o.disabled ? !menu.forParty.includes(o.value) : menu.forParty.includes(o.value)))
        : notExercised("this feed prices no reviewed railcard"),
      `${menu.adults} adult(s): usable ${JSON.stringify(menu.forParty)}; ${JSON.stringify(menu.options)}`
    );
    check(
      "and no railcard is selected by default, so the prices are standard fares",
      cardChoice
        ? menu.value === "" && /No railcard selected/.test(menu.help)
        : notExercised("this feed prices no reviewed railcard"),
      `value=${menu.value} help=${menu.help}`
    );
    const solo = cardChoice
      ? await page.evaluate(() => {
        document.querySelector('input[name="unit"][value="adult"]').checked = true;
        render();
        const select = document.getElementById("railcardSelect");
        return {
          options: Array.from(select.options).map((o) => ({ value: o.value, disabled: o.disabled })),
          cards: DATA.railcards.map((c) => ({ key: c.key, min: c.minAdults, max: c.maxAdults })),
          help: document.getElementById("railcardHelp").textContent,
        };
      })
      : null;
    // S15: a card that needs two travellers cannot price one reader's journey,
    // so it cannot be chosen for a party of one -- but it is still in the list,
    // saying how many it needs. Removing it meant Two Together, whose bounds
    // are 2 to 2, was absent from every one-adult page, which reads as "this
    // page does not price Two Together" rather than "not for the party you
    // have on screen". The bounds are the feed's own records.
    check(
      "one adult is offered only the cards whose own bounds cover one adult",
      cardChoice
        ? solo.options.slice(1).every((o) => {
            const card = solo.cards.find((c) => c.key === o.value);
            const usable = card && card.min <= 1 && 1 <= card.max;
            return o.disabled === !usable;
          })
        : notExercised("this feed prices no reviewed railcard"),
      `options=${solo ? JSON.stringify(solo.options) : ""}`
    );
    const duo = cardChoice
      ? await page.evaluate(() => {
        document.querySelector('input[name="unit"][value="party"]').checked = true;
        render();
        const select = document.getElementById("railcardSelect");
        const options = Array.from(select.options).map((o) => o.value);
        const first = options.find((v) => v !== "") || "";
        if (first) {
          select.value = first;
          render();
        }
        return {
          options,
          first,
          help: document.getElementById("railcardHelp").textContent,
          cards: DATA.railcards,
          disabled: select.disabled,
        };
      })
      : null;
    check(
      "two adults are offered the cards that cover two",
      cardChoice && duo.cards.some((c) => c.minAdults <= 2 && 2 <= c.maxAdults)
        ? duo.first !== "" &&
          duo.cards
            .filter((c) => c.minAdults <= 2 && 2 <= c.maxAdults)
            .every((c) => duo.options.includes(c.key)) &&
          !duo.disabled
        : notExercised(
            cardChoice
              ? "this feed prices no railcard that covers two adults, so a party of two cannot be priced with one"
              : "this feed prices no reviewed railcard"
          ),
      `options=${duo ? duo.options.join(",") : ""} cards=${
        duo ? duo.cards.filter((c) => c.minAdults <= 2 && 2 <= c.maxAdults).map((c) => c.key).join(",") : ""
      }`
    );
    check(
      "and the help names the chosen card, its bounds and what it would discount",
      cardChoice && pair && duo.first
        ? (() => {
            const card = duo.cards.find((c) => c.key === duo.first);
            return (
              card &&
              new RegExp(String(card.minAdults) + " to " + String(card.maxAdults) + " adults").test(duo.help) &&
              duo.help.includes(card.label) &&
              new RegExp(String(card.eligibleCount)).test(duo.help) &&
              /open a row's own details/.test(duo.help)
            );
          })()
        : notExercised("this page prices no card that covers two adults"),
      pair ? duo.help : ""
    );
    // Q2: the browser remembers the card, which is what makes this a collection
    // rather than a per-page question. Every reading here goes through the
    // control itself. Assigning select.value from a script fires no change
    // event, so nothing is written and nothing re-rendered, and a check written
    // that way reads back the value the test just set rather than anything the
    // page remembered.
    // The party is set first, because a card that does not cover the party on
    // screen is not in the list at all. The block above leaves two adults
    // selected, and this feed's only reviewed card covers one, so reading the
    // list without setting the party found nothing to choose.
    // The refinements are folded on every route, and a navigation folds them
    // again, so the control is opened the way the reader opens it rather than
    // driven while hidden.
    const revealCardControl = async () => {
      const folded = await page.evaluate(
        () => (document.getElementById("moreFilters") || {}).dataset.open === "true"
      );
      if (!folded) await page.locator("#moreFiltersToggle").click();
    };
    const holdable = await page.evaluate(() => {
      const cards = DATA.railcards || [];
      for (const adults of [1, 2]) {
        const card = cards.find((c) => c.minAdults <= adults && adults <= c.maxAdults);
        if (!card) continue;
        document.querySelector(
          'input[name="unit"][value="' + (adults === 2 ? "party" : "adult") + '"]'
        ).checked = true;
        render();
        const options = Array.from(document.getElementById("railcardSelect").options)
          .map((o) => o.value)
          .filter(Boolean);
        if (options.includes(card.key)) return card.key;
      }
      return null;
    });
    if (holdable) {
      await revealCardControl();
      await page.selectOption("#railcardSelect", holdable);
      const stored = await page.evaluate(() =>
        window.localStorage.getItem("tbe.railcard." + DATA.origin.crs)
      );
      check(
        "the browser remembers the card the reader chose",
        stored === holdable,
        `stored=${stored} chosen=${holdable}`
      );
      check(
        "and the address carries the card by its code, so a shared link is the same search",
        page.url().includes("card=" + holdable),
        page.url()
      );
      // open() takes a budget, not a URL, so the address is followed directly.
      await page.goto(page.url());
      const cameBack = await page.evaluate(() =>
        document.getElementById("railcardSelect").value
      );
      check(
        "and reopening that address prices with the same card",
        cameBack === holdable,
        `value=${cameBack} expected=${holdable}`
      );
      await revealCardControl();
      await page.selectOption("#railcardSelect", "");
      const cleared = await page.evaluate(() => ({
        stored: window.localStorage.getItem("tbe.railcard." + DATA.origin.crs),
        value: document.getElementById("railcardSelect").value,
        url: window.location.search,
      }));
      check(
        "and clearing the control forgets the card and drops it from the address",
        cleared.stored === null && cleared.value === "" && !/card=/.test(cleared.url),
        JSON.stringify(cleared)
      );
      // A shared link can name a card this origin's feed does not price. It is
      // ignored rather than read as a card the reader holds.
      await page.goto(page.url() + (page.url().includes("?") ? "&" : "?") + "card=ZZZ");
      const ignoredValue = await page.evaluate(() =>
        document.getElementById("railcardSelect").value
      );
      check(
        "and a card code this page does not price is ignored, not half-applied",
        ignoredValue === "",
        `value=${ignoredValue}`
      );
    } else {
      for (const name of [
        "the browser remembers the card the reader chose",
        "and the address carries the card by its code, so a shared link is the same search",
        "and reopening that address prices with the same card",
        "and clearing the control forgets the card and drops it from the address",
        "and a card code this page does not price is ignored, not half-applied",
      ]) {
        check(name, notExercised("this feed prices no railcard for the party on screen"));
      }
    }
    // Q3: the discounted number never stands alone in the cell. With the card
    // chosen a row the card lowers carries the card price and the standard
    // fare it came from; a row it does not lower carries one price; and with
    // no card chosen no row carries a second number at all.
    if (cardChoice) {
      // Each reading carries the row's own standard price beside the two cells.
      // The list is "cheapest of any type", so the card can change which fare
      // wins for a destination -- a two-part row the card lowers can displace
      // the one that won without it (the re-sort check below asserts exactly
      // that). Comparing the card render's "was" against the clear render's
      // price therefore compares two different rows whenever the winner moves;
      // what the check is about is that the "was" beside a card price is the
      // standard fare of the row it sits in.
      const readCells = () => page.evaluate(() => {
        const cells = {};
        for (const row of document.querySelectorAll("#rows tr[data-crs]")) {
          const price = row.querySelector("td.num .price");
          const was = row.querySelector("td.num .was");
          const destination = activeDestinations().find((d) => d.crs === row.dataset.crs);
          cells[row.dataset.crs] = {
            price: price ? price.textContent.trim() : null,
            was: was ? was.textContent.trim() : null,
            standard: destination
              ? standardPrice(destination)
              : null,
          };
        }
        return cells;
      });
      const amount = (text) => Number(String(text).replace(/[^0-9.]/g, ""));
      // A row the card actually lowers is the row this check is about, so the
      // budget is set to reach one instead of inheriting whatever the section
      // before left on screen.
      // The card and the party are chosen together from the feed's own bounds.
      // The demo feed's reviewed card covers one adult, so choosing the party
      // first and then looking for a card that covers it found nothing, and the
      // check reported that no destination is lowered by a card that lowers
      // three of them.
      const pick = await page.evaluate(() => {
        const rows = [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations].flat();
        for (const c of DATA.railcards || []) {
          for (const adults of [2, 1]) {
            if (!(c.minAdults <= adults && adults <= c.maxAdults)) continue;
            const helped = rows.filter((d) => {
              const card = (d.railcards || {})[c.key];
              return card && card.pricePence !== null && card.pricePence < d.adultPence;
            });
            if (helped.length) return { key: c.key, adults, helped: helped.length };
          }
        }
        return null;
      });
      // The clear reading is taken with no card selected and the card reading
      // with it selected. These two were the other way round, so the check
      // compared two card prices and reported every row as unchanged.
      await page.evaluate((choice) => {
        const select = document.getElementById("railcardSelect");
        if (!choice) {
          select.value = "";
          render();
          return;
        }
        document.querySelector(
          'input[name="unit"][value="' + (choice.adults === 2 ? "party" : "adult") + '"]'
        ).checked = true;
        select.value = "";
        // The rows the card lowers are put on the first page. The table shows 20
        // rows a page, cheapest first, and a card's minimum fare means the
        // rows it lowers are the dearer ones: Falmouth Town's 16-25 Railcard
        // lowers nothing under its £12 floor, so all of the first page was
        // unchanged and a right page read as one that ignored the card.
        window.__keptLists = [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations];
        const lowers = (d) => {
          const entry = (d.railcards || {})[choice.key];
          return entry && entry.pricePence !== null && entry.pricePence < d.adultPence;
        };
        // Fifteen it lowers and five it does not, so one page holds both and
        // the checks on unlowered rows still have rows to read.
        const onePage = (list) => list.filter(lowers).slice(0, 15).concat(list.filter((d) => !lowers(d)).slice(0, 5));
        DATA.destinations = onePage(DATA.destinations || []);
        DATA.singleDestinations = onePage(DATA.singleDestinations || []);
        DATA.anytimeDestinations = onePage(DATA.anytimeDestinations || []);
        currentPage = 1;
        render();
        const dearest = [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations]
          .flat()
          .filter((d) => {
            const card = (d.railcards || {})[choice.key];
            return card && card.pricePence !== null && card.pricePence < d.adultPence;
          })
          .reduce((high, d) => Math.max(high, choice.adults === 2 ? d.partyPence : d.adultPence), 0);
        if (dearest) {
          setBudget(Math.min(Number(document.getElementById("budget").max), Math.ceil(dearest / 100)));
        }
        render();
      }, pick);
      const lowered = pick ? pick.helped : 0;
      const clear = await readCells();
      await page.evaluate((choice) => {
        const select = document.getElementById("railcardSelect");
        select.value = choice ? choice.key : "";
        render();
      }, pick);
      const card = await readCells();
      if (pick) {
        await page.evaluate(() => {
          [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations] = window.__keptLists;
          currentPage = 1;
          document.getElementById("railcardSelect").value = "";
          render();
        });
      }
      const rows = Object.keys(clear).filter((crs) => clear[crs].price !== null && card[crs]);
      const helped = rows.filter((crs) => amount(card[crs].price) < amount(clear[crs].price));
      const unchanged = rows.filter((crs) => amount(card[crs].price) === amount(clear[crs].price));
      check(
        "a discounted row shows the card price and the standard fare it was discounted from",
        lowered
          ? helped.length > 0 &&
            helped.every(
              (crs) =>
                Math.round(amount(card[crs].was) * 100) === card[crs].standard &&
                /standard/.test(card[crs].was)
            )
          : notExercised("no destination on this page is lowered by the card"),
        JSON.stringify(helped.slice(0, 3).map((crs) => [crs, clear[crs], card[crs]]))
      );
      check(
        "and a row the card does not lower still shows one price",
        unchanged.every((crs) => card[crs].was === null),
        JSON.stringify(unchanged.slice(0, 3).map((crs) => card[crs]))
      );
      check(
        "with no railcard selected no row shows a second price",
        rows.every((crs) => clear[crs].was === null),
        JSON.stringify(rows.slice(0, 3).map((crs) => clear[crs]))
      );
    } else {
      check("a discounted row shows the card price and the standard fare it was discounted from",
        notExercised("this feed prices no reviewed railcard"));
      check("and a row the card does not lower still shows one price",
        notExercised("this feed prices no reviewed railcard"));
      check("with no railcard selected no row shows a second price",
        notExercised("this feed prices no reviewed railcard"));
    }
    // The railcard note leads with the row's own price, so opening a row's
    // details never shows a bigger number than the row it was opened from. The
    // row the old drawer got wrong is the one the card does not lower: the
    // card's own price for that fare sits above the fare the row is priced at,
    // and it was printed under a label that called it a discount. Read from
    // the notes themselves rather than from the template, because the number
    // is written by script and a string in the source can only say what was
    // meant to be written.
    const drawerChoice = await page.evaluate(() => {
      const rows = [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations].flat();
      // A card that prices a row is not a card that discounts one. On a real
      // page the first card in the list is the 16-25, whose price is the £12
      // DTD minimum on every fare below it, so it prices everything and lowers
      // nothing -- and every check about a discounted row then failed on a page
      // that has none. Prefer a card that actually lowers a price; fall back to
      // one that merely prices something, which is a real answer about rows the
      // card cannot help rather than a substitute for one.
      let anyPriced = null;
      for (const card of DATA.railcards || []) {
        for (const adults of [2, 1]) {
          if (!(card.minAdults <= adults && adults <= card.maxAdults)) continue;
          const priced = rows.filter((d) => {
            const detail = (d.railcards || {})[card.key];
            return detail && detail.pricePence !== null;
          });
          if (!priced.length) continue;
          const discounted = priced.filter((d) => {
            const detail = d.railcards[card.key];
            const standard = adults === 2 ? d.partyPence : d.adultPence;
            return detail.pricePence < standard;
          });
          if (discounted.length) return { key: card.key, adults, discounted: discounted.length };
          if (!anyPriced) anyPriced = { key: card.key, adults, discounted: 0 };
        }
      }
      return anyPriced;
    });
    const noteRows = drawerChoice
      ? await page.evaluate((choice) => {
          // There is no drawer: the note is built into the panel the row
          // already opens, so it is read from there and from nowhere else.
          if (document.getElementById("railcardDrawer")) {
            return { error: "the railcard drawer is still on the page" };
          }
          document.querySelector(
            'input[name="unit"][value="' + (choice.adults === 2 ? "party" : "adult") + '"]'
          ).checked = true;
          document.getElementById("railcardSelect").value = choice.key;
          // Only the list the page is showing: a row in another ticket mode is
          // not on screen, so it is not a note a reader could read.
          const priced = activeDestinations().filter((d) => (d.railcards || {})[choice.key]);
          if (!priced.length) return { error: "this page shows no row that card touches" };
          const dearest = priced.reduce(
            (high, d) => Math.max(high, choice.adults === 2 ? d.partyPence : d.adultPence),
            0
          );
          if (dearest) {
            setBudget(Math.min(Number(document.getElementById("budget").max), Math.ceil(dearest / 100)));
          }
          currentPage = 1;
          render();
          const readings = [];
          for (const row of Array.from(document.querySelectorAll("#rows tr[data-crs]"))) {
            // The note is built when the panel opens, so the row is opened
            // first, the same way a reader reaches it, and closed again after.
            const fold = row.querySelector(".toggle[aria-expanded='false']");
            if (fold) fold.click();
            const detail = row.nextElementSibling;
            const note =
              detail && detail.classList.contains("detail")
                ? detail.querySelector(".card-note")
                : null;
            const price = row.querySelector("td.num .price");
            readings.push({
              crs: row.dataset.crs,
              row: price ? price.textContent.trim() : null,
              inOwnPanel: Boolean(note) && detail.contains(note),
              state: note ? note.dataset.state : null,
              text: note ? note.textContent : null,
            });
            if (fold) fold.click();
          }
          return { readings };
        }, drawerChoice)
      : { readings: [] };
    const noteRowsList = noteRows.readings || [];
    const pounds = (text) => Number(String(text).replace(/[^0-9.]/g, ""));
    // The note names the card's own price first wherever it names one at all:
    // the blocked branch quotes no figure, and every other branch opens with
    // what the card costs for this fare.
    const quoted = (note) => {
      const match = /£\s?([0-9]+(?:\.[0-9]{2})?)/.exec(note.text || "");
      return match ? Number(match[1]) : null;
    };
    // A row with no price on screen carries no number to compare.
    const quotedRows = noteRowsList.filter((r) => r.row !== null && quoted(r) !== null);
    check(
      "the note is in the row's own panel, and no drawer is left behind",
      noteRows.error
        ? false
        : noteRowsList.length > 0 && noteRowsList.every((r) => r.inOwnPanel),
      JSON.stringify({ error: noteRows.error, sample: noteRowsList.slice(0, 3) })
    );
    check(
      "the note never quotes more than the row it sits under",
      quotedRows.length
        ? quotedRows.every((r) => quoted(r) <= pounds(r.row))
        : notExercised("this page prices no railcard against a row it shows"),
      JSON.stringify(quotedRows.slice(0, 4).map((r) => [r.crs, r.row, quoted(r), r.state]))
    );
    check(
      "and a row the card cannot be applied to says so rather than quoting a price",
      noteRowsList.filter((r) => r.state === "blocked").every((r) => quoted(r) === null),
      JSON.stringify(noteRowsList.filter((r) => r.state === "blocked").slice(0, 3).map((r) => r.text))
    );
    // The section that follows reads rows and their panels, so the page is
    // handed back at the budget the rest of this block is written against.
    await open(facts.affordable);
    // Q2 (finding 5): a journey with a change names the station a split ticket
    // would change at, in the same panel as the condition, and prices neither
    // half. Read from this page's own payload first, so a page with no changed
    // row reports that rather than asserting a sentence it cannot show.
    //
    // The row is found in a list the page can actually render: the section
    // above opened the page on its cheapest fare in one mode, and the changed
    // row is not necessarily in that list -- on the Lincoln fixture it sits in
    // the returns while the page opens on the Anytime set. Each named list is
    // tried in turn, at that list's own ceiling, and the page and its panels
    // are put back the way they were found.
    const split = await page.evaluate(() => {
      const budgetBefore = budget.value;
      const modeBefore = document.querySelector('input[name="ticketMode"]:checked').value;
      const lists = { return: "destinations", single: "singleDestinations", anytime: "anytimeDestinations" };
      const restore = () => {
        const back = document.querySelector(`input[name="ticketMode"][value="${modeBefore}"]`);
        if (back) back.checked = true;
        setBudget(Number(budgetBefore));
        currentPage = 1;
        render();
      };
      // The note is read out of the opened panel and the panel is closed again:
      // a row left open would make the next check count one toggle fewer than
      // it has rows.
      const noteFor = (destination) => {
        const line = document.querySelector(`#rows tr[data-crs="${destination.crs}"]`);
        if (!line) return null;
        const toggle = line.querySelector(".toggle[aria-expanded='false']");
        if (!toggle) return null;
        toggle.click();
        const detail = line.nextElementSibling;
        const note = detail && detail.classList.contains("detail")
          ? detail.querySelector(".split") : null;
        toggle.click();
        return note ? note.textContent : "";
      };
      for (const mode of [modeBefore, "return", "single", "anytime"]) {
        const list = DATA[lists[mode]];
        const input = document.querySelector(`input[name="ticketMode"][value="${mode}"]`);
        if (!list || !input) continue;
        input.checked = true;
        setBudget(budgetCeiling());
        currentPage = 1;
        render();
        const changesAt = (d) => (d.changeStations || []).length;
        // The table holds one page of twenty rows and the list behind it holds
        // every destination in the mode, so on a real page the first changed
        // journey is usually not the one on screen. noteFor answers null for a
        // row the page has not rendered, and a check that reads null reports a
        // missing note on a page that prints one -- Nottingham said Derby had
        // no split ticket when the note is there on page three. So the page
        // holding the row is rendered first, and the direct counterpart is
        // taken from that same page: a direct row on another page is not one a
        // reader can set the changed row beside.
        const onScreen = () =>
          Array.from(document.querySelectorAll("#rows tr[data-crs]")).map((r) => r.dataset.crs);
        // A two-ticket row (ADR-0061) is not a through fare, so it carries no
        // note about splitting one; the through-fare rows are the ones asked.
        const changedRows = list.filter((d) => changesAt(d) && !d.tickets);
        let changed = changedRows.find((d) => onScreen().includes(d.crs));
        if (!changed) {
          const elsewhere = changedRows.find((d) => {
            const at = list.indexOf(d);
            if (at < 0) return false;
            currentPage = Math.floor(at / PAGE_SIZE) + 1;
            render();
            return onScreen().includes(d.crs);
          });
          if (!elsewhere) continue;
          changed = elsewhere;
        }
        const direct = onScreen()
          .map((crs) => list.find((d) => d.crs === crs))
          .find((d) => d && !changesAt(d));
        const read = {
          mode,
          changed: { crs: changed.crs, name: changed.changeStations[0].name, note: noteFor(changed) },
          direct: direct ? { crs: direct.crs, note: noteFor(direct) } : null,
        };
        restore();
        return read;
      }
      restore();
      return null;
    });
    check(
      "a changed journey names the station a split ticket would change at",
      // The note says "the station above" and the name is in the row above, so
      // repeating it in the note would be saying the same word twice on one
      // line of screen. What has to hold is that the note points at this row's
      // own station rather than at some other one.
      split && split.changed
        ? Boolean(split.changed.note) && /split ticket/.test(split.changed.note) &&
          /station above|station below|this station/.test(split.changed.note)
        : notExercised("no destination on this page changes"),
      JSON.stringify(split && split.changed || null)
    );
    check(
      "and a direct journey claims no split to make",
      split && split.changed && split.direct
        ? split.direct.note === ""
        : notExercised("no changed row, or no direct row in the same list"),
      JSON.stringify(split && split.direct || null)
    );
// Does this condition tell a reader something its restriction code does not?
//
// The defect it stands for is a panel that prints the code and calls it a
// condition. Three ways to do that, all rejected: nothing at all, the code
// itself, or a string built only from the code's own letters. Digits are
// dropped before comparing, because `B31` beside `B3` is the code again with a
// digit on the end, not a condition. Everything else
// is the feed's wording and is allowed to be as terse as the feed wrote it --
// `OFF-PEAK` beside `B3` says something, and the suite is not in a position
// to improve on the feed's phrasing.
function saysMoreThan(condition, code) {
  const text = (condition || "").trim();
  if (!text) return false;
  const letters = (value) => (value || "").toUpperCase().replace(/[^A-Z]/g, "");
  const said = letters(text);
  const bare = letters(code);
  if (!said) return false;
  return said !== bare && ![...said].every((character) => bare.includes(character));
}
    // S19, with the finding of 29 September 2026 on top: the condition is
    // still a sentence rather than a bare code, and the feed's own vocabulary
    // is still folded away -- but on the real page that same sentence stood in
    // all 20 rows, 40 cells restating the mode the mode control had already
    // named. The row carries the fare's code now and the sentence is one
    // disclosure away on the row the reader is reading. Measured by opening
    // every row, because a panel that never opens is not a disclosure.
    const conditions = await page.evaluate(() => {
      const toggles = Array.from(
        document.querySelectorAll("#rows tr:not(.detail) .toggle[aria-expanded=false]")
      );
      for (const toggle of toggles) toggle.click();
      const found = Array.from(document.querySelectorAll("#rows .restriction")).map((cell) => {
        const row = cell.closest("tr.detail").previousElementSibling;
        const record = Array.from(cell.querySelectorAll(".feed-record dd")).map((dd) => dd.textContent);
        return {
          readable: (cell.querySelector(".condition") || {}).textContent || "",
          sentence: (cell.querySelector(".fare-line") || {}).textContent || "",
          validity: (cell.querySelector(".validity") || {}).textContent || "",
          restricted: cell.dataset.status === "restricted",
          record,
          // The restriction this condition describes, so the check can ask
          // whether the condition says anything the code does not.
          restriction: record[1] || "",
          summary: (cell.querySelector(".feed-record summary") || {}).textContent || "",
          // The code is in the record now, under the "Ticket" label, and the
          // row itself carries the word a reader can act on.
          code: record[0] || "",
          word: (row.querySelector(".fare-kind") || {}).textContent || "",
        };
      });
      // Put the rows back: a later check that found twenty panels open would be
      // measuring a page nobody is looking at.
      for (const toggle of toggles) toggle.click();
      return { found, rows: document.querySelectorAll("#rows tr:not(.detail)").length, toggles: toggles.length };
    });
    check(
      "every row states its fare in a sentence, one disclosure away",
      conditions.rows > 0 &&
        conditions.toggles === conditions.rows &&
        conditions.found.length === conditions.rows &&
        // Every row says what kind of fare it is. A row whose fare carries a
        // restriction code says what the condition is as well; a row with no
        // condition in the feed is not given one, which is why the sentence
        // and the condition are checked separately.
        //
        // The condition is judged against the code it belongs to, not by how
        // it is spelled. It used to be rejected for opening with one to four
        // capitals, which on the real feed rejects 624 of the 841 descriptions
        // in the file -- `OFF-PEAK`, `NTH ADVANCE`, `NOT VALID BEFORE 0915
        // MON-FRI`, `BAN ALL DAY`. Those are the conditions a reader needs,
        // they are the feed's own wording, and paraphrasing them is a
        // licencee's risk. Counted over the whole file: no description is
        // empty and none equals its own code, so the page was never printing a
        // bare one. What must not happen is the code restated as prose.
        conditions.found.every(
          (cell) =>
            cell.sentence.length > 10 &&
            !/^[A-Z0-9]{1,4}\b/.test(cell.sentence) &&
            (!cell.restricted || saysMoreThan(cell.readable, cell.restriction))
        ),
      JSON.stringify(conditions.found[0] || null) +
        ` rows=${conditions.rows} toggles=${conditions.toggles}`
    );
    check(
      "and the row names the fare in a word while the feed's code stays folded",
      conditions.found.length > 0 &&
        conditions.found.every(
          (cell) =>
            cell.summary &&
            cell.record.length >= 2 &&
            cell.code.length > 0 &&
            ["Advance", "Restricted", "Regular"].includes(cell.word)
        ),
      JSON.stringify(conditions.found[0] || null)
    );
    // The rule above is worth stating on its own, because the page has 841
    // codes to choose from and a reader can only act on the ones that are
    // explained. A condition that is its own code is the failure; a condition
    // the feed wrote tersely is not.
    check(
      "no row prints its restriction code as though it were the condition",
      conditions.found.every(
        (cell) => !cell.restricted || saysMoreThan(cell.readable, cell.restriction)
      ),
      JSON.stringify(
        conditions.found.filter((cell) => cell.restricted && !saysMoreThan(cell.readable, cell.restriction))
      )
    );
    // The rule above is the one the whole check rests on, and it was wrong once
    // already: it used to reject a condition for opening with one to four
    // capitals, which rejects 624 of the 841 descriptions in the real file. A
    // rule that has been wrong in the generous direction will be wrong in the
    // other one next, so the cases that separate them are named here rather
    // than left to whoever reads it next.
    const ruleCases = [
      // Conditions the real feed writes tersely. Every one of these was
      // reported as a defect, and none of them is a code.
      ["OFF-PEAK", "B3", true],
      ["NTH ADVANCE", "NT", true],
      ["NOT VALID BEFORE 0915 MON-FRI", "TU", true],
      ["BAN ALL DAY", "ZZ", true],
      ["IEC OFF-PEAK", "1U", true],
      // The condition being its own code, in every disguise a page might
      // print it in. These are the defect the rule exists for.
      ["", "B3", false],
      ["   ", "B3", false],
      ["B3", "B3", false],
      ["b3", "B3", false],
      ["  B3  ", "B3", false],
      ["3B", "B3", false],
      ["BB333", "B3", false],
      ["-B3-", "B3", false],
      ["B3 (2)", "B3", false],
      // The code with a digit on the end, which is the code again. Digits are
      // dropped before comparing precisely so this cannot pass.
      ["B31", "B3", false],
      ["B3 1", "B3", false],
      // A code with something else attached says something, and is allowed.
      ["B3 OFF-PEAK", "B3", true],
    ];
    const wrongRule = ruleCases
      .filter(([text, code, want]) => saysMoreThan(text, code) !== want)
      .map(([text, code, want]) => ({ text, code, want, got: saysMoreThan(text, code) }));
    check(
      "the condition rule accepts the feed's terse wording and rejects a bare code",
      wrongRule.length === 0,
      JSON.stringify(wrongRule)
    );
    // C08: where the feed states what a restriction permits, the row prints it
    // beside the condition rather than leaving the reader with a code. Judged
    // against the payload, so a page whose feed has nothing to decode is not
    // failed for not inventing it -- but a page whose feed has the text and
    // does not print it is.
    //
    // The mode is found rather than assumed: the reviewed set the page opens in
    // drops restricted fares by design, so the row that carries the validity is
    // in a mode the reader has to switch to. The page is put back the way it
    // was, or every later check on this page runs against a mode nobody asked
    // for.
    const restrictedMode = await page.evaluate(() => {
      const fallback = document.querySelector('input[name="ticketMode"]:checked');
      // Every priced row, at the page's own ceiling: the restricted fare is
      // often the dearest one on the page, and a check that only looked at
      // what the current budget happened to leave on screen would report
      // nothing to check on a page that carries the row.
      const budgetBefore = budget.value;
      setBudget(budgetCeiling());
      currentPage = 1;
      const codes = Object.entries(DATA.restrictionValidity || {}).filter(
        ([, value]) => value && (value.outwardText || value.returnText)
      ).map(([code]) => code);
      if (!codes.length) return null;
      for (const wanted of [fallback.value, "return", "single", "anytime"]) {
        const input = document.querySelector(`input[name="ticketMode"][value="${wanted}"]`);
        if (!input) continue;
        input.checked = true;
        render();
        // The condition, its validity and the record are one disclosure away on
        // the row, so every row is opened before it is read. The render() that
        // restores the reader's mode below clears them again.
        for (const toggle of document.querySelectorAll("#rows tr:not(.detail) .toggle[aria-expanded=false]")) {
          toggle.click();
        }
        const shown = Array.from(document.querySelectorAll("#rows .restriction"))
          .filter((cell) => cell.dataset.status === "restricted")
          .map((cell) => ({
            // The record is Ticket, Restriction, Route -- so the code is the
            // second value in it.
            code: Array.from(cell.querySelectorAll(".feed-record dd")).map((dd) => dd.textContent)[1],
            text: (cell.querySelector(".validity") || {}).textContent || "",
          }));
        fallback.checked = true;
        render();
        if (shown.some((cell) => codes.includes(cell.code))) {
          const found = { mode: wanted, cells: shown };
          setBudget(budgetBefore);
          return found;
        }
      }
      fallback.checked = true;
      render();
      setBudget(budgetBefore);
      currentPage = 1;
      render();
      return { mode: null, cells: [] };
    });
    check(
      "a restricted row prints the validity the feed states for its code",
      !restrictedMode || restrictedMode.mode === null
        ? notExercised(
            restrictedMode ? "no mode on this page lists a fare whose restriction code has validity text" : "this page's feed states no restriction validity"
          )
        : restrictedMode.cells.some((cell) => cell.text.length > 20 && /valid/i.test(cell.text)),
      JSON.stringify(restrictedMode)
    );
    // S23: an absence the feed can name is not a dash.
    const typed = await page.evaluate(() => {
      // Every priced row, not just the ones this budget happens to show: a
      // destination with a fare and no service is the case under test, and it
      // is usually outside a budget set to the cheapest affordable fare.
      setBudget(budgetCeiling());
      currentPage = 1;
      render();
      const row = Array.from(document.querySelectorAll("#rows tr")).find((candidate) => {
        const cell = candidate.querySelector("td.missing");
        return cell && cell.dataset.label === "Time";
      });
      if (!row) return null;
      // The feed's record is in the row's disclosure, and this is the row whose
      // expander has no times to count. The control's face is the shared
      // chevron, so its words live in the accessible name rather than in its
      // text; it exists on every row precisely so that this one has somewhere
      // to put its record.
      const toggle = row.querySelector(".toggle[aria-expanded=false]");
      if (toggle) toggle.click();
      const detail =
        row.nextElementSibling && row.nextElementSibling.classList.contains("detail")
          ? row.nextElementSibling
          : null;
      return {
        cells: Array.from(row.querySelectorAll("td.missing")).map((cell) => cell.textContent),
        record: detail
          ? Array.from(detail.querySelectorAll(".feed-record dd")).map((dd) => dd.textContent)
          : [],
        label: toggle ? toggle.getAttribute("aria-label") || "" : "",
        marked: Boolean(toggle && toggle.querySelector(".chevron")),
      };
    });
    // A no-service row carries the day the page is about when the week reaches
    // the station on another day, so the cell is either the bare words or those
    // words and a weekday. Both are checked against the page's own date rather
    // than against a fixed phrase.
    // The cell is the bare words, or those words and the weekday the page is
    // about, so the allowance is the page's own date rather than a fixed
    // phrase. A row that names a day it runs on is checked against that date
    // below rather than accepted here on the strength of a prefix.
    const serviceWeekday = await page.evaluate(() => {
      if (!DATA.serviceDate) return "";
      const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
      return days[new Date(DATA.serviceDate + "T00:00:00Z").getUTCDay()] || "";
    });
    check(
      "a row with no journey says so, and says it is unknown rather than zero",
      typed
        ? typed.cells.some((text) => /^No (service|timetable)/.test(text)) &&
          typed.cells.includes("Unknown") &&
          typed.record.some((value) => /no service|timetable/i.test(value))
        : notExercised("every destination on this page has a journey"),
      JSON.stringify({ ...typed, serviceWeekday })
    );
    // The row expander's face is the page's shared chevron rather than the word
    // "Fare details", so three things are measured on a rendered row instead of
    // asserted in the source: the mark is really drawn and really is the one
    // the filter bar uses, the words a screen reader needs are still its
    // accessible name, and the control is still a 44px target. A chevron with
    // no name and no size is a control nobody can find or aim at.
    const expander = await page.evaluate(() => {
      setBudget(budgetCeiling());
      currentPage = 1;
      render();
      const row = document.querySelector("#rows tr:not(.detail)");
      const button = row && row.querySelector(".row-expand");
      if (!button) return null;
      const mark = button.querySelector("svg.chevron");
      const filterMark = document.querySelector("#moreFiltersToggle svg.chevron");
      const box = button.getBoundingClientRect();
      const open = button.getAttribute("aria-expanded");
      button.click();
      const opened = button.getAttribute("aria-expanded");
      const rotated = getComputedStyle(button.querySelector("svg.chevron")).transform;
      const panelShown = Boolean(row.nextElementSibling && row.nextElementSibling.classList.contains("detail"));
      button.click();
      return {
        marked: Boolean(mark),
        // The same path in both places, which is the point of one CHEVRON.
        samePath: Boolean(mark && filterMark && mark.innerHTML === filterMark.innerHTML),
        name: button.getAttribute("aria-label") || "",
        w: Math.round(box.width),
        h: Math.round(box.height),
        rotated: rotated !== "none",
        open,
        opened,
        panelShown,
        closedAgain: button.getAttribute("aria-expanded") === "false",
      };
    });
    check(
      "a row expands by a chevron that keeps its words and its target",
      expander
        ? expander.marked &&
          expander.samePath &&
          /details for .+/.test(expander.name) &&
          Math.min(expander.w, expander.h) >= 44 &&
          expander.open === "false" &&
          expander.opened === "true" &&
          expander.rotated &&
          expander.panelShown &&
          expander.closedAgain
        : notExercised("this page lists no rows to expand"),
      JSON.stringify(expander)
    );
    // S20: counts on the chips, the union stated, and a way back to All.
    const facets = await page.evaluate(() => {
      const cap = Number(document.getElementById("budgetNumber").value) * 100;
      // The list the page is showing, from the reader rather than re-derived
      // here: on the opening list that is the composed one, and counting the
      // returns instead would call a correct page wrong.
      const available = TYPES.list();
      return Array.from(document.querySelectorAll(".chipcount")).map((slot) => {
        const value = slot.dataset.countFor;
        return {
          value,
          shown: slot.textContent,
          count: available.filter(
            (destination) => TYPES.price(destination) <= cap &&
              (destination.destinationTypes || [destination.destinationType]).includes(value)
          ).length,
        };
      });
    });
    check(
      "every offered chip counts what it would show",
      facets.length > 0 && facets.every((facet) => facet.shown === `(${facet.count})`),
      JSON.stringify(facets)
    );
    check(
      "the chips say that more than one means any of them",
      /any of them/.test((await page.textContent("#typeRule")) || "")
    );
    const cleared = await page.evaluate(() => {
      const all = document.querySelector('input[name="destinationType"][value="all"]');
      const first = Array.from(document.querySelectorAll('input[name="destinationType"]')).find(
        (candidate) => candidate.value !== "all" && !candidate.closest("label").hidden
      );
      if (!first) return null;
      first.checked = true;
      all.checked = false;
      render();
      const offered = !document.getElementById("clearTypes").hidden;
      document.getElementById("clearTypes").click();
      return { offered, back: all.checked, specific: first.checked };
    });
    check(
      "a selected chip offers a clear-all that returns to All",
      cleared
        ? cleared.offered && cleared.back && !cleared.specific
        : notExercised("this page offers no specific chip"),
      JSON.stringify(cleared)
    );
    // S22: a narrowed search starts again at its first page. This page's own
    // result set is too short to paginate, so the page number is put where a
    // reader with a longer list would have left it and the control is judged on
    // what it does with it.
    const reset = await page.evaluate(() => {
      currentPage = 3;
      const before = currentPage;
      const field = document.getElementById("budgetNumber");
      field.value = String(Math.max(1, Number(field.value) - 1));
      field.dispatchEvent(new Event("input", { bubbles: true }));
      return { before, after: currentPage, status: document.getElementById("pageStatus").textContent };
    });
    check(
      "a narrowed search returns to the first page",
      reset.before === 3 && reset.after === 1,
      JSON.stringify(reset)
    );
    check(
      "and the status re-announces the page and the count",
      // Audit item 12, 9 October 2026: "Page 1 of 2 of 30 results" was two
      // facts sharing one "of" twice, so the page and the count keep one each.
      /^1 of \d+ pages? · \d+ destinations?$/.test(reset.status.trim()),
      reset.status
    );
    // S28: an empty list offers the moves that would fill it, and the first
    // move works when it is taken.
    const recovery = await page.evaluate(() => {
      // The floor, read off the control, not a pound named here. A budget the
      // check picks for itself is a budget the reader cannot necessarily
      // reach, and on a page whose cheapest fare is under it the check was
      // measuring a page that cannot be emptied rather than a page that was
      // wrong: the real Grindleford page prices every outbound single at fifty
      // pence, so a one-pound floor showed all thirteen of them and the empty
      // state below -- with the moves that are its whole purpose -- was
      // unreachable on that page at all.
      const floor = Number(document.getElementById("budget").min);
      setBudget(floor);
      currentPage = 1;
      render();
      if (document.getElementById("empty").hidden) return { actions: [], floor };
      const actions = Array.from(document.querySelectorAll("#empty .toggle")).map((button) => button.textContent);
      const first = document.querySelector("#empty .toggle");
      if (first) first.click();
      return {
        actions,
        rows: document.querySelectorAll("#rows tr").length,
        budget: document.getElementById("budgetNumber").value,
        floor,
      };
    });
    check("an empty list says what would fill it", recovery.actions.length > 0, JSON.stringify(recovery));
    check(
      "and the first move it offers changes the answer",
      recovery.actions.length > 0
        && (recovery.rows > 0 || Number(recovery.budget) > recovery.floor),
      JSON.stringify(recovery)
    );
    await open(facts.affordable);
    // S29: the coverage claim is counted, and the count is on the page. The
    // lead sentence is per mode, so the expected shape is read from the mode
    // the page is actually in rather than pinned to one of them.
    const coverage = (await page.textContent("#feedCoverage")) || "";
    const coverageMode = await page.evaluate(() => document.querySelector('input[name="ticketMode"]:checked').value);
    const COVERAGE_LEAD = {
      cheapest: /each on the cheapest fare of any ticket type the feed prices for it/,
      anytime: /reviewed unrestricted Anytime Day Return fares are available in this mode/,
      single: /displayable outbound single fares are available in this mode/,
      return: /standard-return destinations were found in the feed/,
    };
    check(
      "the page states what it could not show",
      Boolean(COVERAGE_LEAD[coverageMode] && COVERAGE_LEAD[coverageMode].test(coverage)),
      `${coverageMode}: ${coverage}`
    );
    check(
      "including the destinations no type chip can select",
      await page.evaluate(() => {
        const text = document.getElementById("feedCoverage").textContent;
        return DATA.unclassifiedDestinationCount
          ? text.includes(String(DATA.unclassifiedDestinationCount)) &&
            /no reviewed destination type/.test(text)
          : /carries a reviewed type|carries no reviewed destination type/.test(text);
      }),
      coverage
    );
    // 7e. S33: the age of the numbers, beside the numbers. A synthetic feed has
    // no download to date, so the fares sentence is conditional; the timetable
    // sentence is not, and is what the check below judges.
    const fresh = await page.evaluate(() => {
      const line = document.getElementById("freshness");
      const now = new Date();
      const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
      const days = (iso) => Math.round((today - Date.parse(iso + "T00:00:00Z")) / 86400000);
      return {
        shown: !line.hidden,
        text: line.textContent,
        // The page reports what it believes; what it claims is judged out
        // here. A regex literal inside this callback is parsed twice -- once
        // by node and once again from the serialised source in the page --
        // and a doubled escape survives the second parse as a literal
        // backslash, so a word boundary arrives as a backslash and matches
        // nothing. That is not a hypothetical: it is how "downloaded 24
        // September 2026, 4 days old" stopped matching and left a check that
        // could only ever fail, on every real build, for a page that was
        // right. (A single escape is fine, and is used elsewhere in this
        // file; tests/test_build_demo_page.py refuses the doubled kind.)
        feedDate: DATA.feedDate || null,
        staleAfterDays: DATA.staleAfterDays,
        // null rather than false when the build carries no timetable. A
        // prices-only page prints no service window because it has none, and
        // asking it for one is a check that cannot pass on a whole build shape
        // -- the sibling `verdict` below already reads the prices-only sentence
        // as the right answer to its own question. Nothing in this suite had
        // been run against a prices-only page until now, which is the same blind
        // spot ADR-0058 records for a list longer than one page: a case that was
        // never swept cannot fail.
        window: DATA.timetableFrom
          ? new RegExp(humanDate(DATA.timetableFrom) + " to " + humanDate(DATA.timetableTo)).test(line.textContent)
          : null,
        verdict: DATA.timetableFrom
          ? (days(DATA.timetableFrom) < 0
            ? /has not started yet/.test(line.textContent)
            : days(DATA.timetableTo) > 0
              ? /has ended/.test(line.textContent)
              : /includes today/.test(line.textContent))
          : /prices fares only/.test(line.textContent),
        // Finding, 29 September 2026: the count line now sits directly on its
        // table, so the age of the numbers is stated above the count rather
        // than below it. The promise is unchanged -- it is beside the numbers
        // and above the first row, not in the footer -- so what is measured is
        // the company it keeps.
        beforeSummary: Boolean(line.compareDocumentPosition(document.getElementById("summary")) &
          Node.DOCUMENT_POSITION_FOLLOWING),
        beforeTable: Boolean(line.compareDocumentPosition(document.querySelector("table")) &
          Node.DOCUMENT_POSITION_FOLLOWING),
        inFooter: Boolean(line.closest("footer") || line.closest(".method")),
      };
    });
    check("the page says how old its numbers are", fresh.shown && fresh.text.length > 20, fresh.text);
    check(
      "the timetable sentence carries the feed's own service window",
      fresh.window === null
        ? notExercised("this build prices fares only, so there is no service window to print")
        : fresh.window,
      `${fresh.text} (${JSON.stringify(fresh.window)})`
    );
    check("and judges that window against the reader's today", fresh.verdict, fresh.text);
    // 7f. The conditions in the table are the fares feed's own wording; the
    // page says what the portal's own restriction feed was asked and answered.
    // It used to sit above the table. It is in the page's method note now,
    // under "Where these prices come from", because the distillation moved
    // every line of legal and provenance text below the results: a reader
    // choosing between two prices needs the price, the time and the fare type,
    // and the claim about which feed was checked is one of the things that can
    // be looked up rather than read first.
    //
    // The dangerous case is the one that reads best: a build that checked
    // nothing and reported the portal as still publishing every condition. So
    // each branch is judged against what the payload actually holds, and "all"
    // is only accepted when conditions were actually compared.
    const reference = await page.evaluate(() => {
      const line = document.getElementById("restrictionReference");
      const ref = DATA.restrictionReference;
      return {
        shown: line ? !line.hidden : false,
        text: line ? line.textContent : "",
        status: ref ? ref.status : null,
        compared: ref ? ref.compared : null,
        // Collected inside the page: DATA lives in the browser, and reading it
        // out here would be an undefined reference that aborts the whole run
        // rather than failing one check.
        unlisted: ref && ref.unlisted ? ref.unlisted.slice() : [],
        // The codes this page's own rows carry, collected from the page's own
        // data. The check reports on what is here, so the invariant can be
        // asserted here rather than compared against a number this suite would
        // have to be told.
        shownCodes: (() => {
          const codes = new Set();
          for (const key of ["destinations", "singleDestinations", "anytimeDestinations"]) {
            for (const row of DATA[key] || []) {
              // A two-ticket row prints each ticket's condition as well as its
              // own (ADR-0061), so those are on the page too.
              for (const raw of [row.restrictionCode].concat((row.tickets || []).map((t) => t.restrictionCode))) {
                const code = (raw || "").trim().toUpperCase();
                if (code) codes.add(code);
              }
            }
          }
          return [...codes].sort();
        })(),
        above: line
          ? Boolean(line.compareDocumentPosition(document.getElementById("rows")) &
              Node.DOCUMENT_POSITION_FOLLOWING)
          : false,
        // And it lives in the method note, which is the disclosure a reader
        // opens to be told how a number was arrived at.
        inMethod: line
          ? Boolean(line.closest("details.method"))
          : false,
      };
    });
    check(
      "the page says what the reference feed was asked and answered",
      reference.shown && reference.text.length > 20,
      reference.text
    );
    // A freshness claim is worse than no claim if the date in it is broken.
    // The first version sliced the reference feed's HTTP-date header as an ISO
    // timestamp and shipped "published undefined undefined NaN" to a real
    // reader, so the line is checked for the failure rather than for its exact
    // wording, which would break for the wrong reason whenever it improves.
    check(
      "no date in it is unrenderable",
      !/undefined|NaN|\[object|null/.test(reference.text),
      reference.text
    );
    // The portal sends no Last-Modified on these feeds, so the sentence has to
    // read properly with no publication date -- the usual case, not the edge
    // one. Joining a clause that is not there with a comma leaves "restriction
    // feed, still publishes", which is what a reader of the real page saw.
    check(
      "the sentence still reads when the portal gives no publication date",
      !/feed, (still|no longer)\b/.test(reference.text),
      reference.text
    );
    check(
      "and keeps it in the method note, below the results",
      reference.inMethod && !reference.above,
      `${reference.text} (in the method note: ${reference.inMethod}, above the table: ${reference.above})`
    );
    // The invariant is about the WORDED claim, not the status value: a build
    // that compared nothing must not be allowed to read as confirmed. Tested
    // against the sentence a reader actually sees, because that is the thing
    // that can mislead. Deliberately not matched on exact wording -- pinning
    // the check to one phrasing would make it a test of this project's prose
    // rather than of the claim, and would break for the wrong reason whenever
    // the sentence is improved.
    //
    // The claim is publication, never agreement about wording. Run against the
    // real portal feed, comparing the two texts word for word reported 628 of
    // 628 conditions disagreeing on a feed where none did: the portal words a
    // condition in prose where the fares feed compresses it, so a page saying
    // the portal disagrees with everything it quotes is crying wolf, and a
    // reader who sees it once stops reading the rest of the line.
    const claimsAll = /still publishes all/i.test(reference.text);
    check(
      "the portal is only credited with publishing when conditions were compared",
      !claimsAll || reference.compared > 0,
      `${reference.text} (compared: ${reference.compared})`
    );
    // The count has to be the conditions on this page's own rows, not every
    // code the origin's flows could carry. Those differ on the real feed -- 32
    // against 10 -- and a page reporting on conditions it does not show is
    // asking a reader to take on trust the one claim they cannot look up.
    check(
      "the conditions it reports on are the ones this page's rows carry",
      reference.status !== "checked" && reference.status !== "unpublished"
        ? true
        : reference.compared === reference.shownCodes.length,
      `compared: ${reference.compared}, on the page: ${reference.shownCodes.join(", ")}`
    );
    // And when it names a condition the portal has retired, the reader has to
    // be able to find that condition here. A named code the page does not show
    // is an alarm about somebody else's paperwork.
    check(
      "and every condition it names is one the reader can find here",
      reference.unlisted.every((code) => reference.shownCodes.includes(code)),
      `unlisted: ${reference.unlisted.join(", ")}, on the page: ${reference.shownCodes.join(", ")}`
    );
    check(
      "an unchecked reference feed says so rather than reading as confirmation",
      reference.status === "absent" || reference.status === "unknown"
        ? !claimsAll && /not been checked|not checked|could not be checked|no .*feed was checked/i.test(reference.text)
        : true,
      `${reference.text} (status: ${reference.status})`
    );
    // The claim is about publication, so the page must never say the two feeds
    // agree about what a condition *says*. The portal words conditions in prose
    // and the fares feed compresses them; that is not a disagreement and must
    // not be printed as one.
    check(
      "it claims publication rather than agreement about wording",
      !/\bagrees\b|\bdisagrees\b|\bwording matches\b/i.test(reference.text),
      reference.text
    );
    if (reference.status === "unpublished") {
      check(
        "a condition the portal no longer lists is named",
        reference.unlisted.length > 0 &&
          reference.unlisted.every((code) => reference.text.includes(code)),
        `${reference.text} (unlisted: ${reference.unlisted.join(", ")})`
      );
    }
    check(
      "and it sits beside the result count, not in the footer",
      fresh.beforeSummary && fresh.beforeTable && !fresh.inFooter,
      `${fresh.text} beforeSummary=${fresh.beforeSummary} beforeTable=${fresh.beforeTable} inFooter=${fresh.inFooter}`
    );
    if (!fresh.feedDate) {
      // A synthetic feed has no download date, so there is nothing to measure.
      // The sentence that is missing is the honest one: the page does not
      // invent a download for a feed nobody downloaded.
      check("a feed with no download date claims no age for its prices", !/downloaded/.test(fresh.text), fresh.text);
    } else {
      // The number has to be the right number, and the threshold beside it has
      // to be the build's own. "Downloaded 24 September 2026" next to a stale
      // "0 days old" passes a presence test and misleads the reader deciding
      // whether to trust a fare, which is the only reason the sentence is here.
      // One day of slack: the page dates the download against its own clock
      // and so does this, and a run straddling midnight is not a defect.
      const expected = daysSince(fresh.feedDate);
      const stated = /downloaded .*?,\s*(\d+) days? old/.exec(fresh.text);
      const namesTheThreshold = new RegExp(String(fresh.staleAfterDays) + "-day freshness threshold").test(fresh.text);
      check(
        "a feed with a download date says how old its prices are",
        // A download dated after today is a clock or download fault, and the
        // page says so instead of counting negative days; the sentence for
        // that case carries no age and no threshold, so it is answered on its
        // own terms rather than failed for omitting a number it cannot have.
        expected < 0
          ? /dated after today/.test(fresh.text)
          : stated !== null &&
            Math.abs(Number(stated[1]) - expected) <= 1 &&
            namesTheThreshold,
        `${fresh.text} (downloaded: ${fresh.feedDate}, ${expected} day(s) ago, threshold: ${fresh.staleAfterDays})`
      );
    }
}
module.exports = { checkTheFareDetails };
