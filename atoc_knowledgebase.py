"""Read the National Rail Enquiries Knowledgebase reference feeds.

The fares feed carries its own copy of the restriction wording in its ``.RST``
file, at the same vintage as the prices it accompanies. The Knowledgebase
``ticket-restrictions`` feed is a separate reference feed, republished at least
daily and independently of the fares file. Reading the two answers a question
the fares feed cannot answer on its own:

    Is the condition printed beside this price still the condition the
    reference feed says today?

That is a question with a real failure mode. A fares file published on Monday
can name a condition the reference feed retired on Tuesday, and a reader
choosing between two prices is exactly the person a stale condition misleads.
So the comparison is a claim the page makes, and the claim carries its own
evidence: which codes were compared, which agreed, which did not, and when the
reference feed was published.

**This reader reports its own uncertainty, and that is the design.** The
Knowledgebase feeds are XML whose exact element names are not published in a
form this project can check, and this code has not been run against the real
feed. Rather than guess a schema and then report agreement it did not verify,
it recognises records by local name from a set of plausible spellings and
counts what it did not recognise. An unrecognised record makes the whole
comparison ``unknown``, which the page says plainly. ``unknown`` is not a
failure of the build and not a claim of agreement: it is the honest answer,
and it is what a schema this code guessed wrong would otherwise be laundered
into.

The fares feed remains the authority. A restriction the fares file carries is
applied as the fares file describes it, whatever the reference feed says,
because a price and the condition attached to it must come from the same
publication. The Knowledgebase feed is a second opinion, and a disagreement is
reported to the reader rather than silently resolved in either direction.
"""

from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

# Local element names that have been used for a restriction code and for the
# three pieces of wording this project shows. Matched case-insensitively
# against the local name, so a namespace prefix or a differently-cased
# publisher does not defeat it. Deliberately a *set* of names: a single
# guessed name would either match nothing or, worse, match the wrong element.
CODE_NAMES = frozenset({"restrictioncode", "code", "restriction"})
DESCRIPTION_NAMES = frozenset({"description", "desc", "restrictiondescription"})
OUTWARD_NAMES = frozenset({"descout", "outwarddescription", "outwardtext", "desc_out", "detailsoutward"})
RETURN_NAMES = frozenset({"descrtn", "returndescription", "returntext", "desc_rtn", "detailsreturn"})

# A restriction code in this data is two characters. Used to decide whether a
# value that arrived in a generically-named element is a code at all, so a
# description is not mistaken for one.
CODE_SHAPE = re.compile(r"^[A-Z0-9]{2}$")


def local_name(tag: str) -> str:
    """An element's name without its namespace, lowercased."""
    return tag.rsplit("}", 1)[-1].strip().lower()


@dataclass(frozen=True)
class KnowledgebaseRestriction:
    """One restriction as the reference feed describes it."""

    code: str
    description: str
    outward_text: str
    return_text: str


def _normalise(text: str) -> str:
    """Fold the differences that are not differences in meaning."""

    return " ".join((text or "").split()).upper()


# The four answers a check can give. Kept as constants so a caller cannot
# invent a fifth by misspelling a string, and so the page's wording for each
# is written in one place.
CHECKED = "checked"
UNPUBLISHED = "unpublished"
UNKNOWN = "unknown"
ABSENT = "absent"

# The pages the Knowledgebase restriction feed is allowed to disagree with. A
# feed that changed shape, or an endpoint that answered something else, should
# not crash a build; it should make the check uncheckable and be named.
_MAX_BYTES = 256 * 1024 * 1024


