"""Write the module rows of AGENTS.md from each module's own docstring.

The map's Python rows and the files they name drifted apart by hand. This
reads the first docstring line of every module under the six areas and writes
those rows between the markers in AGENTS.md, so a new module is one run away
from being on the map and a renamed one cannot leave a stale row behind.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "AGENTS.md"
START = "<!-- module-map:start -->"
END = "<!-- module-map:end -->"

#: The areas whose rows are generated. The page, tests, decisions and release
#: rows name files that are not Python modules and stay in the map by hand.
AREAS = (
    ("Fares", ("trainbudget/fares/*.py",)),
    ("Timetable", ("trainbudget/timetable/*.py",)),
    ("The build", ("trainbudget/build/*.py",)),
    ("Feeds", ("trainbudget/feeds/*.py",)),
    ("Measurements", ("trainbudget/measure/*.py", "tools/measure_*.cjs")),
    ("Operator tools", ("tools/*.py",)),
)


def _description(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".cjs":
        for line in text.splitlines():
            if line.startswith(" * "):
                return line[3:].strip().replace("|", "/")
        return ""
    doc = ast.get_docstring(ast.parse(text)) or ""
    first = doc.strip().splitlines()[0] if doc.strip() else ""
    return " ".join(first.split()).replace("|", "/")


def render_rows() -> str:
    rows = []
    for area, patterns in AREAS:
        entries = []
        paths = sorted({path for pattern in patterns for path in ROOT.glob(pattern)})
        for path in paths:
            if path.name == "__init__.py" or path.name.startswith("test_"):
                continue
            relative = path.relative_to(ROOT).as_posix()
            entries.append(f"`{relative}` ({_description(path)})")
        rows.append(f"| {area} | {', '.join(entries)} |")
    return "\n".join(rows)


def replace_block(text: str) -> str:
    start = text.index(START) + len(START)
    end = text.index(END)
    return text[:start] + "\n" + render_rows() + "\n" + text[end:]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    text = MAP.read_text(encoding="utf-8")
    updated = replace_block(text)
    if "--check" in argv:
        if updated != text:
            print(
                "AGENTS.md's module map is stale; run python -m tools.agents_map",
                file=sys.stderr,
            )
            return 1
        return 0
    if updated != text:
        MAP.write_text(updated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
