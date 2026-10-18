"""The page's HTML, CSS, and JavaScript, as fill-in templates.

Fill-in templates over the page's own CSS and JS files under page/, and no
logic beyond the __TOKEN__ placeholders that
render_page / render_privacy / render_chooser replace. The templates are the
page the reader sees; build_demo_page.py owns what fills them.

SHARED_CSS is the one source for the palette, spacing, focus ring, links,
navigation and disclosure styles every route uses (S39). It is inlined into
each template at the bottom of this module, so a route's own block holds only
what is genuinely its own.
"""

from pathlib import Path

# The markers a built page introduces its inlined payload with. They live beside
# the templates that write them, because the line and the name of the line are
# one fact. Every reader of a built page imports these instead of spelling them
# again: eight spellings existed on 18 October 2026, seven agreed, and the byte
# measurer held the stale one, so it reported every page as carrying no payload
# and passed. `tests/test_page_assets.py` holds each template to its marker, so a
# template that renames the line fails there rather than in a measurement.
PAYLOAD_MARKER = "window.TBE_DATA = "
CHOOSER_MARKER = "window.TBE_CHOOSER_STATIONS = "

# Every stylesheet and every script this site ships, as a file of its own: an
# editor sees them, `node --check` reads them, and a search for a symbol finds
# one answer rather than a copy inside a string. They are read at import, so the
# bytes of a shared asset are the bytes of the file. The read normalizes line
# endings, because a checkout that hands back CRLF must not rewrite every page
# of the release.
_PAGE_ASSETS = Path(__file__).with_name("page")


def _page_file(name: str) -> str:
    """One of the page's own CSS or JS files, as the page inlines it."""
    return (_PAGE_ASSETS / name).read_bytes().decode("utf-8").replace("\r\n", "\n")


SHARED_CSS = _page_file("shared.css")

# Both routes' scripts are read here and written out as one hashed asset each,
# so a page no longer carries a copy of its own code (12 October 2026 audit,
# T1 and T10). The station route's script was measured byte-identical on every
# page of a 24-page sample -- 149,377 bytes of it -- and the chooser's is the
# same shape at one copy. The parts below are still concatenated in this order,
# because the asset is still one script rather than several modules.

# The station route's script, one file per panel under page/station/, in the
# order they are concatenated below.
#
# The order is the one thing a split can get wrong, because the page ships one
# script rather than several modules: a top-level statement that reads a const
# declared in another file only runs if that file has already been
# concatenated. So the payload leads, the panel that owns a control a later
# statement registers a listener on comes before the file holding that
# statement, and the file with the statements themselves -- the wiring -- is
# last. The panels whose declarations a statement reads are named first for
# that reason, not for any order of their own.
STATION_SCRIPT_PARTS = (
    "station/payload.js",
    "station/railcards.js",
    "station/budget.js",
    "station/service-day.js",
    "station/filters.js",
    "station/ticket-modes.js",
    "station/format.js",
    "station/table.js",
    "station/row-cells.js",
    "station/fare-panel.js",
    "station/row-actions.js",
    "station/provenance.js",
    "station/picker.js",
    "station/shortlist.js",
    "station/url-state.js",
    "station/wiring.js",
)

