"""What a build keeps between runs and what it prunes: the parsed-fares and
timetable caches, their prune rules, the timetable index a build cuts, and
the return leg a feed asks for.

Split out of tests/test_build_demo_page.py by feature seam (F6 of the 8
October 2026 agent-efficiency audit)."""

from __future__ import annotations

import ast
import json
import os
import pathlib
import re
import shutil
import tempfile
import unittest
from unittest import mock
import contextlib
import io
import urllib.error
from datetime import date
from pathlib import Path

import atoc_fares_loader
import build_demo_page
import build_state
from atoc_fares import FaresDb
from atoc_timetable import TimetableDb
from make_synthetic_feed import build_synthetic_feed, build_synthetic_timetable

from tests.page_harness import embedded_payload, setUpModule, station_page, tearDownModule


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
            with mock.patch.object(build_state, "CACHE_DIR", root):
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
            with mock.patch.object(build_state, "CACHE_DIR", root):
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

    def test_the_timetable_cache_key_cannot_serve_a_replaced_download(self) -> None:
        # The timetable cache was keyed on names, sizes and mtimes, which cannot
        # tell two downloads apart when a copy preserves timestamps or an archive
        # is extracted with the dates stored in it. A stale hit puts one
        # download's services on a page built from another: a reader is shown a
        # timetable that is not the one in force.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = build_synthetic_timetable(root / "timetable")
            before = build_demo_page.timetable_cache_path(feed, "GRN", {"LCN", "NOT"})
            target = next(item for item in sorted(feed.iterdir()) if item.is_file())
            original = target.read_text(encoding="utf-8")
            stamp = target.stat().st_mtime_ns
            target.write_text(original.replace("NOT", "NT1", 1), encoding="utf-8")
            os.utime(target, ns=(stamp, stamp))
            self.assertEqual(len(target.read_text(encoding="utf-8")), len(original))
            after = build_demo_page.timetable_cache_path(feed, "GRN", {"LCN", "NOT"})
        self.assertNotEqual(before, after, "different bytes are a different cache")
        # The focus is part of the name too: a cache for one station's set of
        # destinations is not an answer for another's.
        self.assertNotEqual(
            build_demo_page.timetable_cache_path(feed, "GRN", {"LCN", "NOT"}),
            build_demo_page.timetable_cache_path(feed, "GRN", {"LCN"}),
        )
        self.assertEqual(
            build_demo_page.timetable_cache_path(feed, "GRN", {"NOT", "LCN"}),
            build_demo_page.timetable_cache_path(feed, "GRN", {"LCN", "NOT"}),
            "the focus set is a set, so its order is not part of the key",
        )

    def test_the_timetable_cache_key_covers_the_code_that_reads_the_feed(self) -> None:
        # The key is the feed's bytes, the focus, and `source_fingerprint` --
        # and the fingerprint covers atoc_timetable.py, so a change to how the
        # feed is *read* invalidates the cache even when the bytes are the same.
        # That is the case a fingerprint over the feed alone cannot catch, and
        # it is not hypothetical: fixing how `0000` is read (that record is the
        # CIF's absent marker, not midnight) changes no byte of the download and
        # changes every calling point the cache holds. A build that kept the
        # old pickle would serve the old timetables and say nothing.
        self.assertIn("atoc_timetable.py", build_demo_page.SOURCE_FILES)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = build_synthetic_timetable(root / "timetable")
            before = build_demo_page.timetable_cache_path(feed, "GRN", {"LCN", "NOT"})
            # Every source file the fingerprint hashes is read off disk and
            # written back, so a one-byte change anywhere in the parser shows up
            # in the cache name. Nothing is left edited: a suite that dirties
            # the tree it runs in is a suite that cannot be trusted to report
            # this at all.
            touched = []
            try:
                for name in build_demo_page.SOURCE_FILES:
                    source = pathlib.Path(build_demo_page.__file__).parent / name
                    original = source.read_bytes()
                    touched.append((source, original))
                    source.write_bytes(original + b"\n")
                build_demo_page.source_fingerprint.cache_clear()
                after = build_demo_page.timetable_cache_path(feed, "GRN", {"LCN", "NOT"})
            finally:
                for source, original in touched:
                    source.write_bytes(original)
                build_demo_page.source_fingerprint.cache_clear()
        self.assertNotEqual(
            before, after,
            "a change to any source file the parser reads is a different cache",
        )

    def test_the_source_list_covers_every_module_the_build_imports(self) -> None:
        # The list was a literal here and again in the runner, and the two had
        # drifted from the build: `atoc_fares_loader`, `atoc_knowledgebase` and
        # `destination_coverage` are imported by every build and were named by
        # neither, so editing one left a built site looking current. It is read
        # from the imports now, and this fails if a module stops being reached.
        root = Path(build_demo_page.__file__).parent
        covered = set(build_demo_page.SOURCE_FILES)
        reached: set[str] = set()
        pending = ["build_demo_page.py"]
        while pending:
            name = pending.pop()
            if name in reached:
                continue
            reached.add(name)
            self.assertIn(name, covered, f"the build imports {name} and does not hash it")
            for node in ast.walk(ast.parse((root / name).read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    names = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module.split(".")[0]]
                else:
                    continue
                pending.extend(f"{module}.py" for module in names if (root / f"{module}.py").is_file())
        self.assertGreater(len(reached), 5, "the build's imports were not followed")
        # The two files a build reads as data rather than importing: the reviewed
        # destination facets, and the brand mark the footer inlines.
        self.assertIn("reference-data/destination-facets.json", covered)
        self.assertIn("assets/powered-by-national-rail.svg", covered)

    def test_module_sources_follows_an_import_chain(self) -> None:
        # The walk is what makes the list above true, so it is held to its own
        # answers rather than only to the tree it runs in: a module reached
        # through another module counts, and a name that is not a file beside
        # it -- the standard library, a misspelling -- does not.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "one.py").write_text(
                "import json\nimport two\nfrom nope import missing\n", encoding="utf-8"
            )
            (root / "two.py").write_text("from three import name\n", encoding="utf-8")
            (root / "three.py").write_text("name = 1\n", encoding="utf-8")
            self.assertEqual(
                build_demo_page.module_sources(root, "one.py"),
                ("one.py", "three.py", "two.py"),
            )

    def test_a_build_says_whether_it_parsed_or_restored_the_timetable(self) -> None:
        # On the real feed those are 55.6s and 2.6s, so the line that reports
        # the load is the line an operator reads to find out which they paid.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = build_synthetic_feed(root / "fares", include_restrictions=True)
            timetable = build_synthetic_timetable(root / "timetable")
            cache = root / "cache"
            with mock.patch.object(build_state, "CACHE_DIR", cache):
                said = []
                for _ in range(2):
                    buffer = io.StringIO()
                    with contextlib.redirect_stdout(buffer):
                        code = build_demo_page.main(
                            [
                                "--feed", str(feed),
                                "--timetable", str(timetable),
                                "--origin", "GRN",
                                "--out", str(root / "site" / "index.html"),
                            ]
                        )
                    self.assertEqual(code, 0)
                    said.append(buffer.getvalue())
        self.assertIn("(parsed; wrote timetable-GRN-", said[0])
        self.assertIn("(restored from timetable-GRN-", said[1])

    def test_a_cache_hit_that_is_the_oldest_file_still_survives(self) -> None:
        # A hit does not touch mtime, so the file this build just read can be
        # the oldest on disk. It must not evict itself.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(build_state, "CACHE_DIR", root):
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

