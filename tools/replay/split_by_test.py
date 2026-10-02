"""Cut the test-file changes by test, so a commit can land with its own tests.

The t-scripts patch the suite in five passes, and each pass carries assertions
for many different tests. A logical commit has to land with the tests that cover
it, so the suite's changes are re-cut here by the test they live in: this
compares HEAD's copy of `tests/test_build_demo_page.py` with the finished one,
method by method, and writes one patch script per group of methods.

    python tools/replay/split_by_test.py

The mapping from test to group is the table below, and it is the only judgement
in the file: everything else is text.
"""

import ast
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent.parent
CACHE = Path(__file__).resolve().parent
TARGET = "tests/test_build_demo_page.py"
BASE = "7b03c17"  # the commit before the first group landed
FINISHED = "eea30b6"  # the tip of the pass, which the split reads as "after"
NL = chr(10)

METHOD = re.compile(r"^    def (test_\w+)", re.M)

# Written in two steps by two_step.py, because each asserts on two changes and
# neither half of one is a whole test.
CUTS = {
    "test_the_row_keeps_the_action_and_the_panel_holds_the_rest",
    "test_result_changes_and_mobile_cells_are_accessible",
    "test_the_count_line_names_the_mix_and_what_the_party_is_two_of",
}

# Which commit each changed test belongs to. A test that changed and is not
# listed here is reported and nothing is written, because a test assigned to
# nothing is a test that would land in a commit that does not cover it.
GROUPS = {
    "columns": [
        "test_a_missing_journey_is_typed_rather_than_a_dash",
        "test_the_page_states_where_a_split_ticket_would_split",
        "test_table_headers_name_their_columns_and_scope",
    ],
    "budget": [
        "test_the_budget_is_inline_in_the_large_heading",
        "test_no_numeric_column_can_wrap",
    ],
    "fixture": [
        "test_a_railcard_is_a_constraint_on_the_party_not_a_discount",
        "test_railcard_pricing_is_available_from_the_feed",
    ],
    "railcard": [
        "test_the_drawer_explains_which_card_it_is_about",
        "test_the_drawer_never_shows_more_than_the_row_it_was_opened_from",
        "test_each_destination_exposes_its_exact_railcard_decision",
        "test_the_railcard_note_never_names_a_price_above_the_row",
        "test_the_railcard_note_names_the_card_it_is_about",
        "test_a_row_states_its_condition_and_folds_the_feed_record_away",
        "test_each_destination_carries_its_fare_restriction_status",
    ],
    "distill": [
        "test_the_station_page_says_which_control_changes_station",
        "test_a_build_with_nowhere_to_change_to_names_the_station_as_text",
        "test_the_opening_sentence_branches_on_whether_a_timetable_was_loaded",
        "test_the_seller_handoff_and_commission_are_above_the_click",
    ],
    "shortlist": [
        "test_a_shortlist_is_a_list_of_places_and_not_a_booking",
    ],
    "runner": [
        "test_a_relative_demo_feed_path_is_still_synthetic",
        "test_a_second_run_serves_what_the_first_one_wrote",
        "test_the_default_builds_the_whole_network",
        "test_a_build_older_than_the_sources_is_not_served",
        "test_a_build_the_sources_have_moved_past_is_rebuilt",
    ],
}


def from_git(rev: str) -> str:
    out = subprocess.run(
        ["git", "show", f"{rev}:{TARGET}"], cwd=ROOT, capture_output=True,
        text=True, encoding="utf-8", check=True,
    ).stdout
    return out.replace(chr(92) + "r" + chr(92) + "n", NL)


def methods(text: str) -> dict[str, tuple[int, int]]:
    found: dict[str, tuple[int, int]] = {}
    starts = [(m.start(), m.group(1)) for m in METHOD.finditer(text)]
    for index, (start, name) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(text)
        found[name] = (start, end)
    return found


