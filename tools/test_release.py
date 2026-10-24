"""The release workflow's steps, held on a desk instead of on a run."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.release import commits, facets, feed_identity, feed_state, manifest, schedule, share


def quietly(call, *args, **kwargs):
    """Run a step and return (its result, what it printed)."""
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(printed):
        result = call(*args, **kwargs)
    return result, printed.getvalue()


class InScratch(unittest.TestCase):
    """A step runs from the repository root; here the root is a scratch folder."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._cwd = os.getcwd()
        os.chdir(self.root)
        self._output = mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(self.root / "outputs")})
        self._output.start()

    def tearDown(self) -> None:
        self._output.stop()
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def outputs(self) -> str:
        path = self.root / "outputs"
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def feeds(self, fares: str = "a" * 64, schedule_bytes: bytes = b"CIF") -> None:
        folder = self.root / "feeds" / "nwr-schedule"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "nwr-schedule.CIF.gz").write_bytes(schedule_bytes)
        entries = [
            {"name": "fares", "sha256": fares, "bytes": 10, "downloaded_at": "2026-10-22T03:17:00Z"},
            {"name": "timetable", "sha256": "b" * 64, "bytes": 20, "downloaded_at": "2026-10-22T03:18:00Z"},
            {"name": "knowledgebase", "sha256": "c" * 64, "bytes": 30},
        ]
        (self.root / "feeds" / "download-manifest.json").write_text(json.dumps({"downloads": entries}), encoding="utf-8")
        schedule.write_identity()


