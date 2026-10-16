/**
 * A real browser test for the generated page.
 *
 * The page is the whole product and nothing tested it in a browser: the Python
 * suite proves the payload, the template strings, and the fare maths, but not that
 * a reader can drag the slider, filter to a town, follow a ticket link, or copy a
 * row's journey details. Those are the things a reader actually does.
 *
 * Run it with playwright on one or more page paths:
 *
 *     npx --yes --package playwright node browser_test.cjs
 *     node browser_test.cjs            # when playwright is installed locally
 *     node browser_test.cjs demo.html _site/index.html
 *     node browser_test.cjs _site/from          # sweep a published site
 *     node browser_test.cjs _site/from --max 20 # and drive twenty of its pages
 *
 * Every expectation is read out of the page under test, so the suite is a
 * test of the template rather than of a station, and one run can sweep the
 * pages a build wrote: each path gets its own context and its own result,
 * and the run fails if any page fails.
 *
 * A path that is a directory is swept: every index.html beneath it becomes a
 * page of the run, in name order, which is how a whole published station set
 * is driven in one command. A page that names a file beyond itself -- the
 * shared station-picker asset -- has that file served from beside it, so the
 * picker is exercised the way a reader's browser would load it. --max bounds
 * the sweep, which is the directory, and says on stderr how many pages it left
 * out, because a run that quietly tested twenty of two thousand has not tested
 * the site. A page named on the command line is not part of the sweep and is
 * always driven: the shapes a sweep cannot otherwise reach -- a one-origin
 * release, a prices-only page -- are exactly the pages a command names, and
 * 16 October 2026 was when the spread was found to be sampling them away.
 *
 * A path that is not a station page is the chooser at the site root, a
 * one-station release's root, or the privacy page. The chooser is driven like
 * any other page -- it is where a
 * reader chooses the station everything else is about -- while the privacy
 * page carries no controls and is reported as 0/0, named at the end of the
 * run, and does not fail it. A run in which no page could be checked at all
 * has tested nothing and does fail, so pointing this at the wrong tree cannot
 * read as a pass. A run in which too much of the suite had nothing to
 * exercise fails too: skips are reported, and a stated fraction of them is the
 * most a run may skip, so a fixture that has quietly stopped exercising the
 * page cannot look green. There are two of those fractions, because a page
 * that carries no timetable cannot run the checks about times, days, journeys
 * and splits while a page that carries one can: each shape is measured against
 * the pages of that shape, so a prices-only sweep is not excused by a
 * timetable page beside it, and a run with no timetable page in it fails as
 * having tested the times half not at all.
 *
 * Exit codes: 0 every page checked behaves, 1 one does not, nothing was
 * checked, or the run skipped more than its budget, 2 playwright is
 * unavailable. A skip is reported loudly and exits 2, because a test that
 * passes quietly on a machine where it never ran is the thing this project
 * keeps refusing to do.
 */

// The suite is split by route and by section under tests/browser/, and this
// file is the entry point the tools and CI invoke. It holds none of the checks
// itself: the shared harness, the chooser, the release root, the accessibility
// matrix and the station page's sections are modules beside it, and this file
// drives them the way the single file did -- one context per page, one page
// after another, and one report at the end.
//
// The command line is unchanged: a list of page paths, --sweep, and --max.
const fs = require("node:fs");
const path = require("node:path");

const { PAGES, expand, requirePlaywright, sharedAssets, serve, report } = require("./browser/harness.cjs");
const { runPage } = require("./browser/station.cjs");

async function main() {
  const playwright = requirePlaywright();
  if (!playwright) process.exit(2);

  const wanted = expand(PAGES.length ? PAGES : ["demo.html"]);
  const pages = wanted.map((given) => {
    const file = path.resolve(given);
    // A path that is not there is a failed page, not a failed run: the others
    // still get driven and still get reported. Missing demo.html is the case
    // worth spelling out, because it is the one a contributor hits first.
    let body = null;
    try {
      body = fs.readFileSync(file);
    } catch (error) {
      if (given === "demo.html") {
        console.error("No page at " + file + ". Build one first:");
        console.error("  python make_synthetic_feed.py _demo_feed --unserved-station --third-origin");
        console.error("  python build_demo_page.py --feed _demo_feed --timetable _demo_feed --all-origins --out _demo_site/index.html");
      }
    }
    return { given, file, body };
  });

  const assets = sharedAssets(pages);
  if (assets.missing.length) {
    console.error(
      "the page(s) under test ask for " + assets.missing.join(", ") +
        ", which is not beside them, so the checks that need it would be skipped."
    );
    process.exit(1);
  }
  const server = await serve(pages.map((entry) => entry.body), assets.files);
  const base = `http://127.0.0.1:${server.address().port}`;
  const browser = await playwright.chromium.launch();
  const results = [];
  try {
    for (let index = 0; index < pages.length; index += 1) {
      results.push(
        await runPage(browser, index, pages[index].given, pages[index].file, pages[index].body, base)
      );
    }
  } finally {
    await browser.close();
    server.close();
  }
  report(results);
}

main().catch((error) => {
  console.error("the browser test could not run: " + error.message);
  process.exit(1);
});
