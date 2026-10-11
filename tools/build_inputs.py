"""One fingerprint for every source a built site is made of.

The release rebuilds when the feeds changed or when the build inputs changed, and
the list of build inputs was hand-kept and written out twice in the workflow:
`sha256sum build_demo_page.py atoc_fares.py page_templates.py`. `build_demo_page`
also imports `atoc_knowledgebase`, `atoc_timetable`, `build_workers`,
`destination_coverage` and `retailer`; `atoc_fares` imports `atoc_restrictions`
and `parse_report`; and the build reads `reference-data/`. Eight of the last 150
commits changed only an input that list did not name, so a fix could sit
unpublished until something else happened to trigger a rebuild (F4 of the 8
October 2026 agent-efficiency audit). The page's CSS and JS moved into `page/`
since, which such a list would have missed for the same reason.

    python tools/build_inputs.py --fingerprint   one digest, for the workflow
    python tools/build_inputs.py --list          every file it hashed

Exit codes: 0 a digest was printed, 2 the arguments named no work to do.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: What a build is made of: the modules beside this one, the page's own CSS and
#: JS, and the generated reference data a build reads. `tests/` and `tools/`
#: are not build inputs, and neither is anything else, which is why this is a
#: rule about where sources live rather than a list of names to keep up to date.
#: The page's pattern reaches below the first level, because the station route's
#: script is one file per panel under a subdirectory: a pattern that stopped at
#: `page/*` would hash the directory and none of the files in it.
INPUTS = ("*.py", "page/**/*", "reference-data/*")


def build_inputs(root: Path = ROOT) -> list[Path]:
    """Every file a build is made of, in a stable order."""
    files = {path for pattern in INPUTS for path in root.glob(pattern) if path.is_file()}
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(root: Path = ROOT) -> str:
    """One digest over each input's name and bytes.

    The name is hashed as well as the bytes, so renaming a file is a change. No
    timestamp is read: a checkout that touches every file must not look like a
    new build.
    """
    digest = hashlib.sha256()
    for path in build_inputs(root):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(file_digest(path)))
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ask = parser.add_mutually_exclusive_group(required=True)
    ask.add_argument("--fingerprint", action="store_true", help="print one digest over every input")
    ask.add_argument("--list", action="store_true", help="print each input with its own hash")
    args = parser.parse_args(argv)

    if args.list:
        for path in build_inputs():
            print(f"{file_digest(path)}  {path.relative_to(ROOT).as_posix()}")
        return 0
    print(fingerprint())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
