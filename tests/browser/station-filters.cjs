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
  const { page, url, check, notExercised, open, installReader, rows, facts, checkChip, budgetFor, initial, revealType } = world;
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
        STATE.page = 1;
        render();
      }
      const lead = document.querySelector("#empty p");
      const table = document.getElementById("rows").closest("table");
      const head = table.querySelector("thead");
      return {
        empty: document.getElementById("empty").hidden === false,
        summary: document.getElementById("summary").textContent,
        lead: lead ? lead.textContent : "",
        // The table scaffold, and the seven column names over it.
        tableHidden: table.hidden === true,
        headPainted: Boolean(head && head.getBoundingClientRect().height),
        sentenceCount: (document.body.innerText.match(/No destinations for up to/g) || []).length,
        doors: Array.from(document.querySelectorAll("#empty button")).map((b) => b.textContent),
      };
    });
    check("an empty budget says so rather than showing nothing", floored.empty, JSON.stringify(floored));
    check("the summary counts what is left", /No destinations for up to/.test(floored.summary), floored.summary);
    // DS1 of the 19 October 2026 distill pass: the sentence has one owner. The
    // count line is the live region, so it keeps it; the block below carries
    // only the way out, and the empty table and its headings stand down rather
    // than drawing seven column names over no rows.
    check(
      "and the sentence is said once, in the count line rather than twice",
      floored.sentenceCount === 1 && !/^No destinations for up to/.test(floored.lead),
      JSON.stringify({ summary: floored.summary, lead: floored.lead, count: floored.sentenceCount })
    );
    check(
      "and no table or column headings are left over an empty list",
      floored.tableHidden && !floored.headPainted,
      JSON.stringify({ tableHidden: floored.tableHidden, headPainted: floored.headPainted })
    );
    // DL2 of the 19 October 2026 delight pass: the door says what it unlocks.
    // "£7.00 reaches SLEAFORD" is proof that pressing it shows something; the
    // button keeps its own verb as its name.
    check(
      "and the door names the place the raised budget reaches",
      /£[0-9.,]+ reaches /.test(floored.lead) && floored.doors.some((door) => /^Raise the budget to £/.test(door)),
      JSON.stringify({ lead: floored.lead, doors: floored.doors })
    );
    // S3 of the 19 October 2026 critique: three of the four doors at £0 changed
    // the ticket set and left the budget at £0, so each promised a set and
    // delivered another empty list. Each one now names the cheapest fare that
    // set holds and sets the budget to it, so the check is that promise: press
    // it, and hold the floor on the label against the price the page actually
    // shows and the budget the count line actually states.
    const setDoors = await page.evaluate(() => {
      const openedMode = ticketMode();
      const reset = () => {
        setBudget(Number(document.getElementById("budget").min));
        chooseMode(openedMode);
      };
      reset();
      const labels = Array.from(document.querySelectorAll("#empty button"))
        .map((button) => button.textContent)
        // "Show all destination types" is a filter door, not a ticket set.
        .filter((label) => /^Show (?!all )/.test(label));
      const doors = [];
      for (const label of labels) {
        reset();
        // Re-read each time: pressing a door rebuilds the empty state it sat
        // in, so the node that was read a moment ago is no longer on the page.
        const button = Array.from(document.querySelectorAll("#empty button"))
          .find((candidate) => candidate.textContent === label);
        if (!button) continue;
        button.click();
        const shown = Array.from(document.querySelectorAll("#rows tr[data-crs]"));
        const price = shown.length ? shown[0].querySelector("td.num .price") : null;
        doors.push({
          label,
          mode: ticketMode(),
          rows: shown.length,
          price: price ? price.textContent.trim() : "",
          summary: document.getElementById("summary").textContent,
          // The budget the door set, because the door names a floor and the
          // page's whole-pound budget is what the count line reports.
          budget: STATE.budget,
        });
      }
      // The same doors pressed by a reader who has already been in the set they
      // name, at £0: that mode remembers 0, and a door that only switched the
      // filter would be overruled by the clamp and land on the empty list it
      // promised to leave. The visit is the reader's own gesture -- the mode
      // chip, the budget down, the chip back.
      const revisited = [];
      for (const door of doors) {
        reset();
        chooseMode(door.mode);
        setBudget(Number(document.getElementById("budget").min));
        render();
        reset();
        const button = Array.from(document.querySelectorAll("#empty button"))
          .find((candidate) => candidate.textContent === door.label);
        if (!button) continue;
        button.click();
        revisited.push({
          label: door.label,
          rows: document.querySelectorAll("#rows tr[data-crs]").length,
          budget: STATE.budget,
        });
      }
      reset();
      return { openedMode, doors, revisited };
    });
    // The door's own promise, in pence: the figure between "from" and the
    // scope clause.
    const promisedPence = (label) => {
      const match = / from £([0-9.]+) \(/.exec(label);
      return match ? Math.round(Number(match[1]) * 100) : null;
    };
    const brokenDoors = setDoors.doors.filter((door) => {
      const promised = promisedPence(door.label);
      const shown = Math.round(Number(door.price.replace(/[^0-9.]/g, "")) * 100);
      return (
        door.rows < 1 ||
        promised === null ||
        // The cheapest row the door produces is the price the door named.
        promised !== shown ||
        // The budget it set is the whole pound above that floor, so the count
        // line says the number the door promised and no other.
        Math.ceil(promised / 100) !== door.budget ||
        !door.summary.includes("for up to £" + Number(door.budget).toFixed(2)) ||
        // A door that leaves the reader in the set they were already in has
        // changed nothing.
        door.mode === setDoors.openedMode
      );
    });
    check(
      "and every ticket-set door lands on the set it names, at the price it names",
      setDoors.doors.length === 0
        ? notExercised("this page offers no ticket-set door at an empty budget")
        : brokenDoors.length === 0,
      JSON.stringify({ openedMode: setDoors.openedMode, broken: brokenDoors, doors: setDoors.doors })
    );
    const stuckDoors = setDoors.revisited.filter((door) => {
      const promised = promisedPence(door.label);
      return (
        promised === null ||
        door.rows < 1 ||
        Math.ceil(promised / 100) !== door.budget
      );
    });
    check(
      "and a door still lands when its set is the last one the reader looked at",
      setDoors.revisited.length === 0
        ? notExercised("this page offers no ticket-set door at an empty budget")
        : stuckDoors.length === 0,
      JSON.stringify(stuckDoors)
    );
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
    // DL1 and OV2 of the 19 October 2026 passes: the drag answers in places. The
    // threshold is computed from the page's own list and the party on screen,
    // not from a name written here, so a page that is behaving correctly cannot
    // fail for the shape of its fixture. The gesture is driven as a reader's
    // pointer drives it -- pointerdown, input, change -- because the line is the
    // gesture's own remark and only a real one produces it.
    const crossing = await page.evaluate(() => {
      const types = new Set(STATE.types);
      const admitted = (d) => !types.size || TYPES.types(d).some((type) => types.has(type));
      const prices = TYPES.list().filter(admitted).map((d) => TYPES.priceOf(d));
      const cheapest = prices.reduce((low, price) => Math.min(low, price), Infinity);
      if (!Number.isFinite(cheapest)) return null;
      // The budget is whole pounds, so the first budget that shows anything is
      // the cheapest fare rounded up. The threshold the drag names is the next
      // fare above *that* budget, not the second fare in the list: two fares can
      // round to the same pound.
      const at = Math.ceil(cheapest / 100);
      const above = prices.filter((price) => price > at * 100);
      const next = above.reduce((low, price) => Math.min(low, price), Infinity);
      if (!Number.isFinite(next)) return null;
      return {
        at,
        price: next,
        names: TYPES.list().filter((d) => admitted(d) && TYPES.priceOf(d) === next).map((d) => d.name),
      };
    });
    if (crossing) {
      // A drag with rows on the page, which is the state the line is for: at a
      // floor the empty state already names the same place, and the page says so
      // once.
      await page.fill("#budgetNumber", String(crossing.at));
      await page.evaluate((value) => {
        const slider = document.getElementById("budget");
        slider.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
        slider.value = String(value);
        slider.dispatchEvent(new Event("input", { bubbles: true }));
      }, crossing.at);
      const amount = "£" + (crossing.price / 100).toFixed(2);
      // Waiting for a non-empty line is not enough: the previous gesture's
      // settle sentence is still on the page. The frame this drag queued is the
      // one that says what the next fare buys, so the line is read at that
      // sentence rather than at whatever was there.
      const during = await page.waitForFunction(
        (prefix) => document.getElementById("budgetNext").textContent.trim().startsWith(prefix),
        amount + " adds ",
        { timeout: 3000 }
      ).then(async () => page.evaluate(() => ({
        text: document.getElementById("budgetNext").textContent.trim(),
        hidden: document.getElementById("budgetNext").hidden,
      }))).catch(() => page.evaluate(() => ({
        text: document.getElementById("budgetNext").textContent.trim(),
        hidden: document.getElementById("budgetNext").hidden,
      })));
      check(
        "a drag names the next fare and the place it adds",
        !during.hidden && during.text.startsWith(amount + " adds ") &&
          (crossing.names.length === 1
            ? during.text.includes(crossing.names[0])
            : new RegExp("^£[0-9.,]+ adds " + crossing.names.length + " places\\.$").test(during.text)),
        JSON.stringify({ during, expected: { amount, names: crossing.names } })
      );
      // The release is the second half: the same gesture crosses the threshold
      // and lets go, so what it says is what the new budget gained.
      const enough = Math.ceil(crossing.price / 100);
      await page.evaluate((value) => {
        const slider = document.getElementById("budget");
        slider.value = String(value);
        slider.dispatchEvent(new Event("input", { bubbles: true }));
        slider.dispatchEvent(new Event("change", { bubbles: true }));
      }, enough);
      const settled = await page.evaluate(() => document.getElementById("budgetNext").textContent.trim());
      // The figure is the difference between the two lists, composed from the
      // payload rather than read off the page's own function: a gain measured
      // from the wrong side of the pound would read as a plausible sentence.
      const gained = await page.evaluate((values) => {
        const types = new Set(STATE.types);
        const admitted = (d) => !types.size || TYPES.types(d).some((type) => types.has(type));
        const count = (pence) => TYPES.list().filter(
          (d) => admitted(d) && TYPES.priceOf(d) <= pence).length;
        return count(values.to * 100) - count(values.from * 100);
      }, { from: crossing.at, to: Math.ceil(crossing.price / 100) });
      const wantedGain = gained === 1 ? "One place added." : gained + " places added.";
      check(
        "and on release it says what the new budget gained",
        gained > 0 && settled === wantedGain,
        `${settled} (expected ${wantedGain} from ${JSON.stringify({ from: crossing.at, price: crossing.price })})`
      );
      // Back to a budget that reaches every row, so the checks after this one
      // read the list they were written for.
      const ceilingNow = await page.evaluate(() => budgetCeiling());
      await page.fill("#budgetNumber", String(ceilingNow));
    } else {
      check("a drag names the next fare and the place it adds", notExercised("this page has no next fare to name"));
      check("and on release it says what the new budget gained", notExercised("no next fare to reach"));
    }
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
    // OV4 of the 19 October 2026 overdrive pass: the budget keeps a rail at the
    // top of the screen once its own slider has scrolled away, so a reader at
    // row 40 changes it without scrolling back. The state is driven by a real
    // scroll, and every reading follows two frames, because the observer
    // reports on the next one rather than during this one.
    const railState = () => page.evaluate(() => {
      const rail = document.getElementById("budgetRail");
      const slider = document.getElementById("budget");
      if (!rail) return null;
      const box = rail.getBoundingClientRect();
      return {
        hidden: rail.hidden,
        height: Math.round(box.height),
        top: Math.round(box.top),
        railValue: document.getElementById("railBudget").value,
        now: document.getElementById("railNow").textContent,
        stop: document.getElementById("railStop"),
        stated: document.getElementById("budgetHint").textContent,
        inlineVisible: slider.getBoundingClientRect().bottom > 0,
        inert: document.getElementById("railBudget").offsetParent === null,
      };
    });
    const settleFrame = () => page.evaluate(() => new Promise((done) =>
      requestAnimationFrame(() => requestAnimationFrame(done))));
    const budgetBeforeRail = await page.evaluate(() => STATE.budget);
    const atTop = await railState();
    check(
      "the budget's rail is not offered while its own slider is on screen",
      atTop && atTop.hidden && atTop.inlineVisible && atTop.inert,
      JSON.stringify(atTop)
    );
    // A slider below the fold has not been scrolled past. "Not intersecting"
    // is true both for a control the reader has passed and for one they have
    // not reached yet, and reading only that raised the rail at the very top of
    // a 304px page whose slider sat under the fold: the rail's own ceiling note
    // then sat over the theme control and took the click meant for it (25
    // October 2026, where the accessibility matrix waited thirty seconds on that
    // click and stopped the page). The window is made short enough here that the
    // slider is off the bottom of the screen, which is the state a zoomed reader
    // reaches on a page with a taller heading than this fixture's.
    const readingViewport = page.viewportSize() || { width: 1280, height: 720 };
    await page.setViewportSize({ width: 304, height: 240 });
    await page.evaluate(() => window.scrollTo(0, 0));
    await settleFrame();
    const belowFold = await page.evaluate(() => {
      const rail = document.getElementById("budgetRail");
      const slider = document.getElementById("budget").getBoundingClientRect();
      const toggle = document.getElementById("themeToggle");
      const box = toggle ? toggle.getBoundingClientRect() : null;
      const hit = box && box.bottom > 0 && box.top < window.innerHeight
        ? document.elementFromPoint(Math.round(box.left + box.width / 2), Math.round(box.top + box.height / 2))
        : null;
      return {
        sliderTop: Math.round(slider.top),
        fold: window.innerHeight,
        belowFold: slider.top >= window.innerHeight,
        hidden: rail.hidden,
        inert: document.getElementById("railBudget").offsetParent === null,
        // What the reader's click on the theme control would actually reach.
        covered: Boolean(hit && toggle && !toggle.contains(hit)),
        reach: hit ? (hit.id || hit.className || hit.tagName) : null,
      };
    });
    check(
      "and a slider below the fold has not been scrolled past, so its rail stays away",
      !belowFold.belowFold
        ? notExercised("this page's slider is above the fold even at 240px, so there is no passed-or-not state to read")
        : belowFold.hidden && belowFold.inert && !belowFold.covered,
      JSON.stringify(belowFold)
    );
    await page.setViewportSize(readingViewport);
    await settleFrame();
    await page.evaluate(() => window.scrollTo(0, Math.round(document.body.scrollHeight / 2)));
    await settleFrame();
    const away = await railState();
    check(
      "and scrolling past the slider brings the budget back in a 56px rail",
      away && !away.hidden && away.height === 56 && away.top === 0 && !away.inlineVisible,
      JSON.stringify(away)
    );
    check(
      "and the rail keeps the figure without repeating the control's stop sentence",
      away && away.stop === null && away.now === "\u00a3" + budgetBeforeRail,
      JSON.stringify(away && { stop: away.stop, now: away.now })
    );
    const beforeRail = await page.evaluate(() => document.getElementById("summary").textContent);
    const railed = await page.evaluate(() => {
      const slider = document.getElementById("railBudget");
      const want = Math.max(0, STATE.budget - 5);
      slider.value = String(want);
      slider.dispatchEvent(new Event("input", { bubbles: true }));
      slider.dispatchEvent(new Event("change", { bubbles: true }));
      return {
        budget: STATE.budget,
        inline: document.getElementById("budgetNumber").value,
        now: document.getElementById("railNow").textContent,
        address: window.location.search,
      };
    });
    const afterRail = await page.evaluate(() => document.getElementById("summary").textContent);
    // A page that prices nothing has no list for the budget to move, and its
    // table is too short to scroll under the rail: both of the next two checks
    // need rows, and skelmersdale-bus has none (21 October 2026).
    const railRows = await page.evaluate(() => document.querySelectorAll("#rows tr[data-crs]").length);
    check(
      "and dragging the rail moves the search rather than a copy of it",
      railRows === 0
        ? notExercised("this page prices no destination, so the budget moves no list")
        : railed.now === "\u00a3" + railed.budget && railed.inline === String(railed.budget) &&
          afterRail !== beforeRail &&
          afterRail.includes("up to \u00a3" + railed.budget + ".00") &&
          railed.address.includes("budget=" + railed.budget),
      JSON.stringify({ railed, beforeRail, afterRail })
    );
    const stuckHeadings = await page.evaluate(() => {
      const rail = document.getElementById("budgetRail").getBoundingClientRect();
      const th = document.getElementById("rows").closest("table").querySelector("thead th");
      return { railBottom: Math.round(rail.bottom), thTop: Math.round(th.getBoundingClientRect().top) };
    });
    check(
      "and the column headings sit below the rail rather than under it",
      railRows === 0
        ? notExercised("this page prices no destination, so its table never scrolls past the rail")
        : stuckHeadings.thTop >= stuckHeadings.railBottom,
      JSON.stringify(stuckHeadings)
    );
    await page.fill("#budgetNumber", String(budgetBeforeRail));
    await page.evaluate(() => window.scrollTo(0, 0));
    await settleFrame();
    const returned = await railState();
    check(
      "and the rail leaves again when the slider is back in view",
      returned && returned.hidden && returned.inert,
      JSON.stringify(returned)
    );
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
      applyState({ unit: "adult" });
      const lowered = [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations]
        .flat()
        .filter((d) => {
          const entry = (d.railcards || {})[card.key];
          return entry && entry.pricePence !== null && entry.pricePence < d.adultPence;
        });
      if (!lowered.length) return null;
      // The rows the card lowers are put on the first page. The table shows 20
      // rows a page, cheapest first, and a card's minimum fare means the
      // rows it lowers are the dearer ones: Falmouth Town's 16-25 Railcard
      // lowers nothing under its £12 floor, so all of the first page was
      // unchanged and a right page read as one that ignored the card.
      window.__keptLists = [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations];
      const lowers = (d) => {
        const entry = (d.railcards || {})[card.key];
        return entry && entry.pricePence !== null && entry.pricePence < d.adultPence;
      };
      // Fifteen it lowers and five it does not, so one page holds both and
      // the checks on unlowered rows still have rows to read.
      const onePage = (list) => list.filter(lowers).slice(0, 15).concat(list.filter((d) => !lowers(d)).slice(0, 5));
      DATA.destinations = onePage(DATA.destinations || []);
      DATA.singleDestinations = onePage(DATA.singleDestinations || []);
      DATA.anytimeDestinations = onePage(DATA.anytimeDestinations || []);
      currentPage = 1;
      const dearest = lowered.reduce((high, d) => Math.max(high, d.adultPence), 0);
      setBudget(Math.min(Number(document.getElementById("budget").max), Math.ceil(dearest / 100)));
      select.value = "";
      render();
      return card.key;
    });
    if (resortable) {
      const beforeCard = await shownPrices();
      await page.evaluate((key) => {
        applyState({ railcard: key });
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
        [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations] = window.__keptLists;
        currentPage = 1;
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
    // A chip the page's list carries inside the budget must be on screen, and
    // one it does not must not be: the two directions are separate checks
    // because they failed separately. Both are read against the budget, because
    // that is the rule the page offers a chip on -- a type whose only
    // destinations are dearer than the budget is a chip that cannot succeed
    // here, and is not offered.
    const carriedTypes = await page.evaluate(() => {
      const types = new Set();
      const affordable = new Set();
      for (const d of TYPES.list()) {
        for (const type of TYPES.types(d)) {
          types.add(type);
          if (d.adultPence <= TYPES.cap()) affordable.add(type);
        }
      }
      const chips = Array.from(document.querySelectorAll('input[name="destinationType"]'))
        .map((input) => input.value)
        .filter((value) => value !== "all");
      return {
        carried: [...types].sort(),
        affordable: [...affordable].sort(),
        offered: chips.filter((value) => !document.querySelector(`input[name="destinationType"][value="${value}"]`).closest("label").hidden).sort(),
        rendered: chips.sort(),
      };
    });
    check(
      "the offered chips are the ones this mode's budget can reach",
      carriedTypes.offered.every((type) => carriedTypes.carried.includes(type)) &&
        carriedTypes.rendered
          .filter((type) => carriedTypes.affordable.includes(type))
          .every((type) => carriedTypes.offered.includes(type)),
      `offered ${carriedTypes.offered.join(", ")}; reachable ${carriedTypes.affordable.join(", ")}; carried ${carriedTypes.carried.join(", ")}`
    );
    // Critique item 3, second half: the four settlement bands and All stay in
    // the row, and the thematic facets are one press away behind the chip that
    // row ends with. Which chip belongs to which half is the build's split, and
    // that is held in tests/test_build_fares.py against the registry; what is
    // read here is the behaviour a reader meets -- where the disclosure sits,
    // what it says, and what the press does. Read on the page rather than
    // named here, so a page whose list carries no facet is asked for nothing.
    const readArrangement = () => page.evaluate(() => {
      const row = document.getElementById("destinationTypes");
      const panel = document.getElementById("moreTypesPanel");
      const toggle = document.getElementById("moreTypes");
      const inPanel = panel ? Array.from(panel.querySelectorAll("label.choice-chip")) : [];
      const inRow = Array.from(row.querySelectorAll("label.choice-chip"));
      return {
        exists: !!panel && !!toggle,
        rowChips: inRow.length,
        panelChips: inPanel.length,
        offered: inPanel.filter((label) => !label.hidden).length,
        // A hidden panel is a claim about the attribute; this is the claim about
        // the pixels, so a stylesheet that stopped hiding it fails here too.
        onScreen: inPanel.filter((label) => label.getBoundingClientRect().height > 0).length,
        rowOffered: inRow.filter((label) => !label.hidden).length,
        lastInRow: !!toggle && row.lastElementChild === toggle,
        expanded: toggle ? toggle.getAttribute("aria-expanded") : null,
        controls: toggle ? toggle.getAttribute("aria-controls") : "",
        panelId: panel ? panel.id : "",
        hidden: panel ? panel.hidden : null,
        toggleHidden: toggle ? toggle.hidden : null,
        count: toggle ? (toggle.querySelector(".more-types-count") || {}).textContent : "",
      };
    });
    // The page is opened again first: the fold is the reader's, so it stays
    // where an earlier chip check left it, and "arrives folded" is a claim
    // about a page nobody has pressed anything on yet.
    await open(facts.affordable);
    let arrangement = await readArrangement();
    if (arrangement.exists && arrangement.offered === 0) {
      // The opening budget reaches no facet, so the page offers no disclosure
      // to press. The budget goes to this mode's ceiling, the way the chip
      // checks above raise it, and the page is handed back afterwards: a page
      // with a facet somewhere inside it is the page this is about.
      await page.evaluate(() => { setBudget(budgetCeiling()); STATE.page = 1; render(); });
      arrangement = await readArrangement();
    }
    if (arrangement.exists && arrangement.offered > 0) {
      check(
        "the facets arrive folded, behind the last chip in the row of sizes",
        arrangement.lastInRow &&
          arrangement.panelChips > 0 &&
          arrangement.rowChips > 0 &&
          arrangement.hidden === true &&
          arrangement.expanded === "false" &&
          arrangement.onScreen === 0,
        JSON.stringify(arrangement)
      );
      check(
        "and the facet disclosure says how many it holds",
        arrangement.count === `(${arrangement.offered})` &&
          arrangement.controls === arrangement.panelId,
        JSON.stringify(arrangement)
      );
      await page.click("#moreTypes");
      const revealed = await page.evaluate(() => {
        const panel = document.getElementById("moreTypesPanel");
        const row = document.getElementById("destinationTypes");
        const offered = (root) => Array.from(root.querySelectorAll("label.choice-chip"))
          .filter((label) => !label.hidden);
        return {
          hidden: panel.hidden,
          expanded: document.getElementById("moreTypes").getAttribute("aria-expanded"),
          onScreen: offered(panel).filter((label) => label.getBoundingClientRect().height > 0).length,
          offered: offered(panel).length,
          rowOnScreen: offered(row).filter((label) => label.getBoundingClientRect().height > 0).length,
        };
      });
      check(
        "one press offers them, and the row above does not move",
        revealed.hidden === false &&
          revealed.expanded === "true" &&
          revealed.offered > 0 &&
          revealed.onScreen === revealed.offered &&
          revealed.rowOnScreen === arrangement.rowOffered,
        JSON.stringify({ arrangement, revealed })
      );
      await page.click("#moreTypes");
      const refolded = await readArrangement();
      check(
        "and a second press folds them away again",
        refolded.hidden === true && refolded.expanded === "false",
        JSON.stringify(refolded)
      );
      // S20's rule, one control up: the disclosure is offered on the chips
      // behind it, so a budget that reaches no facet takes the disclosure with
      // the chips -- a press into an empty row is the dead end the chips
      // themselves are already refused for. Both directions, because a
      // disclosure that never comes back is a filter the reader cannot reach.
      await page.evaluate(() => { setBudget(Number(document.getElementById("budget").min)); render(); });
      const flooredOut = await readArrangement();
      await page.evaluate(() => { setBudget(budgetCeiling()); render(); });
      const raisedBack = await readArrangement();
      check(
        "a budget that reaches no facet takes the disclosure with it, and gives it back",
        flooredOut.offered === 0 && flooredOut.toggleHidden === true &&
          // The panel is shut behind the vanished control rather than left open
          // over no chips, and its number is the zero that took it away.
          flooredOut.hidden === true && flooredOut.expanded === "false" &&
          flooredOut.count === "(0)" &&
          raisedBack.offered > 0 && raisedBack.toggleHidden === false,
        JSON.stringify({ flooredOut, raisedBack })
      );
      await open(facts.affordable);
    } else {
      check(
        "the facets arrive folded, behind the last chip in the row of sizes",
        notExercised("this page's list carries no thematic facet for any budget in this mode")
      );
      check("and the facet disclosure says how many it holds", notExercised("see above"));
      check("one press offers them, and the row above does not move", notExercised("see above"));
      check("and a second press folds them away again", notExercised("see above"));
      check(
        "a budget that reaches no facet takes the disclosure with it, and gives it back",
        notExercised("see above")
      );
    }
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
      // The reader's own controls, clicked where the reader clicks them: a
      // label click is idempotent, and page.check() on a radio the page already
      // holds throws rather than doing nothing, which turned a setup that the
      // page had already satisfied into a failure.
      await page.locator('label:has(input[name="destinationType"][value="all"])').click();
      await page.locator(`label:has(input[name="ticketMode"][value="${heritage.mode}"])`).click();
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
        stateVisible: !!document.getElementById("filterState") &&
          document.getElementById("filterState").getBoundingClientRect().height > 0,
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
      // DS4 of the 19 October 2026 distill pass: the summary is the folded
      // state's line, so the open panel does not repeat itself above the
      // controls that show the same state -- and the toggle keeps the state in
      // its name for the reader who cannot see either.
      const openPlate = await page.evaluate(() => ({
        visible: document.getElementById("filterState").getBoundingClientRect().height > 0,
        label: document.getElementById("moreFiltersToggle").getAttribute("aria-label") || "",
      }));
      check(
        "and the open panel does not repeat the state beside the controls that show it",
        openPlate.visible === false && /^Filter this list\. Ticket: /.test(openPlate.label),
        JSON.stringify(openPlate)
      );
      const chipValue = await page.evaluate(() => {
        // A chip is offered only when a destination of its type is inside the
        // budget, so the visible chips are the ones with rows behind them. The
        // budget is still opened to the ceiling before falling back: a page
        // whose every destination carries no type at all offers no chip, and
        // then the check reports that there was nothing to press rather than
        // failing.
        const boxes = Array.from(document.querySelectorAll('.destination-filter input[type="checkbox"]'));
        const chipsWithRows = () => boxes.filter((box) => {
          const count = document.querySelector(`[data-count-for="${box.value}"]`);
          return count && Number(count.textContent.replace(/\D/g, "")) > 0;
        });
        let withRows = chipsWithRows();
        if (!withRows.length) {
          setBudget(budgetCeiling());
          render();
          withRows = chipsWithRows();
        }
        const input = withRows[0] || boxes[0] || null;
        if (!input) return { pressed: false, rows: 0, label: "", name: "", noneLeft: true };
        const name = input.parentElement.querySelector("span").textContent.trim();
        // A chip behind the "More types" fold is pressed after the press that
        // offers it, the way a reader reaches it: this check is about a
        // refinement made inside the disclosure, and reaching past a fold
        // nobody opened would be a state no reader is in.
        const panel = document.getElementById("moreTypesPanel");
        if (panel && panel.hidden && panel.contains(input)) document.getElementById("moreTypes").click();
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
        // than the state it read before the tap. A page that prices nothing
        // offers no chip to press, and says so rather than failing.
        chipValue.noneLeft
          ? notExercised("this page offers no destination-type chip to press")
          : chipValue.pressed && chipValue.label.includes(chipValue.name) && chipValue.label !== folded.state,
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
          stateVisible: document.getElementById("filterState").getBoundingClientRect().height > 0,
          label: document.getElementById("moreFiltersToggle").getAttribute("aria-label"),
        };
      });
      check(
        "closing it again keeps the narrowed results",
        closed.open === false && closed.rows > 0 && closed.rowVisible,
        JSON.stringify(closed)
      );
      check("and the summary still names what is narrowed", closed.state.trim().length > 0, closed.state);
      check(
        "and the folded plate shows it again rather than leaving it in a label",
        closed.stateVisible === true && !closed.label,
        JSON.stringify(closed)
      );
      // Put the chips back, then hand the rest of the run a desktop viewport:
      // the checks below exercise every control, which on a phone means
      // opening the disclosure each time, and that is what section 7a is for.
      await page.evaluate(() => {
        for (const input of document.querySelectorAll('.destination-filter input[type="checkbox"]')) {
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
      // empty mode must not offer is a type that nothing in it carries. Both
      // chip rows are read, because the facets are behind the disclosure now: a
      // chip the empty mode has taken away is hidden wherever it sits, and the
      // disclosure that holds it is in the read too.
      const chipLabels = await page.locator(".destination-filter label").evaluateAll((labels) =>
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
      // A facet in the pair is one press away, so the press that reaches it is
      // the disclosure's, exactly as a reader makes it.
      for (const type of pair) await revealType(`input[name="destinationType"][value="${type}"]`);
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
        applyState({ mode });
        render();
        offered[mode] = new Set(activeDestinations().flatMap((x) => x.destinationTypes || [x.destinationType]));
      }
      applyState({ mode: original });
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
      // The budget is this mode's own ceiling before the chip is pressed.
      // A chip is offered on the budget on screen, and switching ticket mode
      // re-clamps the budget to the new list, so the mode a facet belongs to is
      // not necessarily a mode whose budget reaches it -- on the demo page
      // `single` clamps to the cheapest singles and the small-town chip the
      // payload carries is no longer offered, which makes pressing it a 30 s
      // wait rather than a failure anybody can read (15 October 2026).
      await page.evaluate(() => { setBudget(budgetCeiling()); render(); });
      // Offered is not on screen: a facet the page folds behind its disclosure
      // has to be revealed before it can be pressed, or the press waits thirty
      // seconds on a hidden chip and says nothing about the page. Every real
      // station page with a folded facet stopped here on 21 October 2026.
      await revealType(`input[name="destinationType"][value="${chip.value}"]`);
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
    // "Ticket: Cheapest available" is what they picked, and it is not what a
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
    // Critique item 8: the page's accelerators, and the line that says they
    // exist. Both are read against what the page does rather than against the
    // string the page writes: a hint promising a key the page does not honour
    // is worse than no hint, and a key that fires while the reader is typing a
    // station name is worse than no key. A listener installed after the page's
    // own is what reads defaultPrevented, because the page's handler runs first.
    // The budget reaches every row this mode carries: the pager half is about a
    // list longer than one page, and the page's own opening budget is a price,
    // not a length, so it left even a twenty-two-row page on one page.
    // Read after a fresh load, because the mode an earlier check left behind
    // decides which list this is about.
    await open();
    const walkAll = await page.evaluate(() =>
      Math.ceil(TYPES.dearest((d) => TYPES.priceOf(d)) / 100));
    await open(walkAll);
    await page.evaluate(() => {
      window.__keys = [];
      document.addEventListener("keydown", (event) => {
        window.__keys.push({
          key: event.key,
          prevented: event.defaultPrevented,
          active: document.activeElement ? document.activeElement.id : "",
        });
      });
    });
    const pressed = async (stroke) => {
      await page.keyboard.press(stroke);
      return page.evaluate(() => window.__keys[window.__keys.length - 1] || null);
    };
    const nothingFocused = () => page.evaluate(() => {
      if (document.activeElement) document.activeElement.blur();
    });
    await nothingFocused();
    const slash = await pressed("/");
    check(
      "/ focuses the budget field",
      !!slash && slash.prevented === true && slash.active === "budgetNumber",
      JSON.stringify(slash)
    );
    await nothingFocused();
    const bee = await pressed("b");
    check(
      "b focuses the same field, for a layout where / needs a shift",
      !!bee && bee.prevented === true && bee.active === "budgetNumber",
      JSON.stringify(bee)
    );
    // The budget field holds focus after the key above, so the next two are
    // typed at a reader who is mid-keystroke: the field keeps them.
    const keyInField = await pressed("b");
    const slashInField = await pressed("/");
    check(
      "a key pressed inside a field belongs to the field",
      !!keyInField && keyInField.prevented === false &&
        !!slashInField && slashInField.prevented === false &&
        slashInField.active === "budgetNumber",
      JSON.stringify({ keyInField, slashInField })
    );
    const hint = await page.evaluate(() => {
      const line = document.getElementById("keyHints");
      return {
        exists: !!line,
        visible: !!line && !line.hidden && line.offsetWidth > 0,
        text: line ? line.textContent.trim() : "",
      };
    });
    // DS3 of the 19 October 2026 distill pass: one key named, not two, and the
    // line is only offered to a fine pointer -- the stylesheet's media query is
    // what this reads, through the computed visibility rather than the text.
    check(
      "the strip that stays on screen names the budget key",
      hint.exists && hint.visible && hint.text.includes("/") && !/\bor b\b/.test(hint.text),
      JSON.stringify(hint)
    );
    const pageAt = () => page.evaluate(() => ({
      status: document.getElementById("pageStatus").textContent.trim(),
      first: (document.querySelector("#rows tr[data-crs]") || { dataset: {} }).dataset.crs || "",
      shown: !document.getElementById("pagination").hidden,
    }));
    // The pager is on screen only when the list is longer than a page, so the
    // budget is put where every row of this mode fits before the pager is read:
    // a two-page fixture whose opening budget hides page two is one page of
    // rows to this block, and a page that behaves would read as no pager.
    const everyRow = await page.evaluate(() =>
      Math.ceil(TYPES.dearest((d) => TYPES.priceOf(d)) / 100));
    await page.fill("#budgetNumber", String(everyRow));
    const hintAfter = await page.evaluate(() => document.getElementById("keyHints").textContent.trim());
    const paging = await pageAt();
    await nothingFocused();
    if (paging.shown) {
      await pressed("n");
      const next = await pageAt();
      await pressed("p");
      const back = await pageAt();
      check(
        "n turns to the next page and p turns back",
        next.status !== paging.status && back.status === paging.status &&
          back.first === paging.first,
        JSON.stringify({ paging, next, back })
      );
      check(
        "and the hint promises the pager the page has",
        hintAfter.includes("n or p"),
        JSON.stringify({ text: hintAfter, paging })
      );
    } else {
      check(
        "the hint promises a pager only when a pager is on the page",
        hintAfter.includes("/") && !hintAfter.includes("n or p"),
        JSON.stringify({ text: hintAfter, paging })
      );
      await pressed("n");
      await pressed("p");
      const still = await pageAt();
      check(
        "a page turn when there is one page leaves the list where it is",
        still.status === paging.status && still.first === paging.first,
        JSON.stringify({ paging, after: still })
      );
      // The shape that reaches this branch is the one no fixture prices, so
      // there is nothing here to temper with a check: the key that is not
      // promised is the key the check above proved inert. The pager itself is
      // exercised on the fixture built for it, which is the demo feed.
    }
    // The tab order a keyboard reader walks, on the controls the fold added:
    // the disclosure is a stop, a folded chip is not, and pressing it decides
    // which. Read by pressing Tab from the top of the document, the way a
    // keyboard reader moves, rather than by asking the DOM what it thinks its
    // order is.
    await open();
    // The readers below are installed after the load: open() navigates, and a
    // navigation drops everything the page had on window.
    await open();
    await page.evaluate(() => {
      window.__entry = (el) => {
        if (!el || el === document.body) return "body";
        if (el.id) return el.id;
        if (el.name === "destinationType") {
          // A radio group is one stop in a browser, so the group is named after
          // its one reachable control rather than four times.
          const group = el.closest("#destinationTypes");
          if (group && el.type === "radio") return "destinationTypes";
          return "chip:" + el.value;
        }
        if (el.name) return el.name + ":" + el.value;
        return el.tagName.toLowerCase() + ":" + (el.textContent || "").trim().slice(0, 20);
      };
      const toggle = document.getElementById("moreTypes");
      const panel = document.getElementById("moreTypesPanel");
      window.__foldedFacets = panel
        ? Array.from(panel.querySelectorAll('input[name="destinationType"]'))
            .filter((input) => !input.closest("label").hidden)
            .map((input) => "chip:" + input.value)
        : [];
      window.__facetState = () => ({
        offered: !!toggle && !toggle.hidden,
        folded: !!panel && panel.hidden,
        expanded: toggle ? toggle.getAttribute("aria-expanded") : null,
      });
    });
    // Twelve Tabs from the top of a freshly loaded page reaches the row: the
    // heading's budget controls, the change control, the refinements toggle and
    // its own controls come first. The walk stops at the table.
    const walk = async () => {
      const steps = [];
      for (let step = 0; step < 20; step += 1) {
        await page.keyboard.press("Tab");
        const entry = await page.evaluate(() => window.__entry(document.activeElement));
        if (entry === "body") break;
        steps.push(entry);
      }
      return steps;
    };
    const focusEntry = (entry) => page.evaluate((label) => {
      const el = label.startsWith("chip:")
        ? document.querySelector(`input[name="destinationType"][value="${label.slice(5)}"]`)
        : document.getElementById(label);
      if (!el) return false;
      el.focus();
      return window.__entry(document.activeElement) === label;
    }, entry);
    const nextStop = async () => {
      await page.keyboard.press("Tab");
      return page.evaluate(() => window.__entry(document.activeElement));
    };
    const facet = await page.evaluate(() => window.__facetState());
    if (facet.offered) {
      const folded = await walk();
      const at = folded.indexOf("moreTypes");
      const facetValues = await page.evaluate(() => window.__foldedFacets);
      // What follows the disclosure with the facets folded, for the comparison
      // below: the fold must not change it.
      const afterFolded = folded[at + 1];
      check(
        "the facet disclosure is a stop at the end of the chip row, and a folded chip is not",
        facet.folded && at !== -1 &&
          folded[at - 1] && folded[at - 1].startsWith("chip:") &&
          // Nothing behind the fold is reached, and nothing after the
          // disclosure is a chip: the row ends where the disclosure says.
          folded.slice(at + 1).every((entry) => !entry.startsWith("chip:")) &&
          facetValues.length > 0 &&
          !folded.some((entry) => facetValues.includes(entry)),
        JSON.stringify({ folded, facet, facetValues })
      );
      const opened = await page.evaluate(() => {
        document.getElementById("moreTypes").click();
        return window.__facetState();
      });
      await focusEntry("moreTypes");
      const firstOpen = await nextStop();
      check(
        "pressing the disclosure puts its chips next in the tab order",
        opened.expanded === "true" && facetValues.includes(firstOpen) &&
          firstOpen !== afterFolded,
        JSON.stringify({ opened, firstOpen, afterFolded, facetValues })
      );
      await focusEntry("moreTypes");
      const closed = await page.evaluate(() => {
        document.getElementById("moreTypes").click();
        return window.__facetState();
      });
      const firstClosed = await nextStop();
      check(
        "and closing it again takes them out, leaving the stop that follows it unchanged",
        closed.expanded === "false" && closed.folded &&
          firstClosed === afterFolded && !firstClosed.startsWith("chip:"),
        JSON.stringify({ closed, firstClosed, afterFolded })
      );
    } else {
      check("the facet disclosure is a stop at the end of the chip row, and a folded chip is not", notExercised("this page offers no facet disclosure"));
      check("pressing the disclosure puts its chips next in the tab order", notExercised("see above"));
      check("and closing it again takes them out, leaving the stop that follows it unchanged", notExercised("see above"));
    }
    await open();
}
module.exports = { driveTheFilters };
