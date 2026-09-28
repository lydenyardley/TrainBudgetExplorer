"""Show what a Knowledgebase reference feed actually contains.

``atoc_knowledgebase`` recognises restriction records by local element name,
from a set of plausible spellings, because the feed's schema is not published
in a form this project can verify. That guess is safe -- an unrecognised record
makes the check report "could not be checked" rather than agreement -- but it is
still a guess, and a guess nobody can inspect is a guess nobody can correct.

This is the tool that inspects it. Given a feed, or a folder of them, it prints:

* every distinct element name, how many times it appears, and where it sits in
  the tree;
* a sample of the text under each, so a name can be matched to a meaning;
* what the reader currently makes of it, record by record, and which element
  names it does not recognise;
* the specific lines to add to ``CODE_NAMES``, ``DESCRIPTION_NAMES``,
  ``OUTWARD_NAMES`` or ``RETURN_NAMES`` when a name is close but not matched.

It reads only the local file and never writes to the reader, so running it
against the real feed is safe even when the reader is wrong. Nothing here is a
claim the build makes; it is evidence for a person deciding what to change.

    python tools/inspect_knowledgebase.py feeds/knowledgebase
    python tools/inspect_knowledgebase.py feeds/knowledgebase/ticket-restrictions.xml
    python tools/inspect_knowledgebase.py feeds/knowledgebase --json
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# Reach the project root whether run as `python tools/inspect_knowledgebase.py`
# or imported as tools.inspect_knowledgebase (the tests' way).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atoc_knowledgebase import (  # noqa: E402
    CODE_NAMES,
    DESCRIPTION_NAMES,
    OUTWARD_NAMES,
    RETURN_NAMES,
    carries_wording,
    check_restrictions,
    load_ticket_restrictions,
    local_name,
)

# The four name sets, in the order the reader applies them to a child element.
# Ordered because a name is a candidate for more than one: `<Description>` is
# both a code field and the wording, and which it is depends on its value.
NAME_SETS = (
    ("code", CODE_NAMES),
    ("description", DESCRIPTION_NAMES),
    ("outward", OUTWARD_NAMES),
    ("return", RETURN_NAMES),
)

# A sample is only evidence if it is short enough to read and long enough to
# identify. Long values are cut with an ellipsis rather than dropped, because a
# value that is cut is often exactly the one that shows what the field means.
SAMPLE_CHARS = 72


@dataclass
class ElementSummary:
    """One distinct element name, across a whole feed."""

    name: str
    count: int = 0
    # A large default, not zero: the summary keeps the SHALLOWEST depth a name
    # appears at, and starting at zero would pin every name to the root.
    depth: int = 99
    parents: set[str] = field(default_factory=set)
    samples: list[str] = field(default_factory=list)
    #: What the reader decided a record-shaped element was, or None.
    matched_as: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "count": self.count,
            "depth": self.depth,
            "parents": sorted(self.parents),
            "samples": self.samples[:3],
            "matchedAs": self.matched_as,
        }


def summarise(payload: bytes) -> tuple[dict[str, ElementSummary], str | None]:
    """Every element name in *payload*, with counts, depth and samples."""

    try:
        root = ET.fromstring(payload)
    except ET.ParseError as error:
        return {}, f"not readable XML ({error})"

    def walk(element, depth: int, parent: str) -> None:
        name = local_name(element.tag)
        summary = elements.setdefault(name, ElementSummary(name))
        summary.count += 1
        # The shallowest place a name appears is the useful one to report: a
        # name that is a record at depth 1 and a field at depth 3 is being used
        # for two different things, and hiding that behind the deepest would
        # make the tree misleading.
        summary.depth = min(summary.depth, depth)
        if parent:
            summary.parents.add(parent)
        text = (element.text or "").strip()
        if text and len(summary.samples) < 3:
            summary.samples.append(text if len(text) <= SAMPLE_CHARS else text[:SAMPLE_CHARS] + "…")
        for child in element:
            walk(child, depth + 1, name)

    elements: dict[str, ElementSummary] = {}
    walk(root, 0, "")
    return elements, None


def classify(names: set[str]) -> dict[str, list[str]]:
    """Which names the reader already matches, and to which field."""

    return {
        field_name: sorted(name for name in names if name in wanted)
        for field_name, wanted in NAME_SETS
    }


def unmatched(names: set[str]) -> dict[str, list[str]]:
    """Names carrying text that the reader matches to no field at all."""

    known = set().union(*(wanted for _, wanted in NAME_SETS))
    out: dict[str, list[str]] = {}
    for name in sorted(names):
        if name not in known:
            out.setdefault("unmatched", []).append(name)
    return out


def suggestions(names: set[str]) -> list[str]:
    """Names that look like one of the four fields but are not in the set.

    A near miss is the case worth surfacing: a publisher who writes
    ``<RestrictionOutwardDescription>`` is plainly describing the outward
    condition, and the reader would silently decline to compare it. That is the
    safe behaviour, but it means the page says "could not be checked" for a feed
    that was perfectly readable, and this is how you find out why.
    """

    out: list[str] = []
    for name in sorted(names):
        if any(name in wanted for _, wanted in NAME_SETS):
            continue
        # One line per name, naming the LONGEST anchor it contains. A name like
        # `restrictionoutwarddescription` contains three of the reader's words,
        # and listing all three said "restriction" -- a code field -- which is a
        # coincidence of spelling and tells the reader nothing. The longest
        # match is the specific one, and `outwarddescription` is plainly the
        # outward field.
        best: tuple[int, str, str] | None = None
        for field_name, wanted in NAME_SETS:
            for anchor in wanted:
                if len(anchor) > 3 and anchor in name and (best is None or len(anchor) > best[0]):
                    best = (len(anchor), anchor, field_name)
        if best is not None:
            out.append(
                f"{name}: contains {best[1]!r}, which the reader treats as a {best[2]} field"
            )
    return out


def inspect_file(path: Path) -> dict[str, object]:
    """Everything this tool can say about one feed file."""

    try:
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as archive:
                members = [n for n in archive.namelist() if n.lower().endswith(".xml")]
                if not members:
                    return {"path": str(path), "problem": "the archive holds no XML member"}
                payload = archive.read(members[0])
                inner = members[0]
        else:
            payload = path.read_bytes()
            inner = path.name
    except (OSError, zipfile.BadZipFile, KeyError) as error:
        return {"path": str(path), "problem": f"could not be read ({type(error).__name__})"}

    elements, problem = summarise(payload)
    if problem:
        return {"path": str(path), "member": inner, "problem": problem}

    names = {name for name, summary in elements.items() if summary.samples}
    matched = classify(names)

    # What the reader actually extracts, read through its own code path rather
    # than reimplemented here, so this cannot disagree with the build. The
    # note is the reader's own, for the same reason: a tool that explained the
    # reader differently would be a second thing to keep correct.
    kb = load_ticket_restrictions(path)
    verdict = check_restrictions({}, kb)
    return {
        "path": str(path),
        "member": inner,
        "elements": [elements[name].as_dict() for name in sorted(elements)],
        "matched": matched,
        "unmatchedNames": sorted(name for name in names if not any(name in w for _, w in NAME_SETS)),
        "suggestions": suggestions(names),
        "reader": {
            "filesRead": len(kb.files_read),
            "recordsUnderstood": kb.records_understood,
            "recordsSeen": kb.records_seen,
            "unrecognised": dict(sorted(kb.unrecognised.items())),
            "usable": kb.usable,
            "problem": kb.problem,
            "codes": sorted(kb.restrictions),
            "codesWithWording": sorted(
                code for code, record in kb.restrictions.items() if carries_wording(record)
            ),
            # What a page built on this feed would say, in the reader's words.
            "verdict": verdict.status,
            "note": verdict.note,
        },
    }


def inspect(path: Path) -> list[dict[str, object]]:
    """Inspect a feed file, or every XML in a folder."""

    if path.is_dir():
        sources = sorted(
            child for child in path.iterdir() if child.suffix.lower() in (".xml", ".zip")
        )
        if not sources:
            return [{"path": str(path), "problem": "no XML or ZIP feed in this folder"}]
        return [inspect_file(child) for child in sources]
    return [inspect_file(path)]


def _print_report(report: dict[str, object], out) -> None:
    print(f"\n{report['path']}", file=out)
    if "problem" in report:
        print(f"  could not be read: {report['problem']}", file=out)
        return
    if report.get("member"):
        print(f"  member: {report['member']}", file=out)
    print("\n  elements (name, count, depth, where it appears):", file=out)
    for element in report["elements"]:  # type: ignore[index]
        parents = ", ".join(element["parents"]) or "(root)"  # type: ignore[index]
        print(
            f"    {element['name']:<34} x{element['count']:<6} depth {element['depth']}  in {parents}",  # type: ignore[index]
            file=out,
        )
        for sample in element["samples"]:  # type: ignore[index]
            print(f"        {sample!r}", file=out)
    matched = report["matched"]  # type: ignore[index]
    print("\n  what the reader matches:", file=out)
    for field_name, names in matched.items():  # type: ignore[union-attr]
        print(f"    {field_name:<12} {', '.join(names) if names else '(nothing)'}", file=out)
    unmatched_names = report["unmatchedNames"]  # type: ignore[index]
    if unmatched_names:
        print(
            f"\n  carrying text but matched to no field: {', '.join(unmatched_names)}",
            file=out,
        )
    suggestions_made = report["suggestions"]  # type: ignore[index]
    if suggestions_made:
        print("\n  possible near misses -- check these before changing the reader:", file=out)
        for line in suggestions_made:
            print(f"    {line}", file=out)
    reader = report["reader"]  # type: ignore[index]
    print(
        f"\n  the reader: {reader['recordsUnderstood']} of {reader['recordsSeen']} record(s) understood, "
        f"usable={reader['usable']}",
        file=out,
    )
    if reader["unrecognised"]:
        print(f"    unrecognised elements: {reader['unrecognised']}", file=out)
    if reader["problem"]:
        print(f"    problem: {reader['problem']}", file=out)
    if reader["codes"]:
        print(f"    codes: {', '.join(reader['codes'][:20])}", file=out)
    if reader["codesWithWording"]:
        print(
            f"    of those, {len(reader['codesWithWording'])} carried wording to compare",
            file=out,
        )
    if not reader["usable"]:
        print(
            f"    a page built on this feed would say ({reader['verdict']}): {reader['note']}",
            file=out,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Show what a Knowledgebase reference feed contains."
    )
    parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=Path("feeds") / "knowledgebase",
        help="a feed XML/ZIP, or a folder of them (default: feeds/knowledgebase)",
    )
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    arguments = parser.parse_args(argv)

    reports = inspect(arguments.path)
    if arguments.json:
        print(json.dumps(reports, indent=2, ensure_ascii=False))
    else:
        if not arguments.path.exists():
            print(
                f"{arguments.path} is not there. Download the reference feeds with "
                "`python dtd_download.py --output-root feeds --kb-only`, or pass the path "
                "to a feed you have.",
                file=sys.stderr,
            )
            return 2
        for report in reports:
            _print_report(report, sys.stdout)
        print(
            "\nChanging what the reader matches means editing CODE_NAMES, "
            "DESCRIPTION_NAMES, OUTWARD_NAMES or RETURN_NAMES at the top of "
            "atoc_knowledgebase.py, and adding a case to "
            "tests/test_atoc_knowledgebase.py for the name you added."
        )
    # A feed the reader cannot use is a finding, not a crash: the report is the
    # deliverable, and this tool exists to be run precisely when something is
    # wrong.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
