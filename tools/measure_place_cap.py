"""What a cap on the places a station page lists would save, measured.

The 23 October 2026 byte audit left one lever that is a product decision rather
than an encoding one: a page lists three fare lists to the same places, and no
re-encoding takes that away without taking a ticket-mode filter with it. The
version that keeps every filter is a cap on the places themselves, every list cut
to the same places, and this tool costs it on built pages.

**The plan.** Build the twelve release-shaped pages the audit measured, then
re-encode each page's payload with the fare lists cut to the cheapest N places,
rebuild the page around it, and compare bytes. The service week is cut the way the
build already cuts it after a row filter -- an answer for a place the page no
longer lists is a station code and eight durations nobody reads -- so the saving
is the one the build would actually make rather than a payload-only figure.

**Why re-encoding is the measurement.** At no cap the rebuilt page is the built
page, byte for byte, on every page: same encoder, same dictionaries, same pool.
The tool checks that and refuses to report if it breaks, because a simulation
that does not reproduce the page it replaces is measuring a different page.

    python -m tools.measure_place_cap --site _scratch --census grantham
    python -m tools.measure_place_cap --site _scratch --caps 600,700 --loss-at 600

**What it cannot know.** It cannot see a page that was never built, and the
twelve pages are a spread of small, medium and large stations rather than a
random draw, so the release figure is a bracket until a whole-network run prints
its own mean (`docs/build-performance-findings.md` says this every time).
"""

from __future__ import annotations

import argparse
import copy
import gzip
import json
import sys
from pathlib import Path

from build_payload import FARE_LISTS, decode_payload, encode_payload
from page_templates import PAYLOAD_MARKER

# The slices the release's own pages are made of, from the twelve-page build in
# the 23 October 2026 audit: the mean page times the page count the release
# writes. Nothing here can measure a release; this is the arithmetic the audit
# uses to read a page figure as a site figure.
RELEASE_PAGES = 2930
# The project's own budget, from tools/page_bytes.py. MiB, as that gate counts.
SITE_BUDGET_MB = 800


