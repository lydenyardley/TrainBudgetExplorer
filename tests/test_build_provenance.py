"""Where the numbers came from: notices, contact, price source and freshness.

F6 of the 8 October 2026 agent-efficiency audit moved the page's content
tests out of the class they all shared, by subject, over the fixture in
``tests/page_harness.PageTestCase``.
"""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from unittest import mock
import contextlib
import io
from pathlib import Path
import argparse
from trainbudget.build import build_demo_page
from trainbudget.build import build_release
from trainbudget.build.build_demo_page import DEFAULT_PRICE_SOURCE, NOTICES, notices_or_attribution
from trainbudget.timetable.atoc_timetable import TimetableDb
from trainbudget.build.build_demo_page import nre_attribution, wants_nre_credit, build_payload, render_chooser, render_page, render_privacy
from trainbudget.feeds.make_synthetic_feed import build_synthetic_feed, build_synthetic_timetable
from tools.check_release_clearance import PRIVACY, parse_sections
from tests.page_harness import browser_suite_text, page_script, setUpModule, station_page, tearDownModule, PageTestCase


class ProvenanceTest(PageTestCase):
    def test_payload_records_the_source_fingerprint_used_to_build_the_page(self) -> None:
        self.assertRegex(self.payload["sourceFingerprint"], r"^[0-9a-f]{16}$")
        self.assertIn("sourceFingerprint", self.html)

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
        self.assertIn("DATA.attribution", page_script(html))

    # -- where the numbers came from, and what they promise ------------------

    def test_the_provenance_line_sits_with_the_prices_by_default(self) -> None:
        # A synthetic build says its prices are synthetic, beside the prices,
        # not in a footer the reader has already left.
        self.assertEqual(self.payload["priceSource"], DEFAULT_PRICE_SOURCE)
        self.assertIn('id="priceSource" hidden', self.html)
        self.assertIn("DATA.priceSource", page_script(self.html))

    def test_the_price_line_tells_the_two_dates_apart_and_names_the_build(self) -> None:
        # Item 45 of the 14 October 2026 clarity audit: the second date is the
        # day the build asked about, not a date on the feed, and the sentence has
        # to say which is which -- "feed dated" read as "the feed is dated
        # today", which is the age the freshness line is warning about. Items 46
        # and 49: the build stamp is named for what it is and dated in the page's
        # own words rather than as the one ISO date on the page.
        script = page_script(self.html)
        self.assertIn('", downloaded "', script)
        self.assertIn('"; fares and times read for "', script)
        self.assertNotIn("feed dated ", script)
        self.assertIn("from this revision of the code", script)

    def test_the_destination_type_source_sits_with_the_attribution(self) -> None:
        # Item 48: the provenance line carries the reader's own facts -- the
        # origin, the count and the day -- and where a destination's type came
        # from is a source, so it is said with the licence text rather than
        # among the numbers.
        self.assertTrue(self.payload["locationTypeSource"])
        script = page_script(self.html)
        self.assertIn('"Destination types from: "', script)
        self.assertNotIn('"destination types: "', script)

    def test_the_page_states_how_old_its_numbers_are(self) -> None:
        # S33: the age of the prices and the window of the times, beside the
        # numbers, judged against the reader's clock rather than the build's.
        self.assertIn('id="freshness"', self.html)
        self.assertEqual(self.payload["staleAfterDays"], build_demo_page.STALE_AFTER_DAYS)
        self.assertEqual(self.payload["timetableFrom"], "2026-09-21")
        self.assertEqual(self.payload["timetableTo"], "2026-12-11")
        # A build with no timetable says so, and that is a choice rather than a
        # feed that has gone stale.
        prices_only = build_payload(self.fares, None, "GRN")
        self.assertIsNone(prices_only["timetableFrom"])
        # The prices-only sentence is read off the prices-only page in the
        # browser suite, which drives one of each shape; pinning its words here
        # passed while the page printed none of them (A6 of the 20 October 2026
        # poteto audit). The stale-window sentence stays here because no fixture
        # in this tree has a window that has ended, so this is its only holder.
        self.assertIn("which has ended, so these times describe services that no longer run", page_script(self.html))

    def test_the_freshness_claim_is_judged_against_the_builds_own_date(self) -> None:
        # The suite reports the page's own feedDate and judges the sentence
        # beside it in node, so the age on the page is compared with the age
        # the page should have printed rather than merely looked for. A page
        # claiming "downloaded 24 September 2026" beside a stale "0 days old"
        # passes a presence test and misleads the reader this sentence exists
        # for, which is the reader deciding whether to trust a fare.
        suite = browser_suite_text()
        self.assertIn("feedDate: DATA.feedDate || null,", suite)
        self.assertIn("daysSince(fresh.feedDate)", suite)
        self.assertIn("a feed with a download date says how old its prices are", suite)

    def test_the_feed_date_is_the_downloads_own_and_never_a_timetables(self) -> None:
        # The date has to describe the fares: a newer timetable download must
        # not make the prices look fresh.
        self.assertEqual(
            build_demo_page.feed_date_from({"downloaded": "2026-09-20T09:15:00Z"}),
            "2026-09-20",
        )
        manifest = {
            "downloads": [
                {"source": "dtd", "name": "fares", "downloaded_at": "2026-09-18T06:00:00Z"},
                {"source": "dtd", "name": "timetable", "downloaded_at": "2026-09-25T06:00:00Z"},
            ]
        }
        self.assertEqual(build_demo_page.feed_date_from(None, manifest), "2026-09-18")
        # A timetable-only manifest still dates something honestly rather than
        # claiming the prices came from a download that never carried them.
        self.assertEqual(
            build_demo_page.feed_date_from(None, {"downloads": [manifest["downloads"][1]]}),
            "2026-09-25",
        )
        self.assertIsNone(build_demo_page.feed_date_from(None, None))
        self.assertIsNone(build_demo_page.feed_date_from({"downloaded": "soon"}, None))

    def test_a_cif_date_becomes_an_iso_date_and_a_non_date_does_not(self) -> None:
        # The feed states its window in six digits; the page measures it in
        # calendar dates, and a value that is not a date is not guessed at.
        self.assertEqual(build_demo_page.cif_date_to_iso("260921"), "2026-09-21")
        for value in ("", "2609", "2609211", "26-09-21", "abcdef"):
            self.assertIsNone(build_demo_page.cif_date_to_iso(value), value)

    def test_the_timetable_reports_its_own_service_window(self) -> None:
        # Read from the feed's own records, so the page and the audit cannot
        # disagree about the window they print.
        self.assertEqual(self.timetable.service_window(), ("260921", "261211"))
        self.assertEqual(TimetableDb().service_window(), ("", ""))
        self.assertEqual(
            TimetableDb().load_feed(build_synthetic_timetable(Path(self._tmp.name) / "again")).service_window(),
            ("260921", "261211"),
        )
        # Asked for by every station page in a full-network build, so it is
        # answered from the database once rather than by rescanning the feed --
        # and the answer is still right if the database grows afterwards.
        again = TimetableDb().load_feed(build_synthetic_timetable(Path(self._tmp.name) / "again"))
        first = again.service_window()
        self.assertIs(again.service_window(), first, "the window is not memoised")
        again.schedules.append(
            type(again.schedules[0])(**{**vars(again.schedules[0]), "date_from": "260101", "date_to": "270101"})
        )
        self.assertEqual(again.service_window(), ("260101", "270101"))

    def test_the_privacy_page_describes_the_build_that_was_made(self) -> None:
        # S36: the notice is generated from the same feature configuration the
        # pages are built from, so it cannot describe a different site.
        plain = build_demo_page.site_features(
            analytics=False, link_mode="fallback", network=None, disclosure=None
        )
        measured = build_demo_page.site_features(
            analytics=True, link_mode="fallback", network=None, disclosure="analytics snippet"
        )
        tracked = build_demo_page.site_features(
            analytics=False, link_mode="fallback", network="affiliate-x", disclosure="Tracked"
        )
        quiet = build_demo_page.render_privacy("note", "/base", "a@b.test", plain)
        self.assertIn("No analytics run", quiet)
        self.assertNotIn("__PRACTICES__", quiet)
        # C19 of the 17 October 2026 critique: the back link and the theme
        # switch are one row of chrome above the document, so the reading order
        # under it is the title.
        self.assertIn('<div class="route-top">', quiet)
        self.assertLess(quiet.index('class="route-top"'), quiet.index('id="themeToggle"'))
        self.assertLess(quiet.index('id="themeToggle"'), quiet.index("<main>"))
        # D13 of the same critique: the address section names its parameters in
        # one line of short names rather than listing them in a sentence.
        self.assertIn("<code>budget</code>, <code>mode</code>", quiet)
        self.assertNotIn("whether the budget covers one adult or two", quiet)
        # One sentence per bullet, pointing at its own section rather than
        # restating it (audit item 17, 9 October 2026): the paragraph and the
        # two bullets below that list entry make the same point with room to
        # explain it, and the entry is read first and learned last.
        self.assertIn("what stays in the address bar, below, explains it in full", quiet)
        self.assertNotIn("so a refresh or a shared link returns the same results", quiet)
        # The word "below" is a claim about the order, so the order is asserted
        # rather than trusted: the summary comes first and the deep dive it
        # points at follows it (route audit item 18, 9 October 2026). A
        # previous copy of this page put the deep dive first and left the word
        # pointing at a section the reader had already read.
        self.assertLess(
            quiet.index("what stays in the address bar, below"),
            quiet.index("<h2>What stays in the address bar</h2>"),
            "the bullet's referent must follow the bullet",
        )
        self.assertLess(
            quiet.index("<h2>What this site does</h2>"),
            quiet.index("<h2>What stays in the address bar</h2>"),
            "the summary must come before the deep dive",
        )
        # The notice's build-dependent sentences are dated from the build's own
        # stamp (route audit item 16, 9 October 2026): "no analytics run" is a
        # promise about a build, and a build nobody can date is a promise
        # nobody can hold.
        dated = build_demo_page.render_privacy(
            "note", "", "a@b.test", plain, built_at="2026-10-11T09:15:00Z"
        )
        # C20/D14 of the 17 October 2026 critique: the line is a fact about the
        # notice, not a sentence addressed to a maintainer.
        self.assertIn("Last updated 11 October 2026.", dated)
        # C17/D12: the third bullet was the union of the cookie and analytics
        # sentences, so it is gone rather than restated.
        self.assertNotIn("does not collect visit data", quiet)
        # And it dates the build rather than claiming a publication: a build
        # nobody deployed is not published, and the phrase is false of every
        # build that never reached the deploy job (clarity audit item 42).
        self.assertNotIn("publish", dated.split('id="builtLine">', 1)[1].split("</p>", 1)[0])
        self.assertIn('id="builtLine"', dated)
        self.assertNotIn(
            'id="builtLine" hidden',
            dated,
            "a dated notice nobody can read is not a dated notice",
        )
        self.assertNotIn("__BUILT_LINE__", dated)
        self.assertNotIn("Last updated", quiet, "an undated build says so by omitting the line")
        self.assertIn("injects an analytics snippet", build_demo_page.render_privacy("note", "", "a@b.test", measured))
        self.assertIn(
            "affiliate network",
            build_demo_page.render_privacy("note", "", "a@b.test", tracked),
        )
        # The contact is required whatever the features are, and the base path
        # still prefixes the way back.
        with self.assertRaises(ValueError):
            build_demo_page.render_privacy("note", "", "   ", plain)
        self.assertIn('href="/base/"', quiet)

    def test_a_public_build_cannot_publish_an_incomplete_notice(self) -> None:
        # S36, S37: fail closed. Each gap is named, because a refusal an
        # operator cannot act on is a refusal they will work around.
        features = build_demo_page.site_features(
            analytics=False, link_mode="fallback", network=None, disclosure=None
        )
        self.assertEqual(
            build_demo_page.release_gate_problems(features, public=False, notices=None, contact="a@b.test"),
            [],
        )
        self.assertEqual(
            build_demo_page.privacy_gaps(features, "  "),
            [
                "no privacy contact is configured, so nobody can be told about a problem "
                "with this site (set PRIVACY_CONTACT or pass --privacy-contact)"
            ],
        )
        tracked = build_demo_page.site_features(
            analytics=False, link_mode="fallback", network="affiliate-x", disclosure=None
        )
        self.assertIn(
            "no disclosure is set",
            " ".join(build_demo_page.privacy_gaps(tracked, "a@b.test")),
        )
        # A deep link is not tracking: it hands the seller the search the
        # reader was reading and the page says so. Only the network tracks.
        deep = build_demo_page.site_features(
            analytics=False, link_mode="deep", network=None, disclosure=None
        )
        self.assertEqual(build_demo_page.privacy_gaps(deep, "a@b.test"), [])
        # Measurement without a plan is a gap, and a plan closes it.
        self.assertIn(
            "no measurement plan is recorded",
            " ".join(
                build_demo_page.privacy_gaps(
                    build_demo_page.site_features(
                        analytics=True, link_mode="fallback", network=None, disclosure=None
                    ),
                    "a@b.test",
                )
            ),
        )
        self.assertEqual(
            build_demo_page.privacy_gaps(
                build_demo_page.site_features(
                    analytics=True,
                    link_mode="fallback",
                    network=None,
                    disclosure=None,
                    measurement="aggregate-referrer-counts",
                ),
                "a@b.test",
            ),
            [],
        )
        # A public build without a licence notice is refused; a synthetic one is
        # exempt because it publishes no real fares.
        self.assertEqual(
            [
                problem
                for problem in build_demo_page.release_gate_problems(
                    features, public=True, notices=None, contact="a@b.test"
                )
                if "licence" in problem
            ],
            [
                "a public build carries no licence or attribution notice; pass --notices "
                "(or --attribution) so the obligations travel with the site"
            ],
        )
        self.assertEqual(
            build_demo_page.release_gate_problems(
                features, public=True, notices=["a notice"], contact="a@b.test"
            ),
            [],
        )

    def test_analytics_needs_a_written_measurement_plan(self) -> None:
        # S38: the flag cannot be reached without naming a plan, and the plans
        # are written out rather than implied.
        self.assertIn("aggregate-referrer-counts", build_demo_page.MEASUREMENT_PLANS)
        self.assertIn("no persistent identifier", build_demo_page.MEASUREMENT_PLANS["aggregate-referrer-counts"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = build_synthetic_feed(root / "fares", include_restrictions=True)
            snippet = root / "snippet.js"
            snippet.write_text("window.x = 1;", encoding="utf-8")
            out = root / "site" / "index.html"
            buffer = io.StringIO()
            with contextlib.redirect_stderr(buffer):
                code = build_demo_page.main(
                    ["--feed", str(feed), "--out", str(out), "--analytics-snippet", str(snippet)]
                )
            self.assertEqual(code, 2)
            self.assertIn("--measurement-plan", buffer.getvalue())
            # With a plan named, the same build proceeds.
            with contextlib.redirect_stdout(io.StringIO()):
                code = build_demo_page.main(
                    [
                        "--feed", str(feed),
                        "--out", str(out),
                        "--analytics-snippet", str(snippet),
                        "--measurement-plan", "aggregate-referrer-counts",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertIn("injects an analytics snippet", (root / "site" / "privacy" / "index.html").read_text(encoding="utf-8"))

    def test_a_real_source_build_is_refused_until_it_carries_a_notice(self) -> None:
        # S37: a build that names a real price source publishes real fares, so
        # the licence notice and somebody to contact are conditions of the
        # build rather than a step in a checklist. Both are named in the
        # refusal, because a refusal nobody can act on is one they route
        # around.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = build_synthetic_feed(root / "fares", include_restrictions=True)
            out = root / "site" / "index.html"
            refused = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(refused):
                code = build_demo_page.main(
                    ["--feed", str(feed), "--out", str(out), "--price-source", "the RSP feed"]
                )
            self.assertEqual(code, 2)
            self.assertFalse(out.exists(), "a refused build writes no page")
            # The project now carries its own contact, so the notice is the
            # condition this build trips. The contact condition is still real
            # and is driven by a deliberately blank one below.
            self.assertIn("carries no licence or attribution notice", refused.getvalue())
            self.assertNotIn("no privacy contact is configured", refused.getvalue())
            # A contact that is configured but blank is refused, so the gate is
            # not satisfied by the mere existence of a default: a build that
            # sets an empty contact on purpose stops.
            with mock.patch.dict(os.environ, {"PRIVACY_CONTACT": "   "}, clear=False):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(refused):
                    code = build_demo_page.main(
                        [
                            "--feed", str(feed),
                            "--out", str(out),
                            "--price-source", "the RSP feed",
                            "--notices", "rdg,ogl,accuracy",
                        ]
                    )
            self.assertEqual(code, 2)
            self.assertIn("no privacy contact is configured", refused.getvalue())
            with contextlib.redirect_stdout(io.StringIO()):
                code = build_demo_page.main(
                    [
                        "--feed", str(feed),
                        "--out", str(out),
                        "--price-source", "the RSP feed",
                        "--notices", "rdg,ogl,accuracy",
                        "--privacy-contact", "privacy@b.test",
                    ]
                )
            self.assertEqual(code, 0)
            privacy = (root / "site" / "privacy" / "index.html").read_text(encoding="utf-8")
            self.assertIn("privacy@b.test", privacy)

    def test_a_real_build_names_the_project_contact_without_being_asked(self) -> None:
        # The contact is a fact about the project, not a deployment setting, so
        # a real build has one without an operator having to supply it. Without
        # this the gate fires on every local real-feed build, and a gate that
        # fires constantly is a gate people route around.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = build_synthetic_feed(root / "fares", include_restrictions=True)
            out = root / "site" / "index.html"
            with contextlib.redirect_stdout(io.StringIO()):
                code = build_demo_page.main(
                    [
                        "--feed", str(feed),
                        "--out", str(out),
                        "--price-source", "the RSP feed",
                        "--notices", "rdg,ogl,accuracy",
                    ]
                )
            self.assertEqual(code, 0)
            privacy = (root / "site" / "privacy" / "index.html").read_text(encoding="utf-8")
            self.assertIn(build_demo_page.ISSUE_TRACKER, privacy)
            contact = privacy.split("<h2>Contact</h2>", 1)[1].split("</p>", 1)[0]
            self.assertNotRegex(contact, r"[\w.+-]+@[\w.-]+")

    def test_the_contact_review_box_and_the_record_agree(self) -> None:
        # Naming the issue tracker is not the same thing as somebody reading it,
        # so the page's promise is only as good as the two places that carry the
        # confirmation agreeing with each other: a box checked with no dated
        # decision behind it publishes a route nobody confirmed anybody reads,
        # and a cleared contact with the box still open sends the publisher to
        # redo work that is already done. Either direction is a defect, so the
        # test asserts the agreement rather than one state.
        self.assertNotIn("@", build_demo_page.DEFAULT_PRIVACY_CONTACT)
        self.assertIn(build_demo_page.ISSUE_TRACKER, build_demo_page.DEFAULT_PRIVACY_CONTACT)
        root_dir = Path(__file__).parent.parent
        checklist = (root_dir / "docs" / "publish-checklist.md").read_text(encoding="utf-8")
        self.assertIn(build_demo_page.ISSUE_TRACKER, checklist)
        box = [
            line
            for line in checklist.splitlines()
            if "monitored contact route exists" in line
        ]
        self.assertEqual(len(box), 1, f"expected one review box, found {box}")
        record = (root_dir / "licences" / "release-clearance.md").read_text(encoding="utf-8")
        heading = next(h for h in parse_sections(record) if PRIVACY in h.lower())
        fields = parse_sections(record)[heading]
        self.assertEqual(
            box[0].startswith("- [x] "),
            fields.get("state") == "cleared",
            f"the checklist box is {box[0][:6]!r} and the record's {heading!r} "
            f"section says state: {fields.get('state')!r}",
        )
        if fields.get("state") == "cleared":
            # A cleared route is a dated decision by a named person, because the
            # thing being cleared is a promise rather than a term.
            for field in ("read on", "approved on", "approved by", "expires"):
                self.assertTrue(fields.get(field), f"the record clears the contact with no {field!r}")

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
        # The feed's name, and nothing else: the download date travels beside it
        # as a value of its own (`feed_date_from`), because every route that
        # names both has to compose one sentence from the pair. While the date
        # lived inside this string the chooser appended its own copy of it and
        # printed the same date twice.
        self.assertEqual(
            build_demo_page.price_source_from_metadata(metadata),
            "the RSP fares feed",
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
                code = build_demo_page.main(
                    [
                        "--feed", str(feed),
                        "--out", str(out),
                        "--notices", "accuracy",
                        "--privacy-contact", "a@b.test",
                    ]
                )
            self.assertEqual(code, 0)
            page = station_page(out).read_text(encoding="utf-8")
            # The page carries the name and the date as two values, and its own
            # script composes the sentence from them (the browser suite reads
            # the rendered `#freshness` and `#priceSource` lines; this holds the
            # pair the build wrote).
            self.assertIn('"priceSource":"the National Rail Data Portal DTD fares feed"', page)
            self.assertIn('"feedDate":"2026-09-23"', page)
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
                code = build_demo_page.main(
                    [
                        "--feed", str(archive),
                        "--out", str(out),
                        "--notices", "accuracy",
                        "--privacy-contact", "a@b.test",
                    ]
                )
            self.assertEqual(code, 0)
            page = station_page(out).read_text(encoding="utf-8")
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
            "the National Rail Data Portal DTD fares feed",
        )
        # The date is the fares entry's own, and the fares entry's alone: a
        # newer timetable download must not make the prices look fresher than
        # they are (`feed_date_from` has that test).
        self.assertEqual(
            build_demo_page.feed_date_from(
                None,
                {
                    "downloads": [
                        {"name": "fares", "source": "dtd", "downloaded_at": "2026-09-23T14:02:11Z"},
                        {"name": "timetable", "source": "dtd", "downloaded_at": "2026-09-24T03:00:00Z"},
                    ]
                },
            ),
            "2026-09-23",
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

    def test_the_analytics_snippet_is_injected_only_when_given(self) -> None:
        snippet = "<script>window.seen=1;</script>"
        self.assertNotIn("window.seen", self.html)
        html = render_page(self.payload, budget_pounds=20, analytics=snippet)
        self.assertIn(snippet, html)
        self.assertNotIn("__ANALYTICS__", html)

    def test_the_nre_credit_is_the_mark_the_guidelines_name(self) -> None:
        # The Developer Brand Guidelines require the "Powered by National Rail
        # Enquiries" logo and a link to NRE's site, inlined so a self-contained
        # page still shows it. The mark is paths, so the name a screen reader
        # reads has to be written out; nothing in an SVG carries it.
        credit = nre_attribution()
        self.assertIn('aria-label="Powered by National Rail Enquiries"', credit)
        self.assertIn("nationalrail.co.uk", credit)
        self.assertIn("<svg", credit)
        self.assertGreater(credit.count("<path"), 5)
        # Inline, not linked: the page is one file and the attribution must not
        # need a second request to appear.
        self.assertNotIn("<?xml", credit)
        self.assertNotIn("Adobe Illustrator", credit)
        self.assertNotIn("<img", credit)
        self.assertNotIn('src="', credit)
        # The mark is reversed onto a dark plate by the page's own stylesheet, so
        # the file in assets/ must still be NRE's, with NRE's colour in it. If
        # somebody "helpfully" baked the light ink into the file, this is what
        # catches it -- and the page would no longer be carrying the artwork it
        # was given.
        mark = (Path(__file__).parent.parent / "assets" / "powered-by-national-rail.svg").read_text(
            encoding="iso-8859-1"
        )
        self.assertIn("2E2D7F", mark)
        self.assertNotIn("cdd6ff", mark.lower())
        self.assertNotIn("141b3d", mark.lower())

    def test_the_credit_is_written_only_where_the_page_acknowledges_nre(self) -> None:
        # Composing the NRE notice is what asks for the mark; a build given
        # verbatim attribution text is not second-guessed.
        self.assertTrue(wants_nre_credit([NOTICES["nre"], NOTICES["ogl"]]))
        self.assertFalse(wants_nre_credit([NOTICES["rdg"], NOTICES["ogl"]]))
        self.assertFalse(wants_nre_credit("some wording of the operator's own"))
        self.assertFalse(wants_nre_credit(None))
        with_credit = render_page(self.payload, budget_pounds=20, nre_credit=True)
        self.assertIn('class="nre-credit"', with_credit)
        self.assertNotIn('class="nre-credit"', render_page(self.payload, budget_pounds=20))
        # The footer credit is the notice the build already uses, linked to the
        # enquiries site, and it says NRE does not endorse the page. A build
        # that did not ask for the NRE notice does not invent the credit.
        self.assertIn(NOTICES["nre"], with_credit)
        self.assertIn('href="https://www.nationalrail.co.uk/"', with_credit)
        self.assertIn("does not endorse this site", with_credit)
        self.assertNotIn("nre-source", render_page(self.payload, budget_pounds=20))

    def test_a_missing_nre_mark_is_a_build_failure_not_a_page_without_one(self) -> None:
        # This is the one thing in the footer the licence names, so a build that
        # cannot find it stops rather than publishing a page with the credit
        # quietly absent.
        with mock.patch.object(build_release, "NRE_LOGO", Path("no-such-mark.svg")):
            with self.assertRaises(SystemExit):
                nre_attribution()

    def test_privacy_requires_a_contact_and_uses_the_deployment_route(self) -> None:
        with self.assertRaises(ValueError):
            render_privacy("note")
        html = render_privacy("note", contact="privacy@example.test")
        self.assertIn("privacy@example.test", html)
        self.assertNotIn("goes here before the site is published", html)
        # The root a release serves is a station list whatever the build
        # priced, so the way back does not call a one-station release a
        # chooser, and the footer link says the same thing (audit item 19,
        # 9 October 2026).
        self.assertIn(">Back to the station list</a>", html)
        self.assertIn('footnav"><a href="/">Station list</a>', html)

    def test_the_privacy_contact_is_escaped_like_every_other_string(self) -> None:
        # E8 of the 17 October 2026 audit: every other substitution on this
        # route was escaped and this one was not. The value is operator-supplied,
        # and the page's promise is that it says exactly what the build does.
        html = render_privacy("note", "", "privacy<team>&legal@example.test")
        self.assertIn("privacy&lt;team&gt;&amp;legal@example.test", html)
        self.assertNotIn("privacy<team>", html)

    def test_every_route_says_when_its_data_is_invented(self) -> None:
        # S45: an invented station or fare must not be mistakable for a real
        # one in a review, a demo or a shared screenshot, so every route states
        # the state above its content and carries it as a machine-readable
        # attribute a fixture can assert in either direction.
        index = [{"crs": "NOT", "name": "NOTTINGHAM", "slug": "nottingham", "destinations": 5}]
        routes = {
            "chooser": render_chooser(index, budget_pounds=20, synthetic=True),
            "privacy": render_privacy(
                "note", "", "a@b.test", synthetic=True
            ),
        }
        for name, page in routes.items():
            self.assertIn('<body data-synthetic="true">', page, f"{name} lost the state attribute")
            self.assertIn("data-synthetic-banner", page, f"{name} has no visible marker")
            self.assertIn(build_demo_page.SYNTHETIC_LABEL, page)
            # The marker is one of the shared components, not a route's own
            # idea of one (S39, S45).
            self.assertIn(".synthetic-banner {", page)
        for name, page in (
            ("chooser", render_chooser(index, budget_pounds=20, synthetic=False)),
            ("privacy", render_privacy("note", "", "a@b.test", synthetic=False)),
        ):
            self.assertIn('<body data-synthetic="false">', page, f"{name} lost the state attribute")
            self.assertNotIn("data-synthetic-banner", page, f"{name} claims invented data")
        # A real build's pages say so and a synthetic build's pages do too, from
        # the same build rather than from a flag per route.
        self.assertIn('<body data-synthetic="true">', self.html)
        self.assertIn("data-synthetic-banner", self.html)
