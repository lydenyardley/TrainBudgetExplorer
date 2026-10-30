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

from trainbudget import ROOT

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
_PAGE_ASSETS = ROOT / "page"


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
    "station/state.js",
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

# What a route may load and what it may reach (audit item 10, 28 October 2026).
#
# Both routes carry their first-paint theme and their payload inline, and the
# station route fetches one hashed script and one hashed stylesheet of its own,
# so `'unsafe-inline'` is the price of the inline theme and nothing more hides
# behind it. What survives that is still worth stating: no frame, no form, no
# plugin, no <base>, and no network call of any kind -- the page has nothing to
# fetch after it loads, so a string that got into the markup cannot become a
# request. `connect-src 'none'` is the line that makes the last part true.
#
# A meta tag is enough for every directive above except `frame-ancestors`, which
# browsers ignore in a meta tag: framing is the host's header to send, and this
# comment is the record that the page knows it rather than believing it is
# framed-proof. Inline script is also why this cannot become a nonce without
# giving up the inline theme (ADR-0033, ADR-0047).
CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "connect-src 'none'; form-action 'none'; base-uri 'none'; object-src 'none'"
)
CSP_META = f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'

# A cross-document navigation needs both documents to opt in, and the browser
# reads the opt-in before the destination's stylesheet has necessarily arrived.
# Measured on 30 October 2026: delaying the station route's stylesheet by three
# seconds made a chooser-to-station navigation skip with "ViewTransition opt-in
# disabled" and log an uncaught InvalidStateError. The at-rule therefore sits in
# the document itself, on every route, ahead of the stylesheet the station route
# fetches. The pseudo-elements that style the cross-fade stay in shared.css,
# where the motion itself is described.
VIEW_TRANSITION_OPT_IN = "<style>@view-transition { navigation: auto; }</style>"

_PRIVACY_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
""" + CSP_META + VIEW_TRANSITION_OPT_IN + """
__SHARED_THEME__
<title>Privacy</title>
<style>
__SHARED_CSS__
""" + _page_file("privacy.css") + """</style>
</head>
<body data-synthetic="__SYNTHETIC__">
__SYNTHETIC_BANNER__
<!-- C19 of the 17 October 2026 critique: the back link, then the theme switch,
     then the title was a reading order that made the switch look like the
     document's second line. The two pieces of chrome share a row above the
     content now, so what follows is the title. -->
<div class="route-top">
<nav class="back-link"><a href="__BASE__/">Back to the station list</a></nav>
__THEME_TOGGLE__
</div>
<main>
<h1>Privacy</h1>
<p>This page works entirely in your browser. There is no account, no sign-in, and nothing you choose is stored on a server by this site.</p>
__BUILT_LINE__
<h2>What this site does</h2>
<ul>
__PRACTICES__</ul>
<h2>What stays in the address bar</h2>
<p>A fare page keeps your search in the web address, so that a refresh, the Back button, or a link you share all return the same results. The search is the parameters <code>budget</code>, <code>mode</code>, <code>party</code>, <code>card</code>, <code>types</code>, <code>page</code>, <code>short</code> and <code>day</code>. It is never sent to this site, because this site has no server to receive it. It does leave your device in two ways that are worth naming plainly:</p>
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
""" + CSP_META + VIEW_TRANSITION_OPT_IN + """
__SHARED_THEME__
<title>Train fares up to &pound;__BUDGET__ from __ORIGIN__</title>
__STATION_STYLE__
</head>
<body data-synthetic="__SYNTHETIC__">
__SYNTHETIC_BANNER__
__THEME_TOGGLE__
<main>
<!-- OV4 of the 19 October 2026 overdrive pass: the budget in a 56px rail, shown
     only while its own control is out of view, so the page never offers two
     sliders for one number at once and the shortcut arrives at the row where a
     reader has scrolled past the control. Hidden until the observer says the
     control is gone, which is also what keeps it out of the tab order on a page
     that does not need it. -->
<div class="budget-rail" id="budgetRail" hidden>
  <label class="budget-rail-label" for="railBudget">Fares up to</label>
  <input id="railBudget" type="range" min="0" max="__MAXPOUNDS__" step="1" value="__BUDGET__" aria-describedby="railStop">
  <span class="budget-rail-now" id="railNow">&pound;__BUDGET__</span>
  <span class="tag" id="railStop">__CEILING_NOTE__</span>
