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
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize import normalise_page  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
CACHE = Path(__file__).resolve().parent

subprocess.run(["git", "checkout", "--", "page_templates.py", "build_demo_page.py", "run.py",
                "make_synthetic_feed.py", "build_workers.py", ".github/workflows/deploy.yml",
                "tests/test_build_demo_page.py", "tests/test_atoc_fares.py",
                "README.md", "adr/ADR-0055-the-runner-builds-what-the-reader-will-ask-for.md"],
               cwd=ROOT, check=True)

for script in ("c1_columns.py", "c1b_css.py", "c2_cardnote.py", "c2b_drawer_listener.py", "c3_distill.py", "c4_shortlist.py", "c4b_shortlist_wiring.py", "c5_expander.py", "c6_table_width.py", "c7_picker.py", "c7b_slot.py", "c7c_picker_place.py", "c8_runner.py", "c9_fixture.py", "c10_chip_button.py", "c11_panel_wrap.py", "c12_bar_above_count.py", "c13_escape.py", "r1_real_feed_fixes.py", "r2_count_line.py", "r3_note_tests.py", "w1_worker_budget.py", "w2_run_workers.py", "w3_deploy_workers.py", "w4_runner_notice.py", "w5_docs.py", "t1_tests.py", "t2_tests.py", "t3_tests.py", "t4_tests.py", "t5_tests.py", "t6_worker_tests.py"):
    normalise_page()
    print("--", script)
    result = subprocess.run([sys.executable, str(CACHE / script)], cwd=ROOT)
    if result.returncode:
        sys.exit(result.returncode)
print("replayed")
