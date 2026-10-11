"""Tests for the credential-safe NRDP downloader and DTD audit."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import tempfile
import unittest
import urllib.error
import urllib.parse
import zipfile
from dataclasses import asdict
from pathlib import Path
from unittest import mock

from dtd_audit import audit_dtd
from dtd_download import (
    AUTH_URL,
    DEFAULT_RETRIES,
    DTD_FEEDS,
    KB_FEEDS,
    RETRY_MAX_SECONDS,
    AuthenticationError,
    DownloadError,
    EntitlementError,
    FeedValidationError,
    DownloadResult,
    _backoff_seconds,
    authenticate,
    download_one,
    feed_fingerprint,
    previous_records,
    write_manifest,
)
from dtd_download import main as dtd_download_main
from make_synthetic_feed import build_synthetic_feed, build_synthetic_timetable


class FakeResponse:
    def __init__(
        self,
        body: bytes,
        *,
        status: int = 200,
        content_type: str = "",
        url: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.body = io.BytesIO(body)
        self.status = status
        self.headers = dict(headers) if headers else {}
        if content_type:
            self.headers["Content-Type"] = content_type
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
        self.requests.append((request, timeout))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if isinstance(response, FakeResponse) and not response.url:
            response.url = request.full_url
        return response


def zip_bytes(*names: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name in names:
            archive.writestr(name, b"fixture")
    return output.getvalue()


def empty_zip_bytes(*names: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name in names:
            archive.writestr(name, b"")
    return output.getvalue()


# The digest of a manifest that names no feeds at all. A build compares against
# it, so a first run and a damaged cache both read as a change.
_EMPTY_FINGERPRINT = feed_fingerprint("does-not-exist.json")
_SOME_FINGERPRINT = "0" * 64


def _response(request, headers: dict[str, str]) -> FakeResponse:
    """A 200 for whichever feed was asked for, carrying *headers*."""

    body = (
        zip_bytes("RJFAF.FFL")
        if "fares" in request.full_url
        else zip_bytes("RJTTF.MCA", "RJTTF.MSN")
    )
    response = FakeResponse(body, content_type="application/zip", headers=headers)
    response.url = request.full_url
    return response


def _raise_timeout():
    raise TimeoutError("the request timed out")


def _previous_record(destination: Path, body: bytes, **overrides) -> DownloadResult:
    """A truthful record of *body* sitting at *destination*.

    Truthful matters: the downloader checks the file on disk against this
    record before believing a 304, so a fabricated digest would be caught --
    correctly -- and the test would be testing its own fixture.
    """

    record = {
        "name": "fares",
        "source": "dtd",
        "url": DTD_FEEDS[0].url,
        "path": str(destination),
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "content_type": "application/zip",
        "downloaded_at": "2026-09-20T00:00:00Z",
        "etag": '"v1"',
    }
    record.update(overrides)
    return DownloadResult(**record)


class AuthenticationTest(unittest.TestCase):
    def test_credentials_are_read_from_the_environment_and_not_logged(self) -> None:
        fake = FakeOpener(FakeResponse(b'{"token":"short-lived-token"}', content_type="application/json"))
        with mock.patch.dict(
            os.environ,
            {"NRDP_USERNAME": "alice", "NRDP_PASSWORD": "do-not-print-me"},
            clear=False,
        ):
            token = authenticate(opener=fake)

        self.assertEqual(token, "short-lived-token")
        request = fake.requests[0][0]
        fields = urllib.parse.parse_qs(request.data.decode("utf-8"))
        self.assertEqual(fields, {"username": ["alice"], "password": ["do-not-print-me"]})
        self.assertNotIn("do-not-print-me", str(token))

    def test_missing_environment_credentials_fail_before_a_request(self) -> None:
        fake = FakeOpener()
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(AuthenticationError, "NRDP_USERNAME"):
                authenticate(opener=fake)
        self.assertEqual(fake.requests, [])

    def test_authentication_http_failure_is_not_reported_as_an_empty_feed(self) -> None:
        error = urllib.error.HTTPError(AUTH_URL, 401, "Unauthorized", {}, None)
        with self.assertRaises(AuthenticationError):
            authenticate("alice", "secret", opener=FakeOpener(error))

    def test_invalid_auth_response_does_not_echo_the_password(self) -> None:
        fake = FakeOpener(FakeResponse(b"not-json", content_type="text/html"))
        with self.assertRaises(AuthenticationError) as raised:
            authenticate("alice", "super-secret", opener=fake)
        self.assertNotIn("super-secret", str(raised.exception))


class DownloadSafetyTest(unittest.TestCase):
    def test_valid_dtd_zip_is_replaced_atomically_and_carries_only_the_token_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "fares" / "dtd-fares.zip"
            destination.parent.mkdir()
            destination.write_bytes(b"previous-good-file")
            fake = FakeOpener(FakeResponse(zip_bytes("RJFAF.FFL", "RJFAF.LOC")))
            result = download_one(DTD_FEEDS[0], destination, "token-value", opener=fake)

            with zipfile.ZipFile(destination) as archive:
                self.assertEqual(archive.namelist(), ["RJFAF.FFL", "RJFAF.LOC"])
            self.assertEqual(result.name, "fares")
            self.assertEqual(result.bytes, destination.stat().st_size)
            request = fake.requests[0][0]
            self.assertEqual(request.get_header("X-auth-token"), "token-value")
            self.assertNotIn("token-value", str(result))
            self.assertEqual(list(destination.parent.glob("*.part")), [])

    def test_error_page_does_not_overwrite_a_good_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "dtd-fares.zip"
            destination.write_bytes(b"known-good")
            fake = FakeOpener(FakeResponse(b"<html>login required</html>", content_type="text/html"))
            with self.assertRaises(FeedValidationError):
                download_one(DTD_FEEDS[0], destination, "token", opener=fake)
            self.assertEqual(destination.read_bytes(), b"known-good")
            self.assertEqual(list(destination.parent.glob("*.part")), [])

    def test_empty_or_unrecognised_zip_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "dtd-timetable.zip"
            for body in (zip_bytes(), zip_bytes("README.txt")):
                with self.subTest(body=body[:4]):
                    with self.assertRaises(FeedValidationError):
                        download_one(
                            DTD_FEEDS[1],
                            destination,
                            "token",
                            opener=FakeOpener(FakeResponse(body)),
                        )
                    self.assertFalse(destination.exists())

    def test_feed_403_explains_possible_dtd_entitlement_without_echoing_a_body(self) -> None:
        error = urllib.error.HTTPError(DTD_FEEDS[0].url, 403, "Forbidden", {}, None)
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "dtd-fares.zip"
            destination.write_bytes(b"keep-me")
            with self.assertRaisesRegex(EntitlementError, "Fares, Routeing Guide and Timetable data"):
                download_one(DTD_FEEDS[0], destination, "token", opener=FakeOpener(error))
            self.assertEqual(destination.read_bytes(), b"keep-me")

    def test_knowledgebase_xml_is_validated_and_destination_is_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "knowledgebase" / "stations.xml"
            fake = FakeOpener(FakeResponse(b"<stations><station/></stations>", content_type="application/xml"))
            result = download_one(KB_FEEDS[-1], destination, "token", opener=fake)
            self.assertEqual(result.source, "knowledgebase")
            self.assertEqual(destination.read_bytes(), b"<stations><station/></stations>")

    def test_manifest_contains_provenance_but_no_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "fares" / "dtd-fares.zip"
            result = download_one(
                DTD_FEEDS[0],
                destination,
                "secret-token",
                opener=FakeOpener(FakeResponse(zip_bytes("RJFAF.FFL"))),
            )
            manifest = write_manifest([result], tmp)
            text = manifest.read_text(encoding="utf-8")
            self.assertIn("RJFAF.FFL", text)
            self.assertNotIn("secret-token", text)
            self.assertNotIn("NRDP_PASSWORD", text)

    def test_separate_downloads_merge_manifest_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fares = download_one(
                DTD_FEEDS[0],
                Path(tmp) / "fares" / "dtd-fares.zip",
                "token",
                opener=FakeOpener(FakeResponse(zip_bytes("RJFAF.FFL"))),
            )
            write_manifest([fares], tmp)
            timetable = download_one(
                DTD_FEEDS[1],
                Path(tmp) / "timetable" / "dtd-timetable.zip",
                "token",
                opener=FakeOpener(FakeResponse(zip_bytes("timetable.MCA", "stations.MSN"))),
            )
            manifest = write_manifest([timetable], tmp)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual({entry["name"] for entry in payload["downloads"]}, {"fares", "timetable"})
            self.assertNotIn("token", manifest.read_text(encoding="utf-8"))


class ConditionalRequestTest(unittest.TestCase):
    """A 304 is an answer, and it has to be answered correctly.

    The properties under test are all about not deceiving the reader: a feed
    the portal did not republish must keep the date it was published, and a
    file that has been deleted must never be "confirmed unchanged".
    """

    def _download(self, tmp: str, *responses, **kwargs):
        destination = Path(tmp) / "fares" / "dtd-fares.zip"
        fake = FakeOpener(*responses)
        return download_one(
            DTD_FEEDS[0], destination, "token", opener=fake, sleep=lambda _s: None, **kwargs
        ), destination, fake

    def test_unchanged_feed_keeps_its_file_and_its_original_download_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            body = zip_bytes("RJFAF.FFL")
            first, destination, _ = self._download(
                tmp,
                FakeResponse(
                    body,
                    headers={"ETag": '"v1"', "Last-Modified": "Wed, 24 Sep 2026 09:00:00 GMT"},
                ),
            )
            self.assertFalse(first.unchanged)
            self.assertEqual(first.etag, '"v1"')
            with zipfile.ZipFile(destination) as archive:
                self.assertEqual(archive.namelist(), ["RJFAF.FFL"])

            not_modified = urllib.error.HTTPError(
                DTD_FEEDS[0].url, 304, "Not Modified", {}, None
            )
            second, destination, fake = self._download(
                tmp, not_modified, previous=asdict(first)
            )
            self.assertTrue(second.unchanged)
            self.assertEqual(second.downloaded_at, first.downloaded_at)
            # The whole point: the 304 is recorded, but not as a new download.
            self.assertNotEqual(second.checked_at, first.checked_at)
            # The file is untouched, so a page built from it still knows how old
            # the data is; and no full download happened.
            self.assertEqual(len(fake.requests), 1)
            self.assertEqual(destination.read_bytes(), body)

    def test_the_validator_headers_are_sent_only_when_there_is_a_record_and_a_file(self) -> None:
        record = {"etag": '"abc"', "last_modified": "Wed, 24 Sep 2026 09:00:00 GMT"}
        body = zip_bytes("RJFAF.FFL")

        # No record at all: a first run asks nothing and fetches in full.
        with tempfile.TemporaryDirectory() as tmp:
            _, _, first = self._download(tmp, FakeResponse(body))
            request = first.requests[0][0]
            self.assertIsNone(request.get_header("If-none-match"))
            self.assertIsNone(request.get_header("If-modified-since"))

            # A record and the file it describes: the question is asked.
            _, _, conditional = self._download(tmp, FakeResponse(body), previous=record)
            request = conditional.requests[0][0]
            self.assertEqual(request.get_header("If-none-match"), '"abc"')
            self.assertEqual(
                request.get_header("If-modified-since"), "Wed, 24 Sep 2026 09:00:00 GMT"
            )

            # A record but the file has been deleted. "Unchanged" would be a
            # lie that leaves nothing to build from, so the validators are
            # withheld and the feed is fetched in full.
            (Path(tmp) / "fares" / "dtd-fares.zip").unlink()
            _, _, missing = self._download(tmp, FakeResponse(body), previous=record)
            request = missing.requests[0][0]
            self.assertIsNone(request.get_header("If-none-match"))
            self.assertIsNone(request.get_header("If-modified-since"))
            self.assertTrue((Path(tmp) / "fares" / "dtd-fares.zip").is_file())

    def test_a_portal_ignoring_the_headers_still_downloads_in_full(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            body = zip_bytes("RJFAF.FFL")
            result, destination, _ = self._download(
                tmp, FakeResponse(body), previous={"etag": '"stale"'}
            )
            self.assertFalse(result.unchanged)
            self.assertNotEqual(result.downloaded_at, "")
            self.assertEqual(destination.read_bytes(), body)

    def test_manifest_records_validators_and_survives_a_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result, destination, _ = self._download(
                tmp,
                FakeResponse(
                    zip_bytes("RJFAF.FFL"),
                    headers={"ETag": '"v2"', "Last-Modified": "Wed, 24 Sep 2026 09:00:00 GMT"},
                ),
            )
            write_manifest([result], tmp)
            records = previous_records(tmp)
            self.assertEqual(records["fares"]["etag"], '"v2"')
            self.assertEqual(
                records["fares"]["last_modified"], "Wed, 24 Sep 2026 09:00:00 GMT"
            )
            # No secret travelled with the validators.
            text = (Path(tmp) / "download-manifest.json").read_text(encoding="utf-8")
            self.assertNotIn("token", text)
            self.assertTrue(destination.exists())

    def test_a_corrupt_manifest_does_not_send_nonsense_validators(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "download-manifest.json").write_text("{not json", encoding="utf-8")
            self.assertEqual(previous_records(tmp), {})
            (Path(tmp) / "download-manifest.json").write_text(
                json.dumps({"downloads": [{"name": "fares", "etag": 12, "last_modified": None}]}),
                encoding="utf-8",
            )
            record = previous_records(tmp)["fares"]
            self.assertNotIn("etag", record)
            self.assertNotIn("last_modified", record)


class RetryTest(unittest.TestCase):
    def test_a_transient_failure_is_retried_and_then_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "fares" / "dtd-fares.zip"
            destination.parent.mkdir(parents=True)
            body = zip_bytes("RJFAF.FFL")
            fake = FakeOpener(
                TimeoutError("timed out"),
                urllib.error.HTTPError(DTD_FEEDS[0].url, 503, "Unavailable", {}, None),
                FakeResponse(body),
            )
            waits: list[float] = []
            result = download_one(
                DTD_FEEDS[0], destination, "token", opener=fake, sleep=waits.append
            )
            self.assertEqual(destination.read_bytes(), body)
            self.assertEqual(result.bytes, len(body))
            self.assertEqual(len(fake.requests), 3)
            # Grows, and never exceeds the cap.
            self.assertEqual(waits, [2.0, 4.0])

    def test_a_refusal_is_not_retried(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "fares" / "dtd-fares.zip"
            destination.parent.mkdir(parents=True)
            destination.write_bytes(b"known-good")
            for status, expected in (
                (403, EntitlementError),
                (404, DownloadError),
                (400, DownloadError),
            ):
                with self.subTest(status=status):
                    fake = FakeOpener(
                        urllib.error.HTTPError(
                            DTD_FEEDS[0].url, status, "no", {}, None
                        )
                    )
                    with self.assertRaises(expected):
                        download_one(
                            DTD_FEEDS[0],
                            destination,
                            "token",
                            opener=fake,
                            sleep=lambda _s: None,
                        )
                    self.assertEqual(len(fake.requests), 1)
                    self.assertEqual(destination.read_bytes(), b"known-good")

    def test_retries_are_bounded_and_the_wait_is_capped(self) -> None:
        self.assertEqual(_backoff_seconds(0), 2.0)
        self.assertEqual(_backoff_seconds(1), 4.0)
        self.assertEqual(_backoff_seconds(2), 8.0)
        self.assertEqual(_backoff_seconds(10), RETRY_MAX_SECONDS)
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeOpener(*[TimeoutError("t")] * 6)
            waits: list[float] = []
            with self.assertRaises(DownloadError):
                download_one(
                    DTD_FEEDS[0],
                    Path(tmp) / "dtd-fares.zip",
                    "token",
                    opener=fake,
                    sleep=waits.append,
                )
            self.assertEqual(len(fake.requests), DEFAULT_RETRIES + 1)
            self.assertEqual(len(waits), DEFAULT_RETRIES)

    def test_a_validated_but_wrong_response_is_not_retried(self) -> None:
        # An HTML page behind a 200 is a portal problem, not a flaky network.
        # Retrying it would just waste the run and hide the real fault.
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeOpener(FakeResponse(b"<html>error</html>", content_type="text/html"))
            with self.assertRaises(FeedValidationError):
                download_one(
                    DTD_FEEDS[0],
                    Path(tmp) / "dtd-fares.zip",
                    "token",
                    opener=fake,
                    sleep=lambda _s: None,
                )
            self.assertEqual(len(fake.requests), 1)


class UnbelievableAnswerTest(unittest.TestCase):
    """A 304 the disk does not support is not an answer, it is a stale file.

    Believing it would leave a manifest asserting a digest for a file that does
    not have it, and would go on asserting it daily for as long as the portal
    declined to republish -- which for a national feed can be weeks.
    """

    def _written(self, tmp: str) -> tuple[DownloadResult, Path]:
        destination = Path(tmp) / "fares" / "dtd-fares.zip"
        destination.parent.mkdir(parents=True, exist_ok=True)
        result = download_one(
            DTD_FEEDS[0],
            destination,
            "token",
            opener=FakeOpener(FakeResponse(zip_bytes("RJFAF.FFL"), headers={"ETag": '"v1"'})),
            sleep=lambda _s: None,
        )
        return result, destination

    def _then_304_then_200(self, *extra_responses):
        responses = [
            urllib.error.HTTPError(DTD_FEEDS[0].url, 304, "Not Modified", {}, None),
            *extra_responses,
        ]
        return FakeOpener(*responses)

    def test_a_truncated_file_is_fetched_again_rather_than_trusted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first, destination = self._written(tmp)
            destination.write_bytes(b"truncated")
            body = zip_bytes("RJFAF.FFL")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                second = download_one(
                    DTD_FEEDS[0],
                    destination,
                    "token",
                    opener=self._then_304_then_200(FakeResponse(body)),
                    previous=asdict(first),
                    sleep=lambda _s: None,
                )
            self.assertFalse(second.unchanged)
            self.assertEqual(destination.read_bytes(), body)
            self.assertIn("downloading it in full", stderr.getvalue())

    def test_a_file_whose_contents_drifted_is_fetched_again(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first, destination = self._written(tmp)
            # Same length, different bytes: the size check alone would pass, so
            # the digest is what catches it.
            original = destination.read_bytes()
            destination.write_bytes(b"x" * len(original))
            self.assertEqual(destination.stat().st_size, first.bytes)
            body = zip_bytes("RJFAF.FFL")
            with contextlib.redirect_stderr(io.StringIO()):
                second = download_one(
                    DTD_FEEDS[0],
                    destination,
                    "token",
                    opener=self._then_304_then_200(FakeResponse(body)),
                    previous=asdict(first),
                    sleep=lambda _s: None,
                )
            self.assertFalse(second.unchanged)
            self.assertEqual(destination.read_bytes(), body)

    def test_a_deleted_file_is_fetched_again(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first, destination = self._written(tmp)
            destination.unlink()
            body = zip_bytes("RJFAF.FFL")
            with contextlib.redirect_stderr(io.StringIO()):
                second = download_one(
                    DTD_FEEDS[0],
                    destination,
                    "token",
                    opener=self._then_304_then_200(FakeResponse(body)),
                    previous=asdict(first),
                    sleep=lambda _s: None,
                )
            self.assertFalse(second.unchanged)
            self.assertEqual(destination.read_bytes(), body)

    def test_a_304_with_nothing_to_carry_forward_is_fetched_instead(self) -> None:
        # No validators were sent, so nothing was asked; a 304 here is a server
        # answering a question it was not asked. Inventing a record from it
        # would put an empty digest in a manifest, so the answer is declined
        # and the feed is fetched.
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "fares" / "dtd-fares.zip"
            destination.parent.mkdir(parents=True)
            destination.write_bytes(b"whatever")
            body = zip_bytes("RJFAF.FFL")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = download_one(
                    DTD_FEEDS[0],
                    destination,
                    "token",
                    opener=self._then_304_then_200(FakeResponse(body)),
                    sleep=lambda _s: None,
                )
            self.assertFalse(result.unchanged)
            self.assertIn("asked no question", stderr.getvalue())
            self.assertEqual(destination.read_bytes(), body)


    def test_a_portal_that_answers_304_to_anything_fails_by_name(self) -> None:
        # The pathological server: 304 to everything, asked or not. It must end
        # as a named failure for this feed, not as an exception the command
        # loop does not catch and the operator reads as a traceback.
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "fares" / "dtd-fares.zip"
            destination.parent.mkdir(parents=True)
            destination.write_bytes(b"whatever")
            always = FakeOpener(
                *[
                    urllib.error.HTTPError(DTD_FEEDS[0].url, 304, "Not Modified", {}, None)
                    for _ in range(3)
                ]
            )
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaisesRegex(DownloadError, "asked no question"):
                    download_one(
                        DTD_FEEDS[0], destination, "token", opener=always, sleep=lambda _s: None
                    )


class FingerprintTest(unittest.TestCase):
    """What the build compares to decide the feeds changed.

    A build that re-reads the same prices must not rebuild the site, so the
    fingerprint has to ignore the record of *checking* the portal and follow
    the record of what the portal published.
    """

    def _feed(self, tmp: str, *, etag: str) -> dict[str, object]:
        destination = Path(tmp) / "fares" / "dtd-fares.zip"
        destination.parent.mkdir(parents=True, exist_ok=True)
        body = zip_bytes("RJFAF.FFL")
        destination.write_bytes(body)
        result = download_one(
            DTD_FEEDS[0],
            destination,
            "token",
            opener=FakeOpener(FakeResponse(body, headers={"ETag": etag})),
            sleep=lambda _s: None,
        )
        write_manifest([result], tmp)
        return result

    def _fingerprint(self, tmp: str) -> str:
        return feed_fingerprint(Path(tmp) / "download-manifest.json")

    def test_an_unchanged_feed_keeps_its_fingerprint_although_the_manifest_moved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = self._feed(tmp, etag='"v1"')
            before = self._fingerprint(tmp)

            not_modified = urllib.error.HTTPError(
                DTD_FEEDS[0].url, 304, "Not Modified", {}, None
            )
            second = download_one(
                DTD_FEEDS[0],
                Path(tmp) / "fares" / "dtd-fares.zip",
                "token",
                opener=FakeOpener(not_modified),
                previous=previous_records(tmp)["fares"],
                sleep=lambda _s: None,
            )
            write_manifest([second], tmp)

            # The manifest's own bytes are different -- that is the whole trap.
            manifest = json.loads(
                (Path(tmp) / "download-manifest.json").read_text(encoding="utf-8")
            )
            self.assertTrue(second.unchanged)
            self.assertNotEqual(manifest["downloads"][0]["checked_at"], "")
            self.assertNotEqual(manifest["downloads"][0]["downloaded_at"], "")
            # But what the feeds are has not moved, so the site is not rebuilt.
            self.assertEqual(self._fingerprint(tmp), before)
            self.assertEqual(second.downloaded_at, first.downloaded_at)

    def test_a_republished_feed_changes_the_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._feed(tmp, etag='"v1"')
            before = self._fingerprint(tmp)
            self._feed(tmp, etag='"v2"')
            self.assertNotEqual(self._fingerprint(tmp), before)

    def test_a_missing_or_damaged_manifest_is_a_change_not_a_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(feed_fingerprint(Path(tmp) / "absent.json"), _EMPTY_FINGERPRINT)
            (Path(tmp) / "download-manifest.json").write_text("{not json", encoding="utf-8")
            self.assertEqual(self._fingerprint(tmp), _EMPTY_FINGERPRINT)
            self.assertNotEqual(self._fingerprint(tmp), _SOME_FINGERPRINT)

    def test_the_fingerprint_needs_no_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._feed(tmp, etag='"v1"')
            printed = io.StringIO()
            # No NRDP_USERNAME, no NRDP_PASSWORD: a build has to be able to ask
            # "did anything change?" without holding the portal's credentials.
            with mock.patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(printed):
                status = dtd_download_main(
                    ["--print-fingerprint", str(Path(tmp) / "download-manifest.json")]
                )
            self.assertEqual(status, 0)
            self.assertEqual(printed.getvalue().strip(), self._fingerprint(tmp))


class CommandLineTest(unittest.TestCase):
    """The flags an unattended job is driven with."""

    def _args(self, tmp: str, *extra: str) -> list[str]:
        return ["--output-root", tmp, *extra]

    def _patched_auth(self, token: str = "short-lived"):
        return mock.patch("dtd_download.authenticate", return_value=token)

    def _no_sleeping(self):
        """Stop the retry backoff from being real inside a unit test."""

        return mock.patch("dtd_download.time.sleep", return_value=None)

    def test_retries_cannot_be_negative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = dtd_download_main(self._args(tmp, "--retries", "-1"))
            self.assertEqual(status, 2)
            self.assertIn("--retries cannot be negative", stderr.getvalue())

    def test_no_conditional_forces_a_full_download(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "fares" / "dtd-fares.zip"
            destination.parent.mkdir(parents=True)
            body = zip_bytes("RJFAF.FFL")
            destination.write_bytes(body)
            write_manifest([_previous_record(destination, body)], tmp)
            not_modified = urllib.error.HTTPError(
                DTD_FEEDS[0].url, 304, "Not Modified", {}, None
            )
            # Left to itself the run asks the question and believes the 304.
            offered: list[str] = []

            def conditional(request, timeout):
                offered.append(request.get_header("If-none-match") or "-")
                raise not_modified

            with self._patched_auth(), mock.patch(
                "dtd_download.urlopen", side_effect=conditional
            ), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(dtd_download_main(self._args(tmp, "--dtd", "fares")), 0)
            self.assertEqual(offered, ['"v1"'])

            # With --no-conditional the question is never asked, which is the
            # escape hatch for a local file that has gone bad underneath us.
            offered.clear()
            with self._patched_auth(), mock.patch(
                "dtd_download.urlopen",
                side_effect=lambda request, timeout: offered.append(
                    request.get_header("If-none-match") or "-"
                )
                or _response(request, {"ETag": '"v2"'}),
            ), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    dtd_download_main(self._args(tmp, "--dtd", "fares", "--no-conditional")), 0
                )
            self.assertEqual(offered, ["-"])
            self.assertEqual(previous_records(tmp)["fares"]["etag"], '"v2"')

    def test_an_unchanged_feed_is_reported_as_unchanged_not_as_a_download(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "fares" / "dtd-fares.zip"
            destination.parent.mkdir(parents=True)
            body = zip_bytes("RJFAF.FFL")
            destination.write_bytes(body)
            write_manifest([_previous_record(destination, body)], tmp)
            not_modified = urllib.error.HTTPError(
                DTD_FEEDS[0].url, 304, "Not Modified", {}, None
            )
            printed = io.StringIO()
            with self._patched_auth(), mock.patch(
                "dtd_download.urlopen", side_effect=not_modified
            ), contextlib.redirect_stdout(printed):
                self.assertEqual(dtd_download_main(self._args(tmp, "--dtd", "fares")), 0)
            output = printed.getvalue()
            self.assertIn("fares: unchanged since 2026-09-20T00:00:00Z", output)
            self.assertNotIn("downloaded", output)

    def test_a_second_run_revalidates_from_the_manifest_the_first_run_wrote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            headers = {"ETag": '"v1"'}
            for run in range(2):
                with self._patched_auth(), mock.patch(
                    "dtd_download.urlopen",
                    side_effect=lambda request, timeout: _response(request, headers),
                ), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(dtd_download_main(self._args(tmp, "--dtd", "fares")), 0)
            # The second run offered the validator the first run recorded.
            self.assertEqual(previous_records(tmp)["fares"]["etag"], '"v1"')
            self.assertTrue((Path(tmp) / "fares" / "dtd-fares.zip").is_file())

    def test_each_feed_is_offered_its_own_previous_record(self) -> None:
        # The daily job takes `--dtd all`, so the multi-feed wiring is proved
        # against the command rather than against a function nothing calls. A
        # wiring mistake here shows up as a full re-download every day, which
        # is invisible rather than wrong.
        with tempfile.TemporaryDirectory() as tmp:
            fares_destination = Path(tmp) / "fares" / "dtd-fares.zip"
            fares_destination.parent.mkdir(parents=True)
            fares_body = zip_bytes("RJFAF.FFL")
            fares_destination.write_bytes(fares_body)
            # Only fares has been downloaded before. The timetable feed must not
            # be sent fares' validators, which would be a question about the
            # wrong object and could earn a 304 that leaves it missing.
            write_manifest(
                [
                    _previous_record(
                        fares_destination, fares_body, etag='"fares-v1"'
                    )
                ],
                tmp,
            )
            offered: list[str] = []

            def opener(request, timeout):
                offered.append(request.get_header("If-none-match") or "-")
                body = (
                    zip_bytes("RJFAF.FFL")
                    if "fares" in request.full_url
                    else zip_bytes("RJTTF.MCA", "RJTTF.MSN")
                )
                response = FakeResponse(body, content_type="application/zip")
                response.url = request.full_url
                return response

            with self._patched_auth(), mock.patch(
                "dtd_download.urlopen", side_effect=opener
            ), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(dtd_download_main(self._args(tmp, "--dtd", "all")), 0)
            self.assertEqual(offered, ['"fares-v1"', "-"])
            # And the manifest now describes both, for the next run to read.
            self.assertEqual(set(previous_records(tmp)), {"fares", "timetable"})

    def test_a_failed_feed_is_reported_and_the_run_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stderr = io.StringIO()
            attempts: list[int] = []
            with self._patched_auth(), self._no_sleeping(), mock.patch(
                "dtd_download.urlopen",
                side_effect=lambda request, timeout: attempts.append(1) or _raise_timeout(),
            ), contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(dtd_download_main(self._args(tmp, "--dtd", "fares")), 1)
            self.assertIn("fares: failed:", stderr.getvalue())
            # A timeout is retried before the day is given up on.
            self.assertEqual(len(attempts), DEFAULT_RETRIES + 1)


class DtdAuditTest(unittest.TestCase):
    def test_audit_distinguishes_missing_and_empty_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fares = Path(tmp) / "fares"
            timetable = Path(tmp) / "timetable"
            fares.mkdir()
            timetable.mkdir()
            report = audit_dtd(fares, timetable)
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["checks"]["fares"]["status"], "empty")
            self.assertEqual(report["checks"]["timetable"]["status"], "empty")

    def test_audit_rejects_a_folder_that_mixes_old_and_new_feed_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fares = Path(tmp) / "fares"
            fares.mkdir()
            (fares / "RJFAF.FFL").write_text("old")
            (fares / "dtd-fares.zip").write_bytes(zip_bytes("RJFAF.FFL"))
            timetable = build_synthetic_timetable(Path(tmp) / "timetable")
            report = audit_dtd(fares, timetable)
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["checks"]["fares"]["status"], "mixed")

    def test_audit_does_not_call_recognized_but_empty_archives_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fares = Path(tmp) / "fares.zip"
            timetable = Path(tmp) / "timetable.zip"
            fares.write_bytes(empty_zip_bytes("RJFAF.FFL", "RJFAF.LOC"))
            timetable.write_bytes(empty_zip_bytes("timetable.MCA", "stations.MSN"))
            report = audit_dtd(fares, timetable)
            self.assertEqual(report["status"], "failed")
            self.assertTrue(any("empty" in error for error in report["errors"]))

    def test_audit_loads_the_existing_synthetic_fixture_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fares = build_synthetic_feed(Path(tmp) / "fares", include_restrictions=True)
            timetable = build_synthetic_timetable(Path(tmp) / "timetable")
            report = audit_dtd(fares, timetable)
            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["checks"]["fares"]["status"], "ok")
            self.assertEqual(report["checks"]["timetable"]["status"], "ok")
            self.assertEqual(report["fares_report"]["files"], 6)
            self.assertEqual(report["timetable_report"]["files"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
