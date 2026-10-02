"""W4: the runner's own notice carried a projection this session falsified.

"2,718 priced stations at roughly 0.28 pages/s per worker, so about 20 minutes
on eight cores and 81 on two" -- re-measured 2 October 2026 against the real
feed with the national timetable: 2,712 priced stations, 0.19 pages/s per
worker, and no eight-worker build at all, because eight workers die. Four
workers, the count the budget now chooses, run the set at 0.77 pages/s, which
is about 63 minutes of page building after a 145s load and an 83s pool start.

The release workflow's own recorded figure -- 54 minutes of page building plus
a 279s load at three workers -- was within a minute of this and is left alone:
it is a measurement of a different machine and it stands on its own evidence.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD = '''    # The default is now the whole network, and this says what that costs
    # before it starts rather than after it has finished. Measured on the real
    # feed: 2,718 priced stations at roughly 0.28 pages/s per worker, so about
    # 20 minutes on eight cores and 81 on two (ADR-0024, re-measured 1 October
    # 2026; ADR-0050). The fast single-origin page is still one flag away,
    # because a build of one station is the right tool for working on one
    # station and the wrong thing to double-click.'''

NEW = '''    # The default is now the whole network, and this says what that costs
    # before it starts rather than after it has finished. Measured on the real
    # feed with the national timetable, 2 October 2026, on this machine: 2,712
    # priced stations at 0.19 pages/s per worker, so an hour of building per
    # worker and about 63 minutes on the four workers the budget below chooses.
    # A single worker is most of a working day. The old figure -- 20 minutes on
    # eight cores -- was measured against a feed without the national timetable
    # and an eight-worker build that now dies with a MemoryError, so it is
    # withdrawn rather than qualified (ADR-0024, ADR-0050, ADR-0055). The fast
    # single-origin page is still one flag away, because a build of one station
    # is the right tool for working on one station and the wrong thing to
    # double-click.'''

patch("run.py", [(OLD, NEW)])