def dumps(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def split_payload(html: str) -> tuple[str, dict, str]:
    """The page before its payload, the payload, and the page after it."""
    head, rest = html.split(PAYLOAD_MARKER, 1)
    payload, end = json.JSONDecoder().raw_decode(rest)
    return head, payload, rest[end:]


def rebuild(head: str, encoded: dict, tail: str) -> str:
    body = json.dumps(encoded, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return head + PAYLOAD_MARKER + body + tail


def page_files(site: Path) -> list[Path]:
    return sorted(site.glob("from/*/index.html"))


def per_key(encoded: dict) -> dict[str, int]:
    """Each top-level value's own bytes, exact to the key it is written under."""
    return {key: dumps({key: value}) - len(key) - 5 for key, value in encoded.items()}


def column_census(encoded: dict) -> dict[str, dict[str, int]]:
    """Bytes a fare list's cells cost, by column.

    A dictionary's values are charged to the column they stand for, and row
    framing is charged to the list: what is left out is the column list itself,
    which is a few hundred bytes once per page.
    """
    out: dict[str, dict[str, int]] = {}
    for key in FARE_LISTS:
        table = encoded[key]
        columns, rows = table["columns"], table["rows"]
        placed = set(table.get("placed") or [])
        derived = set(table.get("derived") or [])
        census = {column: 0 for column in columns}
        for cells in rows:
            at = 0
            for column in columns:
                if column in placed or column in derived:
                    continue
                census[column] += dumps(cells[at])
                at += 1
        for column, values in (table.get("dicts") or {}).items():
            census[column] += dumps(values)
        census["(framing)"] = len(rows) * 3
        out[key] = census
    return out


def cheapest_by_place(decoded: dict) -> dict[str, int]:
    """Each place's cheapest standard adult fare, across every fare list."""
    cheapest: dict[str, int] = {}
    for key in FARE_LISTS:
        for row in decoded[key]:
            price = row["adultPence"]
            if row["crs"] not in cheapest or price < cheapest[row["crs"]]:
                cheapest[row["crs"]] = price
    return cheapest


def capped(decoded: dict, cap: int | None) -> dict:
    """The payload with every fare list cut to the cheapest ``cap`` places."""
    if cap is None:
        return decoded
    cheapest = cheapest_by_place(decoded)
    keep = set(sorted(cheapest, key=lambda crs: (cheapest[crs], crs))[:cap])
    out = dict(decoded)
    for key in FARE_LISTS:
        out[key] = [row for row in decoded[key] if row["crs"] in keep]
    if isinstance(out.get("serviceWeek"), list):
        out["serviceWeek"] = [
            [
                {crs: answer for crs, answer in day.items() if crs in keep}
                if isinstance(day, dict) else day
                for day in week
            ]
            if isinstance(week, list) else week
            for week in out["serviceWeek"]
        ]
    return out


def loss(decoded: dict, cap: int) -> dict:
    """What one page stops listing at one cap, and the price it stops at."""
    cheapest = cheapest_by_place(decoded)
    ranked = sorted(cheapest, key=lambda crs: (cheapest[crs], crs))
    kept = set(ranked[:cap])
    return {
        "places": len(ranked),
        "kept": len(kept),
        "stop": cheapest[ranked[len(kept) - 1]] if kept else 0,
        "dearest": max(
            (row["adultPence"] for key in FARE_LISTS for row in decoded[key]), default=0
        ),
        "rows": sum(len(decoded[key]) for key in FARE_LISTS),
        "keptRows": sum(
            1 for key in FARE_LISTS for row in decoded[key] if row["crs"] in kept
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--site", type=Path, default=Path("_site"),
                        help="a built site holding from/<slug>/index.html")
    parser.add_argument("--caps", default="400,500,600,700",
                        help="comma-separated place caps to cost, plus all")
    parser.add_argument("--loss-at", type=int, default=600,
                        help="the cap whose reader-facing cost is listed")
    parser.add_argument("--census", metavar="SLUG",
                        help="print one page's parts and its fare-list columns")
    parser.add_argument("--pages", type=int, default=RELEASE_PAGES,
                        help="pages the release writes, for the site figure")
    args = parser.parse_args(argv)

    pages = page_files(args.site)
    if not pages:
        print(f"no page under {args.site}/from/, so nothing was measured")
        return 2
    caps: list[int | None] = [None, *sorted(int(part) for part in args.caps.split(",") if part)]
    totals = {cap: 0 for cap in caps}
    gz_totals = {cap: 0 for cap in caps}
    losses: list[tuple[str, dict]] = []
    reproduced = 0

    print(f"{'station':22} {'page':>9} " + " ".join(
        f"{(str(cap) if cap else 'all'):>8}" for cap in caps))
    for page in pages:
        html = page.read_text(encoding="utf-8")
        head, encoded, tail = split_payload(html)
        decoded = decode_payload(copy.deepcopy(encoded))
        sizes = {}
        for cap in caps:
            built = rebuild(head, encode_payload(capped(copy.deepcopy(decoded), cap)), tail)
            sizes[cap] = len(built.encode("utf-8"))
            totals[cap] += sizes[cap]
            gz_totals[cap] += len(gzip.compress(built.encode("utf-8"), 9))
        if sizes[None] == len(html.encode("utf-8")):
            reproduced += 1
        print(f"{page.parent.name:22} {len(html.encode('utf-8')):>9,} " + " ".join(
            f"{sizes[cap]:>8,}" for cap in caps))
        losses.append((page.parent.name, loss(decoded, args.loss_at)))

    print()
    print(f"no cap reproduces each page byte for byte: {reproduced}/{len(pages)}")
    if args.census:
        chosen = next((page for page in pages if page.parent.name == args.census), None)
        if chosen is None:
            print(f"  ({args.census} is not one of the measured pages)")
        else:
            chosen_encoded = split_payload(chosen.read_text(encoding="utf-8"))[1]
            print(f"{args.census} parts:")
            for key, size in sorted(
                per_key(chosen_encoded).items(), key=lambda item: -item[1]
            )[:8]:
                print(f"  {key:26} {size:>9,}")
            print(f"{args.census} fare rows by column:")
            for key, census in column_census(chosen_encoded).items():
                print(f"  {key}: {sum(census.values()):,} B over "
                      f"{len(chosen_encoded[key]['rows'])} rows")
                for column, size in sorted(census.items(), key=lambda item: -item[1])[:6]:
                    print(f"    {column:24} {size:>8,}")

    print()
    print(f"what a cap of {args.loss_at} leaves out:")
    for name, facts in losses:
        print(f"  {name:22} {facts['kept']:>5}/{facts['places']:<5} places  "
              f"stop £{facts['stop'] / 100:.2f}  dearest £{facts['dearest'] / 100:.2f}  "
              f"rows {facts['keptRows']}/{facts['rows']}")

    print()
    print(f"{'cap':>6} {'mean page':>10} {'mean gzip':>10} "
          f"{'release MiB':>12} {'of 800 MiB':>11}")
    budget = SITE_BUDGET_MB * 1024 * 1024
    for cap in caps:
        mean = totals[cap] / len(pages)
        release = mean * args.pages
        print(f"{(str(cap) if cap else 'all'):>6} {mean:>10,.0f} "
              f"{gz_totals[cap] / len(pages):>10,.0f} "
              f"{release / 1024 / 1024:>12,.0f} {release / budget:>10.0%}")
    print(f"\n(the release figure is {args.pages} pages at this mean, and this "
          f"sample is a bracket, not a projection)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
