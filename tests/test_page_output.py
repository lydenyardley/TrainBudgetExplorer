"""The files a build writes rather than the page's own prose: the shared
station asset, slug and route agreement, the release manifest, and the
payload the page carries.

Split out of tests/test_build_demo_page.py by feature seam (F6 of the 8
October 2026 agent-efficiency audit)."""

from __future__ import annotations

import json
import re
import tempfile
import unittest
import contextlib
import io
from pathlib import Path

import build_demo_page
from atoc_fares import LOCATION, FLOW_F, FLOW_T, FaresDb
from atoc_timetable import TimetableDb
from build_demo_page import build_payload, build_station_index, encode_payload, render_page
from make_synthetic_feed import _line, build_synthetic_feed, build_synthetic_timetable

from tests.page_harness import embedded_payload, embedded_text, hydrate_rows, page_script, setUpModule, station_page, tearDownModule


class SharedStationAssetTest(unittest.TestCase):
    """Unit 1d: the picker's list is one file per site, not a copy per page.

    The station list was the release's largest repeated item -- the same rows on
    every page, 445 MB across the projected network -- so the network build
    writes it once and each page names it. The page's own destinations still
    travel inside it (ADR-0033, re-scoped), and a page whose copy of the list
    did not arrive states the station as text rather than offering a control
    that opens nothing.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.feed = build_synthetic_feed(root / "fares", include_restrictions=True)
        self.timetable = build_synthetic_timetable(root / "timetable")
        self.out = root / "site" / "index.html"
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = build_demo_page.main(
                [
                    "--feed",
                    str(self.feed),
                    "--timetable",
                    str(self.timetable),
                    "--all-origins",
                    "--out",
                    str(self.out),
                ]
            )
        self.assertEqual(code, 0)
        self.log = buffer.getvalue()
        self.site = self.out.parent

    def test_the_whole_site_gets_one_station_asset(self) -> None:
        assets = sorted(self.site.rglob("stations.js"))
        self.assertEqual(
            [path.relative_to(self.site).as_posix() for path in assets], ["stations.js"]
        )
        asset = assets[0].read_text(encoding="utf-8")
        self.assertIn("window.TBE_STATIONS = ", asset)
        rows = json.loads(asset.split("window.TBE_STATIONS = ", 1)[1].rstrip().rstrip(";"))
        # Every station this build wrote, including each page's own: a page
        # filters its own origin out as it loads, which is what keeps this one
        # file byte-identical for every page.
        self.assertEqual(sorted(row["crs"] for row in rows), ["GRN", "NOT"])
        self.assertTrue(all(row["href"].startswith("/from/") for row in rows))
        self.assertIn("stations.js", self.log)

    def test_a_station_page_names_the_asset_and_ships_no_station_rows(self) -> None:
        pages = sorted((self.site / "from").glob("*/index.html"))
        self.assertEqual(len(pages), 2)
        for page in pages:
            html = page.read_text(encoding="utf-8")
            self.assertIn('<script src="/stations.js"></script>', html)
            self.assertNotIn('"stations":', embedded_text(html))
            # The page keeps its own destination rows, and the heading control
            # is still the page's own markup rather than something built here.
            self.assertIn('id="changeOrigin"', html)
            self.assertTrue(embedded_payload(html)["destinations"])

    def test_the_page_puts_the_station_name_back_if_the_asset_does_not_arrive(self) -> None:
        page = (self.site / "from" / "grantham" / "index.html").read_text(encoding="utf-8")
        # The fallback is a name in the heading, never an empty one: a heading
        # reading "from" and nothing is the failure this guards against. The
        # sentence travels in the page, the branch that writes it travels in
        # the route's script, and the browser suite drives the fallback itself
        # over a page whose asset is missing.
        self.assertIn("FIRST_USE_FALLBACK", page)
        script = page_script(page)
        self.assertIn("origin-name", script)
        self.assertIn("FIRST_USE_FALLBACK", script)

    def test_the_stylesheet_is_written_once_and_named_for_its_own_bytes(self) -> None:
        # One file beside the pages, and every station page names it. The
        # filename holds a digest of the stylesheet, so a changed stylesheet is
        # a new file: a cached copy can never be served beside a page built
        # from another revision of the CSS, and no build step has to be told to
        # rename anything.
        from page_templates import STATION_STYLESHEET

        name = build_demo_page.station_style_asset_name()
        assets = sorted(path.name for path in self.site.rglob("*.css"))
        self.assertEqual(assets, [name], assets)
        written = (self.site / name).read_text(encoding="utf-8")
        self.assertEqual(written, STATION_STYLESHEET)
        self.assertTrue(name.startswith("station-") and name.endswith(".css"), name)
        self.assertRegex(name, r"^station-[0-9a-f]{12}\.css$")
        self.assertIn(name, self.log, "the build says what it wrote and where")

    def test_every_station_page_names_the_script_and_inlines_none_of_it(self) -> None:
        from page_templates import STATION_SCRIPT

        pages = sorted((self.site / "from").glob("*/index.html"))
        self.assertEqual(len(pages), 2)
        for page in pages:
            html = page.read_text(encoding="utf-8")
            self.assertIn(build_demo_page.station_script_tag("/" + build_demo_page.station_script_asset_name()), html)
            # Not inlined: the whole point is that 2,712 pages stop carrying the
            # same 149 KB, so a page that still held the route's code would mean
            # the file is being fetched and paid for anyway. The body's one
            # inline block is the handoff the asset reads -- the page's own
            # DATA -- and nothing else.
            body = html.split("<body", 1)[1]
            blocks = re.findall(r"<script>(.*?)</script>", body, re.DOTALL)
            self.assertEqual(len(blocks), 1, [block[:60] for block in blocks])
            self.assertTrue(blocks[0].strip().startswith("window.TBE_DATA = "))
            self.assertLess(len(blocks[0]), len(STATION_SCRIPT))

    def test_the_script_is_written_once_and_named_for_its_own_bytes(self) -> None:
        # One file beside the pages, and every station page names it. The
        # filename holds a digest of the script, so a changed script is a new
        # file: a cached copy can never be served beside a page built from
        # another revision of the code, and no build step has to be told to
        # rename anything.
        from page_templates import STATION_SCRIPT

        name = build_demo_page.station_script_asset_name()
        assets = sorted(
            path.name
            for path in self.site.glob("station-*.js")
        )
        self.assertEqual(assets, [name], assets)
        written = (self.site / name).read_text(encoding="utf-8")
        self.assertEqual(written, STATION_SCRIPT)
        self.assertRegex(name, r"^station-[0-9a-f]{12}\.js$")
        self.assertIn(name, self.log, "the build says what it wrote and where")

    def test_the_chooser_names_its_script_and_the_build_writes_it(self) -> None:
        # The chooser's code moves out of the page for the same reason the
        # station route's does (T10): one file beside the release rather than a
        # copy inside the one page that carries it.
        from page_templates import CHOOSER_SCRIPT

        chooser = (self.site / "index.html").read_text(encoding="utf-8")
        name = build_demo_page.chooser_script_asset_name()
        self.assertIn(build_demo_page.chooser_script_tag("/" + name), chooser)
        written = (self.site / name).read_text(encoding="utf-8")
        self.assertEqual(written, CHOOSER_SCRIPT)
        self.assertRegex(name, r"^chooser-[0-9a-f]{12}\.js$")
        # The body's one inline block is the handoff the asset reads -- the
        # build's station list -- and nothing else.
        body = chooser.split("<body", 1)[1]
        blocks = re.findall(r"<script>(.*?)</script>", body, re.DOTALL)
        self.assertEqual(len(blocks), 1, [block[:60] for block in blocks])
        self.assertTrue(blocks[0].strip().startswith("window.TBE_CHOOSER_STATIONS = "))

    def test_the_page_takes_the_switch_away_when_the_stylesheet_does_not_arrive(self) -> None:
        # The picker's failure mode, one route down: a control that cannot do
        # what it offers is removed rather than left inert, and the page says
        # what state it is in. A switch that rewrites an attribute no rule reads
        # is the same defect as a picker that opens an empty panel. The browser
        # suite drives the fallback itself over a page whose stylesheet is
        # withheld (ADR-0047).
        page = (self.site / "from" / "grantham" / "index.html").read_text(encoding="utf-8")
        self.assertIn('class="sub" id="styleNote" hidden', page)
        self.assertIn("stylesheetArrived", page)
        self.assertIn("--tbe-stylesheet", page)
        self.assertIn("styling did not load", page)
        # Whether the switch is there and whether the note appears, and when,
        # is left to the browser suite: it withholds the document on a second
        # page in the same context and reads the element, which is the only
        # place the answer is observable.

    def test_the_crawl_resolves_a_stylesheet_a_page_asks_for(self) -> None:
        # The crawl read href attributes only, so a page could have asked for a
        # stylesheet the build never wrote and the run would still have said
        # every internal link resolves. A shared document is a route like any
        # other, and it is named in src as well as href.
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            (site / "from" / "grantham").mkdir(parents=True)
            (site / "from" / "grantham" / "index.html").write_text(
                '<link rel="stylesheet" href="/station-abc.css">', encoding="utf-8"
            )
            broken = build_demo_page.crawl_internal_links(site)
            self.assertEqual(len(broken), 1, broken)
            self.assertIn("station-abc.css", broken[0])
            (site / "station-abc.css").write_text(":root { --x: 1; }", encoding="utf-8")
            self.assertEqual(build_demo_page.crawl_internal_links(site), [])
            # And a <script src> is followed now, which it was not: the
            # picker's asset was named in one and the crawl never looked.
            (site / "index.html").write_text(
                '<script src="/stations.js"></script>', encoding="utf-8"
            )
            self.assertEqual(
                [entry.split(" links to ")[1].split(",")[0] for entry in
                 build_demo_page.crawl_internal_links(site)],
                ["/stations.js"],
            )

    def test_the_asset_is_the_whole_list_in_plain_objects(self) -> None:
        rows = build_demo_page.station_asset_rows(
            [{"name": "A & B", "crs": "ABB", "slug": "a-b", "destinations": 2}],
            base_path="/tb",
        )
        self.assertEqual(rows, [{"name": "A & B", "crs": "ABB", "href": "/tb/from/a-b/"}])
        asset = build_demo_page.render_station_asset(rows)
        self.assertTrue(asset.endswith(";\n"), asset[-20:])
        # Plain objects keep "href" in the file, which is the shape the route
        # crawl reads: a table of cells would hide every option from it.
        self.assertIn('"href":"/tb/from/a-b/"', asset)

    def test_the_crawl_reads_the_asset_and_fails_a_route_it_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            (site / "from" / "grantham").mkdir(parents=True)
            (site / "from" / "grantham" / "index.html").write_text(
                "<p>the page asks for the asset, and the asset asks for a route</p>",
                encoding="utf-8",
            )
            (site / "stations.js").write_text(
                'window.TBE_STATIONS = [{"name":"LINCOLN","crs":"LCN","href":"/from/lincoln/"}];\n',
                encoding="utf-8",
            )
            broken = build_demo_page.crawl_internal_links(site)
            self.assertEqual(len(broken), 1, broken)
            self.assertIn("stations.js", broken[0])
            self.assertIn("/from/lincoln/", broken[0])
            (site / "from" / "lincoln").mkdir()
            (site / "from" / "lincoln" / "index.html").write_text("ok", encoding="utf-8")
            self.assertEqual(build_demo_page.crawl_internal_links(site), [])

    def test_a_page_written_on_any_os_is_the_same_bytes(self) -> None:
        # A page is bytes a host serves, so the same build has to produce the
        # same bytes on every machine: a text-mode write on Windows turns every
        # newline in the template into CRLF, and the release built there is
        # then not the release CI builds while claiming to be (four-dimension
        # audit R14). The byte budget only ever measures one of the two.
        page = self.site / "from" / "grantham" / "index.html"
        raw = page.read_bytes()
        self.assertNotIn(b"\r", raw, "a station page was written with CRLF")
        self.assertTrue(raw.endswith(b"\n"), raw[-20:])
        self.assertNotIn(b"\r", (self.site / "index.html").read_bytes())
        self.assertNotIn(b"\r", (self.site / "privacy" / "index.html").read_bytes())
        manifest = self.site / "release-manifest.json"
        self.assertTrue(manifest.is_file(), "the release writes its manifest")
        self.assertNotIn(b"\r", manifest.read_bytes())

class SlugAgreementTest(unittest.TestCase):
    """Audit finding A1: both build modes must agree on station addresses.

    Slugs are disambiguated by a shared ``taken`` set, so a build that computed
    them per-station (an empty set each time) can link to a folder the
    --all-origins build wrote under a different name. Two stations named
    NOTTINGHAM exercise it; the synthetic feed alone never would.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        cls.timetable_path = build_synthetic_timetable(root / "timetable")
        cls.timetable = TimetableDb().load_feed(cls.timetable_path)
        # The base feed plus a second station also called NOTTINGHAM (NMP),
        # priced from and to GRANTHAM, written in the real record layouts. NMP
        # needs an outgoing flow of its own so it is a priceable origin -- a
        # slug collision only bites when both same-named stations get pages.
        cls.feed = build_synthetic_feed(
            root / "fares", include_unserved_station=True, include_restrictions=True
        )
        with open(cls.feed / "rjfaf.loc", "a", encoding="utf-8") as locations:
            locations.write(
                _line(
                    {
                        "update_marker": "A",
                        "record_type": "L",
                        "nlc": "8000",
                        "description": "NOTTINGHAM",
                        "crs": "NMP",
                    },
                    LOCATION,
                )
                + "\n"
            )
        with open(cls.feed / "rjfaf.ffl", "a", encoding="utf-8") as flows:
            flows.write(
                _line(
                    {
                        "update_marker": "A",
                        "record_type": "F",
                        "origin_nlc": "1000",
                        "destination_nlc": "8000",
                        "route_code": "00000",
                        "flow_id": "0000020",
                    },
                    FLOW_F,
                )
                + "\n"
                + _line(
                    {
                        "update_marker": "A",
                        "record_type": "T",
                        "flow_id": "0000020",
                        "ticket_code": "SDR",
                        "fare_pence": "1050",
                        "restriction_code": "",
                    },
                    FLOW_T,
                )
                + "\n"
                + _line(
                    {
                        "update_marker": "A",
                        "record_type": "F",
                        "origin_nlc": "8000",
                        "destination_nlc": "1000",
                        "route_code": "00000",
                        "flow_id": "0000021",
                    },
                    FLOW_F,
                )
                + "\n"
                + _line(
                    {
                        "update_marker": "A",
                        "record_type": "T",
                        "flow_id": "0000021",
                        "ticket_code": "SDR",
                        "fare_pence": "1050",
                        "restriction_code": "",
                    },
                    FLOW_T,
                )
                + "\n"
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_single_origin_picker_links_match_all_origins_folders(self) -> None:
        fares = FaresDb().load_feed(self.feed)
        # The single-origin build's picker: built the way main() builds it.
        payload = build_payload(fares, self.timetable, "GRN")
        hrefs = {station["crs"]: station["href"] for station in payload["stations"]}
        # The all-origins build's folder names: the index's slugs.
        # Counted the same way main() counts, so this test cannot pass on a
        # station set the --all-origins build would not write.
        index = build_station_index(
            {
                crs: build_demo_page._priced_destinations(fares, self.timetable, crs)
                for crs in fares.locations_by_crs
            },
            fares.locations_by_crs,
        )
        folders = {entry["crs"]: entry["slug"] for entry in index}
        # A real collision happened: the two NOTTINGHAMs cannot both be
        # "nottingham", exactly the case the empty-set slug call got wrong.
        # Both carry their CRS, whatever order the build sees them in.
        self.assertEqual(folders["NOT"], "nottingham-not")
        self.assertEqual(folders["NMP"], "nottingham-nmp")
        for crs, slug in folders.items():
            if crs == "GRN":  # the page's own origin is not in its picker
                continue
            self.assertEqual(hrefs[crs], f"/from/{slug}/", crs)

    def test_the_all_origins_chooser_links_resolve_to_written_pages(self) -> None:
        out = Path(self._tmp.name) / "site" / "index.html"
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = build_demo_page.main(
                [
                    "--feed", str(self.feed),
                    "--timetable", str(self.timetable_path),
                    "--all-origins", "--out", str(out),
                ]
            )
        self.assertEqual(code, 0)
        chooser = out.read_text(encoding="utf-8")
        for page in (out.parent / "from").iterdir():
            self.assertIn(f"/from/{page.name}/", chooser)

class RouteManifestTest(unittest.TestCase):
    """S01, S03, S04, S07: one manifest of the routes a release actually serves.

    The re-envision audit names the route contract as the weakest subsystem: a
    single-origin build used to publish a station page at the root whose Change
    picker linked to every station in the feed, none of which it had written.
    A release now writes a root at the site root -- the chooser when it offers a
    choice, and the one station named in the heading when that is all it priced
    (recommendation 2, 30 September 2026) -- one page per station at its
    canonical /from/<slug>/ route, and the privacy page, and proves every
    internal link resolves before calling the build good.
    """

    def build_site(self, root: Path, *extra: str) -> tuple[int, str]:
        feed = build_synthetic_feed(root / "fares", include_restrictions=True)
        out = root / "site" / "index.html"
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = build_demo_page.main(["--feed", str(feed), "--out", str(out), *extra])
        return code, buffer.getvalue()

    def test_a_single_origin_build_is_a_site_with_its_own_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, log = self.build_site(root)
            self.assertEqual(code, 0)
            site = root / "site"
            # The root is this release's own: it names the one station it priced
            # rather than asking for it, the station has its canonical route, and
            # the privacy page the footer links to is present (S01, S04, rec 2).
            chooser = (site / "index.html").read_text(encoding="utf-8")
            self.assertIn('class="origin-name"', chooser)
            self.assertNotIn('id="originSearch"', chooser)
            with self.assertRaises(AssertionError):
                # The root carries no fares, so it embeds no priced payload
                # for a reader to be shown a table from. The chooser's
                # station list is not that: it is names and counts.
                embedded_payload(chooser)
            station = station_page(site / "index.html")
            self.assertTrue(station.is_file())
            self.assertTrue(
                embedded_payload(station.read_text(encoding="utf-8"))["destinations"]
            )
            self.assertTrue((site / "privacy" / "index.html").is_file())
            self.assertIn("link crawl", log)

    def test_the_root_names_only_the_stations_the_build_wrote(self) -> None:
        # The single-origin picker used to offer all 3,424 feed stations. The
        # manifest is what the chooser, the picker and the crawl all read, so a
        # named station always has a page behind it.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_site(root)
            chooser = (root / "site" / "index.html").read_text(encoding="utf-8")
            match = re.search(r"window\.TBE_CHOOSER_STATIONS = (\[.*?\]);", chooser, re.DOTALL)
            self.assertIsNotNone(match)
            stations = json.loads(match.group(1))
            self.assertEqual([entry["crs"] for entry in stations], ["GRN"])
            for entry in stations:
                target = root / "site" / entry["href"].strip("/") / "index.html"
                self.assertTrue(target.is_file(), f"chooser names {entry['href']} with no page")

    def test_a_station_page_links_back_to_the_chooser(self) -> None:
        # A one-station site has no sibling to switch to, so the way back to the
        # root is the "All stations" link, not a picker with nothing in it.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_site(root)
            station = station_page(root / "site" / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="/"', station)

    def test_every_internal_link_in_a_built_site_resolves(self) -> None:
        # S03: the crawl is the proof, run from the generated files themselves.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_site(root)
            self.assertEqual(build_demo_page.crawl_internal_links(root / "site"), [])

    def test_the_link_crawl_names_a_link_to_a_page_that_was_not_written(self) -> None:
        # The failure the crawl exists to catch: a picker or footer link to a
        # page the build did not produce must be found, not shipped.
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            (site / "from" / "grantham").mkdir(parents=True)
            (site / "from" / "grantham" / "index.html").write_text(
                '<a href="/from/nottingham/">Nottingham</a><a href="/privacy/">Privacy</a>',
                encoding="utf-8",
            )
            broken = build_demo_page.crawl_internal_links(site)
            self.assertEqual(len(broken), 2, broken)
            self.assertIn("nottingham", broken[0])
            self.assertIn("privacy", broken[1])

    def test_the_crawl_ignores_external_and_seller_links(self) -> None:
        # A link off the site is not this site's contract; the crawl must not
        # fail on the seller's URL or a heritage link.
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            site.mkdir(parents=True)
            (site / "index.html").write_text(
                '<a href="https://example.test/buy">Buy</a>'
                '<a href="//cdn.example.test/x">CDN</a>'
                '<a href="/privacy/">Privacy</a>',
                encoding="utf-8",
            )
            (site / "privacy").mkdir()
            (site / "privacy" / "index.html").write_text("<p>privacy</p>", encoding="utf-8")
            self.assertEqual(build_demo_page.crawl_internal_links(site), [])

    def test_the_crawl_strips_the_site_base_path(self) -> None:
        # A project site serves under /tb/, so its internal links carry the
        # base. The crawl resolves them against files on disk, not against the
        # domain, so the base is stripped before the file lookup.
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            (site / "from" / "grantham").mkdir(parents=True)
            (site / "from" / "grantham" / "index.html").write_text(
                '<a href="/tb/from/nottingham/">Nottingham</a>', encoding="utf-8"
            )
            broken = build_demo_page.crawl_internal_links(site, base_path="/tb")
            self.assertEqual(len(broken), 1, broken)
            (site / "from" / "nottingham").mkdir()
            (site / "from" / "nottingham" / "index.html").write_text("<p>N</p>", encoding="utf-8")
            self.assertEqual(build_demo_page.crawl_internal_links(site, base_path="/tb"), [])

    def test_the_crawl_fail_refuses_to_ship_a_broken_site(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            site.mkdir()
            (site / "index.html").write_text('<a href="/nowhere/">x</a>', encoding="utf-8")
            with self.assertRaises(SystemExit):
                build_demo_page.link_crawl_failed(["index.html links to /nowhere/"], site)

    def test_the_chooser_search_is_wired_to_its_list(self) -> None:
        # The root page is the departure picker, so the one control it exists
        # for has to filter the list. It had no listener at all, so typing a
        # name left every station on screen and the list read as a result.
        # Built with --all-origins, because a one-station release has no search
        # to wire: its root names the station instead of asking for it (rec 2).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_site(root, "--all-origins")
            site = root / "site"
            chooser = (site / "index.html").read_text(encoding="utf-8")
            # The route is handed what was typed and the station being offered,
            # so its list can show the matches a completion would otherwise
            # hide (audit items 1 and 2, 9 October 2026). The wiring travels in
            # the route's own asset rather than in the page, so this reads the
            # file the chooser names; the browser suite drives the typing, the
            # completion and the re-render over the real chooser, which is where
            # the claim actually lives.
            match = re.search(r'<script src="([^"]*chooser-[0-9a-f]+\.js)"', chooser)
            self.assertIsNotNone(match, "the chooser names no shared script")
            script = (site / match.group(1).rsplit("/", 1)[-1]).read_text(encoding="utf-8")
            self.assertIn("onChange", script)
            self.assertIn("typedQuery", script)

    def test_the_chooser_links_to_the_privacy_page(self) -> None:
        # The root page is where a reader starts, so the thing that says what
        # the site sends has to be reachable from it, not only from a station.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_site(root)
            chooser = (root / "site" / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="/privacy/"', chooser)
            # A base path has to prefix it too, and a leading slash must not be
            # doubled: "//privacy/" is a different host, not this site.
            self.assertIn('href="/tb/privacy/"', build_demo_page.render_chooser([], budget_pounds=20, base_path="/tb"))

    def test_the_crawl_reads_the_links_the_chooser_builds_in_the_browser(self) -> None:
        # The chooser's station links are written by its script from an
        # embedded array, so a crawl reading only href attributes would check
        # the root page and find nothing to check.
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            site.mkdir(parents=True)
            (site / "index.html").write_text(
                'const STATIONS = [{"name":"Grantham","crs":"GRN","href":"/from/grantham/"}];',
                encoding="utf-8",
            )
            broken = build_demo_page.crawl_internal_links(site)
            self.assertEqual(len(broken), 1, broken)
            self.assertIn("grantham", broken[0])
            (site / "from" / "grantham").mkdir(parents=True)
            (site / "from" / "grantham" / "index.html").write_text("<p>Grantham</p>", encoding="utf-8")
            self.assertEqual(build_demo_page.crawl_internal_links(site), [])

    def test_a_release_manifest_names_the_routes_this_build_serves(self) -> None:
        # S07: the host consumes one folder, so "the whole verified output" has
        # to be a set somebody can read. The manifest is that set, and it is
        # proved against the files on disk rather than trusted.
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            (site / "from" / "grantham").mkdir(parents=True)
            (site / "from" / "grantham" / "index.html").write_text("<p>G</p>", encoding="utf-8")
            (site / "privacy").mkdir()
            (site / "privacy" / "index.html").write_text("<p>P</p>", encoding="utf-8")
            (site / "index.html").write_text("<p>C</p>", encoding="utf-8")
            path = build_demo_page.write_release_manifest(
                site,
                ["/", "/privacy/", "/from/grantham/"],
                price_source=build_demo_page.DEFAULT_PRICE_SOURCE,
                built_at="2026-09-27T00:00:00Z",
            )
            manifest = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["routes"], ["/", "/from/grantham/", "/privacy/"])
            self.assertTrue(manifest["synthetic"])
            self.assertEqual(manifest["priceSource"], build_demo_page.DEFAULT_PRICE_SOURCE)
            self.assertEqual(build_demo_page.manifest_problems(site, manifest), [])
            # A route the release claims but did not write is the failure the
            # manifest exists to catch, and a base path is stripped before the
            # lookup so a project site resolves the same way its links do.
            manifest["routes"].append("/from/nottingham/")
            self.assertEqual(
                build_demo_page.manifest_problems(site, manifest),
                ["the manifest names /from/nottingham/, which was not written"],
            )
            (site / "from" / "nottingham").mkdir()
            (site / "from" / "nottingham" / "index.html").write_text("<p>N</p>", encoding="utf-8")
            self.assertEqual(build_demo_page.manifest_problems(site, manifest), [])
            based = dict(manifest, routes=["/tb/privacy/"], basePath="/tb")
            self.assertEqual(
                build_demo_page.manifest_problems(site, based, base_path="/tb"), []
            )
            # A route that is not a route on this site is refused rather than
            # resolved against the disk.
            self.assertIn(
                "not a route on this site",
                " ".join(build_demo_page.manifest_problems(site, dict(manifest, routes=["nottingham"]))),
            )

    def test_a_build_writes_and_proves_its_own_manifest(self) -> None:
        # The manifest is written by the build, not only by the helper, and the
        # build refuses rather than reporting success if it cannot be proved.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = build_synthetic_feed(root / "fares", include_restrictions=True)
            out = root / "site" / "index.html"
            log = io.StringIO()
            with contextlib.redirect_stdout(log):
                code = build_demo_page.main(
                    ["--feed", str(feed), "--out", str(out), "--all-origins"]
                )
            self.assertEqual(code, 0)
            manifest = json.loads(
                (root / "site" / build_demo_page.RELEASE_MANIFEST_NAME).read_text(encoding="utf-8")
            )
            self.assertIn("release-manifest.json", log.getvalue())
            # Every route named is a file, and every station page the build wrote
            # is a route named: the two directions, not one.
            self.assertEqual(
                build_demo_page.manifest_problems(root / "site", manifest), []
            )
            written = sorted(
                f"/from/{child.name}/"
                for child in (root / "site" / "from").iterdir()
                if child.is_dir()
            )
            self.assertEqual(
                sorted(route for route in manifest["routes"] if route.startswith("/from/")),
                written,
            )
            self.assertIn("/", manifest["routes"])
            self.assertIn("/privacy/", manifest["routes"])
            # A single-origin build is a release of the same shape.
            solo = root / "solo"
            solo.mkdir()
            with contextlib.redirect_stdout(io.StringIO()):
                code = build_demo_page.main(
                    ["--feed", str(feed), "--out", str(solo / "index.html"), "--origin", "GRN"]
                )
            self.assertEqual(code, 0)
            one = json.loads(
                (solo / build_demo_page.RELEASE_MANIFEST_NAME).read_text(encoding="utf-8")
            )
            self.assertEqual(one["routes"], ["/", "/from/grantham/", "/privacy/"])
            self.assertEqual(build_demo_page.manifest_problems(solo, one), [])

class EncodedPayloadTest(unittest.TestCase):
    """The wire form of the payload: field names once per page, not once per row."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        fares = FaresDb().load_feed(
            build_synthetic_feed(
                Path(cls._tmp.name) / "fares",
                include_unserved_station=True,
                include_restrictions=True,
            )
        )
        timetable = TimetableDb().load_feed(build_synthetic_timetable(Path(cls._tmp.name) / "timetable"))
        cls.page = render_page(build_payload(fares, timetable, "GRN"), budget_pounds=20)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    payload = {
        "origin": {"crs": "GRN", "name": "GRANTHAM"},
        "note": "a note",
        "attribution": [{"url": "https://example.invalid", "label": "Example"}],
        "destinations": [
            {"crs": "NOT", "name": "NOTTINGHAM", "adultPence": 1200, "partyPence": 2400,
             "link": {"url": "https://example.invalid/search", "rel": "noopener"}},
            {"crs": "SLP", "name": "SLEAFORD", "adultPence": 800, "partyPence": 1600,
             "link": {"url": "https://example.invalid/search", "rel": "noopener"}},
        ],
        "singleDestinations": [{"crs": "NOT", "name": "NOTTINGHAM", "adultPence": 700}],
        "stations": [{"name": "LINCOLN", "crs": "LCN", "href": "/from/lincoln/"}],
    }

    def test_every_row_reads_back_as_it_was_written(self) -> None:
        decoded = hydrate_rows(encode_payload(self.payload))
        for key in ("destinations", "singleDestinations", "stations"):
            self.assertEqual(decoded[key], self.payload[key])

    def test_a_field_name_is_sent_once_for_the_whole_list(self) -> None:
        encoded = json.dumps(encode_payload(self.payload), separators=(",", ":"))
        self.assertEqual(encoded.count('"partyPence"'), 1)

    def test_the_lists_keep_their_own_columns(self) -> None:
        encoded = encode_payload(self.payload)
        self.assertEqual(encoded["stations"]["columns"], ["name", "crs", "href"])
        self.assertNotIn("partyPence", encoded["stations"]["columns"])

    def test_a_list_that_is_not_a_row_list_is_left_alone(self) -> None:
        encoded = encode_payload(self.payload)
        self.assertEqual(encoded["attribution"], self.payload["attribution"])

    def test_a_payload_with_no_rows_is_returned_untouched(self) -> None:
        payload = {"origin": {"crs": "GRN"}, "destinations": []}
        self.assertIs(encode_payload(payload), payload)

    def test_the_payload_it_was_given_is_not_modified(self) -> None:
        before = json.loads(json.dumps(self.payload))
        encode_payload(self.payload)
        self.assertEqual(self.payload, before)


    def test_a_value_that_repeats_is_sent_once_for_the_whole_page(self) -> None:
        encoded = encode_payload(self.payload)
        self.assertEqual(len(encoded["pool"]), 1)
        self.assertEqual(encoded["pool"][0]["url"], "https://example.invalid/search")
        link = encoded["destinations"]["columns"].index("link")
        self.assertEqual(encoded["destinations"]["rows"][0][link], -1)

    def test_a_value_used_once_is_left_where_it_is(self) -> None:
        encoded = json.dumps(encode_payload(self.payload), separators=(",", ":"))
        self.assertEqual(encoded.count("NOTTINGHAM"), 2)
        self.assertEqual(encoded.count("https://example.invalid/search"), 1)

    def test_a_payload_with_nothing_repeated_carries_no_pool(self) -> None:
        payload = {"destinations": [{"crs": "NOT", "adultPence": 1}, {"crs": "SLP", "adultPence": 2}]}
        self.assertNotIn("pool", encode_payload(payload))

    def test_a_null_cell_is_still_null(self) -> None:
        payload = {"destinations": [{"crs": "NOT", "minutes": None}, {"crs": "SLP", "minutes": None}]}
        encoded = encode_payload(payload)
        self.assertEqual(encoded["destinations"]["rows"], [["NOT", None], ["SLP", None]])

    def test_the_pool_reads_back_by_hand_as_well_as_through_the_page(self) -> None:
        encoded = encode_payload(self.payload)
        self.assertEqual(hydrate_rows(encoded)["destinations"], self.payload["destinations"])

    def test_a_rendered_page_carries_the_tables_and_the_hydrator(self) -> None:
        self.assertIn('"columns":', embedded_text(self.page))
        self.assertNotIn('"partyPence":', embedded_text(self.page))
        # The tables travel inline; the hydrator travels in the route's shared
        # script, which the page names beside the stylesheet.
        self.assertIn("hydrate", page_script(self.page))

    def test_a_rendered_page_reads_back_as_the_payload_it_was_built_from(self) -> None:
        self.assertTrue(embedded_payload(self.page)["destinations"])
