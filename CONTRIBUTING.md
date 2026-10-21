# Contributing

## Commit convention

This repository uses [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).

```
<type>(<scope>): <description>

<body>

<footers>
```

### Type

One of these, and nothing else:

| Type | Use for |
|---|---|
| `feat` | A new capability, such as a parser or a query |
| `fix` | A defect fix |
| `docs` | Documentation only |
| `test` | Tests only |
| `refactor` | A change that alters no behaviour |
| `perf` | A change that alters only speed or memory |
| `build` | Dependencies, packaging, tooling that builds |
| `ci` | Continuous integration configuration |
| `chore` | Anything else that touches no product behaviour |

### Scope

Optional, lowercase, and the area the change touches: `fares`, `timetable`,
`page`, `tools`, `ci`, or whatever names it best. Use it when a commit touches
one area and leave it out when the change spans several. The checker accepts
letters, digits and hyphens and keeps no list, which is the honest rule: the five
names this paragraph used to give held for neither the checker nor the history,
which uses 29 scopes in its last 150 commits.

### Description

- Imperative mood, as in "add the audit command", not "added" or "adds".
- Lowercase first letter.
- No trailing period.
- 80 characters or fewer including the type and scope.

### Body

Leave one blank line after the subject. Say why the change is needed and what it
costs, not what each line does. Skip the body when the subject already says
everything.

Wrap body prose at about 80 characters, but that is a habit and not a rule the
checker enforces. The closing recap paragraph is a single long line in most of
this repository's commits, and it is meant to be read as one. A limit the
history breaks on nearly every commit is a limit nobody keeps, and an unenforced
limit in this document is worse than none: this checker used to reject all 87
commits in the repository for exceeding a 72-character body line. The subject is
capped because it is a display surface -- it is what `git log --oneline` and a
pull request list show. The body is not.

### Footers

One footer per line at the end, after a blank line:

- `Refs: adr/ADR-0006-timetable-layer.md` when a decision drives the change.
- `Co-Authored-By: Name <email>` for pair and tool authorship.
- `BREAKING CHANGE: <what breaks>` when consumers must act.

### One logical change per commit

A commit that needs the word "and" in its subject is usually two commits. Land a
change with its tests. Every commit in this repository states a test count or a
command whose output a reviewer can reproduce.

## Check a message

```
git log -1 --format=%B | python -m tools.check_commit_message
python -m unittest discover -s tools -p "test_commit_message*.py"
```

The checker accepts the Conventional Commits grammar plus `Merge `, `Revert `,
`fixup! `, and `squash! ` prefixes, which Git generates. The deploy workflow
runs it over every commit the push adds, so the convention is checked rather
than described. The 41 commits that predate the grammar still fail it; they are
left as they are, because rewriting published history to satisfy a linter is a
worse trade than a linter the older history is honestly outside of.

## Run the tests

```
python -m tools.verify --fast      # the page, payload and chooser modules, under a five-minute ceiling
python -m tools.verify --full      # every unit test, the type check, which is what the deploy workflow runs
python -m tools.verify --browser   # the demo and shape builds, then the Playwright suite
```

The two discoveries that make up the full run, which CI also runs:

```
python -m unittest discover -s tests -p "test_*.py"
python -m unittest discover -s tools -p "test_*.py"
```

`--full` also runs the type check, so it wants `mypy`
(`python -m pip install mypy`); `--fast` does not, and reports the step as
`not run` rather than failing when it is missing.

## The annotations and the suppressions are checked

`python -m tools.check_types` runs mypy over the files whose own type errors are
already zero and fails on a new one, and `--all` prints the census (350 errors in
29 of the 70 files, measured 15 October 2026) without failing on any of them.
ADR-0072 says why it is a ratchet over the clean files rather than `--strict`
over the tree. `tests/test_suppressions.py` holds the other half: every `# noqa`
names its cause, on its own line or in the comment block above it, so a
suppression nobody can explain fails the suite instead of living in a table.
