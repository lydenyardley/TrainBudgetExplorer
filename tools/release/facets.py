"""Refuse a release whose facet reference data has drifted from the registry.

    python -m tools.release.facets --feed feeds/fares/dtd-fares.zip

`reference-data/destination-facets.json` is generated, and nothing tied it to
the registry that writes it: ADR-0062 and ADR-0064 each shipped a facet source
without regenerating it, and the copy went stale in silence with every gate
green. This runs on every build, unchanged feed or not, because a gate that
skips when nothing changed cannot catch a file that is already stale. A feed
revision that moves the station count fails here on purpose; the fix is
`regenerate-facets.yml` and a commit with the per-facet counts in front of a
person.

`tools.check_facet_reference` exits 2 when a dataset did not answer, which it
cannot tell from a source that came back empty. That is an infrastructure
condition, so the release warns and carries on, the way the build treats an
unreachable reference feed. A missing checked-in file is a fault in this
repository and drift (exit 1) is drift, so both still fail.

Exit codes: 0 the data matches (or could not be compared, with a warning), 1 it
drifted or is missing.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tools import check_facet_reference
from tools.release import error, warning

REFERENCE = Path("reference-data/destination-facets.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--feed", required=True, help="the fares archive the LOC records are read from")
    args = parser.parse_args(argv)
    if not REFERENCE.is_file():
        error("facet reference", f"{REFERENCE.as_posix()} is not in this checkout")
        return 1
    code = check_facet_reference.main(["--feed", args.feed])
    if code == 2:
        warning(
            "facet reference",
            "the facet reference data could not be verified this run (exit 2, a source did not "
            "answer), so the checked-in copy was not compared against the registry",
        )
        return 0
    return code


if __name__ == "__main__":
    raise SystemExit(main())
