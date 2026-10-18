"""Hold the station page's controls to being drawn from the state, not read back.

After R4 of the 18 October 2026 agent-friendliness plan, whose whole record is in
`docs/open-work.md`, `page/station/state.js` is the page's one mutable object: a control writes into it once, every render derives
from it, and `applyState` is the one place a control is written from it
(`page/station/url-state.js`). A module that *reads* a control back during a
session is the defect R4 closed six times over -- the day lost on Back, the tick
that was not the shortlist, the card swapping the row under the reader -- because
a fact held in an element has a second writer the moment anything else touches it.

A read is a `.value` or `.checked` that is not an assignment. A write is how the
state reaches the DOM, so writes are not what this counts. The counts were
measured when R4 landed, one per panel, and they are a ratchet in the shape
`tools/check_types.py` uses: a panel may not grow one, a panel that loses one has
its number lowered in the same commit, and a new panel joins the table with its
own honest number rather than appearing unmeasured.

    python -m tools.check_page_state            # the ratchet
    python -m tools.check_page_state --census   # every panel's count, and fail on nothing

Exit codes: 0 every panel is at or under its number, 1 a panel is over it or a
panel in the table is missing, 2 there is no page to read. A count that could not
be taken is not a pass.

**What it does not do.** It counts, it does not judge: a read inside a gesture
(`Number(budget.value)` is what the reader just typed) and a read compared against
a chip's markup (`input.value === "all"`) look the same to it. The table is a
size, and the size falling is the evidence; the reason a particular read is there
belongs in the comment beside it.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANELS = "page/station"

#: Reads of a control's own state, per panel, measured 18 October 2026 when R4
#: landed. `state.js` is the object itself and keeps the reads its gestures make;
#: `url-state.js` is the projection and reads which controls this page offers.
BUDGET = {
    "budget.js": 0,
    "fare-panel.js": 0,
    "filters.js": 12,
    "format.js": 0,
    "payload.js": 0,
    "picker.js": 2,
    "provenance.js": 0,
    "railcards.js": 0,
    "row-actions.js": 0,
    "row-cells.js": 0,
    "service-day.js": 0,
    "shortlist.js": 0,
    "state.js": 7,
    "table.js": 0,
    "ticket-modes.js": 1,
    "url-state.js": 5,
    "wiring.js": 7,
}

#: `.value` or `.checked` that is not the left side of an assignment or a
#: comparison with one. `foo.checked = true` writes; `foo.checked` reads.
ACCESS = re.compile(r"\.(?:value|checked)\b(?!\s*=(?!=))")
LINE_COMMENT = re.compile(r"//[^\n]*")
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def reads(source: str) -> int:
    """How many control reads a panel's source makes."""
    text = BLOCK_COMMENT.sub("", LINE_COMMENT.sub("", source))
    return len(ACCESS.findall(text))


def panels(root: Path) -> dict[str, int]:
    """Every panel under `page/station`, read."""
    directory = root / PANELS
    files = sorted(path for path in directory.glob("*.js") if path.is_file())
    if not files:
        raise FileNotFoundError(f"no panel under {PANELS}")
    return {path.name: reads(path.read_text(encoding="utf-8")) for path in files}


def check(root: Path, census: bool) -> int:
    try:
        found = panels(root)
    except FileNotFoundError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    over = {name: count for name, count in found.items()
            if name not in BUDGET or count > BUDGET[name]}
    missing = sorted(name for name in BUDGET if name not in found)
    if census:
        for name in sorted(found):
            budget = BUDGET.get(name)
            print(f"{name:22} {found[name]:3} read(s)"
                  + ("" if budget is None else f", budget {budget}"))
        return 0
    if missing:
        print(
            "error: the budget names " + ", ".join(missing)
            + " and no panel of that name exists: lower the table to the page",
            file=sys.stderr,
        )
        return 2
    if over:
        for name in sorted(over):
            was = BUDGET.get(name)
            print(
                f"{PANELS}/{name}: {over[name]} control read(s)"
                + (f", {was} when R4 landed" if was is not None else ", not in the budget")
            )
        print(
            "a render reads the state, not the controls: read STATE, or lower a"
            " number in tools/check_page_state.BUDGET with the reason",
            file=sys.stderr,
        )
        return 1
    # A budget above the count is not a failure, because a panel that got
    # simpler is the point; it is said out loud so the table keeps following the
    # page down rather than becoming a number nobody reads.
    slack = sorted(name for name, count in found.items() if count < BUDGET[name])
    for name in slack:
        print(f"note: {name} is at {found[name]} read(s); the budget says {BUDGET[name]}")
    print(f"{len(found)} panel(s), no control read past its budget")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--census",
        action="store_true",
        help="print every panel's count, and fail on nothing",
    )
    args = parser.parse_args(argv)
    return check(ROOT, args.census)


if __name__ == "__main__":
    raise SystemExit(main())
