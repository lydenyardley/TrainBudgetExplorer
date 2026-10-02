"""Build one commit: replay a named group of patches, stage, commit.

The edits are patch scripts rather than hand-made, so a logical commit is a
run of named scripts rather than a set of hunks picked out of a finished diff.
Each group carries the page change and the tests that cover it, because a commit
without its tests is a commit a reviewer cannot check.

    python tools/replay/commit_group.py all <message-dir>

or, one group at a time:

    python tools/replay/commit_group.py columns tools/replay/messages/m-columns.txt

Run with no arguments to list the groups. The order below is the order the
patch scripts apply in -- a few of them anchor on text an earlier one writes,
so it is not free to rearrange -- and each group starts from the commit before
it, so `git log` reads as a sequence of decisions rather than as one large
change described afterwards.

The browser suite is not replayed and not grouped: it is a set of measurements
over the finished page, so it is one hand-edited commit at the end. A group
before it leaves `tests/browser_test.cjs` describing the page as it was, and
`python -m unittest discover -s tests` green.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize import normalise_page  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
CACHE = Path(__file__).resolve().parent

SOURCE = [
    "page_templates.py",
    "build_demo_page.py",
    "run.py",
    "make_synthetic_feed.py",
]
TESTS = ["tests/test_build_demo_page.py", "tests/test_atoc_fares.py"]
BROWSER = "tests/browser_test.cjs"

# group -> (patch scripts, files to stage, whether the page needs normalising)
GROUPS: dict[str, tuple[tuple[str, ...], tuple[str, ...], bool]] = {
    "columns": (
        ("c1_columns.py", "tg_columns.py", "tg_columns_mid.py"),
        ("page_templates.py", "tests/test_build_demo_page.py"),
        True,
    ),
    "budget": (
        ("c1b_css.py", "tg_budget.py"),
        ("page_templates.py", "tests/test_build_demo_page.py"),
        True,
    ),
    "railcard": (
        ("c2_cardnote.py", "c2b_drawer_listener.py", "c5_expander.py", "tg_railcard.py", "tg_railcard_late.py"),
        ("page_templates.py", "tests/test_build_demo_page.py"),
        True,
    ),
    "distill": (
        ("c3_distill.py", "tg_distill.py"),
        ("page_templates.py", "build_demo_page.py", "tests/test_build_demo_page.py"),
        True,
    ),
    "shortlist": (
        ("c4_shortlist.py", "c4b_shortlist_wiring.py", "c10_chip_button.py",
         "c12_bar_above_count.py", "tg_shortlist.py", "tg_shortlist_late.py"),
        ("page_templates.py", "tests/test_build_demo_page.py"),
        True,
    ),
    "width": (
        ("c6_table_width.py", "c11_panel_wrap.py"),
        ("page_templates.py", "tests/test_build_demo_page.py"),
        True,
    ),
    "picker": (
        ("c7_picker.py", "c7b_slot.py", "c7c_picker_place.py", "c13_escape.py"),
        ("page_templates.py", "build_demo_page.py", "tests/test_build_demo_page.py"),
        True,
    ),
    "runner": (
        ("c8_runner.py", "tg_runner_module.py", "tg_runner.py"),
        ("run.py", "tests/test_build_demo_page.py"),
        False,
    ),
    "fixture": (
        ("c9_fixture.py", "f1_fixture_tests.py", "tg_fixture.py"),
        ("make_synthetic_feed.py", "tests/test_atoc_fares.py", "tests/test_build_demo_page.py"),
        False,
    ),
}

ORDER = list(GROUPS)


def run(*args: str) -> None:
    subprocess.run(list(args), cwd=ROOT, check=True)


def build(group: str, message_file: Path) -> None:
    scripts, staged, normalise = GROUPS[group]
    # Start from the commit before this one.
    run("git", "checkout", "--", *(SOURCE + TESTS + [BROWSER]))
    if normalise:
        normalise_page()
    for script in scripts:
        print("--", script)
        run(sys.executable, str(CACHE / script))
    run("git", "add", "--", *staged)
    run("git", "commit", "-F", str(message_file))
    run("git", "show", "--stat", "--oneline", "HEAD")


def main(argv: list[str]) -> int:
    if not argv:
        for name, (scripts, staged, _normalise) in GROUPS.items():
            print(f"{name:10s} {' '.join(scripts)}")
            print(f"{'':10s} stages {', '.join(staged)}")
        return 0
    if argv[0] == "all":
        directory = Path(argv[1])
        for group in ORDER:
            print("=" * 12, group)
            build(group, directory / f"m-{group}.txt")
        return 0
    build(argv[0], Path(argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
