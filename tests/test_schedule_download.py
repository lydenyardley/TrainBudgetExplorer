"""Tests for the schedule fetch, which is a URL and nothing else.

The two things worth proving are that the credential cannot travel anywhere it
should not, and that a download which is not a schedule does not become one by
being written to disk.
"""

from __future__ import annotations

import contextlib
import gzip
import io
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from atoc_timetable import TimetableDb
from make_synthetic_feed import build_synthetic_whole_cif
from schedule_download import (
    DownloadError,
    FeedValidationError,
    _DropAuthRedirect,
    _other_feeds,
    _request,
    download_one,
    main,
    redacted,
    validate_download,
)


class FakeResponse:
    def __init__(self, body: bytes, *, status: int = 200, url: str = "") -> None:
        self.body = io.BytesIO(body)
        self.status = status
        self.url = url

    def read(self, size: int = -1) -> bytes:
        return self.body.read(size)

    def close(self) -> None:
        self.body.close()

    def geturl(self) -> str:
        return self.url


class FakeOpener:
    def __init__(self, *responses: FakeResponse | BaseException) -> None:
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if isinstance(response, FakeResponse) and not response.url:
            response.url = request.full_url
        return response


def gzipped_fixture(folder: Path) -> bytes:
    feed = build_synthetic_whole_cif(folder)
    return (Path(feed) / "CIF_ALL_FULL_DAILY_toc-full.CIF.gz").read_bytes()


class RedactedUrlTest(unittest.TestCase):
    def test_the_query_string_is_never_printed(self) -> None:
        # A signed URL's query is the credential: S3 answers one, Darwin's
        # snapshot endpoint answers one, and a log line is a copy.
        self.assertEqual(
            redacted("https://example.test/cif?X-Amz-Signature=secret&type=CIF"),
            "https://example.test/cif",
        )

    def test_a_userinfo_credential_is_never_printed(self) -> None:
        self.assertEqual(redacted("https://user:pw@example.test/cif.gz"), "https://example.test/cif.gz")


class AuthHeaderTest(unittest.TestCase):
    def test_a_credential_is_sent_as_basic_when_one_is_given(self) -> None:
        request = _request("https://example.test/cif.gz", "someone", "hunter2")
        self.assertTrue(request.headers["Authorization"].startswith("Basic "))

    def test_no_credential_means_no_header(self) -> None:
        request = _request("https://example.test/cif.gz", "", "")
        self.assertNotIn("Authorization", request.headers)

    def test_a_redirect_is_followed_without_the_credential(self) -> None:
        # Network Rail's feed answers HTTP Basic with a 302 to a signed S3 URL,
        # and S3 refuses a request that carries both mechanisms at once. The
        # header is copied onto the redirect by urllib, so the handler is the
        # only place it can be dropped -- which is why this is tested here and
        # not through a fake opener, where no redirect ever happens.
        handler = _DropAuthRedirect()
        request = _request("https://example.test/cif.gz", "someone", "hunter2")
        redirected = handler.redirect_request(
            request,
            io.BytesIO(b""),
            302,
            "Found",
            {},
            "https://s3.example.test/signed?X-Amz-Signature=abc",
        )
        self.assertIsNotNone(redirected)
        self.assertNotIn("Authorization", redirected.headers)
        self.assertEqual(redirected.full_url, "https://s3.example.test/signed?X-Amz-Signature=abc")


class DownloadTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.destination = self.root / "feed" / "nwr-schedule.CIF.gz"

    def test_a_downloaded_whole_cif_is_written_and_readable(self) -> None:
        body = gzipped_fixture(self.root / "fixture")
        opener = FakeOpener(FakeResponse(body))
        result = download_one("https://example.test/cif.gz", self.destination, opener=opener)
        self.assertEqual(result.bytes, len(body))
        self.assertEqual(result.path, str(self.destination))
        self.assertTrue(self.destination.is_file())
        # The file it left behind is the one the loader reads: the point of the
        # fetch is a timetable, not a file of the right size.
        timetable = TimetableDb().load_feed(self.destination.parent)
        self.assertEqual([schedule.train_uid for schedule in timetable.schedules], ["W10001"])
        # And the temporary name is gone, because the loader reads every file in
        # a folder and half a download is a second timetable.
        self.assertEqual(sorted(child.name for child in self.destination.parent.iterdir()), [self.destination.name])

    def test_the_header_record_names_the_feed_date(self) -> None:
        body = gzipped_fixture(self.root / "fixture")
        result = download_one(
            "https://example.test/cif.gz", self.destination, opener=FakeOpener(FakeResponse(body))
        )
        self.assertEqual(result.feed_date, "261009")

    def test_a_web_page_is_refused_and_leaves_nothing_behind(self) -> None:
        page = b"<!DOCTYPE html><html><body>Sign in</body></html>"
        opener = FakeOpener(FakeResponse(page))
        with self.assertRaises(FeedValidationError) as caught:
            download_one("https://example.test/cif.gz", self.destination, opener=opener)
        self.assertIn("web page", str(caught.exception))
        self.assertFalse(self.destination.exists())
        self.assertFalse(any(self.destination.parent.iterdir()))

    def test_an_empty_download_is_refused(self) -> None:
        with self.assertRaises(FeedValidationError) as caught:
            download_one(
                "https://example.test/cif.gz",
                self.destination,
                opener=FakeOpener(FakeResponse(b"")),
            )
        self.assertIn("is empty", str(caught.exception))

    def test_a_refusal_names_the_environment_variable_and_not_the_password(self) -> None:
        error = urllib.error.HTTPError("https://example.test/cif.gz", 403, "Forbidden", {}, None)
        with self.assertRaises(DownloadError) as caught:
            download_one(
                "https://example.test/cif.gz",
                self.destination,
                username="someone",
                password="hunter2",
                opener=FakeOpener(error),
            )
        message = str(caught.exception)
        self.assertIn("SCHEDULE_USERNAME", message)
        self.assertNotIn("hunter2", message)

    def test_a_transient_refusal_is_tried_again(self) -> None:
        body = gzipped_fixture(self.root / "fixture")
        busy = urllib.error.HTTPError("https://example.test/cif.gz", 503, "Service Unavailable", {}, None)
        opener = FakeOpener(busy, FakeResponse(body))
        result = download_one("https://example.test/cif.gz", self.destination, opener=opener, retries=2)
        self.assertEqual(len(opener.requests), 2)
        self.assertEqual(result.bytes, len(body))

    def test_a_truncated_archive_is_caught_by_the_parser_that_reads_it(self) -> None:
        body = gzipped_fixture(self.root / "fixture")
        # The head of a truncated gzip is still a valid head, so the fetch
        # accepts it: what refuses it is the load, which is where the whole file
        # is read. Naming that here is what keeps the failure from looking like
        # a fetch that did not check.
        opener = FakeOpener(FakeResponse(body[:-40]))
        download_one("https://example.test/cif.gz", self.destination, opener=opener)
        with self.assertRaises(ValueError) as caught:
            TimetableDb().load_feed(self.destination.parent)
        self.assertIn("not readable as gzip", str(caught.exception))

    def test_a_second_feed_beside_the_first_is_named(self) -> None:
        body = gzipped_fixture(self.root / "fixture")
        download_one("https://example.test/cif.gz", self.destination, opener=FakeOpener(FakeResponse(body)))
        (self.destination.parent / "timetable.mca").write_text("HD", encoding="utf-8")
        self.assertEqual(_other_feeds(self.destination), ["timetable.mca"])
        self.assertEqual(_other_feeds(self.root / "nowhere" / "missing.CIF.gz"), [])


class ValidateDownloadTest(unittest.TestCase):
    def test_a_plain_ungzipped_cif_is_a_feed(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            feed = build_synthetic_whole_cif(Path(folder), gzipped=False)
            line = validate_download(Path(feed) / "CIF_ALL_FULL_DAILY_toc-full.CIF")
            self.assertTrue(line.startswith("HD"))

    def test_a_gzip_that_is_a_gzip_and_nothing_else_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "nwr-schedule.CIF.gz"
            with gzip.open(path, "wb") as handle:
                handle.write(b"not a CIF at all\n")
            with self.assertRaises(FeedValidationError) as caught:
                validate_download(path)
            self.assertIn("not a CIF record", str(caught.exception))


class CommandLineTest(unittest.TestCase):
    def test_no_url_says_where_a_url_comes_from(self) -> None:
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"SCHEDULE_URL": ""}), contextlib.redirect_stderr(stderr):
            code = main([])
        self.assertEqual(code, 2)
        self.assertIn("SCHEDULE_URL", stderr.getvalue())

    def test_a_failed_download_is_exit_one(self) -> None:
        stderr = io.StringIO()
        failure = DownloadError("the feed refused https://example.test/cif.gz (HTTP 403)")
        with mock.patch("schedule_download.download_one", side_effect=failure):
            with contextlib.redirect_stderr(stderr):
                code = main(["--url", "https://example.test/cif.gz"])
        self.assertEqual(code, 1)
        self.assertIn("schedule download failed", stderr.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
