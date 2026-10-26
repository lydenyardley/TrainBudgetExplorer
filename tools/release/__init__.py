"""The release workflow's steps, as commands a desktop can run and a test can hold.

`.github/workflows/deploy.yml` was 1,179 lines with 17 multi-line `run:` blocks,
and shell inside YAML can only be tested by pushing: 13 of the 23 commits that
touched it between 8 and 21 October 2026 were `fix(release)`, each one costing a
push and a run. Every step that does more than call one command now lives here as
`python -m tools.release.<step>`, with its test in `tools/test_release.py`, and the
workflow keeps the jobs, the matrices, the secrets and the calls (task 1 of the 21 October 2026
agent-friendly re-architecture audit, settled in `docs/settled-work.md`).
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: What the release publishes, stated once. The share build loads the timetable
#: because of it, the manifest check expects journey times because of it, and
#: the clearance job's `--release` is held to it by `tools/test_release.py`. It
#: was three literals in the workflow that a test had to keep agreeing.
RELEASE = ("fares", "timetable")


def output(name: str, value: str) -> None:
    """A step output for later jobs, or a line on stdout outside Actions."""
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")
    print(f"{name}={value}", flush=True)


def error(title: str, message: str) -> None:
    print(f"::error title={title}::{message}", flush=True)


def warning(title: str, message: str) -> None:
    print(f"::warning title={title}::{message}", flush=True)
