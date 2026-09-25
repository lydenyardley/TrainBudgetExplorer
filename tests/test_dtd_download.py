"""Tests for the credential-safe NRDP downloader and DTD audit."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
import urllib.error
import urllib.parse
import zipfile
from pathlib import Path
from unittest import mock

from dtd_audit import audit_dtd
from dtd_download import (
    AUTH_URL,
    DTD_FEEDS,
    KB_FEEDS,
    AuthenticationError,
    EntitlementError,
    FeedValidationError,
    authenticate,
    download_one,
    write_manifest,
)
from make_synthetic_feed import build_synthetic_feed, build_synthetic_timetable


class FakeResponse:
    def __init__(self, body: bytes, *, status: int = 200, content_type: str = "", url: str = "") -> None:
        self.body = io.BytesIO(body)
        self.status = status
        self.headers = {"Content-Type": content_type} if content_type else {}
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