class FaresCacheTest(unittest.TestCase):
    """A page build parses the national feed once, then reads it off the disk.

    A focused parse of the real DTD download reads 727,315 flow records to
    keep the ones reachable from one station, and took 32.5s of a real build;
    restoring the split the pool build already persists takes about a second.
    The risk in any such cache is not that it misses, it is that it hits when
    it should not, so most of what is checked here is what must NOT be served.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.cache = root / "cache"
        self.feed = build_synthetic_feed(root / "fares", include_restrictions=True)
        self.out = root / "site" / "index.html"
        # These builds run the real ``main()``, so a classification pass that
        # reached the network would make a test's outcome depend on the
        # internet and on what the ONS server thought of this machine's cache --
        # the suite was printing ``ResourceWarning: <HTTPError 304>`` from
        # exactly that fetch (audit item 3, 14 October 2026). A refused request
        # is what an offline machine gives the loader, and it is already a
        # named, reported outcome rather than a failure.
        self._offline = mock.patch.object(
            atoc_fares_loader.urllib.request, "urlopen",
            side_effect=urllib.error.URLError("the test suite does not fetch"),
        )
        self._offline.start()
        self.addCleanup(self._offline.stop)

    def build(self) -> str:
        buffer = io.StringIO()
        with mock.patch.object(build_state, "CACHE_DIR", self.cache):
            with contextlib.redirect_stdout(buffer):
                code = build_demo_page.main(
                    ["--feed", str(self.feed), "--origin", "GRN", "--out", str(self.out)]
                )
        self.assertEqual(code, 0)
        return buffer.getvalue()

    def cache_paths(self):
        # The cache lives where the build puts it, so it is asked for from
        # there: a test that named the repository's own _cache would be reading
        # and writing the caches of whichever test ran before it.
        with mock.patch.object(build_state, "CACHE_DIR", self.cache):
            return build_demo_page.fares_index_cache_paths(self.feed)

    def load_fares(self, origin: str):
        with mock.patch.object(build_state, "CACHE_DIR", self.cache):
            return build_demo_page.load_page_fares(self.feed, origin)

    def prune(self, *used) -> int:
        with mock.patch.object(build_state, "CACHE_DIR", self.cache):
            return build_demo_page.prune_fare_index_caches(*used)
    def page(self) -> str:
        return station_page(self.out).read_text(encoding="utf-8")

    def without_timestamp(self, html: str) -> str:
        return html.replace(html.split('"builtAt":"')[1][:20], "TIMESTAMP")

    def test_the_second_build_reads_the_cache_and_writes_the_same_page(self) -> None:
        first = self.build()
        self.assertIn("wrote ", first, "the first build parses the feed and fills the cache")
        common, index_dir = self.cache_paths()
        self.assertTrue(common.is_file(), "the shared half is written for the next build")
        self.assertTrue((index_dir / "GRN.pickle").is_file(), "one index per origin")
        written = self.page()

        second = self.build()
        self.assertIn("restored from GRN.pickle", second)
        # The whole point of the cache: the same page, from a different route.
        # A restored database is the one the pool workers already build pages
        # from, and if the two ever disagreed the cache would be quietly
        # changing prices rather than saving time.
        self.assertEqual(self.without_timestamp(written), self.without_timestamp(self.page()))

    def test_a_feed_replaced_by_other_bytes_of_the_same_size_and_time_is_not_served(self) -> None:
        # The stale-cache case a fingerprint cannot catch. A copy that
        # preserves timestamps, or an archive extracted with the dates stored
        # in it, replaces a feed with different fares and no visible change to
        # its name, size or mtime. A cache keyed on any of those would go on
        # serving yesterday's prices, and the page would look entirely normal.
        self.build()
        before = self.page()
        self.assertIn("1160", before, "the fixture's Nottingham return is on the page")
        cache_before = self.cache_paths()

        target = next(item for item in sorted(self.feed.glob("*.ffl")))
        original = target.read_text(encoding="utf-8")
        stamp = target.stat().st_mtime_ns
        # Same length, same timestamp, different fare.
        target.write_text(original.replace("1160", "1260", 1), encoding="utf-8")
        os.utime(target, ns=(stamp, stamp))
        self.assertEqual(len(target.read_text(encoding="utf-8")), len(original))

        said = self.build()
        self.assertIn("wrote GRN.pickle", said, "different bytes are a different cache, so the feed is parsed again")
        self.assertNotEqual(cache_before, self.cache_paths())
        self.assertNotEqual(before, self.page())
        self.assertIn("1260", self.page(), "the page quotes the fare the feed now holds")

    def test_a_classification_corrected_beside_the_feed_misses_the_cache(self) -> None:
        # The station types a parse carries come from files beside the feed and
        # from the code that reads them, not from the feed's own bytes. A key on
        # the feed alone would serve a database whose types came from a source
        # that has since been corrected: current prices, stale classes, and a
        # page that looks entirely normal.
        self.build()
        before_cache = self.cache_paths()
        self.assertEqual(self.destination_type("LCN"), "city")

        types = self.feed.parent / "fares.location-types.json"
        records = json.loads(types.read_text(encoding="utf-8"))
        records["records"]["LCN"] = {"primary": "village", "facets": []}
        types.write_text(json.dumps(records), encoding="utf-8")
        self.assertNotEqual(
            before_cache, self.cache_paths(), "the corrected classification is a different cache"
        )

        said = self.build()
        self.assertIn("wrote GRN.pickle", said, "the feed is parsed again rather than served from before")
        self.assertEqual(self.destination_type("LCN"), "village")

    def destination_type(self, crs: str) -> str:
        rows = {
            row["crs"]: row
            for row in embedded_payload(self.page())["destinations"]
        }
        return rows[crs]["destinationType"]

    def test_the_cache_is_named_after_the_classification_pass_not_before_it(self) -> None:
        # The classification pass writes ``fares.location-types.json`` beside the
        # feed, and the cache identity hashes every file beside it, so a pair
        # named *before* that write is one no later build can ask for: the next
        # build hashes the file this one wrote, computes a different digest,
        # misses, and pays the parse the cache exists to avoid -- 55.6s against
        # 2.6s restored, measured on this repository's own machine (audit item 2,
        # 14 October 2026). The pass is simulated by writing the file from inside
        # the load, which is where it happens; what the test holds is the order,
        # and the order is the whole of the fix.
        unique = self.cache / "probe"
        unique.mkdir(parents=True, exist_ok=True)
        types = self.feed.parent / "fares.location-types.json"
        content = types.read_bytes()
        # A fresh download of this feed has no classification cache beside it yet.
        types.unlink()
        with mock.patch.object(build_state, "CACHE_DIR", self.cache):
            named_before = build_demo_page.fares_index_cache_paths(self.feed)[0]

        real_load = FaresDb.load_feed

        def load_and_classify(self, path, **kwargs):
            fares = real_load(self, path, **kwargs)
            types.write_bytes(content)
            return fares

        with mock.patch.object(FaresDb, "load_feed", load_and_classify):
            first = self.load_fares("GRN")
        self.assertFalse(first.restored)
        self.assertTrue(first.common.is_file())
        self.assertNotEqual(
            named_before,
            first.common,
            "the file that appeared has to be in the key, or this test proves nothing",
        )
        self.assertEqual(
            first.common,
            self.cache_paths()[0],
            "the pair is named by the bytes as they are after the pass",
        )
        second = self.load_fares("GRN")
        self.assertTrue(second.restored, "the next build asks for the pair this one wrote")

    def test_an_index_filed_under_another_origin_is_not_served(self) -> None:
        # The path a build asks for is built from the origin it was asked for,
        # so a file under the wrong name is a hand-mixed cache. Serving it would
        # put one station's fares on another station's page.
        self.build()
        _, index_dir = self.cache_paths()
        self.load_fares("NOT")
        nottingham = index_dir / "NOT.pickle"
        self.assertTrue(nottingham.is_file())
        shutil.copy(nottingham, index_dir / "GRN.pickle")

        served_fares = self.load_fares("GRN")
        self.assertFalse(served_fares.restored, "another origin's index is not this origin's fares")
        self.assertNotEqual(
            served_fares.index.read_bytes(),
            nottingham.read_bytes(),
            "the wrong index is rewritten rather than left in place",
        )
        # And what was written back is this origin's: the flows an index keeps
        # are the ones reachable from the station it names, so an index that
        # had been another station's would answer with another station's NLCs.
        restored = FaresDb.load_fare_index(served_fares.common, served_fares.index)
        self.assertEqual(restored._cache_origin, "GRN")
        carried = {restored.locations_by_nlc[nlc].crs for nlc in restored.flows_touching_nlc}
        self.assertEqual(carried, {"GRN"})
        self.assertEqual(
            served_fares.fares.stats()["fares"], restored.stats()["fares"]
        )

    def test_a_half_written_cache_is_parsed_over_rather_than_trusted(self) -> None:
        # A build interrupted while writing leaves a truncated pickle. A cache
        # is an optimisation, so the worst it may do is be slow.
        self.build()
        common, index_dir = self.cache_paths()
        common.write_bytes(b"\x80\x04 truncated")
        loaded = self.load_fares("GRN")
        self.assertFalse(loaded.restored)
        self.assertTrue(loaded.fares.destinations_within("GRN", 100000, adults=1))
        self.assertTrue(loaded.index.is_file())

    def test_a_corrupt_index_is_parsed_over_rather_than_trusted(self) -> None:
        self.build()
        _, index_dir = self.cache_paths()
        (index_dir / "GRN.pickle").write_bytes(b"not a pickle")
        loaded = self.load_fares("GRN")
        self.assertFalse(loaded.restored)
        self.assertTrue(loaded.fares.destinations_within("GRN", 100000, adults=1))
        self.assertTrue(loaded.index.is_file())

    def cache_pair(self, digest: str, mtime: float) -> tuple[Path, Path]:
        """A cache pair as an earlier revision of the feed would have left it."""
        common = self.cache / f"fare-index-v2-{digest}.pickle"
        common.write_bytes(b"an earlier revision")
        origins = self.cache / f"fare-index-v2-{digest}-origins"
        origins.mkdir()
        (origins / "GRN.pickle").write_bytes(b"an earlier revision")
        os.utime(common, (mtime, mtime))
        os.utime(origins, (mtime, mtime))
        return common, origins

    def test_the_caches_of_older_feeds_are_tidied_and_this_one_is_kept(self) -> None:
        # A fares cache is named by the feed's content, so a new download means
        # a new name and an old pair can never be read again: 37MB of shared
        # metadata per revision, kept for ever otherwise. One revision back is
        # still worth having -- a build that is interrupted and re-run is
        # looking at it -- and anything older than that is deleted whole.
        self.build()
        previous = self.cache_pair("00000000000000000001", 5000.0)
        older = self.cache_pair("00000000000000000002", 1000.0)
        before = self.cache_files()

        loaded = self.load_fares("GRN")
        removed = self.prune(loaded.common, loaded.index.parent)
        # The claim is which files went, not how many: read as a count, the same
        # assertion also failed whenever the directory happened to hold one pair
        # more than this test put there -- the flake an audit found in one run of
        # four, and the reason it is written as the set difference now.
        gone = before - self.cache_files()
        self.assertEqual(
            gone,
            {
                "fare-index-v2-00000000000000000002.pickle",
                "fare-index-v2-00000000000000000002-origins/GRN.pickle",
            },
            "the oldest pair goes and nothing else does",
        )
        self.assertEqual(removed, len(gone), "the number reported is the number deleted")
        self.assertFalse(older[0].exists() and older[1].exists(), "two revisions back goes")
        self.assertTrue(previous[0].exists() and previous[1].exists(), "one revision back stays")
        self.assertTrue(loaded.common.is_file(), "the pair in use survives")
        self.assertTrue(loaded.index.is_file())

    def cache_files(self) -> set[str]:
        """Every cache file on disk, named relative to the cache directory."""
        return {
            path.relative_to(self.cache).as_posix()
            for path in self.cache.rglob("*")
            if path.is_file()
        }

    def test_a_cache_hit_is_never_the_file_the_tidy_would_delete(self) -> None:
        # The hit can be the oldest file on disk, because reading it does not
        # touch its timestamp. Deleting it would make the next build re-parse
        # for no reason, on the one run that had already paid to parse.
        self.build()
        loaded = self.load_fares("GRN")
        os.utime(loaded.common, (1000.0, 1000.0))
        os.utime(loaded.index, (1000.0, 1000.0))
        removed = self.prune(loaded.common, loaded.index.parent)
        self.assertEqual(removed, 0)
        self.assertTrue(loaded.common.is_file() and loaded.index.is_file())

    def test_the_cache_key_names_the_format_so_a_schema_change_misses(self) -> None:
        # The pickled layout is versioned in the file name: a database written
        # by older code must be left alone, not read and rebuilt into a
        # different structure.
        common, origins = self.cache_paths()
        self.assertIn(f"-v{build_demo_page.FARE_INDEX_CACHE_VERSION}-", common.name)
        self.assertIn(f"-v{build_demo_page.FARE_INDEX_CACHE_VERSION}-", origins.name)
        with mock.patch.object(build_state, "CACHE_DIR", self.cache):
            with mock.patch.object(build_state, "FARE_INDEX_CACHE_VERSION", 99):
                moved_common, moved_origins = build_demo_page.fares_index_cache_paths(self.feed)
        self.assertNotEqual(common, moved_common)
        self.assertNotEqual(origins, moved_origins)
        self.assertIn("-v99-", moved_common.name)

    def test_two_different_feeds_never_share_a_cache(self) -> None:
        first, _ = self.cache_paths()
        # The same feed twice is the same cache, or nothing would ever be read
        # back -- and a feed that differs by one file is a different one.
        self.assertEqual(first, self.cache_paths()[0])
        other = build_synthetic_feed(
            Path(self._tmp.name) / "other", include_restrictions=False
        )
        with mock.patch.object(build_state, "CACHE_DIR", self.cache):
            second, _ = build_demo_page.fares_index_cache_paths(other)
        self.assertNotEqual(first, second)

class ReturnNetworkFixtureTest(unittest.TestCase):
    """The optional block that gives the secondary origins a real network.

    The browser suite drives every station page a build writes, so a station
    with one priced destination turns most of the page's checks into skips.
    These assert the block produces what those checks need, from the feed's own
    data rather than from a flag the page reads.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.feed = Path(self.tmp) / "feed"
        build_synthetic_feed(
            self.feed,
            include_restrictions=True,
            include_third_origin=True,
            include_return_network=True,
        )
        build_synthetic_timetable(self.feed, include_return_network=True)
        self.fares = FaresDb().load_feed(self.feed)
        self.timetable = TimetableDb().load_feed(self.feed)

    def test_the_base_fixture_is_unchanged_without_the_flag(self) -> None:
        # Every parser test counts records, so the block has to stay opt-in.
        plain = Path(self.tmp) / "plain"
        build_synthetic_feed(plain, include_restrictions=True)
        build_synthetic_timetable(plain)
        base = FaresDb().load_feed(plain)
        for crs in ("MAT", "RET", "SLD", "LEC"):
            self.assertNotIn(crs, base.locations_by_crs)
        plain_timetable = TimetableDb().load_feed(plain)
        for tiploc in ("MATL", "SLDK", "LEIC"):
            self.assertIsNone(plain_timetable.crs_for_tiploc(tiploc))

    def test_both_secondary_origins_price_more_than_one_destination(self) -> None:
        for origin in ("LCN", "NOT"):
            fares = build_demo_page.build_payload(self.fares, self.timetable, origin)
            self.assertGreater(
                len(fares["anytimeDestinations"]), 1, f"{origin} prices too few to exercise the page"
            )

    def test_the_set_carries_a_heritage_row_a_small_town_and_a_seaside_town(self) -> None:
        payload = build_demo_page.build_payload(self.fares, self.timetable, "LCN")
        with_heritage = [row for row in payload["anytimeDestinations"] if row["heritageSites"]]
        self.assertTrue(with_heritage, "no destination carries a UNESCO property")
        types = {t for row in payload["anytimeDestinations"] for t in row["destinationTypes"]}
        self.assertIn("small_town", types)
        self.assertIn("seaside", types)

    def test_every_row_carries_the_backlog_day_out_lists(self) -> None:
        # ADR-0062: the station cell reads rspbSites, nationalTrustSites and
        # nationalParkSites off each row, so a row without one would render an
        # undefined proof. The key is always present and always a list.
        payload = build_demo_page.build_payload(self.fares, self.timetable, "LCN")
        for row in payload["destinations"]:
            for key in ("rspbSites", "nationalTrustSites", "nationalParkSites"):
                self.assertIsInstance(row[key], list, (row["crs"], key))

    def test_some_fares_sit_above_the_railcard_minimum_and_some_below(self) -> None:
        # Both directions matter: a card with nothing to discount cannot be
        # exercised, and a card that discounts every fare cannot show what the
        # page does with one it does not beat.
        payload = build_demo_page.build_payload(self.fares, self.timetable, "LCN")
        prices = [row["adultPence"] for row in payload["anytimeDestinations"]]
        self.assertTrue(any(p > 1200 for p in prices), "nothing is above the £12.00 minimum")
        self.assertTrue(any(p < 1200 for p in prices), "nothing is below the £12.00 minimum")
        self.assertTrue(
            any(card["eligibleCount"] > 0 for card in payload["railcards"]),
            "no card discounts a displayed fare on this origin",
        )

    def test_a_changed_journey_names_the_station_where_it_changes(self) -> None:
        # Q2 (ADR-0045): a split ticket is the reply the launch post expects,
        # and the page answers it where the fare's condition already sits --
        # naming the interchange, claiming no price.
        payload = build_demo_page.build_payload(self.fares, self.timetable, "LCN")
        changed = [row for row in payload["destinations"] if row["changes"] == 1]
        self.assertTrue(changed, "no destination on this page changes")
        self.assertEqual(changed[0]["changeStations"], [{"crs": "NOT", "name": "NOTTINGHAM"}])
        direct = next(row for row in payload["destinations"] if row["changes"] == 0)
        self.assertEqual(direct["changeStations"], [], "a direct journey has no change to split at")

    def test_one_destination_is_priced_and_never_served(self) -> None:
        # The shape the page's "no service" row exists to report.
        payload = build_demo_page.build_payload(self.fares, self.timetable, "LCN")
        states = {row["journeyState"] for row in payload["anytimeDestinations"]}
        self.assertIn("found", states)
        self.assertTrue(
            any(state != "found" for state in states),
            f"every destination has a journey: {states}",
        )

