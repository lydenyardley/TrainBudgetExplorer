"""The page's HTML, CSS, and JavaScript, as fill-in templates.

Pure strings: no imports, no logic beyond the __TOKEN__ placeholders that
render_page / render_privacy / render_chooser replace. The templates are the
page the reader sees; build_demo_page.py owns what fills them.
"""

PRIVACY = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Privacy</title>
<style>
  :root { --bg:#fff; --fg:#11161d; --muted:#5b6472; --accent:#14509b; --ochre:#a65d00; --line:#d0d5dd; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#14181d; --fg:#e7ebf0; --muted:#9aa4b2; --accent:#7db4f5; --ochre:#f0b35b; --line:#3a424c; }
  }
  body { margin:0; padding:1.5rem; max-width:40rem; background:var(--bg); color:var(--fg);
         font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }
  .brand { color: var(--ochre); font-size: .78rem; font-weight: 750; letter-spacing: .12em;
           text-transform: uppercase; margin: 0 0 1.25rem; }
  h1 { font-size: clamp(2rem, 5vw, 5rem); line-height: 1.35; letter-spacing: -.025em; font-weight: 700; }
  h2 { font-size:1.05rem; margin:1.5rem 0 .25rem; }
  p, li { margin:.4rem 0; }
  .muted { color:var(--muted); }
  a { color:var(--accent); }
  .back-link { display:inline-flex; align-items:center; min-height:44px; margin-bottom:1rem; }
</style>
</head>
<body>
<nav class="back-link"><a href="__BASE__/">Back to the station chooser</a></nav>
<p class="brand">Rail Budget</p>
<h1>Privacy</h1>
<p>This page works entirely in your browser. There is no account, no sign-in, and nothing you choose is stored anywhere: the budget you drag and the destination type you select never leave your device.</p>
<h2>What this site does not do</h2>
<ul>
  <li>No cookies are set by this site.</li>
  <li>No analytics run. If the operator later adds analytics, this page will name them here first.</li>
  <li>The site code does not intentionally collect visit data.</li>
</ul>
<h2>Ticket links</h2>
<p>Ticket buttons open the seller's own website in a new tab. Once you are there, that seller's privacy policy applies, not this page. This site receives no information back about whether you bought anything; if tracked links are ever switched on, the footer of the fare pages says so plainly.</p>
<h2>Hosting</h2>
<p>The site is static files served by the operator's chosen host. That host may process ordinary server logs, such as an IP address and requested pages, under its own privacy and retention policy. The site code itself does not set cookies or intentionally collect visit data.</p>  <h2>Contact</h2>  <p class="muted">__CONTACT__</p>