# The station route's own stylesheet, which used to sit in its <style>
# block beside the shared one. The two are still one string, because a
# station page's CSS is byte-identical on every station page -- measured,
# not assumed: the same 34.6 KB on all 2,712 pages of a full-network
# build -- so it is written once as a hashed asset and fetched, and a
# route whose copy does not arrive says so and loses the theme switch
# rather than offering a control that cannot change a palette the page
# has not got (ADR-0033's boundary, ADR-0047).
STATION_CSS = _page_file("station.css")


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
""" + _page_file("privacy.css") + """</style>
</head>
<body data-synthetic="__SYNTHETIC__">
__SYNTHETIC_BANNER__
<nav class="back-link"><a href="__BASE__/">Back to the station list</a></nav>
__THEME_TOGGLE__
<main>
<h1>Privacy</h1>
<p>This page works entirely in your browser. There is no account, no sign-in, and nothing you choose is stored on a server by this site.</p>
__BUILT_LINE__
<h2>What this site does</h2>
<ul>
__PRACTICES__</ul>
<h2>What stays in the address bar</h2>
<p>A fare page keeps your search in the web address, so that a refresh, the Back button, or a link you share all return the same results. That search &mdash; the budget, the ticket type, whether the budget covers one adult or two, which railcard you chose, the day the times are for, the destination types you selected, and any places you shortlisted &mdash; is written into the page's own address as short query parameters. It is never sent to this site, because this site has no server to receive it. It does leave your device in two ways that are worth naming plainly:</p>
<ul>
<li>the host serving these static files sees the full address, including that search, in its ordinary request logs; and</li>
<li>if you share or bookmark such an address, the whole search travels with it, so a link you hand to somebody carries your budget, any railcard you chose and the places you shortlisted to whoever opens it.</li>
</ul>
<p>Nothing else you type here is transmitted. Clearing the address bar's query parameters and reloading returns a fare page to its default search.</p>
<h2>Ticket links</h2>
<p>Ticket buttons open the seller's own website in a new tab. Once you are there, that seller's privacy policy applies, not this page. This site receives no information back about whether you bought anything; if tracked links are ever switched on, the fare pages will say so in their footer.</p>
<h2>Hosting</h2>
<p>The site is static files served by the operator's chosen host. That host may process ordinary server logs, such as an IP address and requested pages, under its own privacy and retention policy.</p>
<h2>Contact</h2>
<p class="muted">__CONTACT__</p>
</main>
<footer>
__NOTE__
<nav class="footnav"><a href="__BASE__/">Station list</a></nav>
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
<h1 id="pageHeading" aria-label="Train fares up to &pound;__BUDGET__ from __ORIGIN__">Train fares <span class="heading-slot">up to <span class="heading-field" id="budgetField"><span class="budget-prefix">&pound;</span><input id="budgetNumber" type="number" min="0" max="__MAXPOUNDS__" step="1" value="__BUDGET__" inputmode="numeric" aria-label="Budget in pounds"></span></span><br><span class="heading-lead">from</span> __ORIGIN_CONTROL__</h1>
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
  <p id="originCap" hidden></p>
  <p id="originNomatch" hidden></p>
  <span id="originStatus" class="sr-only" role="status"></span>
</div>
<!-- ADR-0047: shown only when the stylesheet did not arrive. The page is
     plain text in that state, and says so rather than leaving a reader to
     wonder why this station looks unlike every other one. -->
<p class="sub" id="styleNote" hidden></p>
<!-- The same failure mode one route down for the route's own code: the table
     below is listed by it, so a page whose copy did not arrive shows an empty
     table with no explanation unless something says so. The script tag's
     onerror reveals this rather than the script itself, because the script is
     what is missing. -->
<p class="sub" id="scriptNote" hidden>The list of destinations needs this page's code, which did not load, so the table below is empty.</p>
<p id="unpriced" class="unpriced" hidden></p>

<section class="filter-bar" aria-label="Journey and destination filters">
  <fieldset class="budget-track">
    <legend class="sr-only">Budget</legend>
    <label class="sr-only" for="budget">Budget in pounds</label>
    <input id="budget" type="range" min="0" max="__MAXPOUNDS__" step="1" value="__BUDGET__" aria-describedby="budgetHint">
    <span class="tag" id="budgetHint">Drag to change the budget in the heading. It stops at the highest fare <span id="budgetHintMode">in the list on screen</span> — <span id="budgetCeiling">__CEILING_NOTE__</span>.</span>
  </fieldset>
  <div class="more-filters" id="moreFilters" data-open="false">
    <button type="button" class="more-filters-toggle" id="moreFiltersToggle"
            aria-expanded="false" aria-controls="moreFiltersPanel">
      <span class="more-filters-label">Filter this list</span>
      <span class="tag" id="filterState"></span>
      __CHEVRON__
    </button>
    <div class="more-filters-panel" id="moreFiltersPanel">
  <fieldset class="ticket-filter">
    <legend>Ticket type</legend>
    <div class="filter-options segmented">
      <label><input type="radio" name="ticketMode" value="cheapest" checked> Cheapest available</label>
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
  <span class="tag" id="typeRule">Each count is how many destinations of that type are inside the budget now.</span>
  <p id="facetNotice" class="tag" role="status" hidden></p>
  <button id="clearTypes" class="toggle" type="button" hidden>Show all destination types</button>
  </fieldset>
    </div>
  </div>