@dataclass
class Knowledgebase:
    """What the reader understood of a Knowledgebase feed."""

    files_read: list[str] = field(default_factory=list)
    restrictions: dict[str, KnowledgebaseRestriction] = field(default_factory=dict)
    records_seen: int = 0
    records_understood: int = 0
    unrecognised: Counter = field(default_factory=Counter)
    problem: str | None = None

    @property
    def loaded(self) -> bool:
        return bool(self.files_read)

    @property
    def usable(self) -> bool:
        """Whether the comparison can be made at all.

        True only when the feed parsed, at least one record was understood,
        nothing was left unrecognised, and at least one record actually
        carried wording. That last condition is the one a code-only parse
        fails: a feed whose records yield restriction codes and no description
        and no validity text has been read successfully and tells us nothing
        about whether the wording the fares feed prints is still current. It is
        a feed this reader cannot compare, and saying so is the whole point.
        """

        return (
            self.loaded
            and self.problem is None
            and self.records_understood > 0
            and not self.unrecognised
            and any(carries_wording(record) for record in self.restrictions.values())
        )

    def summary(self) -> dict[str, object]:
        return {
            "files": len(self.files_read),
            "records": self.records_seen,
            "understood": self.records_understood,
            "unrecognised": dict(sorted(self.unrecognised.items())),
            "problem": self.problem,
        }


def load_ticket_restrictions(path: str | Path) -> Knowledgebase:
    """Read a Knowledgebase ``ticket-restrictions`` feed, or say why it cannot be."""

    kb = Knowledgebase()
    target = Path(path)
    try:
        if target.is_dir():
            sources = sorted(
                child for child in target.iterdir() if child.suffix.lower() in (".xml", ".zip")
            )
        elif target.suffix.lower() == ".zip":
            sources = [target]
        else:
            sources = [target] if target.is_file() else []
    except OSError as error:
        kb.problem = f"the reference feed folder could not be read ({type(error).__name__})"
        return kb
    if not sources:
        kb.problem = "no Knowledgebase restriction feed is present"
        return kb
    for source in sources:
        _read_one(kb, source)
    return kb


def _read_one(kb: Knowledgebase, source: Path) -> None:
    kb.files_read.append(source.name)
    try:
        if source.suffix.lower() == ".zip":
            with zipfile.ZipFile(source) as archive:
                for member in archive.namelist():
                    if not member.lower().endswith(".xml"):
                        continue
                    # Read the size from the central directory before the
                    # bytes. A member's declared size is cheap to check and a
                    # decompressed feed is not something to discover halfway
                    # through reading it into memory.
                    info = archive.getinfo(member)
                    if info.file_size > _MAX_BYTES:
                        kb.problem = f"{source.name}!{member} is larger than this reader will parse"
                        return
                    _read_xml(kb, archive.read(member), f"{source.name}!{member}")
        else:
            if source.stat().st_size > _MAX_BYTES:
                kb.problem = f"{source.name} is larger than this reader will parse"
                return
            _read_xml(kb, source.read_bytes(), source.name)
    except (OSError, zipfile.BadZipFile, ET.ParseError, ValueError, KeyError) as error:
        kb.problem = f"{source.name} could not be read ({type(error).__name__})"


def _read_xml(kb: Knowledgebase, payload: bytes, origin: str) -> None:
    """Read one document into *kb*.

    The counters accumulate rather than reset. The reference feed is a folder
    of seven documents, and a reader that assigned them instead of adding to
    them reported the count of whichever document happened to be read last:
    on the real folder that was ``tocs.xml``, which has no restrictions in it,
    so 644 records the reader had actually understood were counted as zero and
    the whole feed came back unusable -- the reader was working, and the number
    it reported was about a different file.
    """
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as error:
        kb.problem = f"{origin} is not readable XML ({error})"
        return
    elements = list(root.iter())
    understood: set[int] = set()
    for position, element in enumerate(elements):
        record = _restriction_from(element)
        if record is None:
            continue
        # A second record for a code is a re-issue, not a contradiction.
        kb.restrictions[record.code] = record
        understood.add(position)
    kb.records_understood += len(understood)
    unreadable = _unreadable_records(elements, understood)
    kb.records_seen += len(understood) + sum(unreadable.values())
    kb.unrecognised.update(unreadable)


