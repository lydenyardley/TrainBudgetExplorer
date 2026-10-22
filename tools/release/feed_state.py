"""Whether a scheduled run has anything new to build, and the marker that answers it.

    python -m tools.release.feed_state changed --event <github.event_name>
    python -m tools.release.feed_state save

Only the daily schedule may skip. A push is a change someone made and a manual
run is someone asking for a build, so neither is second-guessed by the marker.
The marker is `.feed-state`, written by `save` in the assemble job only after a
build passed every gate, so "unchanged" means the same feed fingerprint, the
same OGL timetable and the same build-inputs digest as the last successful
build.

The feeds are compared by what they ARE, not by the manifest's bytes. The
manifest also records when a download was last *checked*, which moves on every
run, including one where the portal answered 304 and published nothing; a byte
comparison would rebuild and republish the identical site every day. The OGL
timetable has a second publisher and a second update clock, so a day the portal
answered 304 is not evidence that it stood still. The build inputs come from one
rule rather than a hand-kept list: the three-file list this replaced missed the
only changed input of eight of the last 150 commits (F4 of the 8 October 2026
agent-efficiency audit).

Exit codes: 0 the answer was written, 2 the arguments named no work.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from dtd_download import feed_fingerprint
from tools.build_inputs import fingerprint as build_inputs
from tools.release import output

FEEDS = Path("feeds")
STATE = Path(".feed-state")
MANIFEST = "download-manifest.json"
SCHEDULE = "nwr-schedule.sha256"
INPUTS = "build-inputs.sha256"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def unchanged(feeds: Path = FEEDS, state: Path = STATE) -> bool:
    """True only when every part of the last good build's marker matches."""
    previous = feed_fingerprint(state / MANIFEST) if (state / MANIFEST).is_file() else ""
    previous_schedule = _read(state / SCHEDULE)
    previous_inputs = _read(state / INPUTS).strip()
    return bool(
        previous
        and previous == feed_fingerprint(feeds / MANIFEST)
        and previous_schedule
        and previous_schedule == _read(feeds / SCHEDULE)
        and previous_inputs
        and previous_inputs == build_inputs()
    )


def changed(event: str) -> bool:
    if event != "schedule":
        print(f"A {event} run always builds.")
        return True
    if unchanged():
        print("Feeds and build inputs are unchanged; keeping the existing site.")
        return False
    print("Feeds or build inputs changed; a full audited build is required.")
    return True


def save(feeds: Path = FEEDS, state: Path = STATE) -> None:
    state.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(feeds / MANIFEST, state / MANIFEST)
    shutil.copyfile(feeds / SCHEDULE, state / SCHEDULE)
    (state / INPUTS).write_text(build_inputs() + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    ask = commands.add_parser("changed", help="write changed=true|false for the later jobs")
    ask.add_argument("--event", required=True, help="github.event_name")
    commands.add_parser("save", help="record this build as the last good one")
    args = parser.parse_args(argv)
    if args.command == "changed":
        output("changed", "true" if changed(args.event) else "false")
    else:
        save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
