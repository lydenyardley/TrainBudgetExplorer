"""Refuse a public release that no licence clearance covers.

A published page carrying licensed fares is the one artefact in this project
that cannot be undone by regenerating a file, and the licence question behind
it is the one thing this project has never been able to check for itself. The
publish checklist is the record of that: "do not publish until the account terms
and brand pack have been checked", with the DTD row reading "must be confirmed".
The deploy workflow supplies the attribution wording and the privacy contact and
is otherwise perfectly happy to publish, which meant a technically successful
build could go live while every licence question was still open (audit C01).

So the clearance is a file, the file is reviewed like any other change, and
this tool is what makes it binding. It runs on the publish path in CI and
nowhere else: `build_demo_page.py` and `run.py` are untouched, so a contributor
can still build, test and open a real-feed page locally without any of this.

**What this tool can and cannot know.** It cannot read a licence and decide
whether it permits publication; a person has to. What it can do is make that
person's decision binding, dated, scoped, and tied to the exact licence file it
was made from. So it checks the *record*, and the record is the only thing that
can clear a product:

- Every licensed product has a section. The product list is read from
  ``licences/licence-manifest.json`` (filename, SHA-256, product id) plus the
  DTD portal route, which is a subscription rather than a marketplace licence
  and so has no PDF. The PDFs themselves are not in git (ADR-0067). When a PDF
  is on disk its bytes must match the manifest, and a PDF the manifest does
  not name fails the gate. A missing PDF is judged against the manifest, which
  is what CI has. A file dropped into ``licences/`` therefore cannot be filed
  and forgotten: it needs a manifest row and a decision before it can be
  published, which is the same failure ``tests/test_licences.py`` exists to
  prevent on the register side.
- A product is either **cleared** or **excluded**. Exclusion needs a stated
  reason and nothing else -- it is the safe direction, and refusing to publish
  a product should not require an approval to do so.
- Clearing one requires an explicit ``answer: yes``, a date the terms were read,
  a named approver, an approval date, an expiry, and the SHA-256 of the licence
  the decision was made from. That digest is checked against the manifest, and
  against the PDF when the PDF is present. A licence replaced under a standing
  clearance does not inherit it.
- The clearance is **scoped**. A release declares which products it publishes
  (``--release fares``) and the tool fails if any of them is not cleared. This is
  the part that stops a narrow decision from quietly authorising a wide release:
  the Darwin timetable is licensed "internal business purposes only", and the
  project has already decided the timetable is the degradable product, so a
  fares-only release can be cleared and published while the times stay switched
  off. Adding ``--timetable`` to the build demands a clearance nobody has.
- Nothing here reads the attribution wording as permission. A page can carry
  every required credit and still be a page nobody has cleared.

    python check_release_clearance.py --print
    python check_release_clearance.py --release fares
    python check_release_clearance.py --release fares,timetable --record path/to/other.md

Exit codes: 0 every published product is cleared, 1 one is not. Unlike a build
failure this is not a thing to retry: the fix is a decision, made by a person,
recorded in a pull request.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

RECORD = Path("licences/release-clearance.md")
LICENCES = Path("licences")
# The PDFs stay on the machine that holds the licence. Git tracks this
# manifest instead, so a publish job that has no PDFs still knows each
# file's name, product id and SHA-256 (ADR-0067).
MANIFEST_NAME = "licence-manifest.json"

# The product id the marketplace puts in the licence filename, in Schedule 1 §3.
PRODUCT_ID = re.compile(r"P-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

# The DTD/NRD portal is a subscription, not a marketplace product schedule, so it
# has no PDF to file. It is named here because it is the source the fares build
# actually reads, and the thing the audit found the workflow downloading.
DTD = "dtd"

# The privacy contact is not a licence, and it is on this list for the same
# reason the DTD route is: it is a question only a person can answer before
# anything is published, and the build cannot answer it. Every generated route
# promises its reader that somebody is at the end of the address, so a contact
# nobody has confirmed is a promise this project has not made good on. The build
# already refuses a real-feed page with no contact at all; this refuses to
# publish one whose contact nobody has vouched for, and says which address the
# answer is about.
PRIVACY = "privacy contact"

# The build shapes `--release` accepts. Naming the shape rather than a free list
# of products is deliberate: a typo becomes a refusal instead of a scope that
# matches nothing and therefore clears everything.
SHAPES = {
    (),
    ("fares",),
    ("fares", "timetable"),
}


def products_needed(releasing: list[str], folder: Path = LICENCES) -> tuple[list[str], list[str]]:
    """The licences a release of this shape publishes, and the reasons it cannot be mapped.

    The published build reads only the fares feed, and the fares feed comes from
    the DTD subscription. Add the national timetable -- which is what the Darwin
    product schedule is for, and whose §5 this project reads as internal-only --
    and the Darwin clearance is required too, which nobody holds. That is the
    mapping which stops a narrow decision authorising a wide release.
    """
    shape = tuple(sorted(releasing))
    if shape not in SHAPES:
        return [], [
            "'" + ",".join(releasing) + "' is not a build shape this gate knows; a release "
            "publishes "
            + " or ".join(",".join(s) or "(nothing)" for s in sorted(SHAPES) if s)
        ]
    # The empty shape is the report-only mode: it says what the record does and
    # does not clear, and requires nothing.
    #
    # The privacy contact is needed by every release that publishes anything,
    # not by a shape in particular: a published page with an unconfirmed contact
    # is the same defect whichever feeds it is built from.
    needed = [DTD, PRIVACY] if shape else []
    if "timetable" in shape:
        found = [p for p, path in products(folder).items() if path and path.match(TIMETABLE_GLOB)]
        if len(found) != 1:
            return [], [
                f"a release with the timetable needs exactly one filed licence matching "
                f"{TIMETABLE_GLOB} and there are {len(found)}"
            ]
        needed.append(found[0])
    return needed, []

STATES = ("cleared", "excluded")

# The Darwin timetable product schedule, identified by the document it is rather
# than by a product id, so renaming the file cannot quietly point the gate at a
# different licence. No such document is a refusal, not a shrug.
TIMETABLE_GLOB = "Darwin-timetable-license-*.pdf"

# The answer that clears a product. Anything else -- "unknown", "probably", a
# blank, a sentence -- is a refusal, which is the only safe reading of a licence
# question nobody has answered.
CLEARED_ANSWER = "yes"

ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

FIELD = re.compile(r"^-\s+([a-z ]+?):\s*(.*)$")


def load_manifest(folder: Path = LICENCES) -> list[dict]:
    """The committed shelf: one row per licence file, whether or not the PDF is here."""
    path = folder / MANIFEST_NAME
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("files", [])
    return rows if isinstance(rows, list) else []


def manifest_sha(filename: str, folder: Path = LICENCES) -> str:
    for row in load_manifest(folder):
        if row.get("filename") == filename:
            return str(row.get("sha256", "")).strip().lower()
    return ""


def product_digests(folder: Path = LICENCES) -> dict[str, Path]:
    """Marketplace products, by the product id in the committed manifest.

    The path is the PDF's name beside the manifest. The file may be absent:
    CI does not have the PDFs, and the product still has to be decided.
    """
    found: dict[str, Path] = {}
    for row in load_manifest(folder):
        product_id = row.get("product_id") or ""
        filename = row.get("filename") or ""
        if product_id and filename:
            found[str(product_id)] = folder / str(filename)
    return found


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(path: Path) -> str:
    """The licence's identity: the file when it is here, otherwise the manifest.

    A present file wins, so a replaced PDF cannot keep the old hash. A missing
    file falls back to the manifest, which is all a publish job has.
    """
    if path.is_file():
        return file_sha256(path)
    return manifest_sha(path.name, path.parent)


def unexpected_pdfs(folder: Path = LICENCES) -> list[str]:
    """PDFs on disk that the manifest does not name.

    A file dropped into ``licences/`` and left out of the manifest is the
    filed-and-forgotten case, and it has to fail wherever the PDF is present.
    """
    named = {row.get("filename") for row in load_manifest(folder)}
    return sorted(pdf.name for pdf in folder.glob("*.pdf") if pdf.name not in named)


def products(folder: Path = LICENCES) -> dict[str, Path | None]:
    """Every product a clearance has to speak about, and the file it was read from.

    ``None`` is a product with no filed PDF: the DTD portal subscription, and
    the privacy contact. They are in the list because the releases they hold
    back are the ones this gate exists for.
    """
    return {**product_digests(folder), DTD: None, PRIVACY: None}


def parse_sections(text: str) -> dict[str, dict[str, str]]:
    """Read the record's ``## <heading>`` sections into ``{heading: {field: value}}``.

    Only lines that look like ``- key: value`` inside a section are fields, and
    only headings naming a known product carry meaning -- so the prose between
    the fields is read by the person reviewing the pull request and ignored by
    the gate.
    """
    sections: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            current = {}
            sections[line[3:].strip()] = current
            continue
        if current is None or not line.startswith("- "):
            continue
        found = FIELD.match(line)
        if found:
            current[found.group(1).strip()] = found.group(2).strip()
    return sections


def _date_field(fields: dict[str, str], name: str, where: str, problems: list[str]) -> date | None:
    value = fields.get(name, "")
    if not value:
        problems.append(f"{where}: '{name}' is missing")
        return None
    if not ISO_DATE.fullmatch(value):
        problems.append(f"{where}: '{name}' is {value!r}, which is not a YYYY-MM-DD date")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        problems.append(f"{where}: '{name}' is {value!r}, which is not a real date")
        return None


def _match_section(heading: str, product: str) -> bool:
    return heading.strip().lower() == product.lower() or product.lower() in heading.lower()


def clearance_problems(
    text: str,
    *,
    releasing: list[str],
    today: date,
    folder: Path = LICENCES,
) -> list[str]:
    """Everything standing between this record and the release asked for.

    Empty means the release may proceed. The list is the whole answer: a person
    reading a red run should be able to fix it without reading this file.
    """
    problems: list[str] = []
    if not load_manifest(folder):
        problems.append(
            f"no {MANIFEST_NAME} in {folder}; the licence shelf is the manifest, "
            "and a release with no shelf is not a release with no licences"
        )
    for name in unexpected_pdfs(folder):
        problems.append(
            f"{name} is in {folder} and not in {MANIFEST_NAME}; add it to the "
            "manifest and give it a clearance section before anything is published"
        )
    known = products(folder)
    sections = parse_sections(text)
    needed, shape_problems = products_needed(releasing, folder)
    problems += shape_problems

    # A heading that names no known product is prose, not an answer: the record
    # is a document a person reads in a pull request, and "How to clear a
    # product" must not be a syntax error. A mistyped product heading is
    # therefore not flagged here but matches nothing, which reports it as
    # missing -- the same refusal, said in the words that help.
    claimed: dict[str, str] = {}
    for heading in sections:
        for product in [p for p in known if _match_section(heading, p)]:
            if product in claimed:
                problems.append(
                    f"the product {product} is answered twice ('{claimed[product]}' and '{heading}')"
                )
            claimed[product] = heading

    for product, pdf in known.items():
        # Every product needs a decision, not only the ones this release
        # publishes: a section nobody wrote is the "filed and forgotten" case,
        # and it is a later release that picks it up. Exclusion is one line and
        # needs no approval, so asking for it costs nothing until the answer
        # changes to "cleared".
        fields = sections.get(claimed.get(product, ""), {})
        heading = claimed.get(product, "no section")
        # The heading is only worth repeating when it says something the
        # product id does not, which it usually does not.
        where = product if heading.lower() == product.lower() else f"{product} ('{heading}')"
        if not fields:
            problems.append(
                f"{product}: no clearance section. Run --print for a template, then "
                "clear or exclude it in a pull request"
            )
            continue
        state = fields.get("state", "").lower()
        if state not in STATES:
            problems.append(
                f"{where}: 'state' is {fields.get('state', '')!r}, which is not one of "
                + " or ".join(STATES)
            )
            continue
        if state == "excluded":
            if not fields.get("reason"):
                problems.append(f"{where}: excluded, so 'reason' must say why")
            if product in needed:
                problems.append(
                    f"{where}: this release publishes {product}, which is excluded from publication"
                )
            continue
        # A cleared section is checked in full whether or not this release
        # publishes the product, so a clearance cannot be written badly here
        # and relied on by a later build.
        if fields.get("answer", "").strip().lower() != CLEARED_ANSWER:
            problems.append(
                f"{where}: 'answer' is {fields.get('answer', '')!r}; a clearance is "
                f"'{CLEARED_ANSWER}', and anything else -- including a blank -- is a refusal"
            )
        read_on = _date_field(fields, "read on", where, problems)
        approved_on = _date_field(fields, "approved on", where, problems)
        expires = _date_field(fields, "expires", where, problems)
        if not fields.get("approved by"):
            problems.append(f"{where}: 'approved by' is missing, so nobody is answerable for it")
        for name, value in (("read on", read_on), ("approved on", approved_on)):
            if value and value > today:
                problems.append(f"{where}: '{name}' is {value}, which is in the future")
        if expires and expires < today:
            problems.append(
                f"{where}: the clearance expired on {expires}; the terms need reading again, "
                "not a new date typed into the same answer"
            )
        if pdf is not None:
            recorded = fields.get("licence digest", "").strip().lower()
            committed = manifest_sha(pdf.name, folder)
            if not committed:
                problems.append(
                    f"{where}: {pdf.name} has no row in {MANIFEST_NAME}, so this "
                    "clearance is not tied to a licence"
                )
            elif pdf.is_file() and file_sha256(pdf) != committed:
                # The bytes on disk and the bytes git vouches for disagree.
                # Publishing either of them would be publishing a licence this
                # clearance was not made from.
                actual = file_sha256(pdf)
                problems.append(
                    f"{where}: the licence file has changed since this clearance was made "
                    f"({pdf.name} is now {actual[:12]}, the record says {committed[:12]})"
                )
            if not recorded:
                problems.append(
                    f"{where}: 'licence digest' is missing; run --print for the value of "
                    f"{pdf.name}, so this clearance cannot outlive the file it was made from"
                )
            elif committed and recorded != committed:
                problems.append(
                    f"{where}: 'licence digest' does not match {MANIFEST_NAME} "
                    f"({recorded[:12]} against {committed[:12]} for {pdf.name})"
                )
    return problems


def template(folder: Path = LICENCES) -> str:
    """A block per product, with the licence digest filled in.

    So that clearing a product is a copy, a paste and a read of the actual
    terms, rather than a computation the person has to trust.
    """
    lines = []
    for product, pdf in products(folder).items():
        lines.append(f"## {product}")
        lines.append("")
        lines.append("- state: excluded")
        lines.append("- reason: ")
        if pdf is not None:
            lines.append(f"# once cleared, also add: - licence digest: {digest(pdf)}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--record", default=str(RECORD), help="the clearance record to read (default: %(default)s)"
    )
    parser.add_argument(
        "--release",
        default="",
        help="comma-separated build shape this release publishes, e.g. 'fares' or "
        "'fares,timetable'. Required, because an empty scope clears a release by "
        "publishing nothing -- which is exactly the shape of gate that would have "
        "passed the build this exists to stop.",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="report what the record does and does not clear, requiring nothing. "
        "For reading the record, never for gating a release.",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="print a clearance template with the licence digests filled in, and exit",
    )
    arguments = parser.parse_args(argv)

    if arguments.print:
        print(template())
        return 0

    path = Path(arguments.record)
    if not path.is_file():
        print(
            f"no clearance record at {path}. A public release is gated on a written, "
            "dated decision, not on the absence of one; run --print for a template."
        )
        return 1

    releasing = [name.strip() for name in arguments.release.split(",") if name.strip()]
    if not releasing and not arguments.report_only:
        # An unset --release is the dangerous case: an empty scope requires
        # nothing to be cleared, so a mistyped or dropped flag would turn this
        # gate into a no-op and a red run into a green one. Saying so is the
        # only safe reading.
        print(
            "--release is required. Name the shape being published, e.g. --release "
            "fares. Use --report-only to read the record without gating anything.",
            file=sys.stderr,
        )
        return 1
    text = path.read_text(encoding="utf-8")
    problems = clearance_problems(text, releasing=releasing, today=date.today())
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(
            f"\n{len(problems)} problem(s) stand between this record and publishing "
            + (", ".join(releasing) if releasing else "nothing in particular")
            + ". This is a decision for a person, made in a pull request -- see "
            "docs/publish-checklist.md.",
            file=sys.stderr,
        )
        return 1
    if arguments.report_only and not releasing:
        # Reading the record is the whole point of this mode, and the line below
        # was not it: the empty shape requires nothing, so an excluded product
        # produced no problem and the report said "cleared ... as it stands" over
        # a record that blocks publication twice. A product with no section at
        # all counts as outstanding, because unrecorded is not cleared.
        sections = parse_sections(text)
        outstanding = [
            name
            for name in products()
            if (sections.get(name, {}).get("state") or "").strip().lower() != "cleared"
        ]
        if outstanding:
            print(
                f"the record leaves {len(outstanding)} product(s) outstanding, "
                "none of it answered here and none of it gating a build:"
            )
            for name in outstanding:
                print(f"  {name}")
        else:
            print(f"every one of the {len(products())} products the record names is cleared.")
        return 0
    print(
        "cleared for "
        + (", ".join(releasing) if releasing else "the record as it stands")
        + " by " + str(path)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
