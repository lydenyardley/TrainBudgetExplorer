/**
 * What a row does: the ticket link that goes where it says it goes (4), the
 * panel it opens (5) -- the trains beside the fare, and no copy of its own
 * since ADR-0084 -- and the party price a railcard is applied to (6).
 *
 * The two-ticket row is here too, because it is the same subject from the
 * other end: a place the feed prices only in two parts is one row and two
 * purchases, and its panel names both tickets, both conditions and the split.
 */
const { SELLER, money, notExercised } = require("./harness.cjs");

// The page's date words, written here so a check of the panel's lead does not
// read them back off the page it is checking.
const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
function dayWords(iso) {
  const parts = String(iso || "").split("-").map(Number);
  if (parts.length !== 3 || parts.some((value) => !Number.isFinite(value))) return "";
  return parts[2] + " " + MONTHS[parts[1] - 1] + " " + parts[0];
}
async function checkTheRowActions(world) {
  const { page, check, notExercised } = world;
    // 4. A ticket link goes where it says it goes, in a new tab.
    const link = page.locator("#rows a.buy").first();
    const href = await link.getAttribute("href");
    check("the plain link carries no journey at all", href === "https://www.nationalrail.co.uk/journey-planner/", href);
    // Both tokens are load-bearing and both are checked here rather than in the
    // payload: `noopener` keeps the seller's page off this one, and `noreferrer`
    // stops the address -- the budget, the card and the shortlist -- travelling
    // in the Referer header of a click (audit item 9, 28 October 2026).
    const rel = ((await link.getAttribute("rel")) || "").split(/\s+/);
    check("the link is marked untracked", rel.includes("noopener") && rel.includes("noreferrer"), rel.join(" "));
    check("the link opens in a new tab", (await link.getAttribute("target")) === "_blank");
    const [popup] = await Promise.all([page.waitForEvent("popup"), link.click()]);
    await popup.waitForLoadState("domcontentloaded");
    check("following the link reaches the seller", SELLER.test(popup.url()), popup.url());
    await popup.close();
    // 5. The panel a row opens: the trains the fare pays for, the fare itself,
    // and no copy of its own (ADR-0084). Every claim here is about what the
    // panel says for one row, so it is read off the row the reader opens.
    await page.locator("#rows tr:not(.detail) .toggle[aria-expanded='false']").first().click();
    const panel = await page.evaluate(() => {
      const toggle = document.querySelector("#rows tr[data-crs] .toggle[aria-expanded='true']");
      const row = toggle ? toggle.closest("tr[data-crs]") : null;
      const detail = row ? row.nextElementSibling : null;
      const crs = row ? row.dataset.crs : "";
      const destination = (crs && TYPES.list().find((d) => d.crs === crs)) || null;
      const trains = detail ? detail.querySelector(".trains") : null;
      const fare = detail ? detail.querySelector(".fare") : null;
      const columns = detail ? detail.querySelector(".detail-columns") : null;
      const lead = detail
        ? Array.from(detail.querySelectorAll(".trains-lead p")).map((p) => p.textContent.trim())
        : [];
      const items = detail
        ? Array.from(detail.querySelectorAll(".trains > ul > li")).map((li) => li.textContent.trim())
        : [];
      const boxes = trains && fare ? [trains.getBoundingClientRect(), fare.getBoundingClientRect()] : [];
      return {
        crs,
        trains: Boolean(trains),
        fare: Boolean(fare),
        lead,
        items,
        // Read off the DOM rather than off the template: a button or a box in
        // here would be the row's copy back, in a new place.
        controls: detail ? detail.querySelectorAll("button, textarea").length : 0,
        twoTracks: columns
          ? getComputedStyle(columns).gridTemplateColumns.trim().split(/\s+/).length > 1
          : false,
        // The two columns hold the same top edge and do not overlap, which is
        // what "beside" means once the stylesheet has laid them out.
        sideBySide:
          boxes.length === 2 &&
          Math.round(boxes[0].top) === Math.round(boxes[1].top) &&
          boxes[0].right <= boxes[1].left,
        departures: destination ? destination.departures.length : 0,
        described: Boolean(destination && destination.restrictionCode && destination.restrictionDescribed),
        sentence: ((detail && detail.querySelector(".fare-line")) || {}).textContent || "",
        // The day the list belongs to is the one the page is showing, which is
        // the payload's own date on a build that named one.
        day: DATA.serviceDate || "",
      };
    });
    check(
      "the panel a row opens offers no copy of its own",
      panel.controls === 0,
      `${panel.controls} control(s) in the panel`
    );
    // The duration is the subtraction a reader was doing across an hour
    // boundary, so it is checked against the two clocks printed beside it
    // rather than against the payload's own minutes.
    const clockMinutes = (value) => Number(value.slice(0, 2)) * 60 + Number(value.slice(3, 5));
    const timed = panel.items.map((item) => {
      const match = /^(\d\d:\d\d) depart, (\d\d:\d\d) arrive \((\d+)h (\d+)m\)|^(\d\d:\d\d) depart, (\d\d:\d\d) arrive \((\d+)m\)/.exec(item);
      if (!match) return { item, ok: false };
      const depart = clockMinutes(match[1] || match[5]);
      const arrive = clockMinutes(match[2] || match[6]);
      const span = (arrive - depart + 1440) % 1440;
      const shown = match[1]
        ? Number(match[3]) * 60 + Number(match[4])
        : Number(match[7]);
      return { item, ok: span === shown };
    });
    check(
      "and every train it lists carries the duration between the two clocks it prints",
      panel.items.length === panel.departures && timed.every((one) => one.ok),
      `${timed.filter((one) => !one.ok).map((one) => one.item).join(" | ")} (${panel.departures} departure(s))`
    );
    // The list was the first five of the day and said nothing about which day;
    // the lead says it now, from the page's own date (ADR-0084, rule 3).
    const dayLead = "Next trains" + (panel.day ? " on " + dayWords(panel.day) : "") + ".";
    check(
      "and its lead names the day the trains belong to",
      panel.departures === 0
        ? notExercised("this page lists no trains, so the panel has no lead to read")
        : panel.lead.length > 0 && panel.lead[0] === dayLead,
      JSON.stringify({ lead: panel.lead, want: dayLead })
    );
    check(
      "and says whether the condition is on the fare or on one of the trains",
      panel.described
        ? panel.lead.some(
            (line) => line.startsWith("The condition ") && line.includes("is on the fare, not on one of these trains")
          )
        : !panel.lead.some((line) => line.includes("is on the fare, not on one of these trains")),
      JSON.stringify({ described: panel.described, lead: panel.lead })
    );
    // The sentence that used to point at the trains pointed past them on a
    // phone and beside them once the panel had two columns (ADR-0084, rule 5),
    // so it says only what it knows: the fare is restricted.
    check(
      "and a described condition's sentence stands on its own, with no pointer at the trains beside it",
      panel.described
        ? panel.sentence === "Restricted fare."
        : panel.sentence.length > 0 && !/\sbelow\b/.test(panel.sentence),
      JSON.stringify({ sentence: panel.sentence, described: panel.described })
    );
    check(
      "and the trains and the fare sit beside each other where the panel is two columns",
      panel.departures === 0
        ? notExercised("this page lists no trains, so the panel has one column of content")
        : panel.twoTracks
          ? panel.sideBySide
          : notExercised("this window is narrower than the panel's two-column width"),
      JSON.stringify({ twoTracks: panel.twoTracks, sideBySide: panel.sideBySide })
    );
    // 5b. The panel is a row of the results table, so it has to be as wide as
    // the table. A build that stands a column down -- no timetable, so no time
    // or changes -- changes the column count the panel has to span, and a span
    // written down when there were six leaves the disclosure content inside a
    // narrow first cell. Only the rendered row can say what it spanned, which
    // is why this claim lives here and not in the Python suite.
    const span = await page.evaluate(() => {
      const panel = document.querySelector("#rows tr.detail");
      const table = panel ? panel.closest("table") : null;
      const head = table ? table.querySelectorAll("thead th[scope='col']") : [];
      return {
        cells: panel ? panel.cells.length : 0,
        columns: head.length,
        spans: panel ? Array.from(panel.cells).map((cell) => cell.colSpan) : [],
      };
    });
    check(
      "the panel a row opens spans every column of the table it sits in",
      span.columns > 0 && span.cells === 1 && span.spans[0] === span.columns,
      `${span.cells} cell(s), spans ${span.spans.join("+")}, table has ${span.columns} column(s)`
    );
    // 5c. The open row survives the render. A reader who opens a row and then
    // moves the budget is looking at the fare and its condition; every render
    // replaces the rows, and the panel was keyed on the row element, so moving
    // the budget closed the row and took the panel with it (E9 of the 17
    // October 2026 audit, C8 of the critique). Driven as the reader does it:
    // open a row, then type a budget that keeps it.
    const keptOpen = await page.evaluate(() => {
      const first = document.querySelector("#rows tr[data-crs]");
      if (!first) return null;
      const toggle = first.querySelector(".toggle");
      if (toggle.getAttribute("aria-expanded") !== "true") toggle.click();
      const crs = first.dataset.crs;
      const opened = toggle.getAttribute("aria-expanded") === "true";
      // The fare sentence is what the reader opened the row for, and it is the
      // part of the panel that cannot change with the budget: the copy status
      // beside it does, and comparing the whole panel would fail on a control
      // doing its job.
      const sentence = () => {
        const line = document.querySelector("#rows tr.detail .fare-line");
        return line ? line.textContent : "";
      };
      const before = sentence();
      // Raising the budget adds rows and drops none, so the row the reader
      // opened is still one this list carries.
      const field = document.getElementById("budgetNumber");
      field.value = String(Number(field.value) + 1);
      field.dispatchEvent(new Event("input", { bubbles: true }));
      const after = Array.from(document.querySelectorAll("#rows tr[data-crs]")).find(
        (row) => row.dataset.crs === crs
      );
      const control = after ? after.querySelector(".toggle") : null;
      const detail = document.querySelector("#rows tr.detail");
      const facts = {
        crs,
        opened,
        carried: Boolean(after),
        stillOpen: Boolean(control && control.getAttribute("aria-expanded") === "true"),
        panel: Boolean(detail) && sentence() === before && before !== "",
        rows: document.querySelectorAll("#rows tr[data-crs]").length,
      };
      // Left as the sections after this one expect to find it: they open a row
      // themselves and look for a closed one, and a row this check left open
      // would be a page with no closed toggle on it.
      if (control && control.getAttribute("aria-expanded") === "true") control.click();
      return facts;
    });
    check(
      "a row the reader opened is still open when the budget moves",
      keptOpen === null
        ? notExercised("this page shows no rows to open")
        : keptOpen.opened && keptOpen.carried && keptOpen.stillOpen && keptOpen.panel,
      JSON.stringify(keptOpen)
    );
    // 6. The party price carries the railcard, because that price needs it.
    // The budget is the cheapest party price in the payload, not the adult one
    // used above: two adults never cost less than one, so a budget that shows
    // a return row shows no party row at all, and a check written against one
    // was measuring the fixture's numbers rather than the page.
    //
    // A page whose cheapest two-adult price is above the ceiling the page
    // itself sets can show no party row at any budget a reader can type: on a
    // one-destination page the ceiling is that destination's adult fare and the
    // party fare is double it. Found by sweeping a two-station site, where the
    // step used to wait thirty seconds for a button that could never appear and
    // then end the run early -- reported as a page that stopped, with every
    // check it had already done counting as a pass.
    // Two adults are selected before the budget is read, because the ceiling
    // the page allows depends on who the fare covers. Reading it first measured
    // the single-adult ceiling and concluded the party rows were unreachable
    // when the slider does reach them once the party price is the one on screen.
    await page.check('input[name="unit"][value="party"]');
    const party = await page.evaluate(() => ({
      cheapest: DATA.destinations.reduce((low, d) => Math.min(low, d.partyPence), Infinity),
      ceiling: Number(document.getElementById("budget").max) * 100,
    }));
    const partyReachable = party.cheapest <= party.ceiling;
    if (partyReachable) {
    await page.fill("#budgetNumber", String(Math.max(1, Math.ceil(party.cheapest / 100))));
    // The railcard note waits in the row's own panel (finding 4, 29 September
    // 2026), so the row is opened first: a note a reader reaches through a
    // disclosure is still a note, and this is where the suite meets it. It is
    // owed only where the feed prices a card on that fare, so whether one should
    // be there is read off the row the page opened rather than written here.
    await page.locator("#rows tr:not(.detail) .toggle[aria-expanded='false']").first().click();
    const partyNote = await page.evaluate(() => {
      const toggle = document.querySelector("#rows tr[data-crs] .toggle[aria-expanded='true']");
      const row = toggle ? toggle.closest("tr[data-crs]") : null;
      const crs = row ? row.dataset.crs : "";
      const destination = (crs && TYPES.list().find((d) => d.crs === crs)) || null;
      const select = document.getElementById("railcardSelect");
      const card = destination && select && select.value ? (destination.railcards || {})[select.value] : null;
      const line = document.querySelector("#rows tr.detail .card-note");
      return {
        crs,
        // A card the feed refused for this fare is not a card price, so the note
        // is owed only where the feed gives it one.
        owed: Boolean(card && card.pricePence !== null),
        note: line ? line.textContent.trim() : "",
      };
    });
    check(
      "the panel under a party price carries the railcard note when the feed prices the card on that fare, and stays quiet when it does not",
      partyNote.owed ? partyNote.note.length > 0 : partyNote.note === "",
      JSON.stringify(partyNote)
    );
    const partyCopy = await page.evaluate(() => navigator.clipboard.readText());
    check(
      "and the row hands no copied journey to the clipboard",
      !/^Passengers: /m.test(partyCopy),
      partyCopy
    );
    } else {
      const reason =
        `with Two adults selected this page's cheapest price is ${money(party.cheapest)} and its ` +
        `budget goes to ${money(party.ceiling)}, so no party row can be shown at any budget it allows`;
      for (const name of [
        "the panel under a party price carries the railcard note when the feed prices the card on that fare, and stays quiet when it does not",
        "and the row hands no copied journey to the clipboard",
      ]) {
        check(name, notExercised(reason));
      }
    }
}
/**
 * ADR-0061, read off the row the reader opens rather than off the payload, and
 * read again on every other day: the day changes the times and neither price.
 * The address is kept and returned to afterwards, so the checks below read the
 * state they did.
 */
