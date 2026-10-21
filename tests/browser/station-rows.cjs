/**
 * What a row does: the ticket link that goes where it says it goes (4), the
 * handoff text a reader pastes to a seller (5), and the party price a railcard
 * is applied to (6).
 *
 * The two-ticket row is here too, because it is the same subject from the
 * other end: a place the feed prices only in two parts is one row and two
 * purchases, and its panel names both tickets, both conditions and the split.
 */
const { SELLER, money, notExercised } = require("./harness.cjs");
async function checkTheRowActions(world) {
  const { page, check, notExercised } = world;
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
    // What the copy must say is read from the payload rather than matched
    // against a pattern: a real station's name has spaces in it
    // (LONDON KINGS X, NOTTINGHAM), and a one-word pattern rejected the
    // correct answer while accepting a wrong one on the demo feed.
    const rowText = (await page.textContent("#rows tr")).trim();
    // Copy and the railcard note wait in the row's own panel (finding 4,
    // 29 September 2026), so the row is opened first: a control a reader
    // reaches through a disclosure is still a control, and this is where the
    // suite meets it.
    await page.locator("#rows tr:not(.detail) .toggle[aria-expanded='false']").first().click();
    const adultButton = page.locator("#rows button[aria-label^='Copy journey']").first();
    const journey = await page.evaluate((label) => {
      const name = label.replace("Copy journey for ", "");
      const destination = TYPES.list().find((d) => d.name === name) || {};
      return {
        origin: DATA.origin.name + " (" + DATA.origin.crs + ")",
        destination: destination.name + " (" + destination.crs + ")",
      };
    }, await adultButton.getAttribute("aria-label"));
    await adultButton.click();
    await page.waitForFunction(
      () => /copied/i.test((document.getElementById("copyStatus") || {}).textContent || ""),
      null,
      { timeout: 3000 }
    ).catch(() => {});
    const adultCopy = await page.evaluate(() => navigator.clipboard.readText());
    check("the copy names the origin", adultCopy.includes("From: " + journey.origin), adultCopy);
    check("the copy names the destination", adultCopy.includes("To: " + journey.destination), adultCopy);
    check("the copy names the party size", /^Passengers: 1 adult$/m.test(adultCopy), adultCopy);
    const dated = await page.evaluate(() => Boolean(DATA.serviceDate));
    check(
      "the copy dates the journey when the build names a day, and not otherwise",
      dated === /^Date: /m.test(adultCopy),
      `${dated ? "a day" : "no day"}: ${adultCopy}`
    );
    check("one adult's copy does not mention a railcard", !/Railcard/.test(adultCopy), adultCopy);
    // The copy belongs to the row it was copied from, judged on the whole
    // station name rather than its first word, which two stations can share.
    check(
      "the row it copied is the row it sits on",
      adultCopy.includes("To: " + journey.destination) && rowText.includes(journey.destination),
      `${rowText} vs ${adultCopy}`
    );
    check(
      "and the copy is announced, not just performed",
      /copied/i.test(await page.textContent("#copyStatus"))
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
    // Copy and the railcard note wait in the row's own panel (finding 4,
    // 29 September 2026), so the row is opened first: a control a reader
    // reaches through a disclosure is still a control, and this is where the
    // suite meets it.
    await page.locator("#rows tr:not(.detail) .toggle[aria-expanded='false']").first().click();
    const copyButton = page.locator("#rows button[aria-label^='Copy journey']").first();
    const copiedName = (await copyButton.getAttribute("aria-label")).replace("Copy journey for ", "");
    // The railcard note is owed only where the feed prices one, so what the
    // copy should say is read off the row it is about to copy: a page with no
    // eligible fare must stay quiet rather than name a discount that is not there.
    // What the copy should say is read off the chosen card and the row it is
    // about to copy. A card the feed refused for that fare must stay unmentioned
    // rather than named as a discount that is not there.
    const railcardNamed = await page.evaluate((name) => {
      const row = DATA.destinations.find((d) => d.name === name);
      const select = document.getElementById("railcardSelect");
      if (!row || !select || !select.value) return false;
      const card = (row.railcards || {})[select.value];
      return Boolean(card && card.pricePence !== null);
    }, copiedName);
    await copyButton.click();
    await page.waitForFunction(
      () => /2 adults/.test((document.getElementById("copyStatus") || {}).textContent || ""),
      null,
      { timeout: 3000 }
    ).catch(() => {});
    const partyCopy = await page.evaluate(() => navigator.clipboard.readText());
    check("the party copy says two adults", /^Passengers: 2 adults$/m.test(partyCopy), partyCopy);
    check(
      "and names the railcard when the fare is eligible, and stays quiet when it is not",
      railcardNamed ? /discount is not sent to the seller/.test(partyCopy) : !/discount is not sent to the seller/.test(partyCopy),
      `${copiedName} ${railcardNamed ? "is" : "is not"} railcard-eligible: ${partyCopy}`
    );
    } else {
      const reason =
        `with Two adults selected this page's cheapest price is ${money(party.cheapest)} and its ` +
        `budget goes to ${money(party.ceiling)}, so no party row can be shown at any budget it allows`;
      for (const name of [
        "the party copy says two adults",
        "and names the railcard when the fare is eligible, and stays quiet when it is not",
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
      return row ? { crs: row.crs, adult: row.adultPence, tickets: row.tickets, changes: row.changes } : null;
    });
    if (twoTicketRow) {
      // The row is visited through the address, budget, page and day, so it
      // is on screen whatever the number of cheaper rows on a real page: a
      // changed day starts the table again at its first page.
      const budgetPounds = Math.ceil(twoTicketRow.adult / 100);
      await open(budgetPounds);
      const position = await page.evaluate((crs) => {
        const cap = Number(document.getElementById("budgetNumber").value) * 100;
        const wanted = activeDestinations().filter((d) => priceOf(d) <= cap).sort((a, b) => priceOf(a) - priceOf(b));
        return wanted.findIndex((d) => d.crs === crs);
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
      const splitWording = throughPriced
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
        JSON.stringify({ crs: twoTicketRow.crs, expected: expectedPrice, throughPriced: throughPriced, shown: shown })
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
