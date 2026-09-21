"""Damage a copy of a feed on purpose, so the parsers meet bad input here first.

The real feed arrives once, and whatever is wrong with it is discovered then
unless it is discovered now. Each damage below is one thing a real download
does: a Windows line ending, an accented station name, a record cut short, an
archive inside an archive.

Two rules decide what a damaged feed is allowed to do, and the tests hold both:

- cosmetic damage changes no answer at all
- structural damage is reported, never guessed at, and never raises

Usage:
    python damage_feed.py --list
    python damage_feed.py _demo_feed _damaged crlf
    python damage_feed.py _demo_feed _damaged truncated_record --target ffl
"""

from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from io import BytesIO
from pathlib import Path

# Damage that must leave every answer identical.
COSMETIC_DAMAGES = (
    "crlf",
    "trailing_spaces",
    "blank_lines",
    "no_final_newline",
    "accented_name",
    "byte_order_mark",
    "lowercase_record_types",
    "repeated_records",
    "lowercase_extension",
    "zip_in_folder",
)

# Damage that must be reported, and must not raise.
STRUCTURAL_DAMAGES = (
    "truncated_record",
    "stubbed_record",
    "empty_file",
    "unknown_file",
    "nested_archive",
)

DAMAGES = COSMETIC_DAMAGES + STRUCTURAL_DAMAGES

DEFAULT_TARGET = "ffl"
REPLACEMENT_STATION_NAME = "NOTT CAF\xc9 "


class UnknownDamage(ValueError):
    """Raised for a damage name that does not exist."""


def damage(
    source: str | Path,
    destination: str | Path,
    kind: str,
    *,
    target: str = DEFAULT_TARGET,
) -> Path:
    """Write a damaged copy of a feed and return the path to load.

    Usually that path is a folder. For nested_archive it is the archive itself,
    because that shape is the point of the damage.
    """
    if kind not in DAMAGES:
        raise UnknownDamage(f"{kind!r} is not one of: {', '.join(DAMAGES)}")
    source = Path(source)
    destination = Path(destination)
    if destination.exists():
        shutil.rmtree(destination) if destination.is_dir() else destination.unlink()
    files = {child.name: child.read_bytes() for child in sorted(source.iterdir()) if child.is_file()}
    target_name = _target_name(files, target)

    if kind == "zip_in_folder":
        destination.mkdir(parents=True)
        _write_archive(destination / f"{source.name}.zip", files)
        return destination

    if kind == "nested_archive":
        destination.parent.mkdir(parents=True, exist_ok=True)
        inner = BytesIO()
        with zipfile.ZipFile(inner, "w") as archive:
            archive.writestr("notes.txt", "a second archive, which is not a feed")
        files["extra.zip"] = inner.getvalue()
        _write_archive(destination.with_suffix(".zip"), files)
        return destination.with_suffix(".zip")

    if kind == "unknown_file":
        files["readme.txt"] = b"Thank you for your download.\n"
        files["rjfaf.licence"] = b"licence terms, not a feed record\n"
        files["feed.bin"] = bytes(range(256))

    damaged = _damage_bytes(files[target_name], kind, target)
    if damaged is not None:
        files[target_name] = damaged

    if kind == "lowercase_extension":
        stem = Path(target_name).stem
        renamed = f"{stem}.{Path(target_name).suffix.lstrip('.').upper()}"
        files[renamed] = files.pop(target_name)

    destination.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (destination / name).write_bytes(content)
    return destination


def _target_name(files: dict[str, bytes], target: str) -> str:
    for name in files:
        if name.lower().endswith(f".{target.lower()}"):
            return name
    raise UnknownDamage(f"no .{target} file in this feed: {', '.join(sorted(files))}")


def _write_archive(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in sorted(files.items()):
            archive.writestr(name, content)


def _damage_bytes(content: bytes, kind: str, target: str) -> bytes | None:
    if kind == "empty_file":
        return b""
    if kind == "crlf":
        return content.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    if kind == "trailing_spaces":
        return b"\n".join(line + b"   " for line in content.split(b"\n"))
    if kind == "blank_lines":
        lines = content.split(b"\n")
        out: list[bytes] = []
        for index, line in enumerate(lines):
            out.append(line)
            if index % 3 == 2:
                out.append(b"")
        return b"\n".join(out)
    if kind == "no_final_newline":
        return content.rstrip(b"\n")
    if kind == "byte_order_mark":
        return b"\xef\xbb\xbf" + content
    if kind == "accented_name":
        if target != "loc":
            raise UnknownDamage("accented_name needs --target loc")
        # Same character count, one byte that is not valid UTF-8, so the reader
        # has to fall back rather than mangle the record's fixed width.
        return content.replace(b"NOTTINGHAM", REPLACEMENT_STATION_NAME.encode("latin-1"))
    if kind == "lowercase_record_types":
        if target != "ffl":
            raise UnknownDamage("lowercase_record_types needs --target ffl")
        lines = []
        for line in content.split(b"\n"):
            lines.append(line[:1] + line[1:2].lower() + line[2:] if len(line) > 1 else line)
        return b"\n".join(lines)
    if kind == "repeated_records":
        lines = [line for line in content.split(b"\n") if line]
        return b"\n".join(line for pair in zip(lines, lines) for line in pair) + b"\n"
    if kind in {"truncated_record", "stubbed_record"}:
        lines = [line for line in content.split(b"\n") if line]
        if len(lines) < 3:
            raise UnknownDamage("this file has too few records to cut one")
        # The middle record, not the last one: a file's last line is often a
        # trailer, and cutting that proves nothing about a data record.
        middle = len(lines) // 2
        if kind == "truncated_record":
            # Half the line. On both feeds the fields that carry the answer sit
            # early in a record, so this removes only what nobody reads.
            lines[middle] = lines[middle][: max(1, len(lines[middle]) // 2)]
        else:
            # A record that still looks like a record and holds nothing. This is
            # the cut that turns a missing field into an invented one.
            lines[middle] = lines[middle][:4]
        return b"\n".join(lines) + b"\n"
    return None


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Write a deliberately damaged copy of a feed.")
    parser.add_argument("source", nargs="?", help="feed folder to copy")
    parser.add_argument("destination", nargs="?", help="where to write the damaged copy")
    parser.add_argument("kind", nargs="?", help="which damage to apply")
    parser.add_argument("--target", default=DEFAULT_TARGET, help="extension to damage, e.g. ffl or mca")
    parser.add_argument("--list", action="store_true", help="print the damage names and stop")
    arguments = parser.parse_args(argv)

    if arguments.list:
        print("cosmetic, changing no answer:")
        for name in COSMETIC_DAMAGES:
            print(f"  {name}")
        print("structural, which must be reported:")
        for name in STRUCTURAL_DAMAGES:
            print(f"  {name}")
        return 0

    if not (arguments.source and arguments.destination and arguments.kind):
        parser.error("source, destination, and kind are required unless --list is given")
    try:
        where = damage(arguments.source, arguments.destination, arguments.kind, target=arguments.target)
    except UnknownDamage as error:
        print(f"{error}", file=sys.stderr)
        return 2
    print(f"{arguments.kind} damage written to {where}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