async function checkTheTwoTicketRow(world) {
  const { page, url, open, installReader, check, notExercised } = world;
    // ADR-0061: a place the feed prices only in two parts is one row, priced
    // at the two fares added together, naming both tickets, both conditions and
    // the pricing split (change wording only when the journey leaves a train).
    // Read off the row the reader opens, not
    // the payload (ADR-0058), and read again on every other day: the day
    // changes the times and neither price (ADR-0060). The address is kept and
    // returned to afterwards, so the checks below read the state they did.
    const stateBefore = page.url();
    await open();
    const twoTicketRow = await page.evaluate(() => {
      const row = activeDestinations().find((d) => Array.isArray(d.tickets) && d.tickets.length === 2);
      return row
        ? { crs: row.crs, adult: row.adultPence, shown: priceOf(row), tickets: row.tickets, changes: row.changes }
        : null;
    });
    if (twoTicketRow) {
      // The row is visited through the address, budget, page and day, so it
      // is on screen whatever the number of cheaper rows on a real page: a
      // changed day starts the table again at its first page.
      //
      // The budget is the price on screen rather than the payload's adult fare,
      // because that is the number the page filters on: a party or a card the
      // reader left set prices the row differently, and a budget short of it
      // puts the row outside the list the check then looks for. The assertion
      // below still holds the price to the sum of the two tickets, so a state
      // left over fails as a price the reader was shown rather than as a row
      // that is not there.
      const budgetPounds = Math.ceil(twoTicketRow.shown / 100);
      await open(budgetPounds);
      // The row's place in the table is asked of the page's own ordering, not
      // of a price sort written here: the page breaks a tie by name
      // (compareEntries), and a price sort alone puts rows in a different order
      // -- measured on Norwich, 3 November 2026, 198 of 600 rows sat at another
      // index. Once a row crossed a page boundary that way, the visit asked for
      // the page it was not on, the row was missing, and the null read took the
      // whole run with it.
      const position = await page.evaluate((crs) => {
        const cap = Number(document.getElementById("budgetNumber").value) * 100;
        return activeDestinations()
          .map((destination) => ({ destination: destination, pence: priceOf(destination) }))
          .filter((entry) => entry.pence <= cap)
          .sort(compareEntries)
          .findIndex((entry) => entry.destination.crs === crs);
      }, twoTicketRow.crs);
      const visit = async (day) => {
        const address = new URL(url);
        address.searchParams.set("budget", String(budgetPounds));
        if (position >= world.pageSize) address.searchParams.set("page", String(Math.floor(position / world.pageSize) + 1));
        if (day) address.searchParams.set("day", String(day));
        await page.goto(address.href);
      };
      const selector = '#rows tr[data-crs="' + twoTicketRow.crs + '"]';
      const readRow = async (day) => {
        await visit(day);
        if (!(await page.locator(selector).count())) return null;
        const expanded = await page.getAttribute(selector + " button.row-expand", "aria-expanded");
        if (expanded !== "true") await page.click(selector + " button.row-expand");
        return page.evaluate((wanted) => {
          const tr = document.querySelector(wanted);
          const detail = tr.nextElementSibling;
          return {
            price: tr.querySelector(".price").textContent.trim(),
            fareType: tr.querySelector(".fare-type").textContent.trim(),
            tickets: detail ? Array.from(detail.querySelectorAll(".two-tickets li")).map((li) => li.textContent.trim()) : [],
            panel: detail ? detail.textContent : "",
            split: Boolean(detail && detail.querySelector(".split")),
          };
        }, selector);
      };
      const shown = await readRow(0);
      const sum = twoTicketRow.tickets[0].adultPence + twoTicketRow.tickets[1].adultPence;
      const expectedPrice = "\u00a3" + (sum / 100).toFixed(2);
      const viaName = twoTicketRow.tickets[0].toName;
      const throughPriced = (twoTicketRow.changes || 0) === 0;
      // A row the page did not show is a defect this check reports, not an
      // exception it dies on: reading `.panel` off a null row stopped the whole
      // run on Norwich on 2 November 2026, and the report then named a page
      // that stopped rather than the row that was missing.
      const splitWording = shown === null ? false : throughPriced
        ? shown.panel.includes("priced via " + viaName) &&
          shown.panel.includes("stay on the train") &&
          !shown.panel.includes("changing at ")
        : shown.panel.includes("changing at " + viaName);
      check(
        "a place the feed prices in two parts is one row at both fares added together, naming each ticket, its condition and the change",
        shown !== null &&
          twoTicketRow.adult === sum &&
          shown.price === expectedPrice &&
          shown.fareType === "Two tickets" &&
          shown.tickets.length === 2 &&
          twoTicketRow.tickets.every((ticket, at) =>
            shown.tickets[at].includes(ticket.ticket) &&
            shown.tickets[at].includes(ticket.restrictionCode ? "restriction " + ticket.restrictionCode : "no restriction")) &&
          splitWording &&
          shown.panel.includes("two separate purchases") &&
          !shown.split,
        shown === null
          ? `${twoTicketRow.crs} is not on the page at ${money(twoTicketRow.shown)}, as two tickets, so the row could not be read`
          : JSON.stringify({ crs: twoTicketRow.crs, expected: expectedPrice, throughPriced: throughPriced, shown: shown })
      );
      const days = await page.evaluate(() => (DATA.serviceDays || []).length);
      if (days > 1) {
        const differing = [];
        for (let index = 1; index < days; index += 1) {
          const later = await readRow(index);
          if (!later || later.price !== shown.price || later.tickets.join("|") !== shown.tickets.join("|")) {
            differing.push({ day: index, row: later });
          }
        }
        check(
          "the day control changes neither price on a two-ticket row",
          differing.length === 0,
          JSON.stringify({ days: days, differing: differing.slice(0, 2) })
        );
      } else {
        check("the day control changes neither price on a two-ticket row", notExercised("this page carries no week of days"));
      }
    } else {
      const idle = "no place on this page is priced in two parts";
      check("a place the feed prices in two parts is one row at both fares added together, naming each ticket, its condition and the change", notExercised(idle));
      check("the day control changes neither price on a two-ticket row", notExercised(idle));
    }
    await page.goto(stateBefore);
    await installReader();
// The chosen day is part of the search, so it travels in the address like
    // the budget and the ticket type do. A shared link that opens on the day
    // the sender was reading is the whole reason a control like this is worth
    // having, and an address that forgets it on a refresh is a control the
    // reader has to set again every time they come back.
    const dayUrl = await page.evaluate(() => {
      const select = document.getElementById("serviceDay");
      const days = DATA.serviceDays || [];
      if (!select || days.length < 2) return null;
      const plain = window.location.href;
      const chosen = select.options[1] ? select.options[1].value : "1";
      select.value = chosen;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      // The whole address, not the query alone: this is handed to
      // page.goto below, and a bare query string is not a URL.
      const carried = window.location.href;
      const settled = Array.from(document.querySelectorAll("#rows tr[data-crs]")).map((tr) => ({
        crs: tr.getAttribute("data-crs"),
        time: tr.children[3].textContent.trim(),
        changes: tr.children[4].textContent.trim(),
      }));
      select.value = "0";
      select.dispatchEvent(new Event("change", { bubbles: true }));
      return {
        plain: plain,
        carried: carried,
        restored: window.location.href,
        settled: settled,
        chosen: chosen,
      };
    });
    if (dayUrl) {
      const opened = new URL(dayUrl.carried, "http://x").searchParams.get("day");
      const backHome = new URL(dayUrl.restored, "http://x").searchParams.get("day");
      await page.goto(dayUrl.plain);
      await page.goto(dayUrl.carried);
      const arrived = await page.evaluate(() => ({
        shown: document.getElementById("serviceDay") ? document.getElementById("serviceDay").value : "",
        cells: Array.from(document.querySelectorAll("#rows tr[data-crs]")).map((tr) => ({
          crs: tr.getAttribute("data-crs"),
          time: tr.children[3].textContent.trim(),
          changes: tr.children[4].textContent.trim(),
        })),
      }));
      check(
        "the day the reader picked is in the address, and the build's own day is not",
        opened === dayUrl.chosen && backHome === null,
        JSON.stringify({ carried: dayUrl.carried, restored: dayUrl.restored })
      );
      check(
        "and a link carrying that day opens the page on it, showing the same times",
        arrived.shown === dayUrl.chosen &&
          arrived.cells.length === dayUrl.settled.length &&
          arrived.cells.every((cell, at) =>
            cell.crs === dayUrl.settled[at].crs &&
            cell.time === dayUrl.settled[at].time &&
            cell.changes === dayUrl.settled[at].changes),
        JSON.stringify({ chosen: dayUrl.chosen, shown: arrived.shown, rows: arrived.cells.length })
      );
      await page.goto(dayUrl.plain);
    } else {
      const idle = "this page carries no week of days, so there is no day to put in the address";
      check("the day the reader picked is in the address, and the build's own day is not", notExercised(idle));
      check("and a link carrying that day opens the page on it, showing the same times", notExercised(idle));
    }
}
module.exports = { checkTheRowActions, checkTheTwoTicketRow };
