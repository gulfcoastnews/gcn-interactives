# Florida Manatee Mortality — Interactive

A production-ready, mobile-first interactive built from official Florida Fish
and Wildlife Conservation Commission (FWC) mortality data. It is a static site:
GitHub Pages hosts the files, while GitHub Actions refreshes the data once a day.

## What is connected

- Recent preliminary records come from the individual mortality table PDF linked
  on each official FWC annual mortality page.
- Finalized historical records come from FWC's public ArcGIS mortality layer.
- `scripts/update_data.py` discovers current PDF URLs, downloads the sources,
  normalizes them into `data/mortality.json`, validates the result, and only then
  replaces the published JSON.
- `.github/workflows/update-and-deploy.yml` runs the updater every day and
  deploys the current site to GitHub Pages.

The FWC ArcGIS layer currently trails the preliminary reports, so the updater
uses the annual PDFs for the three most recent reporting years and ArcGIS for
the preceding three finalized years. The source URL and status for every year
are written into the JSON metadata.

## Data note for 2026

The official report through July 17, 2026 prints a statewide total of 398, while
its itemized rows and cause subtotals contain 397 records. The interactive uses
the 397 itemized records so every displayed case is auditable and shows a visible
source note explaining the discrepancy. The updater will preserve and re-check
that warning on each refresh.

## Publish on GitHub Pages

1. Create an empty GitHub repository.
2. Upload all files in this folder to the repository's `main` branch.
3. In **Settings → Pages**, set **Source** to **GitHub Actions**.
4. Open the **Actions** tab and run **Update FWC data and deploy Pages** once.
5. After the run succeeds, GitHub shows the public Pages URL.

The workflow needs no API key or secret. Its repository permissions are limited
to updating the generated JSON and deploying Pages.

## Embed

Replace the example URL and use:

```html
<iframe
  id="manatee-mortality"
  src="https://YOUR-ORG.github.io/YOUR-REPO/"
  title="Florida manatee mortality"
  style="display:block;width:100%;min-height:680px;border:0"
  height="900"
  loading="lazy">
</iframe>
<script>
  addEventListener("message", event => {
    const frame = document.getElementById("manatee-mortality");
    const allowedOrigin = new URL(frame.src).origin;
    if (event.origin !== allowedOrigin) return;
    if (event.data?.type === "manatee-embed:height") {
      frame.style.height = `${Math.max(680, event.data.height)}px`;
    }
  });
</script>
```

The iframe width is always 100%. The interactive posts its current height after
layout and filter changes, so the parent page can avoid a second scrollbar.

## Run locally

Install the one updater dependency and serve the folder over HTTP:

```powershell
python -m pip install -r requirements.txt
python -m http.server 8000
```

Then open `http://localhost:8000/`. Opening `index.html` directly from disk will
not load the JSON.

To refresh manually:

```powershell
python scripts/update_data.py
python scripts/validate_data.py
```

## Data schema

`data/mortality.json` contains `_meta` plus `records`. Each record includes:

`fieldId`, `date`, `county`, `sex`, `lengthCm`, `waterway`, `city`, `cause`,
`causeCode`, `latitude`, `longitude`, `status`, `source`, `sourceAsOf`, and
`fetchedAt`.

Cause categories stay aligned with FWC's published buckets:

- Watercraft
- Flood Gate/Canal Lock
- Human-Related, Other
- Perinatal
- Cold Stress
- Natural
- Undetermined: Too Decomposed
- Undetermined: Other
- Verified, Not Necropsied

`status` is never inferred: PDF records remain `preliminary`; ArcGIS historical
records are `final`.

## Project structure

```text
index.html                         responsive interactive
data/mortality.json                generated official dataset
scripts/update_data.py             official-source fetch and normalization
scripts/validate_data.py           independent publication checks
.github/workflows/                 daily refresh and Pages deployment
assets/                            local fonts and brand image
IMPLEMENTATION.md                  component and behavior reference
```

No build system, backend, database, or paid service is required.