</div>
<h1 id="pageHeading" aria-label="Train fares up to &pound;__BUDGET__ from __ORIGIN__">Train fares <span class="heading-slot">up to <span class="heading-field" id="budgetField"><span class="budget-prefix">&pound;</span><input id="budgetNumber" type="number" min="0" max="__MAXPOUNDS__" step="1" value="__BUDGET__" inputmode="numeric" aria-label="Budget in pounds"></span></span><br><span class="heading-lead">from</span> __ORIGIN_CONTROL__</h1>
<!-- D1 of the 17 October 2026 critique: the paragraph that opened the page was
     a third copy of its own claim. The heading states the budget and the
     station, the count line states the destinations and their number, and the
     column headings state time and changes; what was left was the one thing a
     first-time reader cannot guess, which is that the name in the heading can
     be changed. That sentence is now the paragraph, under the word it
     describes, and the 48px it costs the fold is the price of the one fact.
     The build writes it per build, because a one-origin page has no such
     control to point at. -->
<p class="sub" id="firstUse">__FIRST_USE__</p>
<!-- The list, not the field. The field is moved into the heading by the
     script, into the place the station's own name was, so that clicking the
     name and typing are the same gesture in the same place -- and the list
     opens directly under it, because a reader who has just clicked a word
     looks at that word and not two paragraphs further down. -->
<div id="originPicker" hidden>
  <p class="eyebrow origin-picker-label" id="originPicksLabel">Every station on this site</p>
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
    <!-- DS2 of the 19 October 2026 distill pass: the hint named where the control
         was (the heading is directly above it), so it says what the drag does and
         where it stops. The mode is named only when it is not the default one,
         because a default needs no clause; the party and the ceiling stay, which
         are the two facts the budget contract protects. -->
    <span class="tag" id="budgetHint">Drag to set the budget. Stops at <span id="budgetCeiling">__CEILING_NOTE__</span><span id="budgetHintMode"></span>.</span>
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
    <legend class="eyebrow">Ticket type</legend>
    <div class="filter-options segmented">
      <label><input type="radio" name="ticketMode" value="cheapest" checked> Cheapest available</label>
      <label><input type="radio" name="ticketMode" value="anytime"> Anytime Day Return</label>
      <label><input type="radio" name="ticketMode" value="return"> Any return</label>
      <label><input type="radio" name="ticketMode" value="single"> Single</label>
    </div>
    <!-- C21 of the 17 October 2026 review, closed on 20 October 2026: the four
         sets were chosen here and defined below the table, more than a screen
         away, and the empty state asked a lost reader to read the definition
         first. The sentence that says what the open set contains sits under the
         options it explains, shortened to the difference between them rather
         than to a paragraph about all four; the count line still names the mix
         in the list itself. -->
    <p id="modeNote"></p>
  </fieldset>
  <fieldset class="party-filter">
    <legend class="eyebrow">The budget covers</legend>
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
    <legend class="eyebrow">Destination type</legend>
    <div class="filter-options" id="destinationTypes" role="group" aria-label="Destination type">__DESTINATION_TYPE_FILTERS__</div>
    <!-- Critique item 3, second half: the four settlement bands stay in the row
         above and the ten thematic facets arrive here, behind the "More types"
         chip that row ends with. The build writes both, and writes nothing at
         all here on a page whose destinations carry no facet: a disclosure that
         opens onto nothing is the dead end the chips beside it are already
         refused for. -->
    __DESTINATION_FACET_FILTERS__
  <span class="tag" id="typeRule">Each count is how many destinations of that type are inside the budget now. The number on More types is how many kinds are behind it.</span>
  <p id="facetNotice" class="tag" role="status" hidden></p>
  <button id="clearTypes" class="toggle" type="button" hidden>Show all destination types</button>
  </fieldset>
    </div>
  </div>
<!-- Critique item 8: the page's two accelerators, named on the strip that is
     on screen at every width and in every state, which is this one and not the
     fold above it: the fold is the refinements, and a key a reader cannot see
     until they open a drawer is a key they will not press. Written by
     renderKeyHints() rather than here, because the paging half is only a
     promise while the pager is on screen, and only the page's own render knows
     that. Empty and hidden until then, so a page whose script did not arrive
     claims no key it cannot honour. -->
<p class="tag" id="keyHints" hidden></p>
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
    <summary><span id="linkTermsSummary">About the ticket link</span> __CHEVRON__</summary>
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
<!-- tabindex="-1": clearing the shortlist takes the dock away with the focus
     inside it, so focus is moved to this line before the dock goes (S7 of the
     19 October 2026 critique). It is not in the tab order -- it is a place to
     arrive, not a stop on the way. -->
