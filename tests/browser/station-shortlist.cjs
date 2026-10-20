/**
 * The shortlist: places held for comparison, shared and copied, that never
 * read as a booking.
 *
 * A row with no service is in here too, because a shortlist row has to say the
 * same thing the results row says about a day the network does not serve. And
 * the dock is compared with the row it came from rather than with a sentence
 * written here, because a shortlist showing a different price or a different
 * journey than the table would be a comparison of nothing.
 */
const { notExercised } = require("./harness.cjs");
async function checkTheShortlist(world) {
  const { page, check, notExercised, open, facts } = world;
    // 7d. S26: a shortlist of candidate places that can be compared, shared
    // and copied, and that never reads as a booking.
    await open(facts.affordable);
    const shortlist = await page.evaluate(() => {
      // Every priced row, not the one a cheapest-affordable budget happens to
      // leave: comparing two places needs two places on screen.
      setBudget(budgetCeiling());
      STATE.page = 1;
      render();
      const rows = Array.from(document.querySelectorAll("#rows tr[data-crs]"));
      if (rows.length < 2) return { rows: rows.length };
      // One checkbox on each row rather than a select above the table: the
      // control is beside the place it acts on, and holding a place is a tick
      // rather than finding its name in a list of names. Driven by click, so
      // what runs is the gesture a reader makes rather than a state set behind
      // their back.
      const add = (row) => {
        const box = row.querySelector(".hold-box");
        if (box) box.click();
      };
      const first = rows[0];
      const second = rows[1];
      const facts = () =>
        Array.from(document.querySelectorAll("#shortlistDockList tr")).map((tr) => tr.textContent);
      const saved = [];
      add(first);
      saved.push(facts());
      add(second);
      const both = facts();
      // What the dock offers once both places are on it, and the order they
      // are in. Read here, before the mode dance below changes what the page
      // is showing: a check written at the end of the block would be reading a
      // page the reader never saw at that point.
      const chips = () =>
        Array.from(document.querySelectorAll("#shortlistDockList tr")).map((tr) => ({
          text: tr.textContent,
          title: (tr.querySelector(".shortlist-dock-name") || {}).title || "",
        }));
      // Every rendered row's box against the list itself, in both directions:
      // a box ticked for a place that is not held is a row claiming something
      // the strip does not say, and a held place with an unticked box is one
      // the reader cannot see they are carrying.
      const boxes = Array.from(document.querySelectorAll("#rows tr[data-crs]")).map((row) => ({
        crs: row.dataset.crs,
        name: (row.querySelector(".station-name") || {}).textContent || "",
        held: Boolean((row.querySelector(".hold-box") || {}).checked),
        label: row.querySelector(".hold-box")
          ? row.querySelector(".hold-box").getAttribute("aria-label") || ""
          : "",
      }));
      const held = STATE.shortlist.slice();
      // The dock's row is a place and its price. The place and the price are
      // read off the table row it came from, and the order from the dock
      // itself, so this says the row agrees with the table rather than that the
      // page can compute its own number.
      const chipsAgainstRows = Array.from(document.querySelectorAll("#shortlistDockList tr")).map((tr) => {
        const name = (tr.querySelector(".shortlist-dock-name") || {}).textContent || "";
        const row = Array.from(document.querySelectorAll("#rows tr[data-crs]"))
          .find((r) => (r.querySelector(".station-name") || {}).textContent === name);
        return {
          text: tr.textContent,
          title: (tr.querySelector(".shortlist-dock-name") || {}).title || "",
          row: row
            ? {
              name,
              price: (row.querySelector("td.num .price") || {}).textContent || "",
            }
            : null,
        };
      });
      const address = window.location.href;
      // The party price is the price a pair would see, so the comparison has
      // to follow the party control.
      applyState({ unit: "party" });
      render();
      const asPair = facts();
      applyState({ unit: "adult" });
      render();
      const asSolo = facts();
      // A shortlist kept across a mode change must not keep a place whose fare
      // the reader can no longer see. Both named modes are tried, because a row
      // priced as a return leaves the list when the reader asks for singles.
      //
      // The change is fired as an event rather than assigned to .checked, so
      // the control's own handler runs. Assigning the property re-renders
      // without writing the address, which left the page holding one place
      // under a link that still promised two -- and the check below then read
      // the link's two and called a correct page wrong.
      const openedIn = ticketMode();
      const byMode = [];
      const chooseMode = (mode) => {
        const input = document.querySelector(`input[name="ticketMode"][value="${mode}"]`);
        if (!input || !modeCount(mode)) return false;
        input.checked = true;
        input.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      };
      for (const mode of ["single", "return"]) {
        if (!chooseMode(mode)) continue;
        byMode.push({ mode, texts: facts() });
        if (byMode[byMode.length - 1].texts.length) break;
      }
      chooseMode(openedIn);
      const share = document.getElementById("shortlistShare").textContent;
      return {
        both, asPair, asSolo, chipsAgainstRows, byMode, share, address,
        boxes,
        rowCount: rows.length,
        held,
        names: both.map((text) => text.slice(0, 24)),
      };
    });
    if (shortlist.rows !== undefined && shortlist.rows < 2) {
      for (const name of [
        "a shortlisted place is listed as its name and the price beside it",
        "and each chip is a way back to the row it came from",
        "and a place leaves the list when its fare is no longer on the page",
        "and the list is a list of destinations, not a booking",
        "every row carries a box, and a held place's box is ticked",
        "and a box is named for the place it holds",
        "and the change to the list is announced, not just drawn",
        "the shortlist is in the address, so it can be shared",
        "a refresh brings the shortlist back",
        "and it follows the party the reader has chosen",
        "one control clears it",
        "and every copied place names the fare that price is for",
      ]) {
        check(name, notExercised(`this page lists ${shortlist.rows} row(s) to choose from`));
      }
    } else {
      check(
        "a shortlisted place is listed as its name and the price beside it",
        shortlist.both.length === 2 &&
          shortlist.both.every((text) => /£\d/.test(text)) &&
          shortlist.chipsAgainstRows.every(
            (chip) =>
              chip.row &&
              chip.text.includes(chip.row.name) &&
              chip.text.includes(chip.row.price)
          ),
        JSON.stringify({ chips: shortlist.chipsAgainstRows, both: shortlist.both })
      );
      check(
        "and each chip is a way back to the row it came from",
        shortlist.chipsAgainstRows.length === 2 &&
          shortlist.chipsAgainstRows.every(
            (chip) => chip.row && chip.title.includes(chip.row.name)
          ),
        JSON.stringify(shortlist.chipsAgainstRows)
      );
      // A place whose fare the reader can no longer see leaves the list rather
      // than sitting on it as a name with no fare behind it.
      const followed = shortlist.byMode[0];
      check(
        "and a place leaves the list when its fare is no longer on the page",
        followed && followed.texts.every((text) => /£\d/.test(text)),
        JSON.stringify(shortlist.byMode)
      );
      // Said by the page's own copy of the list, which is the text the reader
      // hands to somebody, rather than by a sentence that used to sit above the
      // table and has gone with the rest of that section.
      const shared = await page.evaluate(() => ({
        text: typeof shortlistText === "function" ? shortlistText() : "",
        share: (document.getElementById("shortlistShare") || {}).textContent || "",
        origin: DATA.origin.name,
        held: shortlisted().length,
        url: location.href,
      }));
      check(
        "and the list is a list of destinations, not a booking",
        // The count is read from the list rather than fixed at two. A place
        // whose fare the mode cannot price leaves the shortlist by design, so
        // after the mode change the list may hold one place, and the share
        // line has to count what is actually held -- not what was held before
        // the reader changed their mind about the ticket type.
        /not a booking/i.test(shared.text) &&
          new RegExp(
            "^Shortlist of " + shared.held + " destination" + (shared.held === 1 ? "" : "s")
          ).test(shared.share) &&
          shared.share.includes(shared.origin),
        JSON.stringify(shared).slice(0, 300)
      );
      // The share line and the address are two renderings of one list, so a
      // place that left the shortlist has to leave the link too. They drifted
      // once: the list held one place and the link still named two, which sent
      // whoever followed it a shortlist the page did not have.
      check(
        "and the shared link names exactly the places the list holds",
        shared.held === new URL(shared.url).searchParams.getAll("short").length,
        JSON.stringify({ held: shared.held, url: shared.url })
      );
      check(
        "every row carries a box, and a held place's box is ticked",
        shortlist.boxes.length === shortlist.rowCount &&
          shortlist.boxes.every((row) => row.held === shortlist.held.includes(row.crs)) &&
          shortlist.held.every((crs) => {
            const row = shortlist.boxes.find((box) => box.crs === crs);
            return row && row.held;
          }),
        JSON.stringify({ boxes: shortlist.boxes, held: shortlist.held })
      );
      // A column of unticked boxes is a column of controls with no name of
      // their own, so each one has to say which place it holds.
      check(
        "and a box is named for the place it holds",
        shortlist.boxes.every(
          (row) => /^List .+ in the shortlist$/.test(row.label) && row.label.includes(row.name)
        ),
        JSON.stringify(shortlist.boxes.slice(0, 4))
      );
      const wanted = await page.evaluate(() => STATE.shortlist);
      check(
        "the shortlist is in the address, so it can be shared",
        wanted.every((code) => shortlist.address.includes("short=" + code)),
        shortlist.address
      );
      check(
        "and it follows the party the reader has chosen",
        shortlist.asPair.length === 2 && shortlist.asPair.some((text, index) => text !== shortlist.asSolo[index]),
        JSON.stringify({ pair: shortlist.asPair, solo: shortlist.asSolo })
      );
      check(
        "and the change to the list is announced, not just drawn",
        /Added .+ to the shortlist\./.test(await page.textContent("#shortlistStatus")),
        (await page.textContent("#shortlistStatus")) || ""
      );
      // A shared link is the whole point, so it is opened, not assumed.
      await page.goto(shortlist.address);
      const restored = await page.evaluate(() => Array.from(document.querySelectorAll("#shortlistDockList tr")).length);
      check("a refresh brings the shortlist back", restored === 2, `${restored} of 2`);
      const copied = await page.evaluate(() => {
        document.getElementById("shortlistCopy").click();
        return null;
      });
      void copied;
      // DL4 of the 19 October 2026 delight pass: the acknowledgement is visible,
      // not only in the live region -- the row's copy has always said "Copied",
      // and its twin in the dock saying nothing read as an oversight.
      const acknowledged = await page.waitForFunction(
        () => /^Copied$/.test((document.getElementById("shortlistCopy").textContent || "").trim()),
        null,
        { timeout: 2000 }
      ).then(() => true).catch(() => false);
      check(
        "the dock's Copy acknowledges the copy to the eye as well as the region",
        acknowledged,
        (await page.textContent("#shortlistCopy")) || ""
      );
      await page.waitForFunction(
        () => /copied|copy/i.test(document.getElementById("shortlistStatus").textContent || ""),
        null,
        { timeout: 3000 }
      ).catch(() => {});
      const text = await page.evaluate(() => navigator.clipboard.readText());
      check(
        "and the copied list names the origin, the prices and says it is not a booking",
        /Shortlist from /.test(text) && /Budget: /.test(text) && /not a booking/i.test(text) && text.includes("£"),
        text
      );
      const copiedPlaces = text.split("\n").filter((line) => line.startsWith("- "));
      check(
        "and every copied place names the fare that price is for",
        copiedPlaces.length === 2 &&
          copiedPlaces.every((line) =>
            /Standard outbound single|Advance single|Unrestricted Anytime Day Return|Standard return/.test(line)
          ),
        text
      );
      await open(facts.affordable);
      await page.evaluate(() => { document.getElementById("shortlistDockClear").click(); });
      check(
        "one control clears it",
        (await page.evaluate(() => document.querySelectorAll("#shortlistDockList tr").length)) === 0 &&
          !(await page.evaluate(() => window.location.search.includes("short="))),
        (await page.evaluate(() => document.getElementById("shortlistDockCount").textContent)) || ""
      );
    }
    // 7e. The dock: the shortlist held at the foot of the screen, and the four
    // layout promises a reader scrolling a long table depends on. Read out of
    // the rendered page, because every one of them is a claim about geometry
    // that a template string cannot settle.
    await page.setViewportSize({ width: 1280, height: 800 });
    await open(facts.affordable);
    const dockAtRest = await page.evaluate(() => {
      const dock = document.getElementById("shortlistDock");
      return {
        exists: Boolean(dock),
        hidden: dock ? dock.hidden : null,
        codes: typeof STATE === "undefined" ? null : STATE.shortlist.length,
      };
    });
    check(
      "the shortlist dock is on the page and shows nothing while nothing is shortlisted",
      dockAtRest.exists === true && dockAtRest.codes === 0 && dockAtRest.hidden === true,
      JSON.stringify(dockAtRest)
    );
    // Every shortlist control in one place. Copy and Share were in a section
    // between the count and the table while the rows were in the dock at the
    // foot of the screen, so a reader comparing two places had to look in two
    // places to hand the list to somebody.
    const dockControls = await page.evaluate(() => {
      const dock = document.getElementById("shortlistDock");
      const inside = (id) => Boolean(dock && dock.contains(document.getElementById(id)));
      const copy = document.getElementById("shortlistCopy");
      const share = document.getElementById("shortlistShareBox");
      const bar = document.getElementById("shortlistBar");
      return {
        copy: inside("shortlistCopy"),
        share: inside("shortlistShareBox"),
        clear: inside("shortlistDockClear"),
        copyWord: copy ? copy.textContent.trim() : "",
        shareWord: share ? (share.querySelector("summary") || {}).textContent || "" : "",
        bar: bar ? 1 : 0,
        barAfterCount: bar
          ? Boolean(bar.compareDocumentPosition(document.getElementById("summary")) & Node.DOCUMENT_POSITION_FOLLOWING)
          : false,
        boxInShare: Boolean(share && share.contains(document.getElementById("shortlistBox"))),
      };
    });
    check(
      "Copy, Share and Clear are all in the pinned dock",
      dockControls.copy && dockControls.share && dockControls.clear && dockControls.boxInShare &&
        /^copy$/i.test(dockControls.copyWord) && /^share$/i.test(dockControls.shareWord),
      JSON.stringify(dockControls)
    );
    check(
      "and there is no shortlist section left between the count and the table",
      dockControls.bar === 0 && !dockControls.barAfterCount,
      JSON.stringify(dockControls)
    );
    // A row with no service is a fact about the day the page is about, so these
    // two checks need a page that has a day: a build with no date has no week
    // to walk and there is nothing to report about one. Both shapes are put
    // into the page's own data under codes it has never seen -- the cheapest
    // list is rebuilt from the three ticket lists on every render, and a code it
    // already holds would be replaced rather than shown.
    //
    // Each row also carries `serviceWeekIndex: null`, which is what the build
    // sends for a row it holds no week for. Inheriting the source row's index
    // pointed the row at a week table that cannot name a code this test
    // invented, and the page then worded the absence from that table -- "any
    // day this week", which is the truth about the data it was handed. The
    // row's own next service is what these two checks are about, so the row
    // has to be one the page reads for its own next service.
    const noService = await page.evaluate(() => {
      const source = (DATA.destinations || [])[0];
      if (!source || !DATA.serviceDate) return null;
      const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
      const built = new Date(DATA.serviceDate + "T00:00:00Z");
      const weekday = built.getUTCDay();
      const later = new Date(built.getTime() + ((8 - weekday) % 7 || 7) * 86400000)
        .toISOString()
        .slice(0, 10);
      const shape = (crs, name, nextService) =>
        Object.assign({}, source, {
          crs: crs,
          name: name,
          minutes: null,
          changes: null,
          departures: [],
          journeyState: "no_service",
          serviceWeekIndex: null,
          nextService: nextService,
        });
      const kept = DATA.destinations;
      DATA.destinations = [
        shape("ZSVC", "SERVICE LATER", later),
        shape("ZNRV", "SERVICE NEVER", undefined),
      ];
      setBudget(budgetCeiling());
      STATE.page = 1;
      render();
      const read = (crs) => {
        const row = document.querySelector('#rows tr[data-crs="' + crs + '"]');
        if (!row) return null;
        const cells = Array.from(row.children).map((td) => td.textContent.trim());
        const toggle = row.querySelector(".toggle[aria-expanded=false]");
        if (toggle) toggle.click();
        const detail =
          row.nextElementSibling && row.nextElementSibling.classList.contains("detail")
            ? row.nextElementSibling
            : null;
        const record = detail
          ? Array.from(detail.querySelectorAll(".feed-record dd")).map((dd) => dd.textContent.trim())
          : [];
        return { time: cells[3], changes: cells[4], record: record.join(" | ") };
      };
      const out = { later: read("ZSVC"), never: read("ZNRV") };
      DATA.destinations = kept;
      setBudget(budgetCeiling());
      STATE.page = 1;
      render();
      const nextWeekday = days[new Date(later + "T00:00:00Z").getUTCDay()];
      return out.later ? { rows: out, weekday: days[weekday], nextWeekday: nextWeekday } : null;
    });
    if (noService) {
      check(
        "a row with no service on the page's day says so, and its details name that day",
        noService.rows.later.time === "No service that day" &&
          noService.rows.later.changes === "Unknown" &&
          /it runs on/.test(noService.rows.later.record),
        JSON.stringify({ ...noService.rows.later, weekday: noService.weekday })
      );
      check(
        "and a row the week never reaches says which days it was checked for",
        noService.rows.never.time === "No service that day" &&
          noService.rows.never.changes === "Unknown" &&
          /nor on the \d+ days after it/.test(noService.rows.never.record) &&
          !/it runs on/.test(noService.rows.never.record),
        JSON.stringify(noService.rows.never)
      );
    } else {
      check(
        "a row with no service on the page's day says so, and its details name that day",
        notExercised("this page lists no destination to clone, or carries no service date")
      );
      check(
        "and a row the week never reaches says which days it was checked for",
        notExercised("see above")
      );
    }
    // The reader picks the day the times are for. The control is driven the way
    // a reader drives it, by changing the select, rather than by writing the
    // page's own day index, because the listener is part of what is checked.
    // Four things have to be true of it. The build's own day is what the page
    // already showed, so the control cannot have moved a single cell when the
    // reader arrives. Some other day is a different set of answers, which is
    // the whole reason the control exists. Every absence names the day it is
    // about, on every day, because "No service" beside a station the network
    // serves on the other six reads as a claim about the station. And the row
    // set is restored when the reader comes back to the build's day.
    const dayControl = await page.evaluate(() => {
      const days = DATA.serviceDays || [];
      const bar = document.getElementById("serviceDayBar");
      const select = document.getElementById("serviceDay");
      const help = document.getElementById("serviceDayHelp");
      if (!bar || !select || days.length < 2) return null;
      const label = document.querySelector('label[for="serviceDay"]');
      const cells = () =>
        Array.from(document.querySelectorAll("#rows tr[data-crs]")).map((tr) => {
          const td = tr.children;
          return {
            crs: tr.getAttribute("data-crs"),
            time: td[3].textContent.trim(),
            changes: td[4].textContent.trim(),
          };
        });
      const pick = (index) => {
        select.value = String(index);
        select.dispatchEvent(new Event("change", { bubbles: true }));
      };
      // Day zero read from the payload, not from the cells, so a row the
      // current budget or page number has hidden is compared all the same.
      // journeyFor on day zero is the row's own recorded answer by
      // construction, so this asks whether the build's own week table agrees
      // with the build's own per-row answer it was derived from.
      const drift = (DATA.destinations || []).filter((row) => {
        const answer = serviceAnswer(row);
        if (answer === undefined) return false;
        const found = answer !== null;
        return (
          found !== (row.journeyState === "found") ||
          (found && (answer[0] !== row.minutes || answer[1] !== row.changes))
        );
      });
      const before = cells();
      const baseline = new Map(before.map((cell) => [cell.crs, cell]));
      const movedPerDay = [];
      const unnamed = [];
      // Audit item 22, 14 October 2026: a cell in a column of durations holds
      // the short state, and the day it is about is in the row's own details.
      // Both are read here: no cell may hold a clause, and the row behind one
      // of them must name the day the reader chose.
      const SHORT_ABSENCE = "No service that day";
      for (let index = 1; index < days.length; index += 1) {
        pick(index);
        let moved = 0;
        let sample = null;
        for (const cell of cells()) {
          const was = baseline.get(cell.crs);
          if (was && (was.time !== cell.time || was.changes !== cell.changes)) moved += 1;
          if (!/^No service/.test(cell.time)) continue;
          if (cell.time === SHORT_ABSENCE) {
            if (!sample) sample = cell.crs;
            continue;
          }
          unnamed.push({ day: days[index], crs: cell.crs, time: cell.time, where: "the Time cell" });
        }
        if (sample) {
          const row = document.querySelector(`#rows tr[data-crs="${sample}"]`);
          const toggle = row && row.querySelector(".row-expand");
          if (toggle) {
            if (toggle.getAttribute("aria-expanded") === "false") toggle.click();
            const panel = document.getElementById(toggle.getAttribute("aria-controls"));
            const text = panel ? panel.textContent : "";
            if (!text.includes(humanDate(days[index]))) {
              unnamed.push({ day: days[index], crs: sample, where: "the row's details", text: text.slice(0, 140) });
            }
            if (toggle.getAttribute("aria-expanded") === "true") toggle.click();
          }
        }
        movedPerDay.push(moved);
      }
      pick(0);
      const restored = cells();
      return {
        days: days,
        built: DATA.serviceDate || "",
        optionCount: select.options.length,
        firstOption: select.options[0] ? select.options[0].textContent : "",
        selected: select.value,
        label: label ? label.textContent.trim() : "",
        help: help ? help.textContent.trim() : "",
        helpIsDescribedBy: Boolean(help && select.getAttribute("aria-describedby") === help.id),
        visible: !bar.hidden,
        rows: before.length,
        drift: drift.length,
        driftSample: drift.slice(0, 3).map((row) => row.crs),
        movedPerDay: movedPerDay,
        movedTotal: movedPerDay.reduce((total, count) => total + count, 0),
        unnamed: unnamed.slice(0, 4),
        unnamedTotal: unnamed.length,
        restored:
          restored.length === before.length &&
          restored.every((cell, at) => cell.time === before[at].time && cell.changes === before[at].changes),
      };
    });
    if (dayControl) {
      check(
        "the day control offers every day the build walked, its own day first and named",
        dayControl.optionCount === dayControl.days.length &&
          dayControl.days[0] === dayControl.built &&
          // The weekday leads and the date follows. Two Sundays are not the
          // same day: from Grantham, 4 Oct 2026 reaches 238 stations and
          // 11 Oct reaches 416 (ADR-0060), so an option that named only the
          // weekday would be a claim the feed does not carry, and one that
          // named only "this build" told a reader nothing about which date.
          /^(Mon|Tue|Wed|Thu|Fri|Sat|Sun), \d{1,2} [A-Z][a-z]+ \d{4}$/.test(
            dayControl.firstOption
          ) &&
          !/\(this build\)/.test(dayControl.firstOption) &&
          dayControl.selected === "0",
        JSON.stringify({ days: dayControl.days.length, built: dayControl.built, first: dayControl.firstOption })
      );
      check(
        "and it is labelled, described by its help text, and on show",
        // D4 of the 17 October 2026 critique: the help line is one clause about
        // the limitation, not three about why the control exists.
        /^Times for$/.test(dayControl.label) && dayControl.help.length > 0 &&
          dayControl.help.length <= 90 && /interchange/i.test(dayControl.help) &&
          dayControl.helpIsDescribedBy && dayControl.visible,
        JSON.stringify({ label: dayControl.label, help: dayControl.help, described: dayControl.helpIsDescribedBy, shown: dayControl.visible })
      );
      check(
        "the build's own day is the day the page already showed",
        dayControl.drift === 0 && dayControl.restored,
        JSON.stringify({ rows: dayControl.rows, disagreeing: dayControl.drift, sample: dayControl.driftSample, restored: dayControl.restored })
      );
      if (dayControl.movedTotal > 0) {
        check(
          "another day in the build's week is a different set of times",
          true,
          JSON.stringify({ movedPerDay: dayControl.movedPerDay, rows: dayControl.rows })
        );
      } else {
        check(
          "another day in the build's week is a different set of times",
          notExercised(`all ${dayControl.movedPerDay.length} later day(s) answered every row on screen the same way`),
          JSON.stringify({ movedPerDay: dayControl.movedPerDay })
        );
      }
      check(
        "and every absence on every day names the day it is about",
        dayControl.unnamedTotal === 0,
        JSON.stringify({ unnamed: dayControl.unnamedTotal, sample: dayControl.unnamed })
      );
    } else {
      const idle = "this page carries no week of days, so the control is not on it";
      check("the day control offers every day the build walked, its own day first and named", notExercised(idle));
      check("and it is labelled, described by its help text, and on show", notExercised(idle));
      check("the build's own day is the day the page already showed", notExercised(idle));
      check("another day in the build's week is a different set of times", notExercised(idle));
      check("and every absence on every day names the day it is about", notExercised(idle));
    }
}
/**
 * Every cell in the dock row sits under a heading and every heading has a
 * cell, which is the fault a prices-only build had: the columns stood down by
 * position rather than by name and left a remove button under nothing at all.
 */
