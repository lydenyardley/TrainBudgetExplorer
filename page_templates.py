"""The page's HTML, CSS, and JavaScript, as fill-in templates.

Pure strings: no imports, no logic beyond the __TOKEN__ placeholders that
render_page / render_privacy / render_chooser replace. The templates are the
page the reader sees; build_demo_page.py owns what fills them.

SHARED_CSS is the one source for the palette, spacing, focus ring, links,
navigation and disclosure styles every route uses (S39). It is inlined into
each template at the bottom of this module, so a route's own block holds only
what is genuinely its own.
"""

SHARED_CSS = """  /* S39: the tokens and components every route shares, written once here and
     inlined into each generated file. The chooser, a station page and the
     privacy page therefore cannot drift apart -- and the site still ships no
     external asset, because this block is part of the HTML it is written into.
     A route that needs to differ sets a token (--page-max, --page-pad, --h1)
     in its own :root rather than restating the rule. */
  /* The palette, in one list, both schemes at once.
     Each colour token is written twice: the plain light value first, so a
     browser without light-dark() paints the light page rather than resolving
     an invalid value to nothing, and light-dark() after it, so a browser that
     has it takes both palettes from one declaration and the switcher's only
     job is to say which one. :root asks for "light dark", so a reader with no
     stored choice still gets their system preference; the reader's own choice
     overrides it through the attribute below. The system default is dark --
     this is a page read at night, on a phone, on a train. */
  :root {
    color-scheme: light dark;
    --bg: #fff; --bg: light-dark(#fff, #14181d);
    --fg: #11161d; --fg: light-dark(#11161d, #e7ebf0);
    --line: #d0d5dd; --line: light-dark(#d0d5dd, #3a424c);
    --muted: #5b6472; --muted: light-dark(#5b6472, #a7b2c0);
    --accent: #14509b; --accent: light-dark(#14509b, #7db4f5);
    --ochre: #a65d00; --ochre: light-dark(#a65d00, #f0b35b);
    --best: rgba(20, 80, 155, .07); --best: light-dark(rgba(20, 80, 155, .07), rgba(125, 180, 245, .12));
    --field: #fff; --field: light-dark(#fff, #1c2127);
    /* The stylesheet arrived. A route that fetches this block reads the
       marker to know, and a route that inlined it can always answer yes
       (ADR-0047). It is a token rather than a flag on <html> so the answer
       is the browser's own, not a guess about whether a request is still
       in flight. */
    --tbe-stylesheet: 1;
    /* The warn token is the restricted fare's own words and the "advance"
       and "restricted" marks beside a code, and the cheapest list leads with
       exactly those rows (Q4), so it is measured where the text actually
       sits: on the row panel's --best tint, which is #eff3f8 in the light
       palette. #9a6700 came to 4.36:1 there and the matrix holds every
       kind of text to 4.5:1; #8f5f00 is 4.94:1 on that tint and 5.52:1 on
       white, and the dark value already cleared it. */
    --warn: #8f5f00; --warn: light-dark(#8f5f00, #f0b35b);
    /* The NRE credit, reversed. The file in assets/ is NRE's own, byte for
       byte; the reversal is applied here rather than by editing the artwork,
       because an edited file stops being the file the brand supplied and
       nothing downstream could tell. The mark is painted in a light rendering
       of NRE's blue on a deep plate of the same blue, which is what makes the
       credit read as a designed chip rather than a white box in a dark footer.
       The plate is dark in both palettes, so the mark looks the same either
       way and its contrast does not have to be re-earned per theme.

       This is a judgement call, not a licence finding: NRE's pack ships no
       reversed asset, and their developer page says brand materials are
       subject to their permission, so a reversed rendering is recorded as an
       open question in licences/release-clearance.md. Taking these two tokens
       and the rule at the bottom of this block out, and giving .nre-logo a
       light background, puts NRE's own colours back. */
    --nre-plate: #141b3d; --nre-ink: #cdd6ff;
    --page-max: 78rem; --page-pad: clamp(1rem, 3vw, 2.25rem); --h1: clamp(2rem, 7vw, 7rem);
  }
  /* The reader's choice, which beats the system preference: the tokens are
     already resolved by light-dark(), so naming the scheme is the whole of it,
     and it also moves the form controls, the scrollbars and the canvas. */
  :root[data-theme="light"] { color-scheme: light; }
  :root[data-theme="dark"] { color-scheme: dark; }

  /* The theme control, at the top right of the page and in the flow rather
     than pinned to the corner. A fixed control in the corner sits on top of
     whatever the reader scrolls there: on a phone the filter chips land under
     it, and a tap that should have chosen a destination type chooses the
     palette instead. 44px, because that is the promise the accessibility
     matrix holds every control to. */
  #themeToggle { display: flex; align-items: center; justify-content: center;
                 margin: 0 0 .2rem auto; width: 2.75rem; height: 2.75rem; padding: .4rem;
                 border: 0; border-radius: .6rem;
                 background: transparent; color: var(--muted); font: inherit; cursor: pointer; }
  #themeToggle:hover { background: var(--field); color: var(--fg); }
  #themeToggle .glyph { font-size: 1.15rem; line-height: 1; }
  * { box-sizing: border-box; }
  [hidden] { display: none !important; }
  /* The column is centred on the page. It was not: a max-width with no auto
     margins pinned the whole site to the left edge, so on a wide screen every
     route sat in the first 40rem of the viewport with the rest of the page
     empty. The background goes on the root element as well, or the band either
     side of the column would belong to no design and show the canvas white in
     a dark page. The text inside the column stays left-aligned: this centres
     the measure, not the prose. */
  html { background: var(--bg); }
  body { margin: 0 auto; padding: var(--page-pad); max-width: var(--page-max);
         background: var(--bg); color: var(--fg);
         font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
  /* 1.2, not the 1.35 a paragraph wants: at six rem the line box is most of a
     phone screen, and a display heading that keeps body leading reads as two
     separate sentences. balance splits the long question into two lines of
     similar length instead of one long and one short, which is the difference
     between a heading and a paragraph that happens to be large. */
  h1 { font-size: var(--h1); line-height: 1.06; letter-spacing: -.03em; font-weight: 700;
       text-wrap: balance; }
  h2 { font-size: 1.05rem; margin: 1.5rem 0 .25rem; }
  p, li { margin: .4rem 0; }
  a { color: var(--accent); }
  /* A single unbroken run of characters must not decide the width of the
     page. Real text contains these and the project cannot choose their
     content: a privacy contact address, a tracked affiliate link, a
     restriction code list, a URL in a feed-record line. One that cannot fit
     its column used to widen the whole document, so a 200%-zoom phone reader
     scrolled sideways on a page whose only fault was an email address.

     `anywhere` rather than `break-word` because the text sits inside grid and
     table tracks, and only `anywhere` also shrinks the intrinsic min-content
     size those tracks are sized against -- `break-word` leaves a flex or grid
     child able to overflow before the text has anywhere to break. Prose is
     untouched: a word that fits on a line is never split.

     Inherited, so one rule covers every element including those the page
     script creates after load, which no selector here could name. */
  body { overflow-wrap: anywhere; }
  /* One focus ring for the whole site, on every route, so a keyboard reader
     finds the same affordance wherever they are. */
  :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: .2rem; }
  ::selection { background: color-mix(in srgb, var(--accent) 25%, transparent); }
  .muted, .tag, .disclosure { color: var(--muted); }
  .tag { font-size: .8rem; margin: .2rem 0; }
  .sub { color: var(--muted); max-width: 75ch; }
  .back-link { display: inline-flex; align-items: center; min-height: 44px; margin-bottom: 1rem; }
  input[type=search], input[type=number], select { width: 100%; padding: .5rem; border: 1px solid var(--line);
                                                    border-radius: .35rem; font: inherit; color: var(--fg);
                                                    background: var(--field); }
  /* The two slots a reader edits inside the page's own sentence: the budget,
     and the station they are starting from. They are one component on every
     route -- same accent, same dashed underline, same focus wash -- because
     they are the same two gaps in the same question, and a reader who has met
     one has met the other. The underline is the whole affordance: it is the
     shape a browser draws under a text field, so it says "this part of the
     sentence is yours" without a label floating above it.

     Before a station has been chosen the second slot is a real text field, so
     the caret in it is the browser's own and blinks, and the word in it is a
     placeholder rather than a value. That word is muted: the reader's answer is
     what belongs in the accent, not the page's suggestion. */
  .heading-field, .origin-slot-wrap { display: inline-flex; align-items: baseline; color: var(--accent);
                                 border-bottom: 1px dashed color-mix(in srgb, var(--accent) 55%, transparent);
                                 border-radius: .15rem .15rem 0 0; }
  /* Focus is carried by the underline and by the caret, never by a wash. At
     heading size a background box turns a word in a sentence into a form
     field, which is the one thing this component exists to avoid -- and the
     caret is already sitting in the slot, blinking, which no other affordance
     can say. A keyboard reader gets the page's own focus ring on top, because
     :focus-visible is a different question from :focus-within. */
  .heading-field:focus-within, .origin-slot-wrap:focus-within { border-bottom-style: solid; border-bottom-width: 2px; }
  .heading-field { cursor: text; }
  /* The name inside the wrapper is a button, not a slot of its own, so the
     shared rule does not draw a second underline under it. */
  .origin-slot-wrap .origin-slot { display: inline-flex; align-items: baseline;
                                   color: inherit; border-bottom: 0; padding: 0; }
  /* The currency sign is read, not decorative. It was aria-hidden, so the
     heading's accessible name was "for up to 20" while the page said 20 pounds
     everywhere else; the number field keeps its own label, so nothing is
     announced twice. */
  .budget-prefix { user-select: none; }
  /* "from" sits on the second line in the page's own voice rather than as
     punctuation between the two halves. The middots it replaced were at
     .38em in the muted colour, and at six-plus rem a pair of them either side
     of the number the reader came to set said "and also" about a word that was
     already a separate line. The line break is the separator. */
  .heading-lead { color: var(--muted); margin-right: .15em; }
  /* The amount and the words around it, in one box that cannot wrap. A break
     opportunity sits at the edge of an inline field whatever follows it, so
     without this the second line can begin with the number and the "from" can
     be left at the end of the first. */
  .heading-slot { white-space: nowrap; }
  #budgetNumber { width: 2ch; min-width: 1ch; padding: .05rem .1rem; border: 0; outline: 0;
                  background: transparent; color: inherit; font: inherit; font-weight: inherit;
                  letter-spacing: inherit; appearance: textfield; }
  #budgetNumber::-webkit-inner-spin-button { appearance: none; }
  /* The station slot on the route that has no station yet. It grows with what
     is typed where the browser can resize a field to its content, and holds a
     sensible width where it cannot; the caret is themed from the palette, like
     every other browser surface this page ships. */
  /* The field is as wide as the word in it. It shipped at a fixed 9ch, which is
     wider than "station" at every heading size, so the dashed underline ran on
     past the word it belongs to and said the field was bigger than the question
     (finding, 29 September 2026). `field-sizing: content` sizes it to the
     placeholder while it is empty and to what is being typed as it is typed; the
     width that used to be fixed is the fallback for a browser that cannot size a
     field to its content yet, and the cap keeps a long station name from pushing
     the heading's line past the viewport. Neither half of the cap is a
     percentage: the slot is shrink-to-fit, so a percentage max-width on its only
     child is treated as none while the slot decides its own width, and the
     heading's line then measured the field's content -- 3,047px with sixty
     characters typed, which scrolled the page 1,739px sideways. ch scales with
     the heading's own size, so 18 of them fit the column on a wide screen, and
     the viewport share is what fits on a narrow one. */
  .origin-slot-wrap #originSearch { width: auto; min-width: 4ch; max-width: min(18ch, 90vw); field-sizing: content;
                               padding: .05rem .15rem; border: 0; outline: 0;
                               background: transparent; color: inherit; font: inherit;
                               font-weight: inherit; letter-spacing: inherit;
                               caret-color: var(--accent); }
  @supports not (field-sizing: content) {
    .origin-slot-wrap #originSearch { width: 9ch; }
  }
  .origin-slot-wrap #originSearch::placeholder { color: var(--muted); opacity: 1; }
  /* One drawn disclosure mark, used by both the refinements control and the
     station slot. Authored rather than a character: a character has no stroke
     weight of its own, is styled differently by every font, and the one this
     replaced was written as a CSS escape inside a Python string -- where
     Python read it first, so "\\25be" shipped as a control character followed
     by the letters "be" on every station page. */
  .chevron { width: 1em; height: 1em; flex: none; align-self: center;
             transition: transform .18s ease-out; }
  @media (prefers-reduced-motion: reduce) { .chevron { transition: none; } }
  /* C29: one main landmark per route, so landmark navigation works. It wraps
     the route's own content only; the back link and the footer stay outside it
     as the navigation landmarks they are. */
  main { display: block; padding-top: .5rem; }
  /* The footer, the back link and the footer nav are the same shape on every
     route: a quiet rule above, 44px of touch target for a phone. The height is
     on the anchor itself, not only on a container around it -- a nav that is
     44px tall with a 24px link in it is not a 44px target (C25). */
  /* The NRE "Powered by" mark, reversed onto a dark plate: see --nre-plate.
     The artwork keeps its own fill, and this paints over it, so the file in
     assets/ is still exactly what NRE supplied. The !important is not
     decoration: Illustrator wrote fill:#2E2D7F into a style attribute on each
     of the mark's 22 shapes, and a style attribute outranks any stylesheet
     rule however specific it is, so a plain selector here loses silently and
     the mark stays NRE's blue on a dark plate -- 1.4:1, which the browser
     suite measures and fails on, so the two cannot drift apart. */
  .nre-credit { margin: 0 0 .7rem; }
  /* The link is the pointer target, so it has to be as tall as the plate it
     wraps. Left inline, its box is the line box -- 18px -- while the mark
     overflows it, and a 24px-target check rightly fails. */
  .nre-credit a { display: inline-flex; align-items: center; }
  .nre-logo { display: inline-flex; align-items: center; padding: .3rem .55rem;
              background: var(--nre-plate);
              border: 1px solid color-mix(in srgb, var(--nre-ink) 22%, transparent);
              border-radius: .3rem; }
  /* Every shape in the mark, not just the paths: two of the 22 are rects, and
     a rule that caught the paths alone would leave those in NRE's blue. */
  .nre-logo svg * { fill: var(--nre-ink) !important; }
  .nre-logo svg { display: block; height: 2rem; width: auto; }
  footer { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--line);
           color: var(--muted); font-size: .85rem; }
  .footnav { margin-top: 1.5rem; }
  .footnav a, .back-link a { display: inline-flex; align-items: center; min-height: 44px; color: inherit; }
  .back-link a { color: var(--accent); }
  .sr-only { position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden;
             clip-path: inset(50%); white-space: nowrap; border: 0; }
  /* S45: the synthetic-data state, in the same component on every route, so
     an invented fare cannot be mistaken for a real one in a review, a demo or
     a shared screenshot. It is a banner rather than a footnote because the
     footnote is what gets cropped. */
  .synthetic-banner { display: block; margin: 0 0 1rem; padding: .5rem .7rem;
                      border: 1px solid var(--ochre); border-left-width: .3rem; border-radius: .35rem;
                      background: color-mix(in srgb, var(--ochre) 10%, transparent);
                      color: var(--fg); font-size: .85rem; }
  .synthetic-banner strong { color: color-mix(in srgb, var(--ochre) 80%, var(--fg)); }
"""