<p id="summary" role="status" aria-live="polite" tabindex="-1"></p>
<!-- DL1 of the 19 October 2026 delight pass: the budget's own answer in places.
     It sits under the count, so it speaks to the same question, and it is empty
     and collapsed at rest, so a page that is not being dragged is the page it
     was. Deliberately not a live region: a drag that announced every pound would
     be worse for a screen-reader reader than silence, and the count line above
     already speaks on settle. -->
<p class="tag" id="budgetNext" hidden></p>
<table>
  <thead><tr><th scope="col" class="eyebrow hold">Shortlist</th><th scope="col" class="eyebrow">Station</th><th scope="col" class="eyebrow num">Price</th><th scope="col" class="eyebrow num">Time</th><th scope="col" class="eyebrow num">Changes</th><th scope="col" class="eyebrow">Fare type</th><th scope="col" class="eyebrow">Tickets</th></tr></thead>
  <tbody id="rows"></tbody>
</table>
<div id="empty" hidden></div>
<p id="more" hidden></p>
<nav id="pagination" hidden aria-label="Results pages">
  <button id="previousPage" type="button" class="toggle">Previous</button>
  <span id="pageStatus" role="status"></span>
  <button id="nextPage" type="button" class="toggle">Next</button>
</nav>
<!-- S7 of the 19 October 2026 critique: the shortlist's live region, outside the
     dock, because the dock hides itself when the last place leaves it and a live
     region inside a hidden subtree is announced to nobody -- which is exactly
     the clear this message exists for. It sits here rather than beside the count
     line for a measured reason: anything between the count and the table's first
     row pushes them apart, and two layout checks hold that gap to nothing.
     Position means nothing to a live region; presence and visibility do. -->
<span id="shortlistStatus" role="status" class="sr-only"></span>

</main>

<!-- The dock is the shortlist at the foot of the screen. It is hidden until a
     place is on it, so a page with nothing shortlisted carries no dock and
     gives its rows the whole window. The row headings name the four facts
     because a reader comparing two places is reading columns, and the
     columns need the same names the results table gives them. -->
<aside class="shortlist-dock" id="shortlistDock" hidden aria-label="Shortlisted destinations">
  <div class="shortlist-dock-head">
    <span class="eyebrow shortlist-label">Shortlist</span>
    <span class="tag" id="shortlistDockCount"></span>
    <p class="tag" id="shortlistLimit"></p>
    <button id="shortlistCopy" class="toggle" type="button" hidden>Copy</button>
    <details class="shortlist-share" id="shortlistShareBox" hidden>
      <summary>Share</summary>
      <p id="shortlistShare"></p>
      <textarea id="shortlistBox" class="copybox" rows="6" readonly hidden aria-label="Shortlist to copy"></textarea>
    </details>
    <button id="shortlistDockClear" class="toggle" type="button">Clear</button>
  </div>
  <table>
    <thead><tr><th scope="col" class="eyebrow">Station</th><th scope="col" class="eyebrow num">Price</th>
      <th scope="col" class="eyebrow num">Time</th><th scope="col" class="eyebrow num">Changes</th>
      <th scope="col" class="eyebrow"><span class="sr-only">Remove</span></th></tr></thead>
    <tbody id="shortlistDockList"></tbody>
  </table>
</aside>

