# GitHub Pages deployment runbook

This project can be hosted as a static site. The deployment target is the generated `_site/` directory; the application itself does not need a server.

GitHub Pages is the default deployment target in `.github/workflows/deploy.yml`.

## Before enabling the workflow

1. Push the project to a GitHub repository.
2. Open **Settings → Pages**.
3. Set **Source** to **GitHub Actions**.
4. Keep the workflow's `pages: write` and `id-token: write` permissions enabled.

## Safely configure the feed credentials

The DTD downloader needs National Rail Data Portal credentials for unattended downloads. Store them as **GitHub Actions repository secrets**, never as code, workflow command-line arguments, checked-in files, or chat messages.

1. Open **Settings → Secrets and variables → Actions**.
2. Select **New repository secret**.
3. Add `NRDP_USERNAME`.
4. Add `NRDP_PASSWORD`.
5. Confirm both secrets are visible in the repository's Actions secret list.

The workflow passes them to the downloader as environment variables:

```yaml
env:
  NRDP_USERNAME: ${{ secrets.NRDP_USERNAME }}
  NRDP_PASSWORD: ${{ secrets.NRDP_PASSWORD }}
```

The downloader does not put either value in the download manifest. Do not print the environment in a workflow step or upload the feed credentials as an artifact.

The reference feeds are downloaded in a second step that is allowed to fail, because the Knowledgebase subscription is a different question from the DTD fares and timetable entitlement. A refusal there is a warning and the build continues; the page then says no independent reference feed was checked.

### If secrets are missing

The scheduled workflow fails at the download step and does not publish. That is intentional: publishing synthetic or unaudited data would make the provenance line false.

You can still run the application locally with the synthetic feed, but a public real-feed deployment requires the credentials and the relevant RDG/DTD licence permissions.

## Run the first deployment

1. Open the repository's **Actions** tab.
2. Select **build and publish**.
3. Select **Run workflow**.
4. Watch the order of the steps:

   ```text
   check the commit messages → download → detect whether the feed changed
   → audit → gate the unsourced count → gate the price per minute
   → build the site → hold the bytes → check the manifest and journeys
   → tests → browser test → clearance → publish
   ```

5. The site is published only when every gate before the publish step passes. Two of them are not optional and not softer than they look. `licences/release-clearance.md` must clear the shape the build publishes, which is `fares,timetable` because the build loads the national timetable, and the `github-pages` environment can require a person to approve the run. Until that clearance is written, the build, the tests and the browser run stay green and only publication waits.

The workflow also runs on every push to `main` and daily at 03:17 UTC. GitHub may delay scheduled jobs, so the date shown on the deployed site may be slightly behind the scheduled time.

**What the build step publishes.** The build runs `build_demo_page.py` with `--feed feeds/fares`, `--timetable feeds/timetable`, `--knowledgebase feeds/knowledgebase`, `--all-origins`, the licence notices the terms require, and `--require-live-reviewed-codes`. So the release is the whole network with journey times: a chooser at the root and one page per priced station under `/from/<slug>/`, each carrying its times and changes. The step's `timeout-minutes` is 300, which is sized for the slowest runner the workflow can land on at the worker count that runner's free memory allows.

**What runs before it, and why.** The downloaded feeds are audited, the checked-in destination facet data is regenerated into a temporary file and compared with the registry (`tools/check_facet_reference.py`, so a facet source that shipped without the reference file being rebuilt fails the run rather than classifying stations from an older registry), the unsourced-destination count is held under a ceiling that falls as reviewed settlement classes land, and `tools/check_fare_rate.py` prices what the page's own selectors publish, so an implausible price per minute fails the run before a page is written rather than after. After the build, `tools/page_bytes.py` holds the release against its byte budget, and the manifest check reads the release's own manifest against the folder and refuses if the route count and the page count disagree or if any station page is missing its journeys. Then the Python suite runs under a coverage floor, and the browser suite drives the demo site, the site that ships, and two shape pages.