<!-- The day the times are for. It is not a filter and is not inside the filter
     panel: it does not hide rows, it changes what the Time and Changes columns
     report. It is on the always-visible strip beside the budget rather than
     between the count and the table, because the count belongs to the table it
     counts and ADR-0040 measures the gap between them (57px on the real page,
     against a 100px budget, once a 44px control was added to it). Above the
     count it costs nothing. Hidden when the build carried no week to pick from,
     so a page with one day shows no control that could only offer the day
     already on screen. -->
<div class="service-day" id="serviceDayBar" hidden>
  <label for="serviceDay">Times for</label>
  <select id="serviceDay" aria-describedby="serviceDayHelp"></select>
  <span class="tag" id="serviceDayHelp"></span>
</div>
</section>

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
<!-- The shortlist is only the dock. It was a section here as well as the
     strip at the foot of the screen, so a reader who had chosen two places
     read their list twice and had two Clear buttons to work out which was
     which; the chips here repeated the dock's own rows. Everything it held --
     the copy, the share, the limit message and the live region -- is in the
     dock now, and this gap between the count and the table is a gap again. -->
<!-- The count line belongs to the table below it, not to the panel above: on
     the real Grantham page it sat 205px above the first row, with six
     provenance paragraphs between them (finding, 29 September 2026). -->
<p id="summary" role="status" aria-live="polite"></p>
<table>
  <thead><tr><th scope="col" class="hold">Shortlist</th><th scope="col">Station</th><th scope="col" class="num">Price</th><th scope="col" class="num">Time</th><th scope="col" class="num">Changes</th><th scope="col">Fare type</th><th scope="col">Tickets</th></tr></thead>
  <tbody id="rows"></tbody>
</table>
<div id="empty" hidden></div>
<p id="more" hidden></p>
<!-- How the list was put together. It says what the rows in the table are, so
     it reads as part of the table rather than as a note above it, and it was
     19px between the count and the first row on a laptop and 58px on a phone
     for a sentence a reader only wants once they have decided to read. -->
<p class="tag" id="modeNote"></p>
<nav id="pagination" hidden aria-label="Results pages">
  <button id="previousPage" type="button" class="toggle">Previous</button>
  <span id="pageStatus" role="status"></span>
  <button id="nextPage" type="button" class="toggle">Next</button>
</nav>

</main>

<!-- The dock is the shortlist at the foot of the screen. It is hidden until a
     place is on it, so a page with nothing shortlisted carries no dock and
     gives its rows the whole window. The row headings name the four facts
     because a reader comparing two places is reading columns, and the
     columns need the same names the results table gives them. -->
<aside class="shortlist-dock" id="shortlistDock" hidden aria-label="Shortlisted destinations">
  <div class="shortlist-dock-head">
    <span class="shortlist-label">Shortlist</span>
    <span class="tag" id="shortlistDockCount"></span>
    <p class="tag" id="shortlistLimit"></p>
    <button id="shortlistCopy" class="toggle" type="button" hidden>Copy</button>
    <details class="shortlist-share" id="shortlistShareBox" hidden>
      <summary>Share</summary>
      <p id="shortlistShare"></p>
      <textarea id="shortlistBox" class="copybox" rows="6" readonly hidden aria-label="Shortlist to copy"></textarea>
    </details>
    <button id="shortlistDockClear" class="toggle" type="button">Clear</button>
    <span id="shortlistStatus" role="status" class="sr-only"></span>
  </div>
  <table>
    <thead><tr><th scope="col">Station</th><th scope="col" class="num">Price</th>
      <th scope="col" class="num">Time</th><th scope="col" class="num">Changes</th>
      <th scope="col"><span class="sr-only">Remove</span></th></tr></thead>
    <tbody id="shortlistDockList"></tbody>
  </table>
</aside>

