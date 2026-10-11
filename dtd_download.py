"""Download National Rail Data Portal (NRDP/DTD) static feeds safely.

The portal has two different kinds of access:

* the DTD subscription provides the bulk fares and timetable ZIP files; and
* the Knowledgebase (KB) subscription provides the smaller XML reference feeds.

They are authenticated with the same short-lived token, but they are not the
same subscription.  In particular, having the KB URLs below does not prove
that the account is entitled to fares or timetable data.

Credentials are read only from ``NRDP_USERNAME`` and ``NRDP_PASSWORD`` (with
lowercase ``NRDP_username``/``NRDP_password`` accepted for UK2GTFS compatibility). They
are sent as a form body to the authentication endpoint and are never put in a
URL, a log message, an exception, or the download manifest.  The token returned
by the portal is held in memory and sent as ``X-Auth-Token`` only to the NRDP
host.

The default DTD downloads are written as ZIPs inside ``feeds/fares`` and
``feeds/timetable``.  The existing parsers accept either a folder or a ZIP, so
the normal audit/build commands continue to use ``feeds/fares`` and
``feeds/timetable`` without a special downloader-only path.

A response is validated before its temporary file replaces an existing good
file.  Thus an HTML error page, an entitlement response, an empty ZIP, or a
truncated archive cannot silently turn a working feed into an apparently empty
one.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Iterator


AUTH_URL = "https://opendata.nationalrail.co.uk/authenticate"
NRDP_HOST = "opendata.nationalrail.co.uk"
DTD_FARES_URL = "https://opendata.nationalrail.co.uk/api/staticfeeds/2.0/fares"
DTD_TIMETABLE_URL = "https://opendata.nationalrail.co.uk/api/staticfeeds/3.0/timetable"

DEFAULT_TIMEOUT = 60.0
# How many extra attempts a transient failure gets. Three retries means at most
# four requests and about 30 seconds of waiting, which is a long time for a
# daily job to lose and short enough not to look like a hang.
DEFAULT_RETRIES = 3
RETRY_BASE_SECONDS = 2.0
RETRY_MAX_SECONDS = 20.0
CHUNK_SIZE = 1024 * 1024
MAX_AUTH_BYTES = 1024 * 1024
# A national feed can be large, but a response larger than this is much more
# likely to be a broken endpoint than a legitimate static release.
MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024 * 1024


@dataclass(frozen=True)
class FeedSpec:
    """A named feed and the shape its response must have."""

    name: str
    url: str
    source: str
    format: str
    required_suffixes: tuple[str, ...] = ()
    recognized_suffixes: tuple[str, ...] = ()


DTD_FEEDS: tuple[FeedSpec, ...] = (
    FeedSpec(
        name="fares",
        url=DTD_FARES_URL,
        source="dtd",
        format="zip",
        required_suffixes=(".ffl",),
        recognized_suffixes=(".ffl", ".loc", ".tty", ".rlc", ".rcm"),
    ),
    FeedSpec(
        name="timetable",
        url=DTD_TIMETABLE_URL,
        source="dtd",
        format="zip",
        required_suffixes=(".mca", ".msn"),
        recognized_suffixes=(".mca", ".cfa", ".ztr", ".cif", ".msn"),
    ),
)

# These are the KB subscriptions supplied for this project.  They are reference
# and service information, not the DTD fares/timetable subscription.
KB_FEEDS: tuple[FeedSpec, ...] = (
    FeedSpec(
        name="service-indicators",
        url="https://opendata.nationalrail.co.uk/api/staticfeeds/4.0/serviceIndicators",
        source="knowledgebase",
        format="xml",
    ),
    FeedSpec(
        name="incidents",
        url="https://opendata.nationalrail.co.uk/api/staticfeeds/5.0/incidents",
        source="knowledgebase",
        format="xml",
    ),
    FeedSpec(
        name="tocs",
        url="https://opendata.nationalrail.co.uk/api/staticfeeds/4.0/tocs",
        source="knowledgebase",
        format="xml",
    ),
    FeedSpec(
        name="ticket-restrictions",
        url="https://opendata.nationalrail.co.uk/api/staticfeeds/4.0/ticket-restrictions",
        source="knowledgebase",
        format="xml",
    ),
    FeedSpec(
        name="ticket-types",
        url="https://opendata.nationalrail.co.uk/api/staticfeeds/4.0/ticket-types",
        source="knowledgebase",
        format="xml",
    ),
    FeedSpec(
        name="promotions-publics",
        url="https://opendata.nationalrail.co.uk/api/staticfeeds/4.0/promotions-publics",
        source="knowledgebase",
        format="xml",
    ),
    FeedSpec(
        name="stations",
        url="https://opendata.nationalrail.co.uk/api/staticfeeds/4.0/stations",
        source="knowledgebase",
        format="xml",
    ),
)

ALL_FEEDS = DTD_FEEDS + KB_FEEDS
# Descriptive aliases for callers that prefer URL-oriented names.
KNOWLEDGEBASE_FEEDS = KB_FEEDS
DTD_FEED_URLS = {feed.name: feed.url for feed in DTD_FEEDS}
KB_FEED_URLS = {feed.name: feed.url for feed in KB_FEEDS}
FEEDS_BY_NAME = {feed.name: feed for feed in ALL_FEEDS}


class DownloadError(RuntimeError):
    """Base class for errors safe to show on a command line.

    ``status`` is the HTTP status when there was one, and ``None`` for a
    failure that never got a response -- a timeout, a reset connection. It is
    what separates "the portal is briefly unwell, ask again" from "the portal
    said no, and asking again will not change its mind".
    """

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class AuthenticationError(DownloadError):
    """The portal rejected the environment credentials or auth response."""


class EntitlementError(DownloadError):
    """Authentication worked, but the requested feed was refused."""


class FeedValidationError(DownloadError):
    """A successful HTTP response was not the expected feed format."""


class _NotModified(Exception):
    """The portal answered a conditional request with 304.

    Deliberately not a ``DownloadError``: it is not a failure, and the code
    that turns it into a result has to run before anything that reports one.
    """


@dataclass(frozen=True)
class DownloadResult:
    """Non-secret information about one completed download."""

    name: str
    source: str
    url: str
    path: str
    bytes: int
    sha256: str
    content_type: str
    downloaded_at: str
    members: tuple[str, ...] = ()
    # The validators the portal returned, kept so the next run can ask whether
    # anything changed instead of re-downloading a national feed to find out.
    etag: str = ""
    last_modified: str = ""
    # When the portal last confirmed this feed unchanged, which is a different
    # fact from when it was downloaded. The page's freshness line reads
    # ``downloaded_at`` and must never read this: a 304 must not make a
    # month-old feed look like today's download.
    checked_at: str = ""
    unchanged: bool = False


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Do not forward an authentication header through a redirect."""

    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def _urlopen(request: urllib.request.Request, timeout: float):
    # urllib's default redirect handler can copy X-Auth-Token to a new host. The
    # feed endpoints are fixed HTTPS URLs, so refusing redirects is safer than
    # trying to inspect a redirect after the credential has already travelled.
    return urllib.request.build_opener(_NoRedirectHandler()).open(request, timeout=timeout)


