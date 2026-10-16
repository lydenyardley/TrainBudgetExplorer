/**
 * The accessibility matrix (S41).
 *
 * The AA commitment was evidenced from one station-page happy path. This is
 * the other half of it: the same checks, run against every route in the run --
 * the chooser, a station page, the privacy page -- in both colour schemes, at
 * desktop and phone widths, and at the width a 200% zoom leaves behind.
 *
 * What it measures, and why each is a measurement rather than an assertion
 * about the source:
 *
 *   - names: the accessibility tree's own computed names, so a control with no
 *     label is caught even when its visible text comes from a ::before.
 *   - contrast: the rendered colours, composited over whatever is behind them
 *     and resolved through a canvas, so color-mix() and alpha are read as the
 *     reader sees them. The threshold follows the text: 4.5:1 for body copy,
 *     3:1 for large text, which is the AA rule rather than a number chosen here.
 *   - targets: the rendered box, plus a positioned ::after's slop, which is
 *     how the row actions reach 44px while staying small on screen.
 *   - zoom: a 320px viewport, which is what 200% zoom leaves of a 640px screen,
 *     with the two things zoom breaks checked directly -- sideways scrolling and
 *     text that shrinks below the base size.
 *   - keyboard: the focus ring, read off the focused element, and the fact that
 *     Tab reaches a control without a mouse.
 */
