"""Replay every page-template edit from a clean checkout, in order.

A normalisation pass went wrong and rewrote 21 unicode escapes as the literal
text "\1". Rather than hand-repair 21 sites, the file goes back to HEAD and the
whole edit sequence is re-applied by script, which is the same result with the
mistake absent.

`commit_group.py` normalises before every group, and it has to: a patch that
writes a fresh apostrophe -- `a seller's` in the fare-type comment, say --
lands after that group's own normalisation and is only tidied by the next one.
This applies every patch in one run, so it normalises before each one for the
same reason. Normalising twice over nothing changes nothing.

Two things about the boundary between this driver and the history it describes.

The restore list is filtered to the paths the checkout actually holds. Three
commits in the range (`eea30b6`, `8d8783a`, `be207f2`) create ADR-0053, 0054,
0055 and 0057, so a run against a base older than them has no file to check
out, and `git checkout --` treats an unknown pathspec as a fatal error: the
driver died on the tenth path of eleven and never reached a patch. A path the
base does not hold is not an error -- it is a path this run has nothing to
restore -- so it is dropped, and named at the end rather than silently dropped.

And the run ends by saying what it could not reconstruct. The replay claims to
land the finished state, so the last thing it does is compare every restored
file against HEAD and name any file that does not match. A mismatch is a patch
script that was never written, or one that aged; either way it is invisible
until something says so, and "replayed" on its own is a claim nothing checked.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize import normalise_page  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
CACHE = Path(__file__).resolve().parent

# Every file the edit sequence below touches. The restore is a superset of what
# the scripts patch: a file no script touches is restored to HEAD and stays
# there, which is the same as not restoring it, and being wrong about that is
# cheaper than a file left edited from an earlier run.
RESTORED = (
    "page_templates.py", "build_demo_page.py", "run.py",
    "make_synthetic_feed.py", "build_workers.py", ".github/workflows/deploy.yml",
    "tests/test_build_demo_page.py", "tests/test_atoc_fares.py",
    "README.md", "adr/ADR-0055-the-runner-builds-what-the-reader-will-ask-for.md",
)


def tracked(paths: tuple[str, ...] = RESTORED) -> list[str]:
    """The paths of ``paths`` the checkout holds.

    Asked of git rather than of the filesystem, because the filesystem answers
    a different question: a file left over from an earlier run is on disk and
    is not the checkout's to restore. A path git does not know is dropped here
    so `git checkout --` is never handed one, and returned to the caller so the
    run can name it.
    """
    result = subprocess.run(["git", "ls-files", "--error-unmatch", "--", *paths],
                            cwd=ROOT, capture_output=True, text=True)
    held = {line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()}
    return [path for path in paths if path.replace("\\", "/") in held]


def not_reconstructed(paths: list[str]) -> list[tuple[str, str, list[str]]]:
    """Every restored file that does not match HEAD, with the commits that touched it.

    Asked of git rather than compared here, because git knows how this checkout
    stores line endings and a byte comparison does not: a CRLF file checked out
    on Windows differs from the blob in the object store on every line, and a
    driver that compared the two itself would report every file as a gap. Git's
    own answer -- has the worktree moved away from HEAD for this path -- is the
    question being asked.

    Each gap is reported with the commits in the range that edited that file,
    because a file is not the useful unit of a missing patch. The commit is.
    """
    if not paths:
        return []
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", *paths], cwd=ROOT,
        capture_output=True, text=True,
    )
    out: list[tuple[str, str, list[str]]] = []
    for line in status.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip().replace("\\", "/")
        # A rename reads as "old -> new"; the new name is the one on disk.
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        log = subprocess.run(
            ["git", "log", "--format=%h %s", "-n", "6", "HEAD", "--", path],
            cwd=ROOT, capture_output=True, text=True,
        )
        commits = [entry for entry in log.stdout.splitlines() if entry.strip()]
        out.append((path, "differs from HEAD", commits))
    return out


if __name__ == "__main__":
    held = tracked()
    dropped = [path for path in RESTORED if path not in held]
    subprocess.run(["git", "checkout", "--", *held], cwd=ROOT, check=True)
    for path in dropped:
        print(f"-- no {path} in this checkout, not restoring it")

    for script in ("c1_columns.py", "c1b_css.py", "c2_cardnote.py", "c2b_drawer_listener.py", "c3_distill.py", "c4_shortlist.py", "c4b_shortlist_wiring.py", "c5_expander.py", "c6_table_width.py", "c7_picker.py", "c7b_slot.py", "c7c_picker_place.py", "c8_runner.py", "c9_fixture.py", "c10_chip_button.py", "c11_panel_wrap.py", "c12_bar_above_count.py", "c13_escape.py", "r1_real_feed_fixes.py", "r2_count_line.py", "r3_note_tests.py", "w6_whole_network_rate.py", "w7_rate_remainder.py", "w1_worker_budget.py", "w2_run_workers.py", "w3_deploy_workers.py", "w4_runner_notice.py", "w5_docs.py", "t1_tests.py", "t2_tests.py", "t3_tests.py", "t4_tests.py", "t5_tests.py", "t6_worker_tests.py",
                    # This pass: the five defects found by looking at a page.
                    # n1 narrow rows, n2 the railcard list, n3 the price note,
                    # n4 the journey facts, n5 the chip count, n6/n7/n8 their
                    # checks, n9 this registration.
                    "n1_narrow_rows.py", "n2_railcard_cards.py", "n3_was_ladder.py",
                    "n4_journey_facts.py", "n5_chip_space.py", "n6_tests.py",
                    "n7_browser.py", "n8_railcard_checks.py",
                    # The journey-data pass, in the order it was found: the test
                    # first, then the fix it fails without.
                    "n11_passing_stop_test.py", "n12_zero_times.py",
                    "n13_focus_destinations.py", "n14_focus_test.py",
                    # p1 the replay driver itself: restore only what the
                    # checkout holds, and name what it could not land. p2 the
                    # budget floor, in the page, in the checks that reach it,
                    # and in the test that pins the parser into the cache key.
                    "p1_replay_driver.py", "p2_budget_floor.py",
                    # p3 the browser check that judged a restriction condition
                    # by how it was spelled rather than by what it said.
                    "p3_condition_rule.py"):
        normalise_page()
        print("--", script)
        result = subprocess.run([sys.executable, str(CACHE / script)], cwd=ROOT)
        if result.returncode:
            sys.exit(result.returncode)

    gaps = not_reconstructed(held)
    if not gaps:
        print(f"replayed; all {len(held)} restored files match HEAD")
    else:
        print(f"replayed, but {len(gaps)} of {len(held)} restored files do not match HEAD:")
        for path, why, commits in gaps:
            print(f"  {path}: {why}")
            for commit in commits:
                print(f"    {commit}")
        sys.exit(1)
