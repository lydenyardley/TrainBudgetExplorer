"""W6: the figure I put in the docs an hour ago was measured over a burst.

63 minutes and 0.19 pages/s per worker came from a nine-minute window early in
a build. That window held the smallest stations -- the builder works through the
origin list, and pages written in the first minutes are priced for a handful of
destinations -- so it measured the cheapest tenth of two and a half thousand
pages and called it the rate.

The whole-network build finished: 2,712 pages, first at 10:29:52, last at
12:30:57. That is 121 minutes of page building at 0.37 pages/s on four workers,
or 0.093 pages/s per worker, and about two hours from a cold start including the
145s load, the 83s pool start and the chooser.

Every number this session wrote down from the burst is twice too fast, and it
is now written down in the README, in ADR-0055 and in ADR-0057 as well as in
run.py's own comment. A projection taken from the first tenth of the work is
not a measurement of the work, and the difference between 63 minutes and 121 is
the difference between believing a build takes an hour and planning for two.

The release workflow's own comment records 0.84 pages/s and a 54-minute
extrapolation, taken from "the first twenty pages". That is the same mistake on
a different machine, and it is left in place with a note rather than rewritten:
it is a measurement this session did not take, and the fix for it is a run, not
an edit.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD_RUN = '''    # The default is now the whole network, and this says what that costs
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

NEW_RUN = '''    # The default is now the whole network, and this says what that costs
    # before it starts rather than after it has finished. Measured on the real
    # feed with the national timetable, 2 October 2026, on this machine, by a
    # whole-network build rather than by a stopwatch over its first minutes:
    # 2,712 priced stations in 121 minutes of page building at 0.093 pages/s
    # per worker, so about two hours from a cold start on the four workers the
    # budget below chooses, and most of a working day on one.
    #
    # The figure this replaces was itself wrong twice over -- "20 minutes on
    # eight cores" came from a feed without the national timetable, and the 63
    # minutes that followed came from the first nine minutes of a build, which
    # are the cheapest stations in the set. A rate taken from the first tenth of
    # the work is not a rate for the work. Both are withdrawn rather than
    # qualified (ADR-0024, ADR-0050, ADR-0055, ADR-0057). The fast
    # single-origin page is still one flag away, because a build of one station
    # is the right tool for working on one station and the wrong thing to
    # double-click.'''

OLD_README = """starts \u2014 about an hour on four workers, measured against the national timetable
on a 15.8 GB machine \u2014 and the next run serves what the first one wrote and"""

NEW_README = """starts \u2014 about two hours on four workers, measured by a whole-network build
against the national timetable on a 15.8 GB machine \u2014 and the next run serves
what the first one wrote and"""

OLD_ADR55 = '''machine, 2 October 2026: 0.19 pages/s per worker, so about 63 minutes on the
four workers that machine can hold and most of a working day on one. The figure
in this decision is withdrawn rather than qualified.'''

NEW_ADR55 = '''machine, 2 October 2026: 0.093 pages/s per worker, so about two hours on the
four workers that machine can hold and most of a working day on one. The figure
in this decision is withdrawn rather than qualified, and so is the 63 minutes
that replaced it here an hour earlier: that came from the first nine minutes of
a build, which are the cheapest stations in the set, and a rate taken from the
first tenth of the work is not a rate for the work.'''

OLD_ADR57 = """| a four-worker tree, sampled mid-build | **2.9 GB** total, parent down to 120 MB |
"""

NEW_ADR57 = """| a four-worker tree, sampled mid-build | **2.9 GB** total, parent down to 120 MB |

The wall time that budget was chosen against: a whole-network build of the real
feed, 2 October 2026, wrote 2,712 pages between 10:29:52 and 12:30:57. That is
121 minutes at 0.093 pages/s per worker on four workers, and about two hours
from a cold start including the 145s feed load, the 83s pool start and the
chooser. An earlier note in this file put it at 63 minutes, from a nine-minute
window early in a build; that window held the cheapest stations in the set, and
the error was a factor of two. The release workflow's own comment records
0.84 pages/s and 54 minutes from "the first twenty pages" -- the same mistake on
a different machine, left standing here because correcting it needs that run,
not this edit.
"""

patch("run.py", [(OLD_RUN, NEW_RUN)])
patch("README.md", [(OLD_README, NEW_README)])
patch("adr/ADR-0055-the-runner-builds-what-the-reader-will-ask-for.md", [(OLD_ADR55, NEW_ADR55)])
patch("adr/ADR-0057-the-worker-count-is-what-the-machine-can-hold.md", [(OLD_ADR57, NEW_ADR57)])