# The station route's own stylesheet, which used to sit in its <style>
# block beside the shared one. The two are still one string, because a
# station page's CSS is byte-identical on every station page -- measured,
# not assumed: the same 34.6 KB on all 2,712 pages of a full-network
# build -- so it is written once as a hashed asset and fetched, and a
# route whose copy does not arrive says so and loses the theme switch
# rather than offering a control that cannot change a palette the page
# has not got (ADR-0033's boundary, ADR-0047).
STATION_CSS = """  /* No width of its own: the column, the padding and the heading size are the
     shared ones, so a station page and the chooser are the same page with
     different content. The table simply uses the width it is given. */
  /* The station slot wears the shared .origin-slot skin, so the same underline
     sits under a name that navigates here and under one that is typed into on
     the chooser. This rule only takes the browser's own button chrome off it:
     border-bottom is left to the class, because the border shorthand here
     would win on specificity and erase the affordance. The mark is the shared
     drawn chevron -- an affordance, not a word, and aria-hidden so it is not
     read out as part of the heading's name. */
  #changeOrigin { display: inline-flex; align-items: baseline; gap: .35rem; padding: .05rem .15rem;
                  border-top: 0; border-right: 0; border-left: 0;
                  background: transparent; color: var(--accent);
                  font: inherit; font-weight: inherit; letter-spacing: inherit; cursor: pointer; }
  #changeOrigin:hover, #changeOrigin:focus-visible { border-bottom-style: solid; }
  #changeOrigin:hover .chevron, #changeOrigin:focus-visible .chevron { opacity: 1; }
  #changeOrigin .chevron { width: .8em; height: .8em; opacity: .75; }
  /* One control that is always there and one block that folds away, at every
     width rather than below a breakpoint. Live at 1440px this bar put four
     controls a reader had not asked for -- a budget slider, three ticket
     types, three party choices and six destination chips -- above a list that
     was the reason they came. The budget stays outside the disclosure because
     it is the page's question rather than a refinement of it, and the toggle
     carries what is currently narrowed, so a folded bar is never a hidden
     filter. Nothing here depends on a viewport width or on a resize event. */
  /* No panel around them. The bar was a bordered, tinted card holding two
     controls, so the page had a box for a slider and a box for the button
     inside it -- and the box did not say anything the two controls do not
     say themselves. What is left is the budget under the heading's own
     budget, then the one control that folds the rest away. */
  .filter-bar { display: grid; grid-template-columns: minmax(0, 1fr); gap: .8rem; }
  .filter-bar fieldset { border: 0; margin: 0; padding: 0; min-width: 0; }
  .budget-track { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem .9rem; }
  /* Capped rather than stretched: a range input at the full width of a 78rem
     table is a long thin rule with a thumb somewhere on it, and the reader
     has to find the control inside it. At a control's own width the note
     beside it stays beside it. */
  .budget-track #budget { flex: 1 1 12rem; max-width: 34rem; min-width: 0; }
  .more-filters { display: block; }
  .more-filters-toggle { display: flex; flex-wrap: wrap; align-items: baseline; gap: .35rem .5rem;
                          width: 100%; min-height: 44px; padding: .5rem .6rem;
                          border: 1px solid var(--line); border-radius: .45rem;
                          background: var(--field); color: var(--fg); font: inherit; text-align: left;
                          cursor: pointer; }
  .more-filters-toggle:hover { border-color: var(--accent); }
  .more-filters-label { font-weight: 700; }
  .more-filters-toggle .chevron { margin-left: auto; color: var(--accent); }
  .more-filters[data-open="true"] .more-filters-toggle { margin-bottom: .9rem; border-color: var(--accent); }
  .more-filters[data-open="true"] .more-filters-toggle .chevron { transform: rotate(180deg); }
  .more-filters-panel { display: none; }
  .more-filters[data-open="true"] .more-filters-panel { display: grid; grid-template-columns: 1fr;
                                                          gap: 1.1rem; align-items: start; }
  .filter-bar legend, .filter-label { display: block; margin-bottom: .5rem; font-size: .72rem;
                                      text-transform: uppercase; letter-spacing: .08em; color: var(--muted); font-weight: 700; }
  .filter-options { display: flex; flex-wrap: wrap; gap: .45rem; }
  /* C23: these three families were 36px, below the 44px the row actions are
     already held to. A control a thumb has to hit gets the same floor as the
     others the project promised, and the floor is on the label a finger
     actually touches, not on the input hidden inside it. */
  .segmented label, .choice-chip { position: relative; display: inline-flex; align-items: center; justify-content: center;
                                   min-height: 2.75rem; min-width: 2.75rem;
                                   padding: .4rem .7rem; border: 1px solid var(--line); border-radius: .45rem;
                                   color: var(--fg); background: var(--field); cursor: pointer; font-size: .9rem; }
  .segmented input, .choice-chip input { position: absolute; opacity: 0; pointer-events: none; }
  .segmented label:has(input:checked), .choice-chip:has(input:checked) { border-color: var(--accent);
                                                                       background: var(--best); color: var(--accent); font-weight: 650; }
  .segmented label:has(input:focus-visible), .choice-chip:has(input:focus-visible) { outline: 2px solid var(--accent); outline-offset: 2px; }
  .segmented label:hover, .choice-chip:hover { border-color: var(--accent); }
  .choice-chip input:focus-visible + span { outline: 2px solid var(--accent); outline-offset: 3px; border-radius: .15rem; }
  .choice-chip input { pointer-events: auto; }
  .choice-chip span { pointer-events: none; }
  .choice-chip input { position: absolute; opacity: 0; }
  .choice-chip:has(input:focus-visible) { outline: 2px solid var(--accent); outline-offset: 2px; }
  input[type=range] { width: 100%; accent-color: var(--accent); height: 2.75rem; margin: 0; }
  .filter-bar input[type=checkbox] { accent-color: var(--accent); }
  .railcard-choice { display: flex; align-items: center; gap: .5rem; min-height: 2.75rem; }
  .railcard-choice input { width: 1.1rem; height: 1.1rem; margin: 0; }
  .railcard-help { display: block; color: var(--muted); font-size: .8rem; }
  /* The card list is one control, not six checkboxes. A select says "none of
     these" in its own first option, so the default needs no separate control
     and cannot be left on by a reader who meant standard fares. */
  #railcardSelect { width: auto; max-width: 100%; min-height: 2.75rem; }
  #railcardSelect[disabled] { opacity: .6; }
  /* Tight onto its table, which is the only thing it belongs to: the count
     now sits directly above the first row with the provenance above it
     (finding, 29 September 2026). The 1.75rem this used to carry separated it
     from a block of six paragraphs, and that margin is part of why the first
     fare sat below the fold on a laptop. */
  #summary { margin: .6rem 0 .3rem; font-weight: 600; }
  /* The table is as wide as its columns need and no wider. Stretched to the
     page's 78rem with the station name absorbing the slack, the price sat
     800px from the place it belongs to and the ticket action floated in the
     middle of an otherwise empty row. At content width the six columns sit
     together, the numbers stay near the names, and the list reads as a list.
     `max-width` keeps a very long station name from pushing the last column
     off a narrow screen; below the phone breakpoint the table stops being a
     table at all. */
  table { border-collapse: collapse; width: auto; max-width: 100%; }
  th, td { text-align: left; padding: .5rem .4rem; border-bottom: 1px solid var(--line); }
  td[data-label]::before { content: none; }
  /* A column's width is not the header's to decide. Measured on the real
     Grantham page, the Price column was 56px wide and CHANGES wrapped
     mid-word in 72px, and the two are one bug: the header was setting the
     width and the number paid for it. Neither half of this table wraps now,
     so each column is as wide as the widest number in it (finding, 29
     September 2026). */
  th { font-size: .8rem; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); white-space: nowrap; }
  .toggle { border: 1px solid var(--line); background: var(--field); color: var(--accent);
            border-radius: .3rem; font: inherit; font-size: .85rem; padding: .3rem .55rem;
            margin-left: .75rem; cursor: pointer; position: relative; }
  /* Hit-slop: the visible mark stays small beside its neighbours, but the
     touch target reaches 44px past it. */
  .toggle::after { content: ""; position: absolute; inset: -6px; }
  .toggle[aria-expanded=true] { border-color: var(--accent); }
  .buy { color: var(--accent); text-decoration: none; border-bottom: 1px solid currentColor;
         white-space: nowrap; position: relative; }
  .buy::after { content: ""; position: absolute; inset: -11px -4px; }
  tr.detail td { background: var(--best); border-bottom: 1px solid var(--line); }
  tr.detail ul { margin: 0; padding-left: 1.1rem; }
  tr.detail li { font-variant-numeric: tabular-nums; }
  /* The fare in words and the condition that goes with it, where the FARE and
     CONDITIONS columns put them except on the row the reader is reading
     (finding, 29 September 2026). The condition keeps the muted .restriction
     voice it had in the cell: same sentence, same measured contrast. */
  tr.detail .fare-line { margin: .55rem 0 0; font-weight: 600; }
  tr.detail .condition { margin: .15rem 0 0; }
  /* £10.10 painted as "£10.1" over "0" on 13 of the first 20 rows: a wrapped
     price is not a cramped column, it is a different number, and the reader
     comparing it with the row above has been told something false. */
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
  /* The price the card was taken off, in the same cell as the price: a
     discounted number never stands alone (Q3), and the second number is
     quieter because the first is the one the reader asked for. */
  td.num .was { color: var(--muted); font-size: .875em; }
  /* The destination and its three-letter code, which a seller asks for. The
     name carries the weight and the code recedes, because the code identifies
     the place to a booking system and says nothing to a reader. */
  .station-name { font-weight: 600; }
  .station-code { color: var(--muted); font-variant-numeric: tabular-nums; }
  /* The change count, and under it the station the journey changes at. Q2
     (ADR-0045) put the station in a disclosure on every row, which is a click
     per row to learn the one fact in the row worth acting on. */
  .changes-count { display: block; }
  .interchange { display: block; color: var(--muted); font-size: .82em; font-weight: 400; }
  /* The fare in three words. Two of the three are a warning, so they are the
     accent and the warning colour respectively, and the common case -- an
     ordinary fare -- stays in the page's own voice rather than being tinted to
     draw attention to nothing. The feed's code is in the row's own record. */
  .fare-kind { white-space: nowrap; }
  .fare-type[data-kind="advance"] .fare-kind { color: var(--warn); }
  .fare-type[data-kind="restricted"] .fare-kind { color: var(--warn); }
  .fare-type[data-kind="regular"] .fare-kind { color: var(--muted); }
  /* No row is highlighted for rank. The top row was tinted as the "best" fare,
     which on a page that refuses to imply a recommendation is a recommendation
     stated by a colour and never by a word (finding, 29 September 2026). The
     order the tint stood for is in the count line above the table, in words
     (ADR-0041).

     A row IS tinted under the pointer, and that is a different promise: it
     answers "which line am I reading", which is the one question a table of
     six columns asks and the one the eye cannot otherwise answer when the
     numbers run down the page. It is the field colour, not the accent, so it
     never reads as "this is the best fare", and it is skipped on touch, where
     there is no pointer to hover and the tint would stick. */
  @media (hover: hover) {
    #rows > tr[data-crs]:hover > td { background: var(--field); }
    #rows > tr[data-crs]:hover > td:first-child { border-radius: .3rem 0 0 .3rem; }
    #rows > tr[data-crs]:hover > td:last-child { border-radius: 0 .3rem .3rem 0; }
  }
  /* The action column never wraps its two controls onto two lines, which is
     what used to decide when the table had to stack on a tablet. Written for
     the results rows by name: the disclosure row is also a last child, and a
     panel is prose, so the no-wrap reached the fare sentence and the feed
     record and pushed the whole panel 70px past a 390px page. */
  #rows > tr[data-crs] > td:last-child, thead th:last-child { white-space: nowrap; }
  /* The two halves of one fact, stacked, never side by side: a change count
     with a station after it on the same line reads as two columns. */
  td.num .was { display: block; }
  .restriction { font-size: .78rem; color: var(--muted); }
  /* C14: this was a hard-coded #9a6700, which the dark palette never
     redefined -- so the one piece of text a reader must not misread measured
     3.66:1 in dark, below AA. It is a token now, beside the palette's other
     tokens, and each scheme sets it. */
  .restriction[data-status="restricted"] { color: var(--warn); }
  /* C08: the validity the feed states, in the same voice as the condition it
     belongs to, and separated from it so the two are not read as one run-on
     sentence. */
  .validity { display: block; margin-top: .15rem; }
  .restriction[data-status="unrestricted"] { color: var(--muted); }
  .heritage-proof { display: block; margin-top: .15rem; font-size: .75rem; font-weight: 400; color: var(--muted); }
  .heritage-proof a { color: inherit; text-underline-offset: .15em; }
  .heritage-proof a:hover, .heritage-proof a:focus-visible { color: var(--accent); }
  /* A chip's count is part of its label, so it sits inside the chip and is
     never the only thing carrying the type's name. */
  .chipcount { color: var(--muted); font-variant-numeric: tabular-nums; font-size: .8em; }
  #typeRule { display: block; margin: .35rem 0 0; }
  #clearTypes { margin-top: .35rem; }
  /* S19: the condition is the sentence; the record is folded under it. */
  .feed-record { margin-top: .2rem; font-size: .72rem; }
  .feed-record summary { display: inline-flex; align-items: center; min-height: 24px;
                         cursor: pointer; color: var(--muted); }
  .feed-record dl { margin: .2rem 0 0; display: grid; grid-template-columns: auto 1fr; gap: 0 .4rem; }
  .feed-record dt { color: var(--muted); }
  .feed-record dd { margin: 0; font-variant-numeric: tabular-nums; }
  /* S23: an absence the feed can name is not the same as a zero. */
  td.missing { color: var(--muted); font-style: italic; }
  .empty-actions { display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; }
  /* S26: the shortlist is a strip, not a section. It is a handful of places to
     compare rather than a result set to scan, and it sits directly above the
     table so that the place a reader just added appears in the same view as
     the control they added it with. */
  .shortlist-bar { margin: .35rem 0 .5rem; }
  .shortlist-controls { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem; }
  .shortlist-label { font-size: .72rem; text-transform: uppercase; letter-spacing: .08em;
                     color: var(--muted); font-weight: 700; }
  #shortlistPick { width: auto; min-width: 14rem; min-height: 2.75rem; }
  #shortlistPick:disabled { opacity: .6; }
  .shortlist-controls .toggle { margin-left: 0; min-height: 2.75rem; }
  .shortlist-chips { list-style: none; display: flex; flex-wrap: wrap; gap: .4rem;
                     margin: .55rem 0 0; padding: 0; }
  /* A chip is a place and its price with one way out of it. The cross is
     drawn rather than typed: the page has no icon set, and a letter x at this
     size reads as a multiplication sign. */
  .shortlist-chip { display: inline-flex; align-items: center; gap: .45rem;
                    padding: .3rem .3rem .3rem .6rem; border: 1px solid var(--line);
                    border-radius: 2rem; background: var(--field); }
  .shortlist-name { padding: 0; border: 0; background: transparent; color: var(--accent);
                    font: inherit; font-weight: 600; cursor: pointer; }
  .shortlist-name:hover { text-decoration: underline; }
  .shortlist-price { color: var(--muted); font-variant-numeric: tabular-nums; font-size: .85em; }
  .shortlist-drop { display: inline-flex; align-items: center; justify-content: center;
                    width: 1.75rem; height: 1.75rem; padding: 0; border: 0; border-radius: 50%;
                    background: transparent; color: var(--muted); cursor: pointer; }
  .shortlist-drop:hover { background: color-mix(in srgb, var(--accent) 12%, transparent); color: var(--accent); }
  .shortlist-share { margin-top: .5rem; }
  .shortlist-share summary { min-height: 44px; display: inline-flex; align-items: center;
                             color: var(--accent); cursor: pointer; }
  .empty-actions .toggle { min-height: 44px; }
  /* The railcard, said in the row's own words, in the row's own disclosure. It
     was a dialog with a Close button and a definition list of three numbers
     the row above it already carried; it is now one paragraph, and the only
     part of it that is ever urgent -- a card that cannot be used on this fare
     -- is the part that is coloured. */
  .card-note { margin: .5rem 0 0; padding: .5rem .6rem; border: 1px solid var(--line);
               border-radius: .4rem; background: var(--bg); }
  .card-note[data-state=blocked], .card-note[data-state=unavailable] { border-color: var(--warn); }
  .card-note[data-state=available] { border-color: color-mix(in srgb, var(--accent) 40%, var(--line)); }
  #empty { color: var(--muted); }
  #more { color: var(--muted); font-size: .9rem; }
  .copybox { width: 100%; font: inherit; font-size: .9rem; color: var(--fg); background: var(--field);
             border: 1px solid var(--line); border-radius: .35rem; padding: .5rem; resize: vertical; }
  /* The two actions a row keeps beside buying, inside the row's own panel: the
     railcard eligibility and the handoff text. They sat on the row itself until
     the distill pass measured five controls on every row and a hundred targets
     on page one (finding 4, 29 September 2026). The ticket link and the
     expander stay on the row, because buying is the action and the expander is
     the way in; everything a reader asks for after deciding waits one click in,
     beside the condition it explains. */
  .row-actions { display: flex; flex-wrap: wrap; gap: .75rem; margin-top: .6rem; }
  .row-actions .toggle { margin-left: 0; }
  /* The list, opened directly under the heading it replaces. It is as wide as
     the heading's own measure and no wider: it is a list of names and codes,
     and a column of links 24rem wide in a 78rem page reads as a sidebar. */
  #originPicker { margin: .4rem 0 1rem; max-width: 34rem; }
  .origin-picker-label { margin: 0 0 .3rem; font-size: .72rem;
                         text-transform: uppercase; letter-spacing: .08em; color: var(--muted); font-weight: 700; }
  #originPicks { list-style: none; margin: 0; padding: 0; max-height: 60vh; overflow-y: auto;
                 border-top: 1px solid var(--line); }
  #originPicks a { display: flex; justify-content: space-between; gap: .75rem; min-height: 44px;
                   padding: .55rem .4rem; align-items: baseline;
                   color: var(--accent); text-decoration: none; border-bottom: 1px solid var(--line); }
  #originPicks a:hover, #originPicks a:focus-visible { background: color-mix(in srgb, var(--accent) 8%, transparent); }
  #originPicks .code { color: var(--muted); font-variant-numeric: tabular-nums; }
  #originNomatch { color: var(--muted); margin: .5rem 0 0; }
  /* The unpriced-origin message replaces the intro, so it is page-size text in
     the normal foreground colour: a finding, not a footnote. */
  .unpriced { margin: 0 0 1.25rem; }
  #unpriced a { color: var(--accent); text-decoration: none; border-bottom: 1px solid currentColor; }
  .method { margin-top: 1rem; }
  .method summary { min-height: 44px; display: flex; align-items: center; color: var(--accent); cursor: pointer; }
  /* What the ticket link does, and how this page was built, are one fold above
     the table. The line a reader sees says what is inside it; only the wording
     waits. Those two paragraphs plus the build line were 57px of the 205px
     between the count and the table on the real Grantham page, which is what
     put the first fare below the fold on a laptop (finding, 29 September
     2026). */
  .link-terms { margin: 0; }
  .link-terms summary { min-height: 24px; display: inline-flex; align-items: center;
                        color: var(--muted); cursor: pointer; }
  .link-terms summary:hover, .link-terms summary:focus-visible { color: var(--accent); }
  .link-terms p { margin: .35rem 0 0; }
  code { font-size: .95em; }
  /* On a phone the table reflows into stacked rows, because a six-column table
     pushes the ticket action off-screen (ADR-0019). The markup stays a real
     table for desktop and assistive technology; only the display changes, and
     flex wrapping means no cell can sit outside the viewport however long a
     station name or fare code is. */
  /* 44rem, not 40: measured, the six-column table needs ~700px before its three
     row actions stop wrapping onto a second line, so the stacked layout keeps
     the band between 640 and 704px that the table cannot hold. */
  @media (max-width: 44rem) {
    body { padding: 1rem .75rem; }
    table, tbody { display: block; }
    thead { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden;
             clip-path: inset(50%); white-space:nowrap; border:0; }
    tr { display: flex; flex-wrap: wrap; align-items: baseline; gap: .1rem .75rem;
         padding: .5rem 0; border-bottom: 1px solid var(--line); }
    td[data-label]::before { content: attr(data-label) " "; color: var(--muted); font-size: .78rem;
                             text-transform: uppercase; letter-spacing: .04em; }
    td:first-child { flex: 1 1 100%; padding-left: 0; }
    td.num { text-align: left; }
    /* On a phone the numbers and the fare type share the line under the
       destination, and the actions take the line below them: `margin-left:
       auto` pushed them to the right edge, which is where the thumb is, and
       where a stray tap buys a ticket. */
    td:last-child { margin-left: 0; }
    tr.detail td { flex: 1 1 100%; padding: .5rem 0; }
  }
"""


# The asset's bytes: the shared block, then this route's own rules, which is
# exactly what the <style> element used to hold.
STATION_STYLESHEET = SHARED_CSS + STATION_CSS

_PRIVACY_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
__SHARED_THEME__
<title>Privacy</title>
<style>
__SHARED_CSS__
  /* C30: a policy page is read, not skimmed past. The shared --h1 scales to
     6rem for the pages whose heading is the question a reader came to answer;
     here it is sized for a document title, and the brand line that used to sit
     above it is gone -- a small uppercase eyebrow above a large heading reads
     as a marketing hero and competes with the document's own title. The same
     argument is why the chooser no longer carries one. */
  :root { --h1: 2rem; --page-max: 42rem; }
  h1 { margin: 0 0 1rem; }
  h2 { font-size: 1.15rem; }
