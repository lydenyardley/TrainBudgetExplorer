"""C2b: the drawer's backdrop handler, which had nothing left to close.

The dialog is gone, so the listener that closed it by clicking the backdrop is
a reference to a variable that no longer exists, and it threw on every page
load before a single row was drawn.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

patch(
    "page_templates.py",
    [
        (
            "railcardDrawer.addEventListener(\"click\", (event) => {\n"
            "  if (event.target === railcardDrawer) railcardDrawer.close();\n"
            "});\n",
            "",
        ),
    ],
)
