"""Audit downloaded DTD fares and timetable feeds before using their totals.

``feed_audit.py`` answers a parser question: once two feed objects have been
loaded, what did the readers see?  This command adds the check that matters
before that point.  It distinguishes a missing download, an empty response, a
non-ZIP response, a ZIP with the wrong records, and a valid archive that the
parser could not read.

Usage:
    python dtd_audit.py
    python dtd_audit.py --feed feeds/fares --timetable feeds/timetable

The normal parser audit is still printed after the path checks.  Ancillary DTD
files (for example ``.FLF`` or ``.ALF``) are reported by the parser as unopened;
they do not by themselves make an otherwise valid archive fail.  A ``.RST``
restriction file that did not parse cleanly is different: it is a warning,
because the publishable selector depends on it.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

from atoc_fares import FaresDb
from atoc_timetable import TimetableDb
from dtd_download import DTD_FEEDS, inspect_local_download
from feed_audit import audit as parser_audit
from feed_audit import print_audit


DEFAULT_FARES = "feeds/fares"
DEFAULT_TIMETABLE = "feeds/timetable"


def _spec(name: str):
    return next(feed for feed in DTD_FEEDS if feed.name == name)


def _safe_error(error: BaseException) -> str:
    """Keep parser/network diagnostics useful without dumping a response body."""

    message = str(error).replace("\n", " ")[:240]
    return f"{type(error).__name__}: {message}" if message else type(error).__name__


def audit_dtd(fares_path: str | Path, timetable_path: str | Path) -> dict[str, object]:
    """Return path validation plus the existing cross-feed parser audit.

    The result always has ``status`` (``ok``, ``warning``, or ``failed``),
    ``checks``, and ``errors``.  On a valid pair it also contains the keys
    returned by :func:`feed_audit.audit`.
    """

    checks = {
        "fares": inspect_local_download(fares_path, _spec("fares")),
        "timetable": inspect_local_download(timetable_path, _spec("timetable")),
    }
    result: dict[str, object] = {
        "status": "failed",
        "checks": checks,
        "errors": [],
    }
    errors: list[str] = result["errors"]  # type: ignore[assignment]
    for label, check in checks.items():
        if check["status"] != "ok":
            errors.append(
                f"{label} {check['status']}: {check['detail']} ({check['path']})"
            )
    if errors:
        return result

    try:
        fares = FaresDb().load_feed(fares_path)
        timetable = TimetableDb().load_feed(timetable_path)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        errors.append(f"parser could not read the validated feeds: {_safe_error(error)}")
        return result

    parsed = parser_audit(fares, timetable)
    result.update(parsed)
    result["checks"] = checks
    result["errors"] = errors

    if not fares.report.files_read or not timetable.report.files_read:
        errors.append("a validated archive contained no files recognized by its parser")
        result["status"] = "failed"
        return result
    if fares.stats()["flows"] == 0 or fares.stats()["fares"] == 0:
        errors.append("the fares archive produced no flow/fare records; treat it as empty")
        result["status"] = "failed"
        return result
    if timetable.stats()["stations"] == 0 or timetable.stats()["schedules"] == 0:
        errors.append("the timetable archive produced no stations/schedules; treat it as empty")
        result["status"] = "failed"
        return result

    rejected = fares.report.records_skipped + timetable.report.records_skipped
    if rejected:
        errors.append(f"parser rejected {rejected} record(s); inspect the rejected examples")
        result["status"] = "warning"
    restriction_problem = fares.restrictions.gate_problem()
    if restriction_problem:
        errors.append(f"restriction gate: {restriction_problem}")
        result["status"] = "warning"
    if result["status"] != "warning":
        result["status"] = "ok"
    return result


def print_dtd_audit(report: dict[str, object], limit: int = 10) -> None:
    print("DTD download checks")
    checks = report.get("checks", {})
    if isinstance(checks, dict):
        for label in ("fares", "timetable"):
            check = checks.get(label)
            if not isinstance(check, dict):
                continue
            suffix = f" — {check['detail']}" if check.get("detail") else ""
            print(f"  {label}: {check.get('status', 'unknown')} ({check.get('bytes', 0)} bytes){suffix}")
    errors = report.get("errors", [])
    if errors:
        print("DTD audit findings")
        for error in errors:
            print(f"  {error}")
    if report.get("status") == "failed":
        return
    print()
    print_audit(report, limit)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and audit downloaded NRDP/DTD fares and timetable feeds."
    )
    parser.add_argument(
        "--feed",
        "--fares",
        dest="fares",
        default=DEFAULT_FARES,
        help=f"fares ZIP or folder (default: {DEFAULT_FARES})",
    )
    parser.add_argument(
        "--timetable",
        default=DEFAULT_TIMETABLE,
        help=f"timetable ZIP or folder (default: {DEFAULT_TIMETABLE})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    arguments = _parse_args(argv)
    report = audit_dtd(arguments.fares, arguments.timetable)
    print_dtd_audit(report)
    if report["status"] == "failed":
        return 2
    if report["status"] == "warning":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