</style>
</head>
<body data-synthetic="__SYNTHETIC__">
__SYNTHETIC_BANNER__
<nav class="back-link"><a href="__BASE__/">Back to the station chooser</a></nav>
__THEME_TOGGLE__
<main>
<h1>Privacy</h1>
<p>This page works entirely in your browser. There is no account, no sign-in, and nothing you choose is stored on a server by this site.</p>
<h2>What stays in the address bar</h2>
<p>A fare page keeps your search in the web address, so that a refresh, the Back button, or a link you share all return the same results. That search &mdash; the budget, the ticket type, whether the budget covers one adult or two, the destination types you selected, and any places you shortlisted &mdash; is written into the page's own address as short query parameters. It is never sent to this site, because this site has no server to receive it. It does leave your device in two ways that are worth naming plainly:</p>
<ul>
<li>the host serving these static files sees the full address, including that search, in its ordinary request logs; and</li>
<li>if you share or bookmark such an address, the whole search travels with it, so a shortlist you share carries your budget and party size to whoever opens the link.</li>
</ul>
<p>Nothing else you type here is transmitted. Clearing the address bar's query parameters and reloading returns a fare page to its default search.</p>
<h2>What this site does</h2>
<ul>
__PRACTICES__</ul>
<h2>Ticket links</h2>
<p>Ticket buttons open the seller's own website in a new tab. Once you are there, that seller's privacy policy applies, not this page. This site receives no information back about whether you bought anything; if tracked links are ever switched on, the footer of the fare pages says so plainly.</p>
<h2>Hosting</h2>
<p>The site is static files served by the operator's chosen host. That host may process ordinary server logs, such as an IP address and requested pages, under its own privacy and retention policy. The site code itself does not set cookies or intentionally collect visit data.</p>
<h2>Contact</h2>
<p class="muted">__CONTACT__</p>
</main>
<footer>
<p class="muted">__NOTE__</p>
<nav class="footnav"><a href="__BASE__/">All stations</a></nav>
</footer>
</body>
</html>
"""



_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
__SHARED_THEME__
<title>Train fares up to &pound;__BUDGET__ from __ORIGIN__</title>
__STATION_STYLE__
</head>
<body data-synthetic="__SYNTHETIC__">
__SYNTHETIC_BANNER__
__THEME_TOGGLE__
<main>
<h1 id="pageHeading"><span class="heading-slot">Train fares up to <span class="heading-field" id="budgetField"><span class="budget-prefix">&pound;</span><input id="budgetNumber" type="number" min="1" max="__MAXPOUNDS__" step="1" value="__BUDGET__" inputmode="numeric" aria-label="Budget in pounds"></span></span><br><span class="heading-lead">from</span> __ORIGIN_CONTROL__</h1>
<!-- C04: the opening sentence is written by renderIntro() once the build has
     said whether a timetable was loaded. The static text below is the
     fares-only sentence, because that is the one that cannot overstate what a
     prices-only build shows; a build with a timetable replaces it.

     The first-use note is the second half of the same paragraph rather than a
     paragraph of its own. It answers one question -- what the station name in
     the heading does -- and a reader who has not clicked it should be able to
     read that answer and the page's promise in one go, not in two blocks with a
     line's gap between them. Two elements, because the build writes the second
     one per build and the first one is written by script, and a reader cannot
     tell where the sentence ended. -->
<p class="sub" id="pageIntro">Every destination this feed prices from the station above, inside the budget.<span id="firstUse"> __FIRST_USE__</span></p>
<!-- The list, not the field. The field is moved into the heading by the
     script, into the place the station's own name was, so that clicking the
     name and typing are the same gesture in the same place -- and the list
     opens directly under it, because a reader who has just clicked a word
     looks at that word and not two paragraphs further down. -->
<div id="originPicker" hidden>
  <p class="origin-picker-label" id="originPicksLabel">Every station on this site</p>
  <ul id="originPicks" aria-labelledby="originPicksLabel"></ul>
  <p id="originNomatch" hidden></p>
  <span id="originStatus" class="sr-only" role="status"></span>
</div>
<!-- ADR-0047: shown only when the stylesheet did not arrive. The page is
     plain text in that state, and says so rather than leaving a reader to
     wonder why this station looks unlike every other one. -->
<p class="sub" id="styleNote" hidden></p>
<p id="unpriced" class="unpriced" hidden></p>

<section class="filter-bar" aria-label="Journey and destination filters">
  <fieldset class="budget-track">
    <legend class="sr-only">Budget</legend>
    <label class="sr-only" for="budget">Budget in pounds</label>
    <input id="budget" type="range" min="1" max="__MAXPOUNDS__" step="1" value="__BUDGET__" aria-describedby="budgetHint">
    <span class="tag" id="budgetHint">Drag to change the budget in the heading. It stops at the highest fare in the ticket type you are looking at — <span id="budgetCeiling">__CEILING_NOTE__</span>.</span>
  </fieldset>
  <div class="more-filters" id="moreFilters" data-open="false">
    <button type="button" class="more-filters-toggle" id="moreFiltersToggle"
            aria-expanded="false" aria-controls="moreFiltersPanel">
      <span class="more-filters-label">Narrow this list</span>
      <span class="tag" id="filterState"></span>
      __CHEVRON__
    </button>
    <div class="more-filters-panel" id="moreFiltersPanel">
  <fieldset class="ticket-filter">
    <legend>Ticket type</legend>
    <div class="filter-options segmented">
      <label><input type="radio" name="ticketMode" value="cheapest" checked> Cheapest of any type</label>
      <label><input type="radio" name="ticketMode" value="anytime"> Anytime Day Return</label>
      <label><input type="radio" name="ticketMode" value="return"> Any return</label>
      <label><input type="radio" name="ticketMode" value="single"> Single</label>
    </div>
  </fieldset>
  <fieldset class="party-filter">
    <legend>The budget covers</legend>
    <div class="filter-options">
      <label class="railcard-choice"><input type="radio" name="unit" value="adult" checked> One adult</label>
      <label class="railcard-choice"><input type="radio" name="unit" value="party"> Two adults</label>
    </div>
    <!-- Q2: a railcard is one of a collection the reader picks from, and the
         default is none. The browser remembers the choice, so a reader who
         holds a card names it once rather than on every page. The options are
         written by script from the payload, so the control can never offer a
         card this feed did not price. -->
    <div class="filter-options">
      <label class="railcard-choice" id="railcardChoice" for="railcardSelect">Railcard</label>
      <select id="railcardSelect" name="railcard" aria-describedby="railcardHelp"></select>
    </div>
    <span class="railcard-help" id="railcardHelp">No railcard selected, so these are standard fares.</span>
  </fieldset>
  <fieldset class="destination-filter">
    <legend>Destination type</legend>
    <div class="filter-options" id="destinationTypes" role="group" aria-label="Destination type">__DESTINATION_TYPE_FILTERS__</div>
  <span class="tag" id="typeRule">More than one type shows destinations of any of them. The count on each is how many are inside the budget now.</span>
  <p id="facetNotice" class="tag" role="status" hidden></p>
  <button id="clearTypes" class="toggle" type="button" hidden>Clear destination types</button>
  </fieldset>
    </div>
  </div>
</section>

<p class="tag" id="modeNote"></p>
<!-- The one provenance line that stays above the table: how old the numbers
     are. Everything else about where they came from is reference material and
     sits under the table with the rest of it, where a reader goes when they
     have decided to check rather than before they have decided to read. -->
<p class="tag" id="freshness" hidden></p>
  <!-- C03, as ADR-0040 leaves it: what the ticket action costs is still
       stated above the first ticket action, because the line a reader sees is
       the fold's own summary and it names both what the link does and, when
       the links are tracked, that this site is paid. Only the wording waits.
       These two paragraphs plus the build line were 57px of the 205px between
       the count and the table on the real page (finding, 29 September 2026). -->
  <details class="link-terms" id="linkTerms">
    <summary id="linkTermsSummary">About the ticket link</summary>
    <p class="tag" id="linkNote" hidden></p>
    <p class="tag" id="disclosure" hidden></p>
  </details>
<!-- S26: the shortlist is one control and one strip, above the table. It was a
     named button on every row, so twenty rows carried twenty copies of the
     same word; pressing one changed the button's own text and reflowed the
     table, and the confirmation was a list below the fold the reader had to
     scroll to find. A reader who has just chosen a place is looking at the
     place, not at the foot of the page, so the list is drawn where the action
     is.

     It sits above the count line rather than between the count and the table,
     because the count describes the rows under it and the two were 89px apart
     with a row of controls in the gap. The reader chooses a place, then reads
     what the list beneath them contains. -->
<section class="shortlist-bar" id="shortlistBar" aria-label="Shortlist" hidden>
  <div class="shortlist-controls">
    <label class="shortlist-label" for="shortlistPick">Shortlist</label>
    <select id="shortlistPick"></select>
    <button id="shortlistCopy" class="toggle" type="button" hidden>Copy</button>
    <button id="shortlistClear" class="toggle" type="button" hidden>Clear</button>
  </div>
  <ul id="shortlistList" class="shortlist-chips"></ul>
  <p id="shortlistEmpty" class="tag">Nothing held yet. It is a list to compare and share, not a booking.</p>
  <p id="shortlistLimit" class="tag" role="status"></p>
  <details class="shortlist-share" id="shortlistShareBox" hidden>
    <summary>Share this shortlist</summary>
    <p id="shortlistShare" class="tag"></p>
    <textarea id="shortlistBox" class="copybox" rows="6" readonly hidden aria-label="Shortlist to copy"></textarea>
  </details>
  <span id="shortlistStatus" role="status" class="sr-only"></span>
</section>
<!-- The count line belongs to the table below it, not to the panel above: on
     the real Grantham page it sat 205px above the first row, with six
     provenance paragraphs between them (finding, 29 September 2026). -->
<p id="summary" role="status" aria-live="polite"></p>
<table>
  <thead><tr><th scope="col">Station</th><th scope="col" class="num">Price</th><th scope="col" class="num">Time</th><th scope="col" class="num">Changes</th><th scope="col">Fare type</th><th scope="col">Tickets</th></tr></thead>
  <tbody id="rows"></tbody>
</table>
<div id="empty" hidden></div>
<p id="more" hidden></p>
<nav id="pagination" hidden aria-label="Results pages">
  <button id="previousPage" type="button" class="toggle">Previous</button>
  <span id="pageStatus" role="status"></span>
  <button id="nextPage" type="button" class="toggle">Next</button>
</nav>

</main>

<footer>
  __NRE_CREDIT__
  <div id="attribution" hidden></div>
  <p>__NOTE__</p>
  <p>Cheapest displayable standard-class fare found in the feed for the selected ticket type, and on the list this page opens in the cheapest fare of any ticket type for each destination. ITX placeholder fares are excluded. Advance singles are shown when they are the cheapest single, but they require a qualifying train and their price and availability can change.</p>
  <p>The times on this page are options in the timetable, not a booking. Unrestricted fares are valid on the services listed; an Advance single is valid only on a qualifying train, so no train is picked for you.</p>
  <!-- Everything the page knows about where its numbers came from, in the one
       place a reader goes to check them. These four lines stood between the
       budget control and the first fare on every station page: the feed's
       name and download date, the second opinion on the ticket conditions, the
       build's own stamp, and -- when a build read an undated timetable -- the
       caveat that every schedule in the feed was read. They are not deleted and
       they are not shortened; they are below the results, which is where the
       primary asset is not competing with them for the fold. -->
  <details class="method">
    <summary>Where these prices come from, and how they were calculated</summary>
    <p id="pricingBasis"></p>
    <p id="feedCoverage" class="tag"></p>
    <p id="railcardNote"></p>
    <p class="tag" id="priceSource" hidden></p>
    <p class="tag" id="restrictionReference" hidden></p>
    <p class="tag" id="buildMetadata" hidden></p>
    <p class="tag" id="provenance"></p>
  </details>
  <nav class="footnav"><a href="__BASE__/">All stations</a> <a href="__BASE__/privacy/">Privacy</a></nav>
  <p id="copyStatus" role="status" class="sr-only"></p>
</footer>

__STATIONS_SRC__<script>
__LIST_KEYS__
const DATA = __DATA__;
const FIRST_USE_FALLBACK = __FIRST_USE_FALLBACK__;
// Each row list arrives as a column list and a table of cells, because every row
// in a list carried the same field names and the page was sending them once per
// row. Hydrating here keeps the rest of this script reading rows as objects, and
// it is also what makes an older payload -- a plain list -- still render.
function hydrate(table) {
  if (!table || !Array.isArray(table.rows)) return table || [];
  const pool = DATA.pool || [];
  return table.rows.map((cells) => {
    const row = {};
    for (let i = 0; i < table.columns.length; i += 1) {
      const cell = cells[i];
      // A negative cell is an index into the page's pool of values that repeat,
      // so the rows that share a link or a railcard record share one object.
      row[table.columns[i]] = typeof cell === "number" && cell < 0 ? pool[-cell - 1] : cell;
    }
    return row;
  });
}
for (const key of ["destinations", "singleDestinations", "anytimeDestinations", "stations"]) {
  DATA[key] = hydrate(DATA[key]);
}
// ADR-0033 is re-scoped for the picker: its list is one file the site
// serves once, because the same list on every page was the release's
// largest repeated item (audit, 30 September 2026). The page's own
// destinations still travel in it, and nothing else breaks when this
// request does not arrive -- the branch under the picker says what the
// page is instead of offering a control that opens nothing.
if (window.TBE_STATIONS) {
  DATA.stations = window.TBE_STATIONS.filter(
    (station) => !DATA.origin || station.crs !== DATA.origin.crs
  );
}
const rows = document.getElementById("rows");
const budget = document.getElementById("budget");const budgetNumber = document.getElementById("budgetNumber");const budgetCeilingNote = document.getElementById("budgetCeiling");
const budgetField = document.getElementById("budgetField");
// Q2: the railcard is a select over the reviewed collection rather than one
// checkbox for one card. Its options are written from the payload below, so the
// control can only ever offer a card this build priced.
const railcardSelect = document.getElementById("railcardSelect");
const railcardChoice = document.getElementById("railcardChoice");
// The browser remembers the reader's card between pages. The key is
// per-origin because a reader from one station is answering the same question
// as a reader from another, and a stored card must not travel to a page whose
// feed priced nothing for it.
const RAILCARD_MEMORY = "tbe.railcard.";
let rememberedCard = null;
try {
  rememberedCard = window.localStorage.getItem(RAILCARD_MEMORY + DATA.origin.crs);
} catch (error) {
  // A browser with storage blocked still gets the control; it just asks again.
  rememberedCard = null;
}

// The collection the page offers, keyed by the code the feed priced it under.
const railcards = (DATA.railcards || []).reduce((all, card) => {
  all[card.key] = card;
  return all;
}, {});
const railcardKeys = Object.keys(railcards);
const noCard = () => railcardSelect.value === "";

// The options are written from the payload, so the control lists the cards this
// build actually priced and nothing else. This runs before the address is read
// (ADR-0052): a card named in a shared link is applied to a select that already
// has an option for it, and a card this feed does not price is dropped rather
// than read as one the reader holds.
if (railcardKeys.length) {
  const none = document.createElement("option");
  none.value = "";
  none.textContent = "No railcard";
  railcardSelect.append(none);
  for (const key of railcardKeys) {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = railcards[key].label;
    railcardSelect.append(option);
  }
  // A remembered card is applied only when this page prices it, so a reader who
  // chose a card on a page that offered it is not silently moved onto a
  // different card where it is absent.
  if (rememberedCard && railcardSelect.querySelector('option[value="' + rememberedCard + '"]')) {
    railcardSelect.value = rememberedCard;
  }
}

// The party a chosen card covers, from the feed's own records for it. A card
// that needs two travellers cannot price one reader's journey, and the page says
// so rather than offering a number nobody could buy.
function cardCoversParty(card) {
  const adults = unit() === "party" ? 2 : 1;
  return card.minAdults <= adults && adults <= card.maxAdults;
}
const summary = document.getElementById("summary");
const empty = document.getElementById("empty");
const more = document.getElementById("more");
const destinationTypeInputs = Array.from(document.querySelectorAll('input[name="destinationType"]'));
const destinationType = document.getElementById("destinationTypes");
const PAGE_SIZE = 20;
let currentPage = 1;
const pagination = document.getElementById("pagination");
const previousPage = document.getElementById("previousPage");
const nextPage = document.getElementById("nextPage");
const pageStatus = document.getElementById("pageStatus");
const clearTypes = document.getElementById("clearTypes");
const moreFilters = document.getElementById("moreFilters");
const moreFiltersToggle = document.getElementById("moreFiltersToggle");
const filterState = document.getElementById("filterState");  // The refinements are folded at every width, and the reader is the only thing
  // that opens them. The control is a button carrying aria-expanded, so the
  // state is announced without any of this: the markup opens folded and this
  // only flips that. There used to be a second road in -- a media query and a
  // resize listener that opened the panel above the phone breakpoint and closed
  // it below -- which meant the state a reader had chosen could be overwritten
  // by rotating a device, and meant the fold was a different thing at each
  // width. Both are gone: one control, one state, one place it changes.
  function setFiltersOpen(open) {
    if (!moreFilters) return;
    moreFilters.dataset.open = open ? "true" : "false";
    if (moreFiltersToggle) moreFiltersToggle.setAttribute("aria-expanded", open ? "true" : "false");
  }
  if (moreFiltersToggle) moreFiltersToggle.addEventListener("click", () => {
    setFiltersOpen(moreFilters.dataset.open !== "true");
  });

// What is narrowed, said in the summary, so a reader who has collapsed the
// refinements on a phone can still see that a filter is on.
function filterStateText() {
  // selectedDestinationTypes() is a Set, and the chip's own label is the only
  // wording a reader has seen for it.
  const types = Array.from(selectedDestinationTypes());
  const party = unit() === "party" ? "Two adults" : "One adult";
  const card = noCard() || !railcards[railcardSelect.value] ? "" : " + " + railcards[railcardSelect.value].label;
  const labelOf = (value) => {
    const input = document.querySelector(`input[name="destinationType"][value="${value}"]`);
    const span = input && input.parentElement ? input.parentElement.querySelector("span") : null;
    return span ? span.textContent : value;
  };
  const typeText = types.length ? types.map(labelOf).join(", ") : "all types";
  return modeLabels()[ticketMode()] + " \u00b7 " + party + card + " \u00b7 " + typeText;
}
function renderFilterState() {
  if (filterState) filterState.textContent = filterStateText();
}

function matches(station, needle) {
  if (!needle) return true;
  return station.name.toLowerCase().includes(needle) ||
    station.crs.toLowerCase().startsWith(needle);
}

function ticketMode() {
  return document.querySelector('input[name="ticketMode"]:checked').value;
}
// One place that knows which payload list each ticket mode shows, so the
// count in a message cannot drift from the list the table is built from.
const MODE_LISTS = {
  return: "destinations",
  single: "singleDestinations",
  anytime: "anytimeDestinations",
};
// Q4 (ADR-0044): the page opens on the cheapest fare
// of any ticket type, because "where can I get to for this much" is the
// question the reader arrived with, and a list of one ticket type answers it
// with a number that is often not the fare they can buy. The three named sets
// above stay, as the filters for a reader who wants one kind of fare.
//
// The list is composed here rather than in the build, so it costs no payload
// bytes -- and because which row is cheapest depends on who the price is for,
// it is composed for the party size and the card on screen rather than once.
const CHEAPEST_MODE = "cheapest";
function cheapestDestinations() {
  const cheapest = new Map();
  for (const key of Object.values(MODE_LISTS)) {
    for (const destination of DATA[key] || []) {
      const held = cheapest.get(destination.crs);
      if (!held || priceOf(destination) < priceOf(held)) cheapest.set(destination.crs, destination);
    }
  }
  return Array.from(cheapest.values());
}
function activeDestinations() {
  const mode = ticketMode();
  if (mode === CHEAPEST_MODE) return cheapestDestinations();
  return DATA[MODE_LISTS[mode]] || [];
}
function modeCount(mode) {
  if (mode === CHEAPEST_MODE) return cheapestDestinations().length;
  return (DATA[MODE_LISTS[mode]] || []).length;
}
// The fare a row is priced as, in the words the build's own price-quality
// phrases use. The cheapest list holds one fare per place, so this is what
// names the ticket on a row the reader chose by price rather than by type.
function ticketName(destination) {
  if (destination.isAdvance) return "Advance single";
  if (destination.quality === "unrestricted Anytime Day Return") return "Unrestricted Anytime Day Return";
  if (destination.quality === "outbound single") return "Standard outbound single";
  return "Standard return";
}
// The fare a price belongs to, for everywhere a price is carried off the
// page: the shortlist, the copied shortlist, and a row's own handoff. The
// cheapest list holds one fare per place and can hold a different fare on
// every row, so it names the ticket on the row; a named list holds one kind
// of fare, so it names the list. One helper rather than the same decision
// written three times, because the count line already names the mix of the
// cheapest list (mixPhrase) and a shortlist that named a different fare from
// the count line beside it would be the page disagreeing with itself.
function fareName(destination) {
  return ticketMode() === CHEAPEST_MODE ? ticketName(destination) : modeLabels()[ticketMode()];
}
// The mix of ticket types in a list, for the count line. A list of one kind is
// the case this exists for rather than the case it stays quiet about: on the
// real Grantham page every one of the 101 opening rows is a single, and "cheapest
// first" beside a control named "Cheapest of any type" does not tell a reader
// why no return is on the page.
const MIX_WORDS = {
  "outbound single": "single",
  "unrestricted Anytime Day Return": "Anytime Day Return",
};
function mixPhrase(destinations) {
  const counts = new Map();
  for (const destination of destinations) {
    const word = MIX_WORDS[destination.quality] || "return";
    counts.set(word, (counts.get(word) || 0) + 1);
  }
  if (!counts.size) return "";
  return ": " + listWords(Array.from(counts.entries()).map(
    ([word, count]) => count + " " + (count === 1 ? word : word + "s")));
}
function budgetCeiling() {
  // The ceiling is the most the reader can be asked to consider, and the price
  // on a row depends on who it covers: two adults cost twice one. A ceiling set
  // by the single fare is therefore a budget nobody reading the party price
  // could ever type -- on a page with one destination it caps the budget at that
  // destination's adult fare, and the "Two adults" control then shows nothing at
  // any budget the page allows. Found by sweeping a published two-station site.
  //
  // The railcard is left out on purpose: it makes prices lower, so including it
  // would move the ceiling down the moment the box was ticked, clamping a
  // budget the reader had already chosen.
  const party = unit() === "party";
  return Math.max(1, Math.ceil(Math.max(0, ...activeDestinations().map((d) => (party ? d.partyPence : d.adultPence))) / 100));
}

// A prices-only build has no times to show, and two columns of dashes are
// noise where a shorter table is honest: the columns stand down entirely.
if (!DATA.hasJourneys) {
  for (const th of document.querySelectorAll("thead th:nth-child(3), thead th:nth-child(4)")) th.remove();
}
const columnCount = () => document.querySelectorAll("thead th").length;

// Prices are always two decimal places. The pound sign lines up down the
// column, which is the whole point of a price-first list, and £8.70 is easier
// to compare with £8.65 than £8.70 is with £9.
const money = (pence) => "\u00a3" + (pence / 100).toFixed(2);
const duration = (minutes) => {
  if (minutes === null || minutes === undefined) return "-";
  const hours = Math.floor(minutes / 60);
  return hours ? hours + "h " + String(minutes % 60).padStart(2, "0") + "m" : minutes + "m";
};
const clock = (minutes) => {
  const hour = Math.floor(minutes / 60) % 24;
  return String(hour).padStart(2, "0") + ":" + String(minutes % 60).padStart(2, "0");
};

function unit() {
  return document.querySelector('input[name="unit"]:checked').value;
}
function priceOf(destination) {
  const party = unit() === "party";
  const base = party ? destination.partyPence : destination.adultPence;
  const card = chosenCard(destination);
  if (card) {
    const cardTotal = card.pricePence * (party ? 2 : 1);
    return Math.min(base, cardTotal);
  }
  return base;
}
// The chosen card's decision for one row, or null when none is chosen, this
// row cannot price it, or the card does not cover the party on screen. A card
// the feed blocked for a fare has no price and is not offered as one.
function chosenCard(destination) {
  if (noCard()) return null;
  const card = destination.railcards && destination.railcards[railcardSelect.value];
  if (!card || card.pricePence === null || card.pricePence === undefined) return null;
  const chosen = railcards[railcardSelect.value];
  return chosen && cardCoversParty(chosen) ? card : null;
}
// Q3: with the card ticked the cell shows what the reader would pay *and* the
// standard fare it came from, so a discounted number never stands alone. With
// the box clear there is one price and no second number, because there is one
// price.
function priceCell(destination) {
  const cell = document.createElement("td");
  cell.className = "num";
  cell.dataset.label = "Price";
  const party = unit() === "party";
  const standard = party ? destination.partyPence : destination.adultPence;
  const price = priceOf(destination);
  const amount = document.createElement("span");
  amount.className = "price";
  amount.textContent = money(price);
  cell.append(amount);
  if (price < standard) {
    const was = document.createElement("span");
    was.className = "was";
    was.textContent = " " + money(standard) + " standard";
    cell.append(was);
  }
  return cell;
}
// S15: a railcard covers a named number of adults travelling together, so it
// is a constraint on the party rather than a discount a solo reader can tick.
// The number is the feed's own record for each card rather than a rule this
// page invented, and a card that cannot cover the party on screen is taken out
// of the list rather than left there to be picked and then ignored.
function syncRailcardParty() {
  const help = document.getElementById("railcardHelp");
  if (!railcardKeys.length) {
    // The sentence stays and says why: "standard fares" with no explanation is
    // the claim the whole page rests on, and a reader who owns a 16-25 card is
    // owed the reason their card is not in the list.
    if (help) {
      help.textContent = "This feed prices no reviewed railcard, so these are standard fares.";
      help.hidden = false;
    }
    if (railcardChoice) railcardChoice.hidden = true;
    railcardSelect.disabled = true;
    return;
  }
  if (railcardChoice) railcardChoice.hidden = false;
  // A card that cannot price the party on screen is removed from the list
  // rather than left there to be picked and then ignored. The feed's own
  // records decide, so the page is not inventing a rule about who travels.
  //
  // The list is rebuilt rather than filtered in place, because the party
  // control and the card control are two answers to one question and the second
  // has to follow the first. The earlier version computed the offered list and
  // then left the options alone, so a party of two was still offered a card the
  // feed says prices one traveller; the browser suite found it by asking which
  // options a party of two can see.
  const offered = railcardKeys.filter((key) => cardCoversParty(railcards[key]));
  const wanted = railcardSelect.value;
  railcardSelect.replaceChildren();
  const none = document.createElement("option");
  none.value = "";
  none.textContent = "No railcard";
  railcardSelect.append(none);
  for (const key of offered) {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = railcards[key].label;
    railcardSelect.append(option);
  }
  // The reader's choice survives the rebuild when the party on screen still
  // allows it, and is cleared when it does not.
  railcardSelect.value = offered.includes(wanted) ? wanted : "";
  railcardSelect.disabled = offered.length === 0;
  if (!help) return;
  if (noCard()) {
    help.textContent = "No railcard selected, so these are standard fares. Choose the card you " +
      "hold to price the journey with it; this browser will remember your choice.";
    return;
  }
  const chosen = railcards[railcardSelect.value];
  const covers = "The " + chosen.label + " in this feed covers " + chosen.minAdults + " to " +
    chosen.maxAdults + " adults";
  help.textContent = covers + ", which matches the party on screen. " + chosen.eligibleCount +
    " destinations receive a lower price with it; open a row's own details for the minimum " +
    "fare and the conditions the feed applies.";
}

function selectedDestinationTypes() {
  return new Set(destinationTypeInputs
    .filter((input) => input.value !== "all" && input.checked)
    .map((input) => input.value));
}
function matchesType(destination, wantedTypes) {
  if (wantedTypes.size === 0) return true;
  const types = destination.destinationTypes || [destination.destinationType];
  return types.some((type) => wantedTypes.has(type));
}
function typeLabel() {
  const labels = destinationTypeInputs
    .filter((input) => input.value !== "all" && input.checked)
    .map((input) => input.parentElement.textContent.trim().toLowerCase());
  // "or", not "and": two selected types show the union, and a message that
  // said "and" would describe a filter the page does not apply.
  return labels.length > 1 ? " in " + labels.join(" or ") : labels.length ? " in " + labels[0] : "";
}

// S20: how many of the destinations in the list the reader is looking at are
// inside the budget and carry this type. A chip that can only ever return
// nothing is a broken control; a chip that says it would return nothing is a
// decision the reader gets to make.
function updateChipCounts(available, cap) {
  for (const input of destinationTypeInputs) {
    if (input.value === "all") continue;
    const slot = document.querySelector(`.chipcount[data-count-for="${input.value}"]`);
    if (!slot) continue;
    const count = available.filter(
      (destination) => priceOf(destination) <= cap &&
        (destination.destinationTypes || [destination.destinationType]).includes(input.value)
    ).length;
    slot.textContent = count === 1 ? "(1)" : "(" + count + ")";
  }
  const clear = document.getElementById("clearTypes");
  if (clear) clear.hidden = selectedDestinationTypes().size === 0;
}
function clearDestinationTypes() {
  for (const input of destinationTypeInputs) input.checked = input.value === "all";
  currentPage = 1;
  render();
  writeUrl();
}
function sizeBudgetField() {
  const digits = Math.max(1, String(budgetNumber.value || "1").length);
  budgetNumber.style.width = digits + "ch";
}
function setBudget(value) {
  const safe = Math.max(1, Math.min(Number(budget.max) || 1, Number(value) || 1));
  budget.value = String(safe);
  budgetNumber.value = String(safe);
  sizeBudgetField();
  return safe;
}
function stationInFeedMessage(station) {
  return station.name + " (" + station.crs + ") is in the feed, but this origin has no qualifying " +
    "return or single fare flow to it in this download.";
}
// A chip is offered when a destination in the list the reader is looking at
// carries it. The build offers one from the union of the three ticket modes,
// because it cannot know which a reader will pick, and a chip that can only
// ever return nothing reads as a broken control: on the real Grantham page every
// heritage destination was an outbound single, so return mode offered a
// heritage chip that filtered to no rows at all. So the chips are narrowed to
// the active list, and a chip that disappears takes its selection with it --
// a hidden chip left checked keeps filtering with nothing to show for it.
function syncDestinationTypeChips() {
  const offered = new Set();
  for (const destination of activeDestinations()) {
    for (const type of destination.destinationTypes || [destination.destinationType || "other"]) {
      offered.add(type);
    }
  }
  // C20: a facet present in only one ticket mode used to be silently unchecked
  // when the mode changed, so switching back to the mode the reader had chosen
  // it in showed "All" and no explanation. Each mode now keeps its own
  // selection, and switching restores it, so intent survives the round trip.
  const mode = ticketMode();
  // syncDestinationTypeChips() runs on every render, not only on a mode
  // change, so "the mode changed" is decided once here and the announcement
  // below is tied to it. Without this the same message would be re-announced
  // on every budget drag.
  const modeChanged = lastSyncedMode !== null && lastSyncedMode !== mode;
  if (modeChanged) {
    typeSelectionsByMode[lastSyncedMode] = Array.from(selectedDestinationTypes());
  }
  const all = destinationTypeInputs.find((input) => input.value === "all");
  const dropped = [];
  for (const input of destinationTypeInputs) {
    if (input.value === "all") continue;
    const present = offered.has(input.value);
    const chip = input.closest("label");
    if (chip) chip.hidden = !present;
    if (!present && input.checked) {
      input.checked = false;
      dropped.push(chipLabel(input.value));
    }
  }
  // Restore what the reader chose the last time they were in this mode, minus
  // anything this mode cannot offer. A mode reached for the first time keeps
  // whatever the reader has selected now, which is what the previous behaviour
  // did too.
  const remembered = typeSelectionsByMode[mode];
  const restored = [];
  if (modeChanged && remembered && remembered.length) {
    let anyRestored = false;
    for (const input of destinationTypeInputs) {
      if (input.value === "all") continue;
      const wanted = remembered.includes(input.value) && offered.has(input.value);
      if (wanted) { input.checked = true; anyRestored = true; restored.push(chipLabel(input.value)); }
    }
    if (anyRestored && all) all.checked = false;
  }
  if (!all || !all.checked) {
    const selected = destinationTypeInputs.some(
      (input) => input.value !== "all" && input.checked);
    if (!selected && all) all.checked = true;
  }
  lastSyncedMode = mode;
  if (modeChanged) announceFacetChange(dropped, restored, mode);
}
const typeSelectionsByMode = Object.create(null);
let lastSyncedMode = null;
function chipLabel(value) {
  const input = document.querySelector(`input[name="destinationType"][value="${value}"]`);
  const chip = input ? input.closest("label") : null;
  return chip ? chip.textContent.replace(/\\(\\d+\\)/, "").trim() : value;
}
// A filter that changed the result set without saying so is indistinguishable
// from a broken one, so what happened is stated next to the chips and pushed to
// assistive technology through the live region it is already in.
function announceFacetChange(dropped, restored, mode) {
  const notice = document.getElementById("facetNotice");
  if (!notice) return;
  const modeName = modeLabels()[mode] || "this ticket type";
  const parts = [];
  if (dropped.length) {
    parts.push("Cleared " + listWords(dropped) + " — " + modeName +
      " has no destination of " + (dropped.length === 1 ? "that type" : "those types") +
      " from this station.");
  }
  if (restored.length) {
    parts.push("Restored your " + listWords(restored) + " filter from " + modeName + ".");
  }
  notice.textContent = parts.join(" ");
  notice.hidden = !parts.length;
}
function listWords(items) {
  return items.length > 1 ? items.join(", ") : items[0] || "";
}

// A mode can be empty while other modes are not. An Anytime Day Return is sold
// on a handful of interurban routes, so most origins have none, and the page
// used to return early and leave the reader looking at the previous mode's
// rows with every destination-type chip hidden -- which reads as a broken
// control, not as an answer. So an empty mode now says so, clears the table,
// and says where the fares this origin does have are.
function modeLabels() {
  const labels = {};
  for (const input of document.querySelectorAll('input[name="ticketMode"]')) {
    labels[input.value] = input.parentElement.textContent.trim();
  }
  return labels;
}
const MODE_WHY = {
  anytime: "An Anytime Day Return is valid on any train, so sellers offer it on only some routes and most stations have none.",
};
// C07: a reader has to be told what the open set contains *before* they
// compare two numbers in it, so the note sits above the table rather than
// inside the methodology accordion, and is read at the moment the comparison
// is made. Q4 then changed which set is open: the page opens on the cheapest
// fare of any type, whose caveats are the mix itself and the advance single
// inside it, and the reviewed set this note was written for is now one of the
// filters beside it. The wider "any return" set is offered for the same reason
// it always was -- a restricted off-peak fare is a real price a reader can buy
// -- and whichever set is open, a restricted fare is not interchangeable with
// an unrestricted one, and the page cannot decode the feed's own validity text.
const MODE_NOTE = {
  cheapest: "Each row is the cheapest fare of any ticket type, so this list mixes singles and returns. An advance fare needs a chosen train; a restricted fare's condition is in the row's details.",
  anytime: "Unrestricted Anytime Day Returns: valid on any train on the route, so these prices compare with each other directly.",
  return: "Every standard-class return the feed prices, restricted off-peak and advance included. A restricted fare is not valid on every train or at every time \u2014 its condition is in the row's details.",
  single: "Outbound singles rather than returns. An advance single needs a chosen train, and is labelled where it appears.",
};
function renderModeNote() {
  const note = document.getElementById("modeNote");
  if (!note) return;
  note.textContent = MODE_NOTE[ticketMode()] || "";
}
function emptyModeMessage() {
  const labels = modeLabels();
  const mode = ticketMode();
  const elsewhere = [CHEAPEST_MODE, "return", "single", "anytime"]
    .filter((other) => other !== mode && modeCount(other))
    .map((other) => labels[other] + " has " + modeCount(other));
  const why = MODE_WHY[mode] ? " " + MODE_WHY[mode] : "";
  const where = elsewhere.length
    ? " " + elsewhere.join(" and ") + (elsewhere.length === 1 ? " destination." : " destinations — switch modes to see them.")
    : "";
  return "No " + labels[mode] + " fares were found from " + DATA.origin.name + " in this download." + why + where;
}
// S28: an empty list is a decision the reader has not finished making, so it
// says which of the choices on this page would change the answer and offers
// each as a control. Every move is offered only when it is true for this
// page's own rows -- a "raise the budget" button on a page where the budget
// already covers everything is a control that does nothing.
// The empty-mode case has one recovery this page can offer -- another ticket
// type that does have fares from here -- and it is the same control as
// everywhere else, so a reader who is offered a move is never offered one that
// does nothing.
// S29: "every destination" is a claim about the feed, so the page counts what
// it dropped and what it cannot classify. A destination whose type is not in
// the reviewed registry is still priced and still listed -- it is simply one no
// type chip can select, and saying so is the difference between a complete
// claim and a true one. Written in one place because the ticket-mode switch
// and the first render both rewrite this line.
// S33: how old the numbers are, beside the numbers. Two ages, because they
// answer different questions: a fare download is a snapshot of prices that
// change without expiring, and a timetable is current for the window it says
// it covers. Both are judged against the reader's own clock, not the build's,
// so a page published in March says in June that it is five months old. A
// build with no timetable says so plainly: that is a choice about what to
// compute, not a feed that has gone stale.
function renderFreshness() {
  const line = document.getElementById("freshness");
  if (!line) return;
  const parts = [];
  // Whole calendar days, not elapsed 24-hour periods: a timetable that starts
  // yesterday has not "not started yet" because it started at ten yesterday
  // morning, and a reader reading this at breakfast should get the same answer
  // as one reading it at midnight.
  const now = new Date();
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  // Positive is in the past, negative is in the future.
  const days = (iso) => Math.round((today - Date.parse(iso + "T00:00:00Z")) / 86400000);
  if (DATA.feedDate) {
    const age = days(DATA.feedDate);
    const limit = DATA.staleAfterDays;
    // A download dated in the future is a clock problem, not a fresh feed, and
    // is named as one rather than counted as negative days old.
    const when = age < 0
      ? "dated after today, so the clock or the download is wrong"
      : age + (age === 1 ? " day" : " days") + " old";
    const verdict = age < 0
      ? ""
      : age <= limit
        ? "within the " + limit + "-day freshness threshold"
        : "past the " + limit + "-day freshness threshold, so check the fare before you travel";
    parts.push("Prices are from a fares feed downloaded " + humanDate(DATA.feedDate) + ", " + when +
      (verdict ? " and " + verdict : "") + ".");
  }
  if (!DATA.timetableFrom) {
    parts.push("This build prices fares only: no timetable was supplied, so no times or changes are shown.");
  } else {
    // days() is today minus the date, so a start still ahead is negative and
    // an end already past is positive.
    const starts = days(DATA.timetableFrom);
    const ends = days(DATA.timetableTo);
    const verdict = starts < 0
      ? "which has not started yet"
      : ends > 0
        ? "which has ended, so these times describe services that no longer run"
        : "which includes today";
    parts.push("Times are from a timetable covering " + humanDate(DATA.timetableFrom) + " to " +
      humanDate(DATA.timetableTo) + ", " + verdict + ".");
  }
  line.textContent = parts.join(" ");
  line.hidden = !parts.length;
}

// The conditions printed in the table are the fares feed's own wording, from
// the same publication as the prices. The reference feed is a second opinion,
// published on its own schedule, and this is the claim the page makes about it.
//
// Every branch says what was compared. "All of them" with nothing behind it
// would be a claim the build never checked, so a check that compared no codes
// is written as not checked, and an unreadable reference feed is written as
// unreadable rather than passed over in silence.
//
// The count is the conditions *the fares in this build can carry*, which is a
// bigger set than the rows on screen and deliberately so. Naming only the codes
// the reader's current budget happens to surface would make the sentence change
// meaning when they drag the slider -- and would leave a fare carrying a
// retired condition unremarked, because the page cannot know a budget the
// reader has not chosen yet. Taken from the flows, the set holds at every
// budget, party and ticket mode, so a reader who later sees one of these
// conditions was warned before they saw it.
function renderRestrictionReference() {
  const line = document.getElementById("restrictionReference");
  if (!line) return;
  const ref = DATA.restrictionReference;
  if (!ref) { line.hidden = true; return; }
  // Every date is written through dayPhrase, which returns "" for a date it
  // cannot read. A clause is then built by concatenation, so a missing date
  // removes the clause rather than printing a broken one.
  const published = dayPhrase(ref.published);
  const checked = ref.checkedAt ? dayPhrase(ref.checkedAt) : "";
  const checkedClause = checked ? ", last checked" + checked : "";
  const text = (() => {
    if (ref.status === "absent") {
      return "Ticket conditions are quoted from the fares feed. No portal reference feed was checked.";
    }
    if (ref.status === "unknown") {
      return "Ticket conditions are quoted from the fares feed. The portal's own restriction feed could not be checked"
        + (ref.note ? " (" + ref.note + ")" : "")
        + ", so nothing here has been confirmed against it"
        + (published ? "; it was published" + published : "") + ".";
    }
    if (ref.status === "unpublished") {
      const codes = (ref.unlisted || []).join(", ");
      // The comma belongs to the publication clause, so the verb phrase starts
      // with a space. Built as "feed, published <date>, no longer lists" when
      // there is a date and "feed no longer lists" when there is not, which is
      // what the portal actually sends: no Last-Modified on these feeds, so the
      // clause is usually absent and a leading comma would be a comma splice.
      return "Ticket conditions are quoted from the fares feed. The National Rail Data Portal's own "
        + "restriction feed"
        + (published ? ", published" + published : "")
        + " no longer lists " + ref.missing + " of the " + ref.compared
        + " conditions on this page (" + codes + ")" + checkedClause
        + ". The wording below is the fares feed's, which is the same publication the prices are from.";
    }
    // The publication clause belongs to the publication date, so the verb
    // phrase carries its own connector. Built as "feed, published <date>, still
    // publishes" when the portal gave a date and "feed still publishes" when it
    // did not -- which is the usual case, because these feeds carry no
    // Last-Modified: joining the absent clause with a comma printed "restriction
    // feed, still publishes all 10", a splice a reader sees on the real page.
    return "Ticket conditions are quoted from the fares feed"
      + (DATA.feedDate ? ", downloaded" + dayPhrase(DATA.feedDate) : "")
      + ". The National Rail Data Portal's own restriction feed"
      + (published ? ", published" + published + ", still publishes all " : " still publishes all ")
      + ref.compared + " conditions on this page"
      + checkedClause + ".";
  })();
  line.textContent = text;
  line.hidden = !text;
}

function renderCoverage() {
  const coverage = document.getElementById("feedCoverage");
  if (!coverage || DATA.rawFareDestinationCount === undefined) return;
  const mode = ticketMode();
  const lead = mode === "single"
    ? DATA.singleDestinations.length + " displayable outbound single fares are available in this mode." +
      (DATA.singleJourneyNote ? " " + DATA.singleJourneyNote : "")
    : mode === "anytime"
      ? DATA.anytimeDestinations.length + " reviewed unrestricted Anytime Day Return fares are available in this mode."
      // Q4: the cheapest list is not one of the three sets, so it has a lead of
      // its own rather than borrowing a set's sentence and counting its fares.
      : mode === CHEAPEST_MODE
        ? modeCount(CHEAPEST_MODE) + " destinations are shown, each on the cheapest fare of any ticket type the feed prices for it" + droppedFromFeed() + "."
      : DATA.rawFareDestinationCount + " standard-return destinations were found in the feed" + droppedFromFeed() + "." +
        (DATA.destinations.length
          ? " Raise the budget to include more of the " + DATA.destinations.length + " displayable destinations."
          : "");
  coverage.textContent = lead + classifiedNote() + unnameableNote();
}
function droppedFromFeed() {
  // The naming gap is not listed here. It used to be, in the return mode's
  // sentence only, which is why the single and Anytime modes had no way to
  // report it. unnameableNote() owns that count for all three modes instead,
  // so a reader never sees it stated twice in one line.
  const dropped = [];
  if (DATA.excludedItxCount) dropped.push(DATA.excludedItxCount + " had only ITX placeholder fares");
  return dropped.length ? "; " + dropped.join(" and ") + ", and are not shown" : ", and all are shown";
}
function classifiedNote() {
  if (DATA.unclassifiedDestinationCount) {
    return " " + DATA.unclassifiedDestinationCount + " priced destinations carry no reviewed " +
      "destination type, so no type chip on this page can select them.";
  }
  return DATA.locationTypeReviewed ? " Every destination on this page carries a reviewed type." : "";
}
// C11: the coverage line named destinations lost to a missing *type* but not
// the ones lost to a missing *name*. Those are a different gap with a different
// consequence -- a row the feed could not put a station name on is a row a
// reader cannot recognise -- and saying only the first made a shortlist with a
// known gap in it look complete. It is stated here, as a count of flow records
// the feed could not name, so it is never read as a destination a reader
// should expect to find.
function unnameableNote() {
  if (!DATA.unnameableFareCount) return "";
  return " " + DATA.unnameableFareCount + " priced " +
    (DATA.unnameableFareCount === 1 ? "flow had" : "flows had") +
    " no station name in the feed, so " +
    (DATA.unnameableFareCount === 1 ? "it is" : "they are") +
    " not shown here; that is a gap in the feed's names, not a place with no fare.";
}

function renderEmptyMode() {
  empty.replaceChildren();
  const why = document.createElement("p");
  why.textContent = emptyModeMessage();
  empty.append(why);
  const actions = document.createElement("p");
  actions.className = "empty-actions";
  for (const [mode, label] of Object.entries(modeLabels())) {
    if (mode === ticketMode() || !modeCount(mode)) continue;
    const input = document.querySelector(`input[name="ticketMode"][value="${mode}"]`);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "toggle";
    button.textContent = label + " has " + modeCount(mode);
    button.addEventListener("click", () => {
      input.checked = true;
      currentPage = 1;
      render();
      writeUrl();
    });
    actions.append(button);
  }
  if (actions.childElementCount) {
    actions.prepend(document.createTextNode("Try: "));
    empty.append(actions);
  }
}

function renderEmpty(available, wanted, cap, what) {
  empty.replaceChildren();
  if (wanted.length) return;
  const why = document.createElement("p");
  // C21: the predicate is price <= cap, so every place the budget is named
  // says "up to". "Within" and "under" both read as exclusive to a reader
  // comparing them with a fare that lands exactly on the ceiling, and the
  // summary, the empty state and the heading have to agree.
  why.textContent = "No destinations for up to " + money(cap) + " " + what + typeLabel() + ".";
  empty.append(why);
  const actions = document.createElement("p");
  actions.className = "empty-actions";
  const offer = (label, run) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "toggle";
    button.textContent = label;
    button.addEventListener("click", run);
    actions.append(button);
  };
  // The cheapest destination this mode carries, whatever the budget: the
  // budget that would include it is the one number the reader is missing.
  const cheapest = available.reduce(
    (low, destination) => Math.min(low, priceOf(destination)), Infinity);
  if (Number.isFinite(cheapest) && cheapest > cap) {
    const enough = Math.ceil(cheapest / 100);
    offer("Show everything up to " + money(enough * 100), () => {
      setBudget(enough);
      currentPage = 1;
      render();
      writeUrl({ budget: true });
    });
  }
  if (selectedDestinationTypes().size) {
    offer("Clear the destination type", clearDestinationTypes);
  }
  // A pair's price is a different number, so a party the reader has not chosen
  // yet is a real way out of an empty list rather than advice.
  if (unit() === "adult" && railcardKeys.length) {
    const cheaper = activeDestinations().some((destination) => destination.partyPence <= cap * 100);
    if (cheaper) {
      offer("Price it for two adults", () => {
        document.querySelector('input[name="unit"][value="party"]').checked = true;
        currentPage = 1;
        render();
        writeUrl();
      });
    }
  }
  // Another ticket type on this origin, with its own count.
  for (const [mode, label] of Object.entries(modeLabels())) {
    if (mode !== ticketMode() && modeCount(mode)) {
      const input = document.querySelector(`input[name="ticketMode"][value="${mode}"]`);
      offer(label + " has " + modeCount(mode), () => {
        input.checked = true;
        currentPage = 1;
        render();
        writeUrl();
      });
    }
  }
  if (actions.childElementCount) {
    actions.prepend(document.createTextNode("Try: "));
    empty.append(actions);
  }
}

function render() {
  // The tab title is the same sentence as the heading, and a reader who
  // dragged the budget and then looked at the tab list had no way to tell two
  // searches apart. Before the early returns, because a page with nothing
  // priced still names its origin and its budget.
  document.title = "Train fares up to £" + budgetNumber.value + " from " + DATA.origin.name;
  // Before any price is read: the railcard changes the price of every row, and
  // a card ticked for a party of one is a number no reader could buy. It also
  // decides which row the cheapest list keeps for a destination, so that list
  // is composed after this and not before it.
  syncRailcardParty();
  const available = activeDestinations();
  // Before the filter is read, not after: a chip the active list cannot support
  // must not be part of what the filter is asked to match.
  syncDestinationTypeChips();
  // An unpriced page has no budget conversation: provenance() has already
  // stood the controls and the table down, and anything this function wrote
  // ("Nothing inside this budget") would contradict the page's own first
  // sentence. So it does nothing at all -- but that is the only case where it
  // says nothing.
  if (!DATA.destinations.length && !DATA.singleDestinations.length && !DATA.anytimeDestinations.length) {
    if (filterState) filterState.textContent = "";
    return;
  }
  renderCoverage();
  renderModeNote();
  if (!available.length) {
    // The budget is left alone on purpose. An empty list has no prices to
    // bound, and clamping to the £1 ceiling of an empty list would silently
    // reset the reader's budget for every other mode they switch back to.
    rows.replaceChildren();
    summary.textContent = "No " + modeLabels()[ticketMode()] + " fares from " + DATA.origin.name;
    empty.hidden = false;
    renderEmptyMode();
    more.hidden = true;
    pagination.hidden = true;
    pageStatus.textContent = "";
    // The shortlist is a list of places this mode can price, so a mode that
    // prices none of them empties it rather than leaving a list of names with
    // no fares behind them.
    shortlistCodes = [];
    renderFilterState();
    renderShortlist();
    return;
  }
  const ceiling = budgetCeiling();
  budget.max = String(ceiling);
  budgetNumber.max = String(ceiling);
  // The stop is part of the budget's contract, so it is named where the
  // reader is holding the control, and it is named as a figure rather
  // than a rule: the sentence above the number is what changes, the number
  // is what the reader can predict a boundary fare against.
  budgetCeilingNote.textContent = money(ceiling * 100) + " for "
    + (unit() === "party" ? "two adults" : "one adult");
  if (Number(budget.value) > ceiling) setBudget(ceiling);
  const cap = Number(budget.value) * 100;
  const wantedTypes = selectedDestinationTypes();
  // C17: the three fare arrays arrive sorted once by the standard fare. The
  // price on screen is not always that fare -- choosing two adults doubles it,
  // and the railcard replaces it with a per-ticket discounted price that a
  // minimum fare can hold above the adult price -- so the list is re-sorted by
  // the price actually displayed, and the count line below says so in words.
  // Sorting the displayed number is the only ordering that cannot contradict
  // the number in the cell beside it.
  const wanted = available
    .filter((d) => priceOf(d) <= cap && matchesType(d, wantedTypes))
    .sort((a, b) => priceOf(a) - priceOf(b));
  budgetNumber.value = budget.value;
  sizeBudgetField();
  updateChipCounts(available, cap);
  renderFilterState();
  rows.replaceChildren();

  const pageCount = Math.max(1, Math.ceil(wanted.length / PAGE_SIZE));
  currentPage = Math.min(Math.max(1, currentPage), pageCount);
  const pageItems = wanted.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  for (const destination of pageItems) {
    const row = document.createElement("tr");
    row.dataset.crs = destination.crs;
    // The header is one list and the cells are the same list, in the same
    // order, built here. They used to be two lists written in different places
    // and they had drifted: the header read Station, Price, Time, Changes,
    // Fare code, Tickets while the cells were written Station, Time, Changes,
    // Price, Fare code, Tickets, so the Price column showed "No service" and
    // the Changes column showed the fare. A prices-only build stands two of
    // these columns down, and it stands down the same two here and in the
    // header for the same reason.
    const cells = [stationCell(destination), priceCell(destination)];
    if (DATA.hasJourneys) {
      cells.push(journeyCell(destination, "Time"), journeyCell(destination, "Changes"));
    }
    cells.push(fareTypeCell(destination));
    for (const cell of cells) row.append(cell);
    cellWithLinks(row, destination, wanted);
    rows.append(row);
  }

  // Q4: in the cheapest list every row names its own fare, so the count line
  // names the mix rather than implying one ticket type, and the party figure
  // says what it is two of -- on a single row, two singles, not two returns.
  const what = unit() === "party" ? "for the two of us" : "each";
  const basis = ticketMode() === CHEAPEST_MODE && unit() === "party"
    ? "for the two of us, two of the fare each row names"
    : what;
  // ADR-0041: the order belongs to the list, so it is said once, here, rather
  // than by tinting one row the reader is left to interpret.
  const order = ", cheapest first";
  const mix = ticketMode() === CHEAPEST_MODE ? mixPhrase(wanted) : "";
  // An unpriced origin has no budget conversation to have, so the summary
  // stays empty rather than implying the budget filtered something out.
  summary.textContent = available.length && wanted.length
    ? wanted.length + (wanted.length === 1 ? " destination" : " destinations") + " for up to " + money(cap) + " " + basis + order + mix
    : available.length ? "No destinations for up to " + money(cap) + " " + basis : "";
  empty.hidden = wanted.length > 0;
  renderEmpty(available, wanted, cap, basis);
  more.hidden = true;
  pagination.hidden = pageCount <= 1;
  pageStatus.textContent = "Page " + currentPage + " of " + pageCount + " of " + wanted.length +
    (wanted.length === 1 ? " result" : " results");
  previousPage.disabled = currentPage === 1;
  nextPage.disabled = currentPage === pageCount;
  renderShortlist();
}

// The destination, and nothing else: the name, the three-letter code a seller
// asks for, and the World Heritage proof where the feed names one. The station
// is the widest thing in the row, so the column takes the slack and the
// numbers beside it keep one position each.
function stationCell(destination) {
  const cell = document.createElement("td");
  cell.dataset.label = "Station";
  const name = document.createElement("span");
  name.className = "station-name";
  name.textContent = destination.name;
  const code = document.createElement("span");
  code.className = "station-code";
  code.textContent = destination.crs;
  cell.append(name, " (", code, ")");
  if (destination.heritageSites?.length) {
    const heritage = document.createElement("span");
    heritage.className = "heritage-proof";
    heritage.append("World heritage: ");
    destination.heritageSites.forEach((site, index) => {
      if (index) heritage.append("; ");
      const link = document.createElement("a");
      link.href = site.url;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = site.name;
      link.title = "UNESCO World Heritage List site " + site.id;
      heritage.append(link);
    });
    cell.append(heritage);
  }
  return cell;
}

// Time and Changes, in one builder because they are the same fact read twice:
// a journey this build could not find has neither a duration nor a change
// count, and saying "Unknown" beside a real duration would be a lie. S23's
// point stands -- a dash said nothing about which of three different absences
// it was, so the cell names the absence.
function journeyCell(destination, column) {
  const missing = destination.journeyState !== "found";
  const cell = document.createElement("td");
  cell.className = missing ? "num missing" : "num";
  cell.dataset.label = column;
  if (column === "Time") {
    cell.textContent = missing ? "No service" : duration(destination.minutes);
    return cell;
  }
  const count = document.createElement("span");
  count.className = "changes-count";
  count.textContent = missing ? "Unknown" : changeCount(destination.changes);
  cell.append(count);
  // Q2 (ADR-0045): the station a journey changes at is the part a reader can
  // act on, and it was only ever inside a disclosure they had to open on every
  // row to find. It sits under the count now, in the column whose header is
  // the word "Changes".
  const via = interchangeLine(destination);
  // The station sits on its own line under the count, so this cell is two
  // lines tall by design. It says so in the markup, because the check that
  // measures wrapped numbers cannot otherwise tell that from a number that
  // ran out of room.
  if (via) {
    cell.classList.add("changes");
    cell.append(via);
  }
  return cell;
}

function changeCount(changes) {
  if (changes === null || changes === undefined) return "Unknown";
  if (changes === 0) return "Direct";
  return changes === 1 ? "1 change" : changes + " changes";
}

function interchangeLine(destination) {
  const stations = destination.changeStations || [];
  if (!stations.length) return null;
  const line = document.createElement("span");
  line.className = "interchange";
  line.textContent = "via " + stations.map((station) => station.name).join(" and ");
  return line;
}

// The fare in the reader's own three words. The feed's code is a seller\u2019s
// vocabulary -- SDR, 2AS, BPS -- and it was the column, on every row, in front
// of the one number the reader came for. It is still here, in the row\'s own
// disclosure under "Feed record", which is where a code belongs: available
// when it is asked for, invisible until then.
function fareTypeCell(destination) {
  const cell = document.createElement("td");
  cell.className = "fare-type";
  cell.dataset.label = "Fare type";
  cell.dataset.kind = destination.isAdvance ? "advance"
    : destination.restrictionCode ? "restricted" : "regular";
  const kind = document.createElement("span");
  kind.className = "fare-kind";
  kind.textContent = fareTypeWord(destination);
  cell.append(kind);
  cell.title = fareSummary(destination);
  return cell;
}

function fareTypeWord(destination) {
  if (destination.isAdvance) return "Advance";
  if (destination.restrictionCode) return "Restricted";
  return "Regular";
}

// The one word beside the code, and only where the row differs from its
// neighbours: a fare that needs a second look says so, and a fare that does not
// stays quiet rather than repeating a sentence the mode note already made.
function fareFlag(destination) {
  if (destination.isAdvance) return "advance";
  if (destination.restrictionCode) return "restricted";
  return "";
}

// The fare in words, inside the row's own disclosure. It is a full sentence
// because it is the only thing the panel says before the condition: a fragment
// with a semicolon in it was read as two facts of equal weight, and the second
// half of it ("price and availability can change") was the one a reader needed
// before deciding whether to trust the price at all.
function fareSentence(destination) {
  if (destination.isAdvance) {
    return "Advance single: you choose the train, and the price and availability can change.";
  }
  if (destination.restrictionCode) return "Restricted fare \u2014 the condition is below.";
  if (destination.quality === "outbound single") return "Standard outbound single, with no conditions in the feed.";
  if (destination.quality === "unrestricted Anytime Day Return") {
    return "Unrestricted Anytime Day Return: valid on any train on the route.";
  }
  return "Standard return fare, with no conditions in the feed.";
}

// What the row's title attribute says, in the same voice as the sentence: the
// flag explained without repeating the panel behind it.
function fareSummary(destination) {
  if (destination.isAdvance) return "Advance single: valid only on a qualifying train, and the price and availability can change.";
  if (destination.restrictionCode) return destination.restrictionDescription || "This fare has a restriction code; the condition is in this row's details.";
  return "No fare restriction code is attached to this fare.";
}

// Q2 (ADR-0045): a journey with a change is where a split ticket can undercut
// the through fare, and the station it would change at is the part a reader can
// act on. The page states the possibility and no price: the feed prices flows,
// not itineraries, so which two tickets are cheaper is not in this data.
function splitNote(destination) {
  const stations = destination.changeStations || [];
  if (!stations.length) return null;
  // The station itself is named in the Changes column now, so this says only
  // the thing that is still worth saying and is nowhere else on the page: the
  // through fare is not the cheapest way to buy this journey, and this page
  // cannot tell you which two tickets would be.
  const note = document.createElement("p");
  note.className = "split";
  note.textContent = "A split ticket \u2014 one ticket to the station above and " +
    "another from it \u2014 can sometimes cost less than this through fare. " +
    "This page prices the through fare only.";
  return note;
}

// The FARE and CONDITIONS columns, moved into the panel the row already had
// rather than deleted: the condition is the reader's, the twenty repetitions of
// it were not (finding, 29 September 2026).
function fareDetails(destination) {
  const panel = document.createElement("div");
  panel.className = "restriction";
  const restricted = Boolean(destination.restrictionCode);
  panel.dataset.status = restricted ? "restricted" : "unrestricted";
  const fare = document.createElement("p");
  fare.className = "fare-line";
  fare.textContent = fareSentence(destination);
  panel.append(fare);
  // S19: what the reader has to know to rule the fare in or out, in sentences.
  // Said only when there is a condition to rule out: an unrestricted fare used
  // to open with a second paragraph saying there was nothing to read, which is
  // the same information as silence, said in a line.
  if (restricted) {
    const readable = document.createElement("p");
    readable.className = "condition";
    readable.textContent = destination.restrictionDescription ||
      "This fare carries a restriction code; check the seller's conditions before buying.";
    panel.append(readable);
  }
  const split = splitNote(destination);
  if (split) panel.append(split);
  // The railcard, when one is in play, and the feed's record of the fare --
  // codes, restriction, route, and the exact RR rule that decided the card's
  // price. All of it is the explanation of the number at the top of the row, so
  // all of it is in the one place the reader opened to find the number.
  const card = cardNote(destination);
  if (card) panel.append(card);
  panel.append(feedRecord(destination));
  panel.title = fareSummary(destination);
  return panel;
}

// C08: what the condition actually permits, in the feed's own words. A code
// and a one-line description tell a reader which fare is restricted, not
// whether the train they have in mind is one of the trains it is valid on --
// which is the thing being decided when two prices are compared. So the
// outward and return validity the feed states is printed here, next to the
// description, and the codes stay in the folded record below as audit detail.
//
// The single-mode row is a one-way ticket, so only the outward text can apply
// to it; showing a return condition beside a single would state a limit on a
// leg the ticket does not have.
function validityNote(destination) {
  if (!destination.restrictionCode) return null;
  const validity = DATA.restrictionValidity
    ? DATA.restrictionValidity[destination.restrictionCode]
    : null;
  if (!validity) return null;
  const single = destination.quality === "outbound single";
  const lines = [];
  if (validity.outwardText) lines.push("Valid outward: " + validity.outwardText);
  if (!single && validity.returnText) lines.push("Valid on the return: " + validity.returnText);
  if (!lines.length) return null;
  const note = document.createElement("span");
  note.className = "validity";
  note.append(lines.join(" "));
  return note;
}

// S19: the record as the feed states it -- ticket code, restriction code,
// route, and which price-quality the build chose it as. Folded away, because a
// reader deciding where to go needs the condition, not the vocabulary.
function feedRecord(destination) {
  const details = document.createElement("details");
  details.className = "feed-record";
  const summary = document.createElement("summary");
  summary.textContent = "Feed record";
  const list = document.createElement("dl");
  const add = (term, value) => {
    if (value === null || value === undefined || value === "") return;
    const dt = document.createElement("dt");
    dt.textContent = term;
    const dd = document.createElement("dd");
    dd.textContent = value;
    list.append(dt, dd);
  };
  add("Ticket", destination.ticket);
  add("Restriction", destination.restrictionCode || "none");
  add("Route", destination.routeCode);
  add("Priced as", destination.quality);
  add("Times", destination.journeyState);
  // C08: what the condition permits, in the feed's own words. It was a third
  // paragraph under the row's own, in capitals, between a sentence and a code,
  // and it was the only part of the three that could not be paraphrased without
  // a licencee's risk. It is here now: still verbatim, still present, and
  // behind the record rather than in front of the decision.
  const validity = validityNote(destination);
  if (validity) {
    const dt = document.createElement("dt");
    dt.textContent = "In the feed\u2019s words";
    const dd = document.createElement("dd");
    dd.append(validity);
    list.append(dt, dd);
  }
  const rule = railcardRuleFor(destination);
  if (rule) add("Railcard rule", rule);
  details.append(summary, list);
  return details;
}

// The exact RR rule behind the chosen card\u2019s price on this fare, if there
// is one. It was the last line of a dialog; a rule is a record, and records
// live in the record.
function railcardRuleFor(destination) {
  if (noCard() || !railcards[railcardSelect.value]) return null;
  const details = (destination.railcards || {})[railcardSelect.value];
  if (!details || !details.rule) return null;
  const rule = DATA.railcardRules[details.rule];
  return rule ? rule.text : null;
}

function cellWithLinks(row, destination, wanted) {
  // Two controls on the row and no more: the ticket link, because buying is the
  // action and hiding it behind a second click loses the click; and the
  // expander, because the journeys are what a reader checks first and the
  // panel behind it is where the fare, the condition, the railcard drawer and
  // the handoff text live. This cell used to carry five controls on every row,
  // which is a hundred targets on page one (finding 4, 29 September 2026); the
  // shortlist toggle stays, because comparing places is a thing a reader does
  // while scanning the list rather than after opening a row.
  const cell = document.createElement("td");
  cell.dataset.label = "Tickets";
  const link = document.createElement("a");
  link.className = "buy";
  link.href = destination.link.url;
  link.rel = destination.link.rel;
  link.target = "_blank";
  link.textContent = "Tickets";
  // C13: the visible label stays the one word a price-first column can hold,
  // but a screen reader's links list used to be a column of identical "Tickets"
  // entries with no way to tell them apart. The name carries the destination,
  // and the same word is in the title so a sighted reader's tooltip agrees.
  link.setAttribute("aria-label", "Tickets for " + destination.name);
  link.title = "Tickets for " + destination.name + " — " +
    destination.link.label + " search for " + destination.crs;
  cell.append(link);
  // One disclosure per row, on every row. It used to exist only where the
  // build had times, which left a fare's condition unreachable on a
  // prices-only page; the label still counts the times where there are times
  // to count.
  const times = destination.departures.length;
  const toggle = document.createElement("button");
  toggle.className = "toggle";
  toggle.type = "button";
  toggle.textContent = times ? times + " times" : "Fare details";
  toggle.setAttribute("aria-expanded", "false");
  // WCAG 2.5.3: the accessible name contains the visible label, so "5 times"
  // is still what a reader using voice control has to say to reach it.
  toggle.setAttribute("aria-label",
    (times ? times + " times and fare details for " : "Fare details for ") + destination.name);
  toggle.addEventListener("click", () => toggleDetail(row, destination, toggle));
  cell.append(toggle);
  row.append(cell);
}

// What the railcard did to this row's price, in the row's own disclosure.
//
// It was a dialog: a button on every row, opening a panel on top of a page
// the reader was already reading, to be told a number the row beside it
// already carried. The sentences are unchanged -- they are the ones that keep
// the page honest about a card that cannot help -- but they now sit under the
// fare they explain, where the reader opened the row to look, and the feed's
// exact RR rule sits in the feed record below them with the codes.
function cardNote(destination) {
  // With no card chosen there is nothing to explain: the row is priced at the
  // standard fare, the price cell says so by not saying otherwise, and the
  // control above already reads "No railcard selected, so these are standard
  // fares". A paragraph on every expanded row repeating the page's default is
  // the noise this replaced.
  if (noCard() || !railcards[railcardSelect.value]) return null;
  const note = document.createElement("p");
  note.className = "card-note";

  const card = railcards[railcardSelect.value];
  const details = (destination.railcards || {})[card.key];
  if (!details) {
    note.dataset.state = "unavailable";
    note.textContent =
      "This feed prices no " + card.label + " fare to " + destination.name + ", so there is " +
      "nothing to compare it against.";
    return note;
  }

  // The rule record lives once in DATA.railcardRules and every card's row
  // carries its key, because repeating the record per row cost 388KB on the
  // heaviest real page (audit B3).
  const rule = details.rule ? DATA.railcardRules[details.rule] : null;
  const condition = rule && !rule.totalBan && rule.restrictionCode !== "none"
    ? rule.restrictionCode
    : null;
  const cardBeatsStandard = details.pricePence !== null && details.pricePence < destination.adultPence;
  const minimumClause = details.minimumFarePence === null
    ? ", and no minimum fare is current for this ticket."
    // The build floors the card's price at the minimum, so price == minimum is
    // the only way to land here, and it lands on the branches where the card
    // does help. Saying the minimum makes the fare dearer would be false there,
    // and saying it is above a discounted price the page never sent would be a
    // claim about a number nobody can see: so it says the minimum is the price.
    : details.minimumFarePence >= details.pricePence
      ? ", and the DTD minimum fare of " + money(details.minimumFarePence) +
        " is the price here, so the discount took it no lower."
      : ", and the DTD minimum of " + money(details.minimumFarePence) + " does not raise it.";

  note.dataset.state = details.state;
  // The sentences are written here rather than shipped per row per card. Six
  // cards at the build's own wording measured 2,598 bytes a row against 433
  // for one, on a page that already carries 411KB; the facts cost 98.
  if (details.state === "blocked") {
    note.textContent =
      card.label + " cannot be applied to this fare. A current DTD RR rule matches this ticket, " +
      "route or endpoint and records a total ban, so the standard fare is the only price the feed " +
      "offers here.";
  } else if (!cardBeatsStandard) {
    // The three numbers the build already sent are enough to say this. The
    // discounted price before the minimum is not one of them, and recomputing it
    // here would put a second copy of the rounding rule in the page, where it
    // could drift from the build's.
    // The figure first is the one in the row, not the card's. On a real page
    // the card's own price is often the DTD minimum -- £12.00 on a fare the
    // reader is looking at for £2.70 -- and opening a note with the larger
    // number makes the reader hunt for the one that is theirs. priceOf() is
    // the same figure the Price cell renders, so the two cannot disagree.
    note.textContent =
      "This fare is " + money(priceOf(destination)) + ", and " + card.label +
      " does not reduce it. The card's own price here is " +
      money(details.pricePence) + " per adult, because the minimum fare the feed applies to this " +
      "ticket is " + money(details.minimumFarePence) +
      ". This row is priced at the cheaper of the two, so travelling without the card would " +
      "cost the same.";
  } else if (condition) {
    note.textContent =
      card.label + " is available for this fare, subject to condition " + condition + ". No " +
      "matching total ban applies; the restriction is a travel condition rather than a card ban. " +
      "The feed\u2019s one-third discount gives " + money(details.pricePence) + " per adult" +
      minimumClause;
  } else {
    note.textContent =
      card.label + " is available for this fare. No current RR rule matches this ticket, route or " +
      "either endpoint. The feed\u2019s one-third discount gives " + money(details.pricePence) +
      " per adult" + minimumClause;
  }
  return note;
}

// The row's one secondary action, in the panel rather than on the row: the
// handoff text, which is what a reader pastes to a seller or a friend
// (ADR-0018). The copy text of a refused clipboard lands in this same panel,
// under the button that asked for it.
function rowActions(row, destination) {
  const tools = document.createElement("div");
  tools.className = "row-actions";
  const copy = document.createElement("button");
  copy.className = "toggle";
  copy.type = "button";
  copy.textContent = "Copy";
  copy.setAttribute("aria-label", "Copy the journey details for " + destination.name);
  copy.title = "Copy the from, to, date and party size for this row";
  copy.addEventListener("click", () => copyJourney(destination, copy, tools));
  tools.append(copy);
  return tools;
}

// C28: one panel per row, and one owner for it. It used to be two -- the times
// list and the manual-copy box each removed whatever sat under the row -- so
// opening one silently emptied the other and left its control announcing a
// state that had gone. The copy text now lands inside the panel the button that
// asked for it is already in, which leaves one region per row and one control
// whose state is written back when it closes.
let regionSeq = 0;
// Keyed on the row element, not its station code: every render replaces the
// rows, so a code-keyed map would keep detached rows and their panels alive
// and let one render's state answer for another's row.
const rowPanel = new WeakMap();
function closePanel(row) {
  const panel = rowPanel.get(row);
  if (!panel) return false;
  panel.row.remove();
  if (panel.control) panel.control.setAttribute("aria-expanded", "false");
  rowPanel.delete(row);
  return true;
}
function toggleDetail(row, destination, toggle) {
  if (rowPanel.get(row)) {
    closePanel(row);
    return;
  }
  const detail = document.createElement("tr");
  detail.className = "detail";
  const cell = document.createElement("td");
  cell.colSpan = columnCount();
  if (destination.departures.length) {
    const list = document.createElement("ul");
    for (const option of destination.departures) {
      const item = document.createElement("li");
      item.textContent = clock(option.depart) + " depart, " + clock(option.arrive) + " arrive, " +
        (option.changes ? option.changes + " change(s)" : "no change");
      list.append(item);
    }
    cell.append(list);
  }
  // The fare in words and its condition, in the panel the row already had. A
  // build with no timetable has no times to list and still has a fare to
  // explain, which is why the toggle exists on every row. The row's two
  // secondary actions live at the end of the same panel.
  cell.append(fareDetails(destination), rowActions(row, destination));
  detail.append(cell);
  detail.id = "detail-times-" + destination.crs + "-" + (regionSeq += 1);
  row.after(detail);
  rowPanel.set(row, { row: detail, control: toggle });
  toggle.setAttribute("aria-controls", detail.id);
  toggle.setAttribute("aria-expanded", "true");
}

// C04: the first sentence of the page promised the fastest journey time and
// the number of changes, and the script then removed the Time and Changes
// columns on a prices-only build without revising the sentence. So the
// sentence is written here, from the build's own fact, rather than shipped as
// prose that one shape of build is lying about.
function renderIntro() {
  const intro = document.getElementById("pageIntro");
  if (!intro) return;
  // The first-use note is a child of this paragraph, so it is replaced by
  // writing the first text node and leaving the span the build filled in alone.
  // Setting textContent on the paragraph would delete the build's sentence
  // along with the old one, and a station page with no sentence saying what the
  // station name does is exactly the page the note exists to prevent.
  const first = intro.firstChild;
  const text = DATA.hasJourneys
    ? "Every place you can reach from the station above, inside the budget, with the fastest time and the fewest changes."
    : "Every place this feed prices from the station above, inside the budget. This build has no timetable, so no times are shown.";
  if (first && first.nodeType === 3) first.nodeValue = text + " ";
  else intro.insertBefore(document.createTextNode(text + " "), intro.firstChild);
}

function provenance() {
  // An origin the build could not price is a different page from one whose
  // prices sit outside this budget, so it gets its own first sentence and its
  // own way forward — not an empty table under a slider that can't help.
  if (!DATA.destinations.length && !DATA.singleDestinations.length && !DATA.anytimeDestinations.length) {
    document.getElementById("pageIntro").hidden = true;
    const unpriced = document.getElementById("unpriced");
    const intro = "We couldn't price any journeys from " + DATA.origin.name +
      " (" + DATA.origin.crs + ") in this feed.";
    const why = DATA.unpricedNote ? " " + DATA.unpricedNote : "";
    if (DATA.stations && DATA.stations.length) {
      const link = document.createElement("a");
      link.href = DATA.baseHref;
      link.textContent = "Start from a station we do price";
      unpriced.append(intro + why + " ", link, ".");
    } else {
      unpriced.textContent = intro + why + " Nothing was priced from any station, so there is nothing to explore yet.";
    }
    unpriced.hidden = false;
    const controls = document.querySelector(".filter-bar");
    if (controls) controls.hidden = true;
    // The table scaffold and the budget's empty message answer a question
    // this page is not asking: nothing was priced, so no budget could help.
    for (const id of ["empty", "more"]) {
      const el = document.getElementById(id);
      if (el) el.hidden = true;
    }
    const table = document.querySelector("table");
    if (table) table.hidden = true;
    const summary = document.getElementById("summary");
    if (summary) summary.hidden = true;
  }

  const available = activeDestinations();
  // The same set names itself here as it does above the table: a provenance
  // line counting "return destinations" on a page showing the cheapest fare of
  // any type is the feed's vocabulary, not the reader's.
  const listed = {
    cheapest: "destinations, each on its cheapest fare of any ticket type, in the feed",
    single: "outbound single destinations in the feed",
    anytime: "unrestricted Anytime Day Return destinations in the feed",
    return: "return destinations in the feed",
  };
  const parts = [
    "Origin " + DATA.origin.name + " (" + DATA.origin.crs + ")",
    available.length + " " + (listed[ticketMode()] || "destinations in the feed"),
  ];
  if (DATA.hasJourneys) {
    parts.push(DATA.serviceDate ? "services on " + DATA.serviceDate : "typical services in the feed");
  } else {
    parts.push("no timetable loaded, so no times are shown");
  }
  if (DATA.locationTypeSource) parts.push("destination types: " + DATA.locationTypeSource);
  document.getElementById("provenance").textContent = parts.join(" \u00b7 ");
  document.getElementById("pricingBasis").textContent = DATA.pricingBasis
    ? DATA.pricingBasis + ". Use the ticket-type control to change which fares are listed, then use the budget filter to narrow the list."
    : "";
  renderCoverage();
  renderModeNote();
  renderFreshness();
  renderRestrictionReference();
  renderIntro();
  document.getElementById("railcardNote").textContent = DATA.railcardNote;
  // C03: what the reader has to do for themselves when the link is the plain
  // one, and what the link earns the site. Both sit above the table now, so
  // they are read before the first ticket action rather than after a click has
  // already left the page; the technical detail stays in the accordion.
  if (DATA.linkNote) {
    const linkNote = document.getElementById("linkNote");
    linkNote.textContent = DATA.linkNote;
    linkNote.hidden = false;
  }
  // C04: the undated-schedule caveat is a statement about the times, so it
  // belongs with the times -- the freshness line, above the table -- and not in
  // the methodology accordion, which a reader has no reason to open before
  // trusting a time.
  if (DATA.dateNote) {
    const note = document.createElement("p");
    note.className = "tag";
    note.id = "dateNote";
    note.textContent = DATA.dateNote;
    // Straight after the freshness line, whether or not that line has anything
    // to say: a hidden element still holds its place in the document, so
    // choosing the anchor by visibility would only move the note around
    // depending on a fact the reader did not ask about.
    document.getElementById("freshness").after(note);
  }
  // The licence wording, when there is some. It sits above the note rather than
  // in a comment, because a term that has to be visible is not satisfied by
  // being present in the file.
  if (DATA.attribution) {
    // One notice per paragraph: the RDG credit, the OGL sentence, and the
    // accuracy/liability notice are distinct statements with distinct
    // obligations (ADR-0020, ADR-0021), and one run-on paragraph would let
    // a reader miss the one that disclaims the numbers.
    const attribution = document.getElementById("attribution");
    for (const notice of [].concat(DATA.attribution)) {
      const p = document.createElement("p");
      p.textContent = notice;
      attribution.append(p);
    }
    attribution.hidden = false;
  }
  // Where the numbers came from, stated beside the prices rather than in the
  // footer, because where a number came from is part of the number.
  if (DATA.priceSource) {
    const line = document.getElementById("priceSource");
    const parts = ["Prices from " + DATA.priceSource];
    if (DATA.serviceDate) parts.push("feed dated " + humanDate(DATA.serviceDate));
    line.textContent = parts.join(", ") + ".";
    line.hidden = false;
  }
  if (DATA.builtAt) {
    const line = document.getElementById("buildMetadata");
    line.textContent = "Site built " + DATA.builtAt.replace("T", " ").replace("Z", " UTC") +
      (DATA.sourceFingerprint ? " · source " + DATA.sourceFingerprint : "") + ".";
    line.hidden = false;
  }
  if (DATA.tracked) {
    const disclosure = document.getElementById("disclosure");
    disclosure.textContent = DATA.disclosure;
    disclosure.hidden = false;
  }
  // ADR-0040: the fold above the first ticket action has to say what it holds,
  // and one of the facts in it must not be a click away -- when the links are
  // tracked, the line names the payment. A fold holding nothing is hidden
  // rather than left as a control that opens onto nothing.
  const linkTerms = document.getElementById("linkTerms");
  if (linkTerms) {
    document.getElementById("linkTermsSummary").textContent = DATA.tracked && DATA.disclosure
      ? "About the ticket link, and how this site is paid"
      : "About the ticket link";
    linkTerms.hidden = !Array.from(linkTerms.querySelectorAll("p")).some((p) => !p.hidden);
  }
}

const MONTHS = ["January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];

// Formatted from the ISO string by hand rather than through Date: new
// Date("2026-10-05") is parsed as UTC midnight, which prints as the 4th for any
// reader behind UTC. A copied date that is off by a day is worse than none.
function humanDate(iso) {
  const parts = String(iso).split("-").map(Number);
  return parts[2] + " " + MONTHS[parts[1] - 1] + " " + parts[0];
}

// A date the build could not read is left out of the sentence, not printed as
// whatever the formatter makes of it. The reference feed's publication date
// arrives from an HTTP header, and the first version of this line sliced it as
// an ISO timestamp and shipped the words "published undefined undefined NaN" to
// a real reader -- a page making a freshness claim it could not actually make.
// A clause with no readable date is no clause.
function dayPhrase(value) {
  if (!value) return "";
  const text = String(value).slice(0, 10);
  const parts = text.split("-").map(Number);
  if (parts.length !== 3 || parts.some((n) => !Number.isFinite(n))) return "";
  const shown = humanDate(text);
  return shown.includes("undefined") || shown.includes("NaN") ? "" : " " + shown;
}

// What the reader has to type on the seller's own site, because the ticket link
// carries nothing (ADR-0018). The railcard is named only when the party price is
// what is on screen, and it is named as something to tick rather than sent
// anywhere, because no seller accepts it in a link (ADR-0014).
function journeyText(destination) {
  const together = unit() === "party";
  // C09: the copied text named the stations, the date and the party but not
  // the ticket type the reader had chosen, while the same Copy button is
  // offered in every mode. Copied from Singles and pasted to a seller, the
  // handoff could silently become a different ticket, so the mode travels with
  // it.
  const lines = [
    "From: " + DATA.origin.name + " (" + DATA.origin.crs + ")",
    "To: " + destination.name + " (" + destination.crs + ")",
    "Ticket: " + fareName(destination),
  ];
  if (DATA.serviceDate) lines.push("Date: " + humanDate(DATA.serviceDate));
  lines.push("Passengers: " + (together ? DATA.adults + " adults" : "1 adult"));
  const card = chosenCard(destination);
  if (together && card) {
    lines.push(railcards[railcardSelect.value].label + " discount is not sent to the seller: confirm the railcard on their site");
  }
  return lines.join("\\n");
}

// The manual copy. The text is put where the reader is already looking, inside
// the panel the button is in, rather than in a panel of its own that would have
// taken the row's one slot from the details the reader opened to get here.
function showCopyText(host, text, button) {
  // A second manual copy replaces the first rather than stacking under it: the
  // button describes one box, and the panel grows no copy of the same text.
  for (const stale of host.querySelectorAll("textarea.copybox")) stale.remove();
  const box = document.createElement("textarea");
  box.className = "copybox";
  box.readOnly = true;
  box.rows = 5;
  box.value = text;
  box.id = "copy-text-" + (regionSeq += 1);
  box.setAttribute("aria-label", "Journey details to copy");
  host.append(box);
  // The copy control is not a disclosure -- it has no collapsed state to speak
  // of -- so it names the text it filled rather than claiming to control it.
  if (button) button.setAttribute("aria-describedby", box.id);
  box.focus();
  box.select();
}

async function copyJourney(destination, button, host) {
  const text = journeyText(destination);
  const status = document.getElementById("copyStatus");
  const done = () => {
    button.textContent = "Copied";
    status.textContent = "Journey details copied: " + text.split("\\n").join(". ");
    window.setTimeout(() => { button.textContent = "Copy"; }, 2000);
  };
  // Never claim a copy that did not happen. Clipboard access is refused when a
  // page is opened from a file or served without a secure context, so the
  // reader is shown the text instead of being told it is on their clipboard.
  const manual = () => {
    button.textContent = "Select below";
    status.textContent = "Could not copy automatically. The details are shown under the button.";
    showCopyText(host, text, button);
  };
  if (!navigator.clipboard || !navigator.clipboard.writeText) return manual();
  try {
    await navigator.clipboard.writeText(text);
    done();
  } catch (error) {
    manual();
  }
}

// The picker (ADR-0019): choosing a station is navigation to that station's
// page, not a filter on this one. The options are real anchors, so keyboard
// handling and accessible naming are the browser's own. The list is built from
// the written outputs, so nothing here can lead to a missing page.
const changeOrigin = document.getElementById("changeOrigin");
const originPicker = document.getElementById("originPicker");
if (changeOrigin && DATA.stations && DATA.stations.length) {
  // The field the page's own script created, read here rather than from the
  // document: it is moved into the heading when the picker opens, and the
  // markup no longer holds it.
  const originSearch = document.createElement("input");
  originSearch.id = "originSearch";
  originSearch.type = "search";
  originSearch.placeholder = "station";
  originSearch.autocomplete = "off";
  originSearch.setAttribute("aria-describedby", "originStatus");
  originSearch.setAttribute("aria-controls", "originPicks");
  originSearch.setAttribute("aria-label", "Start from a different station");
  const originSlot = changeOrigin.parentElement;
  const originPicks = document.getElementById("originPicks");
  const originNomatch = document.getElementById("originNomatch");
  const originStatus = document.getElementById("originStatus");

  function renderPicks() {
    const needle = originSearch.value.trim().toLowerCase();
    const wanted = DATA.stations.filter((station) => !needle || matches(station, needle));
    originPicks.replaceChildren();
    for (const station of wanted.slice(0, 40)) {
      const item = document.createElement("li");
      const link = document.createElement("a");
      // The reader's budget, ticket type and facets travel with them: changing
      // station is a correction of where they are leaving from, not a reset of
      // the decision they have already made.
      link.href = station.href + "?" + stateQuery();
      const name = document.createElement("span");
      name.textContent = station.name;
      const code = document.createElement("span");
      code.className = "code";
      code.textContent = station.crs;
      link.append(name, code);
      item.append(link);
      originPicks.append(item);
    }
    if (wanted.length) {
      originNomatch.hidden = true;
    } else {
      originNomatch.textContent = "We don't have prices from '" + originSearch.value.trim() +
        "'. Try the station's name or its three-letter code.";
      originNomatch.hidden = false;
    }
    originStatus.textContent = wanted.length + " station" + (wanted.length === 1 ? "" : "s") + " listed";
  }

  // The field is moved into the slot rather than duplicated, so there is one
  // input in the document and the heading's own accessible name is the one
  // that gets typed into. Moving it back on close keeps the DOM where the
  // script that reads it expects it after a navigation.
  function setPicker(open) {
    changeOrigin.setAttribute("aria-expanded", String(open));
    originPicker.hidden = !open;
    if (open) {
      if (originSearch.parentElement !== originSlot) originSlot.append(originSearch);
      changeOrigin.hidden = true;
      renderPicks();
      // The field is sized to its placeholder, so it is as wide as the word
      // "station" and no wider until something is typed into it.
      originSearch.focus();
      originSearch.select();
    } else {
      changeOrigin.hidden = false;
      if (originSearch.parentElement !== originPicker) originSearch.remove();
      // Escape is a keyboard exit, and focus returns to the control that
      // opened the picker rather than dropping to the top of the page.
      changeOrigin.focus();
    }
  }

  changeOrigin.addEventListener("click", () => {
    setPicker(changeOrigin.getAttribute("aria-expanded") !== "true");
  });
  // The listener is on the field rather than on the panel, because the field
  // is moved out of the panel and into the heading while the picker is open.
  // A listener on the panel alone meant Escape -- pressed in the field, which
  // is the only place a reader can press it -- bubbled past it and did nothing.
  originSearch.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setPicker(false);
  });
  originPicker.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setPicker(false);
  });
  originSearch.addEventListener("input", renderPicks);
  // The picker is the field's other half -- the same selector, reached from the
  // heading -- so it answers the same two keys through the same block. The
  // Escape handler above closes the whole picker; this only adds the way in.
  wireListKeys(originSearch, originPicks);
} else if (changeOrigin) {
  // The shared station list did not arrive, so this control can only open
  // an empty panel. Put the station's own name where the control was --
  // the heading must never be left saying "from" and nothing -- and say
  // what the page is instead of naming a control it does not have. This is
  // still one station's page, and the way to another one is the All
  // stations link in the footer. A build that ships the list inside the
  // page never reaches this branch: DATA.stations is filled before this
  // script runs, so there is no request that can fail.
  const stationName = document.createElement("span");
  stationName.className = "origin-name";
  stationName.textContent = DATA.origin ? DATA.origin.name : "";
  changeOrigin.replaceWith(stationName);
  originPicker.remove();
  const fallbackNote = document.getElementById("firstUse");
  if (fallbackNote) fallbackNote.textContent = FIRST_USE_FALLBACK;
}

// S26: a shortlist of candidate places, and nothing that looks like a
// booking. The list lives in the address like the rest of the search state, so
// it survives a refresh and can be handed to somebody else as a link; what it
// shows is the price currently on screen, because a comparison of a different
// price than the one beside each row would be a comparison of nothing.
const SHORTLIST_LIMIT = 8;
// Read from the address on load and written back on every change, like the rest
// of the search state: a shortlist that only lives in one tab is not a
// shortlist anybody can hand to somebody else.
let shortlistCodes = [];
const shortlistBar = document.getElementById("shortlistBar");
// The one element whose presence means this page has a shortlist at all. It
// was the section below the table; it is the strip above it, and every
// function that guarded on the old id was quietly doing nothing on a page
// without one.
const shortlist = shortlistBar;
const shortlistPick = document.getElementById("shortlistPick");
const shortlistShareBox = document.getElementById("shortlistShareBox");
const shortlistLimit = document.getElementById("shortlistLimit");
const shortlistList = document.getElementById("shortlistList");
const shortlistStatus = document.getElementById("shortlistStatus");
const shortlistEmpty = document.getElementById("shortlistEmpty");
const shortlistShare = document.getElementById("shortlistShare");
const shortlistClear = document.getElementById("shortlistClear");
const shortlistCopy = document.getElementById("shortlistCopy");
const shortlistBox = document.getElementById("shortlistBox");

function shortlisted() {
  const wanted = new Set(shortlistCodes);
  // In the page's own order, and only rows this ticket mode actually carries:
  // a shortlist that named a destination the reader cannot see priced would be
  // a list of places they cannot buy.
  return activeDestinations().filter((destination) => wanted.has(destination.crs));
}
function inShortlist(crs) {
  return shortlistCodes.includes(crs);
}
function toggleShortlist(crs) {
  if (inShortlist(crs)) {
    shortlistCodes = shortlistCodes.filter((code) => code !== crs);
    if (shortlistLimit) shortlistLimit.textContent = "";
  } else {
    if (shortlistCodes.length >= SHORTLIST_LIMIT) {
      // Said on the page rather than to a screen reader alone: a control that
      // stops responding with no explanation is the one thing a reader cannot
      // act on, and the strip is where they are already looking.
      const message = "The shortlist holds " + SHORTLIST_LIMIT + " places. Remove one to add another.";
      setShortlistStatus(message);
      if (shortlistLimit) shortlistLimit.textContent = message;
      return;
    }
    shortlistCodes = [...shortlistCodes, crs];
    if (shortlistLimit) shortlistLimit.textContent = "";
  }
  setShortlistStatus("");
  renderShortlist();
  writeUrl();
}
function setShortlistStatus(text) {
  if (shortlistStatus) shortlistStatus.textContent = text;
}
// One place on the strip. The price is the reason the place is there, so it
// travels with the name; the journey facts did too, and made every chip three
// lines tall on a phone, where the strip is the only thing between the reader
// and the fold. The place's own row still has them.
function shortlistRow(destination) {
  const item = document.createElement("li");
  item.className = "shortlist-chip";
  // A chip is a way back to the row it came from, and a row is not a
  // destination, so it is a button: a link here would be either a fragment
  // that goes nowhere or a javascript: URL, and both are worse than saying
  // what the control does.
  const name = document.createElement("button");
  name.type = "button";
  name.className = "shortlist-name";
  name.textContent = destination.name;
  name.title = "Show " + destination.name + " in the list above";
  name.addEventListener("click", () => focusDestinationRow(destination.crs));
  const price = document.createElement("span");
  price.className = "shortlist-price";
  price.textContent = money(priceOf(destination));
  const drop = document.createElement("button");
  drop.type = "button";
  drop.className = "shortlist-drop";
  // A drawn cross, not the letter x and not an emoji: it is the only icon on
  // the page, and it is drawn at the same weight as the rule it sits on.
  drop.innerHTML = '<svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true" focusable="false">'
    + '<path d="M1 1 L11 11 M11 1 L1 11" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>';
  drop.setAttribute("aria-label", "Remove " + destination.name + " from the shortlist");
  drop.addEventListener("click", () => toggleShortlist(destination.crs));
  item.append(name, price, drop);
  return item;
}

function focusDestinationRow(crs) {
  const row = document.querySelector('#rows tr[data-crs="' + crs + '"]');
  if (!row) return;
  row.scrollIntoView({ block: "center", behavior: "smooth" });
  const link = row.querySelector(".buy");
  if (link) link.focus({ preventScroll: true });
}

function renderShortlist() {
  if (!shortlist) return;
  const kept = shortlisted();
  // A row whose fare the reader can no longer see priced -- a different ticket
  // mode -- leaves the list rather than sitting in it as a name with no price.
  shortlistCodes = kept.map((destination) => destination.crs);
  shortlistList.replaceChildren(...kept.map(shortlistRow));
  const empty = kept.length === 0;
  if (shortlistEmpty) shortlistEmpty.hidden = !empty;
  if (shortlistBar) shortlistBar.hidden = false;
  for (const control of [shortlistClear, shortlistCopy, shortlistShareBox]) {
    if (control) control.hidden = empty;
  }
  if (shortlistShare) {
    shortlistShare.textContent = empty
      ? ""
      : "Shortlist of " + kept.length + (kept.length === 1 ? " place" : " places") + " from " +
        DATA.origin.name + ". " + window.location.href;
  }
  if (shortlistBox) shortlistBox.hidden = true;
  if (shortlistStatus && !shortlistStatus.textContent) {
    shortlistStatus.textContent = kept.length ? kept.length + " shortlisted." : "";
  }
  renderShortlistPicker();
}

// The select that replaces twenty buttons. Its options are the destinations on
// the page the reader is looking at, so it is never longer than the list above
// it, and a place already on the strip is not offered again: the list is the
// record of what is held, and a second way to add the same place is a control
// that silently does nothing.
function renderShortlistPicker() {
  if (!shortlistPick) return;
  const onPage = Array.from(document.querySelectorAll("#rows tr[data-crs]"))
    .map((row) => row.dataset.crs)
    .filter((crs) => !inShortlist(crs));
  const wanted = shortlistPick.value;
  shortlistPick.replaceChildren();
  const prompt = document.createElement("option");
  prompt.value = "";
  prompt.textContent = onPage.length ? "Add a place from this page" : "Nothing on this page to add";
  shortlistPick.append(prompt);
  for (const crs of onPage) {
    const row = document.querySelector('#rows tr[data-crs="' + crs + '"]');
    const name = row ? row.querySelector(".station-name") : null;
    const option = document.createElement("option");
    option.value = crs;
    option.textContent = name ? name.textContent : crs;
    shortlistPick.append(option);
  }
  shortlistPick.disabled = onPage.length === 0;
  // Re-rendering the table rebuilds the select, and a reader who had it open
  // has not chosen yet; the placeholder is the honest state to return to.
  shortlistPick.value = wanted && onPage.includes(wanted) ? wanted : "";
}
function shortlistText() {
  const kept = shortlisted();
  const what = unit() === "party" ? "for the two of us" : "each";
  const lines = [
    "Shortlist from " + DATA.origin.name + " (" + DATA.origin.crs + ")",
    "Budget: \u00a3" + budgetNumber.value + " " + what,
  ];
  if (DATA.serviceDate) lines.push("Date: " + humanDate(DATA.serviceDate));
  for (const destination of kept) {
    const changes = destination.changes === null || destination.changes === undefined
      ? "changes unknown"
      : destination.changes === 0 ? "no change" : destination.changes + " change(s)";
    const time = DATA.hasJourneys
      ? (destination.minutes === null || destination.minutes === undefined ? "no service found" : duration(destination.minutes))
      : "no timetable in this build";
    lines.push("- " + destination.name + " (" + destination.crs + "): " + money(priceOf(destination)) +
      " " + what + ", " + fareName(destination) + ", " + time + ", " + changes);
  }
  lines.push("A shortlist of places, not a booking: no train is chosen and no ticket is held.");
  return lines.join("\\n");
}
if (shortlistCopy) {
  shortlistCopy.addEventListener("click", async () => {
    const text = shortlistText();
    const show = () => {
      // Never claim a copy that did not happen, the same rule the row copy
      // follows: a denied clipboard shows the text instead.
      shortlistBox.value = text;
      shortlistBox.hidden = false;
      shortlistStatus.textContent = "Could not copy automatically. The list is shown below to copy by hand.";
    };
    if (!navigator.clipboard || !navigator.clipboard.writeText) return show();
    try {
      await navigator.clipboard.writeText(text);
      shortlistStatus.textContent = "Shortlist copied.";
    } catch (error) {
      show();
    }
  });
}
// The select is the way in. It is a change rather than a click because a
// <select> has no click to hang a handler on that means anything, and because
// the browser's own list is the control: one tap to open, one to choose, and
// the choice is made in the same gesture the reader used to look at the page.
if (shortlistPick) {
  shortlistPick.addEventListener("change", () => {
    const crs = shortlistPick.value;
    if (!crs || inShortlist(crs)) return;
    toggleShortlist(crs);
    // Focus goes back to the control rather than staying on an option that no
    // longer exists: renderShortlist() rebuilds the option list, and a select
    // left with no matching option drops to its placeholder silently.
    shortlistPick.focus({ preventScroll: true });
  });
}
if (shortlistClear) {
  shortlistClear.addEventListener("click", () => {
    shortlistCodes = [];
    setShortlistStatus("");
    renderShortlist();
    writeUrl();
  });
}

// The address is the search (S05). A reader who has already decided a budget
// and a ticket type, then refreshes, or shares the tab, or presses Back, must
// land on the search they made rather than the one the page was built with.
// Two rules keep it readable. The budget is always written, because it is the
// decision the page exists to record and a shared link without it would not be
// the search that was made; every other value equal to the page default is left
// out entirely. And the facets are repeated short keys rather than one encoded
// blob. The same query is what a picker option carries, so a link to another
// origin is the same search from a different station (S06) -- one function
// writes both, so they cannot drift apart.
const DEFAULT_MODE = document.querySelector('input[name="ticketMode"]:checked').value;
function stateQuery() {
  const params = new URLSearchParams();
  params.set("budget", budgetNumber.value);
  const mode = ticketMode();
  if (mode !== DEFAULT_MODE) params.set("mode", mode);
  if (unit() === "party") params.set("party", "2");
  if (!noCard()) params.set("card", railcardSelect.value);
  const types = Array.from(selectedDestinationTypes()).sort();
  for (const type of types) params.append("types", type);
  if (currentPage > 1) params.set("page", String(currentPage));
  // One repeated short key per place rather than a joined list: URLSearchParams
  // would percent-encode the commas, and a shared link is meant to be readable.
  for (const code of shortlistCodes) params.append("short", code);
  return params.toString();
}

// A decision is one history entry. Dragging the budget is one decision however
// many events it fires, so the budget replaces the address while the pointer
// is down and pushes once it settles; every other control is a single click
// and pushes at once.
let budgetUrlTimer = null;
function writeUrl({ budget = false } = {}) {
  if (!budget) {
    writeUrlNow(true);
    return;
  }
  if (budgetUrlTimer) clearTimeout(budgetUrlTimer);
  writeUrlNow(false);
  budgetUrlTimer = setTimeout(() => {
    budgetUrlTimer = null;
    writeUrlNow(true);
  }, 700);
}
const STATE_KEYS = ["budget", "mode", "party", "card", "types", "page", "short"];
function writeUrlNow(push) {
  const url = new URL(window.location.href);
  // Only this page's own keys are rewritten. A shared link can carry someone
  // else's parameters -- a campaign tag, a referrer -- and dropping them
  // because the reader moved the budget would quietly break whatever they
  // were for.
  for (const key of STATE_KEYS) url.searchParams.delete(key);
  for (const [key, value] of new URLSearchParams(stateQuery())) url.searchParams.append(key, value);
  if (url.href === window.location.href) return;
  history[push ? "pushState" : "replaceState"](null, "", url);
}

// Read the address back into the controls. A value naming a control this page
// does not have is ignored rather than guessed at: a link from another station
// can carry a mode or a facet this origin has no fares for, and the reader
// should get the page's own defaults for those, not a blank table.
function readState() {
  const params = new URLSearchParams(window.location.search);
  return {
    budget: Number(params.get("budget")),
    mode: params.get("mode"),
    unit: params.get("party") === "2" ? "party" : null,
    railcard: params.get("card"),
    types: params.getAll("types"),
    page: Number(params.get("page")) || 1,
    // Only codes this page can price are kept: a shared link must not put a
    // place in the list that the reader cannot see a fare for.
    short: params.getAll("short").map((code) => code.trim().toUpperCase()).filter(Boolean),
  };
}
function applyState(state) {
  if (Number.isFinite(state.budget) && state.budget > 0) setBudget(state.budget);
  for (const input of document.querySelectorAll('input[name="ticketMode"]')) {
    if (input.value === state.mode) input.checked = true;
  }
  for (const input of document.querySelectorAll('input[name="unit"]')) {
    if (input.value === state.unit) input.checked = true;
  }
  // A card code that arrived on a link is applied only when this page prices
  // that card. A link from another station can name a card this origin's feed
  // holds nothing for, and the reader should get this page's own default rather
  // than a control reading as a card they hold.
  const wanted = state.railcard && railcards[state.railcard] ? state.railcard : "";
  railcardSelect.value = wanted;
  for (const input of destinationTypeInputs) {
    input.checked = input.value !== "all" && state.types.includes(input.value);
  }
  const all = destinationTypeInputs.find((input) => input.value === "all");
  if (all && !all.checked && !destinationTypeInputs.some((input) => input.value !== "all" && input.checked)) {
    all.checked = true;
  }
  currentPage = Math.max(1, state.page);
  shortlistCodes = state.short.filter(pricedHere);
}
// Whether this page can price that station at all, in any of its ticket modes.
function pricedHere(code) {
  return [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations]
    .some((list) => (list || []).some((destination) => destination.crs === code));
}
window.addEventListener("popstate", () => {
  // Back is a decision the reader already made, so it is applied without
  // writing the address again: re-writing it here would make the entry Back
  // just left unreachable, and the control would never come back.
  applyState(readState());
  render();
});

// S22: a result set that just changed under the reader starts again at its
// first page, because the cheapest destinations are the ones a narrowed
// search wants to see first and page 4 of the previous set is not where they
// are now. The count and the page position are both re-announced by render().
budget.addEventListener("input", () => { setBudget(budget.value); currentPage = 1; render(); writeUrl({ budget: true }); });
budgetNumber.addEventListener("input", () => { setBudget(budgetNumber.value); currentPage = 1; render(); writeUrl({ budget: true }); });
budgetField.addEventListener("click", (event) => {
  if (event.target === budgetField || event.target.classList.contains("budget-prefix")) {
    budgetNumber.focus();
    budgetNumber.select();
  }
});
railcardSelect.addEventListener("change", () => {
  try {
    if (noCard()) window.localStorage.removeItem(RAILCARD_MEMORY + DATA.origin.crs);
    else window.localStorage.setItem(RAILCARD_MEMORY + DATA.origin.crs, railcardSelect.value);
  } catch (error) {
    // Storage blocked. The choice still applies to this page and still travels
    // in the URL; it just will not be there next time.
  }
  currentPage = 1;
  render();
  writeUrl();
});
for (const input of destinationTypeInputs) {
  input.addEventListener("change", () => {
    const all = destinationTypeInputs.find((candidate) => candidate.value === "all");
    if (input.value === "all") {
      for (const candidate of destinationTypeInputs) candidate.checked = candidate === all;
    } else if (input.checked) {
      all.checked = false;
    } else if (destinationTypeInputs.filter((candidate) => candidate.value !== "all").every((candidate) => !candidate.checked)) {
      all.checked = true;
    }
    currentPage = 1;
    render();
    writeUrl();
  });
}
for (const radio of document.querySelectorAll('input[name="unit"]')) radio.addEventListener("change", () => { currentPage = 1; render(); writeUrl(); });
for (const radio of document.querySelectorAll('input[name="ticketMode"]')) radio.addEventListener("change", () => { currentPage = 1; render(); writeUrl(); });
previousPage.addEventListener("click", () => { currentPage -= 1; render(); writeUrl(); window.scrollTo({ top: 0, behavior: "smooth" }); });
nextPage.addEventListener("click", () => { currentPage += 1; render(); writeUrl(); window.scrollTo({ top: 0, behavior: "smooth" }); });
applyState(readState());
if (clearTypes) clearTypes.addEventListener("click", clearDestinationTypes);
provenance();
sizeBudgetField();
render();
</script>
__ANALYTICS__
</body>
</html>
"""


