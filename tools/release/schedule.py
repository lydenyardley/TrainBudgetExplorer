"""Fetch the OGL timetable the release publishes from, or prove the address first.

    python -m tools.release.schedule --probe   two bytes, before any feed is downloaded
    python -m tools.release.schedule           the file, and its identity beside it

A second product, a second licence and a second host: Network Rail's own CIF
under the Open Government Licence, whose §5 permits distribution where the DTD
timetable's forbids it (ADR-0073). It is fetched in every job that holds the
feeds, for the reason the DTD feeds are: it does not travel as an artifact.

The empty-address gate is here rather than in `schedule_download` because it is
a statement about the release, not the downloader: this release declares the
timetable, so a run without one stops rather than publishing prices under a
shape it no longer builds. The probe runs first because a wrong URL or a refused
credential is a settings question, and the download that would answer it sits
after the DTD feeds' minutes. The identity is written in `sha256sum`'s format,
because `.feed-state` caches carry that format from before this module.

Exit codes: 0 the address answered (and the file was written), 1 it did not, or
no address is set.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path

from trainbudget.feeds import schedule_download
from tools.release import error

OUT = Path("feeds/nwr-schedule/nwr-schedule.CIF.gz")
IDENTITY = Path("feeds/nwr-schedule.sha256")

NO_ADDRESS = (
    "no SCHEDULE_URL repository variable is set, and this release publishes times from "
    "Network Rail's CIF under the Open Government Licence (ADR-0073). Set SCHEDULE_URL in the "
    "repository settings; the credential it needs is the SCHEDULE_USERNAME and SCHEDULE_PASSWORD "
    "secrets from the account that holds the CIF subscription, which is not the fares feed's NRDP "
    "pair. Or point the build at no timetable and declare --release fares instead. The route for "
    "both is docs/github-pages-deployment.md."
)


def write_identity(folder: Path = OUT.parent, identity: Path = IDENTITY) -> None:
    """`sha256sum <folder>/*`, byte for byte, so another job can compare it."""
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.as_posix()}\n"
        for path in sorted(folder.iterdir())
        if path.is_file()
    ]
    identity.write_text("".join(lines), encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--probe", action="store_true", help="prove the address and credential, then stop")
    args = parser.parse_args(argv)
    if not os.environ.get("SCHEDULE_URL"):
        error("timetable source", NO_ADDRESS)
        return 1
    if args.probe:
        return schedule_download.main(["--probe"])
    code = schedule_download.main(["--out", OUT.as_posix()])
    if code == 0:
        write_identity()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