def changed_tests(before: str, after: str) -> dict[str, tuple[str, str]]:
    """Every test that differs, as (anchor, replacement).

    A test this change adds has no old text to anchor on, so a run of new
    tests is anchored on the definition line of the first test after the run
    that HEAD already has. That line is one this split never moves, which is
    what makes inserting tests safe at any point in the sequence.
    """
    old_methods, new_methods = methods(before), methods(after)
    order = list(new_methods)
    changed: dict[str, tuple[str, str]] = {}
    position = 0
    while position < len(order):
        name = order[position]
        start, end = new_methods[name]
        new_text = after[start:end].rstrip(NL)
        if name in old_methods:
            old_start, old_end = old_methods[name]
            old_text = before[old_start:old_end].rstrip(NL)
            if old_text != new_text:
                changed[name] = (old_text, new_text)
            position += 1
            continue
        # A run of tests this change adds, anchored on the first one after it
        # that HEAD already has.
        run = []
        while position < len(order) and order[position] not in old_methods:
            start, end = new_methods[order[position]]
            run.append(after[start:end].rstrip(NL))
            position += 1
        anchor = METHOD.match(after[slice(*new_methods[order[position]])]).group(0)
        key = run[0].split("(")[0].strip().removeprefix("def ")
        changed[key] = (anchor, (NL * 2).join(run) + NL + NL + anchor)

    # A test this change removes is replaced with nothing: its block runs to
    # the definition line of the next test, so removing it takes the blank
    # lines with it and leaves no gap.
    for name in list(old_methods):
        if name in new_methods:
            continue
        old_start, old_end = old_methods[name]
        changed[name] = (before[old_start:old_end].rstrip(NL) + NL + NL, "")
    return changed


def build_script(group: str, pairs: list[tuple[str, str]]) -> str:
    body = ""
    for old, new in pairs:
        # One repr per side, not one per line: adjacent string literals in
        # Python concatenate with no separator, so a line at a time would
        # silently produce an anchor with the lines run together.
        body += "        (" + NL
        body += "            " + repr(old) + "," + NL
        body += "            " + repr(new) + "," + NL
        body += "        )," + NL
    header = (
        '"""' + group + ": the tests that cover this change, cut out of the "
        "finished suite." + NL + NL
        + "Generated by split_by_test.py, so the anchors are the tests as the "
        "commit before" + NL
        + "this one has them and the replacements are the tests as this change "
        "leaves them." + NL
        + "A run of tests this change adds is anchored on the definition line of "
        "the first test" + NL
        + "after it that the commit before already has, which is a line this "
        "split never moves." + NL
        + '"""' + NL + NL
        + "import sys" + NL
        + "from pathlib import Path" + NL + NL
        + "sys.path.insert(0, str(Path(__file__).resolve().parent))" + NL
        + "from patch import patch  # noqa: E402" + NL + NL
        + "patch(" + NL
        + '    "' + TARGET + '",' + NL
        + "    [" + NL
    )
    return header + body + "    ]," + NL + ")" + NL


def main() -> int:
    before = subprocess.run(
        ["git", "show", f"{BASE}:{TARGET}"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout.replace("\r\n", NL)
    after = from_git(FINISHED)
    changed = changed_tests(before, after)

    assigned = {name for names in GROUPS.values() for name in names}
    for name in sorted(changed):
        if name not in assigned and name not in CUTS:
            print("UNASSIGNED changed test:", name)
    for name in sorted(assigned):
        if name not in changed:
            print("mapped but unchanged:", name)

    for group, names in GROUPS.items():
        pairs = [changed[name] for name in names if name in changed]
        if not pairs:
            continue
        script = CACHE / f"tg_{group}.py"
        script.write_text(build_script(group, pairs), encoding="utf-8", newline="")
        ast.parse(script.read_text(encoding="utf-8"))
        print(f"wrote {script.name} with {len(pairs)} test(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