<p class="muted">__NOTE__</p>
</body>
</html>
"""



TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Where can we go from __ORIGIN__ for &pound;__BUDGET__?</title>
<style>
  :root { --bg: #fff; --fg: #11161d; --line: #d0d5dd; --muted: #5b6472; --accent: #14509b;
          --best: rgba(20, 80, 155, .07); --field: #fff; }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #14181d; --fg: #e7ebf0; --line: #3a424c; --muted: #9aa4b2; --accent: #7db4f5;
            --best: rgba(125, 180, 245, .12); --field: #1c2127; }
  }
  * { box-sizing: border-box; }
  body { margin: 0 auto; padding: clamp(1rem, 3vw, 2.25rem); max-width: 78rem;
         background: var(--bg); color: var(--fg);
         font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
  h1 { font-size: clamp(2rem, 5vw, 5rem);
       line-height: 1.35; letter-spacing: -.025em; font-weight: 700; }
  .sub { color: var(--muted); max-width: 75ch; }
  .heading-field { display: inline-flex; align-items: baseline; color: var(--accent);
                   border-bottom: 1px dashed color-mix(in srgb, var(--accent) 55%, transparent);
                   border-radius: .15rem .15rem 0 0; cursor: text; }
  .heading-field:focus-within { background: var(--best); border-bottom-style: solid; }
  .budget-prefix { user-select: none; }
  #budgetNumber { width: 2ch; min-width: 1ch; padding: .05rem .1rem; border: 0; outline: 0;
                  background: transparent; color: inherit; font: inherit; font-weight: inherit;
                  letter-spacing: inherit; appearance: textfield; }
  #budgetNumber::-webkit-inner-spin-button { appearance: none; }
  #changeOrigin { display: inline-flex; align-items: baseline; gap: .4rem; padding: .05rem .15rem;
                  border: 0; border-bottom: 1px dashed color-mix(in srgb, var(--accent) 55%, transparent);
                  border-radius: .15rem .15rem 0 0; background: transparent; color: var(--accent);
                  font: inherit; font-weight: inherit; letter-spacing: inherit; cursor: pointer; }
  #changeOrigin:hover, #changeOrigin:focus-visible { background: var(--best); border-bottom-style: solid; }
  #changeOrigin::after { content: "↕"; font-size: .5em; opacity: .65; }
  [hidden] { display: none !important; }
  .filter-bar { display: grid; grid-template-columns: minmax(16rem, 1.1fr) minmax(18rem, 1.3fr) minmax(17rem, 1fr);
                gap: 1.25rem 2rem; align-items: start; padding: 1.1rem 1.25rem 1.25rem;
                border: 1px solid var(--line); border-radius: .7rem; background: color-mix(in srgb, var(--field) 75%, transparent); }
  .filter-bar fieldset { border: 0; margin: 0; padding: 0; min-width: 0; }
  .filter-bar legend, .filter-label { display: block; margin-bottom: .5rem; font-size: .72rem;
                                      text-transform: uppercase; letter-spacing: .08em; color: var(--muted); font-weight: 700; }
  .filter-options { display: flex; flex-wrap: wrap; gap: .45rem; }
  .segmented label, .choice-chip { position: relative; display: inline-flex; align-items: center; min-height: 2.25rem;
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
  input[type=range] { width: 100%; accent-color: var(--accent); height: 2.25rem; margin: 0; }
  .filter-bar input[type=checkbox] { accent-color: var(--accent); }
  .railcard-choice { display: flex; align-items: center; gap: .5rem; min-height: 2.25rem; }
  .railcard-choice input { width: 1.1rem; height: 1.1rem; margin: 0; }
  .railcard-help { display: block; color: var(--muted); font-size: .8rem; }
  input[type=search], select { width: 100%; padding: .5rem; border: 1px solid var(--line); border-radius: .35rem;
                              font: inherit; color: var(--fg); background: var(--field); }
  /* Generous after the controls, tight onto its table: the summary belongs to
     the list below it, not to the panel above. */
  #summary { margin: 1.75rem 0 .5rem; font-weight: 600; }
  table { border-collapse: collapse; width: 100%; }
  th, td { text-align: left; padding: .5rem .4rem; border-bottom: 1px solid var(--line); }
  td[data-label]::before { content: none; }
  th { font-size: .8rem; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); }
  .toggle { border: 1px solid var(--line); background: var(--field); color: var(--accent);
            border-radius: .3rem; font: inherit; font-size: .85rem; padding: .3rem .55rem;
            margin-left: .75rem; cursor: pointer; position: relative; }
  /* Hit-slop: the visible mark stays small beside its neighbours, but the
     touch target reaches 44px past it. */
  .toggle::after { content: ""; position: absolute; inset: -6px; }
  :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: .2rem; }
  ::selection { background: color-mix(in srgb, var(--accent) 25%, transparent); }
  .toggle[aria-expanded=true] { border-color: var(--accent); }
  .buy { color: var(--accent); text-decoration: none; border-bottom: 1px solid currentColor;
         white-space: nowrap; position: relative; }
  .buy::after { content: ""; position: absolute; inset: -11px -4px; }
  tr.detail td { background: var(--best); border-bottom: 1px solid var(--line); }
  tr.detail ul { margin: 0; padding-left: 1.1rem; }
  tr.detail li { font-variant-numeric: tabular-nums; }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  tr.best td { background: var(--best); }
  .restriction { font-size: .78rem; color: var(--muted); }
  .restriction[data-status="restricted"] { color: #9a6700; }
  .restriction[data-status="unrestricted"] { color: var(--muted); }
  .heritage-proof { display: block; margin-top: .15rem; font-size: .75rem; font-weight: 400; color: var(--muted); }
  .heritage-proof a { color: inherit; text-underline-offset: .15em; }
  .heritage-proof a:hover, .heritage-proof a:focus-visible { color: var(--accent); }
  .tag { font-size: .75rem; color: var(--muted); }
  /* A chip's count is part of its label, so it sits inside the chip and is
     never the only thing carrying the type's name. */
  .chipcount { color: var(--muted); font-variant-numeric: tabular-nums; font-size: .8em; }
  #typeRule { display: block; margin: .35rem 0 0; }
  #clearTypes { margin-top: .35rem; }
  /* S19: the condition is the sentence; the record is folded under it. */
  .feed-record { margin-top: .2rem; font-size: .72rem; }
  .feed-record summary { cursor: pointer; color: var(--muted); }
  .feed-record dl { margin: .2rem 0 0; display: grid; grid-template-columns: auto 1fr; gap: 0 .4rem; }
  .feed-record dt { color: var(--muted); }
  .feed-record dd { margin: 0; font-variant-numeric: tabular-nums; }
  /* S23: an absence the feed can name is not the same as a zero. */
  td.missing { color: var(--muted); font-style: italic; }
  .empty-actions { display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; }
  /* S26: the shortlist reads as a list, not a table, because it is a handful of
     places to compare rather than a result set to scan. */
  #shortlist { margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid var(--line); }
  #shortlist h2 { font-size: 1.05rem; margin: 0 0 .25rem; }
  #shortlistList { list-style: none; margin: .5rem 0; padding: 0; }
  #shortlistList li { display: flex; flex-wrap: wrap; align-items: baseline; gap: .25rem .75rem;
                     padding: .4rem 0; border-bottom: 1px solid var(--line); }
  .shortlist-name { font-weight: 600; }
  .shortlist-facts { color: var(--muted); font-variant-numeric: tabular-nums; }
  .empty-actions .toggle { min-height: 44px; }
  #railcardDrawer { width: min(30rem, calc(100% - 1rem)); max-width: none; height: 100dvh;
                    max-height: none; margin: 0 0 0 auto; padding: 1.25rem;
                    border: 0; border-left: 1px solid var(--line); color: var(--fg);
                    background: var(--field); box-shadow: -1rem 0 2.5rem rgba(0,0,0,.18); }
  #railcardDrawer::backdrop { background: rgba(0,0,0,.38); }
  .drawer-head { display: flex; align-items: start; justify-content: space-between; gap: 1rem; }
  .drawer-head h2 { margin: 0; font-size: 1.25rem; }
  .drawer-close { min-width: 2.75rem; min-height: 2.75rem; }
  .drawer-status { margin: 1.25rem 0; padding: .8rem; border: 1px solid var(--line);
                    border-radius: .5rem; background: var(--best); }
  .drawer-status[data-state=blocked], .drawer-status[data-state=unavailable] { border-color: #b7791f; }
  #railcardRule { padding: .8rem; border: 1px solid var(--line); border-left-color: var(--accent); background: var(--bg);
                  font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .85rem; }
  #railcardDrawer dl { display: grid; grid-template-columns: max-content 1fr; gap: .55rem .8rem; }
  #railcardDrawer dt { color: var(--muted); }
  #railcardDrawer dd { margin: 0; font-variant-numeric: tabular-nums; }
  #empty { color: var(--muted); }
  #more { color: var(--muted); font-size: .9rem; }
  .copybox { width: 100%; font: inherit; font-size: .9rem; color: var(--fg); background: var(--field);
             border: 1px solid var(--line); border-radius: .35rem; padding: .5rem; resize: vertical; }
  .sr-only { position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden;
             clip-path: inset(50%); white-space: nowrap; border: 0; }
  #originPicker { margin: .75rem 0 1rem; }
  .origin-picker-label { display: block; margin-bottom: .35rem; font-size: .8rem;
                         text-transform: uppercase; letter-spacing: .04em; color: var(--muted); }
  #originPicker input[type=search] { width: 100%; max-width: 24rem; padding: .5rem; border: 1px solid var(--line);
                                     border-radius: .35rem; font: inherit; color: var(--fg); background: var(--field); }
  #originPicks { list-style: none; margin: .5rem 0 0; padding: 0; max-width: 24rem; }
  #originPicks a { display: flex; justify-content: space-between; gap: .75rem; min-height: 44px; padding: .55rem .4rem;
                   color: var(--accent); text-decoration: none; border-bottom: 1px solid var(--line); }
  #originPicks a:hover, #originPicks a:focus-visible { background: color-mix(in srgb, var(--accent) 8%, transparent); }
  #originPicks .code { color: var(--muted); }
  #originNomatch { color: var(--muted); margin-top: .5rem; }
  /* The unpriced-origin message replaces the intro, so it is page-size text in
     the normal foreground colour: a finding, not a footnote. */
  .unpriced { margin: 0 0 1.25rem; }
  #unpriced a { color: var(--accent); text-decoration: none; border-bottom: 1px solid currentColor; }
  footer { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--line); color: var(--muted); font-size: .85rem; }
  .method { margin-top: 1rem; }
  .method summary { min-height: 44px; display: flex; align-items: center; color: var(--accent); cursor: pointer; }
  .footnav a { color: inherit; }
  @media (max-width: 44rem) { .footnav { min-height: 44px; display: flex; align-items: center; } }
  code { font-size: .95em; }
  /* On a phone the table reflows into stacked rows, because a six-column table
     pushes the ticket action off-screen (ADR-0019). The markup stays a real
     table for desktop and assistive technology; only the display changes, and
     flex wrapping means no cell can sit outside the viewport however long a
     station name or fare code is. */
  /* 44rem, not 40: measured, the six-column table needs ~700px before its three
     row actions stop wrapping onto a second line, so the stacked layout keeps
     the band between 640 and 704px that the table cannot hold. */
  @media (max-width: 62rem) {
    .filter-bar { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .destination-filter { grid-column: 1 / -1; }
  }
  @media (max-width: 44rem) {
    body { padding: 1rem .75rem; }
    .filter-bar { grid-template-columns: 1fr; gap: 1rem; padding: 1rem; }
    .destination-filter { grid-column: auto; }
    table, tbody { display: block; }
    thead { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden;
             clip-path: inset(50%); white-space:nowrap; border:0; }
    tr { display: flex; flex-wrap: wrap; align-items: baseline; gap: .1rem .75rem;
         padding: .5rem 0; border-bottom: 1px solid var(--line); }
    td[data-label]::before { content: attr(data-label) " "; color: var(--muted); font-size: .78rem;
                             text-transform: uppercase; letter-spacing: .04em; }
    td:first-child { flex: 1 1 100%; padding-left: 0; font-weight: 600; }
    td.num { text-align: left; }
    td:last-child { margin-left: auto; }
    tr.detail td { flex: 1 1 100%; padding: .5rem 0; }
    tr.best { background: var(--best); }
  }
</style>
</head>
<body>
<h1 id="pageHeading">Where can we go for under <span class="heading-field" id="budgetField"><span class="budget-prefix" aria-hidden="true">&pound;</span><input id="budgetNumber" type="number" min="1" max="__MAXPOUNDS__" step="1" value="__BUDGET__" inputmode="numeric" aria-label="Budget in pounds"></span> from <button id="changeOrigin" type="button" aria-expanded="false" aria-controls="originPicker" aria-label="Change starting station"><span>__ORIGIN__</span></button></h1>
<p class="sub" id="pageIntro">Every destination reachable by train for the budget in the heading, with the fastest journey time and the number of changes.</p>
<p class="sub" id="firstUse">This page is about one station: <b>Change</b> in the heading moves to another one. Everything below narrows the destinations from here.</p>
<p id="unpriced" class="unpriced" hidden></p>

<div id="originPicker" hidden>
  <span class="origin-picker-label">Start from a different station</span>
  <input id="originSearch" type="search" placeholder="Type part of a name or its three-letter code" autocomplete="off"
         aria-describedby="originStatus">
  <span id="originStatus" class="sr-only" role="status"></span>
  <ul id="originPicks"></ul>
  <p id="originNomatch" hidden></p>
</div>

<section class="filter-bar" aria-label="Journey and destination filters">
  <fieldset class="budget-track">
    <legend class="sr-only">Budget</legend>
    <label class="sr-only" for="budget">Budget in pounds</label>
    <input id="budget" type="range" min="1" max="__MAXPOUNDS__" step="1" value="__BUDGET__" aria-describedby="budgetHint">
    <span class="tag" id="budgetHint">Drag to change the budget in the heading.</span>
  </fieldset>
  <fieldset class="ticket-filter">
    <legend>Ticket type</legend>
    <div class="filter-options segmented">
      <label><input type="radio" name="ticketMode" value="return" checked> Return</label>
      <label><input type="radio" name="ticketMode" value="single"> Single</label>
      <label><input type="radio" name="ticketMode" value="anytime"> Anytime Day Return</label>
    </div>
  </fieldset>
  <fieldset class="party-filter">
    <legend>The budget covers</legend>
    <div class="filter-options">
      <label class="railcard-choice"><input type="radio" name="unit" value="adult" checked> One adult</label>
      <label class="railcard-choice"><input type="radio" name="unit" value="party"> Two adults</label>
      <label class="railcard-choice" id="railcardChoice"><input id="railcard" type="checkbox"> Two Together railcard</label>
    </div>
    <span class="railcard-help" id="railcardHelp">Eligibility is checked against each fare.</span>
  </fieldset>
  <fieldset class="destination-filter">
    <legend>Destination type</legend>
    <div class="filter-options" id="destinationTypes" role="group" aria-label="Destination type">__DESTINATION_TYPE_FILTERS__</div>
  <span class="tag" id="typeRule">More than one type shows destinations of any of them. The count on each is how many are inside the budget now.</span>
  <button id="clearTypes" class="toggle" type="button" hidden>Clear destination types</button>
  </fieldset>
</section>

<p id="summary" role="status" aria-live="polite"></p>  <p class="tag" id="priceSource" hidden></p>
  <p class="tag" id="buildMetadata" hidden></p>
<table>
  <thead><tr><th scope="col">Station</th><th scope="col" class="num">Price</th><th scope="col" class="num">Time</th><th scope="col" class="num">Changes</th><th scope="col">Fare</th><th scope="col">Conditions</th><th scope="col">Tickets</th></tr></thead>
  <tbody id="rows"></tbody>
</table>
<section id="shortlist" aria-labelledby="shortlistHeading">
  <h2 id="shortlistHeading">Shortlist</h2>
  <p class="tag">Places you are considering from this station. This is a list to compare and share, not a booking: no train is chosen and no ticket is held.</p>
  <p id="shortlistEmpty" class="tag">Nothing shortlisted yet. Use Shortlist on a row to add a place.</p>
  <ul id="shortlistList" hidden></ul>
  <p id="shortlistShare" class="tag"></p>
  <p class="tag"><button id="shortlistCopy" class="toggle" type="button" hidden>Copy the shortlist</button> <button id="shortlistClear" class="toggle" type="button" hidden>Clear the shortlist</button></p>
  <textarea id="shortlistBox" class="copybox" rows="6" readonly hidden aria-label="Shortlist to copy"></textarea>
  <span id="shortlistStatus" role="status" class="sr-only"></span>
</section>
<div id="empty" hidden></div>
<p id="more" hidden></p>
<nav id="pagination" hidden aria-label="Results pages">
  <button id="previousPage" type="button" class="toggle">Previous</button>
  <span id="pageStatus" role="status"></span>
  <button id="nextPage" type="button" class="toggle">Next</button>
</nav>

<dialog id="railcardDrawer" aria-labelledby="railcardDrawerTitle" aria-describedby="railcardReason">
  <div class="drawer-head">
    <h2 id="railcardDrawerTitle">Two Together eligibility</h2>
    <button id="railcardClose" class="toggle drawer-close" type="button" aria-label="Close railcard details">Close</button>
  </div>
  <p id="railcardDestination" class="tag"></p>
  <p id="railcardReason" class="drawer-status"></p>
  <dl>
    <dt>Standard fare</dt><dd id="railcardStandard"></dd>
    <dt>Discounted fare</dt><dd id="railcardDiscounted"></dd>
    <dt>DTD minimum</dt><dd id="railcardMinimum"></dd>
  </dl>
  <h3>Exact DTD rule</h3>
  <p id="railcardRule"></p>
</dialog>

<footer>
  <div id="attribution" hidden></div>
  <p>__NOTE__</p>
  <p>Cheapest displayable standard-class fare found in the feed for the selected ticket type. ITX placeholder fares are excluded. Advance singles are shown when they are the cheapest single, but they require a qualifying train and their price and availability can change.</p>
  <p>The times on this page are options in the timetable, not a booking. Unrestricted fares are valid on the services listed; an Advance single is valid only on a qualifying train, so no train is picked for you.</p>
  <details class="method">
    <summary>How these prices were calculated</summary>
    <p id="pricingBasis"></p>
    <p id="feedCoverage" class="tag"></p>
    <p id="railcardNote"></p>
    <p id="linkNote" hidden></p>
    <p class="tag" id="provenance"></p>
    <p id="disclosure" hidden></p>
  </details>
  <nav class="footnav"><a href="__BASE__/">All stations</a> <a href="__BASE__/privacy/">Privacy</a></nav>
  <p id="copyStatus" role="status" class="sr-only"></p>
</footer>

<script>
const DATA = __DATA__;
const rows = document.getElementById("rows");
const budget = document.getElementById("budget");const budgetNumber = document.getElementById("budgetNumber");
const budgetField = document.getElementById("budgetField");
const railcard = document.getElementById("railcard");


const railcardChoice = document.getElementById("railcardChoice");
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
const railcardDrawer = document.getElementById("railcardDrawer");
const railcardClose = document.getElementById("railcardClose");
const clearTypes = document.getElementById("clearTypes");

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
function activeDestinations() {
  return DATA[MODE_LISTS[ticketMode()]] || [];
}
function modeCount(mode) {
  return (DATA[MODE_LISTS[mode]] || []).length;
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
  if (railcard.checked && destination.railcardPence !== null) {
    const cardTotal = destination.railcardPence * (party ? 2 : 1);
    return Math.min(base, cardTotal);
  }
  return base;
}
// S15: Two Together is a railcard for a named number of adults travelling
// together, so it is a constraint on the party rather than a discount a solo
// reader can tick. The number is the feed's own railcard record, not a rule
// this page invented, and a box that cannot apply is disabled rather than
// left there to be ticked and silently ignored.
function syncRailcardParty() {
  const party = DATA.railcardParty;
  // No railcard record in the feed, or nothing eligible for one, is not this
  // rule's business: provenance() has already stood the control down and owns
  // the sentence beside it.
  if (!party || !DATA.railcardAvailable) return;
  const applies = unit() === "party";
  if (!applies && railcard.checked) railcard.checked = false;
  railcard.disabled = !applies;
  const choice = document.getElementById("railcardChoice");
  if (choice) choice.dataset.state = applies ? "ready" : "needs-a-pair";
  const help = document.getElementById("railcardHelp");
  if (help) {
    const covers = "The railcard in this feed covers " + party.minAdults + " to " + party.maxAdults +
      " adults travelling together";
    help.textContent = applies
      ? covers + ", so it prices a journey for the party rather than for one reader. " +
        DATA.railcardEligibleCount + " destinations receive a lower price with it; Card details on any row " +
        "shows the minimum fare and the conditions."
      : covers + ", so it prices a journey for the party rather than for one reader. " +
        "Choose “Two adults” to use it.";
  }
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
  const all = destinationTypeInputs.find((input) => input.value === "all");
  for (const input of destinationTypeInputs) {
    if (input.value === "all") continue;
    const present = offered.has(input.value);
    const chip = input.closest("label");
    if (chip) chip.hidden = !present;
    if (!present && input.checked) {
      input.checked = false;
      if (all) all.checked = true;
    }
  }
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
function emptyModeMessage() {
  const labels = modeLabels();
  const mode = ticketMode();
  const elsewhere = ["return", "single", "anytime"]
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
function renderCoverage() {
  const coverage = document.getElementById("feedCoverage");
  if (!coverage || DATA.rawFareDestinationCount === undefined) return;
  const mode = ticketMode();
  const lead = mode === "single"
    ? DATA.singleDestinations.length + " displayable outbound single fares are available in this mode." +
      (DATA.singleJourneyNote ? " " + DATA.singleJourneyNote : "")
    : mode === "anytime"
      ? DATA.anytimeDestinations.length + " reviewed unrestricted Anytime Day Return fares are available in this mode."
      : DATA.rawFareDestinationCount + " standard-return destinations were found in the feed" + droppedFromFeed() + "." +
        (DATA.destinations.length
          ? " Raise the budget to include more of the " + DATA.destinations.length + " displayable destinations."
          : "");
  coverage.textContent = lead + classifiedNote();
}
function droppedFromFeed() {
  const dropped = [];
  if (DATA.excludedItxCount) dropped.push(DATA.excludedItxCount + " had only ITX placeholder fares");
  if (DATA.unnameableFareCount) dropped.push(DATA.unnameableFareCount + " had no station name in the feed");
  return dropped.length ? "; " + dropped.join(" and ") + ", and are not shown" : ", and all are shown";
}
function classifiedNote() {
  if (DATA.unclassifiedDestinationCount) {
    return " " + DATA.unclassifiedDestinationCount + " priced destinations carry no reviewed " +
      "destination type, so no type chip on this page can select them.";
  }
  return DATA.locationTypeReviewed ? " Every destination on this page carries a reviewed type." : "";
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
  why.textContent = "No destinations within " + money(cap) + " " + what + typeLabel() + ".";
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
  if (unit() === "adult" && DATA.railcardAvailable) {
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
  document.title = "Where can we go from " + DATA.origin.name + " for £" + budgetNumber.value + "?";
  const available = activeDestinations();
  // Before any price is read: the railcard changes the price of every row, and
  // a card ticked for a party of one is a number no reader could buy.
  syncRailcardParty();
  // Before the filter is read, not after: a chip the active list cannot support
  // must not be part of what the filter is asked to match.
  syncDestinationTypeChips();
  // An unpriced page has no budget conversation: provenance() has already
  // stood the controls and the table down, and anything this function wrote
  // ("Nothing inside this budget") would contradict the page's own first
  // sentence. So it does nothing at all -- but that is the only case where it
  // says nothing.
  if (!DATA.destinations.length && !DATA.singleDestinations.length && !DATA.anytimeDestinations.length) return;
  renderCoverage();
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
    renderShortlist();
    return;
  }
  const ceiling = budgetCeiling();
  budget.max = String(ceiling);
  budgetNumber.max = String(ceiling);
  if (Number(budget.value) > ceiling) setBudget(ceiling);
  const cap = Number(budget.value) * 100;
  const wantedTypes = selectedDestinationTypes();
  const wanted = available.filter(
    (d) => priceOf(d) <= cap && matchesType(d, wantedTypes)
  );
  budgetNumber.value = budget.value;
  sizeBudgetField();
  updateChipCounts(available, cap);
  rows.replaceChildren();

  const pageCount = Math.max(1, Math.ceil(wanted.length / PAGE_SIZE));
  currentPage = Math.min(Math.max(1, currentPage), pageCount);
  const pageItems = wanted.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  for (const destination of pageItems) {
    const row = document.createElement("tr");
    if (destination === wanted[0]) row.className = "best";
    const cells = [
      [destination.name + " (" + destination.crs + ")", "", "Station"],
      [money(priceOf(destination)), "num", "Price"],
    ];
    if (DATA.hasJourneys) {
      // S23: a dash said nothing about which of three different absences this
      // is. The fare is real either way, so the cell names the absence and
      // says so in its tooltip too.
      const missing = destination.journeyState !== "found";
      const tone = missing ? "num missing" : "num";
      cells.push([missing ? "No service" : duration(destination.minutes), tone, "Time"]);
      cells.push([missing ? "Unknown" : String(destination.changes), tone, "Changes"]);
    }
    // An Advance single is train-specific whatever the feed calls it, so it
    // replaces the other labels rather than qualifying them: a reader must not
    // read a walk-up label on a price that only exists on one train.
    const fareLabel = destination.isAdvance
      ? "Advance single — choose a qualifying train; price and availability can change"
      : destination.restrictionCode
        ? "Restricted fare — check seller conditions"
        : destination.quality === "outbound single"
          ? "Standard outbound single"
          : destination.quality === "unrestricted Anytime Day Return"
            ? "Unrestricted Anytime Day Return"
            : "Standard return fare";
    // S19: the reader needs the fare in words beside the price. The codes are
    // the feed's own vocabulary, so they move into the expandable record below
    // rather than competing with the sentence in the cell.
    cells.push([fareLabel, "", "Fare"]);
    row.dataset.crs = destination.crs;
    for (const [text, className, label] of cells) {
      const cell = document.createElement("td");
      cell.dataset.label = label;
      cell.textContent = text;
      if (className) cell.className = className;
      if (label === "Station" && destination.heritageSites?.length) {
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
      row.append(cell);
    }
    const restriction = document.createElement("td");
    restriction.className = "restriction";
    restriction.dataset.label = "Conditions";
    const restricted = Boolean(destination.restrictionCode);
    restriction.dataset.status = restricted ? "restricted" : "unrestricted";
    // S19: what the reader has to know to rule the fare in or out, in
    // sentences. The code, the ticket and the route are below it, folded away.
    const readable = document.createElement("span");
    readable.className = "condition";
    readable.textContent = restricted
      ? (destination.restrictionDescription || "This fare carries a restriction code; check the seller's conditions before buying.")
      : "No travel conditions on this fare in the feed.";
    restriction.title = restricted
      ? (destination.restrictionDescription || "This fare has a restriction code; check the seller before buying.")
      : "No fare restriction code is attached to this fare.";
    restriction.append(readable, feedRecord(destination));
    row.append(restriction);
    cellWithLinks(row, destination, wanted);
    rows.append(row);
  }

  const what = unit() === "party" ? "for the two of us" : "each";
  // An unpriced origin has no budget conversation to have, so the summary
  // stays empty rather than implying the budget filtered something out.
  summary.textContent = available.length && wanted.length
    ? wanted.length + (wanted.length === 1 ? " destination" : " destinations") + " within " + money(cap) + " " + what
    : available.length ? "No destinations within " + money(cap) + " " + what : "";
  empty.hidden = wanted.length > 0;
  renderEmpty(available, wanted, cap, what);
  more.hidden = true;
  pagination.hidden = pageCount <= 1;
  pageStatus.textContent = "Page " + currentPage + " of " + pageCount + " of " + wanted.length +
    (wanted.length === 1 ? " result" : " results");
  previousPage.disabled = currentPage === 1;
  nextPage.disabled = currentPage === pageCount;
  renderShortlist();
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
  details.append(summary, list);
  return details;
}

function cellWithLinks(row, destination, wanted) {
  // The ticket link sits on the row rather than inside the expander: buying is
  // the action, and hiding it behind a second click loses the click. The
  // expander carries the journeys, which are what a reader checks first.
  const cell = document.createElement("td");
  cell.dataset.label = "Tickets";
  const link = document.createElement("a");
  link.className = "buy";
  link.href = destination.link.url;
  link.rel = destination.link.rel;
  link.target = "_blank";
  link.textContent = "Tickets";
  link.title = destination.link.label + " search for " + destination.crs;
  cell.append(link);
  if (destination.departures.length) {
    const toggle = document.createElement("button");
    toggle.className = "toggle";
    toggle.type = "button";
    toggle.textContent = destination.departures.length + " times";
    toggle.setAttribute("aria-expanded", "false");
    toggle.addEventListener("click", () => toggleDetail(row, destination, toggle));
    cell.append(toggle);
  }
  // The ticket link is the plain one by default and carries no journey, so the
  // row hands the reader the four things the seller will ask for (ADR-0018).
  const cardDetails = document.createElement("button");
  cardDetails.className = "toggle";
  cardDetails.type = "button";
  cardDetails.textContent = "Card details";
  cardDetails.setAttribute("aria-label", "Two Together eligibility for " + destination.name);
  cardDetails.addEventListener("click", () => showRailcardDetails(destination));
  cell.append(cardDetails);
  const copy = document.createElement("button");
  copy.className = "toggle";
  copy.type = "button";
  copy.textContent = "Copy";
  copy.setAttribute("aria-label", "Copy the journey details for " + destination.name);
  copy.title = "Copy the from, to, date and party size for this row";
  copy.addEventListener("click", () => copyJourney(row, destination, copy));
  cell.append(copy);
  // S26: saving a place to compare later. A toggle with its pressed state
  // announced, not a link, because nothing is booked and nothing navigates.
  const save = document.createElement("button");
  save.type = "button";
  save.className = "toggle shortlist-toggle";
  save.setAttribute("aria-pressed", "false");
  save.setAttribute("aria-label", "Shortlist " + destination.name);
  save.addEventListener("click", () => toggleShortlist(destination.crs));
  cell.append(save);
  row.append(cell);
}

function showRailcardDetails(destination) {
  const details = destination.railcard;
  document.getElementById("railcardDestination").textContent =
    destination.name + " (" + destination.crs + ") · " + destination.quality;
  const status = document.getElementById("railcardReason");
  status.dataset.state = details.state;
  status.textContent = details.title + ". " + details.reason;
  document.getElementById("railcardStandard").textContent = money(destination.adultPence) + " per adult";
  document.getElementById("railcardDiscounted").textContent =
    details.pricePence === null ? "Not available" : money(details.pricePence) + " per adult";
  document.getElementById("railcardMinimum").textContent =
    details.minimumFarePence === null ? "Not listed for " + destination.ticket : money(details.minimumFarePence);
  // The rule record lives once in DATA.railcardRules; the row carries its
  // key, because repeating the record per row cost 388KB on the heaviest
  // real page (audit B3).
  const rule = details.rule ? DATA.railcardRules[details.rule] : null;
  document.getElementById("railcardRule").textContent = rule
    ? rule.text
    : "No Two Together railcard rule applies because the railcard is not in this feed.";
  railcardDrawer.showModal();
}
railcardClose.addEventListener("click", () => railcardDrawer.close());
railcardDrawer.addEventListener("click", (event) => {
  if (event.target === railcardDrawer) railcardDrawer.close();
});

function toggleDetail(row, destination, toggle) {
  const open = toggle.getAttribute("aria-expanded") === "true";
  toggle.setAttribute("aria-expanded", String(!open));
  if (open) {
    row.nextElementSibling?.remove();
    return;
  }
  const detail = document.createElement("tr");
  detail.className = "detail";
  const cell = document.createElement("td");
  cell.colSpan = columnCount();
  const list = document.createElement("ul");
  for (const option of destination.departures) {
    const item = document.createElement("li");
    item.textContent = clock(option.depart) + " depart, " + clock(option.arrive) + " arrive, " +
      (option.changes ? option.changes + " change(s)" : "no change");
    list.append(item);
  }
  cell.append(list);
  detail.append(cell);
  row.after(detail);
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
  const parts = [
    "Origin " + DATA.origin.name + " (" + DATA.origin.crs + ")",
    available.length + (ticketMode() === "single" ? " outbound single destinations" : ticketMode() === "anytime" ? " unrestricted Anytime Day Return destinations" : " return destinations") + " in the feed",
  ];
  if (DATA.hasJourneys) {
    parts.push(DATA.serviceDate ? "services on " + DATA.serviceDate : "typical services in the feed");
  } else {
    parts.push("no timetable loaded, so no times are shown");
  }
  if (DATA.locationTypeSource) parts.push("destination types: " + DATA.locationTypeSource);
  if (DATA.railcardInFeed !== undefined) {
    railcard.disabled = !DATA.railcardAvailable;
    const help = document.getElementById("railcardHelp");
    if (!DATA.railcardInFeed || !DATA.railcardAvailable) {
      // If the control is hidden, its help must be hidden with it. Leaving the
      // sentence visible made it look like help for the remaining party-size
      // radios even though it described a control the reader could not see.
      help.textContent = "";
      help.hidden = true;
      if (railcardChoice) railcardChoice.hidden = true;
    } else {
      help.textContent = DATA.railcardEligibleCount + " destinations receive a lower Two Together price; Card details show RR conditions.";
      help.hidden = false;
      if (railcardChoice) railcardChoice.hidden = false;
    }
  }
  document.getElementById("provenance").textContent = parts.join(" \u00b7 ");
  document.getElementById("pricingBasis").textContent = DATA.pricingBasis
    ? DATA.pricingBasis + ". Use the ticket-type control to switch between return and outbound single fares, then use the budget filter to narrow the list."
    : "";
  renderCoverage();
  document.getElementById("railcardNote").textContent = DATA.railcardNote;
  // What the reader has to do for themselves when the link is the plain one.
  if (DATA.linkNote) {
    const linkNote = document.getElementById("linkNote");
    linkNote.textContent = DATA.linkNote;
    linkNote.hidden = false;
  }
  if (DATA.dateNote) {
    const note = document.createElement("p");
    note.textContent = DATA.dateNote;
    document.getElementById("railcardNote").after(note);
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
}

const MONTHS = ["January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];

// Formatted from the ISO string by hand rather than through Date: new
// Date("2026-10-05") is parsed as UTC midnight, which prints as the 4th for any
// reader behind UTC. A copied date that is off by a day is worse than none.
function humanDate(iso) {
  const parts = iso.split("-").map(Number);
  return parts[2] + " " + MONTHS[parts[1] - 1] + " " + parts[0];
}

// What the reader has to type on the seller's own site, because the ticket link
// carries nothing (ADR-0018). The railcard is named only when the party price is
// what is on screen, and it is named as something to tick rather than sent
// anywhere, because no seller accepts it in a link (ADR-0014).
function journeyText(destination) {
  const together = unit() === "party";
  const lines = [
    "From: " + DATA.origin.name + " (" + DATA.origin.crs + ")",
    "To: " + destination.name + " (" + destination.crs + ")",
  ];
  if (DATA.serviceDate) lines.push("Date: " + humanDate(DATA.serviceDate));
  lines.push("Passengers: " + (together ? DATA.adults + " adults" : "1 adult"));
  if (together && DATA.railcardAvailable && destination.railcardPence !== null) {
    lines.push("Two Together discount is not sent to the seller: confirm the railcard on their site");
  }
  return lines.join("\\n");
}

function showCopyBox(row, text) {
  const next = row.nextElementSibling;
  if (next && next.classList.contains("detail")) next.remove();
  const detail = document.createElement("tr");
  detail.className = "detail";
  const cell = document.createElement("td");
  cell.colSpan = columnCount();
  const box = document.createElement("textarea");
  box.className = "copybox";
  box.readOnly = true;
  box.rows = 5;
  box.value = text;
  box.setAttribute("aria-label", "Journey details to copy");
  cell.append(box);
  detail.append(cell);
  row.after(detail);
  box.focus();
  box.select();
}

async function copyJourney(row, destination, button) {
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
    status.textContent = "Could not copy automatically. The details are shown under the row.";
    showCopyBox(row, text);
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
  const originSearch = document.getElementById("originSearch");
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

  function setPicker(open) {
    changeOrigin.setAttribute("aria-expanded", String(open));
    originPicker.hidden = !open;
    if (open) {
      renderPicks();
      originSearch.focus();
    } else {
      // Escape is a keyboard exit, and focus returns to the control that
      // opened the picker rather than dropping to the top of the page.
      changeOrigin.focus();
    }
  }

  changeOrigin.addEventListener("click", () => {
    setPicker(changeOrigin.getAttribute("aria-expanded") !== "true");
  });
  originPicker.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setPicker(false);
  });
  originSearch.addEventListener("input", renderPicks);
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
const shortlist = document.getElementById("shortlist");
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
  } else {
    if (shortlistCodes.length >= SHORTLIST_LIMIT) {
      // Said rather than silently ignored: a control that stops responding with
      // no explanation is the one thing a reader cannot act on.
      setShortlistStatus("The shortlist holds " + SHORTLIST_LIMIT + " places. Remove one to add another.");
      return;
    }
    shortlistCodes = [...shortlistCodes, crs];
  }
  setShortlistStatus("");
  renderShortlist();
  writeUrl();
}
function setShortlistStatus(text) {
  if (shortlistStatus) shortlistStatus.textContent = text;
}
function shortlistRow(destination) {
  const item = document.createElement("li");
  const name = document.createElement("span");
  name.className = "shortlist-name";
  name.textContent = destination.name + " (" + destination.crs + ")";
  const facts = document.createElement("span");
  facts.className = "shortlist-facts";
  const price = money(priceOf(destination));
  const changes = destination.changes === null || destination.changes === undefined
    ? "changes unknown"
    : destination.changes === 0 ? "no change" : destination.changes + " change(s)";
  const time = DATA.hasJourneys
    ? (destination.minutes === null || destination.minutes === undefined
      ? "no service found"
      : duration(destination.minutes))
    : "no timetable in this build";
  facts.textContent = price + (unit() === "party" ? " for the two of us" : " each") + " \\u00b7 " + time + " \\u00b7 " + changes;
  const drop = document.createElement("button");
  drop.type = "button";
  drop.className = "toggle";
  drop.textContent = "Remove";
  drop.setAttribute("aria-label", "Remove " + destination.name + " from the shortlist");
  drop.addEventListener("click", () => toggleShortlist(destination.crs));
  item.append(name, facts, drop);
  return item;
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
  if (shortlistList) shortlistList.hidden = empty;
  for (const control of [shortlistClear, shortlistCopy]) {
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
  for (const row of document.querySelectorAll("#rows tr[data-crs]")) {
    const button = row.querySelector(".shortlist-toggle");
    if (!button) continue;
    const on = inShortlist(row.dataset.crs);
    button.setAttribute("aria-pressed", String(on));
    button.textContent = on ? "Shortlisted" : "Shortlist";
  }
}
function shortlistText() {
  const kept = shortlisted();
  const what = unit() === "party" ? "for the two of us" : "each";
  const lines = [
    "Shortlist from " + DATA.origin.name + " (" + DATA.origin.crs + ")",
    "Budget: \\u00a3" + budgetNumber.value + " " + what,
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
      " " + what + ", " + time + ", " + changes);
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
// Two rules keep it readable: a value equal to the page default is left out
// entirely, and the facets are repeated short keys rather than one encoded
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
  if (railcard.checked) params.set("card", "1");
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
    railcard: params.get("card") === "1",
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
  // A card=1 that arrived on a link from a page where the reader had chosen a
  // pair is not applied to a party of one: the control is disabled in that
  // case, and a checkbox the page disables must not read as checked.
  railcard.checked = state.railcard && unit() === "party";
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
railcard.addEventListener("change", () => { currentPage = 1; render(); writeUrl(); });
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


CHOOSER_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Where can we go for &pound;__BUDGET__? Pick your station</title>
<style>
  :root { --bg: #fff; --fg: #11161d; --line: #d0d5dd; --muted: #5b6472; --accent: #14509b; --ochre: #a65d00;
          --field: #fff; }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #14181d; --fg: #e7ebf0; --line: #3a424c; --muted: #9aa4b2; --accent: #7db4f5; --ochre: #f0b35b;
            --field: #1c2127; }
  }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 1.5rem; max-width: 40rem;
         background: var(--bg); color: var(--fg);
         font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
  h1 { font-size: 1.5rem; margin: 0 0 .25rem; }
  .sub { color: var(--muted); margin: 0 0 1.25rem; }
  .brand { color: var(--ochre); font-size: .78rem; font-weight: 750; letter-spacing: .12em;
           text-transform: uppercase; margin: 0 0 1.25rem; }
  label.caption { display: block; font-size: .8rem; text-transform: uppercase;
                  letter-spacing: .04em; color: var(--muted); margin-bottom: .35rem; }
  input[type=search] { width: 100%; padding: .6rem; border: 1px solid var(--line); border-radius: .35rem;
                       font: inherit; color: var(--fg); background: var(--field); }
  #picks { list-style: none; margin: .5rem 0 0; padding: 0; }
  #picks a { display: flex; justify-content: space-between; gap: 1rem; min-height: 44px; padding: .5rem .4rem;
             color: var(--accent); text-decoration: none; border-bottom: 1px solid var(--line); }
  #picks a:hover, #picks a:focus-visible { background: color-mix(in srgb, var(--accent) 8%, transparent); }
  #picks .code { color: var(--muted); font-variant-numeric: tabular-nums; }
  #picks .count { color: var(--muted); font-size: .85rem; white-space: nowrap; }
  #nomatch { color: var(--muted); margin-top: .5rem; }
  #chooserBudget { width: 100%; padding: .6rem; border: 1px solid var(--line); border-radius: .35rem;
                   font: inherit; color: var(--fg); background: var(--field); margin-bottom: 1rem; }
  p.tag { color: var(--muted); font-size: .85rem; margin-top: 2rem; }
  .footnav { margin-top: 1.5rem; }
  .footnav a { color: var(--muted); font-size: .85rem; }
  .sr-only { position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden;
             clip-path: inset(50%); white-space: nowrap; border: 0; }
</style>
</head>
<body>
<h1>Where can we go for &pound;__BUDGET__?</h1>
<p class="brand">Rail Budget</p>
<p class="sub">Pick the station you are starting from, and see every destination reachable by train inside the budget.</p>
<p class="sub">Ordered by how many destinations this download prices from each station &mdash; not by how busy it is, and not by how near it is.</p>
<label class="caption" for="chooserBudget">Starting budget</label>
<input id="chooserBudget" type="number" min="1" max="500" step="1" value="__BUDGET__" inputmode="numeric">
<label class="caption" for="pick">Your station</label>
<input id="pick" type="search" placeholder="Type part of a name or its three-letter code" autocomplete="off"
       aria-describedby="pickStatus">
<span id="pickStatus" class="sr-only" role="status"></span>
<ul id="picks"></ul>
<p id="nomatch" hidden></p>
<p id="capMessage" class="tag" hidden></p>
<p class="tag">__NOTE__</p>
<nav class="footnav"><a href="__BASE__/privacy/">Privacy</a></nav>
<script>
const STATIONS = __STATIONS__;
const picks = document.getElementById("picks");
const nomatch = document.getElementById("nomatch");
const status = document.getElementById("pickStatus");
const pick = document.getElementById("pick");
const chooserBudget = document.getElementById("chooserBudget");
const capMessage = document.getElementById("capMessage");
const CHOOSER_LIMIT = 40;
function matches(station, needle) {
  if (!needle) return true;
  return station.name.toLowerCase().includes(needle) ||
    station.crs.toLowerCase().startsWith(needle);
}
if (chooserBudget) {
  const storedBudget = new URLSearchParams(window.location.search).get("budget");
  if (storedBudget && Number(storedBudget) > 0) chooserBudget.value = storedBudget;
}

function render() {
  // A build that priced no stations has nothing to search over, so the field
  // stands down and the page says so, rather than addressing a typed input
  // the reader never made.
  if (!STATIONS.length) {
    pick.hidden = true;
    document.querySelector("label[for='pick']").hidden = true;
    picks.replaceChildren();
    nomatch.textContent = "Nothing is priced from any station in this build, so there is nothing to explore yet. " +
      "When the build prices journeys, this page lists every station it can start from.";
    nomatch.hidden = false;
    status.textContent = "0 stations listed";
    return;
  }
  const needle = pick.value.trim().toLowerCase();
  const wanted = STATIONS.filter((station) => !needle || matches(station, needle));
  picks.replaceChildren();
  for (const station of wanted.slice(0, CHOOSER_LIMIT)) {
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = station.href;
    if (chooserBudget) {
      const url = new URL(link.href, window.location.href);
      url.searchParams.set("budget", Math.max(1, Number(chooserBudget.value) || 1));
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

if (chooserBudget) {
  chooserBudget.addEventListener("input", () => {
    document.title = "Where can we go for £" + Math.max(1, Number(chooserBudget.value) || 1) + "? Pick your station";
    render();
  });
}
// The field the whole page exists for. It had no listener, so a typed name or
// code changed nothing on screen while the list below sat there looking like a
// search result.
pick.addEventListener("input", render);
render();
pick.focus();
</script>
__ANALYTICS__
</body>
</html>
"""
