"""What a build refuses to publish: unsourced destinations, unreviewed codes,
pseudo-stations, partial metadata and the ceilings above them.

Split out of tests/test_build_demo_page.py by feature seam (F6 of the 8
October 2026 agent-efficiency audit)."""

from __future__ import annotations

import json
import tempfile
import unittest
from unittest import mock
import contextlib
import io
from pathlib import Path

import build_demo_page
from atoc_fares import LOCATION, FLOW_F, FLOW_T, FaresDb
from build_demo_page import build_payload, build_station_index
from make_synthetic_feed import _line, build_synthetic_feed
from destination_coverage import UnsourcedReport
from parse_report import ParseReport

from tests.page_harness import setUpModule, station_page, tearDownModule


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
            code = build_demo_page.main(
                [
                    "--feed", str(feed),
                    "--out", str(out),
                    "--notices", "ogl",
                    "--privacy-contact", "a@b.test",
                ]
            )
        self.assertEqual(code, 0)
        self.assertIn("RSP fares feed", station_page(out).read_text(encoding="utf-8"))

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
                [
                    "--feed", str(feed),
                    "--out", str(out),
                    "--price-source", "the 2026 RSP download",
                    "--notices", "ogl",
                    "--privacy-contact", "a@b.test",
                ]
            )
        self.assertEqual(code, 0)
        self.assertIn("the 2026 RSP download", station_page(out).read_text(encoding="utf-8"))

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
