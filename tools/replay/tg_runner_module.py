"""The runner's test needs a module it did not import.

`test_a_build_older_than_the_sources_is_not_served` writes a manifest's mtime
into the future to make a build look current, and it calls `time.time()` to do
it. The import is at module level rather than inside a test, so the per-test
split that puts each test with its change does not carry it: it is written here,
with the change that needs it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD = """import tempfile
import unittest"""

NEW = """import tempfile
import time
import unittest"""

patch("tests/test_build_demo_page.py", [(OLD, NEW)])
