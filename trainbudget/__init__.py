"""Train Budget Explorer.

The modules are grouped by the area the map in AGENTS.md names, so a reader
who knows which half of the problem they are looking at knows which folder to
open. Every module keeps its own name, so a reader who knows `build_pool`
finds it in the folder the build lives in.
"""

from pathlib import Path

#: The repository root. A module three folders deep still needs the place
#: the caches, the feeds and the built site live relative to, and this is
#: the one place that answer is written.
ROOT = Path(__file__).resolve().parent.parent
