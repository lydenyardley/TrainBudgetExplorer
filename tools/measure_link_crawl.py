"""What the release build's link crawl costs, and what a cheaper one would.

The crawl in `build_release.crawl_internal_links` reads every page and every
shared asset of the release, extracts the internal links, and proves each names
a written file. It is the last full read of a build now that the prune does not
read the pages it wrote (E5 of the 17 October 2026 audit), so this measures what
that last read costs and whether the same check has a cheaper shape.

The corpus is release-shaped and measured directly, not extrapolated: one real
station page copied to 2,712 routes and padded to the 354 KB the 12 October 2026
audit measured, with a payload of thousands of station links so the scan and the
resolution meet the number of links a release page carries. Only the content is
synthetic; the page count, the page size and the link density are the release's.

    python -m tools.measure_link_crawl
    python -m tools.measure_link_crawl --runs 7 --pages 2712
"""

from __future__ import annotations

import argparse
import contextlib
import io
import re
import shutil
import tempfile
import time
from pathlib import Path

from trainbudget.build.build_assets import internal_hrefs
from trainbudget.build.build_release import crawl_internal_links

RELEASE_PAGES = 2_712
RELEASE_PAGE_BYTES = 354 * 1024

BYTES_HREF = re.compile(rb'href="([^"]+)"')
BYTES_SRC = re.compile(rb'src="([^"]+)"')
BYTES_EMBEDDED = re.compile(rb'"href"\s*:\s*"([^"]+)"')


def internal_hrefs_bytes(markup: bytes) -> list[str]:
    """The same links, read from bytes rather than decoded text."""
    return [
        href.decode("utf-8", "replace")
        for href in (
            BYTES_HREF.findall(markup)
            + BYTES_SRC.findall(markup)
            + BYTES_EMBEDDED.findall(markup)
        )
        if href.startswith(b"/") and not href.startswith(b"//")
    ]


def crawl_bytes(out_dir: Path) -> list[str]:
    """The crawl with the decode skipped, and the same route rules as the shipped one."""
    written = {
        path.relative_to(out_dir).as_posix() for path in out_dir.rglob("*") if path.is_file()
    }
    broken: list[str] = []
    for page in sorted(
        path for path in out_dir.rglob("*") if _crawlable(path)
    ):
        source = page.relative_to(out_dir).as_posix()
        for href in internal_hrefs_bytes(page.read_bytes()):
            if _target(href) not in written:
                broken.append(f"{source} links to {href}, which was not written")
    return broken


def crawl_two_walks(out_dir: Path) -> list[str]:
    """The shape the crawl had until 18 October 2026: the tree walked twice."""
    written = {
        path.relative_to(out_dir).as_posix() for path in out_dir.rglob("*") if path.is_file()
    }
    broken: list[str] = []
    for page in sorted(path for path in out_dir.rglob("*") if _crawlable(path)):
        source = page.relative_to(out_dir).as_posix()
        for href in internal_hrefs(page.read_text(encoding="utf-8")):
            if _target(href) not in written:
                broken.append(f"{source} links to {href}, which was not written")
    return broken


def crawl_one_walk(out_dir: Path) -> list[str]:
    """The shipped crawl with the tree walked once rather than twice."""
    files = sorted(path for path in out_dir.rglob("*") if path.is_file())
    written = {path.relative_to(out_dir).as_posix() for path in files}
    broken: list[str] = []
    for page in files:
        if page.suffix.lower() not in (".html", ".js", ".css"):
            continue
        source = page.relative_to(out_dir).as_posix()
        for href in internal_hrefs(page.read_text(encoding="utf-8")):
            if _target(href) not in written:
                broken.append(f"{source} links to {href}, which was not written")
    return broken


