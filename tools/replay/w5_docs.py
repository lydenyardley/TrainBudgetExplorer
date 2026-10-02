"""W5: the docs carried the figure this session measured to be wrong.

"About 20 minutes on eight cores, 81 on two" appears in the README's Run It
section and in ADR-0055's first decision, and both were measured against a feed
without the national timetable. With it, and on a machine that can hold four
workers, the set is about 63 minutes. Eight workers do not run at all.

ADR-0057 records the worker count as its own decision, because ADR-0055 chose
the default build and this is about how that build is carried out: a decision
the release workflow and the runner have to agree on cannot live only in a
constant in build_workers.py.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD_README = """That builds one page per priced station from the current feed, serves it at
http://localhost:8741, and opens your browser. It says what that costs before it
starts — about 20 minutes on eight cores, 81 on two — and the next run serves
what the first one wrote and starts immediately. """

NEW_README = """That builds one page per priced station from the current feed, serves it at
http://localhost:8741, and opens your browser. It says what that costs before it
starts — about an hour on four workers, measured against the national timetable
on a 15.8 GB machine — and the next run serves what the first one wrote and
starts immediately. The worker count comes from what the machine has free rather
than from how many cores it has, because every worker holds the whole timetable;
a machine short of memory builds on one worker rather than dying (ADR-0057).
"""

OLD_ADR = """**1. The default build is the whole network, and it says what that costs before it
starts.** `python run.py` builds one page per priced station, prints the measured
cost (about 20 minutes on eight cores, 81 on two — ADR-0024, re-measured
1 October 2026), and says that the next run will serve what this writes."""

NEW_ADR = """**1. The default build is the whole network, and it says what that costs before it
starts.** `python run.py` builds one page per priced station, prints the measured
cost, and says that the next run will serve what this writes. The cost was
originally recorded here as about 20 minutes on eight cores, 81 on two. That was
measured without the national timetable, and the eight-worker build it assumed
dies with a MemoryError (ADR-0057). Re-measured with the timetable on a 15.8 GB
machine, 2 October 2026: 0.19 pages/s per worker, so about 63 minutes on the
four workers that machine can hold and most of a working day on one. The figure
in this decision is withdrawn rather than qualified."""

patch(
    "README.md",
    [(OLD_README, NEW_README)],
)

patch(
    "adr/ADR-0055-the-runner-builds-what-the-reader-will-ask-for.md",
    [(OLD_ADR, NEW_ADR)],
)