class TimetableIndexBuildTest(unittest.TestCase):
    """A build from an index writes the pages a build from the feed writes.

    The index exists so a build can drop the national feed, and what makes that
    safe is that the slices on disk answer what the feed answered. The pages are
    the comparison, and the feed is booby-trapped rather than merely absent, so a
    build that reads it anyway fails here instead of going unnoticed.
    """

    BUILT_AT = re.compile(r'("builtAt"\s*:\s*)"[^"]*"')

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.feed = build_synthetic_feed(
            self.root / "fares", include_unserved_station=True, include_restrictions=True
        )
        self.timetable = build_synthetic_timetable(self.root / "timetable")
        self.index_root = self.root / "index"

    def build(
        self,
        name: str,
        *extra: str,
        stations: str = "GRN,NOT",
        feed_readable: bool = True,
    ) -> tuple[int, str, str]:
        """Run the build. With ``feed_readable`` False, reading the feed raises."""
        out, err = io.StringIO(), io.StringIO()
        argv = [
            "--feed", str(self.feed),
            "--all-origins",
            "--only-stations", stations,
            "--out", str(self.root / name / "index.html"),
            *extra,
        ]
        trap = (
            mock.patch.object(TimetableDb, "load_feed", side_effect=AssertionError("the timetable feed was read"))
            if not feed_readable
            else contextlib.nullcontext()
        )
        with trap, contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = build_demo_page.main(argv)
        return code, out.getvalue(), err.getvalue()

    def pages(self, name: str) -> dict[str, str]:
        """The station pages written, with the build's own timestamp masked."""
        return {
            path.parent.name: self.BUILT_AT.sub(r'\1"X"', path.read_text(encoding="utf-8"))
            for path in sorted((self.root / name / "from").glob("*/index.html"))
        }

    def write_index(self, *origins: str) -> None:
        from tools.build_timetable_index import main as index_main

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = index_main(
                [
                    "--timetable", str(self.timetable),
                    "--root", str(self.index_root),
                    "--origins", ",".join(origins),
                ]
            )
        self.assertEqual(code, 0, out.getvalue())

    def test_a_build_from_the_index_writes_the_same_pages_as_a_build_from_the_feed(self) -> None:
        code, said, _ = self.build("from_feed", "--timetable", str(self.timetable))
        self.assertEqual(code, 0, said)
        self.write_index("GRN", "NOT")
        code, said, _ = self.build(
            "from_index", "--timetable-index", str(self.index_root), feed_readable=False
        )
        self.assertEqual(code, 0, said)
        self.assertIn("No timetable feed", said)
        self.assertEqual(sorted(self.pages("from_feed")), ["grantham", "nottingham"])
        self.assertEqual(self.pages("from_index"), self.pages("from_feed"))

    def test_a_station_subset_the_index_covers_does_not_read_the_feed(self) -> None:
        # The feed is named on the command line and still not read: the whole
        # point of the index, and the one claim a `--timetable` argument would
        # otherwise hide.
        self.write_index("GRN", "NOT")
        code, said, err = self.build(
            "covered",
            "--timetable", str(self.timetable),
            "--timetable-index", str(self.index_root),
            feed_readable=False,
        )
        self.assertEqual(code, 0, err + said)
        self.assertIn("the timetable feed is not read", said)
        self.assertEqual(sorted(self.pages("covered")), ["grantham", "nottingham"])

    def test_a_page_with_no_slice_stops_the_build_before_it_writes_one(self) -> None:
        self.write_index("GRN")
        code, said, err = self.build(
            "partial", "--timetable-index", str(self.index_root), feed_readable=False
        )
        self.assertEqual(code, 2)
        self.assertIn("NOT", err)
        self.assertFalse(
            (self.root / "partial" / "from").exists(), "a refused build writes no page"
        )

    def test_a_page_with_no_slice_is_built_from_the_feed_when_there_is_one(self) -> None:
        # An index is an optimisation when a feed is present and a requirement
        # when it is not, so a partly indexed build finishes rather than stops.
        self.write_index("GRN")
        code, said, _ = self.build(
            "fallback", "--timetable", str(self.timetable), "--timetable-index", str(self.index_root)
        )
        self.assertEqual(code, 0, said)
        self.assertEqual(sorted(self.pages("fallback")), ["grantham", "nottingham"])

    def test_an_index_cut_from_another_download_is_not_used_by_a_build_that_has_the_feed(self) -> None:
        # The download changed, so the index is keyed to a feed that is no longer
        # here. A build holding the new feed must reach for the new feed rather
        # than for slices of the old one, which is one byte of difference and a
        # different timetable.
        self.write_index("GRN", "NOT")
        target = next(item for item in sorted(self.timetable.iterdir()) if item.is_file())
        original = target.read_text(encoding="utf-8")
        target.write_text(original.replace("NOT", "NT1", 1), encoding="utf-8")
        self.assertEqual(len(target.read_text(encoding="utf-8")), len(original))
        code, said, err = self.build(
            "replaced", "--timetable", str(self.timetable), "--timetable-index", str(self.index_root)
        )
        self.assertEqual(code, 0, said + err)
        self.assertIn("no slices yet", said)
        self.assertEqual(sorted(self.pages("replaced")), ["grantham", "nottingham"])

    def pool_initargs(self, *extra: str) -> tuple:
        """What the pool is created with, captured before it starts a worker.

        The pool is replaced rather than run: what is under test is the argument
        a worker is handed, and a real worker's own parse of the feed is exactly
        what cannot be observed from the parent's stdout.
        """
        seen: list[tuple] = []

        class Stop(BaseException):
            """Raised once the pool has recorded what it was created with."""

        class RecordingPool:
            def __init__(self, workers, *, initializer, initargs, **kwargs):
                seen.append(initargs)
                raise Stop

        argv = [
            "--feed", str(self.feed),
            "--all-origins",
            "--only-stations", "GRN,NOT",
            "--workers", "2",
            "--out", str(self.root / "pool" / "index.html"),
            *extra,
        ]
        with mock.patch("concurrent.futures.ProcessPoolExecutor", RecordingPool):
            with contextlib.redirect_stdout(io.StringIO()):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(Stop):
                        build_demo_page.main(argv)
        return seen[0]

    def test_a_worker_is_handed_the_feed_only_when_the_build_reads_it(self) -> None:
        # A worker given a feed path parses the national timetable itself, which
        # is 56s and 1.87 GB per worker. A build that decided not to read the
        # feed has to hand its workers nothing as well, or the saving is the
        # parent's only and every worker holds what the build set out to drop.
        self.write_index("GRN", "NOT")
        self.assertEqual(
            self.pool_initargs("--timetable", str(self.timetable))[1], str(self.timetable)
        )
        self.assertIsNone(
            self.pool_initargs(
                "--timetable", str(self.timetable), "--timetable-index", str(self.index_root)
            )[1]
        )

    def test_a_canary_origin_the_index_lacks_is_named_and_the_build_goes_on(self) -> None:
        # An all-origins build does not write the origin it samples first: it
        # builds one to prove one can be and to time it before a long batch.
        # With no feed there is no timetable for an origin the index does not
        # hold, so the sample is named and skipped. Refusing instead would
        # refuse the request the index is for -- an index of exactly the pages
        # this build writes, where the sample is a station nobody asked for.
        self.write_index("NOT")
        code, said, err = self.build(
            "canary",
            "--timetable-index", str(self.index_root),
            "--origin", "GRN",
            stations="NOT",
            feed_readable=False,
        )
        self.assertEqual(code, 0, said + err)
        self.assertIn("the index holds no slice for GRN", said)
        self.assertEqual(sorted(self.pages("canary")), ["nottingham"])

    def test_the_sample_with_no_slice_says_what_it_cannot_measure(self) -> None:
        # `--max-origin-seconds` measures a page, and a sample with no timetable
        # behind it measures the fares half of one. The build says so rather
        # than reporting that half as the per-origin cost, and rather than
        # refusing a request an index of the pages it writes is the point of.
        self.write_index("NOT")
        code, said, err = self.build(
            "timed",
            "--timetable-index", str(self.index_root),
            "--origin", "GRN",
            stations="NOT",
            feed_readable=False,
        )
        self.assertEqual(code, 0, said + err)
        self.assertIn("--max-origin-seconds measures the fares half of a page", said)
        self.assertEqual(sorted(self.pages("timed")), ["nottingham"])

    def test_a_page_whose_slice_will_not_read_stops_the_build(self) -> None:
        # The index says the slice is there and the file says otherwise. A page
        # assembled without times says the station has no services, so the build
        # stops while the feed that cut the slice is still in hand.
        self.write_index("GRN", "NOT")
        broken = next(self.index_root.glob("*/NOT.pickle"))
        broken.write_bytes(b"not a slice")
        with self.assertRaises(OSError):
            self.build(
                "broken", "--timetable-index", str(self.index_root), feed_readable=False
            )

    def test_a_build_that_names_the_identity_directory_itself_uses_it(self) -> None:
        # A build log prints the identity directory rather than the root it sits
        # under, so a reader who copies that path has named one. The identity is
        # still the feed's, so naming another download's directory is an empty
        # index rather than another feed's timetables.
        self.write_index("GRN", "NOT")
        named = next(path for path in self.index_root.iterdir() if path.is_dir())
        code, said, err = self.build(
            "named",
            "--timetable", str(self.timetable),
            "--timetable-index", str(named),
            feed_readable=False,
        )
        self.assertEqual(code, 0, said + err)
        self.assertIn("the timetable feed is not read", said)
        self.assertEqual(sorted(self.pages("named")), ["grantham", "nottingham"])

    def test_an_index_is_used_without_a_feed_however_the_download_changed(self) -> None:
        # With no feed there is nothing to compare the index against, and the
        # caller named it: this is the "no feed on the machine" case, and it
        # builds from the slices that are there.
        self.write_index("GRN", "NOT")
        target = next(item for item in sorted(self.timetable.iterdir()) if item.is_file())
        target.write_text(target.read_text(encoding="utf-8").replace("NOT", "NT1", 1), encoding="utf-8")
        code, said, err = self.build(
            "no_feed", "--timetable-index", str(self.index_root), feed_readable=False
        )
        self.assertEqual(code, 0, said + err)
        self.assertEqual(sorted(self.pages("no_feed")), ["grantham", "nottingham"])


