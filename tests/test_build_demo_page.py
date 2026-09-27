"""Tests for the demo page generator."""

from __future__ import annotations

import json
import os
import re
import tempfile
import unittest
import zipfile
from unittest import mock
from datetime import date
import contextlib
import io
from pathlib import Path

import build_demo_page
from build_demo_page import DEFAULT_PRICE_SOURCE, NOTICES, notices_or_attribution
import argparse
from atoc_fares import LOCATION, FLOW_F, FLOW_T, TICKET_TYPE, FaresDb
from atoc_timetable import TimetableDb
from build_demo_page import (
    build_payload,
    build_station_index,
    explain_unpriced,
    render_chooser,
    render_page,
    render_privacy,
    station_slug,
)
from make_synthetic_feed import _line, build_synthetic_feed, build_synthetic_timetable
from destination_coverage import UnsourcedReport
from parse_report import ParseReport
from retailer import DISCLOSURE


def embedded_payload(html: str) -> dict:
    match = re.search(r"const DATA = (\{.*?\});\n", html, re.DOTALL)
    if match is None:
        raise AssertionError("the page carries no embedded payload")
    return json.loads(match.group(1))


class DemoPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.fares = FaresDb().load_feed(
            build_synthetic_feed(
                Path(cls._tmp.name) / "fares",
                include_unserved_station=True,
                include_restrictions=True,
            )
        )
        cls.timetable = TimetableDb().load_feed(build_synthetic_timetable(Path(cls._tmp.name) / "timetable"))
        cls.payload = build_payload(cls.fares, cls.timetable, "GRN")
        cls.html = render_page(cls.payload, budget_pounds=20)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_payload_records_the_source_fingerprint_used_to_build_the_page(self) -> None:
        self.assertRegex(self.payload["sourceFingerprint"], r"^[0-9a-f]{16}$")
        self.assertIn("sourceFingerprint", self.html)

    def test_the_page_carries_every_priced_destination_not_just_the_cheap_ones(self) -> None:
        rows = {row["crs"]: row for row in self.payload["destinations"]}
        self.assertEqual(sorted(rows), ["KGX", "LCN", "NOT", "PBO", "SLP"])

    def test_every_destination_carries_both_prices_and_a_journey(self) -> None:
        rows = {row["crs"]: row for row in self.payload["destinations"]}
        # The page now includes the cheapest standard return found in the feed,
        # even when it is restricted. The browser budget filter does the final
        # selection; the synthetic fixture's cheaper CDR is therefore visible.
        self.assertEqual(rows["NOT"]["adultPence"], 1160)
        self.assertEqual(rows["NOT"]["railcardPence"], 770)
        self.assertEqual(rows["NOT"]["partyPence"], 2320)
        self.assertEqual(rows["NOT"]["minutes"], 45)
        self.assertEqual(rows["NOT"]["changes"], 0)

    def test_single_mode_keeps_and_labels_the_cheaper_advance_ticket(self) -> None:
        row = next(row for row in self.payload["singleDestinations"] if row["crs"] == "NOT")
        self.assertEqual(row["adultPence"], 100)
        self.assertEqual(row["ticket"], "2AS")
        self.assertTrue(row["isAdvance"])
        self.assertIn("Advance single", self.html)

    def test_a_heritage_destination_carries_its_named_unesco_property(self) -> None:
        row = next(row for row in self.payload["destinations"] if row["crs"] == "SLP")
        self.assertEqual(
            row["heritageSites"],
            [{
                "id": 488,
                "name": "Tower of London",
                "url": "https://whc.unesco.org/en/list/488/",
            }],
        )
        self.assertIn("World heritage: ", self.html)
        self.assertIn("destination.heritageSites", self.html)

    def test_expired_flows_are_absent_from_all_ticket_modes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fares = FaresDb().load_feed(
                build_synthetic_feed(Path(tmp) / "fares", include_restrictions=True)
            )
            fares._load_flows(
                _line(
                    {
                        "update_marker": "R",
                        "record_type": "F",
                        "origin_nlc": "1000",
                        "destination_nlc": "2000",
                        "route_code": "00000",
                        "flow_id": "0000001",
                        "start_date": "01012020",
                        "end_date": "31122020",
                    },
                    FLOW_F,
                )
            )
            payload = build_payload(
                fares, None, "GRN", day=date(2026, 9, 24)
            )

        for mode in ("destinations", "singleDestinations", "anytimeDestinations"):
            self.assertNotIn("NOT", {row["crs"] for row in payload[mode]})

    def test_the_page_carries_separate_ticket_modes(self) -> None:
        self.assertEqual(self.payload["destinations"][0]["destinationType"], "city")
        self.assertEqual(
            self.payload["destinations"][0]["destinationTypes"],
            ["city", "seaside", "university"],
        )
        self.assertIn('name="destinationType" value="city"', self.html)
        self.assertIn('name="destinationType" value="seaside"', self.html)
        self.assertIn('name="destinationType" value="university"', self.html)
        self.assertIn("Coastal &amp; seaside", self.html)
        self.assertIn("University towns", self.html)
        self.assertNotIn('<select id="q"', self.html)
        self.assertIn("selectedDestinationTypes", self.html)
        self.assertIn("singleDestinations", self.payload)
        self.assertTrue(self.payload["singleDestinations"])
        self.assertIn("anytimeDestinations", self.payload)
        self.assertTrue(self.payload["anytimeDestinations"])
        self.assertIn('name="ticketMode"', self.html)
        self.assertIn('value="single"', self.html)
        self.assertIn('value="anytime"', self.html)
        self.assertIn("activeDestinations", self.html)
        self.assertIn("unrestricted Anytime Day Return", self.html)
        self.assertIn("no qualifying", self.html)
        self.assertIn("PAGE_SIZE = 20", self.html)
        self.assertIn('id="pagination"', self.html)


    def test_the_cheapest_destination_is_listed_first(self) -> None:
        prices = [row["adultPence"] for row in self.payload["destinations"]]
        self.assertEqual(prices, sorted(prices))

    def test_a_fare_with_no_service_still_reaches_the_page(self) -> None:
        rows = {row["crs"]: row for row in self.payload["destinations"]}
        self.assertEqual(rows["SLP"]["adultPence"], 1200)
        self.assertIsNone(rows["SLP"]["minutes"])
        self.assertEqual(rows["SLP"]["legs"], [])

    # -- the licence wording and the measurement hook ----------------------

    def test_no_attribution_by_default_and_no_stray_placeholder(self) -> None:
        # Nothing claims a licence term that has not been read, and the slot the
        # wording goes in is present but empty rather than missing.
        self.assertIsNone(self.payload["attribution"])
        self.assertIn('<div id="attribution" hidden></div>', self.html)
        self.assertNotIn("__ANALYTICS__", self.html)

    def test_the_licence_wording_reaches_the_page_and_its_own_script(self) -> None:
        wording = "Contains data licensed from Rail Delivery Group."
        payload = build_payload(self.fares, self.timetable, "GRN", attribution=wording)
        self.assertEqual(payload["attribution"], wording)
        html = render_page(payload, budget_pounds=20)
        self.assertIn(wording, html)
        # Present in the payload is not the same as shown, so the page has to
        # unhide it too.
        self.assertIn("DATA.attribution", html)

    # -- where the numbers came from, and what they promise ------------------

    def test_the_provenance_line_sits_with_the_prices_by_default(self) -> None:
        # A synthetic build says its prices are synthetic, beside the prices,
        # not in a footer the reader has already left.
        self.assertEqual(self.payload["priceSource"], DEFAULT_PRICE_SOURCE)
        self.assertIn('id="priceSource" hidden', self.html)
        self.assertIn("DATA.priceSource", self.html)

    def test_each_destination_carries_its_fare_restriction_status(self) -> None:
        rows = {row["crs"]: row for row in self.payload["destinations"]}
        self.assertEqual(rows["NOT"]["restrictionCode"], "1A")
        self.assertIn("restriction", rows["NOT"]["restrictionDescription"].lower())
        self.assertEqual(rows["SLP"]["restrictionCode"], "")
        self.assertIn("restrictionCode", self.html)
        self.assertIn("restrictionDescription", self.html)
        self.assertIn('destination.restrictionCode + (destination.restrictionDescription', self.html)
        self.assertIn("ITX placeholder fares", self.html)

    def test_railcard_pricing_is_available_from_the_feed(self) -> None:
        # R9 is the railcard's travel condition, not a total ban, so the
        # synthetic fares that carry it remain eligible.
        self.assertTrue(self.payload["railcardInFeed"])
        self.assertTrue(self.payload["railcardAvailable"])
        self.assertEqual(self.payload["railcardEligibleCount"], 3)
        self.assertIn("Two Together is in this feed", self.payload["railcardNote"])
        self.assertIn("restriction codes are retained as travel conditions", self.payload["railcardNote"])
        self.assertIn("DATA.railcardNote", self.html)
        self.assertIn("Math.min(base, cardTotal)", self.html)

    def test_the_page_evaluates_a_railcard_for_each_selected_fare(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fares = FaresDb().load_feed(
                build_synthetic_feed(Path(tmp) / "fares", include_restrictions=True)
            )
            fares.restrictions.railcard_rows.clear()
            fares.minimum_fares.clear()
            payload = build_payload(fares, None, "GRN")
        rows = {row["crs"]: row for row in payload["destinations"]}
        self.assertEqual(rows["NOT"]["railcardPence"], 770)
        self.assertTrue(payload["railcardAvailable"])
        self.assertTrue(payload["railcardInFeed"])
        self.assertEqual(payload["railcardEligibleCount"], 4)
        self.assertIn("one-third discount", payload["railcardNote"])

    def test_each_destination_exposes_its_exact_railcard_decision(self) -> None:
        row = next(row for row in self.payload["destinations"] if row["crs"] == "NOT")
        details = row["railcard"]
        self.assertEqual(details["state"], "eligible")
        rule = self.payload["railcardRules"][details["rule"]]
        self.assertIn("any ticket", rule["text"])
        self.assertIn("RR", rule["text"])
        self.assertEqual(rule["restrictionCode"], "R9")
        self.assertFalse(rule["totalBan"])
        self.assertEqual(details["pricePence"], 770)
        self.assertEqual(
            details["minimumFarePence"],
            self.fares.minimum_fares.get(("TWO", row["ticket"])),
        )
        self.assertIn("travel condition rather than a card ban", details["reason"])
        self.assertIn('id="railcardDrawer"', self.html)
        self.assertIn("showRailcardDetails(destination)", self.html)
        self.assertIn("DATA.railcardRules[details.rule]", self.html)
        self.assertIn("Exact DTD rule", self.html)

    def test_rule_records_are_hoisted_out_of_the_rows(self) -> None:
        rows = [
            row
            for key in ("destinations", "singleDestinations", "anytimeDestinations")
            for row in self.payload[key]
        ]
        self.assertTrue(rows)
        for row in rows:
            rule = row["railcard"]["rule"]
            self.assertIsInstance(rule, str, "rows hold a key, never the record")
            self.assertIn(rule, self.payload["railcardRules"])
        rules = self.payload["railcardRules"]
        self.assertTrue(rules, "a page with rows publishes the shared records")

    def test_unavailable_railcard_hides_its_own_help(self) -> None:
        payload = dict(
            self.payload,
            railcardAvailable=False,
            railcardEligibleCount=0,
        )
        html = render_page(payload, budget_pounds=20)
        script = html.split("<script>")[1].split("</script>")[0]
        self.assertIn('help.textContent = ""', script)
        self.assertIn("help.hidden = true", script)
        self.assertIn("railcardChoice.hidden = true", script)
        self.assertNotIn("no displayed fare is currently eligible", html)

    def test_the_notice_presets_compose_into_separate_paragraphs(self) -> None:
        # Three distinct obligations, three paragraphs: one run-on would let a
        # reader miss the one that disclaims the numbers.
        args = argparse.Namespace(notices="rdg,ogl,accuracy", attribution=None)
        notices = notices_or_attribution(args)
        self.assertEqual(len(notices), 3)
        self.assertIn("Rail Delivery Group", notices[0])
        self.assertIn("Open Government Licence v3.0", notices[1])
        self.assertIn("as is", notices[2])
        self.assertIn("liability", notices[2])

    def test_an_unknown_notice_name_is_refused_not_dropped(self) -> None:
        args = argparse.Namespace(notices="rdg,madeup", attribution=None)
        with self.assertRaises(SystemExit):
            notices_or_attribution(args)

    def test_notices_win_over_attribution_and_say_so(self) -> None:
        args = argparse.Namespace(notices="rdg", attribution="custom wording")
        self.assertEqual(notices_or_attribution(args), [NOTICES["rdg"]])

    # -- the prices-only page: what a reader sees without a timetable ---------

    def test_a_prices_only_table_stands_its_empty_columns_down(self) -> None:
        # Two columns of dashes on every row is noise; when no timetable is
        # loaded the Time and Changes columns do not exist at all.
        payload = build_payload(self.fares, None, "GRN")
        html = render_page(payload, budget_pounds=20)
        script = html.split("<script>")[1].split("</script>")[0]
        self.assertIn("if (!DATA.hasJourneys)", script)
        self.assertIn("nth-child(3), thead th:nth-child(4)", script)
        # The detail rows must span whatever the table actually has.
        self.assertIn("cell.colSpan = columnCount()", script)
        # And the footer still says what the page is missing.
        self.assertIn("no timetable loaded", html)

    def test_a_page_with_times_keeps_all_six_columns(self) -> None:
        script = self.html.split("<script>")[1].split("</script>")[0]
        self.assertIn("const columnCount", script)
        self.assertIn("duration(destination.minutes)", script)

    # -- feed metadata: provenance recorded once, read by every build ---------

    def test_metadata_beside_the_feed_supplies_the_price_source(self) -> None:
        # The download records where it came from once; every build after that
        # reads it instead of the operator retyping it.
        with tempfile.TemporaryDirectory() as tmp:
            feed = build_synthetic_feed(Path(tmp) / "fares")
            (Path(feed) / "metadata.json").write_text(
                json.dumps({"source": "RSP fares feed", "downloaded": "3 October 2026"}),
                encoding="utf-8",
            )
            metadata = build_demo_page.read_feed_metadata([Path(feed)])
        self.assertEqual(
            build_demo_page.price_source_from_metadata(metadata),
            "the RSP fares feed, downloaded 3 October 2026",
        )

    def test_a_source_without_a_download_date_still_speaks(self) -> None:
        self.assertEqual(
            build_demo_page.price_source_from_metadata({"source": "RSP fares feed"}),
            "the RSP fares feed",
        )

    def test_no_metadata_keeps_the_synthetic_default(self) -> None:
        self.assertEqual(build_demo_page.price_source_from_metadata({}), None)
        self.assertEqual(
            build_demo_page.price_source_from_metadata({"downloaded": "3 October 2026"}),
            None,
        )

    def test_a_real_download_without_metadata_reads_the_downloader_manifest(self) -> None:
        # dtd_download.py writes download-manifest.json even when nobody
        # hand-writes a metadata.json. A real download must never fall back to
        # the synthetic default just because nobody typed a note.
        with tempfile.TemporaryDirectory() as tmp:
            feed = build_synthetic_feed(Path(tmp) / "fares", include_restrictions=True)
            (Path(tmp) / "download-manifest.json").write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "downloads": [
                            {
                                "name": "fares",
                                "source": "dtd",
                                "downloaded_at": "2026-09-23T14:02:11Z",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            out = Path(tmp) / "site" / "index.html"
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = build_demo_page.main(["--feed", str(feed), "--out", str(out)])
            self.assertEqual(code, 0)
            page = out.read_text(encoding="utf-8")
            self.assertIn("the National Rail Data Portal DTD fares feed", page)
            self.assertIn("downloaded 23 September 2026", page)
            self.assertNotIn("Synthetic demo data", page)
            self.assertIn("price line read from the download manifest", buffer.getvalue())

    def test_a_zip_feed_reads_the_manifest_above_its_own_folder(self) -> None:
        # The real layout: feeds/fares/dtd-fares.zip with the downloader's
        # manifest at feeds/. Looking only at the zip's folder and its parent
        # missed it, and the build fell through to "the synthetic demo feed" for
        # real DTD prices.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "feeds"
            source = build_synthetic_feed(root / "fares", include_restrictions=True)
            archive = root / "fares" / "dtd-fares.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                for item in sorted(Path(source).iterdir()):
                    zipped.write(item, arcname=item.name)
            (root / "download-manifest.json").write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "downloads": [
                            {"name": "fares", "source": "dtd", "downloaded_at": "2026-09-24T09:47:35Z"}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            out = Path(tmp) / "site" / "index.html"
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = build_demo_page.main(["--feed", str(archive), "--out", str(out)])
            self.assertEqual(code, 0)
            page = out.read_text(encoding="utf-8")
            self.assertIn("the National Rail Data Portal DTD fares feed", page)
            self.assertNotIn("the synthetic demo feed", page)

    def test_a_dtd_download_is_recognised_and_never_called_synthetic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "feeds"
            root.mkdir(parents=True)
            dtd = root / "dtd-fares.zip"
            with zipfile.ZipFile(dtd, "w") as zipped:
                zipped.writestr("RJFAF896.TTY", "not read by this test")
            self.assertTrue(build_demo_page.is_dtd_download(dtd))
            synthetic = root / "synthetic.zip"
            with zipfile.ZipFile(synthetic, "w") as zipped:
                zipped.writestr("SYNTHETIC.TTY", "invented")
            self.assertFalse(build_demo_page.is_dtd_download(synthetic))
            # A manifest above the feed is the other way a download is known.
            (root / "download-manifest.json").write_text("{}", encoding="utf-8")
            self.assertTrue(build_demo_page.is_dtd_download(synthetic))
            self.assertFalse(build_demo_page.is_dtd_download(Path(tmp) / "nowhere"))

    def test_the_manifest_prefers_fares_for_the_price_line(self) -> None:
        self.assertEqual(
            build_demo_page.price_source_from_manifest(
                {
                    "downloads": [
                        {"name": "fares", "source": "dtd", "downloaded_at": "2026-09-23T14:02:11Z"},
                        {"name": "timetable", "source": "dtd", "downloaded_at": "2026-09-24T03:00:00Z"},
                    ]
                }
            ),
            "the National Rail Data Portal DTD fares feed, downloaded 23 September 2026",
        )
        # A knowledgebase entry is reference data, not what the page is built
        # from, so it cannot supply the price line.
        self.assertIsNone(
            build_demo_page.price_source_from_manifest(
                {"downloads": [{"name": "stations", "source": "knowledgebase", "downloaded_at": "2026-09-24T03:00:00Z"}]}
            )
        )

    def test_a_manifest_alone_does_not_rescue_a_broken_metadata_note(self) -> None:
        # metadata.json present but names no 'source' -> still a refusal. The
        # manifest is a fallback for an absent note, not a way around one that
        # its operator left unfinished.
        with tempfile.TemporaryDirectory() as tmp:
            feed = build_synthetic_feed(Path(tmp) / "fares", include_restrictions=True)
            (feed / "metadata.json").write_text(
                json.dumps({"downloaded": "3 October 2026"}), encoding="utf-8"
            )
            (Path(tmp) / "download-manifest.json").write_text(
                json.dumps(
                    {"downloads": [{"name": "fares", "source": "dtd", "downloaded_at": "2026-09-23T14:02:11Z"}]}
                ),
                encoding="utf-8",
            )
            out = Path(tmp) / "site" / "index.html"
            stderr = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
                code = build_demo_page.main(["--feed", str(feed), "--out", str(out)])
            self.assertEqual(code, 2)
            self.assertFalse(out.exists())
            self.assertIn("names no 'source'", stderr.getvalue())

    def test_unreadable_metadata_is_named_not_silent(self) -> None:
        # Provenance that silently fell back to the default is provenance the
        # operator believes is real, so a broken file says so.
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "metadata.json"
            broken.write_text("{not json", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                metadata = build_demo_page.read_feed_metadata([broken.parent])
        self.assertEqual(metadata, {})
        self.assertIn("unreadable", stderr.getvalue())

    # -- base path: internal links on a host that is not the domain root ------

    def test_base_path_prefixes_every_internal_link(self) -> None:
        # GitHub Pages project sites and most shared hosting serve the site
        # below the domain root; root-absolute links 404 there.
        payload = build_payload(self.fares, self.timetable, "GRN", base_path="/tb")
        hrefs = {station["href"] for station in payload["stations"]}
        self.assertTrue(all(href.startswith("/tb/from/") for href in hrefs), hrefs)
        self.assertEqual(payload["baseHref"], "/tb/")
        html = render_page(payload, budget_pounds=20)
        self.assertIn('/tb/privacy/', html)

    def test_no_base_path_leaves_links_root_absolute(self) -> None:
        payload = build_payload(self.fares, self.timetable, "GRN")
        self.assertEqual(payload["baseHref"], "/")
        self.assertIn('href="/privacy/"', render_page(payload, budget_pounds=20))

    def test_the_analytics_snippet_is_injected_only_when_given(self) -> None:
        snippet = "<script>window.seen=1;</script>"
        self.assertNotIn("window.seen", self.html)
        html = render_page(self.payload, budget_pounds=20, analytics=snippet)
        self.assertIn(snippet, html)
        self.assertNotIn("__ANALYTICS__", html)

    def test_the_default_link_is_the_sellers_own_search_page(self) -> None:
        # ADR-0018: no seller's parameterised link is known to land on a search,
        # so the page does not walk readers into a "no journeys" page.
        urls = {row["link"]["url"] for row in self.payload["destinations"]}
        self.assertEqual(urls, {"https://www.nationalrail.co.uk/journey-planner/"})

    def test_a_fallback_page_states_what_the_reader_has_to_fill_in(self) -> None:
        # The cost of the fallback is on the page, not left for the reader to
        # discover on somebody else's site.
        self.assertIn("enter the origin", self.payload["linkNote"])
        self.assertIn("same whichever seller", self.payload["linkNote"])
        self.assertIn('<p id="linkNote" hidden></p>', self.html)
        self.assertIn("DATA.linkNote", self.html)

    # -- the copy affordance that gives a row back its memory ---------------

    def test_every_row_offers_to_copy_its_journey_details(self) -> None:
        self.assertIn('copy.textContent = "Copy"', self.html)
        self.assertIn('copy.setAttribute("aria-label", "Copy the journey details for "', self.html)
        self.assertIn("copyJourney(row, destination, copy)", self.html)

    def test_the_copied_text_names_the_things_a_seller_asks_for(self) -> None:
        for label in ('"From: "', '"To: "', '"Date: "', '"Passengers: "'):
            self.assertIn(label, self.html)

    def test_the_copied_text_names_the_railcard_only_for_the_party_price(self) -> None:
        # The card is never sent anywhere; it is named as something to tick, and
        # only when the price on screen is the one that needs it.
        self.assertIn('const together = unit() === "party";', self.html)
        self.assertIn('if (together && DATA.railcardAvailable && destination.railcardPence !== null)', self.html)
        self.assertNotIn('if (together && DATA.railcardInFeed && destination.railcardPence !== null)', self.html)
        self.assertIn('Two Together discount is not sent to the seller', self.html)

    def test_the_copied_date_is_not_parsed_through_the_date_object(self) -> None:
        # new Date("2026-10-05") is UTC midnight and prints as the 4th for a
        # reader behind UTC. A copied date off by one is worse than no date.
        self.assertIn("function humanDate(iso)", self.html)
        self.assertNotIn("new Date(", self.html)

    def test_a_failed_copy_is_never_reported_as_a_copy(self) -> None:
        # Clipboard access is refused when the file is opened from disk, so the
        # failure path has to exist and must not claim the text was copied.
        self.assertIn("if (!navigator.clipboard || !navigator.clipboard.writeText) return manual();", self.html)
        self.assertIn("Could not copy automatically", self.html)
        self.assertIn('button.textContent = "Select below"', self.html)
        self.assertEqual(self.html.count('"Copied"'), 1)

    def test_the_copy_confirmation_is_announced_and_not_only_shown(self) -> None:
        self.assertIn('id="copyStatus" role="status"', self.html)
        self.assertIn("class=\"sr-only\"", self.html)

    def test_the_newlines_in_the_copy_are_escaped_for_the_browser(self) -> None:
        # A real newline inside a JavaScript string literal is a SyntaxError that
        # takes the whole page down, and a Python template will happily produce
        # one from "\n". These assert the backslash-n the browser must receive.
        # This bug shipped past every test in this file and was caught by
        # browser_test.cjs, which is the reason that file exists.
        self.assertIn('lines.join("\\n")', self.html)
        self.assertIn('text.split("\\n").join(". ")', self.html)
        self.assertNotIn('join("\n', self.html)

    def test_the_page_can_be_read_back_as_data(self) -> None:
        self.assertEqual(embedded_payload(self.html), self.payload)

    def test_the_page_names_the_origin_and_offers_a_slider_and_a_filter(self) -> None:
        self.assertIn("GRANTHAM", self.html)
        self.assertIn('id="budget"', self.html)
        self.assertIn('name="destinationType"', self.html)
        self.assertIn('id="destinationTypes"', self.html)
        self.assertIn('value="party"', self.html)
        self.assertIn("Where can we go for under", self.html)

    def test_every_price_renders_with_two_decimal_places(self) -> None:
        # £9 next to £8.70 is harder to scan down a column than £9.00 is.
        self.assertIn("(pence / 100).toFixed(2)", self.html)
        self.assertNotIn("replace(/\\.00$/", self.html)

    # -- the origin picker (ADR-0019) -------------------------------------

    def test_the_payload_carries_a_station_list_for_the_picker(self) -> None:
        codes = [s["crs"] for s in self.payload["stations"]]
        self.assertNotIn("GRN", codes)  # the page's own origin is not offered
        self.assertIn("KGX", codes)
        for station in self.payload["stations"]:
            self.assertEqual(sorted(station), ["crs", "href", "name"])
            self.assertTrue(station["href"].startswith("/from/"))

    # -- the layout: budget leads, the rest refines ------------------------

    def test_the_filter_bar_uses_horizontal_space_without_a_duplicate_budget_field(self) -> None:
        self.assertIn("grid-template-columns: minmax(16rem, 1.1fr) minmax(18rem, 1.3fr) minmax(17rem, 1fr)", self.html)
        self.assertIn('<section class="filter-bar"', self.html)
        self.assertIn('id="budget" type="range"', self.html)
        self.assertIn('id="budgetNumber" type="number"', self.html.split("<h1", 1)[1].split("</h1>", 1)[0])
        self.assertNotIn('id="budgetNumber" type="number"', self.html.split('<section class="filter-bar"', 1)[1])

    def test_the_budget_is_inline_in_the_large_heading(self) -> None:
        heading = self.html.split("<h1", 1)[1].split("</h1>", 1)[0]
        self.assertIn("Where can we go for under", heading)
        self.assertIn('id="budgetNumber"', heading)
        self.assertIn('id="changeOrigin"', heading)
        self.assertIn("font-size: clamp(2rem, 5vw, 5rem)", self.html)
        self.assertIn(".sub { color: var(--muted); max-width: 75ch; }", self.html)
        self.assertNotIn("max-width: 32ch", self.html)
        self.assertNotIn("margin: -1rem 0 1.5rem", self.html)

    def test_result_changes_and_mobile_cells_are_accessible(self) -> None:
        self.assertIn('id="summary" role="status" aria-live="polite"', self.html)
        self.assertIn('cell.dataset.label = label', self.html)
        self.assertIn('restriction.dataset.label = "Restriction"', self.html)
        self.assertIn("Restricted fare — check seller conditions", self.html)

    def test_row_actions_carry_a_44px_touch_target(self) -> None:
        # The visible mark stays small; the hit area reaches 44px via ::after.
        self.assertIn('.toggle::after { content: ""; position: absolute; inset: -6px; }', self.html)
        self.assertIn('.buy::after { content: ""; position: absolute; inset: -11px -4px; }', self.html)

    # -- the unpriced-origin page ------------------------------------------

    def test_the_hidden_attribute_beats_every_display_rule(self) -> None:
        # The controls grid, the picker, and the footer slots all set display;
        # without this rule, hiding them does nothing and an unpriced page
        # shows a slider that cannot help. Regression: the Sleepy page shipped
        # with the controls still on screen under the unpriced message.
        self.assertIn("[hidden] { display: none !important; }", self.html)

    def test_an_unpriced_origin_gets_its_own_first_sentence(self) -> None:
        # All three modes, not just the two the test used to empty: an unpriced
        # page is one that priced nothing in any ticket mode, and leaving the
        # Anytime list populated described a page this is not.
        payload = dict(
            self.payload, destinations=[], singleDestinations=[], anytimeDestinations=[]
        )
        html = render_page(payload, budget_pounds=20)
        self.assertIn('id="unpriced"', html)
        script = html.split("<script>")[1].split("</script>")[0]
        self.assertIn("We couldn't price any journeys from", script)
        # The way forward is the chooser, as a real link, and it honours the
        # site's base path like every other internal link.
        self.assertIn("link.href = DATA.baseHref", script)
        self.assertIn("Start from a station we do price", script)
        # The controls cannot help an origin with no prices, so they stand down.
        self.assertIn("if (controls) controls.hidden = true", script)
        # Nor can the table or the budget's empty message: nothing was priced,
        # so "raise the budget" would be advice about a question nobody asked.
        self.assertIn('for (const id of ["empty", "more"])', script)
        self.assertIn('if (table) table.hidden = true;', script)
        self.assertIn('if (summary) summary.hidden = true;', script)
        # render() runs after provenance() and would un-hide the budget's empty
        # message; on an unpriced page it must not write anything at all. The
        # test is for a mode with nothing in it, not a page with nothing in it.
        render = script.split("function render(")[1].split("\nfunction ")[0]
        self.assertIn(
            "if (!DATA.destinations.length && !DATA.singleDestinations.length "
            "&& !DATA.anytimeDestinations.length) return;",
            render,
        )

    def test_an_unpriced_origin_with_no_stations_at_all_says_that(self) -> None:
        payload = dict(
            self.payload,
            destinations=[],
            singleDestinations=[],
            anytimeDestinations=[],
            stations=[],
        )
        html = render_page(payload, budget_pounds=20)
        script = html.split("<script>")[1].split("</script>")[0]
        self.assertIn("Nothing was priced from any station", script)
        # No chooser exists, so no way-forward link is offered either.
        self.assertIn('if (DATA.stations && DATA.stations.length)', script)

    def test_the_empty_state_carries_the_payloads_note_after_the_intro(self) -> None:
        payload = dict(
            self.payload,
            destinations=[],
            singleDestinations=[],
            anytimeDestinations=[],
            unpricedNote="The feed reaches 2 destinations, cheapest fare an ITX placeholder.",
        )
        html = render_page(payload, budget_pounds=20)
        script = html.split("<script>")[1].split("</script>")[0]
        self.assertIn('unpriced.append(intro + why + " ", link, ".");', script)
        self.assertIn('unpriced.textContent = intro + why + " Nothing was priced', script)
        self.assertEqual(embedded_payload(html)["unpricedNote"], payload["unpricedNote"])

    def test_slugs_are_readable_and_collision_free(self) -> None:
        taken: set[str] = set()
        first = station_slug("NOTTINGHAM", "NOT", taken)
        self.assertEqual(first, "nottingham")
        # A second station with the same name is disambiguated with its code.
        second = station_slug("NOTTINGHAM", "NMP", taken)
        self.assertEqual(second, "nottingham-nmp")
        self.assertNotEqual(first, second)

    def test_a_slug_never_collides_even_with_the_same_name_and_code(self) -> None:
        taken: set[str] = set()
        a = station_slug("X", "AAA", taken)
        b = station_slug("X", "AAA", taken)
        self.assertNotEqual(a, b)

    def test_the_page_offers_to_change_origin_and_navigates_by_link(self) -> None:
        self.assertIn('id="changeOrigin"', self.html)
        self.assertIn('id="originPicks"', self.html)
        # The options are real anchors, not a custom listbox.
        self.assertIn('link.href = station.href', self.html)
        self.assertIn('id="destinationTypes"', self.html.split("<script")[0])
        self.assertIn('name="destinationType" value="city"', self.html.split("<script")[0])
        self.assertIn('name="destinationType" value="seaside"', self.html.split("<script")[0])

    def test_a_destination_type_with_no_matches_gets_no_chip(self) -> None:
        # A chip that can only ever return nothing reads as a broken control,
        # so the page offers only the types its destinations actually carry.
        payload = dict(self.payload)
        payload["destinations"] = [
            dict(row, destinationTypes=["city"], destinationType="city")
            for row in self.payload["destinations"]
        ]
        for mode in ("singleDestinations", "anytimeDestinations"):
            payload[mode] = [
                dict(row, destinationTypes=["city"], destinationType="city")
                for row in self.payload.get(mode, [])
            ]
        html = render_page(payload, budget_pounds=50)
        head = html.split("<script")[0]
        self.assertIn('name="destinationType" value="city"', head)
        self.assertNotIn('name="destinationType" value="seaside"', head)
        self.assertNotIn('name="destinationType" value="university"', head)
        self.assertNotIn('name="destinationType" value="island"', head)

    def test_a_destination_type_with_no_matches_gets_no_chip(self) -> None:
        # A chip that can only ever return nothing reads as a broken control,
        # so the page offers only the types its destinations actually carry.
        payload = dict(self.payload)
        payload["destinations"] = [
            dict(row, destinationTypes=["city"], destinationType="city")
            for row in self.payload["destinations"]
        ]
        for mode in ("singleDestinations", "anytimeDestinations"):
            payload[mode] = [
                dict(row, destinationTypes=["city"], destinationType="city")
                for row in self.payload.get(mode, [])
            ]
        html = render_page(payload, budget_pounds=50)
        head = html.split("<script>")[0]
        self.assertIn('name="destinationType" value="city"', head)
        self.assertNotIn('name="destinationType" value="seaside"', head)
        self.assertNotIn('name="destinationType" value="university"', head)
        self.assertNotIn('name="destinationType" value="island"', head)

    def test_a_type_only_the_singles_carry_still_reaches_the_page(self) -> None:
        # The build narrows chips by the union of the three modes, because it
        # does not know which mode a reader will pick. The page then narrows
        # them again per mode at render time, so a type only the singles carry
        # is still in the HTML and simply hidden on the returns list. If the
        # build decided this, switching to Singles would show a chip that
        # filters nothing.
        payload = dict(self.payload)
        payload["destinations"] = [
            dict(row, destinationTypes=["city"], destinationType="city")
            for row in self.payload["destinations"]
        ]
        payload["anytimeDestinations"] = [
            dict(row, destinationTypes=["city"], destinationType="city")
            for row in self.payload["anytimeDestinations"]
        ]
        payload["singleDestinations"] = [
            dict(row, destinationTypes=["city", "heritage"], destinationType="city")
            for row in self.payload["singleDestinations"]
        ]
        head = render_page(payload, budget_pounds=50).split("<script>")[0]
        self.assertIn('name="destinationType" value="heritage"', head)

    def test_the_chips_are_narrowed_for_the_mode_on_screen(self) -> None:
        # The narrowing reads the active list rather than all three, and runs
        # before the filter is asked what is checked: a chip the list cannot
        # support must not be part of what matchesType is matching.
        script = self.html.split("<script>")[1].split("</script>")[0]
        self.assertIn("function syncDestinationTypeChips()", script)
        sync = script.split("function syncDestinationTypeChips()")[1].split("\n}")[0]
        self.assertIn("activeDestinations()", sync)
        for other_mode in ("DATA.destinations", "singleDestinations", "anytimeDestinations"):
            self.assertNotIn(other_mode, sync)
        # A chip that goes away cannot stay ticked, or the filter would match a
        # type the reader can no longer see selected.
        self.assertIn("chip.hidden = !present", sync)
        self.assertIn("input.checked = false", sync)
        self.assertIn("all.checked = true", sync)
        render = script.split("function render(")[1].split("\nfunction ")[0]
        self.assertLess(
            render.index("syncDestinationTypeChips()"),
            render.index("selectedDestinationTypes()"),
        )

    def test_a_mode_with_no_fares_says_so_instead_of_going_blank(self) -> None:
        # An Anytime Day Return is sold on a handful of interurban routes, so
        # most real origins have none of them: Kings Cross prices 171 returns
        # and no Anytime fares at all. The page used to return from render()
        # before it wrote anything, so a reader who switched to that mode kept
        # the previous mode's rows under a set of destination chips that had
        # all just been hidden -- a filter that looks broken rather than a
        # mode that is empty. The mode now clears the table, says what
        # happened, and says where the fares this origin does have are.
        script = self.html.split("<script>")[1].split("</script>")[0]
        render = script.split("function render(")[1].split("\nfunction ")[0]
        self.assertNotIn("if (!available.length) return;", render)
        branch = render.split("if (!available.length) {")[1].split("\n  }")[0]
        self.assertIn("rows.replaceChildren()", branch)
        self.assertIn("empty.hidden = false", branch)
        self.assertIn("empty.textContent = emptyModeMessage()", branch)
        self.assertIn("pagination.hidden = true", branch)
        # The budget is clamped after the branch, not before it: an empty list
        # has no prices to bound, and its £1 ceiling would otherwise reset the
        # reader's budget for every mode they switched back to.
        self.assertLess(
            render.index("if (!available.length) {"), render.index("setBudget(ceiling)")
        )
        # Silence is now reserved for the one case that already has a message:
        # a page that priced nothing at all, which provenance() explains.
        self.assertIn(
            "if (!DATA.destinations.length && !DATA.singleDestinations.length", render
        )
        # The wording names the mode by the label the reader can see, so it
        # cannot drift from the control, and counts the payload's own lists.
        message = script.split("function emptyModeMessage()")[1].split("\nfunction ")[0]
        self.assertIn("modeLabels()", message)
        self.assertIn("modeCount(", message)
        self.assertIn('"No " + labels[mode] + " fares were found from "', message)
        self.assertIn("MODE_WHY", message)
        # The Anytime mode says why that mode is usually the empty one, since
        # "none in this download" on its own reads like a broken build.
        self.assertIn("An Anytime Day Return is valid on any train", script)
        # One place names which list each mode shows, so a count quoted in a
        # message cannot come from a different list than the table is built
        # from.
        self.assertIn("const MODE_LISTS = {", script)

    def test_the_picker_closes_on_escape_and_returns_focus(self) -> None:
        self.assertIn('event.key === "Escape"', self.html)
        self.assertIn("changeOrigin.focus()", self.html)

    def test_table_headers_name_their_columns_and_scope(self) -> None:
        # "Ticket" and "Tickets" as adjacent headers read as one column twice;
        # the first holds the fare code, so it says so.
        self.assertIn('<th scope="col">Fare code</th>', self.html)
        self.assertNotIn("<th>Ticket</th><th>Tickets</th>", self.html)
        self.assertEqual(self.html.count('<th scope="col"'), 7)

    def test_keyboard_focus_is_visible_everywhere(self) -> None:
        self.assertIn(":focus-visible { outline: 2px solid var(--accent); outline-offset: 2px;", self.html)

    def test_the_picker_hides_itself_when_there_is_nowhere_else_to_go(self) -> None:
        payload = dict(self.payload, stations=[])
        html = render_page(payload, budget_pounds=20)
        self.assertIn('DATA.stations && DATA.stations.length', html)

    def test_the_no_match_wording_names_what_was_tried(self) -> None:
        self.assertIn("We don't have prices from", self.html)
        self.assertIn("three-letter code", self.html)

    def test_the_embedded_script_parses_when_the_template_speaks_in_quotes(self) -> None:
        # The Python template is one big string, so a quote meant for the page
        # can terminate a JavaScript literal and take the whole page down. The
        # no-match wording quotes the reader's own input, so it is written with
        # single quotes inside double-quoted literals and must arrive intact.
        script = self.html.split("<script>")[1].split("</script>")[0]
        self.assertIn("We don't have prices from '", script)
        self.assertNotIn('from \\"', script)

    def test_privacy_requires_a_contact_and_uses_the_deployment_route(self) -> None:
        with self.assertRaises(ValueError):
            render_privacy("note")
        html = render_privacy("note", contact="privacy@example.test")
        self.assertIn("privacy@example.test", html)
        self.assertNotIn("goes here before the site is published", html)

    def test_the_chooser_budget_is_carried_into_station_links(self) -> None:
        chooser = render_chooser(
            [{"crs": "NOT", "name": "NOTTINGHAM", "slug": "nottingham", "destinations": 1}],
            budget_pounds=20,
        )
        self.assertIn('id="chooserBudget"', chooser)
        self.assertIn('url.searchParams.set("budget"', chooser)
        self.assertIn('min-height: 44px', chooser)
        self.assertIn("Rail Budget", chooser)

    def test_the_chooser_explains_a_truncated_match_list(self) -> None:
        chooser = render_chooser([], budget_pounds=20)
        self.assertIn("Showing \" + CHOOSER_LIMIT + \" of \" + wanted.length", chooser)
        self.assertIn("Refine the search to see the rest", chooser)

    def test_the_chooser_counts_destinations_in_the_singular_when_there_is_one(self) -> None:
        # The chooser is read as a fact about the feed, and "1 destinations" is
        # the kind of slip that costs the page its credibility. The count is
        # rendered in the browser, so this asserts the emitted script.
        chooser = render_chooser(
            [{"crs": "NOT", "name": "NOTTINGHAM", "slug": "nottingham", "destinations": 1}],
            budget_pounds=20,
        )
        self.assertIn('? " destination" : " destinations"', chooser)

    def test_an_unpriced_station_is_absent_from_the_index(self) -> None:
        # ADR-0019 decision 3: the picker must never offer a station that priced
        # nothing, because the reader is then sent to a page that cannot answer
        # them. Measured on the synthetic feed, five of seven stations price
        # nothing from themselves.
        locations = self.fares.locations_by_crs
        index = build_station_index(
            {"GRN": 5, "NOT": 1, "KGX": 0, "LCN": 0, "SLP": 0, "PBO": 0, "XFD": 0}, locations
        )
        self.assertEqual([entry["crs"] for entry in index], ["GRN", "NOT"])
        self.assertTrue(all(entry["destinations"] > 0 for entry in index))

    def test_the_chooser_is_the_index_and_carries_no_fares(self) -> None:
        index = [
            {"crs": "KGX", "name": "LONDON KINGS X", "slug": "london-kings-x", "destinations": 6},
            {"crs": "NOT", "name": "NOTTINGHAM", "slug": "nottingham", "destinations": 5},
        ]
        html = render_chooser(index, budget_pounds=20)
        self.assertIn("Pick the station you are starting from", html)
        self.assertNotIn("const DATA", html)  # no fares payload on the chooser
        self.assertIn("/from/nottingham/", html)
        self.assertIn('"destinations":6', html.replace(" ", ""))
        # The ranked count is the cold start, derived from the feed.
        self.assertLess(html.index("/from/london-kings-x/"), html.index("/from/nottingham/"))

    def test_the_chooser_carries_the_note_it_is_given(self) -> None:
        # A real-feed chooser must not sit above station pages claiming
        # synthetic data, so the note is a parameter rather than a constant.
        html = render_chooser(
            [{"crs": "NOT", "name": "NOTTINGHAM", "slug": "nottingham", "destinations": 5}],
            budget_pounds=20,
            note="the RSP fares feed, downloaded 3 October 2026",
        )
        self.assertIn("the RSP fares feed, downloaded 3 October 2026", html)
        self.assertNotIn("Synthetic demo data", html)
        self.assertIn("Synthetic demo data", render_chooser([], budget_pounds=20))

    def test_a_zero_station_chooser_stands_the_search_down_and_says_so(self) -> None:
        html = render_chooser([], budget_pounds=20)
        script = html.split("<script>")[1].split("</script>")[0]
        self.assertIn("if (!STATIONS.length) {", script)
        self.assertIn("Nothing is priced from any station in this build", script)
        # The no-match wording quotes typed input; it must never address an
        # empty field the reader has not touched.
        self.assertIn("} else if (needle) {", script)

    def test_the_mobile_reflow_keeps_the_markup_a_real_table(self) -> None:
        # The reflow is display-only CSS in a max-width media query. The markup
        # must stay a real table for desktop and assistive technology, and the
        # stylesheet must wrap cells rather than fix their width, so no cell can
        # sit outside the viewport however long a station name is.
        self.assertIn("@media (max-width: 44rem)", self.html)
        # From the first max-width block to the end of the stylesheet: the
        # footer nav has its own small block, and the table's rules must be
        # found wherever they sit.
        reflow = self.html[self.html.index("@media (max-width: 44rem)"):].split("</style>")[0]
        self.assertIn("flex-wrap", reflow)
        self.assertNotIn("display: none", reflow.split("thead")[0])
        self.assertIn("thead { position:absolute; width:1px; height:1px;", reflow)
        self.assertIn("td[data-label]::before { content: attr(data-label)", reflow)
        table_markup = self.html.split("<table>")[1].split("</table>")[0]
        self.assertNotIn("<div", table_markup)

    def test_the_slider_ceiling_covers_the_dearest_destination(self) -> None:
        ceiling = int(re.search(r'id="budget"[^>]*max="(\d+)"', self.html).group(1))
        dearest = max(row["adultPence"] for row in self.payload["destinations"])
        self.assertGreaterEqual(ceiling * 100, dearest)

    def test_a_script_tag_in_the_data_cannot_close_the_script_early(self) -> None:
        payload = dict(self.payload, note="a note with </script> in it")
        html = render_page(payload, budget_pounds=20)
        payload_region = html.split("const DATA = ")[1].split(";\nconst rows")[0]
        self.assertNotIn("</script>", payload_region)
        self.assertEqual(embedded_payload(html)["note"], "a note with </script> in it")

    # -- ticket links and the expander ------------------------------------

    def test_every_destination_carries_an_untracked_ticket_link(self) -> None:
        for row in self.payload["destinations"]:
            self.assertTrue(row["link"]["url"].startswith("https://www.nationalrail.co.uk/"))
            self.assertEqual(row["link"]["rel"], "noopener")
        self.assertFalse(self.payload["tracked"])
        self.assertIsNone(self.payload["disclosure"])

    def test_the_deep_link_points_at_the_destination_it_sits_beside(self) -> None:
        # Opt-in, because it depends on a URL that somebody has opened: ADR-0018.
        payload = build_payload(self.fares, self.timetable, "GRN", mode="deep")
        rows = {row["crs"]: row for row in payload["destinations"]}
        self.assertIn("origin=GRN", rows["NOT"]["link"]["url"])
        self.assertIn("destination=NOT", rows["NOT"]["link"]["url"])
        self.assertIsNone(payload["linkNote"])

    def test_a_tracked_page_discloses_itself(self) -> None:
        payload = build_payload(
            self.fares,
            self.timetable,
            "GRN",
            network="partnerize",
            advertiser_id="123456",
        )
        self.assertTrue(payload["tracked"])
        self.assertEqual(payload["disclosure"], DISCLOSURE)
        self.assertIn("nofollow", payload["destinations"][0]["link"]["rel"])
        self.assertIn(DISCLOSURE, render_page(payload, budget_pounds=20))
        self.assertTrue(
            all(x["link"]["rel"] == "noopener" for x in self.payload["destinations"]),
            "an untracked page must not claim otherwise",
        )

    def test_the_page_carries_the_journeys_behind_a_toggle_link(self) -> None:
        rows = {row["crs"]: row for row in self.payload["destinations"]}
        self.assertEqual(
            [option["depart"] for option in rows["NOT"]["departures"]],
            sorted(option["depart"] for option in rows["NOT"]["departures"]),
        )
        self.assertTrue(rows["NOT"]["departures"])
        self.assertEqual(rows["SLP"]["departures"], [])
        self.assertIn("toggleDetail", self.html)
        self.assertIn('link.className = "buy"', self.html)
        self.assertIn('link.textContent = "Tickets"', self.html)
        self.assertIn('link.target = "_blank"', self.html)

    def test_the_page_says_how_many_journeys_it_is_hiding(self) -> None:
        self.assertIn("destination.departures.length + \" times\"", self.html)

    def test_the_departure_list_is_capped_and_configurable(self) -> None:
        payload = build_payload(self.fares, self.timetable, "GRN", departure_limit=2)
        rows = {row["crs"]: row for row in payload["destinations"]}
        self.assertEqual(len(rows["NOT"]["departures"]), 2)

    def test_a_page_without_a_date_warns_that_a_changed_train_appears_twice(self) -> None:
        self.assertIn("has changed appears twice", self.payload["dateNote"])

    def test_a_page_with_a_date_does_not_need_that_warning(self) -> None:
        payload = build_payload(self.fares, self.timetable, "GRN", day=date(2026, 10, 5))
        self.assertIsNone(payload["dateNote"])
        self.assertEqual(payload["serviceDate"], "2026-10-05")
        rows = {row["crs"]: row for row in payload["destinations"]}
        self.assertEqual(len(rows["NOT"]["departures"]), 3)

    def test_the_page_titles_itself_with_the_budget(self) -> None:
        self.assertIn("&pound;20", self.html)

    def test_without_a_timetable_the_page_says_so(self) -> None:
        payload = build_payload(self.fares, None, "GRN")
        self.assertFalse(payload["hasJourneys"])
        self.assertTrue(all(row["minutes"] is None for row in payload["destinations"]))
        self.assertIn("no timetable loaded", render_page(payload, budget_pounds=20))


class ExplainUnpricedTest(unittest.TestCase):
    """The empty state's own sentence, in each shape it can take."""

    def test_a_placeholder_only_origin_names_the_count_and_the_codes(self) -> None:
        self.assertEqual(
            explain_unpriced(3, 3, ["EIF", "EIS"], {}),
            "The feed reaches 3 standard-return destinations, and the cheapest fare "
            "to every one of them is an ITX placeholder (EIF, EIS), which this page "
            "does not publish.",
        )

    def test_a_single_destination_is_written_in_the_singular(self) -> None:
        note = explain_unpriced(1, 1, ["EIS"], {})
        self.assertIn("reaches 1 standard-return destination, and its cheapest fare", note)

    def test_a_partly_withheld_origin_is_not_told_every_destination_is(self) -> None:
        # The placeholder sentence claims *every* destination is withheld, so
        # it is only said when every excluded row is. An origin priced half
        # into ITX and half into a zone boundary has one of each, and the
        # honest answer is the reason list rather than a false "all of them".
        note = explain_unpriced(
            2,
            1,
            ["EIS"],
            {"destination_is_a_fare_construction_point": 1},
        )
        self.assertIn(
            "none prices a publishable fare: 1 flows priced only to zone boundaries",
            note,
        )
        self.assertNotIn("ITX placeholder", note)

    def test_an_origin_priced_only_into_a_zone_says_that(self) -> None:
        note = explain_unpriced(
            1, 0, [], {"destination_is_a_fare_construction_point": 1}
        )
        self.assertIn("flows priced only to zone boundaries or coach stops", note)
        self.assertNotIn("ITX", note)

    def test_rejections_are_named_largest_first_and_capped(self) -> None:
        tally = {
            # Held-cheaper fares are normal traffic, never a reason a
            # destination is missing, so the 99 must not surface.
            "cheaper_index_already_held": 99,
            "ticket_is_not_a_standard_return": 9,
            "flow_expired": 5,
            "flow_with_no_fare": 2,
        }
        self.assertEqual(
            explain_unpriced(0, 0, [], tally),
            "The feed holds flows from this origin, but none prices a publishable fare: "
            "9 fares that are not standard returns; 5 flows past their last valid day; "
            "2 flows carrying no fare.",
        )

    def test_an_origin_the_feed_never_reaches_says_so(self) -> None:
        self.assertEqual(
            explain_unpriced(0, 0, [], {}), "The feed holds no fare from this origin at all."
        )


class UnpricedOriginNoteTest(unittest.TestCase):
    """The note the payload actually carries, built from a real query."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        feed = build_synthetic_feed(Path(cls._tmp.name) / "fares", include_restrictions=True)
        # PBO has no outbound flow in the base fixture. One flow priced only
        # with the ITX placeholder family gives it King's Cross's shape: the
        # feed reaches a destination and its cheapest fare is withheld.
        # KGX gets a CDR-only flow: displayable on the page's default mode,
        # invisible to the reviewed-anytime selector.
        with (feed / "rjfaf.ffl").open("a", encoding="utf-8") as handle:
            handle.write(
                _line(
                    {
                        "update_marker": "A",
                        "record_type": "F",
                        "origin_nlc": "4000",
                        "destination_nlc": "1000",
                        "route_code": "00000",
                        "flow_id": "0000008",
                    },
                    FLOW_F,
                )
                + "\n"
                + _line(
                    {
                        "update_marker": "A",
                        "record_type": "T",
                        "flow_id": "0000008",
                        "ticket_code": "EIS",
                        "fare_pence": "5",
                        "restriction_code": "GA",
                    },
                    FLOW_T,
                )
                + "\n"
                + _line(
                    {
                        "update_marker": "A",
                        "record_type": "F",
                        "origin_nlc": "5000",
                        "destination_nlc": "1000",
                        "route_code": "00000",
                        "flow_id": "0000009",
                    },
                    FLOW_F,
                )
                + "\n"
                + _line(
                    {
                        "update_marker": "A",
                        "record_type": "T",
                        "flow_id": "0000009",
                        "ticket_code": "CDR",
                        "fare_pence": "1160",
                        "restriction_code": "1A",
                    },
                    FLOW_T,
                )
                + "\n"
            )
        with (feed / "rjfaf.tty").open("a", encoding="utf-8") as handle:
            handle.write(
                _line(
                    {
                        "update_marker": "A",
                        "record_type": "T",
                        "ticket_code": "EIS",
                        "description": "ADVANCE ITX R",
                        "tkt_class": "2",
                        "tkt_type": "R",
                        "restricted_by_train": "0",
                    },
                    TICKET_TYPE,
                )
                + "\n"
            )
        cls.fares = FaresDb().load_feed(feed)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_an_origin_with_no_flows_says_the_feed_holds_nothing(self) -> None:
        payload = build_payload(self.fares, None, "LCN")
        self.assertEqual(payload["rawFareDestinationCount"], 0)
        self.assertEqual(payload["unpricedNote"], "The feed holds no fare from this origin at all.")

    def test_an_origin_priced_only_by_a_non_reviewed_fare_still_counts(self) -> None:
        # CDR is a restricted off-peak return: the page's default mode shows
        # it, the reviewed-anytime selector cannot see it. Audit A1 is this
        # shape on the real feed -- King's Cross's 171 returns kept it out of
        # the chooser while its page answered just fine.
        self.assertEqual(
            build_demo_page._priced_destinations(self.fares, None, "KGX"),
            1,
        )
        self.assertEqual(
            self.fares.publishable_destinations_within(
                "KGX", build_demo_page.EVERYTHING_PENCE, adults=1
            ),
            [],
        )
        # And an ITX-only origin still counts as unpriceable: its page is the
        # empty state, which decision 3 keeps out of the index.
        self.assertEqual(
            build_demo_page._priced_destinations(self.fares, None, "PBO"), 0
        )

    def test_a_placeholder_only_origin_counts_destinations_and_names_the_codes(self) -> None:
        payload = build_payload(self.fares, None, "PBO")
        self.assertEqual(payload["destinations"], [])
        self.assertEqual(payload["singleDestinations"], [])
        self.assertEqual(payload["anytimeDestinations"], [])
        self.assertEqual(payload["rawFareDestinationCount"], 1)
        self.assertEqual(payload["excludedItxCodes"], ["EIS"])
        self.assertEqual(
            payload["unpricedNote"],
            "The feed reaches 1 standard-return destination, and its cheapest fare "
            "is an ITX placeholder (EIS), which this page does not publish.",
        )


class AllOriginsCliTest(unittest.TestCase):
    """The whole `--all-origins` run, because the output folder is the product.

    Every assertion here is something a reader or the operator can see: which
    pages exist, what the chooser lists, what the build says about a folder that
    still holds an earlier build, and how to open the result. The order of the
    writes matters, so this exercises the command rather than its pieces.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.feed = build_synthetic_feed(
            root / "fares", include_unserved_station=True, include_restrictions=True
        )
        self.timetable = build_synthetic_timetable(root / "timetable")
        self.out = root / "site" / "index.html"

    def build(self) -> str:
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
        return buffer.getvalue()

    def test_only_priceable_stations_get_a_page(self) -> None:
        self.build()
        written = sorted(child.name for child in (self.out.parent / "from").iterdir())
        self.assertEqual(written, ["grantham", "nottingham"])

    def test_the_chooser_offers_every_page_and_no_others(self) -> None:
        self.build()
        chooser = (self.out.parent / "index.html").read_text(encoding="utf-8")
        pages = [child.name for child in (self.out.parent / "from").iterdir()]
        for slug in pages:
            self.assertIn(f"/from/{slug}/", chooser)
        self.assertNotIn("0 destination", chooser)

    def test_an_earlier_build_in_the_folder_is_named_not_deleted(self) -> None:
        (self.out.parent / "from" / "sleepy").mkdir(parents=True)
        stale_file = self.out.parent / "from" / "sleepy" / "index.html"
        stale_file.write_text("from an earlier build", encoding="utf-8")
        said = self.build()
        self.assertIn("earlier build", said)
        self.assertIn("sleepy", said)
        self.assertTrue(stale_file.exists(), "the build must not delete a page it did not write")

    def test_a_fresh_folder_gets_no_stale_note(self) -> None:
        self.assertNotIn("earlier build", self.build())

    def test_fast_all_origins_reports_progress_and_resumes_completed_pages(self) -> None:
        first = io.StringIO()
        with contextlib.redirect_stdout(first):
            code = build_demo_page.main([
                "--feed", str(self.feed), "--fast-all-origins",
                "--out", str(self.out),
            ])
        self.assertEqual(code, 0)
        self.assertIn("Finding priceable origins", first.getvalue())
        self.assertIn("progress is saved after every page", first.getvalue())
        self.assertTrue((self.out.parent / ".trainbudget-build.json").is_file())

        second = io.StringIO()
        with contextlib.redirect_stdout(second):
            code = build_demo_page.main([
                "--feed", str(self.feed), "--fast-all-origins",
                "--out", str(self.out),
            ])
        self.assertEqual(code, 0)
        self.assertIn("Building 0 station page(s)", second.getvalue())
        self.assertIn("station pages complete: 2/2", second.getvalue())

    def test_an_overrun_origin_trips_the_wire_and_writes_nothing(self) -> None:
        # ADR-0024's tripwire (audit B1): a superquadratic search must be
        # visible on the FIRST origin, not after hours of a doomed full build.
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = build_demo_page.main(
                [
                    "--feed", str(self.feed),
                    "--timetable", str(self.timetable),
                    "--all-origins", "--out", str(self.out),
                    "--max-origin-seconds", "0.000001",
                ]
            )
        self.assertEqual(code, 3)
        self.assertIn("tripwire", stderr.getvalue())
        self.assertFalse(self.out.parent.joinpath("from").exists(), "a stopped build must not leave half a site")

    def test_the_worker_path_and_the_inprocess_path_build_the_same_pages(self) -> None:
        # Audit A2: the two modes went through different job shapes once; the
        # proof they agree is a byte-diff of the pages each mode writes.
        self.build()
        single = (self.out.parent / "from" / "grantham" / "index.html").read_text(encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            code = build_demo_page.main(
                [
                    "--feed", str(self.feed),
                    "--timetable", str(self.timetable),
                    "--all-origins", "--out", str(self.out),
                    "--workers", "2",
                ]
            )
        self.assertEqual(code, 0)
        pooled = (self.out.parent / "from" / "grantham" / "index.html").read_text(encoding="utf-8")
        # Build timestamp is deliberately shared between the in-process and
        # worker paths so their generated pages are byte-for-byte comparable.
        self.assertEqual(single.replace(single.split('"builtAt":"')[1][:20], "TIMESTAMP"), pooled.replace(pooled.split('"builtAt":"')[1][:20], "TIMESTAMP"))

    def test_a_pool_build_restores_fare_indexes_instead_of_re_parsing(self) -> None:
        # Audit B1: without persisted indexes, every worker re-parsed all 8.5M
        # flow lines on top of the parent's parse -- nine parses for eight
        # workers. The pool must find the shared metadata and per-origin
        # slices in CACHE_DIR before it starts.
        with contextlib.redirect_stdout(io.StringIO()):
            code = build_demo_page.main(
                [
                    "--feed", str(self.feed),
                    "--all-origins", "--out", str(self.out),
                    "--workers", "2",
                ]
            )
        self.assertEqual(code, 0)
        common_cache, index_dir = build_demo_page.fares_index_cache_paths(self.feed)
        self.assertTrue(common_cache.is_file(), "the shared metadata is persisted before the pool starts")
        self.assertTrue(index_dir.is_dir())
        self.assertTrue(
            list(index_dir.glob("*.pickle")),
            "one index per priceable origin is written for the workers",
        )
        restored = FaresDb.load_fare_common(common_cache)
        self.assertIsNotNone(restored.feed_stats, "the shared half carries the whole feed's stats")

    def test_the_build_says_how_to_open_what_it_wrote(self) -> None:
        # The pages are build output and their links are root-absolute, so
        # double-clicking the file does not work and a local server does.
        said = self.build()
        self.assertIn("http.server", said)
        self.assertIn("http://localhost", said)

    def test_a_feed_with_no_reviewed_price_still_writes_the_chooser(self) -> None:
        # A real feed can price nothing under the selector. The all-origins
        # build writes no station pages then, so the chooser's folder has to be
        # created by the chooser write rather than by a station page.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = build_synthetic_feed(root / "fares", include_restrictions=True)
            deletes = "".join(
                _line(
                    {
                        "update_marker": "D",
                        "record_type": "T",
                        "flow_id": flow_id,
                        "ticket_code": "SDR",
                    },
                    FLOW_T,
                )
                + "\n"
                for flow_id in ("0000001", "0000002", "0000003", "0000004", "0000005")
            )
            (feed / "zz-delete.ffl").write_text(deletes, encoding="utf-8")
            out = root / "site" / "index.html"
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = build_demo_page.main(
                    [
                        "--feed", str(feed),
                        "--all-origins", "--out", str(out),
                    ]
                )
            self.assertEqual(code, 0)
            chooser = out.read_text(encoding="utf-8")
            self.assertIn("Nothing is priced from any station in this build", chooser)



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


class PartialMetadataTest(unittest.TestCase):
    """Audit finding A3: a real feed's unfinished provenance note must not
    ship a page labelled "the synthetic demo feed". The build refuses instead.
    """

    def test_metadata_without_a_source_refuses_the_build(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        feed = build_synthetic_feed(root / "fares", include_restrictions=True)
        (feed / "metadata.json").write_text(
            json.dumps({"downloaded": "3 October 2026"}), encoding="utf-8"
        )
        out = root / "site" / "index.html"
        out.parent.mkdir(parents=True)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = build_demo_page.main(["--feed", str(feed), "--out", str(out)])
        self.assertEqual(code, 2)
        self.assertFalse(out.exists(), "no page may be written when provenance is unresolved")
        self.assertIn("names no 'source'", stderr.getvalue())

    def test_metadata_with_a_source_builds_normally(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        feed = build_synthetic_feed(root / "fares", include_restrictions=True)
        (feed / "metadata.json").write_text(
            json.dumps({"source": "RSP fares feed", "downloaded": "3 October 2026"}),
            encoding="utf-8",
        )
        out = root / "site" / "index.html"
        out.parent.mkdir(parents=True)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = build_demo_page.main(["--feed", str(feed), "--out", str(out)])
        self.assertEqual(code, 0)
        self.assertIn("RSP fares feed", out.read_text(encoding="utf-8"))

    def test_price_source_override_settles_an_unfinished_note(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        feed = build_synthetic_feed(root / "fares", include_restrictions=True)
        (feed / "metadata.json").write_text(
            json.dumps({"downloaded": "3 October 2026"}), encoding="utf-8"
        )
        out = root / "site" / "index.html"
        out.parent.mkdir(parents=True)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = build_demo_page.main(
                ["--feed", str(feed), "--out", str(out), "--price-source", "the 2026 RSP download"]
            )
        self.assertEqual(code, 0)
        self.assertIn("the 2026 RSP download", out.read_text(encoding="utf-8"))


class PublicationGateTest(unittest.TestCase):
    """No page at all without the data the reviewed selector depends on.

    The gate is the change's whole point: a fares feed whose .RST file never
    arrived cannot have its restriction codes checked, so the build refuses
    rather than falling back to the broad query's prices.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        # include_restrictions defaults to False: a feed with no .RST.
        self.feed = build_synthetic_feed(self.root / "fares")
        self.assertTrue((self.feed / "rjfaf.rst").exists() is False)

    def run_build(self, out: Path, *extra: str) -> tuple[int, str]:
        stderr = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            code = build_demo_page.main(["--feed", str(self.feed), "--out", str(out), *extra])
        return code, stderr.getvalue()

    def test_a_feed_with_no_restriction_file_refuses_the_build(self) -> None:
        out = self.root / "site" / "index.html"
        code, said = self.run_build(out)
        self.assertEqual(code, 2)
        self.assertFalse(out.exists(), "a refused build must write no page")
        self.assertIn("no .RST restriction file", said)

    def test_the_refusal_also_writes_no_chooser_or_station_pages(self) -> None:
        out = self.root / "site" / "index.html"
        code, _ = self.run_build(out, "--all-origins")
        self.assertEqual(code, 2)
        self.assertFalse(out.parent.exists(), "a refused build must leave no folder behind")


class UnsourcedDestinationTest(unittest.TestCase):
    """The build names a priced destination it cannot classify.

    The synthetic feed classifies every station, so a row is made unsourced
    here: the point of the check is what the build does with one, not how a
    feed comes to have one.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.feed = build_synthetic_feed(self.root / "fares", include_restrictions=True)
        (self.root / "metadata.json").write_text(
            json.dumps({"source": "RSP fares feed", "downloaded": "3 October 2026"}),
            encoding="utf-8",
        )

    def run_build(self, out: Path, *extra: str, unsourced: bool = True) -> tuple[int, str]:
        """Build, with Lincoln left unclassified when ``unsourced``.

        The gap is made at the source -- ``destination_type`` is the one answer
        both the payload and the chooser's own query read -- so this exercises
        the same path a real unnamed station takes rather than a faked row.
        """
        stderr = io.StringIO()
        patches = []
        if unsourced:
            real = FaresDb.destination_type

            def lossy(self, crs):
                return "other" if crs.strip().upper() == "LCN" else real(self, crs)

            patches.append(mock.patch.object(FaresDb, "destination_type", lossy))
        with contextlib.ExitStack() as stack:
            for patch in patches:
                stack.enter_context(patch)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
                code = build_demo_page.main(["--feed", str(self.feed), "--out", str(out), *extra])
        return code, stderr.getvalue()

    def test_a_clean_page_is_not_warned_about(self) -> None:
        out = self.root / "site" / "index.html"
        code, said = self.run_build(out, unsourced=False)
        self.assertEqual(code, 0)
        self.assertNotIn("no settlement class", said)

    def test_an_unsourced_destination_is_named_in_a_warning(self) -> None:
        out = self.root / "site" / "index.html"
        code, said = self.run_build(out)
        self.assertEqual(code, 0)
        self.assertIn("no settlement class from any source", said)
        self.assertIn("LCN", said)

    def test_the_strict_flag_refuses_and_writes_nothing(self) -> None:
        out = self.root / "site" / "index.html"
        code, said = self.run_build(out, "--fail-on-unsourced")
        self.assertEqual(code, 2)
        self.assertFalse(out.exists(), "a refused build must write no page")
        self.assertIn("refusing to publish", said)

    def test_the_strict_flag_refuses_before_writing_any_page(self) -> None:
        out = self.root / "site" / "index.html"
        code, _ = self.run_build(out, "--all-origins", "--fail-on-unsourced")
        self.assertEqual(code, 2)
        self.assertFalse(out.parent.exists(), "a refused build must leave no folder behind")


class ClassificationGateTest(unittest.TestCase):
    """A lost classification source is a visible build event (audit A5).

    The synthetic feed's classification sources are all local, so the failure
    is injected where the loader would record it: the point is what the build
    does with a recorded failure, not how one comes to exist.
    """

    FAILURE = "seaside station classification unavailable: no network in this sandbox"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.feed = build_synthetic_feed(self.root / "fares", include_restrictions=True)
        (self.root / "metadata.json").write_text(
            json.dumps({"source": "RSP fares feed", "downloaded": "3 October 2026"}),
            encoding="utf-8",
        )

    def build(self, *extra: str) -> tuple[int, str, str, Path]:
        out = self.root / "site" / "index.html"
        original = FaresDb.load_feed

        def with_failure(db_self, *args, **kwargs):
            loaded = original(db_self, *args, **kwargs)
            loaded.report.classification_failures.append(self.FAILURE)
            return loaded

        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(FaresDb, "load_feed", with_failure):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = build_demo_page.main(
                    ["--feed", str(self.feed), "--out", str(out), *extra]
                )
        return code, stdout.getvalue(), stderr.getvalue(), out

    def test_a_lost_classification_source_is_printed_and_the_build_publishes(self) -> None:
        code, said, _, out = self.build()
        self.assertEqual(code, 0, "without the flag the page still builds on the fallbacks")
        self.assertIn(f"classification: {self.FAILURE}", said)
        self.assertTrue(out.exists())

    def test_the_require_flag_refuses_and_writes_nothing(self) -> None:
        code, _, said, out = self.build("--require-classification")
        self.assertEqual(code, 2)
        self.assertIn("refusing to publish", said)
        self.assertIn("seaside station classification unavailable", said)
        self.assertFalse(out.exists(), "a refused build must write no page")

    def test_a_classification_skip_is_also_a_skipped_file(self) -> None:
        # feed_audit still sees it as an unopened source; the second list is
        # only what the build's gate reads.
        report = ParseReport()
        report.skip_classification(self.FAILURE)
        self.assertEqual(report.classification_failures, [self.FAILURE])
        self.assertEqual(report.skipped_files, [self.FAILURE])


class ReviewedCodeGateTest(unittest.TestCase):
    """A dead reviewed code is a visible build event (audit A7).

    The synthetic feed carries six stations, so almost every reviewed
    settlement-fallback code is absent from it -- which is exactly the state
    this gate exists to catch, and why the test needs no injection.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.feed = build_synthetic_feed(self.root / "fares", include_restrictions=True)
        (self.root / "metadata.json").write_text(
            json.dumps({"source": "RSP fares feed", "downloaded": "3 October 2026"}),
            encoding="utf-8",
        )

    def build(self, *extra: str) -> tuple[int, str, str, Path]:
        out = self.root / "site" / "index.html"
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = build_demo_page.main(
                ["--feed", str(self.feed), "--out", str(out), *extra]
            )
        return code, stdout.getvalue(), stderr.getvalue(), out

    def test_the_dead_codes_are_named_and_the_build_publishes(self) -> None:
        code, said, _, out = self.build()
        self.assertEqual(code, 0, "without the flag the page still builds")
        self.assertIn("reviewed codes:", said)
        self.assertIn("match no station in this feed", said)
        self.assertTrue(out.exists())

    def test_the_require_flag_refuses_and_names_the_codes(self) -> None:
        code, _, said, out = self.build("--require-live-reviewed-codes")
        self.assertEqual(code, 2)
        self.assertIn("refusing to publish", said)
        self.assertIn("reviewed settlement fallback code", said)
        self.assertFalse(out.exists(), "a refused build must write no page")

    def test_a_dead_code_is_named_once_and_is_not_an_unopened_file(self) -> None:
        # It is a list going stale, not a file left unread, so it gets its own
        # channel: reporting it as an unopened source would be a lie that also
        # hid it among the archive-inside-an-archive notes.
        with tempfile.TemporaryDirectory() as tmp:
            db = FaresDb().load_feed(
                build_synthetic_feed(Path(tmp) / "fares", include_restrictions=True)
            )
        self.assertTrue(db.report.reviewed_codes_absent)
        self.assertEqual(
            db.report.skipped_files,
            [],
            f"a dead reviewed code is not a skipped file: {db.report.skipped_files!r}",
        )

    def test_a_code_the_workbook_already_names_refuses_too(self) -> None:
        # The other half of the same staleness, and the harder half to notice.
        # The code resolves, so the absent list is not the one that catches it,
        # and nothing about the page looks wrong: the entry applies to nothing
        # at all until a name match misses and then lands its class on a
        # station the workbook had already classified correctly. BHC is stood in
        # for a reviewed Welsh entry, because the synthetic feed has no
        # workbook to read and this gate is about what the build does with what
        # the loader found.
        def workbook(self: FaresDb) -> None:
            self.ons_classified_crs.add("BHC")
            self._apply_major_station_fallbacks()

        (self.root / "download-manifest.json").write_text("{}", encoding="utf-8")
        # The synthetic feed ships its own classification cache, and a cache
        # that classifies the feed ends the pass before the workbook is read
        # -- so the gate under test would never run with it in place.
        (self.root / "fares.location-types.json").unlink()
        out = self.root / "site" / "index.html"
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(FaresDb, "_load_ons_location_types", workbook):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = build_demo_page.main(
                    ["--feed", str(self.feed), "--out", str(out), "--require-live-reviewed-codes"]
                )
        self.assertEqual(code, 2)
        # The note is where the code is legible: the refusal below it carries
        # the count, because the synthetic feed's 305 absent codes would
        # otherwise push BHC out of a truncated list, and a test that found
        # BHC in the *absent* list would pass without this half ever working.
        self.assertIn(
            "name a station the ONS workbook already classifies, so the entry "
            "applies to nothing: BHC",
            stdout.getvalue(),
        )
        self.assertIn("1 name a station the workbook already classifies", stderr.getvalue())
        self.assertFalse(out.exists(), "a refused build must write no page")


class PseudoStationTest(unittest.TestCase):
    """Zone boundaries are priceable in the feed but are not places (audit A6)."""

    class Station:
        def __init__(self, crs: str, name: str) -> None:
            self.crs = crs
            self.name = name

    def test_the_chooser_omits_a_priced_zone_boundary(self) -> None:
        locations = {
            "GRA": self.Station("GRA", "GRANTHAM"),
            "QAH": self.Station("QAH", "BOUNDARY ZONE 4"),
        }
        index = build_station_index({"GRA": 5, "QAH": 611}, locations)
        self.assertEqual([entry["crs"] for entry in index], ["GRA"])

    def test_the_jump_list_omits_pseudo_stations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fares = FaresDb().load_feed(
                build_synthetic_feed(Path(tmp) / "fares", include_restrictions=True)
            )
            fares.locations_by_crs = dict(
                fares.locations_by_crs,
                QAH=self.Station("QAH", "BOUNDARY ZONE 4"),
            )
            payload = build_payload(fares, None, "GRN")
        names = {station["name"] for station in payload["stations"]}
        self.assertNotIn("BOUNDARY ZONE 4", names)
        self.assertTrue(names, "the jump list still carries the real stations")
        self.assertTrue(any("NOTTINGHAM" in name for name in names))

    def test_a_pseudo_destination_is_not_published_as_a_place(self) -> None:
        # A zone boundary records a fare change, not a journey, so it must not
        # become a row a reader could buy a ticket to. The rule lives in the
        # shared query loop, so the page, the chooser and the coverage report
        # cannot disagree about it.
        with tempfile.TemporaryDirectory() as tmp:
            feed = build_synthetic_feed(Path(tmp) / "fares", include_restrictions=True)
            (feed / "rjfaf.loc").open("a", encoding="utf-8").write(
                _line(
                    {
                        "update_marker": "A",
                        "record_type": "L",
                        "nlc": "9999",
                        "description": "BOUNDARY ZONE 4",
                        "crs": "QAH",
                        "group_nlc": "9999",
                    },
                    LOCATION,
                )
                + "\n"
            )
            (feed / "rjfaf.ffl").open("a", encoding="utf-8").write(
                _line(
                    {
                        "update_marker": "A",
                        "record_type": "F",
                        "origin_nlc": "1000",
                        "destination_nlc": "9999",
                        "route_code": "00000",
                        "flow_id": "0000099",
                    },
                    FLOW_F,
                )
                + "\n"
                + _line(
                    {
                        "update_marker": "A",
                        "record_type": "T",
                        "flow_id": "0000099",
                        "ticket_code": "CDR",
                        "fare_pence": "1500",
                        "restriction_code": "1A",
                    },
                    FLOW_T,
                )
                + "\n"
            )
            fares = FaresDb().load_feed(feed)
            # The feed does reach the zone and does price a fare to it, and the
            # query says where that fare went rather than dropping it silently.
            tally: dict[str, int] = {}
            reachable = fares.destinations_within("GRN", 10_000_000, adults=1, tally=tally)
            self.assertEqual(tally["destination_is_a_fare_construction_point"], 1)
            self.assertNotIn(
                "QAH", [row.crs for row in reachable], "the zone is not a destination"
            )
            payload = build_payload(fares, None, "GRN")
            rows = (
                payload["destinations"]
                + payload["singleDestinations"]
                + payload["anytimeDestinations"]
            )
        self.assertTrue(
            all(row["crs"] != "QAH" for row in rows),
            f"a zone boundary was published as a destination: {rows!r}",
        )
        self.assertTrue(rows, "the page's real destinations are untouched")


class UnnameableCeilingTest(unittest.TestCase):
    """The payload carries the priced rows the feed could not name (audit A3)."""

    @staticmethod
    def shapes_feed(root: Path) -> FaresDb:
        return FaresDb().load_feed(
            build_synthetic_feed(
                root / "shapes", include_real_shapes=True, include_restrictions=True
            )
        )

    def test_the_payload_counts_the_rows_with_no_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fares = self.shapes_feed(Path(tmp))
            payload = build_payload(fares, None, "GRN")
        self.assertEqual(payload["unnameableFareCount"], 2)

    def test_the_index_pass_records_them_for_the_coverage_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fares = self.shapes_feed(Path(tmp))
            coverage = UnsourcedReport()
            count = build_demo_page._priced_destinations(
                fares, None, "GRN", None, coverage
            )
        self.assertGreater(count, 0)
        self.assertEqual(coverage.unnameable_by_origin(), {"GRN": 2})


class TimetableCachePruneTest(unittest.TestCase):
    """Each origin keeps its newest timetable caches; stale digests go (audit B4)."""

    @staticmethod
    def cache(root: Path, name: str, mtime: float) -> Path:
        path = root / name
        path.write_bytes(b"stale")
        os.utime(path, (mtime, mtime))
        return path

    def test_the_caches_in_use_survive_and_the_origin_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(build_demo_page, "CACHE_DIR", root):
                main = self.cache(
                    root, "timetable-GRA-11111111111111111111.pickle", 1000.0
                )
                single = self.cache(
                    root, "timetable-GRA-22222222222222222222.pickle", 2000.0
                )
                self.cache(root, "timetable-GRA-33333333333333333333.pickle", 3000.0)
                old = self.cache(
                    root, "timetable-GRA-44444444444444444444.pickle", 500.0
                )
                other = self.cache(
                    root, "timetable-SFA-55555555555555555555.pickle", 400.0
                )
                pruned = build_demo_page.prune_timetable_caches(main, single)
            self.assertEqual(pruned, 2, "the two stale GRA digests are deleted")
            self.assertTrue(main.exists() and single.exists(), "caches in use survive")
            self.assertFalse(
                (root / "timetable-GRA-33333333333333333333.pickle").exists()
            )
            self.assertFalse(old.exists())
            self.assertTrue(other.exists(), "another origin's cache is untouched")

    def test_a_single_cache_keeps_one_newest_stale_sibling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(build_demo_page, "CACHE_DIR", root):
                main = self.cache(
                    root, "timetable-GRA-aaaaaaaaaaaaaaaaaaaa.pickle", 1000.0
                )
                newest = self.cache(
                    root, "timetable-GRA-bbbbbbbbbbbbbbbbbbbb.pickle", 3000.0
                )
                stale = self.cache(
                    root, "timetable-GRA-cccccccccccccccccccc.pickle", 500.0
                )
                pruned = build_demo_page.prune_timetable_caches(main)
            self.assertEqual(pruned, 1)
            self.assertTrue(main.exists())
            self.assertTrue(
                newest.exists(), "the keep line retains the newest stale sibling"
            )
            self.assertFalse(stale.exists())

    def test_a_cache_hit_that_is_the_oldest_file_still_survives(self) -> None:
        # A hit does not touch mtime, so the file this build just read can be
        # the oldest on disk. It must not evict itself.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(build_demo_page, "CACHE_DIR", root):
                hit = self.cache(
                    root, "timetable-GRA-dddddddddddddddddddd.pickle", 100.0
                )
                newer = self.cache(
                    root, "timetable-GRA-eeeeeeeeeeeeeeeeeeee.pickle", 9000.0
                )
                newest = self.cache(
                    root, "timetable-GRA-ffffffffffffffffffff.pickle", 8000.0
                )
                pruned = build_demo_page.prune_timetable_caches(hit, keep=1)
            self.assertEqual(pruned, 2)
            self.assertTrue(hit.exists(), "the used cache survives even at keep=1")
            self.assertFalse(newer.exists())
            self.assertFalse(newest.exists())


class FreshOutputFolderTest(unittest.TestCase):
    """The README tells the operator to delete a stale _site/, so the build must
    create a missing output folder rather than only working when one exists."""

    def test_a_single_origin_build_creates_its_output_folder(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        feed = build_synthetic_feed(root / "fares", include_restrictions=True)
        out = root / "fresh" / "site" / "index.html"
        self.assertFalse(out.parent.exists())
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = build_demo_page.main(["--feed", str(feed), "--out", str(out)])
        self.assertEqual(code, 0)
        self.assertTrue(out.exists())
        self.assertIn("GRANTHAM", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
