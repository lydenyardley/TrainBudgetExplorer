"""Replace files atomically, retrying a moment's sharing lock.

Windows refuses the replace while an indexer, a virus scanner, or a reader
holds the destination open. The lock is usually released in milliseconds, so
the wait is bounded and the last attempt still raises for an operator to see.
"""

from __future__ import annotations

import time
from pathlib import Path


def replace_with_retry(temporary: Path, path: Path, attempts: int = 5) -> None:
    """Put ``temporary`` in place of ``path``, waiting out a transient lock."""
    for attempt in range(attempts):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.2 * (attempt + 1))
