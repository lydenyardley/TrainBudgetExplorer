"""W3: the release workflow had the same worker count and the same exposure.

`max(2, os.cpu_count())` on a runner is a core count, and the runner that
publishes the site is a machine like any other: every worker is handed the
whole national timetable. On a two-vCPU runner it asks for two, which the
budget also allows; on a bigger runner it asks for more workers than have ever
been measured to finish the build. The count now comes from the same measured
budget the runner uses, so the two paths cannot drift apart.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD_COMMENT = '''          # The worker count is read from the runner rather than written down:
          # the work is CPU-bound, so the useful worker count is the core
          # count, and a runner with more cores than this repository's machine
          # should get more workers for free.'''
NEW_COMMENT = '''          # The worker count is read from the runner rather than written down,
          # because a runner with more memory than this repository's machine
          # should get more workers for free. It was os.cpu_count() alone,
          # which is a core count wearing a memory claim: every worker is
          # handed the whole national timetable, and eight of them die with a
          # MemoryError in the pool initialiser having written no pages. The
          # budget measures what a worker costs, asks the runner what it has,
          # and caps the answer at the largest count measured to finish.'''

OLD_FLAG = '''            --workers "$(python -c 'import os; print(max(2, os.cpu_count() or 2))')" \\'''
NEW_FLAG = '''            --workers "$(python -c 'from build_workers import worker_budget; print(worker_budget())')" \\'''

patch(
    ".github/workflows/deploy.yml",
    [
        (OLD_COMMENT, NEW_COMMENT),
        (OLD_FLAG, NEW_FLAG),
    ],
)