async function compareTheDockWithTheTable(world) {
  const { page, check, notExercised, facts } = world;
    // The split note points at "the station above", which is printed only on
    // the build's own day. On any other day the Changes cell prints a count and
    // no station, so a note still naming one is a row claiming to change where
    // the row beside it reads Direct. Read on every day, because the days that
    // disagree are not the ones that happen to be showing.
    const splitByDay = await page.evaluate(() => {
      const select = document.getElementById("serviceDay");
      const days = DATA.serviceDays || [];
      if (!select || days.length < 2) return null;
      const row = (DATA.destinations || []).find((r) => (r.changeStations || []).length && !r.tickets);
      if (!row) return null;
      // The row is put on screen on its own, the way the no-service check
      // above stages its rows. Read where it fell in the full list, a real
      // page's first screen often holds none of its changed rows, the cell
      // was empty, and an empty cell read as a day claiming a split.
      const kept = DATA.destinations;
      const keptBudget = document.getElementById("budget").value;
      // And in the list it comes from: the row is a return, and on the
      // "cheapest of any type" view the table is built from every list, so
      // the cell read was another row's or none.
      const keptMode = (document.querySelector('input[name="ticketMode"]:checked') || {}).value;
      // Through the state, not by assigning the radio: the page draws its
      // controls from the state now, so an assignment is undone by the next
      // render and this setup would have measured the mode it came in with.
      applyState({ mode: "return" });
      DATA.destinations = [row];
      setBudget(budgetCeiling());
      STATE.page = 1;
      render();
      const clashes = [];
      for (let i = 0; i < days.length; i += 1) {
        select.value = String(i);
        select.dispatchEvent(new Event("change", { bubbles: true }));
        const tr = document.querySelector(`#rows tr[data-crs="${row.crs}"]`);
        const cell = tr ? tr.children[4].textContent.trim() : "";
        // The note is in the row's own detail panel, which is only built when
        // the reader opens it, so it is asked for as the page would build it.
        const note = splitNote(row);
        if (note && !/via /.test(cell)) clashes.push({ day: days[i], cell: cell });
      }
      DATA.destinations = kept;
      if (keptMode) applyState({ mode: keptMode });
      select.value = "0";
      select.dispatchEvent(new Event("change", { bubbles: true }));
      setBudget(keptBudget);
      STATE.page = 1;
      render();
      return { crs: row.crs, days: days.length, clashes: clashes };
    });
    if (splitByDay) {
      check(
        "no day claims a split ticket at a station the row does not name",
        splitByDay.clashes.length === 0,
        JSON.stringify(splitByDay)
      );
    } else {
      check(
        "no day claims a split ticket at a station the row does not name",
        notExercised("no destination on this page changes")
      );
    }
    // The composition note reads as part of the table rather than as another
    // paragraph above it. It is reference material about how the list was built,
    // the same class of sentence the provenance block holds, and the gap it
    // leaves above the first row is the reason it moved.
    const notePlacement = await page.evaluate(() => {
      const note = document.getElementById("modeNote");
      const first = document.querySelector("#rows tr[data-crs]");
      const table = document.querySelector("table");
      if (!note || !first || !table) return null;
      const afterFirstRow = note.getBoundingClientRect().top > first.getBoundingClientRect().top;
      // compareDocumentPosition answers where the note is relative to the
      // table, so a note after the table comes back as FOLLOWING.
      const afterTable = Boolean(table.compareDocumentPosition(note) & Node.DOCUMENT_POSITION_FOLLOWING);
      return {
        text: (note.textContent || "").trim(),
        afterFirstRow,
        afterTable,
        top: Math.round(note.getBoundingClientRect().top),
        firstRowTop: Math.round(first.getBoundingClientRect().top),
      };
    });
    check(
      "how the list was composed is said below the rows, not above them",
      notePlacement && notePlacement.text.length > 0 &&
        notePlacement.afterFirstRow && notePlacement.afterTable,
      JSON.stringify(notePlacement)
    );
    // The first column is a membership mark, and a membership mark reads as
    // centred rather than as a box in a left-hand gutter.
    const firstColumn = await page.evaluate(() => {
      const th = document.querySelector("thead th.hold");
      const td = document.querySelector("#rows td.hold");
      return {
        head: th ? th.textContent.trim() : null,
        headAlign: th ? getComputedStyle(th).textAlign : null,
        cellAlign: td ? getComputedStyle(td).textAlign : null,
      };
    });
    check(
      // Audit item 13, 9 October 2026: the dock, its count and its clear button
      // already say Shortlist, and the column head now says it too.
      "the first column is named Shortlist, and centred",
      firstColumn.head === "Shortlist" && firstColumn.headAlign === "center" && firstColumn.cellAlign === "center",
      JSON.stringify(firstColumn)
    );
    const dock = await page.evaluate(() => {
      setBudget(budgetCeiling());
      STATE.page = 1;
      render();
      const boxes = Array.from(document.querySelectorAll("#rows tr[data-crs] .hold-box"));
      if (boxes.length < 2) return { rows: boxes.length };
      boxes[0].click();
      boxes[1].click();
      const read = (tr) => {
        const cells = Array.from(tr.children).map((td) => td.textContent.trim());
        const labelled = {};
        for (const td of tr.children) {
          const label = td.dataset.label;
          if (label && !(label in labelled)) labelled[label] = td.textContent.trim();
        }
        // The two tables do not label their cells the same way: the results
        // row carries data-label on every cell, and the dock row carries none,
        // because the dock's own headings are fixed and it is narrower than the
        // results table. So the dock row is read by position against the
        // headings above it. The last heading is the remove button and carries
        // no text, so it is named here rather than skipped by an emptiness
        // test -- which is what dropped the Changes column and made the check
        // ask a price-only page for a journey time it had no source for.
        const headings = Array.from(
          document.querySelectorAll("#shortlistDock table thead th")
        ).map((th, index) =>
          th.textContent.trim() || (index === 4 ? "Remove" : "")
        );
        if (!Object.keys(labelled).length && headings.length) {
          headings.forEach((name, index) => {
            if (name && !(name in labelled)) {
              labelled[name] = cells[index] === undefined ? "" : cells[index];
            }
          });
        }
        return { cells, labelled };
      };
      // Whether this build has a timetable, read inside the page. It was read
      // from DATA on the Node side of this evaluate, where DATA does not exist,
      // and the throw ended the run silently -- 193 checks passed and the rest
      // of the page was never driven.
      const hasJourneys = Boolean(DATA.hasJourneys);
      const dockHeadings = document.querySelectorAll("#shortlistDock table thead th").length;
      const firstDockRow = document.querySelector("#shortlistDockList tr");
      const widths = { headings: dockHeadings, rowCells: firstDockRow ? firstDockRow.children.length : 0 };
      const element = document.getElementById("shortlistDock");
      const box = element.getBoundingClientRect();
      return {
        rows: element.querySelectorAll("#shortlistDockList tr").length,
        hidden: element.hidden,
        hasJourneys,
        widths,
        position: getComputedStyle(element).position,
        atFootOfScreen: Math.round(box.bottom) === window.innerHeight,
        cells: Array.from(element.querySelectorAll("#shortlistDockList tr")).map((tr) => {
          const crs = tr.dataset.crs;
          const row = document.querySelector('#rows tr[data-crs="' + crs + '"]');
          return {
            crs,
            here: read(tr),
            there: row ? read(row) : null,
            drop: Boolean(tr.querySelector(".shortlist-drop")),
            labelled: (tr.querySelector(".shortlist-drop") || {}).getAttribute
              ? tr.querySelector(".shortlist-drop").getAttribute("aria-label") || ""
              : "",
          };
        }),
      };
    });
    if (dock.rows >= 2) {
      check(
        "shortlisting a place puts a row in a dock held at the foot of the screen",
        dock.rows === 2 && dock.hidden === false && dock.position === "fixed" && dock.atFootOfScreen,
        JSON.stringify({ rows: dock.rows, hidden: dock.hidden, position: dock.position, foot: dock.atFootOfScreen })
      );
      // The dock row is compared with the row it came from rather than with a
      // sentence written here: a shortlist that showed a different price or a
      // different journey than the table would be a comparison of nothing.
      // The results row carries a code and a second price the dock has no room
      // for, so each fact is checked against its own cell's leading token.
      //
      // The results cells are found by their column label rather than by
      // position. A prices-only build stands the Time and Changes columns down,
      // which shifts every cell after them, so a fixed index read 'Fare type'
      // as the journey time and failed a page that was correct. The dock keeps
      // its own time and change columns whatever the build has, so the two are
      // compared on the facts both of them carry.
      check(
        "a dock row names its station, price, time and changes, and agrees with the row above",
        dock.cells.every((entry) => {
          const here = entry.here.labelled;
          const there = entry.there;
          if (!there || !there.labelled || !here.Station) return false;
          return (
            there.labelled.Station.startsWith(here.Station) &&
            /^£\d/.test(here.Price) &&
            there.labelled.Price.trim().startsWith(here.Price) &&
            // A build with no timetable stands the dock's Time and Changes
            // columns down along with the table's, so there is nothing on
            // either side to compare and the row has to agree on the facts it
            // does carry. Where the columns are present they must say the same
            // thing in both places.
            (!here.Time
              ? true
              : dock.hasJourneys
                ? there.labelled.Time === here.Time &&
                  there.labelled.Changes.split(/\s+/)[0] === here.Changes
                : /no timetable|unknown/i.test(there.labelled.Time) ===
                  /no timetable/i.test(here.Time))
          );
        }),
        JSON.stringify(dock.cells)
      );
      check(
        "and every dock row can be taken off the shortlist from the dock itself",
        dock.cells.every((entry) => entry.drop && entry.labelled.startsWith("Remove " + entry.here.labelled.Station + " from")),
        JSON.stringify(dock.cells.map((entry) => entry.labelled))
      );
      // Every cell in the dock row sits under a heading, and every heading has
      // a cell. A prices-only build stood the dock's Time and Changes headings
      // down by position rather than by name, which left a five-cell row under
      // three headings and a remove button under nothing at all.
      check(
        "every dock cell sits under a heading of its own",
        dock.widths && dock.widths.rowCells === dock.widths.headings,
        JSON.stringify(dock.widths)
      );
      const tail = await page.evaluate(() => {
        window.scrollTo(0, document.body.scrollHeight);
        const rows = Array.from(document.querySelectorAll("#rows tr[data-crs]"));
        const last = rows[rows.length - 1].getBoundingClientRect();
        const element = document.getElementById("shortlistDock").getBoundingClientRect();
        return {
          lastBottom: Math.round(last.bottom),
          dockTop: Math.round(element.top),
          padding: document.body.style.paddingBottom,
          viewport: window.innerHeight,
        };
      });
      check(
        "the dock covers no results: the last row ends above it at the foot of the page",
        tail.lastBottom <= tail.dockTop && tail.lastBottom <= tail.viewport && parseFloat(tail.padding) > 0,
        JSON.stringify(tail)
      );
      await page.setViewportSize({ width: 390, height: 720 });
      const stacked = await page.evaluate(() => {
        const element = document.getElementById("shortlistDock");
        const row = element.querySelector("#shortlistDockList tr");
        return {
          table: getComputedStyle(element.querySelector("table")).display,
          body: getComputedStyle(element.querySelector("tbody")).display,
          cell: row ? getComputedStyle(row.children[0]).display : null,
          overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth,
          inScreen: Math.round(element.getBoundingClientRect().width) <= window.innerWidth,
        };
      });
      await page.setViewportSize({ width: 1280, height: 800 });
      check(
        "the dock keeps its four columns on a phone rather than stacking every cell",
        stacked.table === "table" && stacked.body === "table-row-group" && stacked.cell === "table-cell" &&
          stacked.inScreen && stacked.overflow <= 0,
        JSON.stringify(stacked)
      );
      const headings = await page.evaluate(() => {
        const head = document.querySelector("#shortlistDock th.num");
        const cell = document.querySelector("#shortlistDock tbody td.num");
        if (!head || !cell) return null;
        const h = head.getBoundingClientRect();
        const c = cell.getBoundingClientRect();
        return {
          align: getComputedStyle(head).textAlign,
          left: Math.round(h.left - c.left),
          right: Math.round(h.right - c.right),
        };
      });
      check(
        "a dock heading stands over its own column",
        Boolean(headings) && headings.align === "right" &&
          Math.abs(headings.left) < 1.5 && Math.abs(headings.right) < 1.5,
        JSON.stringify(headings)
      );
      await page.evaluate(() => { document.getElementById("shortlistDockClear").click(); });
      const cleared = await page.evaluate(() => ({
        rows: document.querySelectorAll("#shortlistDockList tr").length,
        hidden: document.getElementById("shortlistDock").hidden,
        padding: document.body.style.paddingBottom,
        // The tick on a row is the shortlist drawn on the row, so clearing the
        // list has to clear them. It did not: the boxes kept their ticks and the
        // page showed two places held above a list of none.
        ticked: Array.from(document.querySelectorAll("#rows input.hold-box"))
          .filter((box) => box.checked).length,
        listed: document.querySelectorAll("#shortlistDockList tr").length,
      }));
      check(
        "the dock's own Clear empties it and takes the strip off the screen",
        cleared.rows === 0 && cleared.hidden === true && cleared.padding === "",
        JSON.stringify(cleared)
      );
      check(
        "and clearing the shortlist clears the tick on every row",
        cleared.ticked === 0 && cleared.listed === 0 && dock.cells.length > 0,
        JSON.stringify(cleared)
      );
    } else {
      for (const name of [
        "shortlisting a place puts a row in a dock held at the foot of the screen",
        "a dock row names its station, price, time and changes, and agrees with the row above",
        "and every dock row can be taken off the shortlist from the dock itself",
        "every dock cell sits under a heading of its own",
        "the dock covers no results: the last row ends above it at the foot of the page",
        "the dock keeps its four columns on a phone rather than stacking every cell",
        "the dock's own Clear empties it and takes the strip off the screen",
      ]) {
        check(name, notExercised(`this page lists ${dock.rows} row(s) to choose from`));
      }
    }
}
module.exports = { checkTheShortlist, compareTheDockWithTheTable };