def _unreadable_records(elements: list, understood: set[int]) -> dict[str, int]:
    """Record-shaped elements this reader could not get a restriction out of.

    Without this a feed whose real shape differs from the one guessed here
    would read as *agreeing*: three records understood out of four hundred
    looks exactly like a feed that confirms those three and says nothing about
    the rest. So every element that looks like a restriction record but yielded
    no code is counted, and any count at all makes the comparison ``unknown``.

    A container is not a record, and neither is a record's own field. An element
    that *contains* recognised records -- ``<TicketRestrictions>`` around
    ``<Restriction>`` -- or *is inside* one -- ``<RestrictionCode>`` -- is left
    alone, or every well-formed feed would disqualify itself on its own
    vocabulary. Both directions are needed: the wrapper is an ancestor and the
    field is a descendant, and only one of them is obvious.
    """
    unreadable: dict[str, int] = {}
    understood_nodes: set[int] = set()
    for position in understood:
        understood_nodes.update(id(node) for node in elements[position].iter())
    for position, element in enumerate(elements):
        if position in understood or id(element) in understood_nodes:
            continue
        name = local_name(element.tag)
        if "restriction" not in name:
            continue
        # A container is only a container while something sits inside it.
        if any(id(node) in understood_nodes for node in element.iter()):
            continue
        if _restriction_from(element) is not None:
            continue
        unreadable[name] = unreadable.get(name, 0) + 1
    return unreadable


def _code_fields(element: ET.Element) -> list[tuple[int, str]]:
    """Every code field at or inside *element*, with its depth below it.

    Depth 1 is a direct child. The depth is what tells a record from a wrapper
    and a record from its own code field, which look identical by name alone.
    """

    found: list[tuple[int, str]] = []
    stack: list[tuple[ET.Element, int]] = [(child, 1) for child in element]
    while stack:
        node, depth = stack.pop()
        name = local_name(node.tag)
        text = (node.text or "").strip()
        if text and name in CODE_NAMES and CODE_SHAPE.match(text.upper()):
            found.append((depth, text.upper()))
        for child in node:
            stack.append((child, depth + 1))
    return found


def _restriction_from(element: ET.Element) -> KnowledgebaseRestriction | None:
    """A restriction from *element*, or ``None`` if it is not one.

    An element counts as a restriction record when it carries a child whose
    local name is a known code field *and* whose value looks like a code. Any
    other element is not a record and is not counted, so a document that this
    reader does not understand produces no records rather than wrong ones.

    Two things the real feed taught, both found by running this reader against
    it rather than against a fixture shaped like the guess:

    The record is the *innermost* element carrying a code. Search only direct
    children and the real 644 records read fine but yield no wording, because
    the feed wraps the wording as
    ``TicketRestriction > Restrictions > Restriction > DetailsOutward``. Search
    everything and three other things start reading as records: the file's root,
    each ``RestrictionCode`` field (a leaf whose own text is its own code), and
    so 1,289 "records" of which the 644 code fields are last, and last wins --
    every code ends up mapped to a bare field with no wording, which is the
    "partly understood" shape this reader exists to catch. So the code must be
    a direct child, and no code may sit deeper than that: that is what makes
    the root a wrapper rather than a record.

    The wording, once a record is established, is found wherever it sits inside
    it. Everything within a record's own extent is a field of that record.
    """

    codes = _code_fields(element)
    if not codes or any(depth != 1 for depth, _ in codes):
        return None
    code = codes[0][1]
    description = ""
    outward = ""
    return_text = ""

    for child in element.iter():
        if child is element:
            continue
        name = local_name(child.tag)
        text = (child.text or "").strip()
        if not text or name in CODE_NAMES:
            continue
        if name in DESCRIPTION_NAMES:
            description = text
        elif name in OUTWARD_NAMES:
            outward = text
        elif name in RETURN_NAMES:
            return_text = text
    return KnowledgebaseRestriction(
        code=code, description=description, outward_text=outward, return_text=return_text
    )


