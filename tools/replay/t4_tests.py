"""T4: the plural branch of the change count.

The count reads "1 change" from a ternary rather than an early return, and the
test that says so should say what the page says.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD = r"""        self.assertIn('if (changes === 1) return "1 change";', self.html)"""

NEW = r"""        self.assertIn(
            'return changes === 1 ? "1 change" : changes + " changes";', self.html
        )"""

patch("tests/test_build_demo_page.py", [(OLD, NEW)])