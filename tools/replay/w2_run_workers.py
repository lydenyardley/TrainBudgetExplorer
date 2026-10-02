"""W2: the runner asks the machine what it can hold, not what it has cores for.

`min(8, cpu_count())` is a core count wearing a memory claim. On this machine
it is eight, and eight workers die with a MemoryError inside the pool
initialiser after five minutes having written no pages, reproducibly. The
count now comes from `build_workers.worker_budget`, which is measured.

The comment above it carried a projection this change falsifies: "about 20
minutes on eight cores and 81 on two". Measured on this machine, four workers
run at 0.77 pages/s and the whole set extrapolates to about 63 minutes from a
cold start, which is within a minute of the release workflow's own recorded
54 minutes of page building plus a 279s load at three workers.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD = '''    if args.all_origins:
        # Each origin's page is independent and the work is CPU-bound, so the
        # worker count is the core count. Left at the builder's default of one,
        # the whole network took 2,718 / 0.28 pages/s -- over two and a half
        # hours on this machine, and about a quarter of that with the cores
        # this runner actually has.
        cmd += ["--all-origins", "--workers", str(min(8, os.cpu_count() or 1))]'''

NEW = '''    if args.all_origins:
        # Each origin's page is independent and the work is CPU-bound, so the
        # worker count would be the core count if cores were the only thing
        # that mattered. They are not: every worker is handed the whole
        # national timetable, and min(8, cpu_count()) -- eight, here -- dies
        # with a MemoryError in the pool initialiser after five minutes,
        # reproducibly, having written no pages. The budget measures what a
        # worker costs and asks the machine what it has, and caps the answer at
        # the largest count measured to finish.
        #
        # Measured here, real feed, four workers: the feeds load in 145s, the
        # pool takes a further 83s, and the 2,712 pages then take 121 minutes at
        # 0.37 pages/s -- about two hours from a cold start. The first 239 pages
        # arrive at 0.77 pages/s, because the builder works through the origin
        # list and the early ones are priced for a handful of destinations; a
        # stopwatch over those is not a stopwatch over the work. One worker is
        # 2,712 / 0.093 -- most of a working day.
        # The free-memory figure is read once and named, because the count it
        # produces is the number a reader would ask about and "1 worker" on its
        # own does not say whether that was a choice or a shortage.
        free = free_memory_bytes()
        workers = worker_budget(free_bytes=free)
        print(f"Building the whole network on {workers} worker(s)"
              + (f", with {free / 1e9:.1f} GB free." if free is not None else "."))
        cmd += ["--all-origins", "--workers", str(workers)]'''

OLD_IMPORT = "from build_demo_page import NOTICES, RELEASE_MANIFEST_NAME  # noqa: E402"
NEW_IMPORT = ("from build_demo_page import NOTICES, RELEASE_MANIFEST_NAME  # noqa: E402\n"
              "from build_workers import free_memory_bytes, worker_budget  # noqa: E402")

patch(
    "run.py",
    [
        (OLD_IMPORT, NEW_IMPORT),
        (OLD, NEW),
    ],
)
