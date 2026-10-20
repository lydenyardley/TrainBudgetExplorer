"""Fetch Network Rail's own CIF schedule from a URL, and refuse anything else.

The timetable a release may publish comes from Network Rail's Schedule feed
under the Open Government Licence. The DTD timetable product carries the same
CIF under a licence whose Schedule 1 §5 allows internal business purposes only,
so changing the source is what makes publishing times possible at all
(``docs/dtd-licensing-and-data-access.md``).

Where the file lives is a separate question from what may be done with it, and
it is the owner's to answer: Network Rail's data feed answers HTTP Basic and
redirects to a signed S3 URL, the Rail Data Marketplace hands the same file out
through its dashboard, and a copy at any other URL would do just as well. So
this command takes a URL and an optional credential and knows nothing else about
the source. The one thing it does know is that the credential must not travel
through the redirect: S3 refuses a request carrying both a signature in the
query and an ``Authorization`` header, and urllib's default redirect handler
copies the headers onto the new request.

A download is not a feed until it has been read. The bytes are streamed to a
temporary name beside the destination, then decompressed far enough to see a CIF
record, and only then moved into place: half a schedule publishes as confidently
as a whole one, and it is wrong more often.

``--probe`` is the same address and credential asked for two bytes, so a wrong
URL or an account the feed refuses costs one request rather than a run that has
already spent its minutes on the feeds beside it.

Credentials come from ``SCHEDULE_USERNAME`` and ``SCHEDULE_PASSWORD``, never
from the command line, and are never written to a log, a message, or the
downloaded copy of the file. The URL is only ever printed without its query
string, because a signed URL's query is the credential.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import http.client
import os
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator
from urllib.parse import urlsplit, urlunsplit

from atoc_timetable import CIF_HEADER_OFFSETS, CIF_RECORD_TYPES

DEFAULT_OUT = "feeds/timetable-nwr/nwr-schedule.CIF.gz"
DEFAULT_TIMEOUT = 120.0
DEFAULT_RETRIES = 3
RETRY_BASE_SECONDS = 2.0
RETRY_MAX_SECONDS = 20.0
CHUNK_SIZE = 1024 * 1024
# The CIF full extract is about 100 MB compressed and the JSON beside it about
# 140 MB, so this is a guard against a wrong URL answering with something
# enormous rather than a budget.
MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024 * 1024
GZIP_MAGIC = b"\x1f\x8b"
TRANSIENT_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
# Extensions the timetable loader reads out of one folder. A second one beside
# the file means two timetables, which the loader would read as one.
FEED_SUFFIXES = (".cif", ".mca", ".cfa", ".ztr", ".msn")


class DownloadError(RuntimeError):
    """The file did not arrive."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class FeedValidationError(DownloadError):
    """The file arrived and is not a schedule."""


@dataclass(frozen=True)
class ScheduleDownload:
    """Non-secret information about one completed download."""

    path: str
    source: str
    final_url: str
    bytes: int
    sha256: str
    feed_date: str
    downloaded_at: str


class _DropAuthRedirect(urllib.request.HTTPRedirectHandler):
    """Follow a redirect without the credential that opened the door.

    Network Rail's feed answers an authenticated request with a 302 to a signed
    S3 URL, and only one authentication mechanism may be presented at a time:
    S3's "Only one auth mechanism allowed" is what it says when the header
    arrives with the signature. The caller cannot fix this, because the header is
    copied onto the redirect by urllib itself.
    """

    def redirect_request(self, request, fp, code, message, headers, newurl):
        redirected = super().redirect_request(request, fp, code, message, headers, newurl)
        if redirected is not None:
            redirected.remove_header("Authorization")
        return redirected


def _urlopen(request: urllib.request.Request, timeout: float):
    return urllib.request.build_opener(_DropAuthRedirect()).open(request, timeout=timeout)


# ``urlopen`` is a module attribute so the HTTP seam can be replaced in tests
# without the production code knowing a test client exists.
urlopen = _urlopen
Opener = Callable[..., object]