**Unchanged feeds skip the work.** The workflow compares a fingerprint of what the feeds *are*, plus a digest of the builder's own source files, against the last successful build. When neither moved, it says so, keeps the existing site, skips the audit, the build and everything that reads the built site, and still runs the commit message check, the Python suite and the browser suite. A failed download, audit, build, gate or test never replaces the previous deployment.

The generated pages show the feed provenance and date and the UTC build timestamp, so a reader can tell when the snapshot was produced, and a build with a date outside the feed's own window fails the journey check instead of publishing prices without times.

## Project sites and base paths

A normal repository site such as `https://username.github.io/` needs no base path.

A project site such as `https://username.github.io/TrainBudgetExplorer/` needs the path added as an Actions repository variable:

1. Open **Settings → Secrets and variables → Actions**.
2. Open the **Variables** tab.
3. Add a repository variable named `SITE_BASE_PATH`.
4. Set its value to the project path, for example `TrainBudgetExplorer`, without a leading or trailing slash.

The workflow passes this value to the page builder so internal links work under that prefix.

### The privacy contact

The build carries a project default privacy address so a real-feed build works locally without an operator supplying one. That default has not been confirmed as monitored, so set a repository variable named `PRIVACY_CONTACT` to the address the publish checklist has confirmed, and the workflow passes it to the build.

## What gets published

The workflow uploads `_site/`, which contains:

- the chooser page at the root;
- one page per priced station under `from/<slug>/`, each with its own fares, times and provenance;
- the privacy page every footer links to;
- the release manifest the build writes beside the pages, and the two shared files a page fetches (the station list its picker reads, and this route's stylesheet).

Static HTML, CSS, and JavaScript are embedded in the pages. The licensed feed ZIPs are not included in the Pages artifact. They are used to generate the pages and are not served as public files.

## Troubleshooting

### Pages shows a 404

Check that **Settings → Pages → Source** is **GitHub Actions**, then inspect the Actions log for the deployment URL.

### The publish job never starts

That is the clearance gate, not a broken workflow. Run

```
python tools/check_release_clearance.py --release fares,timetable
```

and read `docs/publish-checklist.md` §1. The build and its tests are expected to be green while this refuses.

### The build step times out

The step is bounded at 300 minutes. A timeout means the build got slower than the measurement the bound came from, so re-measure rather than raising the number: the comment above the bound in `.github/workflows/deploy.yml` records the workers, the page count and the rate it was set from.

### Internal links do not work on a project site

Set `SITE_BASE_PATH` to the repository name and run the workflow manually again.

### The download step fails

Check that both `NRDP_USERNAME` and `NRDP_PASSWORD` exist as **Actions repository secrets**. Do not paste their values into an issue or chat.

### The audit or a gate fails

Do not bypass it. Inspect the failing feed or parser finding, fix the cause, and rerun. The workflow will not publish a failed audit, an unsourced count over its ceiling, a price per minute outside the band, a release over its byte budget, or a page that lost its journeys.

### The commit message check fails

Every commit the push adds must follow `CONTRIBUTING.md`. The step names the commit that failed; amend the message rather than skipping the step. A scheduled or manual run adds no commits, so it checks nothing and says so.

### The workflow is using synthetic data locally

That is expected for a fresh local checkout. The scheduled workflow is intentionally real-feed-only. Local `run.bat` uses downloaded real fares when `feeds/fares` exists, otherwise it uses the synthetic demo feed. Journey times are opt-in with `python run.py --with-timetable`, because the national timetable is too large to load on every double-click.

## Hosting elsewhere

The same `_site/` directory can be deployed to any static host that accepts a folder or an artifact: Cloudflare Pages, Netlify, Vercel static hosting, GitLab Pages, or an ordinary web server. Preserve the same build and audit gate before uploading the folder, and configure the host's base path if the site is not served at the domain root.