_CHOOSER_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
__SHARED_THEME__
<title>Train fares up to &pound;__BUDGET__ &middot; __TITLE_SUFFIX_HTML__</title>
<style>
__SHARED_CSS__
  /* The same heading over the same sentence as a station page. When this route
     offers a choice, its slot is a field to type a station into; when the
     release priced exactly one station there is no choice to make, so the
     heading names that station instead, and the origin clause carries whichever
     of the two it is (recommendation 2, 30 September 2026). It is the same
     slot in the same place either way, which is what makes the pages read as
     one product.
     Nothing else here is a control, so this route has no filter bar: the two
     things a reader can change are the two gaps in the heading, and the list
     below answers them. A one-station release has one gap, because the second
     already has an answer. */
  /* No width of its own either: see the token in the shared block. */
  h1 { margin: 0 0 .7rem; }
  .sub { margin: 0 0 .3rem; }
  #orderingNote { margin: 0 0 1.6rem; }
  /* One cell per station, as many across as the column holds: at 78rem a
     single row per station put a station's own count most of a screen away
     from its name, so the three facts of a row stopped being one thing. The
     cells are a fixed measure rather than a share of the width, so one
     station does not stretch to fill the page and a full-network build reads
     as columns of names rather than a very long list. */
  /* The space above the list belongs to the list, not to the note that used to
     sit there: a one-station release carries no ordering note, and the list
     then sat 5px under its sentence (finding, 30 September 2026). Adjacent
     margins collapse, so the chooser's spacing is unchanged. */
  #picks { list-style: none; margin: 1.6rem 0 0; padding: 0;
           display: grid; grid-template-columns: repeat(auto-fill, minmax(min(20rem, 100%), 1fr));
           gap: 0 1.5rem; }
  #picks a { display: flex; justify-content: space-between; gap: 1rem; min-height: 44px; padding: .55rem .4rem;
             color: var(--accent); text-decoration: none; border-bottom: 1px solid var(--line); }
  #picks a:hover, #picks a:focus-visible { background: color-mix(in srgb, var(--accent) 8%, transparent); }
  #picks .code { color: var(--muted); font-variant-numeric: tabular-nums; }
  #picks .count { color: var(--muted); font-size: .85rem; white-space: nowrap; }
  #nomatch { color: var(--muted); margin-top: .75rem; }
  #capMessage { margin-top: .75rem; }
  p.tag { margin-top: 2rem; }