class PageFactsTest(unittest.TestCase):
    """One origin's reusable answers: the week's journeys and the priced counts.

    T2, T3, T6 and T9 of the 12 October 2026 build-cost audit: the timetable
    half of a page is searched once per timetable feed rather than once per
    build, and the pricing pre-pass replays the counts it already priced. The
    cache directory is the module's patched one, so no test reads another
    run's facts -- and each test below names its own identity, so no test
    reads another test's either.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.fares = FaresDb().load_feed(
            build_synthetic_feed(root / "fares", include_restrictions=True)
        )
        self.timetable = TimetableDb().load_feed(build_synthetic_timetable(root / "timetable"))
        self.day = date(2026, 10, 5)


    def test_a_fares_focused_timetable_is_never_a_journey_facts_source(self) -> None:
        # The single-origin build cuts the timetable to the destinations its
        # fares price, so its week is not a fact about the timetable alone; a
        # fares refresh reusing it would call a newly priced row "No service".
        import argparse

        single = argparse.Namespace(all_origins=False, timetable="feed")
        self.assertIsNone(build_demo_page.timetable_facts_identity(single, object(), None))
        network = argparse.Namespace(all_origins=True, timetable=None)
        index = type("Index", (), {"identity": "slice-id"})()
        self.assertEqual(build_demo_page.timetable_facts_identity(network, None, index), "slice-id")
    def test_a_service_week_written_is_a_service_week_read(self) -> None:
        from datetime import timedelta

        days = [self.day + timedelta(days=offset) for offset in range(8)]
        weeks = [{"LCN": [50, 0], "NOT": [45, 0]} for _ in days]
        build_demo_page.write_service_week("GRN", "timetable-a", 0, 1, days, weeks)
        self.assertEqual(
            build_demo_page.read_service_week("GRN", "timetable-a", 0, 1, days), weeks
        )

    def test_a_fact_from_another_timetable_is_a_miss_not_a_page(self) -> None:
        from datetime import timedelta

        days = [self.day + timedelta(days=offset) for offset in range(8)]
        build_demo_page.write_service_week(
            "GRN", "timetable-a", 0, 1, days, [{"LCN": [50, 0]} for _ in days]
        )
        self.assertIsNone(build_demo_page.read_service_week("GRN", "timetable-b", 0, 1, days))
        self.assertIsNone(build_demo_page.read_service_week("GRN", "timetable-a", 1, 1, days))
        self.assertIsNone(build_demo_page.read_service_week("GRN", "timetable-a", 0, 2, days))
        other = [self.day + timedelta(days=offset + 1) for offset in range(8)]
        self.assertIsNone(build_demo_page.read_service_week("GRN", "timetable-a", 0, 1, other))
        self.assertIsNone(build_demo_page.read_service_week("NOT", "timetable-a", 0, 1, days))

    def test_a_half_written_facts_file_is_a_miss(self) -> None:
        path = build_demo_page.page_facts_path("GRN")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        self.assertIsNone(build_demo_page.read_page_facts("GRN"))
        self.assertIsNone(
            build_demo_page.read_service_week("GRN", "timetable-a", 0, 1, [self.day])
        )

    def test_a_second_build_searches_no_week_it_already_searched(self) -> None:
        # T9: the fares-only refresh reuses every journey fact. The build-day
        # search still runs -- the legs and departures are the page's own --
        # but the eight sweeps do not.
        calls = []
        real = TimetableDb.journeys_from

        def spy(db, origin, **kwargs):
            calls.append((origin, kwargs.get("day")))
            return real(db, origin, **kwargs)

        with mock.patch.object(TimetableDb, "journeys_from", spy):
            cold = build_demo_page.build_payload(
                self.fares, self.timetable, "GRN", day=self.day, timetable_identity="week-reuse"
            )
        cold_calls = len(calls)
        self.assertGreater(cold_calls, 1, "the cold build searches the week")
        with mock.patch.object(TimetableDb, "journeys_from", spy):
            warm = build_demo_page.build_payload(
                self.fares, self.timetable, "GRN", day=self.day, timetable_identity="week-reuse"
            )
        warm_calls = len(calls) - cold_calls
        self.assertEqual(warm_calls, 1, "the warm build searches only its own day")
        self.assertEqual(warm["serviceWeek"], cold["serviceWeek"])
        self.assertEqual(warm["serviceDays"], cold["serviceDays"])

    def test_a_new_row_priced_by_new_fares_finds_its_journeys_waiting(self) -> None:
        # The whole reached set is stored rather than the wanted subset, so a
        # destination the next fares feed prices for the first time is timed
        # from the facts rather than searched for.
        from datetime import timedelta

        days = [self.day + timedelta(days=offset) for offset in range(8)]
        build_demo_page.write_service_week(
            "GRN", "timetable-a", 0, 1, days, [{"ZZZ": [99, 1]} for _ in days]
        )
        stored = build_demo_page.read_service_week("GRN", "timetable-a", 0, 1, days)
        self.assertEqual(stored[0], {"ZZZ": [99, 1]})

    def test_priced_counts_written_are_priced_counts_read(self) -> None:
        coverage = {"count": 0, "coverage": {"totals": ["LCN"], "unsourced": [], "unnameable": 0}}
        build_demo_page.write_priced_facts("GRN", "fares-a", self.day, 3, coverage["coverage"])
        stored = build_demo_page.read_priced_facts("GRN", "fares-a", self.day)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored["count"], 3)
        self.assertEqual(stored["coverage"]["totals"], ["LCN"])

    def test_priced_counts_do_not_survive_a_new_fares_feed(self) -> None:
        build_demo_page.write_priced_facts("GRN", "fares-a", self.day, 3, {})
        self.assertIsNone(build_demo_page.read_priced_facts("GRN", "fares-b", self.day))
        self.assertIsNone(build_demo_page.read_priced_facts("GRN", "fares-a", None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