@unittest.skipUnless(shutil.which("git"), "git is not on PATH")
class CommitsTest(InScratch):
    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()

    def commit(self, message: str) -> str:
        self.git("-c", "user.name=A Person", "-c", "user.email=person@example.net", "-c", "core.hooksPath=/dev/null",
                 "commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def setUp(self) -> None:
        super().setUp()
        self.git("init", "-q")
        self.base = self.commit("docs: the base")

    def test_a_run_that_added_no_commits_checks_none(self) -> None:
        for before in ("", "0" * 40):
            code, printed = quietly(commits.main, ["--before", before])
            self.assertEqual(code, 0)
            self.assertIn("no message to check", printed)

    def test_every_added_commit_is_checked(self) -> None:
        self.commit("docs: a good one")
        self.commit("Added a bad one.")
        code, printed = quietly(commits.main, ["--before", self.base])
        self.assertEqual(code, 1)
        self.assertIn("::error title=commit message::Added a bad one.", printed)
        self.assertIn("1 of the 2 commit messages", printed)

    def test_a_clean_push_passes(self) -> None:
        self.commit("docs: a good one")
        code, printed = quietly(commits.main, ["--before", self.base])
        self.assertEqual(code, 0, printed)

    def test_a_replaced_base_holds_every_commit_to_the_credit_rule_only(self) -> None:
        # The grammar is not applied backwards, the credit rule is.
        self.commit("Old style subject")
        code, printed = quietly(commits.main, ["--before", "1" * 40])
        self.assertEqual(code, 0, printed)
        self.commit("docs: x\n\nCo-Authored-By: Codebuff <noreply@codebuff.com>")
        code, printed = quietly(commits.main, ["--before", "1" * 40])
        self.assertEqual(code, 1)
        self.assertIn("credits Codebuff", printed)

    def test_a_range_with_no_commit_fails(self) -> None:
        code, printed = quietly(commits.main, ["--before", self.base])
        self.assertEqual(code, 1)
        self.assertIn("contains no commit", printed)


class FeedIdentityTest(InScratch):
    def test_the_build_job_names_an_identity_another_job_can_match(self) -> None:
        self.feeds()
        code, _ = quietly(feed_identity.main, [])
        self.assertEqual(code, 0)
        value = self.outputs().strip().removeprefix("value=")
        self.assertRegex(value, r"^[0-9a-f]{64}$")
        self.assertEqual(quietly(feed_identity.main, ["--expect", value])[0], 0)

    def test_the_knowledgebase_and_the_download_time_are_not_part_of_it(self) -> None:
        self.feeds()
        before = feed_identity.identity()
        data = json.loads((self.root / "feeds/download-manifest.json").read_text())
        for entry in data["downloads"]:
            entry["downloaded_at"] = "2026-10-22T04:00:00Z"
            if entry["name"] == "knowledgebase":
                entry["sha256"] = "d" * 64
        (self.root / "feeds/download-manifest.json").write_text(json.dumps(data))
        self.assertEqual(feed_identity.identity(), before)

    def test_a_republished_fares_feed_is_refused(self) -> None:
        self.feeds()
        audited = feed_identity.identity()
        self.feeds(fares="e" * 64)
        code, printed = quietly(feed_identity.main, ["--expect", audited])
        self.assertEqual(code, 1)
        self.assertIn("the portal republished mid-run", printed)

    def test_a_moved_timetable_is_refused(self) -> None:
        self.feeds()
        audited = feed_identity.identity()
        self.feeds(schedule_bytes=b"another CIF")
        self.assertEqual(quietly(feed_identity.main, ["--expect", audited])[0], 1)

    def test_nothing_to_name_is_refused_rather_than_read_as_agreement(self) -> None:
        self.assertEqual(feed_identity.identity(), "")
        self.assertEqual(quietly(feed_identity.main, [])[0], 1)
        self.assertEqual(quietly(feed_identity.main, ["--expect", ""])[0], 1)


class FeedStateTest(InScratch):
    def changed(self, event: str) -> str:
        quietly(feed_state.main, ["changed", "--event", event])
        return self.outputs().strip().splitlines()[-1]

    def test_a_push_or_a_manual_run_always_builds(self) -> None:
        self.feeds()
        feed_state.save()
        for event in ("push", "workflow_dispatch"):
            self.assertEqual(self.changed(event), "changed=true")

    def test_a_schedule_with_no_marker_builds(self) -> None:
        self.feeds()
        self.assertEqual(self.changed("schedule"), "changed=true")

    def test_a_schedule_skips_only_when_feeds_timetable_and_inputs_all_match(self) -> None:
        self.feeds()
        feed_state.save()
        self.assertEqual(self.changed("schedule"), "changed=false")
        self.feeds(schedule_bytes=b"a moved CIF")
        self.assertEqual(self.changed("schedule"), "changed=true")
        self.feeds()
        self.feeds(fares="f" * 64)
        self.assertEqual(self.changed("schedule"), "changed=true")

    def test_a_checked_but_unchanged_download_does_not_rebuild(self) -> None:
        # The manifest records when a download was last checked, which moves on
        # every run, including one the portal answered 304.
        self.feeds()
        feed_state.save()
        data = json.loads((self.root / "feeds/download-manifest.json").read_text())
        data["downloads"][0].update(checked_at="2026-10-23T03:17:00Z", unchanged=True)
        (self.root / "feeds/download-manifest.json").write_text(json.dumps(data))
        self.assertEqual(self.changed("schedule"), "changed=false")

    def test_new_build_inputs_rebuild(self) -> None:
        self.feeds()
        feed_state.save()
        with mock.patch.object(feed_state, "build_inputs", return_value="0" * 64):
            self.assertEqual(self.changed("schedule"), "changed=true")


class ScheduleTest(InScratch):
    def test_no_address_stops_before_any_request(self) -> None:
        with mock.patch.dict(os.environ, {"SCHEDULE_URL": ""}), mock.patch.object(schedule.schedule_download, "main") as fetch:
            code, printed = quietly(schedule.main, ["--probe"])
        self.assertEqual(code, 1)
        self.assertIn("no SCHEDULE_URL repository variable is set", printed)
        fetch.assert_not_called()

    def test_the_identity_is_the_one_sha256sum_writes(self) -> None:
        self.feeds(schedule_bytes=b"CIF bytes")
        digest = hashlib.sha256(b"CIF bytes").hexdigest()
        self.assertEqual(
            (self.root / "feeds/nwr-schedule.sha256").read_bytes(),
            f"{digest}  feeds/nwr-schedule/nwr-schedule.CIF.gz\n".encode(),
        )

    def test_a_failed_download_writes_no_identity(self) -> None:
        (self.root / "feeds/nwr-schedule").mkdir(parents=True)
        with mock.patch.dict(os.environ, {"SCHEDULE_URL": "https://example.net/cif.gz"}), \
                mock.patch.object(schedule.schedule_download, "main", return_value=1):
            self.assertEqual(quietly(schedule.main, [])[0], 1)
        self.assertFalse((self.root / "feeds/nwr-schedule.sha256").exists())


class FacetsTest(InScratch):
    def run_with(self, code: int) -> tuple[int, str]:
        with mock.patch.object(facets.check_facet_reference, "main", return_value=code):
            return quietly(facets.main, ["--feed", "feeds/fares/dtd-fares.zip"])

    def test_a_missing_reference_file_fails(self) -> None:
        code, printed = self.run_with(0)
        self.assertEqual(code, 1)
        self.assertIn("is not in this checkout", printed)

    def test_drift_fails_and_an_unanswered_source_warns(self) -> None:
        (self.root / "reference-data").mkdir()
        (self.root / "reference-data/destination-facets.json").write_text("{}")
        self.assertEqual(self.run_with(0)[0], 0)
        self.assertEqual(self.run_with(1)[0], 1)
        code, printed = self.run_with(2)
        self.assertEqual(code, 0)
        self.assertIn("::warning title=facet reference::", printed)


class ShareTest(unittest.TestCase):
    def test_a_share_is_the_build_for_its_slice_and_its_day(self) -> None:
        built = share.command("3/12", "2026-10-22", 4, base_path="trainbudget")
        for flag, value in (("--shard", "3/12"), ("--date", "2026-10-22"), ("--workers", "4"),
                            ("--base-path", "trainbudget"), ("--notices", "nre,rdg,ogl,accuracy")):
            self.assertEqual(built[built.index(flag) + 1], value)
        self.assertIn("--all-origins", built)
        self.assertIn("--require-live-reviewed-codes", built)
        self.assertNotIn("--base-path", share.command("3/12", "2026-10-22", 4))
        # The page's place cap, at the number the twelve measured pages were
        # costed at (docs/build-performance-findings.md). A release that stopped
        # passing it would build pages twice the site's budget again.
        self.assertEqual(share.PLACE_CAP, 600)
        self.assertEqual(built[built.index("--max-places") + 1], "600")

    def test_a_share_that_nears_the_bound_says_so(self) -> None:
        clock = iter([0.0, share.NEARING_MINUTES * 60.0])
        with mock.patch.object(share.subprocess, "run") as build, \
                mock.patch.object(share, "worker_budget", return_value=2), \
                mock.patch.object(share.time, "monotonic", side_effect=lambda: next(clock)):
            build.return_value.returncode = 0
            code, printed = quietly(share.main, ["--shard", "1/12", "--date", "2026-10-22"])
        self.assertEqual(code, 0)
        self.assertIn(f"took {share.NEARING_MINUTES} minutes", printed)
        self.assertIn("::warning title=The share is nearing its bound::", printed)

    def test_a_failed_build_fails_the_step(self) -> None:
        with mock.patch.object(share.subprocess, "run") as build, mock.patch.object(share, "worker_budget", return_value=2):
            build.return_value.returncode = 3
            self.assertEqual(quietly(share.main, ["--shard", "1/12", "--date", "2026-10-22"])[0], 3)


class ManifestTest(InScratch):
    def site(self, routes: int, journeys: list[str]) -> Path:
        site = self.root / "_site"
        (site / "privacy").mkdir(parents=True)
        (site / "index.html").write_text("chooser")
        (site / "privacy/index.html").write_text("privacy")
        for number, value in enumerate(journeys):
            page = site / "from" / f"s{number}" / "index.html"
            page.parent.mkdir(parents=True)
            page.write_text(value)
        (site / "release-manifest.json").write_text(json.dumps({"routes": list(range(routes))}))
        return site

    def test_a_site_whose_pages_carry_times_passes(self) -> None:
        site = self.site(4, ['{"hasJourneys":true}', '{"hasJourneys": true}'])
        self.assertEqual(quietly(manifest.problems, site, with_times=True)[0], [])

    def test_a_manifest_that_disagrees_with_the_folder_fails(self) -> None:
        site = self.site(3, ['{"hasJourneys":true}', '{"hasJourneys":true}'])
        found, _ = quietly(manifest.problems, site, with_times=True)
        self.assertEqual([title for title, _ in found], ["release manifest"])

    def test_no_manifest_fails(self) -> None:
        site = self.site(2, [])
        (site / "release-manifest.json").unlink()
        found, _ = quietly(manifest.problems, site)
        self.assertIn("wrote no", found[0][1])

    def test_a_page_without_times_fails_a_release_that_declares_them(self) -> None:
        site = self.site(4, ['{"hasJourneys":true}', '{"hasJourneys":false}'])
        found, _ = quietly(manifest.problems, site, with_times=True)
        self.assertIn("carry no journey times", found[0][1])
        self.assertIn("s1/index.html (hasJourneys is false)", found[0][1])

    def test_a_page_with_no_field_or_no_station_page_fails(self) -> None:
        found, _ = quietly(manifest.problems, self.site(3, ["{}"]), with_times=True)
        self.assertIn("no hasJourneys field at all", found[0][1])

    def test_a_site_with_no_station_page_is_unverified_not_passed(self) -> None:
        found, _ = quietly(manifest.problems, self.site(2, []), with_times=True)
        self.assertEqual([title for title, _ in found], ["journeys"])

    def test_a_fares_only_release_refuses_pages_with_times(self) -> None:
        site = self.site(3, ['{"hasJourneys":true}'])
        found, _ = quietly(manifest.problems, site, with_times=False)
        self.assertIn("fares-only release", found[0][1])


if __name__ == "__main__":
    unittest.main()
