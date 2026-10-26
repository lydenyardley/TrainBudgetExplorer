"""The markup: a payload and a template become the HTML a reader gets.

The route's script and stylesheet are written once per site rather than inlined into
every page, and the file names carry their own content digest so a reader never runs
code the page was not built with (ADR-0038).
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from trainbudget.fares.atoc_fares import DESTINATION_FACET_SOURCES, DESTINATION_TYPE_FILTERS
# The asset names come from the module that writes the assets, so a release
# that renames one (a script edit, a stylesheet edit) renames it for the pages
# and the prune in the same place, and a test that changes the assets patches
# one name rather than four copies of it (ADR-0071).
from trainbudget.build import build_assets
from trainbudget.build.build_assets import (
    chooser_script_tag,
    page_path_for_route,
    prune_shared_assets,
    station_asset_tag,
    station_script_tag,
    station_style_tag,
    with_base,
    write_chooser_script,
    write_page_atomic,
)
from trainbudget.build.build_payload import encode_payload, without_station_facts
from trainbudget.build.build_provenance import human_date
from trainbudget.build.build_release import (
    DEFAULT_NOTE,
    DEFAULT_PRICE_SOURCE,
    SYNTHETIC_BANNER,
    SYNTHETIC_LABEL,
    crawl_internal_links,
    link_crawl_failed,
    manifest_problems,
    nre_attribution,
    nre_source_line,
    write_release_manifest,
)
from trainbudget.build.page_templates import CHEVRON, CHOOSER_TEMPLATE, PRIVACY, TEMPLATE


def write_release(
    out_dir: Path,
    *,
    index: list[dict],
    routes: list[str],
    budget_pounds: int,
    note: str,
    price_source: str,
    feed_date: str | None,
    analytics: str,
    synthetic: bool,
    privacy_contact: str,
    features: dict,
    built_at: str,
    base_path: str = "",
) -> Path:
    """Write the release's own routes: the chooser, the notice, the manifest.

    One function for both build shapes, because the all-origins path and the
    single-origin path used to hold a copy of this block each -- two writers
    (a plain ``write_text`` against ``write_page_atomic``), two clocks for the
    release's ``builtAt``, and two places for the shapes to drift apart
    (four-dimension audit R8). The chooser carries the build's provenance and
    the notice is dated from the stamp the pages themselves were built with,
    so every route of a release names one build (R3, R6).

    Returns the manifest path, because the caller reports what it wrote.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    # The chooser and the one script it fetches, written together: a release
    # whose chooser names a script it did not write is the contract the crawl
    # below refuses. Both build shapes end here, so neither can drift apart.
    write_chooser_script(out_dir)
    write_page_atomic(
        out_dir / "index.html",
        render_chooser(
            index,
            budget_pounds=budget_pounds,
            analytics=analytics,
            base_path=base_path,
            note=note,
            synthetic=synthetic,
            price_source=price_source,
            feed_date=feed_date,
        ),
    )
    print(f"wrote {out_dir / 'index.html'} (the chooser) offering {len(index)} station(s)")
    privacy = out_dir / "privacy" / "index.html"
    write_page_atomic(
        privacy,
        render_privacy(
            note,
            base_path,
            privacy_contact,
            features,
            synthetic,
            built_at=built_at,
        ),
    )
    print(f"wrote {privacy}")

    broken = crawl_internal_links(out_dir, base_path)
    if broken:
        link_crawl_failed(broken, out_dir)
    print(f"link crawl: every internal link in {out_dir} resolves to a written page")

    manifest_path = write_release_manifest(
        out_dir,
        [with_base(base_path, "/"), with_base(base_path, "/privacy/")] + list(routes),
        price_source=price_source,
        built_at=built_at,
        base_path=base_path,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    missing = manifest_problems(out_dir, manifest, base_path)
    if missing:
        raise SystemExit(
            "error: the release manifest names routes this build did not write:\n"
            + "\n".join(f"  {problem}" for problem in missing)
        )
    print(f"wrote {manifest_path} naming {len(manifest['routes'])} route(s) of this release")
    # Last: a rebuild into the same folder must not accumulate the hashed
    # files an earlier build wrote under another digest (T11). The crawl above
    # already proved every page's requests resolve, so what is removed here is
    # named by nothing.
    prune_shared_assets(
        out_dir,
        build_assets.station_style_asset_name(),
        build_assets.station_script_asset_name(),
        build_assets.chooser_script_asset_name(),
        # Every route this release serves was written by this build a few lines
        # above, and each of those pages requests only the names just passed.
        # Reading them back is the whole release's bytes for an answer already
        # held here (E5); the pages left unread are the ones an earlier build
        # wrote, which are exactly the ones that can name an older asset.
        written=[
            page_path_for_route(out_dir, route, base_path)
            for route in manifest["routes"]
        ],
    )
    return manifest_path


def origin_control(payload: dict) -> str:
    """The origin in the heading: a control only when there is somewhere to go.

    A one-origin build has no other station's page to move to, and a
    "Change starting station" button that opens nothing is a control that lies: it was
    rendered, focusable, announced, and inert, and the browser suite failed on
    it for exactly that reason. So the control is written only when the build
    wrote another station's page, and the name stands as text when it did not.

    The control names itself "Change starting station" in front of the station
    rather than through aria-label, because an aria-label replaces the text the
    heading is read from: the heading's accessible name came out as "from
    Change starting station", which says what the control does and not which
    station the reader is at. The hidden text is the page's own .sr-only
    pattern, and it keeps the station visible in the name (WCAG 2.5.3).
    """

    name = html.escape(payload["origin"]["name"])
    if not picker_has_options(payload):
        # Plain text, not the shared slot: the slot's underline is the promise
        # that this part of the sentence can be changed, and on a build with
        # nowhere to go that promise would be a lie. The browser suite checks
        # this direction too -- it fails a page that renders a control which
        # opens nothing.
        return f'<span class="origin-name">{name}</span>'
    # The wrapper is the slot: it carries the underline and the heading's own
    # weight whether the reader is looking at the station's name or at the field
    # that replaces it, so clicking the name and typing into it are the same
    # gesture in the same place.
    return (
        '<span class="origin-slot-wrap">'
        '<button id="changeOrigin" class="origin-slot" type="button" aria-expanded="false"'
        ' aria-controls="originPicker">'
        '<span class="sr-only">Change starting station: </span>'
        f'<span>{name}</span>{CHEVRON}</button>'
        '</span>'
    )


# The first-use note for a build with nowhere to change to. It is a constant
# because the page ships it twice: as the text in the document, and as the
# sentence the script falls back to if the shared picker list did not arrive.
# The document's own copy names the station; this fallback cannot, because it is
# also the sentence for a build whose shared list failed to load.
ONE_STATION_FIRST_USE = "The station name in the heading is not a link."


def first_use_sentence(payload: dict) -> str:
    """The first-use note, which can only name a control the page has.

    The one thing a first-time reader cannot guess is what the station slot in
    the heading does, so this sentence spends its first clause on it. It named
    a "Change" button until that button became the station's own name with a
    chevron beside it, at which point the sentence pointed at a word the page
    no longer showed; it names what is on the page instead -- the name in the
    heading, which is also the accessible name's own words, so the sentence and
    the control agree for a reader using either.

    On a one-origin build there is no such control -- the same condition
    ``origin_control`` writes for -- so the sentence points at nothing and
    keeps the half that is still true either way: everything below the heading
    narrows the destinations.
    """

    if not picker_has_options(payload):
        name = (payload.get("origin") or {}).get("name")
        if name:
            return (
                f"This site covers {html.escape(name)} only, so the name in the "
                "heading is not a link."
            )
        return ONE_STATION_FIRST_USE
    return "Click the <b>station name</b> to start from somewhere else."


# A template's own placeholder, and nothing else: the pattern is narrow enough
# that a page's prose or payload can never match it by accident.
_PLACEHOLDER = re.compile(r"__[A-Z_]+__")


def refuse_unfilled(page: str, route: str) -> str:
    """The page, or a refusal naming the placeholder the template kept.

    Each route substitutes forty-odd placeholders over the document it just
    embedded a payload into, so a placeholder added to a template and forgotten
    here would ship literally on every page of a release, and a feed's own text
    containing one would be rewritten by the substitution that ran after it. The
    two checks below catch the only placeholders anybody thought to name; this
    one is the whole document, which is the claim that was missing (E3 of the 17
    October 2026 audit).
    """
    match = _PLACEHOLDER.search(page)
    if match:
        raise ValueError(f"the {route} shipped {match.group()} unfilled")
    return page


def destination_type_chip(value: str, label: str) -> str:
    """One destination-type chip, with the count slot its own label carries.

    The count lives in the chip, not beside it, so the number and the thing it
    counts are one target and one label. render() fills it in from the page's own
    rows at the budget on screen.
    """
    return (
        f'<label class="choice-chip"><input type="checkbox" name="destinationType" value="{html.escape(value)}"> '
        f'<span>{html.escape(label)}</span> <span class="chipcount" data-count-for="{html.escape(value)}"></span></label>'
    )


def render_page(
    payload: dict,
    *,
    budget_pounds: int,
    analytics: str = "",
    nre_credit: bool = False,
) -> str:
    """Fill the template from the payload.

    ``analytics`` is whatever snippet the owner chose for counting referrers. It
    is injected as given, and empty by default, so the page is self-contained
    unless someone deliberately decides otherwise.

    ``payload["stationsSrc"]`` is the one deliberate exception to the one-file
    route (ADR-0033, re-scoped 30 September 2026): the picker's list is the
    site's largest repeated item, so a build may point the page at the shared
    asset while the page's own destination payload still travels inline.

    ``payload["scriptSrc"]`` is the second exception, and the larger one: the
    station route's script measured 149,377 bytes byte-identical across 24
    sampled pages, so it ships as one hashed asset beside the stylesheet (T1,
    ADR-0033 amended). The payload travels inline because it is the one part of
    the page that differs per origin.
    """
    prices = [row["adultPence"] for row in payload["destinations"]]
    prices += [row["adultPence"] for row in payload.get("singleDestinations", [])]
    prices += [row["adultPence"] for row in payload.get("anytimeDestinations", [])]
    ceiling = max(1, -(-max(prices or [100]) // 100)) if prices else 100
    # A page opens on a fare, not on an empty table. The opening budget is the
    # build's own figure unless this station prices nothing that cheaply, in
    # which case it opens at the cheapest fare's pound -- the amount the reader
    # would have to spend here to get anywhere, which is the one number the page
    # exists to answer. Nine of the 2,706 station pages the 21 October 2026
    # release wrote were in that position -- Farnborough North's cheapest fare
    # is £29.70, Thorne South's £58.10 -- and each opened saying "No destinations
    # for up to £20.00", with the fares it does have one press away. Opening
    # there rather than on the build's figure is what "open on the mode that has
    # fares" means for a page whose fares are not all inside the opening budget:
    # the list the reader arrives on is the one fare this station sells, and no
    # check about a page's own rows has to be written around an empty first
    # screen.
    opening = max(int(budget_pounds), -(-min(prices or [100]) // 100))
    # The picker's list is the one thing a page no longer carries once the
    # build serves it as the shared asset: sending both would be the hundreds
    # of MB across the network the asset exists to remove. The station's own
    # facts -- its type and its named sites -- are the second, and they are the
    # same document (D1 of the 23 October 2026 byte audit): on a cluster-priced
    # page they were 120 KB of a 690 KB page, identical on every page of the
    # release that lists the place.
    embedded_payload = (
        without_station_facts(
            {key: value for key, value in payload.items() if key != "stations"}
        )
        if payload.get("stationsSrc")
        else payload
    )
    embedded = json.dumps(encode_payload(embedded_payload), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    initial_budget = max(1, min(opening, ceiling))
    # A facet chip is only offered when this page has a destination carrying
    # it. The taxonomy is shared, so a facet with no matches here is a filter
    # that can only ever return nothing, which reads as a broken control rather
    # than an empty result.
    used = {
        kind
        for row in payload["destinations"] + payload.get("singleDestinations", []) + payload.get("anytimeDestinations", [])
        for kind in row.get("destinationTypes") or [row.get("destinationType", "other")]
    }
    # The four settlement bands and the ten thematic facets answer two different
    # questions -- how big a place is, and what it has -- and the row used to put
    # all fifteen chips at one decision point. The bands stay where they are; the
    # facets are one press away behind the chip row's own last chip, so "the
    # other ten" is found where the first five are rather than under a heading a
    # reader has to be told to read (critique item 3, second half). Which chips
    # are which is the same split DESTINATION_TYPE_FILTERS is built from: the
    # facet registry, not a second list that could drift from it.
    facet_keys = {facet.key for facet in DESTINATION_FACET_SOURCES}
    bands = [(value, label) for value, label in DESTINATION_TYPE_FILTERS
             if value not in facet_keys and value in used]
    facets = [(value, label) for value, label in DESTINATION_TYPE_FILTERS
              if value in facet_keys and value in used]
    more_types = ""
    fold = ""
    if facets:
        # "More types (10)" counts the kinds behind it, not the destinations --
        # which is why the number is not a `.chipcount`: that class is the count
        # of destinations a chip would show, and it is read as exactly that by
        # the checks on it. render() keeps it true as the budget narrows what is
        # offered, because the number sits in the chip row where every other
        # number beside a chip is the count of destinations now.
        more_types = (
            '<button type="button" class="choice-chip more-types" id="moreTypes"'
            ' aria-expanded="false" aria-controls="moreTypesPanel">'
            f'<span>More types</span> <span class="more-types-count">({len(facets)})</span>'
            f'{CHEVRON}</button>'
        )
        fold = (
            '<div class="filter-options" id="moreTypesPanel" role="group"'
            ' aria-label="More destination types" hidden>'
            + "".join(destination_type_chip(value, label) for value, label in facets)
            + "</div>"
        )
    destination_filters = (
        ['<label class="choice-chip"><input type="radio" name="destinationType" value="all" checked> <span>All</span></label>']
        + [destination_type_chip(value, label) for value, label in bands]
        + [more_types]
    )
    script_tag = station_script_tag(payload.get("scriptSrc", ""))
    page = (
        TEMPLATE.replace("__DATA__", embedded)
        .replace("__DESTINATION_TYPE_FILTERS__", "".join(destination_filters))
        .replace("__DESTINATION_FACET_FILTERS__", fold)
        .replace("__ORIGIN__", html.escape(payload["origin"]["name"]))
        .replace("__STATIONS_SRC__", station_asset_tag(payload.get("stationsSrc")))
        .replace("__ORIGIN_CONTROL__", origin_control(payload))
        .replace("__FIRST_USE__", first_use_sentence(payload))
        .replace("__FIRST_USE_FALLBACK__", json.dumps(ONE_STATION_FIRST_USE, ensure_ascii=False))
        .replace("__NRE_CREDIT__", nre_attribution() if nre_credit else "")
        .replace("__NRE_SOURCE__", nre_source_line() if nre_credit else "")
        .replace("__MAXPOUNDS__", str(ceiling))
        # S17: the control's stop is a build fact, so the page states it
        # before any script runs. The script keeps it true afterwards.
        .replace("__CEILING_NOTE__", "&pound;" + str(ceiling) + ".00 for one adult")
        .replace("__BUDGET__", str(initial_budget))
        # D6 of the 17 October 2026 critique: a synthetic build's note said in
        # the footer what the banner at the top already says, so the banner is
        # the only copy. A real build never carries that note; one with a
        # provenance note of its own still gets the paragraph.
        .replace(
            "__NOTE__",
            "" if payload.get("synthetic", True) else note_markup(payload["note"]),
        )
        # C5: the paragraph about times is the payload's own sentence, which
        # build_payload chose from hasJourneys. A template that wrote its own
        # would be the second owner of the claim.
        .replace("__SERVICE_CLAIM__", html.escape(payload["pricingNote"]))
        .replace("__BASE__", payload.get("baseHref", "/").rstrip("/"))
        .replace("__ANALYTICS__", analytics)
        .replace("__SYNTHETIC__", "true" if payload.get("synthetic", True) else "false")
        .replace("__SYNTHETIC_BANNER__", synthetic_markup(payload.get("synthetic", True)))
        .replace("__STATION_STYLE__", station_style_tag(payload.get("styleSrc", "")))
        .replace("__STATION_SCRIPT__", script_tag)
    )
    # A station page with no stylesheet link is a page with no styling and no
    # request for any, which reads as a broken page rather than a broken build.
    # with_shared() cannot catch this one: the link needs the path this release
    # is published at, which only the build knows (ADR-0033 inlined the block;
    # ADR-0047 fetches it). Both ways of getting here are refused -- an
    # unfilled placeholder, and a payload that never named the document.
    if "__STATION_STYLE__" in page or '<link rel="stylesheet"' not in page:
        raise ValueError("the station page shipped without a stylesheet link")
    # The same rule for the route's script, and it is the one that decides
    # whether a page carries 149 KB of code or a request for it. A page whose
    # payload names no script would render tables and wire nothing.
    if "__STATION_SCRIPT__" in page or not script_tag:
        raise ValueError("the station page shipped without its script")
    return refuse_unfilled(page, "station page")


def note_markup(note: str, css_class: str = "") -> str:
    """A route's provenance note as its own paragraph, or nothing at all.

    A real build passes ``""`` for the note, and the template used to ship an
    empty ``<p>`` wherever the note would have been -- a block of dead space
    saying nothing (audit item 8, 9 October 2026). ``synthetic_markup`` beside
    this is the same shape of fix for the same reason.
    """
    if not note:
        return ""
    return f'<p class="{css_class}">{note}</p>' if css_class else f"<p>{note}</p>"


def synthetic_markup(synthetic: bool) -> str:
    """The visible synthetic-data state for a route, or nothing for a real one.

    S45: the marker is markup rather than a sentence passed in, so a build
    cannot ship a page whose banner says something the rest of the page
    contradicts. A real build writes no banner and keeps ``data-synthetic="false"``,
    which is the state a screenshot fixture can assert in either direction.
    """
    if not synthetic:
        return ""
    return (
        '<p class="synthetic-banner" data-synthetic-banner>'
        f"<strong>{html.escape(SYNTHETIC_LABEL)}</strong> {html.escape(SYNTHETIC_BANNER)}</p>"
    )


def render_privacy(
    note: str,
    base_path: str = "",
    contact: str = "",
    features: dict | None = None,
    synthetic: bool = True,
    built_at: str | None = None,
) -> str:
    if not contact.strip():
        raise ValueError("a privacy contact is required before publishing the privacy page")
    features = features or {}
    # The three sentences a reader's decision depends on, written from what the
    # build ships. A behaviour that is on is named; one that is off is named as
    # off. Either way the page cannot claim a privacy practice the build does
    # not have.
    practices = [
        "No cookies are set by this site.",
        # C10: the page used to claim the budget and the selected types "never
        # leave your device" while also writing both into the address, and the
        # address is in every request the host logs. The honest statement is
        # that the state is client-side and is disclosed where it is sent: in
        # the URL, to the host's logs and to anyone a link is shared with. The
        # full explanation is its own section on the page; this is the list
        # entry, so it states the fact and points there rather than saying the
        # same paragraph twice.
        # One sentence, not the section it points at (audit item 17, 9 October
        # 2026): the paragraph and the two bullets below make the same point
        # with more room, and a list entry that repeats them is read first and
        # learned last. The word stays true because the summary now comes
        # before the deep dive: "What this site does" is the first section and
        # "What stays in the address bar" the one it points down to (route
        # audit item 18, 9 October 2026).
        (
            "Your search is kept in the page's web address, so the host "
            "serving these files sees it in its request logs; what stays in "
            "the address bar, below, explains it in full."
        ),
        (
            "This build injects an analytics snippet, so visits are measured by "
            "that snippet. The reviewed plan it is allowed under: it "
            + features.get("measurement", "has none recorded, which should not "
              "happen -- a build cannot inject a snippet without one (ADR-0032).")
            if features.get("analytics")
            else "No analytics run. If analytics are ever added to this site, this page will name them here first."
        ),
    ]
    # C17/D12 of the 17 October 2026 critique: the list used to end with "This
    # site does not collect visit data", which was the union of the cookie and
    # analytics sentences already above it and added nothing a reader could act
    # on. A build that does track a click still says so, because that is a
    # third practice rather than a restatement.
    if features.get("trackedLinks"):
        practices.append(
            "Ticket buttons carry a tracked link, so the seller is told which page sent "
            "the reader. The fare pages say so in their footer."
        )
    if features.get("affiliate"):
        practices.append(
            "Ticket buttons pass through the " + features["affiliate"] +
            " affiliate network, which may record the click and the fare shown."
        )
    # The date this notice's build-dependent sentences were true of: "no
    # analytics run" is a promise about a build, and the build knows when it
    # was made (route audit item 16, 9 October 2026).
    # "dated", not "published": a build nobody has deployed is not a
    # publication, so the verb was false of every local build and true only of
    # the ones a run reached the deploy job with (clarity audit item 42,
    # answered 16 October 2026). The date is what the sentence needs, and the
    # date is true either way.
    # C20/D14 of the 17 October 2026 critique: "This notice describes the build
    # dated ..." is a sentence for a maintainer. A reader of a static notice
    # wants to know when the notice last changed, which is the same date.
    built_line = (
        '<p class="muted" id="builtLine">Last updated '
        + html.escape(human_date(built_at[:10]))
        + ".</p>"
        if built_at
        else ""
    )
    privacy = (
        PRIVACY.replace("__BASE__", base_path)
        .replace("__BUILT_LINE__", built_line)
        .replace("__NOTE__", note_markup(note, "muted"))
        # Escaped like every other string on this route: the address is
        # operator-supplied, and a page whose promise is that it says exactly
        # what the build does cannot be the one place a character becomes markup.
        .replace("__CONTACT__", html.escape(contact))
        .replace("__PRACTICES__", "".join(f"  <li>{item}</li>\n" for item in practices))
        .replace("__SYNTHETIC__", "true" if synthetic else "false")
        .replace("__SYNTHETIC_BANNER__", synthetic_markup(synthetic))
    )
    return refuse_unfilled(privacy, "privacy page")


def picker_has_options(payload: dict) -> bool:
    """Whether this page was built with another station's page to move to.

    Two ways to answer yes, because the list arrives two ways: inline in the
    payload for a build that ships one file per route, and as the shared asset
    (``stationsSrc``) for the network build that cannot afford 2,712 copies of
    it. The heading control and the first-use note both ask this question rather
    than reading the list, so a page cannot render a control while shipping no
    options, or ship options with no way to open them.
    """
    return bool(payload.get("stations") or payload.get("stationsSrc"))


def render_chooser(
    index: list[dict],
    *,
    budget_pounds: int,
    analytics: str = "",
    base_path: str = "",
    note: str = DEFAULT_NOTE,
    synthetic: bool = True,
    price_source: str = DEFAULT_PRICE_SOURCE,
    feed_date: str | None = None,
) -> str:
    """The root page: the station chooser itself, with no fares on it.

    ``index`` is the priced station index -- the root offers exactly the
    stations whose pages this build wrote, and nothing else, so a root that
    names a station always has a page behind it (S01).

    A release that priced exactly one station is not a chooser: there is no
    choice to make, and the published artefact used to ask the reader to type
    a station that could only ever be the one it already knew. So it states
    the choice in its shape as well as its sentence -- the heading names that
    station, the field and the ordering note are absent, and the one row is
    the page to open (audit recommendation 2, 30 September 2026).

    ``note`` is the same provenance note the station pages carry, so a real-feed
    site does not have a chooser claiming synthetic data above pages that name
    the real feed.

    ``price_source`` and ``feed_date`` are the station page's own provenance:
    the entry route is the one every community link points at, and it used to
    say what the ordering was while saying nothing about what the site was,
    whose feed its prices came from, or how old that feed was
    (four-dimension audit R3, route audit item 6).
    """
    # One sentence, composed here from the pair: the source names the feed and
    # the date travels beside it. The date used to be appended to a source
    # sentence that already ended in one, and this line printed it twice -- the
    # first sentence a reader arriving from a community post reads.
    provenance = f"Prices from {price_source}"
    if feed_date:
        provenance += f", downloaded {human_date(feed_date)}"
    provenance += "."
    stations = json.dumps(
        [
            {"name": e["name"], "crs": e["crs"], "href": with_base(base_path, f"/from/{e['slug']}/"), "destinations": e["destinations"]}
            for e in index
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    ).replace("</", "<\\/")
    # S11 of the 19 October 2026 critique: one line names the three columns every
    # row carries, because a row read "GRANTHAM GRN 22" and only its own
    # accessible name said what the number counted. It is written once and for
    # the eye -- each row's name already carries the count -- and a build that
    # priced no station leaves it out rather than labelling a list that is not
    # there.
    columns = (
        '<p class="eyebrow" id="picksColumns" aria-hidden="true">'
        "Station &middot; Code &middot; Destinations</p>"
        if index
        else ""
    )
    if len(index) == 1:
        only = index[0]
        origin_clause = (
            '<span id="originClause"><span class="heading-lead">from</span> '
            '<span class="origin-name">'
            f'{html.escape(only["name"])}</span></span>'
        )
        intro = (
            f'<p class="sub">This site covers {html.escape(only["name"])} only. Open its '
            "row below for every destination your budget reaches from there.</p>"
        )
        # Nothing is ordered, so the page makes no ranking claim: an ordering
        # note over one row describes a choice the reader does not have.
        ordering = ""
        title_suffix = only["name"]
    else:
        # C14/D11 of the 17 October 2026 critique: the field's placeholder is
        # the prompt. It used to be the bare word "station" under an
        # instruction paragraph that said what to do with it, so the sentence
        # read "from station" and the instruction had to explain it. "your
        # station" is a word the sentence can take, and the paragraph is gone.
        origin_clause = (
            '<span id="originClause"><span class="heading-lead">from</span> '
            '<span class="origin-slot-wrap" id="originField">'
            '<input id="originSearch" type="search" placeholder="your station" autocomplete="off" '
            'aria-label="The station you are starting from" aria-describedby="pickStatus" '
            'aria-controls="picks"></span></span>'
        )
        # S2 of the 19 October 2026 critique: the field in the heading is the
        # page's whole job and it looked like the end of the title -- no verb, no
        # label, nothing that says typing is possible. The station page spends a
        # sentence on the same control; this is that sentence, under the same
        # heading, before the list rather than in a tooltip.
        # A build that priced nothing has no field left by the time its script
        # has run (the station clause is hidden and the page says there is
        # nothing here yet), so there is nothing for the sentence to point at.
        intro = (
            '<p class="sub" id="chooserHint">Type your station\u2019s name, or pick '
            "one below.</p>"
            if index
            else ""
        )
        ordering = '<p class="tag" id="orderingNote">Most first.</p>'
        title_suffix = "pick your station"
    chooser = (
        CHOOSER_TEMPLATE.replace("__STATIONS__", stations)
        .replace("__ORIGIN_CLAUSE__", origin_clause)
        .replace("__CHOOSER_INTRO__", intro)
        .replace("__PICKS_COLUMNS__", columns)
        .replace("__PROVENANCE__", html.escape(provenance))
        .replace("__ORDERING_NOTE__", ordering)
        .replace("__TITLE_SUFFIX_HTML__", html.escape(title_suffix))
        .replace("__TITLE_SUFFIX_JS__", json.dumps(title_suffix, ensure_ascii=False))
        .replace("__BUDGET__", str(budget_pounds))
        .replace("__NOTE__", note_markup(note, "tag"))
        .replace("__BASE__", base_path.rstrip("/"))
        .replace("__CHOOSER_SCRIPT__", chooser_script_tag(with_base(base_path, "/" + build_assets.chooser_script_asset_name())))
        .replace("__ANALYTICS__", analytics)
        .replace("__SYNTHETIC__", "true" if synthetic else "false")
        .replace("__SYNTHETIC_BANNER__", synthetic_markup(synthetic))
    )
    return refuse_unfilled(chooser, "station list")
