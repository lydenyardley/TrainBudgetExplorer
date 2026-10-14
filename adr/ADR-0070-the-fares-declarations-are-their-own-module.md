# ADR-0070: The fares declarations are their own module

**Status:** Accepted
**Date:** 14 October 2026
**Relates to:** ADR-0005 (the feeds are licensed, so the fixture is the test), the
comment audit of 14 October 2026 (its suppression census), the build-inputs rule
in `tools/build_inputs.py`

## Context

`atoc_fares.py` held two things at once: every declaration the fares feed is read
with, and `FaresDb`, the object the queries are asked of. The loader,
`atoc_fares_loader.py`, is mixed into `FaresDb` and reads 40 of those
declarations -- the fixed-width record layouts, the row types, the reviewed
classification tables and five decode helpers. Because they lived in the same
module as the class that consumes the loader, each module had to import the other
**below its own definitions**: `atoc_fares.py` imported `FaresLoader` at line
2,636, after the declarations the loader needs, and
`atoc_fares_loader.py` imported the 40 names at its line 1,247, after the class
that reads it. Both imports carried `# noqa: E402`, and the 14 October 2026
comment audit named them as the only two suppressions in the tree whose cause was
still present.

The audit did not fix them. Its reasoning was that the move needed a re-export
surface, a new module on the `AGENTS.md` map and a decision about whether that
surface stays whole, because `atoc_fares.py` is 3,856 lines with `FaresDb`
starting at 2,638, and 45 import statements in 41 other files take 56 names from
it (measured 14 October 2026). That is a decision before it is a code change.

## Decision

The declarations get their own module, `atoc_fare_declarations.py`, holding the
fixed-width record layouts, the row types those records become, the reviewed
classification tables, the URL constants and the small helpers that decode a
field. It imports nothing from either fares module.

- `atoc_fares.py` imports it at the top and **re-exports every name any other
  module already took from it**. `FaresDb` stays where it is, now importing
  `FaresLoader` at the top rather than below its code.
- `atoc_fares_loader.py` imports the declarations at the top. It still reaches
  `FaresDb` lazily, through `TYPE_CHECKING` and two function-local imports, because
  `FaresDb` subclasses the loader and the opposite direction would be the cycle
  again.
- Both `# noqa: E402` comments and both late imports are deleted, not suppressed
  elsewhere.

The re-export surface **stays whole**. Its point is that the split moves wherethe declarations live and not what a caller imports them from: 56 names have call
sites in 45 import statements across 41 files, and rewriting every one of them
would be a diff about import paths rather than about the cycle. `atoc_fares` remains, on the map and in the
`README`, the module a reader goes to for the fares layer, and a name it re-exports
is one it still answers for. A later change that moves a *caller* rather than a
declaration is free to import `atoc_fare_declarations` directly.

## Evidence

- `python -c "import atoc_fares, atoc_fares_loader, atoc_fare_declarations"` and
  `FaresDb.__mro__[1] is atoc_fares_loader.FaresLoader` both hold; the old file's
  `# noqa: E402` count in these two modules is now **0**.
- A scan of every `.py` file in the tree for `from atoc_fares import ...` and for
  `atoc_fares.<name>` attribute use finds **56 distinct names, none missing** on
  the new module.
- `python tools/verify.py --fast` and the fares modules' own suites pass with the
  declarations in the new file; `tools/build_inputs.py` fingerprints `*.py`, so
  the new module re-triggers a rebuild without being named in the workflow.

## Consequences

- The cycle is gone by structure rather than by import order: neither fares
  module needs to be imported before the other, so a future name added to the
  shared declarations is reachable from the top of both.
- `atoc_fare_declarations.py` is a build input and must stay on the `AGENTS.md`
  map; `tests/test_agents_map.py` fails if it does not.
- It is on `build_demo_page.SOURCE_FILES`, which is read from the build's own
  imports and imported by the runner rather than repeated (ADR-0055's amendment
  of 14 October 2026), so editing a reviewed table still marks a built site out
  of date; `tools/build_inputs.py` reaches it as a `*.py` input for CI, and
  `tools/test_build_inputs.py` proves that by following the build's imports.
- The re-export block is 85 names long. It is a flat, alphabetical list, and a
  name that moves out from under it fails at import rather than at a call site.
