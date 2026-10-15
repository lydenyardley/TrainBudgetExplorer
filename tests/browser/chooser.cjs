const { notExercised, completionProbe, expectedCompletion } = require("./harness.cjs");
/**
 * The chooser at the site root, which S01 made the departure picker: the page
 * a reader lands on, and the only page whose whole job is choosing where to
 * depart from. It carries no fares, so every fact is read out of its own
 * STATIONS array and the list it builds from that array -- the suite never
 * names a station here either.
 */
async function checkChooser(page, url, check) {
  const listed = await page.evaluate(() => STATIONS.map((s) => ({ name: s.name, crs: s.crs, href: s.href })));
  const budget = await page.inputValue("#budgetNumber");
  check("the chooser has stations to choose from", listed.length > 0, `${listed.length} stations`);
  // The heading is a station page's heading with a field where the station's
  // name goes: the same question, the same two slots, and the slot this route
  // has no answer for is a text field rather than a name to click. Read out of
  // the page rather than matched against a sentence written here, because the
  // point is that the two routes have not drifted apart. C15 and C21: the
  // figure in the heading is written from the same resolved budget as the
  // field, the tab title and every outgoing link, and the wording is the
  // inclusive one.
  const heading = await page.evaluate(() => {
    const el = document.getElementById("pageHeading");
    // The sentence a reader sees, which is not the heading's textContent: an
    // input carries no text, so reading textContent alone compares against a
    // sentence with both the budget and the station missing from it. Each
    // field's value is written where the field sits, and the hidden text that
    // exists only for a screen reader's name is left out.
    const seen = (node) => {
      let out = "";
      for (const child of node.childNodes) {
        if (child.nodeType === Node.TEXT_NODE) out += child.textContent;
        else if (child.nodeType === Node.ELEMENT_NODE && !child.classList.contains("sr-only")) {
          out += child.tagName === "INPUT" ? child.value : seen(child);
        }
      }
      return out;
    };
    return {
      text: seen(el).replace(/\u2060/g, "").replace(/\s+/g, " ").trim(),
      // The heading's own name, which is what a screen reader announces for it
      // (audit items 9 and 13).
      name: el.getAttribute("aria-label") || "",
      field: (document.getElementById("budgetNumber") || {}).value || "",
      // The shared slot class, which is what a station page's slot wears too: the
      // chooser's field is that slot with nothing in it yet.
      slot: Boolean(el.querySelector(".origin-slot-wrap")),
      placeholder: (document.getElementById("originSearch") || {}).placeholder || "",
    };
  });
  check(
    "the heading is the sentence a station page carries, with a field where its name goes",
    // Audit item 7, 9 October 2026: the chooser kept two middot separators the
    // station page had already retired, so the sentence is now the station
    // page's own -- "Train fares up to £X" then "from", with the field at the
    // end of the second line holding the station the reader has not typed yet.
    new RegExp("^Train fares\\s+up to £" + heading.field + "\\s*from$").test(heading.text),
    JSON.stringify(heading)
  );
  check(
    "and the station it has no answer for is a field holding the word station",
    heading.slot && heading.placeholder === "station",
    JSON.stringify(heading)
  );
  check(
    "and the heading carries that sentence as its own name",
    // Items 9 and 13, 14 October 2026: the heading holds the budget field and
    // the station field, so a name computed from its contents was the two
    // controls run together. It is written as the whole sentence, with the
    // station clause in the reader's words where there is a station to pick and
    // the name the title already carries where there is one station.
    new RegExp("^Train fares up to £" + heading.field + " from ").test(heading.name) &&
      (!heading.slot ||
        heading.name === "Train fares up to £" + heading.field + " from your starting station"),
    JSON.stringify(heading)
  );
  // The chooser's field is the same control as a station page's, so the three
  // behaviours are checked here as well and against this page's own list.
  const wholeList = await page.evaluate(() => ({
    shown: document.querySelectorAll("#picks a").length,
    total: typeof STATIONS === "undefined" ? 0 : STATIONS.length,
    cap: STATION_LIST_CAP,
    first: typeof STATIONS === "undefined" || !STATIONS.length ? null : STATIONS[0],
    // The panel waits for the first keystroke, and it is drawn over the list's
    // own place rather than over the field's: a page nobody has touched shows
    // its own explanation (four-dimension audit R1, route audit item 3).
    fixed: document.getElementById("picks").classList.contains("under-field"),
    introVisible: (() => {
      const box = document.getElementById("picks").getBoundingClientRect();
      const intro = document.querySelector("#pageHeading + p.sub");
      const top = intro ? intro.getBoundingClientRect().bottom : 0;
      return box.top >= top - 1;
    })(),
    capText: (document.getElementById("capMessage") || {}).textContent || "",
    capHidden: (document.getElementById("capMessage") || {}).hidden,
  }));
  check(
    "the field opens on a stated top-N of stations rather than the whole directory",
    wholeList.total > 0 &&
      wholeList.shown === Math.min(wholeList.total, wholeList.cap) &&
      !wholeList.fixed &&
      wholeList.introVisible &&
      (wholeList.total <= wholeList.cap ||
        (wholeList.capHidden === false && new RegExp("Showing " + wholeList.cap + " of " + wholeList.total).test(wholeList.capText))),
    JSON.stringify(wholeList)
  );
  const probeData = await page.evaluate(() =>
    STATIONS.map((station) => ({ name: station.name, destinations: station.destinations || 0 }))
  );
  const probe = completionProbe(probeData);
  if (probe && probe.matches.length) {
    const letters = probe.letters;
    const expected = expectedCompletion(probe);
    await page.fill("#originSearch", "");
    await page.type("#originSearch", letters, { delay: 10 });
    await page.waitForTimeout(80);
    const completed = await page.evaluate(() => {
      const field = document.getElementById("originSearch");
      const list = document.getElementById("picks");
      const f = field.getBoundingClientRect();
      const l = list.getBoundingClientRect();
      // The panel is drawn over the list's own place in the document, so the
      // intro and the ordering note between the field and it stay above the
      // panel: a click aimed at them is a click on prose (four-dimension R1).
      const intro = document.querySelector("#pageHeading + p.sub");
      return {
        value: field.value,
        start: field.selectionStart,
        end: field.selectionEnd,
        position: getComputedStyle(list).position,
        introBottom: intro ? Math.round(intro.getBoundingClientRect().bottom) : 0,
        panelTop: Math.round(l.top),
        options: list.querySelectorAll("a").length,
        sideScroll:
          Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth,
      };
    });
    check(
      `typing ${letters} in the chooser's field completes ${expected}, with the alternatives still listed`,
      completed.value === expected &&
        completed.start === letters.length &&
        completed.end === expected.length &&
        completed.position === "fixed" &&
        completed.panelTop >= completed.introBottom &&
        completed.options >= Math.min(probe.matches.length, 40) &&
        completed.sideScroll <= 0,
      JSON.stringify({ letters, expected, matches: probe.matches.map((station) => station.name), completed })
    );
    // The defect this anchor answers: with the field focused and a completion
    // in it, a click aimed at the page's own explanation must be a click on
    // prose. It used to land on the completion drawn over the intro, and the
    // reader left for a station they had not chosen (four-dimension audit R1).
    const introClick = await page.evaluate(() => {
      const intro = document.querySelector("#pageHeading + p.sub");
      const before = window.location.href;
      intro.click();
      return { before, after: window.location.href };
    });
    check(
      "a click on the prose leaves the page alone while a completion is in the field",
      introClick.before === introClick.after,
      JSON.stringify(introClick)
    );
    await page.fill("#originSearch", "");
  } else {
    check(
      "typing in the chooser's field completes the shortest matching station, with the alternatives still listed",
      notExercised("this release lists no station a reader could type")
    );
  }
  // A placeholder is text a reader has to read, so it is measured like text:
  // muted is the design call, and still meeting AA is the floor under it. The
  // colour is painted onto a canvas over the page rather than parsed out of
  // the computed string, so whatever notation the browser reports it in, this
  // measures the pixels a reader sees.
  const placeholderInk = await page.evaluate(() => {
    const input = document.getElementById("originSearch");
    const probe = document.createElement("canvas");
    probe.width = probe.height = 1;
    const painter = probe.getContext("2d");
    const paint = (value, backdrop) => {
      painter.clearRect(0, 0, 1, 1);
      painter.fillStyle = "rgb(" + backdrop.join(", ") + ")";
      painter.fillRect(0, 0, 1, 1);
      painter.fillStyle = value;
      painter.fillRect(0, 0, 1, 1);
      const pixel = painter.getImageData(0, 0, 1, 1).data;
      return [pixel[0], pixel[1], pixel[2]];
    };
    const luminance = (rgb) =>
      rgb
        .map((channel) => {
          const c = channel / 255;
          return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
        })
        .reduce((sum, c, i) => sum + c * [0.2126, 0.7152, 0.0722][i], 0);
    const ratio = (a, b) => {
      const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
      return (hi + 0.05) / (lo + 0.05);
    };
    const behind = paint(getComputedStyle(document.body).backgroundColor, [255, 255, 255]);
    const placeholder = paint(getComputedStyle(input, "::placeholder").color, behind);
    return {
      ratio: ratio(placeholder, behind),
      ink: placeholder.join(","),
      behind: behind.join(","),
    };
  });
  check(
    "the placeholder is muted and still meets AA",
    placeholderInk.ratio >= 4.5,
    `${placeholderInk.ratio.toFixed(1)}:1, ${placeholderInk.ink} on ${placeholderInk.behind}`
  );
  // The reader's own answer belongs in the accent colour, and the caret in the
  // slot is what says the page is waiting for one.
  const slotState = await page.evaluate(() => ({
    focused: document.activeElement === document.getElementById("originSearch"),
    caret: getComputedStyle(document.getElementById("originSearch")).caretColor,
    empty: document.getElementById("originSearch").value === "",
  }));
  check(
    "the empty station slot holds the caret on arrival",
    slotState.focused && slotState.empty,
    JSON.stringify(slotState)
  );
  const capped = await page.evaluate(() => STATION_LIST_CAP);
  if (listed.length > capped) {
    // The state the cap exists for: a typed search matching more than it. The
    // letter is read from this release's own list (the one most of its names
    // share) and only the route's typed query is set, so this is about the
    // list the page draws rather than about the completion.
    const busiest = await page.evaluate(() => {
      const counts = new Map();
      for (const station of STATIONS) {
        for (const letter of new Set(station.name.toLowerCase())) {
          counts.set(letter, (counts.get(letter) || 0) + 1);
        }
      }
      let best = null;
      for (const [letter, count] of counts) if (!best || count > best[1]) best = [letter, count];
      return best ? best[0] : "";
    });
    const cappedState = await page.evaluate((letter) => {
      typedQuery = letter;
      render();
      const message = document.getElementById("capMessage");
      return {
        letter,
        rows: document.querySelectorAll("#picks a").length,
        hidden: message.hidden,
        text: message.textContent,
        matches: STATIONS.filter((station) => stationMatches(station, letter)).length,
      };
    }, busiest);
    const said = cappedState.matches > capped
      ? cappedState.rows === capped &&
        !cappedState.hidden &&
        /Showing \d+ of \d+/.test(cappedState.text)
      : notExercised(
          `no letter in this release's names matches more than the cap of ${capped} (the best is ${cappedState.matches})`
        );
    check(
      "a search matching more than the cap shows the cap and says how many it is hiding",
      said,
      JSON.stringify(cappedState)
    );
    await page.evaluate(() => {
      typedQuery = "";
      render();
    });
  } else {
    check(
      "a search matching more than the cap shows the cap and says how many it is hiding",
      notExercised(`this release lists ${listed.length} station(s), no more than the cap of ${capped}`)
    );
  }
  const rows = await page.evaluate(() =>
    Array.from(document.querySelectorAll("#picks a")).map((a) => ({
      href: a.getAttribute("href"),
      text: a.textContent,
      tall: a.getBoundingClientRect().height,
    }))
  );
  check(
    "every option is a link to a station page",
    rows.every((row) => /\/from\/[^/]+\/$/.test(new URL(row.href, "http://x").pathname)),
    rows.map((row) => row.href).join(" ")
  );
  check(
    "every option carries its name, its code and a count",
    rows.length > 0 &&
      rows.every((row) =>
        listed.some((station) => row.text.includes(station.name) && row.text.includes(station.crs)) &&
        /\d+ destinations?/.test(row.text)),
    JSON.stringify(rows[0] || null)
  );
  check("every option is a 44px target", rows.every((row) => row.tall >= 44), `${rows[0] ? rows[0].tall : 0}px`);
  check(
    "the budget travels with the station link",
    rows.every((row) => new URL(row.href, "http://x").searchParams.get("budget") === budget),
    rows[0] ? rows[0].href : "no options"
  );
  // The search, judged against the page's own list rather than a fixture name.
  const first = listed[0];
  const query = first.name.split(/[\s(]+/)[0].slice(0, 4);
  await page.fill("#originSearch", query);
  const narrowed = await page.locator("#picks a").count();
  // What the empty field showed before this search, which is the directory's
  // stated top-N rather than every station the release prices.
  const options = Math.min(listed.length, capped);
  check(
    "typing narrows the list",
    // A chooser holding one station cannot be narrowed by typing: the query
    // that would exclude it is the reader's own spelling of it. A published
    // one-origin build is that page, so this is reported as not exercised
    // rather than failed, and the count is on the page's tally.
    options < 2
      ? notExercised(`this chooser lists ${options} station(s), so typing cannot narrow it`)
      : narrowed > 0 && narrowed < options && /Showing|list/i.test(await page.textContent("#pickStatus")),
    `${query} -> ${narrowed} of ${options}`
  );
  const code = listed[1] ? listed[1].crs : first.crs;
  await page.fill("#originSearch", code);
  check(
    "a three-letter code finds its station",
    (await page.locator("#picks a").count()) === 1 && (await page.textContent("#picks")).includes(code),
    code
  );
  await page.fill("#originSearch", "zzzz");
  const noMatch = await page.locator("#nomatch").isVisible();
  check("a query with no answer says so", noMatch && (await page.locator("#picks a").count()) === 0, await page.textContent("#nomatch"));
  check("and it names the code route", /three-letter code/.test(await page.textContent("#nomatch")));
  await page.fill("#originSearch", "");
  // The budget is the reader's, and it is the one thing the root page can carry
  // into the station page it opens (S05).
  const next = Math.min(500, Number(budget) + 7);
  await page.fill("#budgetNumber", String(next));
  check("changing the budget retitles the page", new RegExp("£" + next + "\?").test(await page.title()), await page.title());
  const carried = await page.evaluate(() => new URL(document.querySelector("#picks a").href).searchParams.get("budget"));
  check("and the station links carry it", carried === String(next), String(carried));
  // A shared link: the budget a reader was given is the budget they get back.
  await page.goto(url + "?budget=42");
  check("a budget in the link opens the page at that budget", (await page.inputValue("#budgetNumber")) === "42", await page.inputValue("#budgetNumber"));
  check(
    "and the station links carry it on",
    (await page.evaluate(() => new URL(document.querySelector("#picks a").href).searchParams.get("budget"))) === "42"
  );
  check("the station field takes focus on arrival", (await page.evaluate(() => document.activeElement && document.activeElement.id)) === "originSearch");
  // S10: a cold-start order that does not say what it is looks like a
  // recommendation. The page has to name the measure and deny the two things
  // a reader would otherwise assume it means (audit item 2, 14 October 2026:
  // the measure is "how many journeys this page prices from the station", in
  // the reader's words rather than the build's).
  const ranking = await page.textContent("body");
  check(
    "the chooser says what its order is, and what it is not",
    /most first/i.test(ranking) && /not by how busy/i.test(ranking) && /not by how near/i.test(ranking),
    (await page.textContent("#orderingNote")) || ""
  );
  // The route has no filter bar, and that is a design decision rather than an
  // omission: the only two things a reader can change here are the two slots in
  // the heading, and this is what says so if one is ever added back.
  check(
    "the chooser carries no filter bar",
    (await page.locator(".filter-bar").count()) === 0 && (await page.locator("#moreFilters").count()) === 0
  );
  // S11: a code fragment is what somebody who knows the network types.
  // Lowercased to match the page, which lowercases what the reader typed
  // before comparing: a code in the address bar is upper case.
  const fragment = (listed[1] || first).crs.slice(0, 2).toLowerCase();
  await page.fill("#originSearch", fragment);
  const byFragment = await page.evaluate(() =>
    Array.from(document.querySelectorAll("#picks a")).map((a) => ({
      code: (a.querySelector(".code") || {}).textContent || "",
      name: (a.querySelector("span") || {}).textContent || "",
    }))
  );
  check(
    "a code fragment finds its station",
    byFragment.some((row) => row.code.toLowerCase().startsWith(fragment)) &&
      byFragment.every((row) => row.code.toLowerCase().startsWith(fragment) || row.name.toLowerCase().includes(fragment)),
    `${fragment} -> ${byFragment.map((row) => row.code).join(" ") || "nothing"}`
  );
  await page.fill("#originSearch", "");
  const privacy = await page.evaluate(() => (document.querySelector(".footnav a") || {}).getAttribute
    ? document.querySelector(".footnav a").getAttribute("href")
    : null);
  check("the chooser links to the privacy page", privacy !== null && /\/privacy\/$/.test(new URL(privacy, "http://x").pathname), String(privacy));
  // The list the field filters is what the field is for, so the key that means
  // "down into it" is the way in, and the keys that mean "leave" are the way
  // back. The options stay real anchors, so focus lands on the anchor itself.
  const optionCount = await page.locator("#picks a").count();
  await page.fill("#originSearch", "");
  await page.focus("#originSearch");
  await page.keyboard.press("ArrowDown");
  const entered = await page.evaluate(() => ({
    isFirst: document.activeElement === document.querySelector("#picks a"),
    tag: document.activeElement ? document.activeElement.tagName : "",
  }));
  check(
    "ArrowDown from the station field enters its list",
    optionCount ? entered.isFirst : notExercised("this chooser lists no station to enter"),
    JSON.stringify({ ...entered, options: optionCount })
  );
  await page.keyboard.press("ArrowUp");
  check(
    "ArrowUp from the first option returns to the field",
    optionCount
      ? await page.evaluate(() => document.activeElement && document.activeElement.id === "originSearch")
      : notExercised("see above")
  );
  if (optionCount > 1) {
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("ArrowDown");
    check(
      "and ArrowDown again reaches the second option",
      await page.evaluate(() => document.activeElement === document.querySelectorAll("#picks a")[1]),
      `${optionCount} options`
    );
    await page.keyboard.press("Escape");
    check(
      "Escape in the list returns to the field",
      await page.evaluate(() => document.activeElement && document.activeElement.id === "originSearch")
    );
  } else {
    check("and ArrowDown again reaches the second option", notExercised("this chooser lists one station"));
    check("Escape in the list returns to the field", notExercised("see above"));
  }
  // A station name can be pasted from anywhere, and the field sits inside the
  // heading's own line: an unbounded field takes the page sideways with it.
  // Sixty characters is longer than any station's name in the feed.
  const longQuery = "Z".repeat(60);
  await page.fill("#originSearch", longQuery);
  const wide = await page.evaluate(() => ({
    overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth,
    field: Math.round(document.getElementById("originSearch").getBoundingClientRect().width),
  }));
  check(
    "a sixty-character station name does not push the page sideways",
    wide.overflow <= 0,
    `${wide.field}px field, ${wide.overflow}px of sideways scroll`
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
  // The field replaces a word in the heading, and it was a fixed eighteen
  // characters wide: opening the picker put a field most of the line wide
  // where four letters had been, and the sentence under it moved down a line
  // to make room. It is now as wide as the word inside it, which for an empty
  // field is the placeholder.
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
  // The budget slot beside it is a real field, so a keyboard reader tabs to it
  // and types. Where the station's name is a button instead, a button takes no
  // keystroke: the reader tabbed to the name and stopped, and the field was
  // only reachable by pressing Enter or Space on it first, which is two
  // gestures for one edit.
  const stationControl = (await page.locator("#changeOrigin").count()) ? "#changeOrigin" : "#originSearch";
  const hadFocus = await page.evaluate((selector) => {
    const control = document.querySelector(selector);
    control.focus();
    return document.activeElement === control;
  }, stationControl);
  await page.keyboard.type("N");
  await page.waitForTimeout(120);
  const typedAtName = await page.evaluate(() => {
    const field = document.getElementById("originSearch");
    return field && document.activeElement === field ? field.value : null;
  });
  check(
    "typing at the station name starts the edit, as it does at the budget",
    hadFocus && typedAtName !== null && typedAtName.length > 0,
    `focus ${stationControl}, typed N -> ${JSON.stringify(typedAtName)}`
  );
  await page.fill("#originSearch", "");
  await page.setViewportSize({ width: 390, height: 720 });
  const overflow = await page.evaluate(() => {
    const html = document.documentElement;
    return Math.max(html.scrollWidth, document.body.scrollWidth) - window.innerWidth;
  });
  check("at 390px nothing overflows horizontally", overflow <= 0, `${overflow}px`);
  await page.fill("#originSearch", longQuery);
  const narrowOverflow = await page.evaluate(() => ({
    overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth,
    field: Math.round(document.getElementById("originSearch").getBoundingClientRect().width),
  }));
  check(
    "and not at 390px either",
    narrowOverflow.overflow <= 0,
    `${narrowOverflow.field}px field, ${narrowOverflow.overflow}px of sideways scroll`
  );
}
module.exports = { checkChooser };
