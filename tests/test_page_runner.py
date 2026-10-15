"""The runner's own tests: the station-selection flags, what the runner passes
to the builder, what it builds or serves, and how many workers it may start.

Split out of tests/test_build_demo_page.py by feature seam (F6 of the 8
October 2026 agent-efficiency audit), so that the page-content tests are no
longer the only thing a reader of that file is looking for."""

from __future__ import annotations

import ast
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock
import contextlib
import io
from pathlib import Path
import argparse

import build_assets
import build_demo_page
import build_pool
import build_state
import build_workers
import run
from atoc_fares import FLOW_T, FaresDb
from build_workers import ONE_WORKER_FLOOR, PARENT_BYTES, RESERVED_BYTES, WORKER_BYTES, free_memory_bytes, worker_budget
from make_synthetic_feed import _line, build_synthetic_feed, build_synthetic_timetable

from tests.page_harness import setUpModule, tearDownModule


class OnlyStationsCliTest(unittest.TestCase):
    """`--only-stations`: a few stations, and still one site.

    The flag exists so a person can build two stations to read without paying
    for the other 2,710. What must not change is the contract underneath it: the
    chooser offers what was written, the release manifest names what was
    written, and a code the feed does not price is refused rather than quietly
    dropped -- because a subset that quietly drops one of the two codes you
    named is a build that lies about what it wrote.
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

    def build(self, *extra: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = build_demo_page.main(
                [
                    "--feed",
                    str(self.feed),
                    "--timetable",
                    str(self.timetable),
                    "--all-origins",
                    "--out",
                    str(self.out),
                    *extra,
                ]
            )
        return code, out.getvalue(), err.getvalue()

    def page(self, slug: str) -> str:
        return (self.out.parent / "from" / slug / "index.html").read_text(encoding="utf-8")

    def written_slugs(self) -> list[str]:
        from_dir = self.out.parent / "from"
        if not from_dir.is_dir():
            return []
        return sorted(child.name for child in from_dir.iterdir())

    def test_only_the_named_station_gets_a_page(self) -> None:
        code, said, _ = self.build("--only-stations", "GRN")
        self.assertEqual(code, 0)
        self.assertEqual(self.written_slugs(), ["grantham"])
        self.assertRegex(said, r"Building 1 of the feed's [\d,]+ priceable station\(s\): GRN")

    def test_two_named_stations_are_one_site_with_one_chooser(self) -> None:
        code, _, _ = self.build("--only-stations", "GRN,NOT")
        self.assertEqual(code, 0)
        self.assertEqual(self.written_slugs(), ["grantham", "nottingham"])
        chooser = (self.out.parent / "index.html").read_text(encoding="utf-8")
        self.assertIn("/from/grantham/", chooser)
        self.assertIn("/from/nottingham/", chooser)

    def test_the_station_list_offers_the_subset_and_nothing_else(self) -> None:
        self.build("--only-stations", "GRN")
        stations_js = (self.out.parent / build_demo_page.STATION_ASSET_NAME).read_text(
            encoding="utf-8"
        )
        self.assertIn('"name":"GRANTHAM"', stations_js)
        self.assertNotIn("NOTTINGHAM", stations_js)

    def test_the_release_manifest_names_the_subset(self) -> None:
        self.build("--only-stations", "GRN")
        manifest = json.loads(
            (self.out.parent / build_demo_page.RELEASE_MANIFEST_NAME).read_text(encoding="utf-8")
        )
        self.assertEqual(
            sorted(manifest["routes"]), ["/", "/from/grantham/", "/privacy/"]
        )

    def test_a_subset_page_is_a_full_page_not_a_summary(self) -> None:
        # The point of the flag is a page you can read: with the timetable
        # loaded it must carry what the prices-only build of the same station
        # cannot show. Asserted as a difference between the two builds rather
        # than against any wording, because the wording is the template's
        # business and this is the flag's.
        self.build("--only-stations", "GRN")
        with_times = self.page("grantham")
        second = Path(self._tmp.name) / "prices"
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = build_demo_page.main(
                [
                    "--feed",
                    str(self.feed),
                    "--all-origins",
                    "--only-stations",
                    "GRN",
                    "--out",
                    str(second / "index.html"),
                ]
            )
        self.assertEqual(code, 0)
        without_times = (second / "from" / "grantham" / "index.html").read_text(encoding="utf-8")
        # The page says so in its own payload, which is the build's answer and
        # not the template's wording: "no timetable in this build" also appears
        # in the template's shortlist fallback, so it would pass either way.
        self.assertIn('"hasJourneys":true', with_times)
        self.assertIn('"hasJourneys":false', without_times)

    def test_a_code_the_feed_does_not_price_is_refused_and_nothing_is_written(self) -> None:
        code, _, err = self.build("--only-stations", "GRN,ZZZ")
        self.assertEqual(code, 2)
        self.assertIn("ZZZ", err)
        self.assertFalse(self.out.parent.exists(), "a refused build must write nothing")

    def test_lowercase_and_spaced_codes_are_accepted(self) -> None:
        code, said, _ = self.build("--only-stations", " grn , not ")
        self.assertEqual(code, 0)
        self.assertEqual(self.written_slugs(), ["grantham", "nottingham"])
        self.assertIn("GRN, NOT", said)

    def test_no_code_at_all_is_refused_rather_than_building_nothing(self) -> None:
        code, _, err = self.build("--only-stations", " , ")
        self.assertEqual(code, 2)
        self.assertIn("no code", err)

    def test_without_all_origins_the_flag_is_refused_rather_than_ignored(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = build_demo_page.main(
                [
                    "--feed",
                    str(self.feed),
                    "--only-stations",
                    "GRN,NOT",
                    "--out",
                    str(self.out),
                ]
            )
        self.assertEqual(code, 2)
        self.assertIn("--all-origins", err.getvalue())

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

    def test_a_second_build_of_the_same_feeds_rewrites_nothing(self) -> None:
        # T3: the key is the payload with builtAt masked, so a rebuild whose
        # inputs did not move rewrites no page. The resume record makes the
        # second build skip every page; deleting the record exercises the
        # write path instead, which compares each page and still writes none.
        first = self.build()
        self.assertNotIn("pages rewritten: 0", first)
        second = self.build()
        self.assertIn("pages rewritten: 0", second)
        (self.out.parent / ".trainbudget-build.json").unlink()
        third = self.build()
        self.assertIn("pages rewritten: 0", third)
        self.assertIn("unchanged: 2", third)

    def test_a_timetabled_build_records_progress_for_a_resume(self) -> None:
        # T3: resume was the prices-only parallel mode's alone, so a
        # timetabled build that died at page 900 started again at page one.
        # The progress record is written after every page whatever the mode.
        self.build()
        self.assertTrue((self.out.parent / ".trainbudget-build.json").is_file())

    def test_a_bad_shard_share_is_refused_before_anything_builds(self) -> None:
        for spec in ("0/2", "3/2", "1/0", "half", "1/2/3"):
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = build_demo_page.main(
                    [
                        "--feed", str(self.feed),
                        "--all-origins", "--shard", spec,
                        "--out", str(self.out),
                    ]
                )
            self.assertEqual(code, 2, spec)

    def test_a_shard_needs_the_network_build_it_shares(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = build_demo_page.main(
                ["--feed", str(self.feed), "--shard", "1/2", "--out", str(self.out)]
            )
        self.assertEqual(code, 2)

    def test_shards_merge_to_the_site_a_single_build_writes(self) -> None:
        # T4: wall clock divides by the shard count, which is the only lever
        # that does. Two shares built apart merge to the same routes and the
        # same page bytes as one build over the whole list.
        shards = []
        for number in (1, 2):
            shard_out = self.out.parent / f"shard-{number}" / "index.html"
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = build_demo_page.main(
                    [
                        "--feed", str(self.feed),
                        "--timetable", str(self.timetable),
                        "--all-origins", "--shard", f"{number}/2",
                        "--out", str(shard_out),
                    ]
                )
            self.assertEqual(code, 0, buffer.getvalue())
            shards.append(shard_out.parent)
        for number, shard in enumerate(shards, 1):
            manifest = json.loads((shard / "shard.json").read_text(encoding="utf-8"))
            self.assertEqual((manifest["shard"], manifest["of"]), (number, 2))
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = build_demo_page.main(
                [
                    "--merge", *[str(shard) for shard in shards],
                    "--feed", str(self.feed),
                    "--out", str(self.out),
                ]
            )
        self.assertEqual(code, 0, buffer.getvalue())
        merged = sorted(child.name for child in (self.out.parent / "from").iterdir())
        self.assertEqual(merged, ["grantham", "nottingham"])
        whole = self.out.parent / "whole" / "index.html"
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = build_demo_page.main(
                [
                    "--feed", str(self.feed),
                    "--timetable", str(self.timetable),
                    "--all-origins",
                    "--out", str(whole),
                ]
            )
        self.assertEqual(code, 0, buffer.getvalue())
        for slug in ("grantham", "nottingham"):
            merged_page = (self.out.parent / "from" / slug / "index.html").read_text(encoding="utf-8")
            self.assertTrue(
                build_demo_page.page_is_current(
                    whole.parent / "from" / slug / "index.html", merged_page
                ),
                f"shard-built {slug} differs from the whole-list build",
            )

    def test_a_merge_refuses_shards_that_do_not_partition_the_feed(self) -> None:
        shard_out = self.out.parent / "shard-1" / "index.html"
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = build_demo_page.main(
                [
                    "--feed", str(self.feed),
                    "--all-origins", "--shard", "1/2",
                    "--out", str(shard_out),
                ]
            )
        self.assertEqual(code, 0, buffer.getvalue())
        shard = shard_out.parent
        # Twice the same share: the shares overlap rather than partition.
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = build_demo_page.main(
                ["--merge", str(shard), str(shard), "--feed", str(self.feed),
                 "--out", str(self.out)]
            )
        self.assertEqual(code, 2)
        # One share of two: the merge is gapped.
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = build_demo_page.main(
                ["--merge", str(shard), "--feed", str(self.feed), "--out", str(self.out)]
            )
        self.assertEqual(code, 2)

    def test_a_merge_refuses_shards_built_from_different_inputs(self) -> None:
        first = self.out.parent / "shard-1" / "index.html"
        second = self.out.parent / "shard-2" / "index.html"
        for out, note in ((first, None), (second, "--note")):
            flags = ["--feed", str(self.feed), "--all-origins"]
            if note is None:
                flags += ["--shard", "1/2"]
            else:
                flags += ["--shard", "2/2", note, "a different footer"]
            flags += ["--out", str(out)]
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = build_demo_page.main(flags)
            self.assertEqual(code, 0, buffer.getvalue())
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = build_demo_page.main(
                ["--merge", str(first.parent), str(second.parent),
                 "--feed", str(self.feed), "--out", str(self.out)]
            )
        self.assertEqual(code, 2)

    def test_a_changed_script_rewrites_every_page_and_keeps_the_release_whole(self) -> None:
        # A script change leaves every payload alone and renames the hashed
        # asset each page requests. A rebuild that kept pages because their
        # payload matched, or resumed past them, would leave them naming the
        # old file -- and the prune would then delete it from under them.
        self.build()
        site = self.out.parent
        renamed = "station-feedfacecafe.js"
        # Patched where the name is read: the asset name is a digest of the
        # script's own bytes, and every module that names it asks build_assets
        # for it, so one patch is the release's new name everywhere (ADR-0071).
        with mock.patch.object(
            build_assets, "station_script_asset_name", return_value=renamed
        ):
            second = self.build()
        self.assertNotIn("pages rewritten: 0", second)
        for slug in ("grantham", "nottingham"):
            page = (site / "from" / slug / "index.html").read_text(encoding="utf-8")
            self.assertIn(f"/{renamed}", page, slug)
        self.assertEqual(build_demo_page.crawl_internal_links(site), [])

    def test_a_page_the_build_left_alone_keeps_the_asset_it_names(self) -> None:
        # The build names an earlier build's page rather than deleting it, so
        # the prune must not delete the stylesheet that page still requests.
        self.build()
        site = self.out.parent
        kept = site / "station-0123456789ab.css"
        kept.write_text(":root {}", encoding="utf-8")
        orphan = site / "station-ba9876543210.css"
        orphan.write_text(":root {}", encoding="utf-8")
        earlier = site / "from" / "sleepy" / "index.html"
        earlier.parent.mkdir(parents=True)
        earlier.write_text(
            '<link rel="stylesheet" href="/station-0123456789ab.css">', encoding="utf-8"
        )
        (site / ".trainbudget-build.json").unlink()
        self.build()
        self.assertTrue(kept.is_file(), "a page in the folder still names it")
        self.assertFalse(orphan.exists(), "nothing names it")

    def _shards(self) -> list[Path]:
        shards = []
        for number in (1, 2):
            shard_out = self.out.parent / f"shard-{number}" / "index.html"
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = build_demo_page.main(
                    [
                        "--feed", str(self.feed),
                        "--all-origins", "--shard", f"{number}/2",
                        "--out", str(shard_out),
                    ]
                )
            self.assertEqual(code, 0, buffer.getvalue())
            shards.append(shard_out.parent)
        return shards

    def _merge(self, shards: list[Path]) -> tuple[int, str]:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            code = build_demo_page.main(
                ["--merge", *[str(shard) for shard in shards],
                 "--feed", str(self.feed), "--out", str(self.out)]
            )
        return code, buffer.getvalue()

    def test_a_merge_refuses_shards_built_by_other_code(self) -> None:
        # The merge writes the assets of the code it runs; shards from another
        # revision name assets it never writes.
        shards = self._shards()
        # `build_pool` is where the merge reads this name, so patching the
        # module that defines it would leave the merge comparing the real
        # fingerprint against itself and the test passing for no reason.
        with mock.patch.object(build_pool, "source_fingerprint", return_value="0" * 16):
            code, said = self._merge(shards)
        self.assertEqual(code, 2)
        self.assertIn("different revision", said)
        self.assertFalse((self.out.parent / "from").exists(), "a refused merge copies nothing")

    def test_a_merge_refuses_a_folder_that_already_holds_pages(self) -> None:
        shards = self._shards()
        earlier = self.out.parent / "from" / "sleepy"
        earlier.mkdir(parents=True)
        (earlier / "index.html").write_text("from an earlier build", encoding="utf-8")
        code, said = self._merge(shards)
        self.assertEqual(code, 2)
        self.assertIn("already holds station pages", said)
        self.assertNotIn("overlap", said)
        self.assertEqual(
            sorted(child.name for child in (self.out.parent / "from").iterdir()), ["sleepy"]
        )

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
        # proof they agree is a byte-diff of the pages each mode writes. The
        # pages are deleted between the builds so the pool really writes: a
        # rebuild over present pages would skip the write after proving the
        # bytes match, which proves the comparison rather than the writer.
        self.build()
        single = (self.out.parent / "from" / "grantham" / "index.html").read_text(encoding="utf-8")
        shutil.rmtree(self.out.parent / "from")
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
            # The empty-build sentence is drawn by the route's own code, which
            # travels in the shared asset the chooser names rather than in the
            # page, so this reads the file the build wrote beside it.
            match = re.search(r'<script src="([^"]*chooser-[0-9a-f]+\.js)"', chooser)
            self.assertIsNotNone(match, "the chooser names no shared script")
            script = (out.parent / match.group(1).rsplit("/", 1)[-1]).read_text(encoding="utf-8")
            self.assertIn("There is nothing here yet", script)

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

class RunnerPassthroughTest(unittest.TestCase):
    """What `python run.py` can reach on the builder.

    The runner assembles a fixed argument list, so a flag the builder
    understands is a flag the double-click path cannot pass. That is how the
    licence notice and the privacy contact became unreachable from the entry
    point a first-time user actually takes: a real feed could only be built by
    calling the builder by hand. These assert the argument list, because that
    is the whole of the passthrough -- the build itself is covered elsewhere.
    """

    def _command(self, **overrides) -> list[str]:
        captured: list[str] = []

        class _Result:
            returncode = 0

        def fake_run(cmd, cwd=None):
            captured.extend(cmd)
            return _Result()

        values = {
            "feed": Path("feeds/fares"),
            "origin": "GRA",
            "timetable": None,
            "with_single_timetable": False,
            "date": None,
            "all_origins": False,
            "base_path": None,
            "notices": None,
            "privacy_contact": None,
        }
        values.update(overrides)
        args = argparse.Namespace(**values)
        with mock.patch.object(run, "ROOT", Path(__file__).parent.parent), mock.patch.object(
            run, "_feed_exists", return_value=True
        ), mock.patch.object(run.subprocess, "run", fake_run), contextlib.redirect_stdout(
            io.StringIO()
        ):
            run.build(args)
        return captured

    def test_the_notice_and_contact_flags_reach_the_builder(self) -> None:
        command = self._command(
            notices="rdg,ogl,accuracy", privacy_contact="me@example.org"
        )
        self.assertIn("--notices", command)
        self.assertEqual(command[command.index("--notices") + 1], "rdg,ogl,accuracy")
        self.assertEqual(command[command.index("--privacy-contact") + 1], "me@example.org")

    def test_neither_flag_is_passed_when_neither_was_given(self) -> None:
        # Passing an empty --notices would satisfy the builder's "is it
        # present" test with nothing in it, so an absent flag has to stay
        # absent rather than become an empty one. This is the synthetic feed:
        # nothing here is a public build, and crediting NRE for prices NRE did
        # not supply would be false attribution rather than a missing one.
        command = self._command(feed=run.ROOT / "_demo_feed")
        self.assertNotIn("--notices", command)
        self.assertNotIn("--privacy-contact", command)

    def test_a_real_feed_carries_every_notice_without_being_asked(self) -> None:
        # `python run.py` with no arguments swaps the demo feed for the
        # downloaded one the moment it exists, so the default path *is* a public
        # build. It used to be refused by the builder for carrying no notice,
        # which made the documented way to run the app fail as soon as the feeds
        # were downloaded. The set comes from the builder's own table, so a
        # notice added there cannot be missing here.
        command = self._command()
        self.assertIn("--notices", command)
        carried = command[command.index("--notices") + 1].split(",")
        self.assertEqual(sorted(carried), sorted(build_demo_page.NOTICES))
        self.assertEqual(len(carried), len(set(carried)))

    def test_a_narrower_notice_set_is_passed_verbatim(self) -> None:
        # The direction that is allowed is narrowing. A person who knows why
        # their release owes less can say so; nothing here widens a set past
        # what the builder offers.
        command = self._command(notices="rdg,ogl")
        self.assertEqual(command[command.index("--notices") + 1], "rdg,ogl")

    def test_a_real_feed_builds_through_the_runner_with_only_the_notice(self) -> None:
        # The contact now defaults in the builder, so the notice is the only
        # thing a real-feed build needs the runner to carry.
        self.assertIn("--notices", self._command(notices="rdg"))

    def test_an_explicitly_empty_notice_set_is_not_replaced_by_the_default(self) -> None:
        # The default is for a flag that was never passed. An empty one is a
        # person asking for no notice, and the honest answer is the builder's
        # refusal -- not this line handing over the set they just declined.
        self.assertNotIn("--notices", self._command(notices=""))


    def test_a_whole_network_run_asks_the_builder_for_what_this_machine_can_hold(self) -> None:
        # Left at the builder's default of one worker, the 2,712-page set
        # takes most of a working day: each origin's page is independent and
        # the work is CPU-bound, so one worker leaves every other core idle.
        # Cores were the wrong ceiling -- eight workers on this machine die
        # with a MemoryError having written no pages -- so the count is the
        # measured budget, and this holds the runner to passing it through
        # rather than recomputing it.
        command = self._command(all_origins=True)
        self.assertIn("--workers", command)
        workers = int(command[command.index("--workers") + 1])
        self.assertEqual(workers, worker_budget())
        self.assertGreaterEqual(workers, 1)
        self.assertLessEqual(workers, build_workers.MAX_WORKERS)
        # A single-origin run has one page to build, so a worker count says
        # nothing there and passing one would only misreport the shape of the
        # work.
        self.assertNotIn("--workers", self._command(all_origins=False))

    def test_a_relative_demo_feed_path_is_still_synthetic(self) -> None:
        # The same folder arrives as "_demo_feed" on the command line and as an
        # absolute path from the default. Comparing the two as strings would let
        # the relative one through as a real feed, and every generated price
        # would be credited to NRE.
        command = self._command(feed=Path("_demo_feed"))
        self.assertNotIn("--notices", command)

class RunnerBuildOrServeTest(unittest.TestCase):
    """Which of the two jobs the runner does on a given run.

    The decision is the point. A runner that rebuilds on every start cannot
    answer "is this the build I made?", and these tests are about that answer
    being knowable rather than about the build itself.
    """

    def run_main(self, *flags, site_exists=True, stale=False):
        served = []

        class FakeServer:
            allow_reuse_address = True

            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def serve_forever(self):
                served.append(1)

        # The flags are the tokens a reader would type, because the decision
        # under test belongs to run.py and a dict would rewrite them.
        argv = ["run.py"] + list(flags)
        # The decision turns on whether _site/ is there, so the two states have
        # to be real directories rather than a flag the runner cannot see.
        # Both are temporary: the repository's own _site/ is a local build
        # that a clean checkout -- CI's -- does not have, so pointing at it
        # made "a site exists" false there and every serve case a build case.
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        if site_exists:
            site = root / "_site"
            site.mkdir()
        else:
            site = root / "never-built"
        builder = mock.Mock(return_value=0)
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(sys, "argv", argv))
            stack.enter_context(mock.patch.object(run, "SITE", site))
            stack.enter_context(mock.patch.object(run.socketserver, "ThreadingTCPServer", FakeServer))
            stack.enter_context(mock.patch.object(run, "webbrowser", mock.Mock()))
            stack.enter_context(mock.patch.object(run.threading, "Timer", mock.Mock()))
            stack.enter_context(mock.patch.object(run, "build", builder))
            # The freshness check reads this machine's file times, which
            # are not what is under test; the decision is.
            stack.enter_context(
                mock.patch.object(run, "sources_are_newer", lambda: stale)
            )
            stack.enter_context(mock.patch.object(run.os, "chdir", mock.Mock()))
            out = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
            code = run.main()
        # The builder mock, not its call count: whether the runner decided to
        # build is in how many times it was called, and what it decided to
        # build is in the flags it was handed.
        return code, out.getvalue(), builder, served

    def test_a_clean_checkout_builds_because_there_is_nothing_to_serve(self) -> None:
        _, _, builder, _ = self.run_main("--no-build", site_exists=True)
        self.assertEqual(builder.call_count, 0)
        _, _, builder, served = self.run_main(site_exists=False)
        self.assertEqual(builder.call_count, 1)
        self.assertEqual(len(served), 1)

    def test_a_second_run_serves_what_the_first_one_wrote(self) -> None:
        # --origin is the fast single-station build, and it is the one a
        # second run of it serves without rebuilding.
        _, said, builder, served = self.run_main("--origin", "GRA", site_exists=True)
        self.assertEqual(builder.call_count, 0)
        self.assertEqual(len(served), 1)
        self.assertIn("without rebuilding", said)

    def test_the_default_is_the_fast_page_not_the_network(self) -> None:
        # T7: the double-click path set --all-origins itself, which made a
        # first run a whole-network batch job -- hours on an 8 GB machine --
        # so it never finished. The default is the fast single-origin page
        # again, and the network is the named job behind --all-origins with
        # its acknowledgement flag.
        _, _, builder, served = self.run_main(site_exists=False)
        self.assertEqual(builder.call_count, 1)
        self.assertEqual(len(served), 1)
        args = builder.call_args[0][0]
        self.assertFalse(args.all_origins)
        self.assertIsNone(args.origin)

    def test_the_network_build_names_itself_as_the_slow_job(self) -> None:
        # --all-origins without the acknowledgement is refused before it
        # starts, with the measured cost named, rather than after it has
        # finished.
        code, _, builder, served = self.run_main(
            "--all-origins", site_exists=False
        )
        self.assertEqual(code, 2)
        self.assertEqual(builder.call_count, 0)
        self.assertEqual(served, [])
        code, _, builder, served = self.run_main(
            "--all-origins", "--i-know-this-is-slow", site_exists=False
        )
        self.assertEqual(code, 0)
        self.assertEqual(builder.call_count, 1)
        self.assertTrue(builder.call_args[0][0].all_origins)

    def test_a_build_older_than_the_sources_is_not_served(self) -> None:
        # Nine hours of committed work, a double-clicked runner, and a page
        # from before it: nothing on the page says so. The runner rebuilds
        # when what it would serve is out of date, and names the reason.
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            manifest = site / run.RELEASE_MANIFEST_NAME
            manifest.write_text("{}", encoding="utf-8")
            os.utime(manifest, (1000, 1000))
            with mock.patch.object(run, "SITE", site):
                self.assertTrue(run.sources_are_newer())
            os.utime(manifest, (time.time() + 60, time.time() + 60))
            with mock.patch.object(run, "SITE", site):
                self.assertFalse(run.sources_are_newer())
        # A build with no manifest answers no: an unreadable answer must
        # never be the one that starts an hour-long build.
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(run, "SITE", Path(tmp)):
                self.assertFalse(run.sources_are_newer())

    def test_every_file_the_build_reads_is_a_reason_to_rebuild(self) -> None:
        # The runner kept its own copy of the build's inputs, and the copy had
        # drifted from the build's: three modules every build imports --
        # atoc_fares_loader, atoc_knowledgebase and destination_coverage -- were
        # named by neither list, so a fix to one of them left this command
        # serving the pages from before it. The runner asks the build now, and
        # every name on the build's list is tried here: a name added to the
        # build without the runner reading it fails this.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site = root / "_site"
            site.mkdir()
            manifest = site / run.RELEASE_MANIFEST_NAME
            manifest.write_text("{}", encoding="utf-8")
            os.utime(manifest, (1000, 1000))
            sources = []
            for name in build_demo_page.SOURCE_FILES:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")
                os.utime(path, (2000, 2000))
                sources.append(path)
            with mock.patch.object(run, "ROOT", root), mock.patch.object(run, "SITE", site):
                self.assertTrue(run.sources_are_newer())
                # One file at a time, the rest older than the manifest: the
                # answer has to be that file's mtime and not the list's length.
                for path in sources:
                    for other in sources:
                        stamp = 2000 if other is path else 500
                        os.utime(other, (stamp, stamp))
                    self.assertTrue(
                        run.sources_are_newer(), f"{path.name} does not mark the site stale"
                    )
                for path in sources:
                    os.utime(path, (500, 500))
                self.assertFalse(run.sources_are_newer())
        self.assertIn("atoc_knowledgebase.py", build_demo_page.SOURCE_FILES)

    def test_a_build_the_sources_have_moved_past_is_rebuilt(self) -> None:
        # Nine hours of committed work, a double-clicked runner and a page
        # from before it, with nothing on the page saying so. The runner
        # rebuilds when what it would serve is out of date, and says why.
        _, said, builder, served = self.run_main(
            "--origin", "GRA", site_exists=True, stale=True
        )
        self.assertEqual(builder.call_count, 1)
        self.assertEqual(len(served), 1)
        self.assertIn("newer than _site/", said)

    def test_rebuild_builds_even_when_a_site_is_already_there(self) -> None:
        _, _, builder, _ = self.run_main("--rebuild", site_exists=True)
        self.assertEqual(builder.call_count, 1)

    def test_no_build_refuses_rather_than_building_what_it_was_told_not_to(self) -> None:
        code, _, builder, served = self.run_main("--no-build", site_exists=False)
        self.assertEqual(code, 1)
        self.assertEqual(builder.call_count, 0)
        self.assertEqual(served, [])

class WorkerBudgetTest(unittest.TestCase):
    """How many build workers this machine can hold.

    `min(8, cpu_count())` was a core count wearing a memory claim. On a
    twelve-core machine with 15.8 GB it asked for eight, every worker was
    handed the whole national timetable, and the build died with a
    MemoryError in the pool initialiser after five minutes having written no
    pages -- reproducibly, twice. These hold the budget to the answers that
    matter rather than to the arithmetic behind them.
    """

    GB = 10 ** 9

    def test_a_machine_with_room_gets_the_measured_ceiling(self) -> None:
        # Twelve cores and plenty of memory is the case the ceiling exists
        # for: it is the machine the old core count got wrong.
        self.assertEqual(worker_budget(cores=12, free_bytes=16 * self.GB), 4)

    def test_the_ceiling_is_not_the_core_count(self) -> None:
        # The whole point: cores are not the question. Sixty-four cores with
        # room to spare still gets four, because four is the largest count
        # measured to finish a whole-network build.
        self.assertEqual(worker_budget(cores=64, free_bytes=64 * self.GB), 4)
        self.assertLess(worker_budget(cores=64, free_bytes=64 * self.GB), 64)

    def test_a_machine_without_room_gets_one_worker_and_still_builds(self) -> None:
        # Never zero. A build that cannot have a pool still builds, one page
        # at a time; refusing to build would be a worse answer than a slow one.
        for free in (0, 2 * self.GB, 6 * self.GB):
            with self.subTest(free=free):
                self.assertEqual(worker_budget(cores=12, free_bytes=free), 1)

    def test_the_floor_is_the_larger_phase_and_not_the_sum_of_both(self) -> None:
        # The parent loads both feeds and prices every origin; the workers then
        # hold one timetable each. `build_demo_page.py` releases the parent's
        # databases before the pool starts, so the two phases are sequential and
        # the machine needs room for the larger, not for both at once. The sum
        # was the right formula while the parent held its databases for the
        # whole build, and it is 900 MB too high now.
        self.assertEqual(
            ONE_WORKER_FLOOR,
            max(PARENT_BYTES, WORKER_BYTES) + RESERVED_BYTES,
        )
        self.assertLess(ONE_WORKER_FLOOR,
                        PARENT_BYTES + WORKER_BYTES + RESERVED_BYTES)

    def test_the_floor_still_covers_the_both_phases_case(self) -> None:
        # The floor is a floor, not a target: a machine with less free than this
        # cannot run the parent and the workers at all, so the build drops to
        # one. Checked against a whole number of gigabytes because the reserve
        # and the worker cost are both rounded up from a measurement.
        self.assertLessEqual(ONE_WORKER_FLOOR, 7 * 10 ** 9)
        self.assertGreater(ONE_WORKER_FLOOR, 6 * 10 ** 9)

    def test_the_core_count_still_bounds_it_from_below(self) -> None:
        # A two-core runner cannot use four workers whatever it has free.
        self.assertEqual(worker_budget(cores=2, free_bytes=16 * self.GB), 2)
        self.assertEqual(worker_budget(cores=1, free_bytes=16 * self.GB), 1)

    def test_a_platform_that_will_not_say_falls_back_on_the_ceiling(self) -> None:
        # None is not zero. A machine that will not report its memory gets the
        # measured count rather than the one-worker answer a zero would give.
        with mock.patch.object(build_workers, "free_memory_bytes", lambda: None):
            self.assertEqual(worker_budget(cores=12), 4)
        with mock.patch.object(build_workers, "free_memory_bytes", lambda: 0):
            self.assertEqual(worker_budget(cores=12), 1)

    def test_passing_none_means_ask_the_machine_not_trust_the_ceiling(self) -> None:
        # free_bytes=None is "I have not read it yet", which is not the same
        # answer as "the machine could not tell me". Conflating them would let
        # a caller who meant one get the other.
        with mock.patch.object(build_workers, "free_memory_bytes",
                               return_value=4 * self.GB),                 mock.patch.object(build_workers.os, "cpu_count", return_value=12):
            self.assertEqual(worker_budget(cores=12, free_bytes=None), 1)

    def test_the_budget_reads_the_machine_when_it_is_not_told(self) -> None:
        # The no-argument path is the one the runner and the workflow use, so
        # it has to consult the platform rather than answer from a constant.
        with mock.patch.object(build_workers, "free_memory_bytes",
                               return_value=16 * self.GB):
            with mock.patch.object(build_workers.os, "cpu_count", return_value=12):
                self.assertEqual(worker_budget(), 4)

    def test_free_memory_is_a_number_or_nothing_at_all(self) -> None:
        free = free_memory_bytes()
        self.assertTrue(free is None or (isinstance(free, int) and free > 0))

    def test_the_figures_the_budget_is_built_from_are_the_measured_ones(self) -> None:
        # Both constants are measurements now rather than recollections, so this
        # pins each in both directions. One below the figure it came from hands
        # out workers the machine cannot hold -- which is how this constant was
        # wrong by a factor of 2.4 for as long as it stood at 900 MB. One well
        # above refuses builds that would have finished.
        #
        # A little headroom is expected, because both are rounded up: the parent
        # is 4,017 MB measured here against 4,110 recorded. Ten per cent is
        # rounding up and not inventing, and it is what makes this catch a
        # constant doubled by an edit that was not looking for it.
        mb = 10 ** 6
        self.assertGreaterEqual(PARENT_BYTES, 4_110 * mb)
        self.assertLess(PARENT_BYTES, 4_110 * 1.1 * mb)
        self.assertGreaterEqual(WORKER_BYTES, 2_188 * mb)
        self.assertLess(WORKER_BYTES, 2_188 * 1.1 * mb)

    def test_four_workers_fitted_and_eight_did_not(self) -> None:
        # The reconciliation ADR-0057 records, held as arithmetic rather than
        # prose. A worker measures 2,188 MB through `init_worker` and
        # `build_page_job`. The parent is not added: it releases its databases
        # before the pool starts, so the workers are the whole of the tree's
        # demand while they run.
        #
        # Four workers is 8,752 MB against this machine's 15.8 GB, which is why
        # the four-worker build in the committed log finished. Eight is
        # 17,504 MB, which is why the eight-worker log holds a MemoryError
        # rather than a page. Note that four workers no longer fit in the 8 GB
        # the old records describe: that observation predates the corrected
        # worker figure and cannot be reproduced on today's feed.
        worker = 2_188
        machine = 15_800
        self.assertLess(4 * worker, machine)
        self.assertGreater(8 * worker, machine)
        self.assertGreater(4 * WORKER_BYTES, 8 * 10 ** 9)

    @staticmethod
    def _worker_branch() -> tuple[ast.AST, ast.AST]:
        """The two halves of the `if workers == 1` branch in the builder.

        Returns (in-process body, pool body). Found through the AST rather than
        by slicing the text, because the text of a 3,000-line module offers far
        too many places to start from and none of them are the right one.
        """
        # `build_pool` is where the builder's phases live since the split
        # (ADR-0071); the command above them is what build_demo_page.py holds.
        tree = ast.parse((pathlib.Path(__file__).resolve().parent.parent
                          / "build_pool.py").read_text(encoding="utf-8"))
        found = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) in ("workers == 1", "max(1, args.workers) == 1")
        ]
        # Two sites assert on `workers`: the all-origins branch, which renders
        # in-process or in the pool, and the fast path's own default. Only the
        # first has a pool in its `orelse`.
        with_pool = [node for node in found if node.orelse]
        assert len(with_pool) == 1, f"expected one worker-count branch, got {len(with_pool)}"
        branch = with_pool[0]
        return branch.body, branch.orelse

    @staticmethod
    def _deleted_names(body: list[ast.stmt]) -> set[str]:
        names: set[str] = set()
        for node in ast.walk(ast.Module(body=list(body), type_ignores=[])):
            if isinstance(node, ast.Delete):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
        return names

    def test_the_pool_branch_releases_the_databases_the_workers_do_not_need(self) -> None:
        # The budget divides free memory by a worker's cost and does not add the
        # parent's, because `build_demo_page.py` drops `fares` and `timetable`
        # before the pool starts. That premise lives in one place in the source,
        # and if the release is moved, narrowed or deleted the division starts
        # overcounting, so a machine gets more workers than it can hold. So the
        # premise is pinned where it is written.
        _in_process, pool = self._worker_branch()
        released = self._deleted_names(pool)
        self.assertIn("fares", released)
        self.assertIn("timetable", released)

    def test_the_in_process_branch_restores_a_slice_and_releases_the_feed(self) -> None:
        # The other half, and the one a careless reader of the test above would
        # break. With one worker the build renders in this process, and what it
        # renders from is the worker state: the per-origin slice the shared
        # helper restores, not the national feed. That feed was held through the
        # whole render phase until the indexes were written for this path too,
        # and holding 2.1 GB of fares beside the national timetable is what
        # paged a two-station build on a machine whose own floor is 6.4 GB free.
        # No number in this file can catch that; only the placement can.
        in_process, _pool = self._worker_branch()
        # Structurally rather than by text: `ast.unparse` normalises quotes, so
        # a test written against the source's own spelling fails on `"` vs `'`
        # and says nothing about the code.
        handed = {
            (node.targets[0].slice.value, node.value.id)
            for node in ast.walk(ast.Module(body=list(in_process), type_ignores=[]))
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Subscript)
            and isinstance(node.targets[0].value, ast.Name)
            and node.targets[0].value.id == "_WORKER"
            and isinstance(node.targets[0].slice, ast.Constant)
            and isinstance(node.value, ast.Name)
        }
        self.assertIn(("timetable", "timetable"), handed)
        self.assertNotIn(("fares", "fares"), handed)
        self.assertIn("fares", self._deleted_names(in_process))
        called = {
            node.func.id
            for node in ast.walk(ast.Module(body=list(in_process), type_ignores=[]))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertIn("restore_worker_fares", called)

    def test_a_process_with_the_indexes_takes_a_slice_and_one_without_keeps_the_feed(self) -> None:
        # The one decision both ways into a page now make, held as behaviour
        # rather than as placement: with the shared metadata and the index
        # directory, a process holds no national fare data and lets the page
        # function restore its own slice. Without them it keeps the feed it was
        # handed, and does not pay for a second parse to get one, because a
        # working page beats a released one and two copies of the feed is the
        # one answer that is worse than either.
        shared = {
            "fare_common_cache": str(pathlib.Path(tempfile.gettempdir()) / "common.pickle"),
            "fare_index_dir": str(pathlib.Path(tempfile.gettempdir()) / "origins"),
        }
        try:
            with mock.patch.object(
                build_workers.FaresDb, "load_fare_common", return_value="the shared metadata"
            ) as loader:
                build_workers.restore_worker_fares("feeds/fares", shared, loaded="the whole feed")
            self.assertIsNone(build_workers._WORKER["fares"])
            self.assertEqual(build_workers._WORKER["fares_common"], "the shared metadata")
            loader.assert_called_once_with(shared["fare_common_cache"])
            build_workers._WORKER.clear()
            build_workers.restore_worker_fares("feeds/fares", {}, loaded="the whole feed")
            self.assertEqual(build_workers._WORKER["fares"], "the whole feed")
        finally:
            build_workers._WORKER.clear()

class RunnerWorkerCountTest(unittest.TestCase):
    """That `python run.py` asks the budget rather than counting cores.

    It carries its own harness rather than borrowing the passthrough test's,
    because that one redirects stdout internally and the notice this is about
    is printed. A harness that swallowed the line under test could not assert
    on it.
    """

    GB = 10 ** 9

    def setUp(self) -> None:
        self.saved = (run.worker_budget, run.free_memory_bytes)
        self.addCleanup(setattr, run, "worker_budget", self.saved[0])
        self.addCleanup(setattr, run, "free_memory_bytes", self.saved[1])

    def _build(self, workers: int, free: int | None) -> tuple[list[str], str]:
        run.worker_budget = lambda free_bytes=None: workers
        run.free_memory_bytes = lambda: free

        captured: list[str] = []

        class _Result:
            returncode = 0

        def fake_run(cmd, cwd=None):
            captured.extend(cmd)
            return _Result()

        args = argparse.Namespace(
            feed=Path("feeds/fares"), origin=None, timetable=None,
            with_single_timetable=False, date="2026-10-02", all_origins=True,
            base_path=None, notices=None, privacy_contact=None,
        )
        out = io.StringIO()
        with mock.patch.object(run, "ROOT", Path(__file__).parent.parent),                 mock.patch.object(run, "_feed_exists", return_value=True),                 mock.patch.object(run.subprocess, "run", fake_run),                 contextlib.redirect_stdout(out):
            run.build(args)
        return captured, out.getvalue()

    def test_the_runner_passes_the_budget_to_the_builder(self) -> None:
        command, _ = self._build(3, 16 * self.GB)
        self.assertIn("--all-origins", command)
        self.assertEqual(command[command.index("--workers") + 1], "3")

    def test_the_runner_says_which_count_it_chose_and_what_it_had_to_work_with(self) -> None:
        # "1 worker" on its own does not say whether that was the ceiling or a
        # shortage of memory, and those are different problems for whoever has
        # to wait for the build.
        _, said = self._build(1, 4 * self.GB)
        self.assertIn("1 worker(s)", said)
        self.assertIn("4.0 GB free", said)

    def test_a_platform_that_cannot_report_memory_is_not_reported_as_having_none(self) -> None:
        _, said = self._build(4, None)
        self.assertIn("4 worker(s)", said)
        self.assertNotIn("GB free", said)

    def test_the_runner_no_longer_asks_for_the_core_count(self) -> None:
        source = Path(run.__file__).read_text(encoding="utf-8")
        self.assertNotIn("min(8, os.cpu_count()", source)
        self.assertIn("worker_budget(", source)

class SingleOriginRunnerTidyTest(unittest.TestCase):
    """What `python run.py` leaves behind after a single-origin build.

    C31: the runner used to delete the whole /from/ tree, which a single-origin
    build had just written its one station page into, so the chooser it served
    linked to a 404. These drive the real builder and then the real tidying
    step, because the bug lived in the seam between them and neither half
    reproduces it alone.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.root = Path(self.tmp)
        self.feed = self.root / "feed"
        build_synthetic_feed(self.feed, include_restrictions=True, include_third_origin=True)
        self.site = self.root / "site"

    def _build(self, *extra: str) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            code = build_demo_page.main(
                ["--feed", str(self.feed), "--out", str(self.site / "index.html"), "--origin", "GRN", *extra]
            )
        self.assertEqual(code, 0)

    def _tidy(self) -> list[str]:
        with mock.patch.object(run, "SITE", self.site):
            with contextlib.redirect_stdout(io.StringIO()):
                return run.remove_unwritten_station_pages()

    def _station_folders(self) -> list[str]:
        from_dir = self.site / "from"
        return sorted(child.name for child in from_dir.iterdir()) if from_dir.is_dir() else []

    def test_the_page_the_build_just_wrote_survives(self) -> None:
        # A single-origin build writes the chooser, privacy and the one station
        # page. Tidying must not remove that page, which is the whole defect.
        self._build()
        self.assertEqual(self._station_folders(), ["grantham"])
        self.assertEqual(self._tidy(), [])
        self.assertTrue((self.site / "from" / "grantham" / "index.html").is_file())

    def test_a_previous_all_origins_tree_is_removed(self) -> None:
        # The case the old step was written for: leftovers from a wider build,
        # which the chooser this build wrote does not offer.
        self._build("--all-origins")
        self.assertEqual(self._station_folders(), ["grantham", "lincoln", "nottingham"])
        self._build()
        self.assertEqual(self._tidy(), ["lincoln", "nottingham"])
        self.assertEqual(self._station_folders(), ["grantham"])

    def test_a_base_path_build_keeps_its_own_page(self) -> None:
        # A subpath build writes "/app/from/grantham/", not "/from/grantham/".
        # Reading the route without the prefix matched nothing and deleted the
        # page, which is C31 again for every subpath deployment.
        self._build("--base-path", "app")
        manifest = json.loads(
            (self.site / build_demo_page.RELEASE_MANIFEST_NAME).read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["basePath"], "/app")
        self.assertIn("/app/from/grantham/", manifest["routes"])
        self.assertEqual(self._tidy(), [])
        self.assertTrue((self.site / "from" / "grantham" / "index.html").is_file())

    def test_nothing_is_deleted_when_the_manifest_is_absent_or_unreadable(self) -> None:
        # Deleting generated pages on a guess is the worse failure: the worst
        # case for a missing manifest is a stale folder left on disk, which the
        # build already names in its own output.
        #
        # The last two cases are the sharp ones. A manifest whose "routes" is a
        # string iterates character by character, and one whose top level is a
        # list has no "routes" at all; either way the keep-set comes out empty,
        # and an empty keep-set deletes the page the build just wrote. That is
        # the C31 defect arriving by a different road, so it is refused.
        for content in (None, "{not json", '"/from/grantham/"', "[1, 2, 3]", '{"routes": "/from/grantham/"}'):
            self._build("--all-origins")
            manifest = self.site / build_demo_page.RELEASE_MANIFEST_NAME
            if content is None:
                manifest.unlink()
            else:
                manifest.write_text(content, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self._tidy(), [], f"manifest {content!r}")
            self.assertEqual(self._station_folders(), ["grantham", "lincoln", "nottingham"])

    def test_a_build_that_priced_nothing_removes_every_station_folder(self) -> None:
        # No station route in the manifest means no station page is part of
        # this release, so none may be left behind to be reached by URL.
        self._build("--all-origins")
        (self.site / build_demo_page.RELEASE_MANIFEST_NAME).write_text(
            json.dumps({"basePath": "", "routes": ["/", "/privacy/"]}), encoding="utf-8"
        )
        self.assertEqual(self._tidy(), ["grantham", "lincoln", "nottingham"])
        self.assertEqual(self._station_folders(), [])
