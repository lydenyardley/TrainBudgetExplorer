"""CRLF-safe exact-match patcher for the project's CRLF source files.

Every anchor is written here as it reads in the terminal (no CR), and the
helper matches it against the file with line endings normalised, then writes
the file back with the endings it already had. Each replacement must match
exactly once: a patch that lands twice is a patch that guessed.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def patch(relative: str, replacements: list[tuple[str, str]]) -> None:
    path = ROOT / relative
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    for index, (old, new) in enumerate(replacements, start=1):
        old = _unescape(old)
        new = _unescape(new)
        count = text.count(old)
        if count != 1:
            raise SystemExit(
                f"{relative} replacement {index} matched {count} times, expected 1:\n"
                f"--- anchor ---\n{old[:400]}"
            )
        text = text.replace(old, new)
    out = text.replace("\n", "\r\n") if crlf else text
    path.write_bytes(out.encode("utf-8"))
    print(f"patched {relative} ({len(replacements)} replacement(s), "
          f"{'CRLF' if crlf else 'LF'} preserved)")


def _unescape(value: str) -> str:
    """Drop a backslash that a Python or JavaScript escape left in front of a
    real character.

    The anchors here are written the way they read in a terminal, and a
    non-ASCII character can reach one of them through two layers of string
    escaping -- the patch script's own source and the template's. A stray
    backslash in front of the character is never what the file holds, and
    hunting for it by hand across a dozen anchors is how a patch ends up
    half-applied.
    """
    out = []
    for index, char in enumerate(value):
        if char == "\\" and index + 1 < len(value) and ord(value[index + 1]) > 127:
            continue
        out.append(char)
    return "".join(out)


if __name__ == "__main__":
    sys.exit("import this, do not run it")