</style>
</head>
<body data-synthetic="__SYNTHETIC__">
__SYNTHETIC_BANNER__
__THEME_TOGGLE__
<main>
<h1 id="pageHeading">Train fares&#8288;<span class="heading-sep" aria-hidden="true">&middot;</span> <span class="heading-slot">up to <span class="heading-field" id="budgetField"><span class="budget-prefix">&pound;</span><input id="budgetNumber" type="number" min="1" max="500" step="1" value="__BUDGET__" inputmode="numeric" aria-label="Budget in pounds"></span>&#8288;<span class="heading-sep" aria-hidden="true">&middot;</span></span><br>__ORIGIN_CLAUSE__</h1>
__CHOOSER_INTRO__
__ORDERING_NOTE__
<ul id="picks"></ul>
<p id="nomatch" hidden></p>
<p id="capMessage" hidden></p>
<span id="pickStatus" class="sr-only" role="status"></span>
<p class="tag">__NOTE__</p>
</main>
<nav class="footnav"><a href="__BASE__/privacy/">Privacy</a></nav>
<script>
__LIST_KEYS__
const STATIONS = __STATIONS__;
// What the tab and every retitle say after the budget. A release that
// priced one station names it; a chooser says what it is for.
const TITLE_SUFFIX = __TITLE_SUFFIX_JS__;
const picks = document.getElementById("picks");
const nomatch = document.getElementById("nomatch");
const status = document.getElementById("pickStatus");
const pick = document.getElementById("originSearch");
const budgetNumber = document.getElementById("budgetNumber");
const originClause = document.getElementById("originClause");
const capMessage = document.getElementById("capMessage");
const CHOOSER_LIMIT = 40;
function matches(station, needle) {
  if (!needle) return true;
  return station.name.toLowerCase().includes(needle) ||
    station.crs.toLowerCase().startsWith(needle);
}
if (budgetNumber) {
  const storedBudget = new URLSearchParams(window.location.search).get("budget");
  if (storedBudget && Number(storedBudget) > 0) budgetNumber.value = storedBudget;
}
// C15: the heading is the page's most prominent promise, and it is written from
// the same resolved budget as the field, the tab title and every outgoing link,
// so the sentence a reader reads, the title their tab list shows, and the budget
// the page they open next is given cannot disagree.
function resolvedBudget() {
  return Math.max(1, Number(budgetNumber.value) || 1);
}
function syncChooserBudget() {
  const value = resolvedBudget();
  document.title = "Train fares up to £" + value + " · " + TITLE_SUFFIX;
  return value;
}