<footer>
  __NRE_CREDIT__
  __NRE_SOURCE__
  <p id="commissionDisclosure" hidden></p>
  <div id="attribution" hidden></div>
  __NOTE__
  <!-- This paragraph opened by restating what the count line above the table
       and #modeNote already say -- which fare the price is, and what the list
       mixes (audit item 14, 9 October 2026). What is left is what only a
       limitation can say, and the standard-class fact is in the method note. -->
  <p>ITX placeholder fares are excluded. Advance singles are shown when they are the cheapest single, but they require a qualifying train and their price and availability can change.</p>
  <!-- C5 of the 17 October 2026 critique: this sentence named "the services
       listed" on a build that lists no services. It is the payload's own
       sentence now, chosen from hasJourneys, so the page cannot make a claim
       its payload does not support (build_release.SERVICE_CLAIM). -->
  <p>__SERVICE_CLAIM__</p>
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
    <!-- Item 44 of the 14 October 2026 clarity audit, answered "the glossary
         only": the trade words the lines above quote are defined once, here,
         rather than glossed where each is met. The definitions come from the
         route's shared script, so they cost the release nothing per page. -->
    <details class="words"><summary>The words this page uses</summary><dl id="wordList"></dl></details>
  </details>
  <nav class="footnav"><a href="__BASE__/">Station list</a> <a href="__BASE__/privacy/">Privacy</a></nav>
  <p id="copyStatus" role="status" class="sr-only"></p>
</footer>

__STATIONS_SRC__
<!-- The page's own answer, inlined because it is the one part of the page
     that differs per origin. The route's script arrives separately as one
     shared asset and reads this block, so the bytes the browser keeps are the
     same on every page of the route (T1). -->
<script>
window.TBE_DATA = __DATA__;
window.TBE_FIRST_USE_FALLBACK = __FIRST_USE_FALLBACK__;
</script>
__STATION_SCRIPT__
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
""" + _page_file("chooser.css") + """</style>
</head>
<body data-synthetic="__SYNTHETIC__">
__SYNTHETIC_BANNER__
__THEME_TOGGLE__
<main>
<h1 id="pageHeading">Train fares <span class="heading-slot">up to <span class="heading-field" id="budgetField"><span class="budget-prefix">&pound;</span><input id="budgetNumber" type="number" min="0" max="500" step="1" value="__BUDGET__" inputmode="numeric" aria-label="Budget in pounds"></span></span><br>__ORIGIN_CLAUSE__</h1>
__CHOOSER_INTRO__
<p class="sub" id="provenanceLine">__PROVENANCE__</p>
__ORDERING_NOTE__
<ul id="picks"></ul>
<p id="nomatch" hidden></p>
<!-- The station list is drawn by the route's own code, so a chooser whose copy
     did not arrive shows an empty list with no explanation unless something
     says so. The script tag's onerror reveals this rather than the script
     itself, because the script is what is missing. -->
<p class="sub" id="scriptNote" hidden>The station list needs this page's code, which did not load, so nothing is listed below.</p>
<p id="capMessage" hidden></p>
<span id="pickStatus" class="sr-only" role="status"></span>
__NOTE__
</main>
<nav class="footnav"><a href="__BASE__/privacy/">Privacy</a></nav>
<!-- The chooser's own stations, inlined because they are the one part of the
     page that differs per build. The route's script arrives separately as one
     shared asset and reads this block, so the bytes the browser keeps are the
     same for every release that does not change its code (T10). -->
<script>
window.TBE_CHOOSER_STATIONS = __STATIONS__;
window.TBE_TITLE_SUFFIX = __TITLE_SUFFIX_JS__;
</script>
__CHOOSER_SCRIPT__
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


# One matcher and one cap, wherever a reader types a station name. The
# chooser's field and a station page's picker ask the same question in two
# headings, so they cannot answer it differently: a name substring or a
# three-letter code prefix, and a stated cap on how many rows either list
# draws. Two routes used to hold the same matcher each, and the picker capped
# silently where the chooser said so (audit item 22, 9 October 2026).
STATION_MATCH_JS = """const STATION_LIST_CAP = 40;
function stationMatches(station, needle) {
  if (!needle) return true;
  return station.name.toLowerCase().includes(needle) ||
    station.crs.toLowerCase().startsWith(needle);
}"""