def carries_wording(reference: KnowledgebaseRestriction) -> bool:
    """Whether a reference record says anything at all about its condition."""
    return bool(
        reference.description.strip() or reference.outward_text.strip() or reference.return_text.strip()
    )


@dataclass(frozen=True)
class RestrictionCheck:
    """The answer to "does the portal still publish these conditions?"."""

    status: str
    compared: int = 0
    listed: int = 0
    missing: int = 0
    #: The codes the portal no longer lists, so the page can name them rather
    #: than asserting a count. A reader is entitled to know *which* condition
    #: is missing, because that is the one they would otherwise trust.
    unlisted: tuple[str, ...] = ()
    note: str = ""
    #: When the reference feed says it was published, and when it was last
    #: confirmed. The first is the portal's own word for its vintage; the
    #: second is when this project's downloader last asked.
    published: str = ""
    checked_at: str = ""

    @property
    def verified(self) -> bool:
        """Whether a claim of confirmation may be made at all.

        A count of zero compared codes is not confirmation. It is the absence
        of any evidence, and a page that read it as confirmation would be
        asserting something it did not check.
        """

        return self.status == CHECKED and self.compared > 0


def check_restrictions(
    codes: Iterable[str],
    kb: Knowledgebase | None,
    *,
    published: str = "",
    checked_at: str = "",
) -> RestrictionCheck:
    """Whether the portal still publishes every condition the claim covers.

    *codes* is the set of restriction codes the claim is about. For a page that
    is the codes its own rows show, which is the set a reader can check.

    What is compared is *publication*, not wording, and that is not a
    simplification -- it is the only thing this feed can honestly be asked. Run
    against the real download, the two feeds describe the same conditions in
    different vocabularies: the fares feed says ``VALID ON ANY TRAIN 0930 OR
    LATER M-F`` where the portal's own record says "Not valid to depart the
    origin station shown on the ticket until 09:30". Comparing the two texts
    reported 628 of 628 conditions disagreeing on a feed where nothing at all
    did, which is a false alarm printed on every page of every release.

    So the claim is the one the data supports: the portal still lists these
    conditions. That is checkable, it catches a condition being retired, and it
    cannot be wrong in the direction of crying wolf. A missing code is reported
    and named, because a page quoting a condition the portal no longer lists
    is telling a reader something the portal would not.
    """

    if kb is None or not kb.loaded:
        return RestrictionCheck(
            status=ABSENT,
            note=(kb.problem if kb is not None and kb.problem else "no reference feed was read"),
        )
    if not kb.usable:
        detail = kb.problem
        if not detail and kb.unrecognised:
            names = ", ".join(sorted(kb.unrecognised))
            detail = f"{sum(kb.unrecognised.values())} record(s) were not understood ({names})"
        if not detail and kb.records_understood:
            # Codes were read and the wording was not. The feed was parsed
            # successfully, which is exactly the case where a reader might
            # report a confirmed check, so the note has to say what was
            # actually found rather than blame the file.
            detail = (
                f"{kb.records_understood} restriction record(s) were read but none carried a "
                "description or validity text, so this is not known to be a feed of "
                "restriction conditions at all"
            )
        if not detail:
            detail = "the reference feed held no restriction records this reader recognises"
        return RestrictionCheck(status=UNKNOWN, note=detail, published=published, checked_at=checked_at)

    compared = listed = 0
    unlisted: list[str] = []
    for code in sorted({(str(one) or "").strip().upper() for one in codes}):
        if not code:
            continue
        compared += 1
        if kb.restrictions.get(code) is None:
            unlisted.append(code)
        else:
            listed += 1
    if compared == 0:
        return RestrictionCheck(
            status=UNKNOWN,
            note="this page quotes no restriction condition the reference feed could speak to",
            published=published,
            checked_at=checked_at,
        )
    status = CHECKED if not unlisted else UNPUBLISHED
    return RestrictionCheck(
        status=status,
        compared=compared,
        listed=listed,
        missing=len(unlisted),
        unlisted=tuple(unlisted),
        published=published,
        checked_at=checked_at,
    )
