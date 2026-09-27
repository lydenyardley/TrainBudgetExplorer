# ADR-0034 — The release is the routes its manifest names

**Date:** 27 September 2026
**Status:** accepted

## Context

The re-envision audit's S07 asks for a staging directory: build there, validate,
then publish the whole verified artifact, so a host never serves a mixture of
this build's pages and an earlier build's.

An earlier commit in this project added `publish_staged()` for exactly that: it
moved the output folder aside and moved the staging folder into place. It was
never called. Two things in this project make it the wrong shape:

1. **`--fast-all-origins` resumes from the folder it writes into.** It keeps a
   `.trainbudget-build.json` beside the pages and treats a page file that is
   already there as complete. A staging folder that starts empty throws away the
   work a resumed run was about to skip — which is the entire point of that
   mode on a 2,500-station build.
2. **The project has a tested decision not to delete a page it did not write.**
   A build names the folders in the output that came from an earlier build and
   leaves them alone, because deleting an operator's files without asking is not
   something a build should do on its own initiative.

Swapping the whole folder anyway would have been the easy version, and it would
have quietly reversed both.

## Decision

1. **A release is a named set of routes, and the build proves it.** Every build
   writes `release-manifest.json` beside the pages: the base path, the price
   source, whether the data is synthetic, the build time, and every route in the
   release — the chooser, each station page, the privacy page. The build then
   resolves each route against the files on disk and **refuses** rather than
   reporting success if it named a route it did not write.
2. **The link crawl asks the other question.** It walks every internal link a
   reader can follow — including the chooser's station links, which its script
   builds from an embedded array rather than from `href` attributes — and
   refuses a site with a dangling one. Manifest and crawl together are a release
   that is complete in both directions: every route exists, and every link
   resolves.
3. **CI checks the manifest against the artifact.** A build that wrote no
   manifest fails the deploy, and so does a folder whose `index.html` count and
   manifest route count disagree.
4. **The output folder is not cleared first, and pages the build did not write
   are still named rather than deleted.** A local preview can therefore hold an
   earlier build's pages; nothing links to them, because the chooser and the
   picker are built from this release's manifest.

## Consequences

- "The whole verified output" is a set a person or a host can read, rather than
  a property of a folder. `jq '.routes | length' _site/release-manifest.json`
  answers the question the audit was really asking.
- A build that half-finished cannot be published: the manifest is written last,
  after the crawl passes, so a folder without one is a folder whose release was
  never completed.
- The resume mode and the non-deletion rule both survive. What is given up is
  the guarantee that the folder contains nothing but this release — which, given
  that no link can reach a foreign page, was a guarantee about files rather than
  about anything a reader sees.
- The staged swap is gone rather than dormant. Dead code that describes a
  guarantee the build does not make is worse than no code: it reads as done.

## Alternatives rejected

- **Wire up the swap and change the two behaviours it breaks.** Deleting a
  resumed build's pages to satisfy a suggestion is a bad trade in both
  directions, and the resume mode exists because the full-network build is
  measured in hours.
- **Copy the existing folder into staging first, then swap.** Correct, and
  quadratic in the size of a full-network build for no gain a reader can see.
- **A link crawl alone.** It proves every link resolves; it cannot say a route
  the release intended to serve is missing, because nothing links to it.
- **Leave the helper in place, unused, with a note.** The note is the thing that
  goes stale.
