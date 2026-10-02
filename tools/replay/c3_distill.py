"""C3: the page says less, and says it above the results.

Six paragraphs of provenance stood between the budget control and the fares.
Four of them are reference material -- where a feed was downloaded, when it
was last checked, what the build fingerprint is -- and they move under the
table into the disclosure that already exists for reference material. What
stays above is the one line a reader needs before they trust a number (how
old it is), one line saying what the list is, and the count.
"""

import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD_H1 = '''<h1 id="pageHeading">Train fares&#8288;<span class="heading-sep" aria-hidden="true">&middot;</span> <span class="heading-slot">up to <span class="heading-field" id="budgetField"><span class="budget-prefix">&pound;</span><input id="budgetNumber" type="number" min="1" max="__MAXPOUNDS__" step="1" value="__BUDGET__" inputmode="numeric" aria-label="Budget in pounds"></span>&#8288;<span class="heading-sep" aria-hidden="true">&middot;</span></span><br>from __ORIGIN_CONTROL__</h1>'''

NEW_H1 = '''<h1 id="pageHeading"><span class="heading-slot">Train fares up to <span class="heading-field" id="budgetField"><span class="budget-prefix">&pound;</span><input id="budgetNumber" type="number" min="1" max="__MAXPOUNDS__" step="1" value="__BUDGET__" inputmode="numeric" aria-label="Budget in pounds"></span></span><br><span class="heading-lead">from</span> __ORIGIN_CONTROL__</h1>'''

OLD_INTRO = '''<!-- C04: the opening sentence is written by renderIntro() once the build has
     said whether a timetable was loaded. The static text below is the
     fares-only sentence, because that is the one that cannot overstate what a
     prices-only build shows; a build with a timetable replaces it. -->
<p class="sub" id="pageIntro">Every destination reachable by train for the budget in the heading.</p>
<!-- The first-use note is written by first_use_sentence() per build, because
     the one thing a first-time reader cannot guess -- what the Change control
     in the heading does -- only exists on a build that wrote another
     station's page. A one-station build points the reader at a control it does
     not have. -->
<p class="sub" id="firstUse">__FIRST_USE__</p>'''

NEW_INTRO = '''<!-- C04: the opening sentence is written by renderIntro() once the build has
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
<p class="sub" id="pageIntro">Every destination this feed prices from the station above, inside the budget.<span id="firstUse"> __FIRST_USE__</span></p>'''

OLD_TAGS = '''<p class="tag" id="modeNote"></p>  <p class="tag" id="priceSource" hidden></p>
<!-- The conditions in the table are the fares feed's own wording. This is the
     second opinion on it, and the reader gets it before the table rather than
     after a row: a condition that has since changed is exactly what a reader
     comparing two prices needs to know before, not after, they choose. -->
<p class="tag" id="restrictionReference" hidden></p>
<p class="tag" id="freshness" hidden></p>'''

NEW_TAGS = '''<p class="tag" id="modeNote"></p>
<!-- The one provenance line that stays above the table: how old the numbers
     are. Everything else about where they came from is reference material and
     sits under the table with the rest of it, where a reader goes when they
     have decided to check rather than before they have decided to read. -->
<p class="tag" id="freshness" hidden></p>'''

OLD_LINK_TERMS = '''  <details class="link-terms" id="linkTerms">
    <summary id="linkTermsSummary">About the ticket link, and how this page was built</summary>
    <p class="tag" id="linkNote" hidden></p>
    <p class="tag" id="disclosure" hidden></p>
    <p class="tag" id="buildMetadata" hidden></p>
  </details>'''

NEW_LINK_TERMS = '''  <details class="link-terms" id="linkTerms">
    <summary id="linkTermsSummary">About the ticket link</summary>
    <p class="tag" id="linkNote" hidden></p>
    <p class="tag" id="disclosure" hidden></p>
  </details>'''

OLD_FOOTER = '''  <details class="method">
    <summary>How these prices were calculated</summary>
    <p id="pricingBasis"></p>
    <p id="feedCoverage" class="tag"></p>
    <p id="railcardNote"></p>
    <p class="tag" id="provenance"></p>
  </details>'''

NEW_FOOTER = '''  <!-- Everything the page knows about where its numbers came from, in the one
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
  </details>'''