function render() {
  // A build that priced no stations has nothing to search over. The station
  // slot is the one thing on this page that cannot tell the truth here -- a
  // field that finds nothing is a control that lies -- so the whole "from ..."
  // clause leaves the heading and the page says why underneath it.
  if (!STATIONS.length) {
    if (originClause) originClause.hidden = true;
    picks.replaceChildren();
    nomatch.textContent = "Nothing is priced from any station in this build, so there is nothing to explore yet. " +
      "When the build prices journeys, this page lists every station it can start from.";
    nomatch.hidden = false;
    status.textContent = "0 stations listed";
    return;
  }
  // A one-station release has no field, so there is nothing to filter by
  // and the whole list is what it offers.
  const needle = pick ? pick.value.trim().toLowerCase() : "";
  const wanted = STATIONS.filter((station) => matches(station, needle));
  picks.replaceChildren();
  for (const station of wanted.slice(0, CHOOSER_LIMIT)) {
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = station.href;
    if (budgetNumber) {
      const url = new URL(link.href, window.location.href);
      url.searchParams.set("budget", resolvedBudget());
      link.href = url.pathname + url.search + url.hash;
    }
    const name = document.createElement("span");
    name.textContent = station.name;
    const code = document.createElement("span");
    code.className = "code";
    code.textContent = station.crs;
    const count = document.createElement("span");
    count.className = "count";
    count.textContent = station.destinations + (station.destinations === 1 ? " destination" : " destinations");
    link.append(name, code, count);
    item.append(link);
    picks.append(item);
  }
  if (capMessage) {
    capMessage.textContent = wanted.length > CHOOSER_LIMIT
      ? "Showing " + CHOOSER_LIMIT + " of " + wanted.length + " matching stations. Refine the search to see the rest."
      : "";
    capMessage.hidden = wanted.length <= CHOOSER_LIMIT;
  }
  // The no-match wording answers typed input; with an empty field it would
  // quote nothing back at the reader, so it stays hidden instead.
  if (wanted.length) {
    nomatch.hidden = true;
  } else if (needle) {
    nomatch.textContent = "We don't have prices from '" + pick.value.trim() +
      "'. Try the station's name or its three-letter code.";
    nomatch.hidden = false;
  } else {
    nomatch.hidden = true;
  }
  status.textContent = wanted.length + " station" + (wanted.length === 1 ? "" : "s") + " listed";
}