# One station field. A station page's heading and the chooser's heading ask a
# reader to do the same three things -- narrow the list under it as they type,
# see the rest of the name they are typing in the field, and walk away without
# having changed anything -- so they are answered here once rather than twice.
# The route supplies the field, the list and the stations; it keeps ownership of
# what each of them draws.
STATION_FIELD_JS = """function attachStationField(options) {
  const field = options.field;
  if (!field) return null;
  const stations = options.stations || [];
  const inside = options.inside || [];
  const onChange = options.onChange || function () {};
  const onUse = options.onUse || function () {};
  const onCancel = options.onCancel || function () {};
  const dropdown = options.dropdown || null;
  const onChoose = options.onChoose || null;
  const CAP = options.cap || 544;
  // Where the panel is drawn from, and what makes it appear. A route whose
  // field sits above the page's own explanation anchors the panel to the
  // list's place in the document, so the prose between them stays readable and
  // clickable (four-dimension audit R1); the station page's picker has no
  // prose under its field and is drawn from the field itself. A chooser also
  // opens on typing rather than on focus: a panel over prose the reader has
  // not asked to replace is the defect that anchor answers.
  const LIST_ANCHORED = options.anchor === "list";
  const OPEN_ON_TEXT = options.openOn === "text";
  // The list's place in the document, read once before it leaves the flow.
  let listTop = 0;
  // The station a completion is offering, held so Tab and Enter can go to it
  // rather than merely accept the text. A field that can complete a name can
  // then act on one.
  let proposal = null;

  const selected = () => field.selectionEnd > field.selectionStart;
  // The station the field still holds. A completion is offered as a selection
  // over the rest of the name, and reading only the selection lost it the
  // moment an arrow key walked the caret over that tail: the field said the
  // same word, the caret was at its end, and Tab and Enter did nothing at all
  // rather than going to the station the field was showing. The value is
  // compared rather than the proposal trusted, so a keystroke after the arrow
  // key -- which does change the value -- drops the offer instead of choosing
  // a station the field no longer spells.
  const offered = () => (proposal && field.value === proposal.name ? proposal : null);
  function commit() {
    proposal = null;
    if (selected()) field.setSelectionRange(field.value.length, field.value.length);
  }
  // The station a completion offers for what has been typed. An exact match
  // wins, so the field settles on the name's own spelling and Tab can go there;
  // otherwise the shortest name that starts with the text, with destination
  // count breaking a tie. The rule used to be the first station in list order,
  // and list order is destination count, so typing "gran" completed GRANGETOWN
  // CRDIF over GRANTHAM (audit item 1, 9 October 2026).
  function completionFor(typed) {
    const wanted = typed.trim().toLowerCase();
    if (!wanted) return null;
    let best = null;
    for (const station of stations) {
      const name = station.name.toLowerCase();
      if (name.indexOf(wanted) !== 0) continue;
      if (name === wanted) return station;
      if (!best || name.length < best.name.length ||
          (name.length === best.name.length && (station.destinations || 0) > (best.destinations || 0))) {
        best = station;
      }
    }
    return best;
  }
  // The text the reader typed, kept while a completion is written over it: a
  // route lists the stations matching this text, so the field can show a
  // completed name while the list still offers the alternatives that name
  // would hide (audit item 2, 9 October 2026).
  let query = "";

  // The rest of the name, inside the field, selected so it reads as a suggestion
  // rather than as what was typed. Only a prefix is completed this way, and only
  // with the caret at the end of the text, so a reader editing the middle of a
  // word is never rewritten underneath themselves.
  //
  // A deletion completes nothing. Backspace, Delete and cut all arrive as an
  // input event like any other, so completing on them re-applied the suggestion
  // to its own undo: Backspace deleted the suggested tail and complete() put it
  // straight back, leaving the field byte-identical and the key apparently dead.
  // A completion that does not fit is reverted for the same reason a long one
  // is never offered: the field would scroll its own value and the part the
  // reader typed would leave the window.
  function complete(event) {
    if (event && event.inputType && event.inputType.indexOf("delete") === 0) {
      proposal = null;
      query = field.value;
      return;
    }
    const typed = field.value;
    if (!typed) {
      proposal = null;
      query = "";
      return;
    }
    if (field.selectionStart !== typed.length || field.selectionEnd !== typed.length) {
      proposal = null;
      query = typed;
      return;
    }
    const station = completionFor(typed);
    if (!station) {
      proposal = null;
      query = typed;
      return;
    }
    field.value = station.name;
    field.setSelectionRange(typed.length, field.value.length);
    if (field.scrollWidth > field.clientWidth) {
      field.value = typed;
      field.setSelectionRange(typed.length, typed.length);
      proposal = null;
      query = typed;
      return;
    }
    proposal = station;
    query = typed;
  }
  const inUse = () =>
    field.value.trim() !== "" || (!OPEN_ON_TEXT && document.activeElement === field);
  // The list is drawn under the field from the field's own rectangle. Nothing
  // on the page is made into its ancestor for that, and nothing moves in the
  // document to make it possible: the field is a word in the middle of a
  // heading, and a heading may not hold a list.
  function place() {
    if (!dropdown || !dropdown.classList.contains("under-field")) return;
    const box = field.getBoundingClientRect();
    const width = Math.min(CAP, Math.max(box.width, window.innerWidth * 0.9));
    const left = Math.max(0, Math.min(box.left, window.innerWidth - width - 8));
    dropdown.style.left = left + "px";
    dropdown.style.width = width + "px";
    // The list's own place in the document for the anchored routes, so the
    // panel covers the list and nothing written above it.
    dropdown.style.top = LIST_ANCHORED
      ? listTop - window.scrollY + "px"
      : box.bottom + 4 + "px";
  }
  const follow = () => place();
  function enterUse() {
    if (dropdown && !dropdown.classList.contains("under-field")) {
      if (LIST_ANCHORED) {
        listTop = dropdown.getBoundingClientRect().top + window.scrollY;
      }
      dropdown.classList.add("under-field");
      window.addEventListener("scroll", follow, { passive: true });
      window.addEventListener("resize", follow);
    }
    place();
    // Twice, because taking the list out of the flow shortens the page, and a
    // heading with balanced lines rebalances when the page under it changes
    // height -- which moves the field the list was just placed against.
    requestAnimationFrame(place);
  }
  function leaveUse() {
    if (dropdown && dropdown.classList.contains("under-field")) {
      dropdown.classList.remove("under-field");
      dropdown.style.left = "";
      dropdown.style.top = "";
      dropdown.style.width = "";
      window.removeEventListener("scroll", follow);
      window.removeEventListener("resize", follow);
    }
  }
  const reportUse = () => {
    const used = inUse();
    if (used) enterUse();
    else leaveUse();
    onUse(used);
  };
  const isInside = (target) => {
    if (!target) return false;
    if (field.contains(target)) return true;
    return inside.some((element) => element && element.contains(target));
  };
  field.addEventListener("input", (event) => {
    complete(event);
    onChange(field.value, query, offered());
    // The keystroke is what opens the panel on a route that waits for one:
    // the list is not drawn over the page until the reader has typed into the
    // field (four-dimension audit R1).
    reportUse();
    // The completion widens the field, and a heading with balanced lines
    // rebalances around a wider word, which moves the field the list was
    // placed against. Placed again on the next frame, once it has settled.
    requestAnimationFrame(place);
  });
  field.addEventListener("keydown", (event) => {
    if (event.key === "Tab" || event.key === "Enter") {
      // A completion is a place, not a spelling, so accepting one is choosing
      // it. It is accepted whether or not its tail is still selected, because
      // the reader has said where they are going either way. The route owns
      // the URL because the route owns what travels with it.
      const station = offered();
      if (station && onChoose) {
        event.preventDefault();
        onChoose(station);
        return;
      }
      // A key with nothing half-typed belongs to the page: Tab moves on, Enter
      // is the browser's own.
      if (!selected()) return;
      event.preventDefault();
      commit();
      onChange(field.value, query, offered());
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      onCancel();
    }
  });
  // A click inside the field is a reader placing the caret, and the browser
  // drops a selection on its own.
  field.addEventListener("mousedown", commit);
  field.addEventListener("focus", reportUse);
  field.addEventListener("blur", () => {
    commit();
    reportUse();
  });
  // A pointerdown anywhere else on the page is the reader saying they are done
  // here. It is on the document rather than on a wrapper so that a click on the
  // page's own prose closes the field too, which is the whole of the promise.
  document.addEventListener("pointerdown", (event) => {
    if (isInside(event.target)) return;
    commit();
    reportUse();
    onCancel();
  });
  return { complete: complete, commit: commit, reportUse: reportUse };
}"""


