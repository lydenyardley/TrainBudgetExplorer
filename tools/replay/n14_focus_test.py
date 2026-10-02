"""N14: the test for a timetable scoped to less than the page shows.

Written before the fix, and it fails without it.

This one reads the build's own wiring rather than driving it, and the comment
says so: the behaviour needs the real feed and a station reachable only as an
outbound single, which the synthetic fixture does not have. The behavioural
guard is the browser check "no row claims no service for a destination the
page's own payload times", which passes on the synthetic build for want of the
shape and fails on the real one. This test is the cheap one that runs always.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from patch import patch  # noqa: E402

OLD = '''if __name__ == "__main__":
    unittest.main(verbosity=2)'''

NEW = '''class TimetableFocusTest(unittest.TestCase):
    """The timetable index is scoped to the stations the page can show.

    It was scoped to the stations a return reaches, which is a narrower set:
    the outbound-single list reaches thirteen more on a real page. Those
    stations had no services in the index, so each was a row reading "No
    service" and "Unknown" -- a statement about the build wearing the voice of
    a statement about the network.

    This reads the wiring rather than driving the build. The behaviour needs
    the real feed and a station reachable only as an outbound single, which no
    synthetic fixture has; the behavioural guard is the browser check that no
    row claims no service for a destination the page's own payload times, and
    that check can only fail on a real page. This one runs everywhere.
    """

    def test_the_focus_set_covers_every_list_the_page_composes(self) -> None:
        source = Path(__file__).resolve().parent.parent / "build_demo_page.py"
        code = source.read_text(encoding="utf-8")
        start = code.index("focus_destinations: set[str] = set()")
        block = code[start:code.index("cache_path = (", start)]
        for query in (
            "page_destinations_within",
            "page_single_destinations_within",
            "publishable_destinations_within",
        ):
            self.assertIn(
                query, block,
                f"the timetable focus set does not include {query}, so one of the "
                f"three lists the page composes has no services in the index",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)'''

if __name__ == "__main__":
    patch("tests/test_atoc_timetable.py", [(OLD, NEW)])