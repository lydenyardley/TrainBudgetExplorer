"""N12: `0000` is the CIF's absent marker, not midnight.

One line, and it is the root cause of four symptoms on the real Grindleford
page at once.

The CIF has no midnight. A time after midnight is written 2400 to 2949 -- the
real feed contains 2457, 2706, 2807 and 2847, read back by counting the four
digit time fields in the first 40MB of the MCA. So `0000` is never a clock
time; it is what the feed writes when a calling point has no time of that kind.

A train that passes a station is recorded exactly that way. The pass-through
time goes in `scheduled_pass`, which nothing here reads, and both public time
fields are left `0000`. Verified against the record the page's worst row came
from, a passing call at Grindleford on service C04439:

    location            GRNDLFD
    scheduled_arrival       (blank)
    scheduled_departure     (blank)
    scheduled_pass          0855   <- the real time, in a field nobody read
    public_arrival          0000   <- read as 535's neighbour: minute 0
    public_departure        0000   -> board = 0, not None

`CallingPoint.board` returns the public departure, `0` is not `None`, so the
departure index registered a departure from Grindleford at minute zero, and
every service that merely passed through became an outbound service leaving at
midnight. What the page then showed, all measured from that phantom zero:

    GRN -> Manchester Piccadilly   11 minutes
    GRN -> Liverpool Lime Street    7 minutes
    GRN -> Edge Hill                0 minutes

The same station on the one service that genuinely calls there gave the right
answer, GRNDLFD dep 591 to SHEFFLD arr 604, 13 minutes.

So `0000` is read as absent. That is the whole change: the four symptoms the
page showed were one mechanism. The absurd durations were it directly, and it
also explains the rows that said no service at all -- the phantom midnight
departures filled the connection budget with services that do not stop, so the
search stopped looking and never reached the real ones behind them.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from patch import patch  # noqa: E402

OLD = '''def _minutes(value: str) -> int | None:
    """Read a CIF time as minutes past midnight. Blank means the train does not stop."""
    digits = value.strip()
    if len(digits) < 4 or not digits[:4].isdigit():
        return None
    return int(digits[0:2]) * 60 + int(digits[2:4])'''

NEW = '''def _minutes(value: str) -> int | None:
    """Read a CIF time as minutes past midnight. Blank means the train does not stop.

    So does `0000`, and that is not a detail of the format. The CIF has no
    midnight: a time after it is written 2400 to 2949, so `0000` can only be
    the marker for "no time of this kind here". A train that passes a station
    is recorded that way -- its real time is in the pass-through field, which
    nothing here reads, and its public times are left `0000`.

    Read as a clock time it was midnight, which is a departure: 0 is not None,
    so the departure index took every station on the network to have a service
    leaving at minute zero, and every one of them was a train passing through.
    Measured on the real Grindleford page, that made Manchester eleven minutes
    away and Liverpool seven, because the duration was measured from a
    departure at midnight to a real arrival.
    """
    digits = value.strip()
    if len(digits) < 4 or not digits[:4].isdigit():
        return None
    if digits[:4] == "0000":
        return None
    return int(digits[0:2]) * 60 + int(digits[2:4])'''

if __name__ == "__main__":
    patch("atoc_timetable.py", [(OLD, NEW)])