def _shared_script(text: str, what: str) -> str:
    """One route's script as the asset ships it, shared blocks filled in.

    The blocks are the ones with_shared() inlines into the templates, because
    the asset is the same code the template used to carry. The page's own
    values the scripts used to declare inline -- the station page's DATA, the
    chooser's station list -- now arrive on window.TBE_* from a small block
    each page inlines, so everything filled here is the same on every page of
    the route, which is the whole reason the file can be shared. A placeholder
    left unfilled would ship a literal __NAME__ to the browser, so this refuses
    like with_shared() does.
    """
    import json

    filled = text
    for placeholder, block, name in (
        ("__LIST_KEYS__", LIST_KEYS_JS, "list keyboard block"),
        ("__STATION_MATCH__", STATION_MATCH_JS, "station matcher block"),
        ("__STATION_FIELD__", STATION_FIELD_JS, "station field block"),
        ("__CHEVRON_JS__", json.dumps(CHEVRON), "disclosure mark for the script"),
    ):
        filled = filled.replace(placeholder, block)
        if placeholder in filled:
            raise ValueError(f"the shared {name} was not filled into {what}")
    if "__DATA__" in filled or "__STATIONS__" in filled or "__TITLE_SUFFIX_JS__" in filled:
        raise ValueError(
            f"{what} still declares a per-page value, so it cannot be one shared file"
        )
    return filled


