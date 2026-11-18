"""A Windows sharing lock, as the cache and page tests meet it.

Windows refuses the replace while an indexer, a virus scanner, or a reader
holds the destination open. The writer waits it out, so these tests refuse it
on purpose, twice, and observe the file rather than the clock.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator, Mapping
from pathlib import Path
from unittest import mock


@contextlib.contextmanager
def replace_fails(failures: Mapping[Path, int]) -> Iterator[dict[Path, int]]:
    """Refuse each named target's replace ``failures`` times, then allow it.

    Yields how many times each target was refused, so a test can show the lock
    was met rather than passed over.
    """
    limits = {Path(path): count for path, count in failures.items()}
    refused = dict.fromkeys(limits, 0)
    real_replace = Path.replace

    def locked(self, target):
        target = Path(target)
        if refused.get(target, 0) < limits.get(target, 0):
            refused[target] += 1
            raise PermissionError(13, "used by another process")
        return real_replace(self, target)

    with mock.patch.object(Path, "replace", locked):
        yield refused
