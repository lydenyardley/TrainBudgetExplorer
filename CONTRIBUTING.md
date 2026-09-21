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

Optional, lowercase, and one of the module names: `fares`, `timetable`, `sweep`,
`feeds`, `docs`. Use it when a commit touches one module. Leave it out when the
change spans several.

### Description

- Imperative mood, as in "add the audit command", not "added" or "adds".
- Lowercase first letter.
- No trailing period.
- 72 characters or fewer including the type and scope.

### Body

Leave one blank line after the subject. Say why the change is needed and what it
costs, not what each line does. Wrap body lines at 72 characters. Skip the body
when the subject already says everything.

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
git log -1 --format=%B | python check_commit_message.py
python -m unittest test_commit_message
```

The checker accepts the Conventional Commits grammar plus `Merge `, `Revert `,
`fixup! `, and `squash! ` prefixes, which Git generates.

## Run the tests

```
python -m unittest discover -p "test_*.py"
```