CHEVRON = (
    '<svg class="chevron" viewBox="0 0 16 16" width="16" height="16"'
    ' aria-hidden="true" focusable="false">'
    '<path d="M4 6.25 8 10.25l4-4" fill="none" stroke="currentColor"'
    ' stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


# The station route's script as the asset ships it: the panels concatenated in
# STATION_SCRIPT_PARTS order, with the shared blocks filled in.
STATION_SCRIPT = _shared_script(
    "".join(_page_file(part) for part in STATION_SCRIPT_PARTS),
    "the station route's script",
)

# The chooser route's own script. It is one file rather than several because the
# route is one field over one list, and it moves out of the page for the same
# reason the station route's does (T10).
CHOOSER_SCRIPT = _shared_script(_page_file("chooser.js"), "the chooser route's script")


SHARED_THEME = """<meta name="color-scheme" content="light dark">
<script>
""" + _page_file("theme.js") + """</script>"""

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
    # json is imported here rather than at the top because it is used once,
    # to quote the chevron for the script. The module's own docstring calls it
    # pure strings, and this is the one place a value is escaped rather than
    # pasted.
    import json

    filled = template.replace("__SHARED_CSS__", SHARED_CSS)
    if "__SHARED_CSS__" in filled:
        raise ValueError("the shared stylesheet was not inlined into this template")
    for placeholder, block, what in (
        ("__SHARED_THEME__", SHARED_THEME, "theme block"),
        ("__THEME_TOGGLE__", THEME_TOGGLE, "theme control"),
        ("__CHEVRON__", CHEVRON, "disclosure mark"),
        ("__CHEVRON_JS__", json.dumps(CHEVRON), "disclosure mark for the script"),
        ("__LIST_KEYS__", LIST_KEYS_JS, "list keyboard block"),
        ("__STATION_MATCH__", STATION_MATCH_JS, "station matcher block"),
        ("__STATION_FIELD__", STATION_FIELD_JS, "station field block"),
    ):
        filled = filled.replace(placeholder, block)
        if placeholder in filled:
            raise ValueError(f"the shared {what} was not inlined into this template")
    return filled


PRIVACY = with_shared(_PRIVACY_TEMPLATE)
TEMPLATE = with_shared(_TEMPLATE)
CHOOSER_TEMPLATE = with_shared(_CHOOSER_TEMPLATE)
