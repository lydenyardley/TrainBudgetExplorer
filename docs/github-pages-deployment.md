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

### If secrets are missing

The scheduled workflow fails at the download step and does not publish. That is intentional: publishing synthetic or unaudited data would make the provenance line false.

You can still run the application locally with the synthetic feed, but a public real-feed deployment requires the credentials and the relevant RDG/DTD licence permissions.

## Run the first deployment

1. Open the repository's **Actions** tab.
2. Select **build and publish**.
3. Select **Run workflow**.
4. Watch the order of the steps:

   ```text
   download → audit → build → tests → browser test → publish
   ```

5. The site is published only when the audit, Python tests, and browser test all pass.

The workflow also runs daily at 03:17 UTC. GitHub may delay scheduled jobs, so the date shown on the deployed site may be slightly behind the scheduled time.

The feed is checked before building. If the downloaded manifest is unchanged from the last successful build, the workflow skips the build and leaves the currently published site untouched. A changed feed is downloaded, audited, built as a fast single-origin prices page, tested in a browser, and published only if every later step succeeds. The timetable is audited but not loaded for this daily publication because the national calling-point feed makes that a long batch job; local users can opt into it with `run.py --with-timetable`. A failed download, audit, build, or test does not replace the previous GitHub Pages deployment.

The generated page shows both the feed provenance/date and the UTC build timestamp near the prices, so a reader can tell when the snapshot was produced. The daily deployment is a single Grantham-origin page; use the local `--with-timetable` option when journey times are required.

## Project sites and base paths

A normal repository site such as `https://username.github.io/` needs no base path.

A project site such as `https://username.github.io/TrainBudgetExplorer/` needs the path added as an Actions repository variable:

1. Open **Settings → Secrets and variables → Actions**.
2. Open the **Variables** tab.
3. Add a repository variable named `SITE_BASE_PATH`.
4. Set its value to the project path, for example `TrainBudgetExplorer`, without a leading or trailing slash.

The workflow passes this value to the page builder so internal links work under that prefix.

## What gets published

The workflow uploads `_site/`, which contains:

- the generated Grantham-origin page;
- the privacy page;
- static HTML, CSS, and JavaScript embedded in the pages.

The licensed feed ZIPs are not included in the Pages artifact. They are used to generate the pages and are not served as public files.

## Troubleshooting

### Pages shows a 404

Check that **Settings → Pages → Source** is **GitHub Actions**, then inspect the Actions log for the deployment URL.

### Internal links do not work on a project site

Set `SITE_BASE_PATH` to the repository name and run the workflow manually again.

### The download step fails

Check that both `NRDP_USERNAME` and `NRDP_PASSWORD` exist as **Actions repository secrets**. Do not paste their values into an issue or chat.

### The audit fails

Do not bypass the audit. Inspect the failing feed or parser finding, fix the cause, and rerun. The workflow will not publish a failed audit.

### The workflow is using synthetic data locally

That is expected for a fresh local checkout. The scheduled workflow is intentionally real-feed-only. Local `run.bat` uses downloaded real fares when `feeds/fares` exists, otherwise it uses the synthetic demo feed. Journey times are opt-in with `python run.py --with-timetable`, because the national timetable is too large to load on every double-click.

## Hosting elsewhere

The same `_site/` directory can be deployed to any static host that accepts a folder or an artifact: Cloudflare Pages, Netlify, Vercel static hosting, GitLab Pages, or an ordinary web server. Preserve the same build and audit gate before uploading the folder, and configure the host's base path if the site is not served at the domain root.
