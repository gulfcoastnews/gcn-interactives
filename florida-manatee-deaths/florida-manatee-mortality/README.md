# Florida Manatee Mortality Interactive V2

A mobile-first, embeddable interactive built from official Florida Fish and
Wildlife Conservation Commission (FWC) mortality records. GitHub Pages hosts
the static files, and GitHub Actions refreshes the data every day.

## Official data sources

Recent preliminary records are extracted from the individual mortality table
PDF linked on each annual FWC page:

- [FWC manatee mortality statistics](https://myfwc.com/research/manatee/rescue-mortality-response/statistics/mortality/)
- [2026 mortality page](https://myfwc.com/research/manatee/rescue-mortality-response/statistics/mortality/2026/)

Finalized historical records come from:

- [FWC ArcGIS mortality layer](https://gis.myfwc.com/mapping/rest/services/Open_Data/Manatee_Carcass_Recovery_locations_in_Florida/MapServer/32)

`scripts/update_data.py` discovers FWC's current PDF links, parses the three
most recent annual reports, retrieves the preceding three years from ArcGIS,
normalizes the records, validates the result, and atomically replaces
`data/mortality.json`.

## Automatic refresh

The repository-level workflow is:

```text
.github/workflows/update-and-deploy.yml
```

It runs:

- Every day at 8:00 a.m. America/New_York.
- Whenever a change is pushed to `main`.
- Whenever **Run workflow** is selected in GitHub Actions.

The workflow retrieves the sources, validates the data, saves the refreshed
JSON, and deploys the complete `gcn-interactives` repository to GitHub Pages.
If retrieval or validation fails, deployment stops and the last successful
public version remains online.

## Current packaged data

The included dataset contains 4,049 official records covering 2021–2026. The
2026 report is through July 17, 2026.

FWC's 2026 PDF prints a statewide total of 398, while its itemized rows and
cause subtotals contain 397 records. The interactive uses the 397 auditable
records and conditionally displays that source warning immediately above the
footer. If a later report reconciles the totals, the warning automatically
disappears after the next successful update.

## GitHub location

In the existing repository, this directory must be:

```text
gcn-interactives/
├── .github/
│   └── workflows/
│       └── update-and-deploy.yml
└── florida-manatee-mortality/
    ├── index.html
    ├── data/
    ├── scripts/
    ├── assets/
    └── requirements.txt
```

The workflow must remain at the repository root. GitHub will not detect it if
`.github` is placed inside `florida-manatee-mortality`.

## Public URL

```text
https://derricktshaw.github.io/gcn-interactives/florida-manatee-mortality/
```

## Embed

The interactive sends its current height to the parent page. When scripts are
allowed in the publishing system, use:

```html
<iframe
  id="manatee-mortality"
  src="https://derricktshaw.github.io/gcn-interactives/florida-manatee-mortality/"
  width="100%"
  height="4100"
  frameborder="0"
  scrolling="no"
  loading="lazy"
  title="Florida manatee mortality interactive"
  style="display:block;width:100%;border:0;">
</iframe>

<script>
(() => {
  const frame = document.getElementById("manatee-mortality");
  window.addEventListener("message", event => {
    if (event.origin !== "https://derricktshaw.github.io") return;
    if (event.source !== frame.contentWindow) return;
    if (event.data?.type === "manatee-embed:height") {
      frame.style.height =
        `${Math.max(680, Math.ceil(Number(event.data.height) || 4100))}px`;
    }
  });
})();
</script>
```

If the publishing system removes scripts, use the responsive fixed-height CSS
documented in `IMPLEMENTATION.md`.

## Run locally

```powershell
python -m pip install -r requirements.txt
python -m http.server 8000
```

Open `http://localhost:8000/`. To refresh manually:

```powershell
python scripts/update_data.py
python scripts/validate_data.py
```

No API key, database, backend, build system, or paid service is required.
