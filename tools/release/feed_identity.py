"""Name the downloads the gates audited, or refuse a job holding other ones.

    python -m tools.release.feed_identity              the build job: publish it
    python -m tools.release.feed_identity --expect X   a later job: refuse another

The shard and assemble jobs download the feeds again, because an artifact of a
public repository is downloadable by anyone signed in and the feeds are
licensed. The portal can republish between jobs, and every gate ran on the build
job's download, so a job holding a different one stops rather than publishing
fares nobody audited. (The merge would refuse mismatched shards too; this names
the reason first.) It was the same fifteen lines of Python in a heredoc, three
times over.

The identity is the DTD fares and timetable, plus the OGL timetable the release
publishes its times from. The Knowledgebase download shares the manifest and
changes no fare, so it stays out; the shards' pages are built from it, though,
so a shard must have it (the licensed-feeds action's `knowledgebase: required`)
and the merge compares its fingerprint.
The bytes, not the download time: each job downloads at its own minute.

Exit codes: 0 an identity was named (and matched), 1 there was none to name, or
it did not match.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from trainbudget.feeds import dtd_download
from tools.release import error, output

MANIFEST = Path("feeds/download-manifest.json")
SCHEDULE_IDENTITY = Path("feeds/nwr-schedule.sha256")


def identity(manifest: Path = MANIFEST, schedule_identity: Path = SCHEDULE_IDENTITY) -> str:
    """One digest over what was downloaded, or "" when part of it is missing.

    An empty answer is refused by both callers rather than read as agreement.
    """
    rows = [
        {field: entry.get(field) for field in ("name", "sha256", "bytes")}
        for entry in sorted(dtd_download._existing_manifest_entries(manifest), key=lambda e: str(e.get("name")))
        if entry.get("name") in ("fares", "timetable")
    ]
    if not schedule_identity.is_file() or not rows or not all(row["sha256"] for row in rows):
        return ""
    schedule = hashlib.sha256(schedule_identity.read_bytes()).digest()
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode() + schedule).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--expect", help="the identity the build job's gates audited")
    args = parser.parse_args(argv)
    here = identity()
    if args.expect is None:
        if not here:
            error("feed identity", "the download manifest names no fares or timetable download")
            return 1
        output("value", here)
        return 0
    if not args.expect:
        error("feed moved", "the build job named no audited download to compare against")
        return 1
    if here != args.expect:
        error(
            "feed moved",
            f"this job downloaded feed {here or '(none)'}, but the gates audited {args.expect}; "
            "the portal republished mid-run, so rerun the workflow",
        )
        return 1
    print(f"this job holds the audited download {here}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