<footer>
  __NRE_CREDIT__
  __NRE_SOURCE__
  <p id="commissionDisclosure" hidden></p>
  <div id="attribution" hidden></div>
  <!-- D6 of the 17 October 2026 critique: on a synthetic build this paragraph
       repeated the banner at the top of the same page, so the build passes no
       note here at all; a real build with a note of its own still gets one. -->
  __NOTE__
  <!-- This paragraph opened by restating what the count line above the table
       and #modeNote already say -- which fare the price is, and what the list
       mixes (audit item 14, 9 October 2026). What is left is what only a
       limitation can say, and the standard-class fact is in the method note. -->
  <!-- DS5 of the 19 October 2026 distill pass: the Advance limitation was stated
       twice, twenty pixels apart, and each copy had a clause the other did not.
       One paragraph now, and the payload's own sentence is the one that carries
       it: the excluded placeholder fares stay their own clause, because they are
       a different fact about a different fare. -->
  <p>ITX placeholder fares are excluded. __SERVICE_CLAIM__</p>
  <!-- C5 of the 17 October 2026 critique: the sentence is the payload's own,
       chosen from hasJourneys, so the page cannot make a claim its payload does
       not support (build_release.SERVICE_CLAIM). -->
  <!-- Everything the page knows about where its numbers came from, in the one
       place a reader goes to check them. These four lines stood between the
       budget control and the first fare on every station page: the feed's
       name and download date, the second opinion on the ticket conditions, the
       build's own stamp, and -- when a build read an undated timetable -- the
       caveat that every schedule in the feed was read. They are not deleted and
       they are not shortened; they are below the results, which is where the
       primary asset is not competing with them for the fold. -->
  <details class="method">
    <summary>Where these prices come from, and how they were calculated __CHEVRON__</summary>
    <p id="pricingBasis"></p>
    <p id="feedCoverage" class="tag"></p>
    <!-- D4 of the 17 October 2026 critique: the window the timetable covers is
         a date about a source, like the rest of this fold, and it was a
         sentence of the freshness line above the table -- one of the two
         blocks that put the first fare below a laptop's fold. -->
    <p class="tag" id="timetableCoverage" hidden></p>
    <p id="railcardNote"></p>
    <p class="tag" id="priceSource" hidden></p>
    <p class="tag" id="restrictionReference" hidden></p>
    <p class="tag" id="buildMetadata" hidden></p>
    <p class="tag" id="provenance"></p>
    <!-- Item 44 of the 14 October 2026 clarity audit, answered "the glossary
         only": the trade words the lines above quote are defined once, here,
         rather than glossed where each is met. The definitions come from the
         route's shared script, so they cost the release nothing per page.

         D7 of the 17 October 2026 critique: this was a second disclosure
         nested inside the first, which gave the page's trust content two
         entrances for one question. It is the last thing in this fold now. -->
    <p class="tag" id="wordListLead">The words this page uses</p>
    <dl id="wordList"></dl>
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
""" + CSP_META + VIEW_TRANSITION_OPT_IN + """
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
<!-- C12/D10 of the 17 October 2026 critique: every row ended with the same
     nine words, "N destinations this feed prices", which on the real release
     is 2,712 repetitions of one phrase. The phrase is the list's heading now
     and each row carries the number alone, in the same column. -->
<h2 id="picksHeading">Destinations this feed prices</h2>
__ORDERING_NOTE__
<!-- S11 of the 19 October 2026 critique: the row's number was a bare count after
     a code, and nothing above it named the column -- the heading says what the
     list is, not what the third column is. One column line, written once, is
     what the count needed; the row still does not repeat the phrase. It is for
     the eye only: each row's own accessible name already says "22
     destinations", so a screen reader would hear the legend and then the same
     fact on every link. A build that priced no station writes nothing here: a
     column line over an empty list names columns that are not on the page. -->
__PICKS_COLUMNS__
<ul id="picks" aria-labelledby="picksHeading"></ul>
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
  if (!field) return;
  const stations = options.stations || [];
  const inside = options.inside || [];
  const onChange = options.onChange || function () {};
  const onCancel = options.onCancel || function () {};
  const dropdown = options.dropdown || null;
  const onChoose = options.onChoose || null;
  const CAP = 544;
  // What makes the panel appear. A chooser opens on typing rather than on
  // focus: a panel over prose the reader has not asked to replace is noise,
  // and the caret in the field already says the page is waiting (C11 of the 17
  // October 2026 critique moved the panel under the field on both routes).
  const OPEN_ON_TEXT = options.openOn === "text";
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
    // Under the word the reader is typing in, on both routes.
    dropdown.style.top = box.bottom + 4 + "px";
  }
  const follow = () => place();
  function enterUse() {
    if (dropdown && !dropdown.classList.contains("under-field")) {
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
  const reportUse = () => (inUse() ? enterUse() : leaveUse());
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


def station_script(parts: tuple[str, ...] = STATION_SCRIPT_PARTS) -> str:
    """The station route's script: the named panels concatenated, shared blocks filled.

    The default is the whole artifact. A prefix is what the artifact check in
    `tools/verify.py` builds when the whole one does not parse, so the failure
    names the panel whose addition broke it rather than the route.
    """
    return _shared_script(
        "".join(_page_file(part) for part in parts),
        "the station route's script",
    )


# The station route's script as the asset ships it, in STATION_SCRIPT_PARTS
# order, with the shared blocks filled in.
STATION_SCRIPT = station_script()

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
