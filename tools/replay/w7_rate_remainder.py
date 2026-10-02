"""W7: the two places the burst rate was still standing.

`run.py`'s own comment on the worker count and ADR-0057's consequences both
still said 63 minutes. They were written from the same nine-minute window as
the figures W6 corrects, and left behind because the first pass found the
sentence that announced the cost and not the two that repeat it.

The 0.77 pages/s they quote is the rate over the first 239 pages of a build,
which are the cheapest stations in the set. The whole-network figure is 0.37
pages/s on four workers.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD_RUN = '''        # Measured here, real feed, four workers: the feeds load in 145s, the
        # pool takes a further 83s, and the pages then arrive at 0.77 pages/s,
        # which puts the whole 2,712 at about 63 minutes from a cold start.
        # Left at the builder's default of one worker that is 2,718 / 0.19 --
        # nearly four hours.'''

NEW_RUN = '''        # Measured here, real feed, four workers: the feeds load in 145s, the
        # pool takes a further 83s, and the 2,712 pages then take 121 minutes at
        # 0.37 pages/s -- about two hours from a cold start. The first 239 pages
        # arrive at 0.77 pages/s, because the builder works through the origin
        # list and the early ones are priced for a handful of destinations; a
        # stopwatch over those is not a stopwatch over the work. One worker is
        # 2,712 / 0.093 -- most of a working day.'''

OLD_ADR = '''- A machine with room to spare builds the network in about 63 minutes; one
  without builds it on a single worker in most of a day, and says so.'''

NEW_ADR = '''- A machine with room to spare builds the network in about two hours; one
  without builds it on a single worker in most of a day, and says so.'''

patch("run.py", [(OLD_RUN, NEW_RUN)])
patch("adr/ADR-0057-the-worker-count-is-what-the-machine-can-hold.md", [(OLD_ADR, NEW_ADR)])