def _crawlable(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in (".html", ".js", ".css")


def _target(href: str) -> str:
    route = href.lstrip("/")
    if not route:
        return "index.html"
    return route + "index.html" if route.endswith("/") else route


def build_site(root: Path) -> Path:
    """A real three-station site, written by the build's own command."""
    from trainbudget.build.build_demo_page import main
    from trainbudget.feeds.make_synthetic_feed import build_synthetic_feed, build_synthetic_timetable

    feed = build_synthetic_feed(root / "fares", include_restrictions=True)
    timetable = build_synthetic_timetable(root / "timetable")
    out = root / "site" / "index.html"
    with contextlib.redirect_stdout(io.StringIO()):
        code = main(
            [
                "--feed",
                str(feed),
                "--timetable",
                str(timetable),
                "--all-origins",
                "--out",
                str(out),
            ]
        )
    if code != 0:
        raise SystemExit(f"error: the demo build exited {code}")
    return out.parent


def release_shaped(site: Path, pages: int, page_bytes: int, root: Path) -> Path:
    """One real page at a release's size and link density, copied to its route count.

    The padding is a payload of destination rows rather than inert text, because
    what a release page's last 300 KB are is that payload. It carries no
    ``href``, because a station page does not: the payload is column-encoded and
    the route's script builds the links from it, so the 32 KB page this is
    copied from holds five internal links in 32 KB. Padding with station links
    instead measured 12,234 links a page and 33 million to resolve, which is a
    page no build writes; the first run on 18 October 2026 did exactly that.
    """
    origin_page = sorted((site / "from").glob("*/index.html"))[0]
    markup = origin_page.read_text(encoding="utf-8")
    origin = origin_page.parent.name
    row = '["NOT","NOTTINGHAM",1234,1234,"",["city"],[],0,0,0,0,0,0,0,"off-peak",0,1,"1A","00000",""],'
    rows = max(0, (page_bytes - len(markup)) // len(row))
    markup = markup.replace(
        "</body>",
        '<script type="application/json" id="filler">['
        + (row * rows).rstrip(",")
        + "]</script></body>",
    )
    out = root / "release"
    out.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "stations.js"):
        shutil.copy2(site / name, out / name)
    for pattern in ("station-*", "chooser-*"):
        for asset in site.glob(pattern):
            shutil.copy2(asset, out / asset.name)
    (out / "privacy").mkdir(exist_ok=True)
    shutil.copy2(site / "privacy" / "index.html", out / "privacy" / "index.html")
    # The station the copied pages link to, so their links resolve.
    shutil.copytree(origin_page.parent, out / "from" / origin)
    for index in range(pages):
        target = out / "from" / f"copy-{index:04d}" / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(markup, encoding="utf-8")
    return out


def timed(run, *args) -> float:
    started = time.perf_counter()
    run(*args)
    return time.perf_counter() - started


def best_of(runs: int, run, *args) -> float:
    return min(timed(run, *args) for _ in range(runs))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--pages", type=int, default=RELEASE_PAGES)
    parser.add_argument("--page-bytes", type=int, default=RELEASE_PAGE_BYTES)
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        site = build_site(root)
        page = sorted((site / "from").glob("*/index.html"))[0]
        real = page.read_text(encoding="utf-8")
        if sorted(internal_hrefs(real)) != sorted(internal_hrefs_bytes(real.encode("utf-8"))):
            print("error: the bytes scan and the text scan disagree about a page's links")
            return 1

        print(f"writing {args.pages:,} pages of {args.page_bytes:,} bytes…", flush=True)
        corpus = release_shaped(site, args.pages, args.page_bytes, root)
        files = sorted(path for path in corpus.rglob("*") if path.is_file())
        total_bytes = sum(path.stat().st_size for path in files)
        sample = (corpus / "from" / "copy-0000" / "index.html").read_text(encoding="utf-8")
        print(
            f"corpus: {args.pages:,} pages at {len(sample.encode('utf-8')):,} bytes, "
            f"{len(files):,} files, {total_bytes / 1e9:.2f} GB"
        )
        print(
            f"links: {len(internal_hrefs(real)):,} on the real page, "
            f"{len(internal_hrefs(sample)):,} on a release-shaped one"
        )

        variants = (
            ("two walks (until 18 October)", crawl_two_walks),
            ("shipped: one walk", crawl_internal_links),
            ("bytes: two walks, no decode", crawl_bytes),
        )
        # Correctness first: a cheaper crawl that reported different broken
        # links would be a different check, not a faster one.
        expected = sorted(crawl_internal_links(corpus))
        for label, run in (variants[0], variants[2]):
            if sorted(run(corpus)) != expected:
                print(f"error: {label} disagrees about the broken links")
                return 1
        if sorted(crawl_one_walk(corpus)) != expected:
            print("error: the one-walk prototype and the shipped crawl disagree")
            return 1
        print(f"every variant reports the same {len(expected)} broken link(s)")

        results: dict[str, list[float]] = {label: [] for label, _ in variants}
        for _ in range(args.runs):
            # Interleaved, so warmup and drift do not favour one side.
            for label, run in variants:
                results[label].append(timed(run, corpus))

        for label, _ in variants:
            seconds = results[label]
            print(
                f"{label}: best {min(seconds):.2f} s of {len(seconds)} "
                f"({min(seconds) / len(files) * 1000:.2f} ms a file, "
                f"{total_bytes / 1e6 / min(seconds):.0f} MB/s, "
                f"range {min(seconds):.2f}-{max(seconds):.2f})"
            )

        # What the number is made of, each measured on the same corpus.
        walk_twice = best_of(
            args.runs,
            lambda: [path for path in corpus.rglob("*") if path.is_file()]
            + [path for path in corpus.rglob("*") if _crawlable(path)],
        )
        walk_once = best_of(
            args.runs, lambda: [path for path in corpus.rglob("*") if path.is_file()]
        )
        pages = [path for path in files if _crawlable(path)]
        read = best_of(args.runs, lambda: [path.read_text(encoding="utf-8") for path in pages])
        texts = [path.read_text(encoding="utf-8") for path in pages]
        scanned: list[list[str]] = []

        def scan_all() -> None:
            scanned.clear()
            scanned.extend(internal_hrefs(text) for text in texts)

        scan = best_of(args.runs, scan_all)
        links = [href for group in scanned for href in group]
        written = {path.relative_to(corpus).as_posix() for path in files}
        resolve = best_of(
            args.runs, lambda: [href for href in links if _target(href) not in written]
        )
        print(f"of which: walking the tree twice {walk_twice:.2f} s, once {walk_once:.2f} s")
        print(f"reading and decoding {len(pages):,} files: {read:.2f} s")
        print(f"scanning {len(links):,} links out of them: {scan:.2f} s")
        print(f"resolving those links against {len(written):,} written files: {resolve:.2f} s")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