def redacted(url: str) -> str:
    """A URL safe to print: the query string is where a signed credential sits."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _request(url: str, username: str, password: str) -> urllib.request.Request:
    request = urllib.request.Request(url, headers={"Accept-Encoding": "identity"})
    if username or password:
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        request.add_header("Authorization", f"Basic {token}")
    return request


def _response_status(response: object) -> int | None:
    value = getattr(response, "status", None)
    getter = getattr(response, "getcode", None)
    if value is None and callable(getter):
        value = getter()
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def _http_error(status: int | None, url: str, *, authenticating: bool) -> DownloadError:
    shown = f"HTTP {status}" if status is not None else "an HTTP error"
    if status in (401, 403):
        if authenticating:
            return DownloadError(
                f"the feed refused the credential for {redacted(url)} ({shown}); check "
                "SCHEDULE_USERNAME and SCHEDULE_PASSWORD, and that the account is "
                "subscribed to the feed this URL names"
            )
        return DownloadError(f"the feed refused {redacted(url)} ({shown})")
    return DownloadError(f"request to {redacted(url)} failed with {shown}", status=status)


def _check_status(response: object, url: str, *, authenticating: bool) -> None:
    status = _response_status(response)
    if status is None or 200 <= status < 300:
        return
    raise _http_error(status, url, authenticating=authenticating)


def _check_https(response: object, url: str) -> str:
    """Refuse a redirect that left HTTPS, and return where the response came from.

    The destination host cannot be known in advance -- it is a signed S3 URL --
    so the scheme is the one thing worth holding: a plain HTTP hop would put the
    schedule in the clear, and on a signed URL that costs more than the file.
    """
    getter = getattr(response, "geturl", None)
    final = str(getter() or "") if callable(getter) else ""
    if final and urlsplit(final).scheme != "https":
        raise DownloadError(f"{redacted(url)} redirected to a URL that is not https")
    return final or url


@contextmanager
def _open_response(opener: Opener | None, request: urllib.request.Request, timeout: float) -> Iterator[object]:
    """Open and always close a response, including a fake one."""
    client = opener or urlopen
    try:
        response = client(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        close = getattr(error, "close", None)
        if callable(close):
            close()
        # Never include the error body: an upstream error page can carry
        # account detail, and nothing here needs it to act.
        raise _http_error(error.code, request.full_url, authenticating="Authorization" in request.headers) from None
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as error:
        raise DownloadError(f"request to {redacted(request.full_url)} failed ({type(error).__name__})") from None
    try:
        yield response
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()


def _read_chunks(response: object, destination: Path) -> tuple[int, str]:
    """Stream a response to *destination* and return its size and SHA-256."""
    digest = hashlib.sha256()
    total = 0
    read = getattr(response, "read")
    with destination.open("wb") as handle:
        while True:
            try:
                chunk = read(CHUNK_SIZE)
            except (OSError, http.client.HTTPException) as error:
                raise DownloadError(
                    f"the download stopped early ({type(error).__name__})"
                ) from error
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_DOWNLOAD_BYTES:
                raise DownloadError(
                    f"the download passed {MAX_DOWNLOAD_BYTES} bytes; that is not a schedule feed"
                )
            digest.update(chunk)
            handle.write(chunk)
    return total, digest.hexdigest()


def _first_record(path: Path) -> str:
    """The first non-blank line of the download, gzipped or not.

    Only the head is read here. A truncated archive is what the parser finds
    when it reads the whole file, and it says so then: reading every byte twice
    in one command would buy a second message for the same fault.
    """
    with path.open("rb") as raw:
        magic = raw.read(len(GZIP_MAGIC))
        raw.seek(0)
        stream = gzip.GzipFile(fileobj=raw) if magic == GZIP_MAGIC else raw
        try:
            for line_bytes in stream:
                line = line_bytes.decode("utf-8", "replace").rstrip("\r\n")
                if line.strip():
                    return line
            return ""
        except (OSError, EOFError) as error:
            raise FeedValidationError(
                f"{path.name} is not readable as gzip ({type(error).__name__}: {error})"
            ) from error
        finally:
            if stream is not raw:
                stream.close()


def validate_download(path: str | Path, *, shown: str = "") -> str:
    """Refuse anything that is not a CIF, and return its first record line.

    *shown* names the file in the message. A download is validated under its
    temporary name, and "..nwr-schedule.CIF.gz.part is empty" would name a file
    that never appears in the feed folder.
    """
    path = Path(path)
    name = shown or path.name
    line = _first_record(path)
    if not line:
        raise FeedValidationError(f"{name} is empty")
    if line[:2] in CIF_RECORD_TYPES:
        return line
    if line.lstrip().startswith("<"):
        raise FeedValidationError(f"{name} is a web page or XML, not a schedule: {line[:60]!r}")
    raise FeedValidationError(f"{name} starts with {line[:60]!r}, which is not a CIF record")


def feed_date(line: str) -> str:
    """The header record's own extract date, YYMMDD, when the file has one."""
    if line[:2] != "HD":
        return ""
    start, end = CIF_HEADER_OFFSETS["extract_date"]
    return line[start:end].strip()


def _backoff_seconds(attempt: int) -> float:
    return min(RETRY_BASE_SECONDS * (2 ** (attempt - 1)), RETRY_MAX_SECONDS)


def _is_transient(error: DownloadError) -> bool:
    return error.status in TRANSIENT_STATUS