async function checkAccessibilityMatrix(page, url, check, routeKind) {
  // ------------------------------------------------------------- the names
  // Read from the browser's own accessibility tree rather than from the
  // markup, so a control whose name comes from a label, an aria-label or text
  // this suite has never heard of is counted, and one with no name at all is
  // caught however it was built.
  await page.goto(url);
  const CONTROL_ROLES = new Set([
    "button", "link", "textbox", "searchbox", "checkbox", "radio", "combobox",
    "slider", "spinbutton", "switch", "heading", "listbox", "option", "img",
  ]);
  const tree = await page.locator("body").ariaSnapshot();
  const unnamed = [];
  let named = 0;
  for (const line of String(tree).split("\n")) {
    // A line reads `- link "Name":`, `- heading "Name" [level=1]` or
    // `- button:` for a control with no name at all. The quoted string between
    // the role and the colon is the accessible name; anything in brackets is
    // state, not a name.
    const found = line.match(/^\s*-\s+([a-z]+)\s*(?:"([^"]*)")?\s*:?/);
    if (!found || !CONTROL_ROLES.has(found[1])) continue;
    if (found[2] && found[2].trim()) named += 1;
    else unnamed.push(found[1]);
  }
  check(
    `every control on the ${routeKind} has a name a screen reader reads`,
    unnamed.length === 0 && named > 0,
    `${named} named, ${unnamed.length} unnamed${unnamed.length ? " (" + unnamed.join(", ") + ")" : ""}`
  );
  // The heading is the one sentence a screen reader announces for the page, so
  // what it says is the page's own claim, not a detail. Its currency sign was
  // aria-hidden, so the name read "for up to 20" while the status line said
  // "£20.00" -- the reader was told a number and no unit. Read from the
  // browser's tree, not from the markup, so hiding the sign again fails here.
  if (routeKind === "station" || routeKind === "chooser" || routeKind === "release") {
    const headingName = (String(await page.locator("h1").ariaSnapshot()).split("\n")[0].match(/"([^"]*)"/) || [])[1] || "";
    // The chooser's page data is STATIONS, not DATA, and its heading asks which
    // station rather than naming one, so the station is only read where it is
    // both in the payload and in the sentence. A one-station release names its
    // station in that heading, so it is read there too.
    const origin =
      routeKind === "station"
        ? await page.evaluate(() => DATA.origin.name)
        : routeKind === "release"
          ? await page.evaluate(() => (STATIONS[0] || {}).name || "")
          : "";
    check(
      `the heading a screen reader reads states the budget in pounds${origin ? " and names the station" : ""}`,
      /up to £\s*\d+/.test(headingName) && (!origin || headingName.includes(origin)),
      headingName || "(no heading name)"
    );
  }
  // A placeholder is an accessible-name fallback, so the check above reports a
  // field that has only a placeholder as named -- and it names it with text the
  // reader cannot see once they start typing, which is the whole reason C12 was
  // a defect while the gate stayed green. A control counted as properly labelled
  // here has a real label element, an aria-label or an aria-labelledby; only a
  // placeholder is a failure.
  const placeholderOnly = await page.evaluate(() => {
    const namedProperly = (el) => {
      if (el.getAttribute("aria-label")?.trim()) return true;
      const by = el.getAttribute("aria-labelledby");
      if (by && by.split(/\s+/).some((id) => document.getElementById(id)?.textContent?.trim())) {
        return true;
      }
      if (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`)?.textContent?.trim()) {
        return true;
      }
      return el.closest("label")?.textContent?.trim() ? true : false;
    };
    const out = [];
    for (const el of document.querySelectorAll("input, select, textarea")) {
      if (el.closest("[hidden]") || el.type === "hidden") continue;
      if (!el.placeholder?.trim()) continue;
      if (!namedProperly(el)) {
        out.push((el.id || el.name || el.type) + ` (placeholder "${el.placeholder.trim().slice(0, 24)}")`);
      }
    }
    return out;
  });
  check(
    `no ${routeKind} field is named only by its placeholder`,
    placeholderOnly.length === 0,
    placeholderOnly.length ? placeholderOnly.join("; ") : "every placeholder field also has a real label"
  );
  // C29: one main landmark, and the back link and footer stay outside it as
  // the navigation landmarks they are. A route that omitted it made landmark
  // navigation the only way through a long page, and nothing above caught it.
  const landmarks = await page.evaluate(() => ({
    main: document.querySelectorAll("main").length,
    nav: document.querySelectorAll("nav").length,
    navsInMain: document.querySelectorAll("main nav").length,
    headingsInMain: document.querySelectorAll("main h1").length,
  }));
  check(
    `the ${routeKind} has exactly one main landmark around its own content`,
    landmarks.main === 1 && landmarks.headingsInMain === 1,
    JSON.stringify(landmarks)
  );
  // C13: a links list of identical "Tickets" entries cannot be scanned. Every
  // ticket link is named for its destination, and no two names collide, so a
  // reader choosing one from a list can tell them apart.
  const isStation = routeKind === "station";
  const ticketNames = await page.evaluate(() => {
    const names = Array.from(document.querySelectorAll("a.buy")).map(
      (a) => a.getAttribute("aria-label") || a.textContent.trim());
    return { total: names.length, distinct: new Set(names).size, sample: names.slice(0, 3) };
  });
  check(
    `the ${routeKind} names each ticket link for its destination`,
    !isStation || (ticketNames.total > 0 && ticketNames.distinct === ticketNames.total),
    `${ticketNames.distinct} distinct of ${ticketNames.total}` +
      (ticketNames.sample.length ? " -- " + JSON.stringify(ticketNames.sample) : "")
  );
  // One heading, and it is the page's own subject rather than a brand line.
  const headings = await page.evaluate(() =>
    Array.from(document.querySelectorAll("h1, h2")).map((el) => ({
      level: el.tagName,
      text: (el.textContent || "").trim(),
    }))
  );
  check(
    "the route has one first-level heading and it is not the brand",
    headings.filter((h) => h.level === "H1").length === 1 &&
      !/rail budget/i.test(headings[0].text),
    JSON.stringify(headings.slice(0, 3))
  );
  // ------------------------------------------------------------ the keyboard
  const focusStyle = () =>
    page.evaluate(() => {
      const el = document.activeElement;
      const described = (node) => {
        if (!node) return "";
        const style = getComputedStyle(node);
        // Everything a focus style is allowed to change. An indicator is a
        // visible difference, and WCAG does not require it to be an outline --
        // but it does require there to be one.
        return [
          style.outlineStyle, style.outlineWidth, style.outlineColor,
          style.backgroundColor, style.borderBottomStyle, style.borderBottomColor,
          style.borderBottomWidth, style.boxShadow, style.textDecorationLine,
        ].join("|");
      };
      return {
        reached: !!el && el !== document.body,
        tag: el ? el.tagName : null,
        self: described(el),
        parent: el ? described(el.parentElement) : "",
        name: el ? (el.getAttribute("aria-label") || el.textContent || el.value || "").trim().slice(0, 40) : "",
      };
    });
  const beforeFocus = await focusStyle();
  await page.keyboard.press("Tab");
  const focus = await focusStyle();
  const outlined = await page.evaluate(() => {
    const style = getComputedStyle(document.activeElement);
    return style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0;
  });
  check(
    "one Tab reaches a control",
    focus.reached && focus.tag !== "BODY",
    JSON.stringify(focus)
  );
  check(
    "the focused control shows where it is",
    focus.reached && (outlined || focus.self !== beforeFocus.self || focus.parent !== beforeFocus.parent),
    JSON.stringify({ outlined, before: beforeFocus.self.slice(0, 40), after: focus.self.slice(0, 40), parent: focus.parent.slice(0, 40) })
  );
  // The refinements fold away on every route and at every width, so they are
  // opened here, once, before anything is measured. A control inside a closed
  // panel has no box, and both readers below skip an element with no box: the
  // contrast reader and the target reader would each quietly stop covering the
  // filter families they exist to hold to AA and to 44px. Opening it is also a
  // state a reader reaches by pressing the control, so what is measured is a
  // state the page can really be in.
  if (await page.locator("#moreFiltersToggle").count()) {
    await page.evaluate(() => {
      const details = document.getElementById("moreFilters");
      const toggle = document.getElementById("moreFiltersToggle");
      if (details && toggle && details.dataset.open !== "true") toggle.click();
    });
  }
  // ------------------------------------------- contrast, targets, reflow, per scheme
  for (const scheme of ["light", "dark"]) {
    // The page's own control decides the palette now, not the OS preference, so
    // the scheme is set the way a reader sets it: by pressing the switch. The
    // media query is still emulated, because a reader whose system says light
    // and who has chosen dark must get dark, and the system default is only
    // the default.
    await page.emulateMedia({ colorScheme: scheme });
    const theme = await setTheme(page, scheme);
    check(
      `the switch takes the page to the ${scheme} palette`,
      theme === scheme,
      `switch says ${theme}, asked for ${scheme}`
    );
    // The scheme has to change the page, or the dark pass is the light pass
    // wearing a different name and every check below it proves nothing.
    const painted = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    check(
      `the ${scheme} palette is the one the page paints`,
      scheme === "light" ? isLight(painted) : !isLight(painted),
      painted
    );
    // The credit is NRE's mark painted white onto a dark plate, painted by the
    // page's own stylesheet rather than by editing the artwork, and the plate is
    // the same in both palettes. Legibility is therefore not a thing to argue
    // from the CSS: the guidelines require the logo to be legible, so the
    // painted ink is measured against the plate it is painted on, in each
    // scheme, and the plate is measured against the page it sits on. Reading it
    // off the computed style is what makes this a check of the page: drop the
    // rule that sets the ink and it falls back to the file's own #2E2D7F, which
    // on a dark plate is 1.4:1 and fails here.
    // Read from the page rather than from the credit read further down, so
    // this does not depend on which half of the matrix runs first.
    if (await page.locator(".nre-credit").count()) {
      const legibility = await page.evaluate(() => {
        const plate = document.querySelector(".nre-logo");
        // A colour, as the pixels a reader would see: painted onto a canvas over
        // whatever is behind it. Not a regex over the computed string, because
        // the border here is a color-mix() with an alpha in it, and the browser
        // reports such a colour in a notation whose numbers are not channels --
        // color(srgb 1 1 1 / .22) rather than rgba(255, 255, 255, .22). A
        // checker that reads the numbers out of that string reads 0.8 as a
        // channel and measures a colour nobody is looking at.
        const probe = document.createElement("canvas");
        probe.width = probe.height = 1;
        const painter = probe.getContext("2d");
        const asColour = (rgb) => "rgb(" + rgb.join(", ") + ")";
        const paint = (value, backdrop) => {
          // Both arguments have to be colours the canvas understands. A
          // [r, g, b] array assigned to fillStyle is not one: the assignment is
          // ignored and the previous fillStyle survives, so an earlier call in
          // this same function left the backdrop as whatever it last painted.
          // That is not a hypothetical -- it is what made this check pass a
          // plate whose border was transparent, because the "edge" it measured
          // was the ink from the shape before it.
          painter.clearRect(0, 0, 1, 1);
          painter.fillStyle = typeof backdrop === "string" ? backdrop : asColour(backdrop);
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
        const painted = plate ? getComputedStyle(plate) : null;
        const bodyColour = paint(getComputedStyle(document.body).backgroundColor, "#fff");
        const plateColour = painted ? paint(painted.backgroundColor, bodyColour) : bodyColour;
        // Every shape the mark is drawn from, and the worst of them rather than
        // the first: 20 of the mark's 22 shapes are paths and two are rects, so
        // a rule that caught the paths alone would leave two rectangles in
        // NRE's blue, and a checker that read one path would not notice. The
        // clip-path rect in <defs> is filtered out because it is never painted,
        // and it is black by default, so counting it would fail every page.
        const shapes = plate
          ? Array.from(plate.querySelectorAll("svg path, svg rect, svg polygon, svg circle, svg ellipse"))
              .filter((shape) => {
                const box = shape.getBoundingClientRect();
                return box.width > 0 && box.height > 0;
              })
          : [];
        const inks = shapes.map((shape) => paint(getComputedStyle(shape).fill, plateColour));
        // The plate has to be findable: a dark chip on a dark page is a plate
        // only because of the line round it. An earlier version compared the
        // border's colour string to the plate's, which every border passed,
        // visible or not -- "rgba(0, 0, 0, 0)" differs from everything by
        // string alone. This composites the border over the plate it is drawn
        // on and measures what is left, so 1.5:1 is the line.
        const edgeInk = painted ? paint(painted.borderTopColor, plateColour) : plateColour;
        const borderWide = painted ? parseFloat(painted.borderTopWidth) >= 1 : false;
        return {
          plate: plateColour.join(","),
          shapes: inks.length,
          markOnPlate: inks.length ? Math.min(...inks.map((ink) => ratio(ink, plateColour))) : 0,
          plateOnPage: ratio(plateColour, bodyColour),
          edge: borderWide ? ratio(edgeInk, plateColour) : 0,
        };
      });
      // 3:1 is the non-text contrast floor for the mark itself. The plate has
      // to be findable, which in the dark palette means the edge rather than a
      // fill that differs from the page: #141b3d on #14181d is 1.06:1.
      check(
        `the NRE mark stays legible in ${scheme}`,
        legibility.markOnPlate >= 3 && (legibility.plateOnPage >= 1.05 || legibility.edge >= 1.5),
        `${legibility.shapes} shapes, ink on plate ${legibility.plate}: ${legibility.markOnPlate.toFixed(1)}:1, plate on page ${legibility.plateOnPage.toFixed(2)}:1, edge ${legibility.edge.toFixed(2)}:1`
      );
    }
    const contrast = await page.evaluate(() => {
      // Any CSS colour the browser understands, read as pixels: color-mix(),
      // oklab, currentColor and alpha all resolve, and a contrast ratio
      // computed from a string would be a guess about the string.
      const probe = document.createElement("canvas");
      probe.width = probe.height = 1;
      const ctx = probe.getContext("2d", { willReadFrequently: true });
      const toRgba = (value) => {
        ctx.clearRect(0, 0, 1, 1);
        ctx.fillStyle = "#000";
        ctx.fillStyle = value;
        ctx.fillRect(0, 0, 1, 1);
        const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data;
        return [r, g, b, a / 255];
      };
      // What is behind the text, composited: a transparent background is not a
      // background, it is whatever is behind it.
      const behind = (el) => {
        const layers = [];
        for (let node = el; node; node = node.parentElement) {
          const [r, g, b, a] = toRgba(getComputedStyle(node).backgroundColor);
          if (a > 0) {
            layers.push([r, g, b, a]);
            if (a === 1) break;
          }
        }
        let out = [255, 255, 255, 1];
        for (const [r, g, b, a] of layers.reverse()) {
          out = [r * a + out[0] * (1 - a), g * a + out[1] * (1 - a), b * a + out[2] * (1 - a), 1];
        }
        return out;
      };
      const channel = (value) => {
        const c = value / 255;
        return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
      };
      const luminance = ([r, g, b]) =>
        0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
      const ratio = (a, b) => {
        const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
        return (light + 0.05) / (dark + 0.05);
      };
      const SELECTORS = [
        ["body", "the page's own text"],
        [".sub", "the intro"],
        [".tag", "a hint under a control"],
        ["a", "a link"],
        [".footnav a", "a footer link"],
        ["th", "a column heading"],
        ["#summary", "the result count"],
        ["td", "a cell"],
        [".restriction", "a travel condition"],
        [".restriction[data-status=restricted]", "a restricted-fare condition"],
        ["h1", "the page heading"],
        ["h2", "a section heading"],
        [".condition", "the condition in words"],
        [".fare-line", "the fare in words on the row"],
        [".origin-picker-label", "the change-station field label"],
        [".chipcount", "a chip's count"],
        [".condition", "the readable condition"],
        [".validity", "the fare validity"],
        ["#facetNotice", "a filter-change notice"],
        [".synthetic-banner", "the synthetic-data banner"],
        [".synthetic-banner strong", "the banner's label"],
        [".origin-slot", "the station slot in the heading"],
        ["#orderingNote", "the chooser's ordering note"],
        ["legend", "a group label"],
        [".choice-chip", "a destination chip"],
        [".segmented label", "a ticket type"],
        [".railcard-choice", "a party choice"],
        [".toggle", "a button"],
        [".buy", "a ticket link"],
        ["#moreFiltersToggle", "the refinements control"],
        ["#nomatch", "a no-match message"],
        [".method summary", "the method disclosure"],
        ["#empty", "an empty result"],
      ];
      // The condition and its validity are one disclosure away on the row, so
      // the first row is opened for the measuring and closed again afterwards.
      // A contrast check that only measured what happened to be unfolded is how
      // the warn token regressed before (C14): the sentence a reader must not
      // misread would simply have stopped being measured.
// The row opened for the measuring is a row that HAS a condition: the
      // condition is only printed where a fare carries a restriction code, so
      // a probe that opened the first row found nothing to measure on a page
      // whose cheapest fare is an unrestricted one, and reported the C14
      // regression as covered when it had measured no condition at all. The
      // named modes are tried in turn and the page is put back afterwards, so
      // the probe does not change what the rest of the matrix measures.
      const modeBefore =
        (document.querySelector('input[name="ticketMode"]:checked') || {}).value || "";
      const budgetBefore = document.getElementById("budget") ? budget.value : "";
      let rowToggle = null;
      if (document.getElementById("rows") && typeof setBudget === "function") {
        setBudget(budgetCeiling());
        currentPage = 1;
        render();
        for (const mode of [modeBefore, "single", "return", "anytime"]) {
          const input = document.querySelector(`input[name="ticketMode"][value="${mode}"]`);
          if (!input) continue;
          input.checked = true;
          currentPage = 1;
          render();
          const row = Array.from(document.querySelectorAll("#rows tr:not(.detail)")).find((r) => {
            const found = activeDestinations().find((d) => d.crs === r.dataset.crs);
            return found && found.restrictionCode;
          });
          if (row) {
            rowToggle = row.querySelector(".toggle[aria-expanded=false]");
            break;
          }
        }
      }
      if (rowToggle) rowToggle.click();
      const measured = [];
      for (const [selector, what] of SELECTORS) {
        const el = document.querySelector(selector);
        if (!el) continue;
        const style = getComputedStyle(el);
        const box = el.getBoundingClientRect();
        if (box.width === 0 || box.height === 0) continue;
        const size = parseFloat(style.fontSize);
        const bold = parseInt(style.fontWeight, 10) >= 700;
        // WCAG's own split: large text is 24px, or 18.66px when bold.
        const needed = size >= 24 || (bold && size >= 18.66) ? 3 : 4.5;
        const value = ratio(toRgba(style.color).slice(0, 3), behind(el).slice(0, 3));
        measured.push({ what, selector, value: Math.round(value * 100) / 100, needed, size });
      }
      if (rowToggle) rowToggle.click();
      const back = document.querySelector(`input[name="ticketMode"][value="${modeBefore}"]`);
      if (back) back.checked = true;
      if (document.getElementById("rows") && typeof setBudget === "function") {
        setBudget(Number(budgetBefore));
        currentPage = 1;
        render();
      }
      // Whether this page's feed prices any fare with a condition at all. A
      // page that has none cannot be asked to have measured one, and saying so
      // is the difference between "nothing to measure" and "the condition was
      // dropped". Carried on the array so every reader below keeps its shape.
      measured.hasRestricted = Boolean(
        typeof DATA !== "undefined" &&
          [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations]
            .flat()
            .filter(Boolean)
            .some((d) => Boolean(d.restrictionCode))
      );
      return measured;
    });
    const failures = contrast.filter((entry) => entry.value < entry.needed);
    check(
      `every kind of text meets AA contrast in ${scheme}`,
      contrast.length >= 4 && failures.length === 0,
      `${contrast.length} measured, worst ${contrast.reduce((low, e) => Math.min(low, e.value / e.needed), 99).toFixed(2)}x of what it needs` +
        (failures.length ? " -- " + failures.map((f) => `${f.what} ${f.value}:1 needs ${f.needed}:1`).join("; ") : "")
    );
    // The condition a reader must not misread is now one disclosure away, so
    // the probe above opens the first row before it measures. That is the whole
    // of the C14 regression cover, and a probe that stopped opening it would
    // report every condition as 0x0 and skip it in silence -- so the measurement
    // is a check in its own right on every route that has rows.
    check(
      `the row's fare condition is measured for contrast in ${scheme}`,
      contrast.some((entry) => entry.selector === ".condition") ||
        !contrast.hasRestricted ||
        (await page.locator("#rows .toggle").count()) === 0,
      contrast.map((entry) => entry.selector).join(" ")
    );
    // ------------------------------------------------------------- the targets
    const targets = await page.evaluate(() => {
      // The rendered box, plus a positioned ::after's slop: the row actions
      // are small marks that reach 44px through it, and measuring the mark
      // alone would fail a target that is really 44px.
      const hitBox = (el) => {
        const rect = el.getBoundingClientRect();
        const after = getComputedStyle(el, "::after");
        if (after.content === "none" || after.position !== "absolute") {
          return { w: rect.width, h: rect.height, rawW: rect.width, rawH: rect.height };
        }
        // The slop is written as a negative inset and reaches outwards, so its
        // magnitude is what adds to the box.
        const inset = (name) => {
          const raw = parseFloat(after[name]);
          return Number.isFinite(raw) ? Math.abs(raw) : 0;
        };
        return {
          w: rect.width + inset("left") + inset("right"),
          h: rect.height + inset("top") + inset("bottom"),
          rawW: rect.width,
          rawH: rect.height,
        };
      };
      // WCAG 2.5.8 is 24px for any pointer target; the row actions and the
      // phone control are promised at 44px, so both are measured and named.
      const MINIMUM = 24;
      const PROMISED = 44;
      const small = [];
      const underPromised = [];
      const inlineInText = [];
      const seen = [];
      // The row's own actions are inside the row's panel, so one panel is
      // opened for the sweep and closed at the end: an unmeasured promise is a
      // promise nobody checked.
      const expander = document.querySelector("#rows tr:not(.detail) .toggle[aria-expanded='false']");
      const firstPanel = document.querySelector("#rows tr.detail") ? null : expander;
      if (firstPanel) firstPanel.click();
      for (const el of document.querySelectorAll(
        "button, a[href], input, select, textarea, summary, [role=button]"
      )) {
        if (el.closest("[hidden]")) continue;
        const style = getComputedStyle(el);
        if (style.display === "none" || style.visibility === "hidden") continue;
        // A control that is optically hidden inside its own label is measured
        // through that label: the label is what a finger touches.
        const measured = el.type && el.closest("label") ? el.closest("label") : el;
        if (measured.getBoundingClientRect().width === 0 || measured.getBoundingClientRect().height === 0) continue;
        // WCAG 2.5.8 exempts a target that sits in a sentence or a block of
        // text -- a link inside a fare's description is read, not aimed at. The
        // exemption is counted and reported rather than applied silently.
        if (el.tagName === "A" && getComputedStyle(el).display === "inline") {
          const surrounding = (el.parentElement ? el.parentElement.textContent : "").trim();
          if (surrounding.length > el.textContent.trim().length) {
            inlineInText.push(el.getAttribute("href") || el.textContent.trim().slice(0, 30));
            continue;
          }
        }
        const box = hitBox(measured);
        const record = {
          what: el.id || el.getAttribute("aria-label") || el.tagName.toLowerCase(),
          w: Math.round(box.w),
          h: Math.round(box.h),
          raw: `${Math.round(box.rawW || box.w)}x${Math.round(box.rawH || box.h)}`,
          html: el.outerHTML.slice(0, 70),
        };
        seen.push(record);
        if (Math.min(box.w, box.h) + 0.5 < MINIMUM) small.push(record);
        // The filter families were 36px and outside the gate entirely, because
        // the control a finger touches is a <label> wrapping a hidden input and
        // the selector below only ever asked for buttons, links and inputs.
        // C23 holds the segmented ticket types, the destination chips and the
        // party choices to the same 44px the row actions are held to, and the
        // label is what is measured.
        const filterControl = el.closest(".segmented label, .choice-chip, .railcard-choice, input[type=range]");
        const promised = el.classList.contains("toggle") || el.classList.contains("buy") ||
          el.id === "moreFiltersToggle" || !!filterControl;
        if (promised && Math.min(box.w, box.h) + 0.5 < PROMISED) underPromised.push(record);
      }
      if (firstPanel) firstPanel.click();
      return { small, underPromised, inlineInText, seen };
    });
    check(
      `every pointer target is at least 24px in ${scheme}`,
      targets.small.length === 0,
      targets.small.length
        ? JSON.stringify(targets.small.slice(0, 5))
        : `${targets.seen.length} targets measured, ${targets.inlineInText.length} inline in a sentence and exempt`
    );
    check(
      `the controls promised at 44px are at least 44px in ${scheme}`,
      targets.underPromised.length === 0,
      targets.underPromised.length ? JSON.stringify(targets.underPromised.slice(0, 5)) : "row actions and the phone control"
    );
    // ------------------------------------------------------------------ zoom
    // 320px is what 200% zoom leaves of a 640px screen: the width at which a
    // layout that only works at desktop stops working.
    await page.setViewportSize({ width: 320, height: 720 });
    const zoomed = await page.evaluate(() => {
      const html = document.documentElement;
      return {
        overflow: Math.max(html.scrollWidth, document.body.scrollWidth) - window.innerWidth,
        body: parseFloat(getComputedStyle(document.body).fontSize),
      };
    });
    check(
      `at 320px -- a 200% zoom -- nothing scrolls sideways in ${scheme}`,
      zoomed.overflow <= 0,
      `${zoomed.overflow}px`
    );
    check(
      `at 320px the text is still the base size in ${scheme}`,
      zoomed.body >= 16,
      `${zoomed.body}px`
    );
    // The width check above can only judge the text a fixture happens to
    // contain, and that is how a 36px sideways scroll shipped: the demo
    // privacy page names a contact made of ordinary words, while the real one
    // carries an address whose 40 unbroken characters were wider than the
    // column. The demo page passed and the real page did not.
    //
    // So the contract is tested directly rather than waited for: put a run
    // that cannot break in the page's own text and prove the page still does
    // not scroll sideways. No fixture can hide it, because the fixture supplies
    // nothing -- the check brings its own worst case.
    const injected = await page.evaluate(() => {
      const long = "A".repeat(160) + "@example.invalid";
      // The narrowest real container on the page, not the document, because
      // the document can always look fine while a column inside it is the
      // thing that actually widened.
      const targets = [
        ...document.querySelectorAll("main p, main li, main td, main dd, main h2, p.muted, .tag"),
      ];
      if (!targets.length) return { skipped: true };
      const probe = document.createElement("p");
      probe.className = "muted";
      probe.id = "overflow-probe";
      probe.textContent = long;
      const host = targets[Math.min(2, targets.length - 1)];
      host.parentElement.insertBefore(probe, host);
      // Two ways a reader actually loses text, and only two.
      //
      // A column is a fault when it CLIPS: its computed overflow-x is not
      // visible, so the excess is gone rather than painted outside. The
      // opposite case is not a fault and was measured here first: a small
      // button reports a few pixels of scrollWidth past its own box while its
      // text sits ten pixels inside it on both sides. That is box arithmetic,
      // and calling it a defect would have sent someone to fix a rendering
      // that is correct.
      //
      // `.sr-only` is excluded by width: a 1px box holding nowrap text is
      // what that class is FOR -- read by assistive technology, not seen -- so
      // its scrollWidth says nothing about layout. A real column is hundreds
      // of pixels wide, so nothing else is skipped by this.
      const clipped = Math.max(
        0,
        ...[...document.querySelectorAll("main *")]
          .filter((el) => el.clientWidth > 2)
          .filter((el) => getComputedStyle(el).overflowX !== "visible")
          .map((el) => el.scrollWidth - el.clientWidth)
      );
      const scroll =
        Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) -
        window.innerWidth;
      probe.remove();
      return { skipped: false, scroll, clipped, tagged: targets.length };
    });
    check(
      `at 320px an unbreakable run does not widen the page in ${scheme}`,
      injected.skipped || (injected.scroll <= 0 && injected.clipped <= 1),
      injected.skipped
        ? "the page has no prose container to measure, so this proves nothing"
        : `document ${injected.scroll}px, worst clipped column ${injected.clipped}px, from ${injected.tagged} candidate(s)`
    );
  }
  // The theme switch. A reader who cannot change the palette has a page built
  // for one person, so the control is read from the page: it is there, it is a
  // switch with a name, and the state it holds is the palette the page is
  // actually painting. The default is checked on a first visit with the
  // storage emptied, because "dark unless the reader says otherwise" is a claim
  // about a reader who has never pressed anything.
  await page.evaluate(() => { try { localStorage.clear(); } catch (e) { /* nothing stored */ } });
  await page.reload();
  const themeControl = await page.evaluate(() => {
    const toggle = document.getElementById("themeToggle");
    if (!toggle) return { present: false };
    return {
      present: true,
      role: toggle.getAttribute("role"),
      checked: toggle.getAttribute("aria-checked"),
      theme: document.documentElement.dataset.theme,
      name: (toggle.textContent || "").trim(),
      hidden: toggle.hidden,
      box: (() => {
        const r = toggle.getBoundingClientRect();
        return { w: Math.round(r.width), h: Math.round(r.height) };
      })(),
    };
  });
  check(
    "the page offers a theme switch",
    themeControl.present && !themeControl.hidden,
    themeControl.present ? (themeControl.hidden ? "rendered but hidden" : "shown") : "no #themeToggle"
  );
  if (themeControl.present) {
    check(
      "the theme switch is a named switch whose state is the page's palette",
      themeControl.role === "switch" &&
        Boolean(themeControl.name) &&
        themeControl.checked === String(themeControl.theme === "dark"),
      `role ${themeControl.role}, name "${themeControl.name}", checked ${themeControl.checked}, theme ${themeControl.theme}`
    );
    check(
      "and a reader with no stored choice gets the dark palette",
      themeControl.theme === "dark" && themeControl.checked === "true",
      `first visit painted ${themeControl.theme}`
    );
    check(
      "and the switch is a pointer target of at least 44px",
      themeControl.box.w >= 44 && themeControl.box.h >= 44,
      `${themeControl.box.w}x${themeControl.box.h}px`
    );
    // The choice has to outlive the visit, or it is not a choice.
    await page.locator("#themeToggle").click();
    const chosen = await page.evaluate(() => document.documentElement.dataset.theme);
    await page.reload();
    const afterReload = await page.evaluate(() => document.documentElement.dataset.theme);
    check(
      "and the reader's choice survives a reload",
      chosen === "light" && afterReload === "light",
      `pressed to ${chosen}, reloaded as ${afterReload}`
    );
  }
  // The NRE source credit, on a page that composes the NRE notice and on no
  // other page. The Developer Brand Guidelines require the "Powered by National
  // Rail Enquiries" logo and a link to NRE's site, placed underneath the
  // information the feed supplied, so all three are read here rather than
  // assumed from the markup: the mark must be visible, must be legible (it is
  // white on a fixed dark fill, so the light palette could swallow it), and must
  // carry a name a screen reader reads, because the mark is paths.
  const credit = await page.evaluate(() => {
    const node = document.querySelector(".nre-credit");
    if (!node) return { present: false };
    const img = node.querySelector('[role="img"]');
    const link = node.querySelector("a");
    const mark = node.querySelector("svg");
    const plate = node.querySelector(".nre-logo");
    const box = plate ? plate.getBoundingClientRect() : { width: 0, height: 0 };
    return {
      present: true,
      name: img ? img.getAttribute("aria-label") : "",
      href: link ? link.getAttribute("href") : "",
      markPaths: mark ? mark.querySelectorAll("path").length : 0,
      width: Math.round(box.width),
      height: Math.round(box.height),
      // Underneath the results, which is the placement the guidelines name for
      // a feed that is the page's predominant information.
      belowTable: (() => {
        const table = document.querySelector("table");
        if (!table) return true;
        return table.getBoundingClientRect().top < node.getBoundingClientRect().top;
      })(),
    };
  });
  const nreNotice = await page.evaluate(() =>
    [].concat((typeof DATA !== "undefined" && DATA.attribution) || []).some(
      (notice) => /National Rail Enquiries/.test(notice)
    )
  );
  check(
    "the NRE credit appears exactly when the page acknowledges NRE as the source",
    credit.present === nreNotice,
    `credit: ${credit.present}, NRE notice: ${nreNotice}`
  );
  if (credit.present) {
    check(
      "the credit shows the Powered by National Rail Enquiries mark",
      credit.markPaths > 0 && credit.name === "Powered by National Rail Enquiries",
      `${credit.markPaths} path(s), name "${credit.name}"`
    );
    check(
      "and it links to NRE, as the guidelines ask",
      /nationalrail\.co\.uk/.test(credit.href),
      credit.href
    );
    check(
      "and it is legible, sitting on its own plate underneath the information",
      credit.width > 100 && credit.height >= 24 && credit.belowTable,
      `${credit.width}x${credit.height}px, below the table: ${credit.belowTable}`
    );
  }
  // The matrix leaves the page as it found it: the next section drives controls.
  await page.emulateMedia({ colorScheme: "light" });
  await setTheme(page, "light");
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto(url);
}
/**
 * Press the page's theme switch until it holds the asked-for scheme, and report
 * what it holds afterwards. Driving the real control rather than setting the
 * attribute is the point: a switch that reads right and does nothing is the
 * defect this suite exists to catch, and setting the attribute by hand would
 * never notice.
/**
 * Press the page's theme switch until it holds the asked-for scheme, and report
 * what it holds afterwards. Driving the real control rather than setting the
 * attribute is the point: a switch that reads right and does nothing is the
 * defect this suite exists to catch, and setting the attribute by hand would
 * never notice.
 */
async function setTheme(page, scheme) {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const now = await page.evaluate(() => document.documentElement.dataset.theme);
    if (now === scheme) return now;
    const toggle = page.locator("#themeToggle");
    if (!(await toggle.count()) || (await toggle.isHidden())) return now || "no control";
    await toggle.click();
  }
  return page.evaluate(() => document.documentElement.dataset.theme);
}
/** Is a painted background the light one? Used only to prove the scheme landed. */
function isLight(colour) {
  const parts = String(colour).match(/[\d.]+/g);
  if (!parts) return true;
  const [r, g, b] = parts.map(Number);
  // Rec. 601 luma: the same split the eye makes, and enough to tell #fff from
  // #14181d without a colour library.
  return 0.299 * r + 0.587 * g + 0.114 * b > 128;
}
module.exports = { checkAccessibilityMatrix, setTheme, isLight };
