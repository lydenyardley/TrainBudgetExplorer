# ADR-0067: Licence PDFs stay off the public repository

**Status:** Accepted
**Date:** 9 October 2026
**Relates to:** ADR-0005 (a licensed feed is not checked in), ADR-0021 (the register matches the shelf), the release gate in `tools/check_release_clearance.py`

## Context

The repository is public. `licences/` held the marketplace PDFs and the NRE
terms, brand guidelines and developer pack. Those files are the publisher's
text. Keeping them in a public git history publishes them to anyone who can
clone the repository, which this project has not been told it may do.

The release gate and `tests/test_licences.py` were written to read those PDFs:
a product id from the filename, a SHA-256 so a clearance cannot outlive the
file it was made from, and a refusal when a PDF has no decision. Deleting the
files and leaving the checks to shrug would let a changed or missing licence
through, which is the failure the gate exists to stop.

The PDFs are already in the history of the commit that was pushed. This ADR
does not rewrite that history.

## Decision

1. **Git tracks a manifest, not the PDFs.** `licences/licence-manifest.json`
   has one row per file: `filename`, `sha256`, and `product_id` (null for a
   supporting document). `licences/*.pdf` is ignored. `git rm --cached` drops
   the files from the index and leaves the local copies in place.
   `licences/README.md` and `licences/release-clearance.md` stay tracked.

2. **The product list is the manifest.** `products()` reads product ids from
   the manifest, including when the PDF is not in the checkout. CI therefore
   still demands a clearance section for every marketplace product.

3. **The digest check has two sides, and both refuse.**
   - The clearance's `licence digest` must equal the manifest hash. Replacing
     a row without a new clearance fails the publish job, which has no PDF.
   - When the PDF is on disk, its SHA-256 must equal the manifest. A local
     copy that has drifted fails the gate even if the clearance still matches
     the old manifest, and a PDF the manifest does not name fails it too.
   A missing manifest is a refusal, not an empty shelf.

4. **The register test follows the same shelf.** `tests/test_licences.py`
   pairs the manifest with `licences/README.md`. It hashes PDFs only when
   they are present, so CI (no PDFs) and a workstation (PDFs on disk) both
   fail a shelf that has drifted.

5. **Nothing here clears a product.** `state` stays `excluded` until a person
   writes a clearance. Taking the PDFs out of git is not a licence decision.

## Consequences

A clone from GitHub has no licence text. A person who holds the PDFs keeps
them in `licences/` and the gate checks them. A person who does not can still
run the suite; the publish path checks the manifest.

The pushed history still contains the PDFs. Removing them from the public
history means a history rewrite and a force-push. This change does not do that.

`python tools/check_release_clearance.py --print` still prints each product's
digest: from the PDF when the file is there, otherwise from the manifest.