if (budgetNumber) {
  budgetNumber.addEventListener("input", () => {
    syncChooserBudget();
    render();
  });
}
// The field the whole page exists for, and the one a reader arrives at. It is
// focused rather than merely present: the caret in the heading is what says the
// page is waiting for a station, without a label above it saying so.
if (pick) pick.addEventListener("input", render);
// The budget slot has been clickable across its whole width since it was
// written, and the station slot is the other half of the same sentence: both
// are a gap in the heading that the reader fills in. Clicking the slot -- not
// the caret inside it, which is the reader placing the caret -- puts the field
// in focus, so the gap and the field are one target rather than a word beside
// a field. Nothing is selected: the value here is the reader's own query, and
// selecting it would lose it on the next keystroke.
const originField = document.getElementById("originField");
if (originField) {
  originField.addEventListener("click", (event) => {
    if (event.target !== originField) return;
    pick.focus();
  });
}
wireListKeys(pick, picks);
syncChooserBudget();
render();
if (pick) pick.focus();
</script>
__ANALYTICS__
</body>
</html>
"""


# The theme, before the first paint and on every route. The choice is read here
# and written to the root element rather than left to CSS, because a page that
# paints light and then repaints dark is a flash every reader sees on every
# visit. localStorage can throw -- a private window, a file:// page with storage
# blocked -- and then the reader simply gets the default, which is the point of
# having a default.
# The one drawn mark the chrome uses: a chevron that says "there is more behind
# this". It is authored SVG rather than a character for three reasons, and the
# third is the one that bit: a character has no stroke weight of its own and is
# styled differently by every installed font; it is not an element a stylesheet
# can size against the text it sits beside; and this mark used to be written as
# a CSS escape inside a Python string, where Python reads it first -- "\\25be"
# is octal 0o25 followed by the letters "be", so every station page rendered a
# control character and the word "be" on its refinements control. A drawn path
# cannot be misread by an interpreter, and it is the same shape on every
# machine.
# The two arrow keys a reader expects of a field that sits over a list, in one
# place because two routes now ask for them: the chooser's field over the
# station list, and a station page's picker over the same list. The options stay
# real anchors -- focus goes to the anchor itself, so the browser keeps its own
# naming, its own Enter, and its own open-in-a-new-tab -- which is why this is a
# dozen lines rather than a combobox implementation.
LIST_KEYS_JS = """function wireListKeys(field, list) {
  if (!field || !list) return;
  const links = () => Array.from(list.querySelectorAll("a"));
  field.addEventListener("keydown", (event) => {
    const first = links()[0];
    if (event.key === "ArrowDown" && first) {
      event.preventDefault();
      first.focus();
    }
  });
  list.addEventListener("keydown", (event) => {
    const options = links();
    if (event.key === "Escape" || (event.key === "ArrowUp" && document.activeElement === options[0])) {
      event.preventDefault();
      field.focus();
      return;
    }
    if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
    const step = event.key === "ArrowDown" ? 1 : -1;
    const next = options[options.indexOf(document.activeElement) + step];
    event.preventDefault();
    if (next) next.focus();
  });
}"""


CHEVRON = (
    '<svg class="chevron" viewBox="0 0 16 16" width="16" height="16"'
    ' aria-hidden="true" focusable="false">'
    '<path d="M4 6.25 8 10.25l4-4" fill="none" stroke="currentColor"'
    ' stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


SHARED_THEME = """<meta name="color-scheme" content="light dark">
<script>
  // The one thing this page does before it renders anything: say which palette
  // it is, so there is no flash of the other one. Dark unless the reader has
  // chosen otherwise, on this device, in this browser.
  (function () {
    var dark = true;
    try {
      var stored = localStorage.getItem("tbe-theme");
      if (stored) dark = stored === "dark";
    } catch (e) { /* storage blocked: the default stands */ }
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  })();
  // The control, wired once the body exists. It ships hidden and is revealed
  // here: a button that cannot do anything without this script is a control
  // that lies, which is the same defect as the Change button this replaced.
  //
  // It is revealed only if the stylesheet is here to be changed. A route that
  // fetches its stylesheet (ADR-0047) may not get it, and a switch that
  // rewrites an attribute no rule reads is the picker's "a control that opens
  // nothing" in a different dress: so the switch is taken away and the page
  // says what state it is in, which is the picker's failure mode one route
  // down. The marker is a token the stylesheet sets, so the answer is the
  // browser's own rather than a guess about whether a request is still in
  // flight -- and it is read again on load, because a stylesheet still
  // arriving when the body exists has not failed yet.
  function stylesheetArrived() {
    return getComputedStyle(document.documentElement)
      .getPropertyValue("--tbe-stylesheet").trim() !== "";
  }
  function wireTheme() {
    var root = document.documentElement;
    var toggle = document.getElementById("themeToggle");
    if (!toggle) return;
    var glyph = toggle.querySelector(".glyph");
    function paint(dark) {
      root.dataset.theme = dark ? "dark" : "light";
      toggle.setAttribute("aria-checked", String(dark));
      if (glyph) glyph.textContent = dark ? "\u263E" : "\u2600";
    }
    if (!stylesheetArrived()) {
      // Gone rather than inert, and the page says why it is plain text.
      toggle.remove();
      var note = document.getElementById("styleNote");
      if (note) {
        note.textContent = "This page\u2019s styling did not load, so it is plain"
          + " text. Every price, time and restriction on it is still here.";
        note.hidden = false;
      }
      return;
    }
    paint(root.dataset.theme === "dark");
    toggle.hidden = false;
    toggle.addEventListener("click", function () {
      var dark = root.dataset.theme !== "dark";
      paint(dark);
      try { localStorage.setItem("tbe-theme", dark ? "dark" : "light"); } catch (e) { /* remembered for this page only */ }
    });
  }
  document.addEventListener("DOMContentLoaded", wireTheme);
  window.addEventListener("load", function () {
    // A page that was styled all along is left exactly as it is, so this
    // only speaks when the switch is still hidden and the note still is.
    var toggle = document.getElementById("themeToggle");
    if (toggle && !toggle.hidden) return;
    var note = document.getElementById("styleNote");
    if (note && note.hidden) wireTheme();
  });