OLD_SEP_CSS = '''  /* The dot between the heading's three parts. Muted, because it is
     punctuation rather than one of the two things the reader came to set:
     at six rem a separator in the text colour is as loud as the words it is
     separating. aria-hidden, because the three parts are one sentence to a
     reader, and "middle dot" is not a word the page means to say. */
  .heading-sep { color: var(--muted); font-size: .38em; padding: 0 .45em; vertical-align: middle; }
  /* The amount and the separator after it, in one box that cannot wrap. A
     break opportunity sits at the edge of an inline field whatever follows
     it, so without this the second line starts with the dot -- a separator
     opening a line reads as a bullet, and the dot belongs to the phrase
     before it. */
  .heading-slot { white-space: nowrap; }'''

NEW_SEP_CSS = '''  /* "from" sits on the second line in the page's own voice rather than as
     punctuation between the two halves. The middots it replaced were at
     .38em in the muted colour, and at six-plus rem a pair of them either side
     of the number the reader came to set said "and also" about a word that was
     already a separate line. The line break is the separator. */
  .heading-lead { color: var(--muted); margin-right: .15em; }
  /* The amount and the words around it, in one box that cannot wrap. A break
     opportunity sits at the edge of an inline field whatever follows it, so
     without this the second line can begin with the number and the "from" can
     be left at the end of the first. */
  .heading-slot { white-space: nowrap; }'''

OLD_MODE_NOTE = '''const MODE_NOTE = {
  cheapest: "The cheapest fare of any ticket type for each destination, so this list mixes: a return to the same place always costs more than a single to it, so most rows are a single. Use the ticket type above to see one kind of fare instead. An advance single is valid on a particular train only and is labelled where it appears; a restricted fare's condition is in the row's details.",
  anytime: "Unrestricted Anytime Day Returns only: these fares are valid on any train on the route, so the prices can be compared with each other directly.",
  return: "Every standard-class return the feed prices, including restricted off-peak and advance fares. A restricted fare is not valid on every train or at every time, so check the Conditions column before treating two prices here as the same thing.",
  single: "Outbound singles rather than returns. An advance single is valid on a particular train only, and is labelled where it appears.",
};'''

NEW_MODE_NOTE = '''const MODE_NOTE = {
  cheapest: "Each row is the cheapest fare of any ticket type, so this list mixes singles and returns. An advance fare needs a chosen train; a restricted fare's condition is in the row's details.",
  anytime: "Unrestricted Anytime Day Returns: valid on any train on the route, so these prices compare with each other directly.",
  return: "Every standard-class return the feed prices, restricted off-peak and advance included. A restricted fare is not valid on every train or at every time \\u2014 its condition is in the row's details.",
  single: "Outbound singles rather than returns. An advance single needs a chosen train, and is labelled where it appears.",
};'''

OLD_RENDER_INTRO = '''function renderIntro() {
  const intro = document.getElementById("pageIntro");
  if (!intro) return;
  if (!DATA.hasJourneys) {
    intro.textContent = "Every destination this feed prices for the budget in the heading, " +
      "with the fare and any conditions that come with it. This build has no timetable, " +
      "so no times or changes are shown.";
    return;
  }
  intro.textContent = "Every destination reachable by train for the budget in the heading, " +
    "with the fastest journey time and the number of changes.";
}'''

NEW_RENDER_INTRO = '''function renderIntro() {
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
}'''

OLD_FIRST_USE = '''ONE_STATION_FIRST_USE = (
    "This page is about one station, and it is the only one this site "
    "was built for: everything below narrows the destinations "
    "reachable from it."
)'''

NEW_FIRST_USE = '''ONE_STATION_FIRST_USE = (
    "This is the only station this build has pages for, so the name above "
    "is not a link."
)'''

OLD_FIRST_USE_MULTI = '''    return (
        "This page is about one station: <b>the station name</b> in the heading "
        "opens a list of the others. Everything below narrows the destinations "
        "from here."
    )'''

NEW_FIRST_USE_MULTI = '''    return "Click the <b>station name</b> to start from somewhere else."'''

patch(
    "page_templates.py",
    [
        (OLD_H1, NEW_H1),
        (OLD_INTRO, NEW_INTRO),
        (OLD_TAGS, NEW_TAGS),
        (OLD_LINK_TERMS, NEW_LINK_TERMS),
        (OLD_FOOTER, NEW_FOOTER),
        (OLD_SEP_CSS, NEW_SEP_CSS),
        (OLD_MODE_NOTE, NEW_MODE_NOTE),
        (OLD_RENDER_INTRO, NEW_RENDER_INTRO),
    ],
)

patch(
    "build_demo_page.py",
    [
        (OLD_FIRST_USE, NEW_FIRST_USE),
        (OLD_FIRST_USE_MULTI, NEW_FIRST_USE_MULTI),
    ],
)
