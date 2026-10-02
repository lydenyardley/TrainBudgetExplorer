"""T3: the last three failures.

The change-count assertion still carried the ternary the function used to be
written with; the shortlist test still looked for a per-row button the design
removed in favour of one select; and the freshness test used time.time()
without importing time.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD_COUNT = r"""        self.assertIn('return changes === 0 ? "Direct"'.replace("? ", "? "), self.html)"""

NEW_COUNT = r"""        self.assertIn('if (changes === 0) return "Direct";', self.html)
        self.assertIn('if (changes === 1) return "1 change";', self.html)"""

OLD_SAVE = r"""        self.assertIn('save.setAttribute("aria-label", "Shortlist " + destination.name);', self.html)"""

NEW_SAVE = r"""        # One control for the whole page rather than a button on every row:
        # twenty rows is twenty buttons that all say the same thing, and a
        # reader comparing prices wants one list, not twenty ways of making
        # it. The select's own options are the rows on this page.
        self.assertIn('document.querySelectorAll("#rows tr[data-crs]")', self.html)
        self.assertIn(".filter((crs) => !inShortlist(crs));", self.html)"""

OLD_IMPORT = """import tempfile
import unittest"""

NEW_IMPORT = """import tempfile
import time
import unittest"""

patch(
    "tests/test_build_demo_page.py",
    [
        (OLD_COUNT, NEW_COUNT),
        (OLD_SAVE, NEW_SAVE),
        (OLD_IMPORT, NEW_IMPORT),
    ],
)