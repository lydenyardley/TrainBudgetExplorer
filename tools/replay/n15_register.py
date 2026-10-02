"""N15: register the journey-data pass in the replay driver.

Four scripts, in order: the test for a passing stop, the parser fix it fails
without, the union of the timetable focus set, and the test that holds the
union in place.

They sit after the ones this session added for the five UI defects. The chain
still stops before reaching any of them, at `r3_note_tests.py`, which is the
gap named in 70ee802 and unchanged here.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from patch import patch  # noqa: E402

OLD = '''                "n7_browser.py", "n8_railcard_checks.py"):'''

NEW = '''                "n7_browser.py", "n8_railcard_checks.py",
                # The journey-data pass, in the order it was found: the test
                # first, then the fix it fails without.
                "n11_passing_stop_test.py", "n12_zero_times.py",
                "n13_focus_destinations.py", "n14_focus_test.py"):'''

if __name__ == "__main__":
    patch("tools/replay/replay.py", [(OLD, NEW)])