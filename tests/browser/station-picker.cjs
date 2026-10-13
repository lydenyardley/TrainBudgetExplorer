/**
 * 8. The origin picker: search, navigate, and the no-match wording (ADR-0019).
 *
 * Choosing a station is navigation, so the link must go to another page, and
 * there must never be an empty picker. The field's three keys and its
 * completion are asked the same question the chooser is asked, from the page's
 * own station list rather than from a name a fixture happens to carry, so a
 * build of one station and a build of three thousand are driven the same way.
 */
const { completionProbe, expectedCompletion, notExercised } = require("./harness.cjs");
async function checkTheOriginPicker(world) {
  const { page, check, notExercised, open, facts } = world;
    // 8. The origin picker: search, navigate, and the no-match wording
    // (ADR-0019). Choosing a station is navigation, so the link must go to
    // another page, and there must never be an empty picker.
    await page.setViewportSize({ width: 1280, height: 800 });
    await open(facts.affordable);
    // The layout's thesis: the budget leads, and row actions carry real touch
    // targets. Measured, not assumed.
    const layout = await page.evaluate(() => {
      // The two actions a row keeps beside buying are inside the row's panel, so
      // a panel is opened for the measurement and closed again: a target this
      // gate never sees is a promise nobody measured.
      const copyHitInPanel = (measure) => {
        const already = document.querySelector("#rows tr.detail button[aria-label^='Copy']");
        if (already) return measure(already);
        const expander = document.querySelector("#rows tr:not(.detail) .toggle[aria-expanded='false']");
        if (!expander) return 0;
        expander.click();
        const button = document.querySelector("#rows tr.detail button[aria-label^='Copy']");
        const size = button ? measure(button) : 0;
        expander.click();
        return size;
      };
      const toPx = (v) => parseFloat(v);
      const budgetSize = toPx(getComputedStyle(document.getElementById("budgetNumber")).fontSize);
      const h1Size = toPx(getComputedStyle(document.querySelector("h1")).fontSize);
      const secondary = document.querySelector(".filter-bar .party-filter");
      const destinationFilter = document.querySelector(".filter-bar .destination-filter");
      const hitOf = (el) => { const r = el.getBoundingClientRect();
        // The ::after slop is positioned relative to the padding box. It
        // renders only when the element has position: relative (both do).
        const cs = getComputedStyle(el, "::after");
        if (cs.content !== '""') return Math.round(r.height);
        // The slop's reach is read from its computed insets rather than
        // assumed: .buy sizes its reach from its own line box, so a fixed
        // figure here would credit a reach the page does not draw.
        const reach = (name) => { const v = parseFloat(cs[name]); return Number.isFinite(v) ? Math.abs(v) : 0; };
        return Math.round(r.height + reach("top") + reach("bottom")); };
      return {
        budgetLeads: budgetSize >= h1Size,
        secondaryHoldsPartyAndFilter: !!secondary &&
          !!secondary.querySelector('input[name="unit"]') && !!destinationFilter &&
          !!destinationFilter.querySelector('input[name="destinationType"]'),
        copyHit: copyHitInPanel(hitOf),
        buyHit: hitOf(document.querySelector("#rows a.buy"))
      };
    });
    check("the budget is inline in the large heading", layout.budgetLeads);
    check("party and destination filters share the horizontal bar", layout.secondaryHoldsPartyAndFilter);
    // The disclosure's own name and what it says is on. A folded panel whose
    // summary line reads as a sentence rather than as three labelled facts
    // leaves a reader on a phone unable to tell which of the three is narrowed.
    const filterBar = await page.evaluate(() => {
      const more = document.getElementById("moreFilters");
      const toggle = document.getElementById("moreFiltersToggle");
      const panel = document.getElementById("moreFiltersPanel");
      if (!more || !toggle || !panel) return null;
      const wasOpen = more.dataset.open === "true";
      if (!wasOpen) document.getElementById("moreFiltersToggle").click();
      const openStyle = getComputedStyle(panel);
      const toggleStyle = getComputedStyle(toggle);
      const closed = {
        display: openStyle.display,
        columns: openStyle.gridTemplateColumns,
        gap: openStyle.gap,
        background: openStyle.backgroundColor,
        padding: openStyle.paddingTop,
        marginBottom: openStyle.marginBottom,
        toggleMarginBottom: toggleStyle.marginBottom,
      };
      const state = document.getElementById("filterState").textContent;
      const label = (toggle.querySelector(".more-filters-label") || {}).textContent || "";
      if (!wasOpen) document.getElementById("moreFiltersToggle").click();
      return { closed, state: state.trim(), label: label.trim() };
    });
    if (filterBar) {
      // The panel is two columns with the page's own gaps, and it carries no
      // fill and no gap under it: the shape is drawn by the border it shares
      // with the toggle, so a tint here would say "card" a second time.
      check(
        "the filter panel opens as a two-column grid with no fill of its own",
        filterBar.closed.display === "grid" &&
          filterBar.closed.columns.split(" ").length === 2 &&
          filterBar.closed.columns.split(" ").every((part) => parseFloat(part) > 0) &&
          filterBar.closed.gap === "16px 32px" &&
          filterBar.closed.background === "rgba(0, 0, 0, 0)" &&
          filterBar.closed.padding === "16px" &&
          filterBar.closed.marginBottom === "0px" &&
          filterBar.closed.toggleMarginBottom === "0px",
        JSON.stringify(filterBar.closed)
      );
      check(
        "the disclosure is named Filter this list",
        /^filter this list$/i.test(filterBar.label),
        JSON.stringify(filterBar.label)
      );
      check(
        "the summary names what is narrowed, counts the railcard and says All",
        /^Ticket: Cheapest of any type \u00b7 Travellers: One adult, 0 railcard \u00b7 Destination: All$/.test(
          filterBar.state
        ),
        JSON.stringify(filterBar.state)
      );
    } else {
      check(
        "the filter panel opens as a two-column grid on the field background",
        notExercised("this page carries no filter bar")
      );
      check("the disclosure is named Filter this list", notExercised("see above"));
      check("the summary names what is narrowed, counts the railcard and says All", notExercised("see above"));
    }
    check("the copy action carries a 44px target", layout.copyHit >= 44, layout.copyHit + "px");
    check("the buy link carries a 44px target", layout.buyHit >= 44, layout.buyHit + "px");
    // The change control exists exactly when the build wrote another station's
    // page, and both halves of that are asserted here. The block below drives
    // it, so a control that is present must work; and a page with nowhere to
    // change to must not carry an inert one, which is the bug this replaced.
    // Dropping the control everywhere would otherwise pass by testing less.
    const pickerState = await page.evaluate(() => ({
      others: (DATA.stations || []).length,
      control: Boolean(document.getElementById("changeOrigin")),
    }));
    check(
      "the change control appears exactly when the build has another station",
      pickerState.control === (pickerState.others > 0),
      `${pickerState.others} other station(s), control rendered: ${pickerState.control}`
    );
    const pickerButton = page.locator("#changeOrigin");
    if (await pickerButton.count()) {
      await pickerButton.click();
      check("Change opens the picker", await page.locator("#originPicker").isVisible());
      const pickCount = await page.locator("#originPicks a").count();
      check("the picker lists stations without typing", pickCount > 0, `${pickCount} options`);
      // The cap is said where the rows stop: station search is one behaviour
      // with one cap and one sentence, wherever a reader types a station name
      // (route audit items 10 and 22, 9 October 2026).
      const pickCap = await page.evaluate(() => ({
        rows: document.querySelectorAll("#originPicks a").length,
        cap: STATION_LIST_CAP,
        total: (DATA.stations || []).length,
        text: (document.getElementById("originCap") || {}).textContent || "",
        hidden: (document.getElementById("originCap") || {}).hidden,
      }));
      check(
        "the picker shows the cap and says how many stations it is hiding",
        pickCap.total <= pickCap.cap ||
          (pickCap.rows === pickCap.cap &&
            pickCap.hidden === false &&
            new RegExp("Showing " + pickCap.cap + " of " + pickCap.total).test(pickCap.text)),
        JSON.stringify(pickCap)
      );
      const href = pickCount
        ? await page.locator("#originPicks a").first().getAttribute("href")
        : null;
      // Judged against the base the page itself carries, not a root-absolute
      // path: a project site is published under owner.github.io/repo/ and
      // prefixes every internal link with it (ADR-0024), so a check that
      // demanded /from/ would fail the published page and only that page.
      const baseHref = await page.evaluate(() => DATA.baseHref);
      // The path is the route; the query is the reader's search state (S05),
      // so it is judged on the path alone and then checked separately below.
      const route = href === null ? null : new URL(href, "http://x").pathname;
      check(
        "options are links to station pages",
        route === null
          ? notExercised("this page lists no other station to link to")
          : route.startsWith(baseHref + "from/") && route.endsWith("/") && route.length > baseHref.length + 6,
        href === null ? "" : `${href} under base ${baseHref}`
      );
      // S06: choosing another station is a correction of where the reader is
      // leaving from, so the option carries the search they have already made.
      check(
        "the option carries the budget on screen",
        href === null
          ? notExercised("this page lists no other station to link to")
          : new URL(href, "http://x").searchParams.get("budget") === (await page.inputValue("#budgetNumber")),
        href === null ? "" : href
      );
      // The query comes from the picker's own first option, so the check is
      // about narrowing rather than about a station name the fixture happened
      // to carry.
      const firstWord = pickCount
        ? (((await page.locator("#originPicks a").first().textContent()) || "").trim().split(/[\s(]+/)[0] || "")
        : "";
      const query = firstWord.slice(0, 4);
      await page.fill("#originSearch", query);
      const narrowed = await page.locator("#originPicks a").count();
      const narrowedText = await page.locator("#originPicks").textContent();
      // S11: the same tolerant match the chooser has, on the page that offers
      // thousands of stations rather than three.
      const listedCrses = await page.evaluate(() => DATA.stations.map((station) => station.crs));
      // Lowercased to match the page, which lowercases what the reader typed
      // before comparing: a code in the address bar is upper case.
      const fragment = (listedCrses[0] || "").slice(0, 2).toLowerCase();
      await page.fill("#originSearch", fragment);
      const byFragment = await page.evaluate(() =>
        Array.from(document.querySelectorAll("#originPicks a")).map((a) => ({
          code: (a.querySelector(".code") || {}).textContent || "",
          name: (a.querySelector("span") || {}).textContent || "",
        }))
      );
      check(
        "a code fragment finds its station in the picker",
        fragment && byFragment.length > 0 && byFragment.some((row) => row.code.toLowerCase().startsWith(fragment)) &&
          byFragment.every((row) => row.code.toLowerCase().startsWith(fragment) || row.name.toLowerCase().includes(fragment)),
        `${fragment} -> ${byFragment.map((row) => row.code).join(" ") || "nothing"}`
      );
    // The completion is a word inside the field, and the field is a word inside
    // the heading, so three keys matter: Backspace to take the suggestion back,
    // and Tab or Enter to go to the place it names. The prefix comes from the
    // page's own station list rather than from a name the fixture happened to
    // carry, so a build of one station and a build of three thousand are asked
    // the same question.
    const completable = await page.evaluate(() => {
      const list = (typeof STATIONS !== "undefined" ? STATIONS : DATA.stations) || [];
      return list
        .map((station) => station.name)
        .filter((name) => name.length >= 8)
        .sort((a, b) => a.length - b.length)[0] || "";
    });
    const canComplete = completable.length >= 4;
    const prefix = completable.slice(0, 3);
    const headingHeight = () =>
      page.evaluate(() => {
        const heading = document.getElementById("pageHeading");
        return heading ? Math.round(heading.getBoundingClientRect().height) : -1;
      });
    await page.fill("#originSearch", "");
    const heights = [await headingHeight()];
    if (canComplete) {
      await page.focus("#originSearch");
      await page.type("#originSearch", prefix, { delay: 10 });
      const completed = await page.inputValue("#originSearch");
      heights.push(await headingHeight());
      // The completion is a suggestion, so it is written with its tail
      // selected. Backspace has to remove what was suggested, not consume one
      // character of the name the reader typed: it re-applied the suggestion to
      // its own undo, so the field came back byte-identical and the key looked
      // dead.
      await page.keyboard.press("Backspace");
      const taken = await page.inputValue("#originSearch");
      check(
        "Backspace takes the completion back",
        completed.toLowerCase().startsWith(prefix.toLowerCase()) && taken === prefix,
        `${prefix} -> "${completed}" -> Backspace -> "${taken}"`
      );
      await page.keyboard.press("Backspace");
      const shorter = await page.inputValue("#originSearch");
      check(
        "and Backspace again deletes a character of what was typed",
        shorter === prefix.slice(0, -1),
        `"${taken}" -> Backspace -> "${shorter}"`
      );
      // The field is a word in a balanced heading. A field sized to its content
      // changes that word's width on every keystroke, and the heading
      // rebalances around it: measured at 1280px, 220px tall when empty and
      // 196px from the first keystroke on.
      await page.fill("#originSearch", "");
      await page.focus("#originSearch");
      for (const value of ["", "N", "No", "Not", prefix, completable]) {
        await page.fill("#originSearch", value);
        heights.push(await headingHeight());
      }
      check(
        "the heading does not change height as the field is typed into",
        heights.every((height) => height === heights[0]) && heights[0] > 0,
        heights.join("px, ") + "px"
      );
      // Accepting a completion is choosing a place, so it goes there.
      await page.fill("#originSearch", "");
      await page.focus("#originSearch");
      await page.type("#originSearch", prefix, { delay: 10 });
      const wanted = await page.evaluate(() => {
        const list = (typeof STATIONS !== "undefined" ? STATIONS : DATA.stations) || [];
        const typed = document.getElementById("originSearch").value.trim().toLowerCase();
        const station = list.find((s) => s.name.toLowerCase() === typed);
        return station ? station.href : null;
      });
      const before = page.url();
      const beforePath = new URL(before).pathname;
      const probe = await page.context().newPage();
      let landed = "";
      try {
        await probe.goto(before);
        if (await probe.locator("#changeOrigin").count()) await probe.click("#changeOrigin");
        await probe.waitForSelector("#originSearch");
        await probe.focus("#originSearch");
        await probe.type("#originSearch", prefix, { delay: 10 });
        const moved = probe
          .waitForURL((url) => new URL(url).pathname !== beforePath, { timeout: 5000 })
          .catch(() => null);
        await probe.keyboard.press("Tab");
        await moved;
        landed = probe.url();
      } finally {
        await probe.close();
      }
      check(
        "Tab on a completion goes to that station's page",
        wanted !== null && landed && new URL(landed, before).pathname === new URL(wanted, before).pathname,
        `${completable} -> ${landed || "(no navigation)"} (wanted ${wanted})`
      );
      // An arrow key walks the caret over the suggested tail and changes no
      // character, and it used to take the station away with it: the Tab and
      // Enter branch asked only whether anything was selected, and a caret at
      // the end of the name selects nothing, so the two keys that accept a
      // completion silently stopped accepting it. Reported on a station page
      // that lists another station long enough to complete: type "Not", press
      // the right arrow, press Enter, and nothing happens where Enter alone
      // goes to that station's page.
      await page.fill("#originSearch", "");
      await page.focus("#originSearch");
      await page.type("#originSearch", prefix, { delay: 10 });
      await page.keyboard.press("ArrowRight");
      const afterArrow = await page.inputValue("#originSearch");
      const walked = await page.evaluate(() => {
        const field = document.getElementById("originSearch");
        return field.selectionStart === field.selectionEnd;
      });
      const arrowProbe = await page.context().newPage();
      let arrowLanded = "";
      try {
        await arrowProbe.goto(before);
        if (await arrowProbe.locator("#changeOrigin").count()) await arrowProbe.click("#changeOrigin");
        await arrowProbe.waitForSelector("#originSearch");
        await arrowProbe.focus("#originSearch");
        await arrowProbe.type("#originSearch", prefix, { delay: 10 });
        const arrowMoved = arrowProbe
          .waitForURL((url) => new URL(url).pathname !== beforePath, { timeout: 5000 })
          .catch(() => null);
        await arrowProbe.keyboard.press("ArrowRight");
        await arrowProbe.keyboard.press("Tab");
        await arrowMoved;
        arrowLanded = arrowProbe.url();
      } finally {
        await arrowProbe.close();
      }
      check(
        "an arrow key over the completion leaves Tab able to go to it",
        wanted !== null && walked && afterArrow.toLowerCase().startsWith(prefix.toLowerCase()) &&
          arrowLanded && new URL(arrowLanded, before).pathname === new URL(wanted, before).pathname,
        `${prefix} -> "${afterArrow}" -> ArrowRight -> Tab -> ${arrowLanded || "(no navigation)"} (wanted ${wanted})`
      );
      await page.fill("#originSearch", "");
    } else {
      for (const name of [
        "Backspace takes the completion back",
        "and Backspace again deletes a character of what was typed",
        "the heading does not change height as the field is typed into",
        "Tab on a completion goes to that station's page",
        "an arrow key over the completion leaves Tab able to go to it",
      ]) {
        check(name, notExercised("no station on this page has a name long enough to complete"));
      }
    }
      await page.fill("#originSearch", "");
      // The field replaces the station's own name in the heading, and it was a
      // fixed eighteen characters wide: clicking the name put a field most of
      // the line wide where the name had been, and pushed the sentence under
      // it down a line to make room. It is now as wide as the word inside it,
      // which for an empty field is the placeholder.
      const shrinkToFit = await page.evaluate(() => {
        const field = document.getElementById("originSearch");
        const heading = document.getElementById("pageHeading");
        return {
          field: Math.round(field.getBoundingClientRect().width),
          line: Math.round(heading.getBoundingClientRect().width),
        };
      });
      check(
        "the empty station field is as wide as the word in it rather than the line",
        shrinkToFit.field > 0 && shrinkToFit.field < shrinkToFit.line * 0.6,
        `${shrinkToFit.field}px field in a ${shrinkToFit.line}px line`
      );
      // The budget slot beside it is a real field, so a keyboard reader tabs to
      // it and types. The station's name is a button, and a button takes no
      // keystroke: a keyboard reader tabbed to the name and stopped, and the
      // field was only reachable by pressing Enter or Space on it first, which
      // is two gestures for one edit.
      if (await page.locator("#changeOrigin").count()) {
        // From a fresh page, because the picker is open by now and a button the
        // picker has hidden cannot be focused, which would make the check pass
        // or fail on the state rather than on the key.
        const typeProbe = await page.context().newPage();
        let hadFocus = false;
        let typedAtName = null;
        try {
          await typeProbe.goto(page.url());
          hadFocus = await typeProbe.evaluate(() => {
            const control = document.getElementById("changeOrigin");
            control.focus();
            return document.activeElement === control;
          });
          await typeProbe.keyboard.type("N");
          await typeProbe.waitForTimeout(150);
          typedAtName = await typeProbe.evaluate(() => {
            const field = document.getElementById("originSearch");
            return field && document.activeElement === field ? field.value : null;
          });
        } finally {
          await typeProbe.close();
        }
        check(
          "typing at the station name starts the edit, as it does at the budget",
          hadFocus && typedAtName !== null && typedAtName.length > 0,
          `focus #changeOrigin, typed N -> ${JSON.stringify(typedAtName)}`
        );
      } else {
        check(
          "typing at the station name starts the edit, as it does at the budget",
          notExercised("this page has no other station to change to")
        );
      }
      // S12: the one distinction a first-time reader cannot guess, said once,
      // in the page's own terms, and only on the page where it is true.
      const firstUse = (await page.textContent("#firstUse")) || "";
      check(
        "the page says the station name in the heading moves station",
        // The control is the station's own name with a field beside it, so the
        // sentence has to name the name rather than a button that is no longer
        // there: it said "Change" for exactly as long as that word was on the
        // page, which is the whole point of the check. Nothing about narrowing
        // is claimed now: the field filters the list as it is typed into.
        /station name/i.test(firstUse) && /start from somewhere else/i.test(firstUse),
        JSON.stringify(firstUse)
      );
      // A list of one cannot be narrowed. That is a fact about the page's own
      // station list rather than about the filter, so it is reported as the
      // check this page cannot exercise.
      check(
        "typing narrows the picker",
        pickCount > 1
          ? narrowed > 0 && narrowed < pickCount && narrowedText.includes(firstWord)
          : notExercised(`this page lists ${pickCount} station, so there is nothing to narrow`),
        `${query || "(no options)"} -> ${narrowed} of ${pickCount} options`
      );
      await page.fill("#originSearch", "zzzz");
      check(
        "a no-match says so and names the code route",
        pickCount
          ? (await page.locator("#originNomatch").isVisible()) && /three-letter code/.test(await page.textContent("#originNomatch"))
          : notExercised("this page lists no other station, so a query has nothing to narrow")
      );
      const emptyOptions = await page.locator("#originPicks a").count();
      check("and the list itself is empty rather than stale", emptyOptions === 0, `${emptyOptions} left`);
      // Keyboard exit: Escape closes and focus returns to the control that opened it.
      await page.fill("#originSearch", query);
      await page.keyboard.press("Escape");
      check("Escape closes the picker", !(await page.locator("#originPicker").isVisible()));
      // The completion, driven from a station this page actually lists rather
      // than from a name a fixture happens to carry, so the check is a test of
      // the field and not of the feed.
      const pickerStations = await page.evaluate(() =>
        (DATA.stations || []).map((station) => ({
          name: station.name,
          destinations: station.destinations || 0,
        }))
      );
      const pickerProbe = completionProbe(pickerStations);
      if (pickerProbe && pickerProbe.matches.length) {
        const letters = pickerProbe.letters;
        const expected = expectedCompletion(pickerProbe);
        await page.click("#changeOrigin");
        await page.fill("#originSearch", "");
        await page.type("#originSearch", letters, { delay: 10 });
        await page.waitForTimeout(80);
        const typed = await page.evaluate(() => {
          const field = document.getElementById("originSearch");
          return {
            value: field.value,
            start: field.selectionStart,
            end: field.selectionEnd,
          };
        });
        check(
          `typing ${letters} completes ${expected} in the field, with the rest of it selected`,
          typed.value === expected &&
            typed.start === letters.length &&
            typed.end === expected.length,
          JSON.stringify({ letters, expected, typed })
        );
        // Where the list is drawn, measured against the field it belongs to.
        const placed = await page.evaluate(() => {
          const field = document.getElementById("originSearch").getBoundingClientRect();
          const list = document.getElementById("originPicker");
          const box = list.getBoundingClientRect();
          return {
            gap: Math.round(box.top - field.bottom),
            position: getComputedStyle(list).position,
            aligned: Math.abs(box.left - field.left) < 200,
            options: list.querySelectorAll("a").length,
          };
        });
        check(
          "the list of stations is drawn under the field, not two paragraphs further down",
          placed.position === "fixed" && placed.gap >= 0 && placed.gap < 40 && placed.aligned && placed.options > 0,
          JSON.stringify(placed)
        );
        // Walking away: a click on the page, not in the field and not in the list.
        await page.mouse.click(24, 520);
        await page.waitForTimeout(120);
        const walked = await page.evaluate(() => ({
          field: Boolean(document.getElementById("originSearch")),
          picker: Boolean(document.getElementById("originPicker")),
          name: (document.getElementById("changeOrigin") || { textContent: "" }).textContent.replace(/\s+/g, " ").trim(),
          expanded: (document.getElementById("changeOrigin") || {}).getAttribute
            ? document.getElementById("changeOrigin").getAttribute("aria-expanded")
            : null,
        }));
        // Walking away is the gesture that does not commit anything. It puts
        // the page's own station name back, closes the picker and leaves the
        // reader where they were, which is what the check below says; with Tab
        // and Enter now going to the station a completion names, this is the
        // only way out of a half-typed name that keeps the page.
        check(
          "a click on the page puts the station's name back where the field was",
          walked.field === false && walked.name.length > 0 && walked.expanded === "false",
          JSON.stringify(walked)
        );
        await page.evaluate(() => { document.getElementById("changeOrigin").focus(); });
      } else {
        for (const name of [
          "typing a station's first letters completes the name in the field",
          "the list of stations is drawn under the field",
          "a click on the page puts the station's name back where the field was",
        ]) {
          check(name, notExercised("this page lists no station a reader could type"));
        }
      }
      check("and focus returns to the heading station control", await page.evaluate(() => document.activeElement && document.activeElement.id === "changeOrigin"));
      // The field the reader types in lives in the heading while the picker is
      // open, so Escape has to be caught where the key is actually pressed.
      check(
        "and Escape in the field closes it too",
        await page.evaluate(() => {
          // The field is detached while the picker is closed, so it is read
          // after the picker is opened, not before.
          document.getElementById("changeOrigin").click();
          const field = document.getElementById("originSearch");
          if (!field) return false;
          field.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
          return document.getElementById("originPicker").hidden;
        })
      );
      // The station name is the control while the picker is closed, and it is
      // the field while the picker is open: pressing it a second time is not
      // something a reader can do, because the name is not on the page any
      // more. What has to be true instead is that closing it puts the name
      // back, and that the field sits in the heading while it is open.
      check(
        "closing the picker puts the station name back",
        await page.evaluate(() => {
          const button = document.getElementById("changeOrigin");
          return Boolean(button) && !button.hidden && button.textContent.trim().length > 0;
        })
      );
      await pickerButton.click();
      check(
        "and opening it puts the field where the name was",
        await page.evaluate(() => {
          const field = document.getElementById("originSearch");
          const button = document.getElementById("changeOrigin");
          return Boolean(field) && Boolean(button) && button.hidden && field.closest("h1") !== null;
        })
      );
      // Keyboard-only reachability of the picker's first option.
      const firstOption = page.locator("#originPicks a").first();
      check(
        "picker options are keyboard-focusable links",
        pickCount
          ? await firstOption.evaluate((el) => el.tagName === "A" && new URL(el.href).pathname.endsWith("/"))
          : notExercised("this page lists no option to focus")
      );
      // The same key that enters the chooser's list enters this one: the picker
      // is that selector reached from the heading, so a reader who has met one
      // has met the other.
      await page.fill("#originSearch", "");
      await page.focus("#originSearch");
      await page.keyboard.press("ArrowDown");
      check(
        "ArrowDown from the picker field enters its list",
        pickCount
          ? await page.evaluate(() => document.activeElement === document.querySelector("#originPicks a"))
          : notExercised("this page lists no option to enter")
      );
      await page.keyboard.press("ArrowUp");
      check(
        "and ArrowUp comes back to the picker field",
        pickCount
          ? await page.evaluate(() => document.activeElement && document.activeElement.id === "originSearch")
          : notExercised("see above")
      );
      await page.keyboard.press("Escape");
    } else {
      // A build with one origin has nowhere to change to, so the heading
      // states the station as text and carries no control -- the inert button
      // this replaced was rendered, focusable, announced and did nothing. So
      // the absence is not the whole check: the origin still has to be named
      // in the heading, or a page could pass by dropping it altogether.
      const named = await page.evaluate(() => {
        const el = document.querySelector("#pageHeading .origin-name");
        return el ? el.textContent.trim() : "";
      });
      const heading = await page.textContent("#pageHeading");
      check(
        "the heading names the station as text when there is no Change control",
        Boolean(named) && (heading || "").includes(named),
        named ? `no control, heading says ${named}` : "no .origin-name in the heading"
      );
      // And the page does not spend its first-use note telling the reader what
      // a Change control does when there is no Change control. The note was
      // static text written for a page that has one, so a one-station build
      // pointed a reader at a button that was not there.
      const firstUse = (await page.textContent("#firstUse")) || "";
      check(
        "and the page does not tell the reader about a Change control it does not have",
        !/change/i.test(firstUse),
        JSON.stringify(firstUse)
      );
    }
}
module.exports = { checkTheOriginPicker };
