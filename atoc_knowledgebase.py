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
from dataclasses import dataclass, field
from pathlib import Path

# Local element names that have been used for a restriction code and for the
# three pieces of wording this project shows. Matched case-insensitively
# against the local name, so a namespace prefix or a differently-cased
# publisher does not defeat it. Deliberately a *set* of names: a single
# guessed name would either match nothing or, worse, match the wrong element.
CODE_NAMES = frozenset({"restrictioncode", "code", "restriction"})
DESCRIPTION_NAMES = frozenset({"description", "desc", "restrictiondescription"})
OUTWARD_NAMES = frozenset({"descout", "outwarddescription", "outwardtext", "desc_out"})
RETURN_NAMES = frozenset({"descrtn", "returndescription", "returntext", "desc_rtn"})

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

    def wording_matches(self, description: str, outward: str, return_text: str) -> bool:
        """Whether this record says the same thing as the fares feed's header.

        Compared on the three pieces of wording separately and on a normalised
        form, because a feed that reflows a line or changes its case has not
        changed the condition, and a page that reported that as a disagreement
        would be crying wolf until nobody read it.
        """

        return (
            _normalise(self.description) == _normalise(description)
            and _normalise(self.outward_text) == _normalise(outward)
            and _normalise(self.return_text) == _normalise(return_text)
        )


def _normalise(text: str) -> str:
    """Fold the differences that are not differences in meaning."""

    return " ".join((text or "").split()).upper()


# The four answers a check can give. Kept as constants so a caller cannot
# invent a fifth by misspelling a string, and so the page's wording for each
# is written in one place.
CHECKED = "checked"
DISAGREES = "disagrees"
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

        True only when the feed parsed, at least one record was understood, and
        nothing was left unrecognised. A partially understood feed is not a
        feed that agrees; it is a feed whose agreement is unknown for the part
        it did not understand.
        """

        return (
            self.loaded
            and self.problem is None
            and self.records_understood > 0
            and not self.unrecognised
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
    kb.records_understood = len(understood)
    unreadable = _unreadable_records(elements, understood)
    kb.records_seen = len(understood) + sum(unreadable.values())
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


def _restriction_from(element: ET.Element) -> KnowledgebaseRestriction | None:
    """A restriction from *element*, or ``None`` if it is not one.

    An element counts as a restriction record when it carries a child whose
    local name is a known code field *and* whose value looks like a code. Any
    other element is not a record and is not counted, so a document that this
    reader does not understand produces no records rather than wrong ones.
    """

    code = ""
    description = ""
    outward = ""
    return_text = ""
    for child in element:
        name = local_name(child.tag)
        text = (child.text or "").strip()
        if not text:
            continue
        if not code and name in CODE_NAMES and CODE_SHAPE.match(text.upper()):
            code = text.upper()
        elif name in DESCRIPTION_NAMES:
            description = text
        elif name in OUTWARD_NAMES:
            outward = text
        elif name in RETURN_NAMES:
            return_text = text
    if not code:
        return None
    return KnowledgebaseRestriction(
        code=code, description=description, outward_text=outward, return_text=return_text
    )


def _carries_wording(reference: KnowledgebaseRestriction) -> bool:
    """Whether a reference record says anything at all about its condition."""
    return bool(
        reference.description.strip() or reference.outward_text.strip() or reference.return_text.strip()
    )


@dataclass(frozen=True)
class RestrictionCheck:
    """The answer to "is the printed condition still the published one?"."""

    status: str
    compared: int = 0
    agree: int = 0
    disagree: int = 0
    #: Codes whose wording differs, so the page can name them rather than
    #: asserting a count. A reader is entitled to know *which* condition moved.
    differing: tuple[tuple[str, str], ...] = ()
    note: str = ""
    #: When the reference feed says it was published, and when it was last
    #: confirmed. The first is the portal's own word for its vintage; the
    #: second is when this project's downloader last asked.
    published: str = ""
    checked_at: str = ""

    @property
    def verified(self) -> bool:
        """Whether a claim of agreement may be made at all.

        A count of zero compared codes is not agreement. It is the absence of
        any evidence, and a page that read it as agreement would be asserting
        something it did not check.
        """

        return self.status == CHECKED and self.compared > 0


def check_restrictions(
    fares_headers: dict[str, object],
    kb: Knowledgebase | None,
    *,
    published: str = "",
    checked_at: str = "",
) -> RestrictionCheck:
    """Compare the fares feed's restriction wording with the reference feed.

    *fares_headers* maps a code to an object exposing ``description``,
    ``outward_text`` and ``return_text`` -- the ``RestrictionHeader`` the
    ``.RST`` parser produces. Only codes the page actually shows are compared,
    because agreement about a condition nobody is reading is not a fact about
    this page.
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
        if not detail:
            detail = "the reference feed held no restriction records this reader recognises"
        return RestrictionCheck(status=UNKNOWN, note=detail, published=published, checked_at=checked_at)

    compared = agree = disagree = 0
    differing: list[tuple[str, str]] = []
    for code, header in sorted(fares_headers.items()):
        if not code:
            continue
        reference = kb.restrictions.get(code)
        if reference is None:
            # The reference feed not carrying a code is not a contradiction of
            # it. Skipped rather than counted, and the count of compared codes
            # is what the claim is made from.
            continue
        compared += 1
        if not _carries_wording(reference):
            # A reference record with no wording is not a claim about this
            # condition, so it cannot be compared and cannot be said to
            # disagree. Treating it as a disagreement would be the worst
            # possible failure for this feature: it would tell a reader the
            # reference feed has retired a condition when the truth is that
            # this reader did not find the text.
            compared -= 1
            continue
        if reference.wording_matches(
            header.description, header.outward_text, header.return_text
        ):
            agree += 1
        else:
            disagree += 1
            differing.append((code, reference.description or reference.outward_text))
    if compared == 0:
        return RestrictionCheck(
            status=UNKNOWN,
            note="the reference feed describes none of the conditions on this page",
            published=published,
            checked_at=checked_at,
        )
    status = CHECKED if disagree == 0 else DISAGREES
    return RestrictionCheck(
        status=status,
        compared=compared,
        agree=agree,
        disagree=disagree,
        differing=tuple(differing),
        published=published,
        checked_at=checked_at,
    )