</script>"""

# The control itself, identical on every route, and outside <main> so it cannot
# join the page's one content landmark. The name is the state it holds and the
# glyph is decorative, so a screen reader says "Dark theme, switch, on" and a
# sighted reader sees a moon.
THEME_TOGGLE = (
    '<button id="themeToggle" type="button" role="switch" aria-checked="true" hidden>'
    '<span class="glyph" aria-hidden="true">&#9790;</span>'  # the moon, as an entity: HTML has no backslash escapes
    '<span class="sr-only">Dark theme</span></button>'
)


def with_shared(template: str) -> str:
    """Inline the shared stylesheet, theme block and control into one route.

    The site's promise is one file per route with no external asset, so the
    shared blocks are substituted at import time rather than fetched. A template
    that still holds a placeholder is a bug, so this says so rather than
    shipping a page with unstyled text or an unwired control.
    """
    filled = template.replace("__SHARED_CSS__", SHARED_CSS)
    if "__SHARED_CSS__" in filled:
        raise ValueError("the shared stylesheet was not inlined into this template")
    for placeholder, block, what in (
        ("__SHARED_THEME__", SHARED_THEME, "theme block"),
        ("__THEME_TOGGLE__", THEME_TOGGLE, "theme control"),
        ("__CHEVRON__", CHEVRON, "disclosure mark"),
        ("__LIST_KEYS__", LIST_KEYS_JS, "list keyboard block"),
    ):
        filled = filled.replace(placeholder, block)
        if placeholder in filled:
            raise ValueError(f"the shared {what} was not inlined into this template")
    return filled


PRIVACY = with_shared(_PRIVACY_TEMPLATE)
TEMPLATE = with_shared(_TEMPLATE)
CHOOSER_TEMPLATE = with_shared(_CHOOSER_TEMPLATE)
