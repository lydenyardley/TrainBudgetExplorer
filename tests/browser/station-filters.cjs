/**
 * 2. The budget slider, dragged to the floor and back, and 3. the
 * destination-type chips.
 *
 * Both are the refinements, and both are read against the payload rather than
 * against a number written here: the budget the slider is dragged from is the
 * one that reaches every row the page has, and a chip's expectation is
 * composed from the list the current mode shows, so a page that is behaving
 * correctly cannot fail for the shape of its fixture.
 */
const { notExercised } = require("./harness.cjs");
async function driveTheFilters(world) {
  const { page, url, check, notExercised, open, installReader, rows, facts, checkChip, budgetFor, initial } = world;
    // 2. Dragging the budget slider to the floor empties the list. It starts
    // from a budget that reaches every row the page has: a station whose own
    // cheapest fare is a pound has nothing left to drop from that budget, and
    // a drag from a floor to a floor would measure nothing.
    const reachAll = await page.evaluate(() =>
      Math.max(
        Math.ceil(TYPES.cheapest((d) => d.adultPence) / 100),
        Math.ceil(TYPES.dearest((d) => d.adultPence) / 100)
      )
    );
    await open(reachAll);
    const beforeDrag = await rows();
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
    check("a dragged-down budget drops rows", afterDrag < beforeDrag, `${beforeDrag} -> ${afterDrag}`);
    // The floor empties the list, because the floor is zero and no fare is.
    // The check reads the floor off the control rather than naming a budget:
    // a budget the test picks for itself is not one the reader can be shown
    // reaching, and on a page pricing every fare at fifty pence a one-pound
    // floor put thirteen rows in the list and reported them as a defect the
    // page did not have.
    const floored = await page.evaluate(() => {
      if (document.getElementById("empty").hidden) {
        setBudget(Number(document.getElementById("budget").min));
        currentPage = 1;
        render();
      }
      return {
        empty: document.getElementById("empty").hidden === false,
        summary: document.getElementById("summary").textContent,
      };
    });
    check("an empty budget says so rather than showing nothing", floored.empty, JSON.stringify(floored));
    check("the summary counts what is left", /No destinations for up to/.test(floored.summary), floored.summary);
    // S17: the slider has always stopped somewhere the page never said out
    // loud, so a reader could not predict whether a fare at the boundary was
    // included without dragging the control to find out. The figure is read
    // out of the rendered page and compared with the input's own max -- not
    // with the resolver that produced it -- so a note that drifts from the
    // control is what fails.
    const statedStop = () => page.evaluate(() => ({
      max: Number(document.getElementById("budget").max),
      stated: ((document.getElementById("budgetCeiling") || {}).textContent || "").trim(),
    }));
    // The empty-budget check above may have left the page priced for two
    // adults, so the one-adult figure is read from a state this block sets.
    await page.check('input[name="unit"][value="adult"]');
    const oneAdultStop = await statedStop();
    check(
      "the budget control says where it stops, and the figure is the stop",
      oneAdultStop.stated.includes("\u00a3" + oneAdultStop.max + ".00 for one adult"),
      `${oneAdultStop.stated} against a slider that stops at ${oneAdultStop.max}`
    );
    // Two adults double every price, which leaves the order alone and puts
    // the stop at twice as much, so this is where the stated figure is proved
    // to follow the party rather than being written once at build time.
    await page.check('input[name="unit"][value="party"]');
    const twoAdultStop = await statedStop();
    check(
      "and the stated stop follows the party the reader chooses",
      twoAdultStop.stated.includes("\u00a3" + twoAdultStop.max + ".00 for two adults") &&
        twoAdultStop.max > oneAdultStop.max,
      `${twoAdultStop.stated} against ${oneAdultStop.stated} for one adult`
    );
    await page.check('input[name="unit"][value="adult"]');
    // C17, the one state the existing reading cannot reach. Doubling every
    // price leaves an order untouched, so the adult and two-adult readings
    // above cannot tell a page that re-sorts from one that happens to be
    // right. The railcard is the only control that replaces each row's price
    // with a different discount, so it is the only state where a row can move.
    //
    // This page's own feed cannot prove it, and the check says so rather than
    // borrowing a proof it does not have: the discounts here fall in the same
    // order as the fares they come from (measured, two adults, no card to card:
    // 2 17.4 24 44.8 252 -> 1.3 17.4 24 29.8 168), so a sort that ignored the
    // card entirely was measured and passed this state. It is a guard for a
    // feed whose discounts are not uniform, and the tamper that cleared it is
    // recorded so the next reader does not mistake it for a gate.
    const shownPrices = () => page.evaluate(() =>
      Array.from(document.querySelectorAll("#rows tr[data-crs] td.num .price"))
        .map((cell) => Number(cell.textContent.replace(/[^0-9.]/g, "")))
    );
    const ascending = (xs) => xs.every((value, i) => i === 0 || xs[i - 1] <= value);
    // The card is chosen through the same select a reader uses, and the party
    // is set to one the chosen card actually covers, because a card that does
    // not cover the party on screen is taken out of the list rather than priced.
    // The budget is raised to reach a row the chosen card actually lowers.
    // Without that the guard depends on the fixture's numbers: on a page whose
    // only row inside the budget is under the card's minimum fare, the card
    // changes nothing on screen and the guard read "9.5 -> 9.5" and reported a
    // page that does not re-sort.
    const resortable = await page.evaluate(() => {
      const select = document.getElementById("railcardSelect");
      const card = (DATA.railcards || []).find((c) => c.minAdults <= 1 && 1 <= c.maxAdults);
      if (!select || !card) return null;
      document.querySelector('input[name="unit"][value="adult"]').checked = true;
      const lowered = [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations]
        .flat()
        .filter((d) => {
          const entry = (d.railcards || {})[card.key];
          return entry && entry.pricePence !== null && entry.pricePence < d.adultPence;
        });
      if (!lowered.length) return null;
      const dearest = lowered.reduce((high, d) => Math.max(high, d.adultPence), 0);
      setBudget(Math.min(Number(document.getElementById("budget").max), Math.ceil(dearest / 100)));
      select.value = "";
      render();
      return card.key;
    });
    if (resortable) {
      const beforeCard = await shownPrices();
      await page.evaluate((key) => {
        const select = document.getElementById("railcardSelect");
        select.value = key;
        render();
      }, resortable);
      const withCard = await shownPrices();
      check(
        "and the list re-sorts when the railcard replaces every price",
        ascending(withCard) && withCard.join(" ") !== beforeCard.join(" "),
        `${beforeCard.join(" ")} -> ${withCard.join(" ")}`
      );
      await page.evaluate(() => {
        const select = document.getElementById("railcardSelect");
        select.value = "";
        render();
      });
    } else {
      check(
        "and the list re-sorts when the railcard replaces every price",
        notExercised("this feed prices no railcard that lowers a displayed fare for one adult")
      );
    }
    // 3. The destination-type chips narrow the result set and support both
    // exclusive All and multi-select specific types. Every chip is judged
    // against the page's own data in both directions, and the ticket mode is
    // part of that data: a chip belongs to the list the reader is looking at.
    // The budget is the page's own cheapest, because a chip that leaves no
    // rows would pass without proving anything about the filter.
    await open(facts.affordable);
    await checkChip("city", "a type this page offers is offered", "the city chip leaves the priced city destinations");
    await checkChip(
      "seaside",
      "a type this page offers is offered",
      "a coastal destination is reachable without also asking for a city"
    );
    await checkChip("university", "a type this page offers is offered", "a university town is findable by the university facet");
    await checkChip("island", "a facet with no destination here offers no chip", "an island destination is findable by the island facet");
    // A chip the payload says the page carries must be on screen, and one it
    // does not must not be: the two directions are separate checks because
    // they failed separately.
    const carriedTypes = await page.evaluate(() => {
      const types = new Set();
      for (const d of TYPES.list()) for (const type of TYPES.types(d)) types.add(type);
      const chips = Array.from(document.querySelectorAll('input[name="destinationType"]'))
        .map((input) => input.value)
        .filter((value) => value !== "all");
      return {
        carried: [...types].sort(),
        offered: chips.filter((value) => !document.querySelector(`input[name="destinationType"][value="${value}"]`).closest("label").hidden).sort(),
        rendered: chips.sort(),
      };
    });
    // Both directions, because they are different promises: nothing is offered
    // that no destination in this mode carries, and nothing carried is hidden.
    // A type the template never renders is neither offered nor hidden, so it
    // cannot fail the second half.
    check(
      "the offered chips are the ones this mode's destinations carry",
      carriedTypes.offered.every((type) => carriedTypes.carried.includes(type)) &&
        carriedTypes.rendered
          .filter((type) => carriedTypes.carried.includes(type))
          .every((type) => carriedTypes.offered.includes(type)),
      `offered ${carriedTypes.offered.join(", ")}; carried ${carriedTypes.carried.join(", ")}`
    );
    await page.locator('.ticket-filter label').filter({ hasText: "Single" }).click();
    // An advance single is train-specific whatever the feed calls it, so the
    // flag is asserted against the rows the payload says are advance singles in
    // this mode, at this budget -- and against their absence when there are
    // none, so a page cannot pass by never showing one. Finding, 29 September
    // 2026: the sentence moved into the row's own disclosure and the row names
    // its fare in the reader's own words, so what is on the row is the word
    // "Advance" and the sentence is read where a reader now reads it.
    const advance = await page.evaluate(() => {
      const wanted = TYPES.list().filter((d) => d.isAdvance && d.adultPence <= TYPES.cap()).length;
      const rows = Array.from(document.querySelectorAll("#rows tr:not(.detail)"));
      const flagged = rows.filter((row) => {
        const cell = row.querySelector(".fare-type");
        return Boolean(cell) && cell.dataset.kind === "advance";
      });
      const sentences = flagged.map((row) => {
        const toggle = row.querySelector(".toggle[aria-expanded=false]");
        if (toggle) toggle.click();
        const detail =
          row.nextElementSibling && row.nextElementSibling.classList.contains("detail")
            ? row.nextElementSibling
            : null;
        const text = detail ? detail.textContent : "";
        if (toggle) toggle.click();
        return text;
      });
      return { wanted, rows: rows.length, flagged: flagged.length, sentences };
    });
    check(
      "an advance single is flagged on its row, and only when one is shown",
      advance.wanted === 0 ? advance.flagged === 0 : advance.flagged > 0,
      `${advance.wanted} advance singles in this mode at this budget, ${advance.flagged} flagged of ${advance.rows} rows`
    );
    check(
      "and every flagged row says train-specific, one disclosure away",
      advance.flagged === 0
        ? advance.wanted === 0
        : advance.sentences.every((text) => /Advance single/.test(text)),
      `${advance.flagged} flagged; ${(advance.sentences[0] || "").slice(0, 160)}`
    );
    // The chips follow the mode, so the heritage destinations this page has
    // must now be offered, and a page whose only heritage destination was the
    // single just selected must offer it here and not in return mode.
    await checkChip("heritage", "a type this page offers is offered", "the heritage chip leaves the heritage destinations");
    // Which mode a UNESCO property appears in, and what it costs, are facts
    // about the feed: on one of these pages the heritage destinations are
    // returns, on the other they are outbound singles, and a check pinned to
    // either mode can only ever be right about one of them. The check goes to
    // the mode that carries one, raises the budget to reach it, and only
    // accepts a property that the page shows on its first page of results.
    const heritage = await page.evaluate((limit) => {
      for (const mode of ["return", "single", "anytime"]) {
        const list = mode === "single" ? DATA.singleDestinations
          : mode === "anytime" ? DATA.anytimeDestinations : DATA.destinations;
        for (const d of list) {
          if (!TYPES.types(d).includes("heritage") || !(d.heritageSites || []).length) continue;
          const shown = list.filter((x) => x.adultPence <= d.adultPence).slice(0, limit);
          if (shown.some((x) => x.name === d.name)) {
            return { mode, name: d.name, site: d.heritageSites[0], pounds: Math.ceil(d.adultPence / 100) };
          }
        }
      }
      return null;
    }, world.pageSize);
    if (heritage) {
      await page.check('input[name="destinationType"][value="all"]');
      await page.locator(`input[name="ticketMode"][value="${heritage.mode}"]`).check({ force: true });
      await page.fill("#budgetNumber", String(heritage.pounds));
      const heritageText = await page.textContent("#rows");
      // Read the link off the row the payload named rather than the first proof
      // on the page. The station cell's proof span is `.site-proof` since the
      // nature and coastal sublimes joined it (6f1f4ad), and the first proof in
      // `#rows` can belong to a different row than the property under test.
      const heritageHref = await page.evaluate((name) => {
        for (const row of document.querySelectorAll("#rows tr")) {
          const station = row.querySelector(".station-name");
          if (!station || station.textContent.trim() !== name) continue;
          const link = row.querySelector(".site-proof a");
          return link ? link.getAttribute("href") : null;
        }
        return null;
      }, heritage.name);
      check(
        "a heritage row links the UNESCO property the payload names",
        heritageText.includes("World heritage: " + heritage.site.name) && heritageHref === heritage.site.url,
        `${heritage.name} in ${heritage.mode} mode: ${heritage.site.name} ${heritage.site.url}; ${heritageText.slice(0, 160)}`
      );
    } else {
      check(
        "a heritage row links the UNESCO property the payload names",
        notExercised("no destination on this page carries a UNESCO property")
      );
    }
    // 3d. The refinements fold away on every route and at every width, and
    // the reader is the only thing that opens them. Driven the way a reader
    // drives it -- press the control, narrow something, press it again --
    // because a disclosure that only works when it is forced open is not a
    // disclosure. The budget is deliberately outside it: that is the page's
    // question, and a reader should never have to open a drawer to answer it.
    // A fresh navigation, because this is about what the page arrives as.
    await page.goto(url);
    await installReader();
    await page.fill("#budgetNumber", String(facts.affordable));
    const folded = await page.evaluate(() => {
      const details = document.getElementById("moreFilters");
      const toggle = document.getElementById("moreFiltersToggle");
      const budget = document.getElementById("budget");
      const firstRow = document.querySelector("#rows tr");
      return {
        open: details ? details.dataset.open === "true" : null,
        expanded: toggle ? toggle.getAttribute("aria-expanded") : null,
        summaryVisible: toggle ? getComputedStyle(toggle).display !== "none" : false,
        budgetVisible: !!budget && budget.getBoundingClientRect().height > 0,
        resultsVisible: !!firstRow && firstRow.getBoundingClientRect().height > 0,
        state: (document.getElementById("filterState") || {}).textContent || "",
      };
    });
    check("the refinements arrive folded and the plate says so", folded.open === false, JSON.stringify(folded));
    // The plate names what is narrowed, so the name is read off the radio the
    // page arrives with rather than written here: a check that asks for one
    // mode's word fails the moment the page decides to open in another.
    const plateMode = await page.evaluate(() => {
      const checked = document.querySelector('input[name="ticketMode"]:checked');
      return (checked ? checked.closest("label").textContent : "").trim();
    });
    // Labelled, so a reader on a phone who cannot open the panel can still
    // tell which of the three decisions has been made.
    check(
      "and the folded plate says what is narrowed",
      /^Ticket: /.test(folded.state) &&
        folded.state.includes(plateMode) &&
        plateMode.length > 2 &&
        /Travellers: .*adult/.test(folded.state) &&
        /Destination: /.test(folded.state),
      `${JSON.stringify(folded.state)} in ${plateMode}`
    );
    check("the budget stays out of the fold", folded.budgetVisible, JSON.stringify(folded));
    check("the results are on screen without opening anything", folded.resultsVisible, JSON.stringify(folded));
    check("the control that opens them is on screen", folded.summaryVisible, JSON.stringify(folded));
    check(
      "the toggle announces whether the refinements are open",
      folded.open === false ? folded.expanded === "false" : folded.expanded === "true",
      String(folded.expanded)
    );
    if (folded.open === false && folded.summaryVisible) {
      await page.click("#moreFiltersToggle");
      const opened = await page.evaluate(() => {
        const details = document.getElementById("moreFilters");
        const panel = document.getElementById("moreFiltersPanel");
        return {
          open: details.dataset.open === "true",
          expanded: document.getElementById("moreFiltersToggle").getAttribute("aria-expanded"),
          panelVisible: panel.getBoundingClientRect().height > 0,
        };
      });
      check(
        "one tap opens the refinements",
        opened.open === true && opened.expanded === "true" && opened.panelVisible,
        JSON.stringify(opened)
      );
      const chipValue = await page.evaluate(() => {
        // A chip whose count is zero inside the current budget empties the
        // list by design, and the page says so on the chip before the press.
        // This check is about the disclosure keeping whatever the reader
        // narrowed to, so it presses a chip that has something to narrow to;
        // a page where no chip does is reported rather than failed.
        const boxes = Array.from(document.querySelectorAll('#destinationTypes input[type="checkbox"]'));
        const withRows = boxes.filter((box) => {
          const count = document.querySelector(`[data-count-for="${box.value}"]`);
          return count && Number(count.textContent.replace(/\D/g, "")) > 0;
        });
        const input = withRows[0] || boxes[0] || null;
        if (!input) return { pressed: false, rows: 0, label: "", name: "", noneLeft: true };
        const name = input.parentElement.querySelector("span").textContent.trim();
        const before = document.querySelectorAll("#rows tr").length;
        input.click();
        return {
          pressed: input.checked,
          name,
          before,
          // A small page can press a chip and keep every row it had, so the
          // row count is reported rather than asserted: what has to change is
          // the state the reader can see.
          after: document.querySelectorAll("#rows tr").length,
          label: (document.getElementById("filterState") || {}).textContent || "",
        };
      });
      check(
        "a refinement pressed inside the disclosure is applied and says so",
        // The chip took the press, and the summary now names that chip rather
        // than the state it read before the tap.
        !chipValue.noneLeft && chipValue.pressed && chipValue.label.includes(chipValue.name) && chipValue.label !== folded.state,
        JSON.stringify(chipValue)
      );
      await page.click("#moreFiltersToggle");
      const closed = await page.evaluate(() => {
        const details = document.getElementById("moreFilters");
        const row = document.querySelector("#rows tr");
        return {
          open: details.dataset.open === "true",
          rows: document.querySelectorAll("#rows tr").length,
          rowVisible: !!row && row.getBoundingClientRect().height > 0,
          state: (document.getElementById("filterState") || {}).textContent || "",
        };
      });
      check(
        "closing it again keeps the narrowed results",
        closed.open === false && closed.rows > 0 && closed.rowVisible,
        JSON.stringify(closed)
      );
      check("and the summary still names what is narrowed", closed.state.trim().length > 0, closed.state);
      // Put the chips back, then hand the rest of the run a desktop viewport:
      // the checks below exercise every control, which on a phone means
      // opening the disclosure each time, and that is what section 7a is for.
      await page.evaluate(() => {
        for (const input of document.querySelectorAll('#destinationTypes input[type="checkbox"]')) {
          if (input.checked) input.click();
        }
      });
    }
    // 3b. A ticket mode the feed has nothing for says so. An Anytime Day
    // Return is sold on a few interurban routes, so most real origins have
    // none, and the page used to return from render() before it wrote
    // anything: the reader kept the previous mode's rows under a set of
    // destination chips that had all just been hidden, which reads as a
    // broken filter rather than an answer.
    await open(facts.affordable);
    const plan = await page.evaluate(() => {
      const list = {
        return: DATA.destinations,
        single: DATA.singleDestinations,
        anytime: DATA.anytimeDestinations,
      };
      const cap = Number(document.getElementById("budgetNumber").value) * 100;
      const modes = ["return", "single", "anytime"];
      const counts = {};
      const onScreen = {};
      for (const mode of modes) {
        counts[mode] = list[mode].length;
        onScreen[mode] = list[mode].filter((d) => d.adultPence <= cap).length;
      }
      const from = modes.find((mode) => onScreen[mode]) || null;
      if (!from) return null;
      const empty = modes.find((mode) => !counts[mode]);
      if (empty) return { from, to: empty, forced: false, counts };
      // This page priced all three modes, so there is no empty mode to switch
      // to and the branch would go untested. One is emptied here instead, so a
      // page whose feed happens to be complete still drives the path a station
      // with no Anytime fares takes; the mode switched back to is left alone.
      DATA.anytimeDestinations = [];
      return { from, to: "anytime", forced: true, counts: { ...counts, anytime: 0 } };
    });
    if (plan) {
      await page.locator(`input[name="ticketMode"][value="${plan.from}"]`).check({ force: true });
      const budgetBefore = (await page.inputValue("#budgetNumber")).trim();
      const rowsBefore = await page.locator("#rows tr").count();
      await page.locator(`input[name="ticketMode"][value="${plan.to}"]`).check({ force: true });
      const budgetAfter = (await page.inputValue("#budgetNumber")).trim();
      const emptyText = (await page.textContent("#empty")) || "";
      const labels = await page.evaluate(() => {
        const found = {};
        for (const input of document.querySelectorAll('input[name="ticketMode"]')) {
          found[input.value] = input.parentElement.textContent.trim();
        }
        return found;
      });
      const offeredHere = Object.entries(plan.counts)
        .filter(([other, count]) => other !== plan.to && count);
      check(
        "a mode with no fares clears the table rather than leaving the last mode's rows",
        rowsBefore > 0 && (await page.locator("#rows tr").count()) === 0,
        `${rowsBefore} ${plan.from}-mode rows before, ${await page.locator("#rows tr").count()} in the empty ${plan.to} mode`
      );
      check(
        "a mode with no fares says so, and says where the fares are",
        (await page.locator("#empty").isVisible()) &&
          emptyText.startsWith(`No ${labels[plan.to]} fares were found from ${facts.origin}`) &&
          offeredHere.every(([other, count]) =>
            emptyText.includes(labels[other]) && emptyText.includes(String(count))),
        `${labels[plan.to]}: ${emptyText.slice(0, 240)}; the other modes are ${offeredHere.map(([o, n]) => `${labels[o]} ${n}`).join(", ") || "empty too"}`
      );
      check(
        "an empty mode leaves the budget alone",
        budgetAfter === budgetBefore,
        `${budgetBefore} -> ${budgetAfter}`
      );
      // All is the unfiltered state and stays offered in every mode; what an
      // empty mode must not offer is a type that nothing in it carries.
      const chipLabels = await page.locator("#destinationTypes label").evaluateAll((labels) =>
        labels
          .filter((label) => !label.hidden)
          .map((label) => label.querySelector("input"))
          .filter((input) => input && input.value !== "all")
          .map((input) => input.value)
      );
      check(
        "an empty mode offers no destination-type chip to press",
        chipLabels.length === 0,
        `offered: ${chipLabels.join(", ") || "none"}`
      );
      await page.locator(`input[name="ticketMode"][value="${plan.from}"]`).check({ force: true });
      check(
        "and switching back to a priced mode restores its list",
        (await page.locator("#rows tr").count()) > 0 && !(await page.locator("#empty").isVisible()),
        `${await page.locator("#rows tr").count()} rows back in ${plan.from} mode` +
          (plan.forced ? " (the empty mode was forced: this page priced all three)" : "")
      );
    } else {
      check(
        "a mode with no fares clears the table rather than leaving the last mode's rows",
        false,
        "this page shows no rows in any mode at this budget, so the empty-mode case cannot be exercised on it"
      );
    }
    // Back to returns for the rest of the step, on a page that has not been
    // left holding the previous step's mode, budget and filters.
    await open(facts.affordable);
    // A class that costs more than the page's opening budget is only worth
    // looking at with the budget raised, and the budget that shows every row of
    // the class is worked out from the payload rather than written down.
    const smallTownBudget = await budgetFor("small_town");
    if (smallTownBudget) {
      await page.fill("#budgetNumber", String(smallTownBudget));
      const smallTown = await checkChip(
        "small_town",
        "a type this page offers is offered",
        "a small town is its own class, not a town"
      );
      const smallTownText = await page.textContent("#rows");
      check(
        "and it is not folded into the towns",
        smallTown.rows.every((d) => !(d.destinationTypes || []).includes("town")) && smallTown.rows.length > 0,
        `${smallTown.rows.length} small towns, ${smallTownText.slice(0, 160)}`
      );
    } else {
      check(
        "a small town is its own class, not a town",
        notExercised("this page has no small town in return mode")
      );
    }
    await page.fill("#budgetNumber", String(facts.affordable));
    // Multi-select, on whichever two types the page carries: the two sets can
    // overlap -- a station can be coastal and a university town -- so the union
    // is worked out from the data rather than by adding the two counts.
    const pair = carriedTypes.offered.slice(0, 2);
    if (pair.length === 2) {
      await page.check(`input[name="destinationType"][value="${pair[0]}"]`);
      await page.check(`input[name="destinationType"][value="${pair[1]}"]`);
      const unionRows = await rows();
      const expectedUnion = await page.evaluate((types) =>
        TYPES.list().filter(
          (d) => TYPES.types(d).some((t) => types.includes(t)) && d.adultPence <= TYPES.cap()
        ).length
      , pair);
      check(
        "specific destination chips are multi-select and union their matches",
        (await page.locator(`input[name="destinationType"][value="${pair[0]}"]`).isChecked()) &&
          (await page.locator(`input[name="destinationType"][value="${pair[1]}"]`).isChecked()) &&
          unionRows === Math.min(expectedUnion, world.pageSize),
        `${pair.join(" + ")} -> ${unionRows}; expected ${Math.min(expectedUnion, world.pageSize)}`
      );
      await page.uncheck(`input[name="destinationType"][value="${pair[1]}"]`);
      await page.uncheck(`input[name="destinationType"][value="${pair[0]}"]`);
    } else {
      check(
        "specific destination chips are multi-select and union their matches",
        notExercised(`this page offers ${pair.length} specific chip(s), so multi-select cannot be exercised`)
      );
    }
    // The chips this page offers, left for the railcard section below: it reads
    // whether a facet was offered at all, not which one.
    world.pair = pair;
    await page.check('input[name="destinationType"][value="all"]');
    // Judged over every chip the page rendered, not one of them by name: a
    // check that watched the city chip alone passed on a page with no city.
    const exclusivity = await page.evaluate(() => ({
      all: document.querySelector('input[name="destinationType"][value="all"]').checked,
      also: Array.from(document.querySelectorAll('input[name="destinationType"]'))
        .filter((input) => input.value !== "all" && input.checked)
        .map((input) => input.value),
    }));    check("All is checked exclusively",
      exclusivity.all && exclusivity.also.length === 0,
      `all ${exclusivity.all}; also checked: ${exclusivity.also.join(", ") || "none"}`
    );
    check("clearing the type filter restores the list", (await rows()) === initial);
    // C20: a facet present in only one mode used to be silently unchecked when
    // the mode changed, and switching back showed "All" with no explanation.
    // The selection is now kept per mode, and a change is announced. Both are
    // checked here, on whatever modes this page actually carries chips for.
    // C17 and C20 each start from a fresh load: both drive the ticket-mode
    // radios, and leaving a mode or a party selected behind them would make a
    // later check read a page state it did not ask for.
    await open();
    const chipInMode = await page.evaluate(() => {
      // Which chips does each mode offer? A chip the reader can pick has to be
      // offered by the mode they pick it in; the mode it is then compared
      // against is one that cannot carry it, because that is the only situation
      // where it is dropped. A mode with fares is preferred for that second
      // role because it is the harder case -- an empty mode drops everything
      // anyway -- but a mode with no fares at all is what most real stations
      // actually have for Anytime Day Return, so it is used when nothing else
      // will do rather than reported as a check this page cannot make.
      const MODES = ["return", "single", "anytime"];
      const rowsFor = (mode) => {
        const list = { return: "destinations", single: "singleDestinations", anytime: "anytimeDestinations" }[mode];
        return (DATA[list] || []).length;
      };
      const switchable = MODES.filter((mode) => document.querySelector(`input[name="ticketMode"][value="${mode}"]`));
      if (switchable.length < 2) return [];
      const original = document.querySelector('input[name="ticketMode"]:checked').value;
      const offered = {};
      for (const mode of switchable) {
        document.querySelector(`input[name="ticketMode"][value="${mode}"]`).checked = true;
        render();
        offered[mode] = new Set(activeDestinations().flatMap((x) => x.destinationTypes || [x.destinationType]));
      }
      document.querySelector(`input[name="ticketMode"][value="${original}"]`).checked = true;
      render();
      const out = [];
      for (const input of document.querySelectorAll('input[name="destinationType"]')) {
        if (input.value === "all") continue;
        const home = switchable.find((m) => rowsFor(m) && offered[m].has(input.value));
        if (!home) continue;
        const away = switchable.find((m) => m !== home && rowsFor(m) && !offered[m].has(input.value)) ||
          switchable.find((m) => m !== home && !offered[m].has(input.value));
        if (away) out.push({ value: input.value, home, away });
      }
      return out;
    });
    if (chipInMode.length) {
      const chip = chipInMode[0];
      await page.locator(`input[name="ticketMode"][value="${chip.home}"]`).check({ force: true });
      await page.check(`input[name="destinationType"][value="${chip.value}"]`);
      await page.locator(`input[name="ticketMode"][value="${chip.away}"]`).check({ force: true });
      const notice = ((await page.textContent("#facetNotice").catch(() => "")) || "").trim();
      // The notice names the facet the way the reader knows it -- the chip's
      // own label, without its count -- so that is what is looked for.
      const chipLabel = ((await page.locator(`input[name="destinationType"][value="${chip.value}"]`)
        .evaluate((el) => el.closest("label")?.textContent || "")).replace(/\(\d+\)/, "")).trim();
      check(
        "switching ticket mode says a filter was cleared",
        notice.startsWith("Cleared ") && notice.includes(chipLabel),
        JSON.stringify({ notice, chipLabel, chip })
      );
      await page.locator(`input[name="ticketMode"][value="${chip.home}"]`).check({ force: true });
      check(
        "and switching back restores the filter the reader had",
        await page.isChecked(`input[name="destinationType"][value="${chip.value}"]`),
        `${chip.value} checked again in ${chip.home}`
      );
    } else {
      check("switching ticket mode says a filter was cleared",
        notExercised("every chip this page offers is offered by every mode it can switch to"));
      check("and switching back restores the filter the reader had", notExercised("see above"));
    }
    await page.check('input[name="destinationType"][value="all"]');
    // C17: the order follows the price actually on screen, which is not the
    // standard fare once the party or the railcard changes it. Read in both
    // states, because the defect was only visible in one of them. The order is
    // stated in the count line instead of by tinting a row: a page that will not
    // say which fare is best cannot say it with a colour either. The tint is
    // judged as paint rather than as a class name, so a row that is highlighted
    // by any rule at all is caught.
    await open();
    const orderState = () => page.evaluate(() => {
      const shown = Array.from(document.querySelectorAll("#rows tr[data-crs]"));
      return {
        // The price is its own span, because the cell can also carry the
        // standard fare a discount was taken from (Q3); reading the whole
        // cell would read two numbers as one.
        prices: shown.map((r) => Number(r.querySelector("td.num .price").textContent.replace(/[^0-9.]/g, ""))),
        paints: Array.from(new Set(shown.map((r) => getComputedStyle(r.querySelector("td") || r).backgroundColor))),
        words: (document.getElementById("summary") || {}).textContent || "",
      };
    });
    const adultOrder = await orderState();
    await page.check('input[name="unit"][value="party"]');
    const partyOrder = await orderState();
    const sortedAscending = (xs) => xs.every((v, i) => i === 0 || xs[i - 1] <= v);
    check(
      "the rows are ordered by the price on screen, not by the feed's order",
      sortedAscending(adultOrder.prices) && sortedAscending(partyOrder.prices),
      `adult ${JSON.stringify(adultOrder.prices.slice(0, 4))}; party ${JSON.stringify(partyOrder.prices.slice(0, 4))}`
    );
    // No row carries a tint now, so the check is the absence: a page that
    // tints the cheapest row and says nothing is recommending with a colour.
    // The order is judged in the count line's own words, which is where it is
    // stated, and where an empty list has nothing to state.
    const onePaint = (s) => s.paints.length <= 1;
    const saysOrder = (s) => s.prices.length === 0 || /cheapest first/i.test(s.words);
    check(
      "no row is painted differently from the rest",
      onePaint(adultOrder) && onePaint(partyOrder),
      `adult rows painted ${JSON.stringify(adultOrder.paints)}, ` +
        `two adults ${JSON.stringify(partyOrder.paints)}`
    );
    check(
      "and the count line says the list is cheapest first",
      saysOrder(adultOrder) && saysOrder(partyOrder),
      JSON.stringify(adultOrder.words)
    );
    await page.check('input[name="unit"][value="adult"]');
    // C09: the copied journey carries the ticket mode, so a handoff to a
    // seller cannot silently become a different ticket. Read from the page's
    // own journeyText() rather than from a clipboard, which the context denies.
    // The counts come from the payload rather than from the page's modeCount(),
    // which is not a global: one list per mode is the same fact the page reads.
    await open();
    const modeHasRows = await page.evaluate(() => ({
      return: (DATA.destinations || []).length,
      single: (DATA.singleDestinations || []).length,
      anytime: (DATA.anytimeDestinations || []).length,
    }));
    const copyForMode = async (mode) => {
      await page.locator(`input[name="ticketMode"][value="${mode}"]`).check({ force: true });
      return page.evaluate(() => journeyText(TYPES.list()[0] || { name: "X", crs: "XXX" }));
    };
    // The default is read off the checked radio rather than written here, so a
    // change to which mode the page opens in cannot leave this block asserting
    // against a mode the page never opens in.
    const defaultMode = await page.evaluate(() => document.querySelector('input[name="ticketMode"]:checked').value);
    const secondMode = ["return", "single", "anytime"].find((m) => modeHasRows[m] && m !== defaultMode);
    if (secondMode) {
      const copied = await copyForMode(secondMode);
      // The expected name is read off the mode's own visible label, not from
      // the page's modeLabels() helper: journeyText() builds its line with that
      // same helper, so comparing the two would pass on any string at all --
      // including a label of "" or one carrying a row count.
      const visibleLabel = async (mode) =>
        (((await page.locator(`input[name="ticketMode"][value="${mode}"]`)
          .evaluate((el) => el.closest("label")?.textContent || "")) || "").trim());
      const expected = await visibleLabel(secondMode);
      const otherLabel = await visibleLabel(defaultMode);
      const ticketLine = (copied.split("\n").find((line) => line.startsWith("Ticket: ")) || "").trim();
      check(
        "the copied journey names the ticket type the reader chose",
        expected.length > 2 && ticketLine === "Ticket: " + expected && expected !== otherLabel,
        JSON.stringify({ ticketLine, expected, otherLabel, secondMode })
      );
    } else {
      check("the copied journey names the ticket type the reader chose", notExercised("no second mode on this page has a row"));
    }
    // The next section reads the ticket link off the first row, so the page is
    // handed back in the default state rather than in whatever ticket mode the
    // C09 check happened to be in.
    await open();
    await page
      .locator(`input[name="ticketMode"][value="${defaultMode}"]`)
      .check({ force: true })
      .catch(() => {});
    // Q4: in the cheapest list the reader chose a price rather than a ticket
    // type, so the handoff text has to name the fare the row is priced as --
    // "Ticket: Cheapest of any type" is what they picked, and it is not what a
    // seller needs to hear. Driven from the page's opening mode, which is the
    // one this is about: the check above left the page in a named set.
    const cheapestCopy = await page.evaluate(() => {
      const rows = Array.from(document.querySelectorAll("#rows tr[data-crs]"));
      const line = rows[0];
      if (!line) return null;
      const crs = line.dataset.crs;
      const destination = TYPES.list().find((d) => d.crs === crs);
      if (!destination) return null;
      const text = journeyText(destination);
      // The fare name is composed here from the row's own quality phrase, so
      // the check is not the page's own ticketName() agreeing with itself.
      const want = destination.isAdvance
        ? "Advance single"
        : destination.quality === "unrestricted Anytime Day Return"
          ? "Unrestricted Anytime Day Return"
          : destination.quality === "outbound single"
            ? "Standard outbound single"
            : "Standard return";
      return {
        crs,
        want,
        mode: document.querySelector('input[name="ticketMode"]:checked').value,
        ticketLine: (text.split("\n").find((entry) => entry.startsWith("Ticket: ")) || "").trim(),
        modeLabel: (document.querySelector('input[name="ticketMode"]:checked').closest("label").textContent || "").trim(),
      };
    });
    check(
      "and a row in the cheapest list hands over the fare it is priced as",
      cheapestCopy
        ? cheapestCopy.mode === "cheapest" &&
          cheapestCopy.ticketLine === "Ticket: " + cheapestCopy.want &&
          cheapestCopy.ticketLine !== "Ticket: " + cheapestCopy.modeLabel
        : notExercised("this page has no row to copy"),
      JSON.stringify(cheapestCopy)
    );
}
module.exports = { driveTheFilters };