def download_one(
    url: str,
    destination: str | Path,
    *,
    username: str = "",
    password: str = "",
    opener: Opener | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> ScheduleDownload:
    """Fetch *url* to *destination*, atomically and only after reading it."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Beside the destination rather than in a temporary directory: the rename at
    # the end is atomic only within one filesystem.
    temporary = destination.with_name(f".{destination.name}.part")
    size, digest, line, final_url = 0, "", "", url
    try:
        request = _request(url, username, password)
        for attempt in range(1, retries + 1):
            try:
                with _open_response(opener, request, timeout) as response:
                    _check_status(response, url, authenticating=bool(username or password))
                    final_url = _check_https(response, url)
                    size, digest = _read_chunks(response, temporary)
                break
            except DownloadError as error:
                if attempt == retries or not _is_transient(error):
                    raise
                time.sleep(_backoff_seconds(attempt))
        line = validate_download(temporary, shown=destination.name)
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return ScheduleDownload(
        path=str(destination),
        source=redacted(url),
        final_url=redacted(final_url),
        bytes=size,
        sha256=digest,
        feed_date=feed_date(line),
        downloaded_at=_now(),
    )


@dataclass(frozen=True)
class ScheduleProbe:
    """What one short request to the timetable's address proved."""

    source: str
    final_url: str
    status: int | None
    seconds: float


PROBE_BYTES = 2


def probe(
    url: str,
    *,
    username: str = "",
    password: str = "",
    opener: Opener | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> ScheduleProbe:
    """Read the first bytes of *url* and refuse anything that is not a gzip.

    Two bytes are the whole check this can buy, and they are the one a status
    line cannot make: the gzip magic proves a schedule file answered, where an
error page served with a 200 looks exactly like the feed from the outside.

    One attempt, no retry. A 503 here is worth reporting where it is cheap to
    read, and the download that follows is where a retry belongs.
    """
    request = _request(url, username, password)
    request.add_header("Range", f"bytes=0-{PROBE_BYTES - 1}")
    started = time.monotonic()
    with _open_response(opener, request, timeout) as response:
        status = _response_status(response)
        _check_status(response, url, authenticating=bool(username or password))
        final_url = _check_https(response, url)
        # A server that ignores the range answers 200 and would stream the whole
        # file, so the read stops at the magic either way and the response is
        # closed under us.
        head = bytes(getattr(response, "read")(PROBE_BYTES) or b"")
    seconds = time.monotonic() - started
    if not head:
        raise FeedValidationError(f"{redacted(url)} answered with no bytes")
    if head[:2] != GZIP_MAGIC:
        if head.lstrip().startswith(b"<"):
            raise FeedValidationError(
                f"{redacted(url)} answered with a web page or XML, not a gzipped schedule"
            )
        raise FeedValidationError(
            f"{redacted(url)} answered with {head[:2]!r}, which is not the gzip magic a CIF has"
        )
    return ScheduleProbe(
        source=redacted(url),
        final_url=redacted(final_url),
        status=status,
        seconds=seconds,
    )


def _other_feeds(destination: Path) -> list[str]:
    """Any other feed file in the folder the download was written to.

    The loader reads every file in a folder, so a second CIF beside this one is
    two timetables read as one -- a page of journeys that cannot be taken, with
    nothing about it to look wrong. Naming the file is the whole safeguard.
    """
    if not destination.parent.is_dir():
        return []
    others = []
    for child in sorted(destination.parent.iterdir()):
        if not child.is_file() or child == destination or child.name.startswith("."):
            continue
        lowered = child.name.lower()
        if lowered.endswith(".gz") or child.suffix.lower() in FEED_SUFFIXES:
            others.append(child.name)
    return others


def _credentials() -> tuple[str, str]:
    return os.environ.get("SCHEDULE_USERNAME", ""), os.environ.get("SCHEDULE_PASSWORD", "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--url",
        default=os.environ.get("SCHEDULE_URL", ""),
        help="where the gzipped CIF is (or SCHEDULE_URL). Never printed with its query.",
    )
    parser.add_argument("--out", default=DEFAULT_OUT, help="the file to write")
    parser.add_argument(
        "--no-credential",
        action="store_true",
        help="do not send SCHEDULE_USERNAME/SCHEDULE_PASSWORD, for a URL that needs none",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="read two bytes from the URL and stop, proving the address and credential in seconds",
    )
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    args = parser.parse_args(argv)

    if not args.url:
        print(
            "no URL: pass --url or set SCHEDULE_URL. Network Rail's own feed is "
            "'https://publicdatafeeds.networkrail.co.uk/ntrod/CifFileAuthenticate"
            "?type=CIF_ALL_FULL_DAILY&day=toc-full.CIF.gz', which needs an account",
            file=sys.stderr,
        )
        return 2

    username, password = ("", "") if args.no_credential else _credentials()
    if args.probe:
        try:
            found = probe(args.url, username=username, password=password)
        except DownloadError as error:
            print(f"schedule probe failed: {error}", file=sys.stderr)
            return 1
        shown = f"HTTP {found.status}" if found.status is not None else "an answer"
        print(f"{found.source} answered {shown} with gzip bytes in {found.seconds:.1f}s")
        print(f"it answered from {found.final_url}")
        return 0

    try:
        result = download_one(
            args.url,
            args.out,
            username=username,
            password=password,
            retries=max(1, args.retries),
        )
    except DownloadError as error:
        print(f"schedule download failed: {error}", file=sys.stderr)
        return 1

    print(f"{result.path}: {result.bytes} bytes, sha256 {result.sha256}")
    print(f"source {result.source} downloaded {result.downloaded_at}")
    if result.feed_date:
        print(f"the feed's own extract date (YYMMDD) is {result.feed_date}")
    for name in _other_feeds(Path(result.path)):
        print(
            f"warning: {name} is beside {Path(result.path).name}. The loader reads every "
            "feed file in a folder, so two CIFs there are two timetables read as one.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