# ``urlopen`` is kept as a module attribute to make the small HTTP seam easy to
# replace in tests without making the production code aware of a test client.
urlopen = _urlopen
Opener = Callable[..., object]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _response_status(response: object) -> int | None:
    value = getattr(response, "status", None)
    if value is None:
        getter = getattr(response, "getcode", None)
        if callable(getter):
            value = getter()
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _header(response: object, name: str) -> str:
    headers = getattr(response, "headers", None)
    getter = getattr(headers, "get", None)
    if not callable(getter):
        return ""
    value = getter(name)
    return str(value) if value is not None else ""


@contextmanager
def _open_response(
    opener: Opener | None,
    request: urllib.request.Request,
    timeout: float,
    *,
    authenticating: bool = False,
) -> Iterator[object]:
    """Open and always close a urllib response, including fake test responses."""

    client = opener or urlopen
    try:
        response = client(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        # 304 is the answer to a conditional request and carries no body, so it
        # arrives here like any other error status. It is not an error: it is
        # the cheapest possible answer to "has this changed?".
        if error.code == 304:
            # Still close it: an HTTPError holds a file object, and the 304
            # path is the one that most easily leaks one.
            close = getattr(error, "close", None)
            if callable(close):
                close()
            raise _NotModified() from None
        # Never include error.read(): an upstream error page can contain
        # account or diagnostic information and is not needed to act on it.
        close = getattr(error, "close", None)
        if callable(close):
            close()
        raise _http_error(error.code, request.full_url, authenticating=authenticating) from None
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as error:
        raise DownloadError(
            f"request to {request.full_url} failed ({type(error).__name__})"
        ) from None
    try:
        yield response
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()


def _http_error(status: int | None, url: str, *, authenticating: bool) -> DownloadError:
    if authenticating and status in (401, 403):
        return AuthenticationError(
            "NRDP authentication failed; check NRDP_USERNAME and NRDP_PASSWORD"
        )
    if status in (401, 403):
        return EntitlementError(
            f"NRDP refused {url} (HTTP {status}); the DTD subscription may be missing "
            "(select 'Fares, Routeing Guide and Timetable data') or the token may have expired"
        )
    shown_status = f"HTTP {status}" if status is not None else "an HTTP error"
    return DownloadError(f"request to {url} failed with {shown_status}", status=status)


def _check_status(response: object, url: str, *, authenticating: bool = False) -> None:
    status = _response_status(response)
    if status is None or 200 <= status < 300:
        return
    if 300 <= status < 400:
        raise DownloadError(f"request to {url} was redirected; refusing an unexpected response")
    raise _http_error(status, url, authenticating=authenticating)


def _read_chunks(response: object, destination: Path, max_bytes: int) -> tuple[int, str]:
    """Stream a response to *destination* and return size and SHA-256."""

    digest = hashlib.sha256()
    total = 0
    with destination.open("wb") as handle:
        while True:
            try:
                chunk = response.read(CHUNK_SIZE)  # type: ignore[attr-defined]
            except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as error:
                raise DownloadError(f"reading the NRDP response failed ({type(error).__name__})") from None
            if not chunk:
                break
            if not isinstance(chunk, (bytes, bytearray)):
                raise DownloadError("NRDP returned a non-binary feed response")
            chunk = bytes(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise DownloadError("NRDP response exceeded the configured size limit")
            handle.write(chunk)
            digest.update(chunk)
        handle.flush()
        os.fsync(handle.fileno())
    return total, digest.hexdigest()


def _read_limited(response: object, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        try:
            chunk = response.read(64 * 1024)  # type: ignore[attr-defined]
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as error:
            raise DownloadError(f"reading the NRDP response failed ({type(error).__name__})") from None
        if not chunk:
            break
        if not isinstance(chunk, (bytes, bytearray)):
            raise DownloadError("NRDP returned a non-binary authentication response")
        total += len(chunk)
        if total > limit:
            raise DownloadError("NRDP authentication response was unexpectedly large")
        chunks.append(bytes(chunk))
    return b"".join(chunks)


def _validate_url(url: str, allowed_hosts: set[str]) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in allowed_hosts:
        raise DownloadError(f"refusing to send an NRDP token to {url!r}")
    try:
        port = parsed.port
    except ValueError:
        raise DownloadError(f"refusing malformed NRDP URL {url!r}") from None
    if port not in (None, 443):
        raise DownloadError(f"refusing to send an NRDP token to non-standard port in {url!r}")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise DownloadError("NRDP feed URLs must not contain credentials, a query, or a fragment")


def _validate_final_url(response: object, allowed_hosts: set[str]) -> None:
    getter = getattr(response, "geturl", None)
    if not callable(getter):
        return
    final_url = getter()
    if final_url:
        _validate_url(str(final_url), allowed_hosts)


def _environment_credential(name: str) -> str:
    # Uppercase is the documented interface. The lowercase spelling is accepted
    # because the UK2GTFS documentation uses it; neither value is ever persisted.
    value = os.environ.get(name)
    if value is None:
        value = os.environ.get(name.lower())
    return value or ""


def authenticate(
    username: str | None = None,
    password: str | None = None,
    *,
    opener: Opener | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """Authenticate to NRDP and return its token without logging credentials.

    When omitted, *username* and *password* are read from ``NRDP_USERNAME`` and
    ``NRDP_PASSWORD``.  There is deliberately no command-line credential
    option: command lines are commonly captured in shell history and CI logs.
    """

    username = _environment_credential("NRDP_USERNAME") if username is None else username
    password = _environment_credential("NRDP_PASSWORD") if password is None else password
    if not username or not password:
        raise AuthenticationError(
            "set NRDP_USERNAME and NRDP_PASSWORD in the environment; do not put credentials in files or command-line arguments"
        )

    body = urllib.parse.urlencode({"username": username, "password": password}).encode("utf-8")
    request = urllib.request.Request(
        AUTH_URL,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "TrainBudgetExplorer/1.0 (static feed downloader)",
        },
    )
    with _open_response(opener, request, timeout, authenticating=True) as response:
        _check_status(response, AUTH_URL, authenticating=True)
        raw = _read_limited(response, MAX_AUTH_BYTES)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise AuthenticationError("NRDP authentication returned invalid JSON") from None
    token = payload.get("token") if isinstance(payload, dict) else None
    if not isinstance(token, str) or not token.strip():
        raise AuthenticationError("NRDP authentication response did not contain a usable token")
    return token.strip()


def _suffixes(names: Iterable[str]) -> set[str]:
    return {Path(name).suffix.lower() for name in names if not name.endswith("/")}


def _unsafe_archive_names(names: Iterable[str]) -> list[str]:
    unsafe: list[str] = []
    for name in names:
        path = Path(name.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts:
            unsafe.append(name)
    return unsafe


def _zip_info(path: Path, spec: FeedSpec) -> dict[str, object]:
    try:
        size = path.stat().st_size
    except OSError as error:
        return {"status": "unreadable", "bytes": 0, "members": [], "detail": type(error).__name__}
    if size == 0:
        return {"status": "empty", "bytes": 0, "members": [], "detail": "file is zero bytes"}
    try:
        with zipfile.ZipFile(path) as archive:
            names = tuple(name for name in archive.namelist() if not name.endswith("/"))
            if not names:
                return {"status": "empty", "bytes": size, "members": [], "detail": "ZIP contains no files"}
            unsafe = _unsafe_archive_names(names)
            if unsafe:
                return {
                    "status": "invalid_archive",
                    "bytes": size,
                    "members": names,
                    "detail": "ZIP contains an unsafe member path",
                }
            suffixes = _suffixes(names)
            required = set(spec.required_suffixes)
            if required and not required.issubset(suffixes):
                missing = ", ".join(sorted(required - suffixes))
                return {
                    "status": "unrecognized",
                    "bytes": size,
                    "members": names,
                    "detail": f"ZIP is missing expected member suffix(es): {missing}",
                }
            damaged_member = archive.testzip()
            if damaged_member is not None:
                return {
                    "status": "invalid_archive",
                    "bytes": size,
                    "members": names,
                    "detail": "ZIP failed its CRC check",
                }
    except (zipfile.BadZipFile, OSError, ValueError):
        return {
            "status": "invalid_archive",
            "bytes": size,
            "members": [],
            "detail": "response is not a readable ZIP archive",
        }
    return {"status": "ok", "bytes": size, "members": names, "detail": ""}


def _xml_info(path: Path) -> dict[str, object]:
    try:
        size = path.stat().st_size
    except OSError as error:
        return {"status": "unreadable", "bytes": 0, "detail": type(error).__name__}
    if size == 0:
        return {"status": "empty", "bytes": 0, "detail": "file is zero bytes"}
    try:
        with path.open("rb") as handle:
            prefix = handle.read(512).lower()
        if prefix.startswith(b"<!doctype html") or b"<html" in prefix:
            return {
                "status": "unrecognized",
                "bytes": size,
                "detail": "response looks like an HTML page, not XML",
            }
        if not prefix.lstrip().startswith(b"<"):
            return {
                "status": "unrecognized",
                "bytes": size,
                "detail": "response does not look like XML",
            }
        root = ET.parse(path).getroot()
        if root.tag.rsplit("}", 1)[-1].lower() == "html":
            return {
                "status": "unrecognized",
                "bytes": size,
                "detail": "response is an HTML page, not a feed XML document",
            }
    except (ET.ParseError, OSError, ValueError, UnicodeError):
        return {"status": "invalid_xml", "bytes": size, "detail": "response is not well-formed XML"}
    return {"status": "ok", "bytes": size, "detail": ""}


def _is_zip(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4).startswith(b"PK")
    except OSError:
        return False


def inspect_local_download(path: str | Path, spec: FeedSpec) -> dict[str, object]:
    """Classify a local download without treating an invalid file as empty.

    The result has a ``status`` of ``ok``, ``missing``, ``empty``,
    ``unrecognized``, ``invalid_archive``, ``invalid_xml``, or ``unreadable``.
    DTD ZIPs must contain the expected record-file suffixes; ancillary files in
    a valid DTD archive are allowed and are left for the parser audit to name.
    """

    path = Path(path)
    base: dict[str, object] = {"path": str(path), "status": "missing", "bytes": 0, "detail": "path does not exist"}
    if not path.exists():
        return base
    if path.is_dir():
        children = sorted(child for child in path.iterdir() if child.is_file())
        if not children:
            base.update(status="empty", detail="directory contains no files")
            return base
        total = 0
        for child in children:
            try:
                total += child.stat().st_size
            except OSError:
                return {"path": str(path), "status": "unreadable", "bytes": total, "detail": child.name}
        archives = [child for child in children if child.suffix.lower() == ".zip" or _is_zip(child)]
        recognized = set(spec.recognized_suffixes)
        raw_feed_files = [child for child in children if child.suffix.lower() in recognized]
        if archives and raw_feed_files:
            return {
                "path": str(path),
                "status": "mixed",
                "bytes": total,
                "members": (),
                "detail": "directory contains both loose feed files and a ZIP; use one feed shape",
            }
        if len(archives) > 1:
            return {
                "path": str(path),
                "status": "multiple_archives",
                "bytes": total,
                "members": (),
                "detail": "directory contains more than one ZIP; keep only the current download",
            }
        if archives:
            infos = [_zip_info(child, spec) for child in archives]
            bad = next((info for info in infos if info["status"] != "ok"), None)
            if bad is not None:
                return {
                    "path": str(path),
                    "status": bad["status"],
                    "bytes": total,
                    "members": bad.get("members", []),
                    "detail": f"{archives[infos.index(bad)].name}: {bad['detail']}",
                }
            return {
                "path": str(path),
                "status": "ok",
                "bytes": total,
                "members": tuple(name for info in infos for name in info.get("members", [])),
                "detail": "",
            }
        matching = raw_feed_files
        if not matching:
            return {
                "path": str(path),
                "status": "unrecognized",
                "bytes": total,
                "detail": "directory contains no feed files recognized for this feed",
            }
        return {"path": str(path), "status": "ok", "bytes": total, "members": (), "detail": ""}

    if spec.format == "xml":
        info = _xml_info(path)
        return {"path": str(path), **info}
    try:
        size = path.stat().st_size
    except OSError:
        return {"path": str(path), "status": "unreadable", "bytes": 0, "detail": "cannot stat file"}
    if size == 0:
        return {"path": str(path), "status": "empty", "bytes": 0, "detail": "file is zero bytes"}
    if _is_zip(path):
        return {"path": str(path), **_zip_info(path, spec)}
    return {
        "path": str(path),
        "status": "not_zip" if spec.format == "zip" else "unrecognized",
        "bytes": size,
        "detail": "DTD response is not a ZIP archive" if spec.format == "zip" else "unknown format",
    }


def validate_download(path: str | Path, spec: FeedSpec) -> dict[str, object]:
    """Raise :class:`FeedValidationError` unless a local response is usable."""

    info = inspect_local_download(path, spec)
    if info["status"] != "ok":
        raise FeedValidationError(
            f"{spec.name} response failed validation ({info['status']}): {info['detail']}"
        )
    return info


def _destination(output_root: str | Path, spec: FeedSpec) -> Path:
    root = Path(output_root)
    if spec.source == "dtd":
        return root / spec.name / f"dtd-{spec.name}.zip"
    return root / "knowledgebase" / f"{spec.name}.xml"


def _safe_temp_path(destination: Path) -> tuple[int, Path]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".part", dir=str(destination.parent))
    return fd, Path(name)


def _remove_temp(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def download_one(
    spec: FeedSpec,
    destination: str | Path,
    token: str,
    *,
    opener: Opener | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    allowed_hosts: set[str] | None = None,
    max_bytes: int = MAX_DOWNLOAD_BYTES,
    previous: dict[str, object] | None = None,
    retries: int = DEFAULT_RETRIES,
    sleep: Callable[[float], None] | None = None,
) -> DownloadResult:
    """Download one feed, validating it before an atomic replacement.

    Two things make a daily refresh cheap and an unattended one survive a bad
    moment, and both are here rather than in the workflow because every caller
    gets them.

    **Conditional.** A national fares or timetable ZIP is large and is
    re-requested on every run whether or not the portal has published a new
    one. When a previous record for this feed carries a validator and the file
    is still on disk, the request asks "has this changed?" with
    ``If-None-Match``/``If-Modified-Since``, and a 304 keeps the file. A server
    that ignores the headers answers 200 and the download happens exactly as
    before, so this cannot break against a portal that does not support it.

    A 304 is only ever believed when there is a file to keep. The record says a
    download happened once; if the file has been deleted since, "unchanged"
    would leave nothing to build from, so the validators are withheld and the
    full download runs.

    **Retrying.** A timeout or a 502 on an unattended daily job used to fail the
    whole run for a reason that would be gone in a minute. Transient failures
    are retried with a growing pause; a 4xx is not, because a portal that has
    refused the subscription or the credentials will refuse them again.
    """

    attempt_errors: list[DownloadError] = []
    # Resolved here rather than as a default argument, so that `time.sleep` is
    # still the module's at the moment of the call and not the one captured
    # when this line was first imported.
    wait = time.sleep if sleep is None else sleep
    for attempt in range(max(0, retries) + 1):
        try:
            return _download_once(
                spec,
                destination,
                token,
                opener=opener,
                timeout=timeout,
                allowed_hosts=allowed_hosts,
                max_bytes=max_bytes,
                previous=previous,
            )
        except _NotModified:
            # A 304 is a claim about a file. Believe it only if the file is
            # still the one that claim was made about.
            problem = _disagrees_with_record(destination, previous)
            if problem is None:
                return _unchanged_result(spec, destination, previous)
            # The portal says the feed is unchanged and the disk says otherwise.
            # The disk is the evidence we build from, so it wins: fetch it again
            # and ask no question.
            # Note it on stderr rather than swallowing it: a feed that keeps
            # needing a full download is a fact an operator wants in the log.
            print(
                f"{spec.name}: the portal reports it unchanged but {problem}; "
                "downloading it in full",
                file=sys.stderr,
            )
            try:
                return _download_once(
                    spec,
                    destination,
                    token,
                    opener=opener,
                    timeout=timeout,
                    allowed_hosts=allowed_hosts,
                    max_bytes=max_bytes,
                    previous=None,
                )
            except _NotModified:
                # No question was asked, so a 304 here is the portal refusing to
                # send the file at all. Left alone it would escape as something
                # the command loop does not catch, and the run would end in a
                # traceback instead of naming the feed that could not be had.
                raise DownloadError(
                    f"{spec.name}: the portal answered 304 to a request that asked "
                    "no question, so the feed could not be downloaded"
                ) from None
        except DownloadError as error:
            attempt_errors.append(error)
            if attempt >= retries or not _is_transient(error):
                raise
            wait(_backoff_seconds(attempt))
    # Unreachable: the loop either returns or raises on its last attempt.
    raise attempt_errors[-1]  # pragma: no cover


def _download_once(
    spec: FeedSpec,
    destination: str | Path,
    token: str,
    *,
    opener: Opener | None,
    timeout: float,
    allowed_hosts: set[str] | None,
    max_bytes: int,
    previous: dict[str, object] | None,
) -> DownloadResult:
    """One download attempt, with no retry of its own."""

    if not isinstance(token, str) or not token.strip():
        raise DownloadError("an NRDP token is required for a feed download")
    hosts = {NRDP_HOST} if allowed_hosts is None else set(allowed_hosts)
    _validate_url(spec.url, hosts)
    destination = Path(destination)
    headers = {
        "X-Auth-Token": token,
        "Accept": "application/zip, application/xml, application/octet-stream",
        "User-Agent": "TrainBudgetExplorer/1.0 (static feed downloader)",
    }
    # The validators only travel when there is a file they could be about.
    if previous is not None and destination.is_file():
        etag = str(previous.get("etag") or "").strip()
        modified = str(previous.get("last_modified") or "").strip()
        if etag:
            headers["If-None-Match"] = etag
        if modified:
            headers["If-Modified-Since"] = modified
    request = urllib.request.Request(spec.url, method="GET", headers=headers)
    fd, temporary = _safe_temp_path(destination)
    os.close(fd)
    try:
        with _open_response(opener, request, timeout) as response:
            _check_status(response, spec.url)
            _validate_final_url(response, hosts)
            content_type = _header(response, "Content-Type").split(";", 1)[0].strip()
            size, digest = _read_chunks(response, temporary, max_bytes)
            etag = _header(response, "ETag").strip()
            modified = _header(response, "Last-Modified").strip()
        info = validate_download(temporary, spec)
        os.replace(temporary, destination)
        members = tuple(str(member) for member in info.get("members", ()))
        return DownloadResult(
            name=spec.name,
            source=spec.source,
            url=spec.url,
            path=str(destination),
            bytes=size,
            sha256=digest,
            content_type=content_type,
            downloaded_at=_now(),
            members=members,
            etag=etag,
            last_modified=modified,
        )
    except (FeedValidationError, DownloadError):
        raise
    except (OSError, zipfile.BadZipFile, ValueError, urllib.error.URLError, TimeoutError, http.client.HTTPException) as error:
        raise DownloadError(f"could not save {spec.name} safely ({type(error).__name__})") from None
    finally:
        _remove_temp(temporary)


def _unchanged_result(
    spec: FeedSpec, destination: Path, previous: dict[str, object]
) -> DownloadResult:
    """The previous record, carried forward, for a feed the portal says is the same.

    Every field the manifest holds is copied through untouched. That includes
    ``downloaded_at``, which is the one that matters: the page measures the age
    of its prices against it, and a feed the portal last changed a month ago
    must keep saying so however many 304s it has answered since.

    Only reached once ``_disagrees_with_record`` has confirmed the record
    describes the file on disk, so every field copied here is a claim this run
    has just verified rather than one it inherited.
    """
    return DownloadResult(
        name=spec.name,
        source=spec.source,
        url=spec.url,
        path=str(destination),
        bytes=_as_int(previous.get("bytes")),
        sha256=str(previous.get("sha256") or ""),
        content_type=str(previous.get("content_type") or ""),
        downloaded_at=str(previous.get("downloaded_at") or ""),
        members=tuple(str(member) for member in previous.get("members", ()) or ()),
        etag=str(previous.get("etag") or ""),
        last_modified=str(previous.get("last_modified") or ""),
        checked_at=_now(),
        unchanged=True,
    )


def _disagrees_with_record(destination: Path, previous: dict[str, object] | None) -> str | None:
    """Describe how *destination* fails to match *previous*, or ``None``.

    The point is not to be paranoid about the portal. It is that the manifest
    is a provenance record: if the file on disk is truncated, replaced or
    half-written and the manifest still asserts a digest for it, then a record
    that is checkable has become a record that is merely believed -- and a
    304 would keep asserting it daily, indefinitely, for a portal that may not
    republish for a month.

    Hashing costs a fraction of a second against ~125 MB, which is less time
    than the request it saved, and it turns the manifest's central claim into
    one this run actually verified rather than one it inherited.
    """

    if not previous:
        # A 304 to a request that asked no question. There is no claim to check
        # and nothing to carry forward, so the only honest reading is that the
        # feed is not known to be here and must be fetched.
        return "the request asked no question"
    try:
        actual = destination.stat().st_size
    except OSError:
        return "the file is not on disk"
    recorded = _as_int(previous.get("bytes"))
    if recorded and actual != recorded:
        return f"it is {actual} bytes on disk and {recorded} in the record"
    recorded_digest = str(previous.get("sha256") or "")
    if not recorded_digest:
        return "the record has no digest to check it against"
    digest = hashlib.sha256()
    with destination.open("rb") as handle:
        while True:
            chunk = handle.read(CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    if digest.hexdigest() != recorded_digest:
        return "its contents do not match the digest in the record"
    return None


def _as_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


# Statuses worth asking again about. Everything else -- 401, 403, 404, 400 --
# is the portal answering a question, not failing to answer it, and asking the
# same question again only spends the run's time.
TRANSIENT_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


def _is_transient(error: DownloadError) -> bool:
    if isinstance(error, (AuthenticationError, EntitlementError, FeedValidationError)):
        return False
    if error.status is None:
        # No response at all: a timeout, a reset, a DNS failure. The request may
        # well succeed on a second attempt.
        return True
    return error.status in TRANSIENT_STATUS


def _backoff_seconds(attempt: int) -> float:
    """A pause that grows and then stops growing.

    Capped, because a run that waits five minutes for the same 503 is no longer
    a retry. The jitter is a fixed fraction of the delay rather than random, so
    the wait is reproducible in a test and in a log.
    """
    return min(RETRY_BASE_SECONDS * (2**attempt), RETRY_MAX_SECONDS)


_MANIFEST_FIELDS = (
    "name",
    "source",
    "url",
    "path",
    "bytes",
    "sha256",
    "content_type",
    "downloaded_at",
    "members",
    # Carried so the next run can ask the portal whether anything changed.
    "etag",
    "last_modified",
    "checked_at",
    "unchanged",
)


def _manifest_entry(result: DownloadResult, output_root: Path) -> dict[str, object]:
    entry = asdict(result)
    try:
        entry["path"] = str(Path(result.path).relative_to(output_root))
    except ValueError:
        pass
    entry["members"] = list(result.members)
    return entry


def _existing_manifest_entries(target: Path) -> list[dict[str, object]]:
    """Read only known, non-secret fields from a previous manifest."""

    try:
        with target.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    raw_entries = payload.get("downloads") if isinstance(payload, dict) else None
    if not isinstance(raw_entries, list):
        return []

    entries: list[dict[str, object]] = []
    for raw in raw_entries:
        if not isinstance(raw, dict) or not isinstance(raw.get("name"), str):
            continue
        entry = {field: raw[field] for field in _MANIFEST_FIELDS if field in raw}
        if "members" in entry and not isinstance(entry["members"], list):
            entry.pop("members")
        # A validator read from JSON is only usable as a string; anything else
        # is dropped rather than str()'d into a header that will not match.
        for field in ("etag", "last_modified"):
            if field in entry and not isinstance(entry[field], str):
                entry.pop(field)
        entries.append(entry)
    return entries


def previous_records(output_root: str | Path) -> dict[str, dict[str, object]]:
    """The previous download records for a manifest, keyed by feed name.

    Read before any download in a run, so every feed in that run asks its
    conditional question against the record the *last* run wrote rather than
    against whatever this run has just replaced.
    """

    root = Path(output_root)
    return {
        entry["name"]: entry
        for entry in _existing_manifest_entries(root / "download-manifest.json")
        if isinstance(entry.get("name"), str)
    }


# What makes a feed a *different* feed: its identity and its bytes.
# Deliberately not included are `checked_at` and `unchanged`, which record that
# a download was attempted and found unnecessary. A portal that answers 304 has
# published nothing new, and byte-comparing a manifest that carries the time of
# the check would report a change every single day -- and then rebuild, retest
# and republish the identical site every single day.
_FINGERPRINT_FIELDS = (
    "name",
    "source",
    "url",
    "sha256",
    "bytes",
    "downloaded_at",
    "members",
    "etag",
    "last_modified",
)


def feed_fingerprint(manifest_path: str | Path) -> str:
    """A digest of what the manifest says the feeds *are*.

    Compare this, not the manifest's bytes, to decide whether a rebuild is
    needed. An absent or unreadable manifest fingerprints as the empty string
    rather than raising, so a first run is a change and a damaged cache is a
    change too -- never a silent "nothing to do".
    """

    records = _existing_manifest_entries(Path(manifest_path))
    identity = [
        {field: entry[field] for field in _FINGERPRINT_FIELDS if field in entry}
        for entry in sorted(records, key=lambda item: str(item.get("name")))
    ]
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def write_manifest(results: Iterable[DownloadResult], output_root: str | Path) -> Path:
    """Merge and atomically write non-secret records of completed downloads.

    Separate ``--dtd fares`` and ``--dtd timetable`` commands are common. A
    later successful command must not erase the earlier successful download's
    provenance, so entries are replaced by name and existing entries are kept.
    """

    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    target = root / "download-manifest.json"
    by_name: dict[str, dict[str, object]] = {}
    for entry in _existing_manifest_entries(target):
        # The name is the stable identity used by this manifest. Ignore an
        # unusable old entry rather than allowing it to break a refresh.
        if isinstance(entry.get("name"), str):
            by_name[entry["name"]] = entry
    for result in results:
        entry = _manifest_entry(result, root)
        if isinstance(entry.get("name"), str):
            by_name[entry["name"]] = entry
    entries = [by_name[name] for name in sorted(by_name)]
    payload = {
        "schema": 1,
        "generated_at": _now(),
        "downloads": entries,
    }
    fd, temporary = _safe_temp_path(target)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        _remove_temp(temporary)
    return target


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download authenticated NRDP DTD and Knowledgebase static feeds."
    )
    parser.add_argument(
        "--dtd",
        choices=("fares", "timetable", "all"),
        default="all",
        help="DTD feed(s) to download (default: fares and timetable)",
    )
    parser.add_argument(
        "--kb",
        action="store_true",
        help="also download the seven supplied Knowledgebase XML feeds",
    )
    parser.add_argument(
        "--kb-only",
        action="store_true",
        help="download only Knowledgebase feeds; implies --kb and skips DTD",
    )
    parser.add_argument("--output-root", type=Path, default=Path("feeds"))
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=(
            "extra attempts for a transient failure (timeout, connection reset, "
            f"5xx, 429); default {DEFAULT_RETRIES}. A 4xx is never retried"
        ),
    )
    parser.add_argument(
        "--no-conditional",
        action="store_true",
        help="always download in full, ignoring any ETag or Last-Modified from the last run",
    )
    parser.add_argument("--no-manifest", action="store_true", help="do not write download-manifest.json")
    parser.add_argument("--list-feeds", action="store_true", help="list configured feed names and URLs")
    parser.add_argument(
        "--print-fingerprint",
        metavar="MANIFEST",
        help=(
            "print a digest of what a download manifest says the feeds are, and "
            "exit; this needs no credentials and is what a build should compare "
            "to decide whether the feeds changed"
        ),
    )
    return parser.parse_args(argv)


def _selected_specs(arguments: argparse.Namespace) -> list[FeedSpec]:
    if arguments.kb_only:
        return list(KB_FEEDS)
    names = ["fares", "timetable"] if arguments.dtd == "all" else [arguments.dtd]
    specs = [FEEDS_BY_NAME[name] for name in names]
    if arguments.kb:
        specs.extend(KB_FEEDS)
    return specs


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    arguments = _parse_args(argv)
    if arguments.list_feeds:
        for spec in ALL_FEEDS:
            print(f"{spec.name}\t{spec.source}\t{spec.url}")
        return 0
    if arguments.print_fingerprint:
        # Deliberately before authentication: a build compares fingerprints and
        # must not need the portal's credentials to find out it has nothing new.
        print(feed_fingerprint(arguments.print_fingerprint))
        return 0
    if arguments.timeout <= 0:
        print("--timeout must be greater than zero", file=sys.stderr)
        return 2
    if arguments.retries < 0:
        print("--retries cannot be negative", file=sys.stderr)
        return 2

    try:
        token = authenticate(timeout=arguments.timeout)
    except DownloadError as error:
        print(f"authentication failed: {error}", file=sys.stderr)
        return 2

    results: list[DownloadResult] = []
    failed = False
    # ``--no-conditional`` is a deliberate way to fetch in full, which is also
    # what a corrupted local file looks like from the portal's point of view.
    previous = {} if arguments.no_conditional else previous_records(arguments.output_root)
    for spec in _selected_specs(arguments):
        destination = _destination(arguments.output_root, spec)
        try:
            result = download_one(
                spec,
                destination,
                token,
                timeout=arguments.timeout,
                previous=previous.get(spec.name),
                retries=arguments.retries,
            )
        except DownloadError as error:
            failed = True
            print(f"{spec.name}: failed: {error}", file=sys.stderr)
            continue
        results.append(result)
        if result.unchanged:
            # Said plainly, because "unchanged" must never be mistaken for a
            # fresh download: the feed on disk is the one the portal last
            # published, and the page will keep dating it from that day.
            print(
                f"{spec.name}: unchanged since {result.downloaded_at or 'an unknown date'}"
                f" ({result.path})"
            )
        else:
            print(f"{spec.name}: downloaded {result.bytes} bytes to {result.path}")

    if results and not arguments.no_manifest:
        manifest = write_manifest(results, arguments.output_root)
        print(f"manifest: {manifest}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
