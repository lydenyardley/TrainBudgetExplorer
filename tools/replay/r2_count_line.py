"""R2: the count-line check counted the rows on screen; the count line describes
the whole list.

Its own comment said "the mix is the mix of the rows on screen", and on the
synthetic fixture that was true because the whole result set fitted on one
page. On a real page the line reads "266 destinations for up to £2.00 each,
cheapest first: 2 singles, 264 returns" while twenty rows are on screen, so the
check compared a page of rows with a summary of everything below the budget.

The count line is right and the check was wrong. It describes every destination
the budget admits, which is the number a reader needs in order to know how much
of the network they are looking at.

The fix is not to reach into the page for that list -- `available` is local to
`render()` and is not reachable, and the first attempt at this tried and found
that out -- but to ask the line a question it can answer about itself: the
counts it names must add up to the total it states, and every kind of fare
among the rows on screen must be one it names. The first is the real
guarantee, and it holds whether the list fits on one page or forty.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD_KINDS = '''      // The mix is the mix of the rows on screen: the count line describes the
      // list the reader is looking at, and a budget that leaves one row leaves
      // one kind of fare in it.
      const kinds = {};
      for (const crs of shown.map((row) => row.crs)) {
        const wanted = cheapest.get(crs);
        if (!wanted) continue;
        const word = wanted.quality === "outbound single"
          ? "single" : wanted.quality === "unrestricted Anytime Day Return" ? "Anytime Day Return" : "return";
        kinds[word] = (kinds[word] || 0) + 1;
      }'''

NEW_KINDS = '''      // The mix among the rows on screen, kept for the second half of the check:
      // every kind of fare a reader can see must be one the line names.
      const kinds = {};
      for (const crs of shown.map((row) => row.crs)) {
        const wanted = cheapest.get(crs);
        if (!wanted) continue;
        const word = wanted.quality === "outbound single"
          ? "single" : wanted.quality === "unrestricted Anytime Day Return" ? "Anytime Day Return" : "return";
        kinds[word] = (kinds[word] || 0) + 1;
      }
      // The counts the line states for itself. It describes every destination
      // the budget admits, which is not the twenty rows on screen and not the
      // page's private list either -- `available` is local to render(). So the
      // line is asked to agree with itself, which is the guarantee that matters
      // and the only one that can be read off it.
      const line = document.getElementById("summary").textContent;
      const total = Number((/([0-9,]+) destinations?/.exec(line) || [0, "0"])[1].replace(/,/g, ""));
      const named = [];
      for (const m of line.matchAll(/([0-9,]+) (Anytime Day Returns?|singles?|returns?)\\b/g)) {
        named.push({ word: m[2], count: Number(m[1].replace(/,/g, "")) });
      }'''

OLD_CHECK = '''    const kinds = Object.entries(headline.kinds);
    const namedKinds = kinds.filter(([word, count]) =>
      new RegExp(`\\\\b${count} ${count === 1 ? word : word + "s"}\\\\b`).test(headline.summary)
    );
    check(
      "and the count line names the mix of ticket types it is showing",
      headline.shown.length === 0
        ? notExercised("this page shows no row to count")
        : namedKinds.length === kinds.length,
      JSON.stringify({ kinds: headline.kinds, summary: headline.summary })
    );'''

NEW_CHECK = '''    const kinds = Object.entries(headline.kinds);
    // Every kind of fare among the rows on screen is named by the line, and the
    // line's own counts add up to the total it states. The second half is the
    // one that cannot be satisfied by a coincidence of a small fixture: a line
    // that says "266 destinations ... 2 singles, 264 returns" is either right
    // about its own arithmetic or it is not.
    const namedSum = headline.named.reduce((total, entry) => total + entry.count, 0);
    const unseen = kinds.filter(([word]) => !headline.named.some(
      (entry) => entry.word.replace(/s$/, "").toLowerCase() === word.toLowerCase()
    ));
    check(
      "and the count line names the mix of ticket types it is showing",
      headline.shown.length === 0
        ? notExercised("this page shows no row to count")
        : unseen.length === 0 &&
          headline.named.length > 0 &&
          namedSum === headline.total,
      JSON.stringify({ kinds: headline.kinds, total: headline.total, named: headline.named, summary: headline.summary })
    );'''

OLD_RETURN = '''        shown,
        kinds,
        summary: document.getElementById("summary").textContent,
      };'''

NEW_RETURN = '''        shown,
        kinds,
        total,
        named,
        summary: document.getElementById("summary").textContent,
      };'''

patch(
    "tests/browser_test.cjs",
    [
        (OLD_KINDS, NEW_KINDS),
        (OLD_CHECK, NEW_CHECK),
        (OLD_RETURN, NEW_RETURN),
    ],
)
