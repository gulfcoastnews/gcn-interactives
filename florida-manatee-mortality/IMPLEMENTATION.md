# Florida Manatee Mortality V2 — Implementation Notes

## Runtime

The interactive is a static, buildless site:

```text
index.html                 complete interface, CSS and JavaScript
data/mortality.json        generated official FWC dataset
scripts/update_data.py     official-source retrieval and normalization
scripts/validate_data.py   independent publication checks
requirements.txt           updater dependency
assets/                    fonts and brand image
```

D3 7.9.0 and TopoJSON Client 3.1.0 are loaded from pinned CDNs for the
choropleth. County geometry is loaded from `us-atlas`. If the map dependency is
unavailable, charts and the county ranking continue to work.

## Data contract

`data/mortality.json` contains `_meta` and `records`.

Metadata includes:

- `sample`: always `false` in production.
- `source` and `sourceUrl`: official attribution.
- `fetchedAt`: most recent successful website refresh.
- `recordCountsByYear`: validation totals.
- `coverage`: source, status, through date and totals by year.
- `sourceFeeds`: official annual-page and ArcGIS endpoints.
- `warnings`: source discrepancies suitable for public display.

Each record contains:

```text
fieldId, date, county, sex, lengthCm, waterway, city, cause,
causeCode, latitude, longitude, status, source, sourceAsOf, fetchedAt
```

## Official cause categories

The interface and updater preserve FWC's nine categories:

- Watercraft (`WC`)
- Flood Gate/Canal Lock (`GL`)
- Human-Related, Other (`HR`)
- Perinatal (`PN`)
- Cold Stress (`CS`)
- Natural (`NA`)
- Undetermined: Too Decomposed (`UD`)
- Undetermined: Other (`UO`)
- Verified, Not Necropsied (`VN`)

## Status and integrity

- Annual-PDF records remain `preliminary`.
- Finalized ArcGIS records are labeled `final`.
- Preliminary records are never inferred to be final because a year ended.
- Both the source through-date and website refresh date are displayed.
- Mortality totals are explicitly separated from population estimates.
- A one- or two-record source-total discrepancy becomes a public warning.
- A larger mismatch, duplicate ID, empty report, unknown cause, invalid date or
  other structural error stops publication.
- The previous-year chart is cut off at the same day of year as the selected
  report.

## Conditional source warning

`_meta.warnings` is rendered only when it is non-empty. The warning appears
after the methodology drawer and immediately above the footer. When totals
reconcile, the array is empty and no warning element is created.

## Responsive fixed-height fallback

The preferred embed uses the built-in `postMessage` height event. If parent-page
scripts are unavailable, measured default-state fallbacks are:

```css
#manatee-mortality {
  display: block;
  width: 100%;
  height: 4100px;
  border: 0;
}

@media (min-width: 350px) {
  #manatee-mortality { height: 3900px; }
}

@media (min-width: 420px) {
  #manatee-mortality { height: 3800px; }
}

@media (min-width: 900px) {
  #manatee-mortality { height: 2550px; }
}
```

Opening methodology or table views can increase the page height; dynamic
resizing is therefore preferred.

## GitHub workflow

The deployment workflow lives at the root of the multi-interactive repository,
not inside this site folder. It:

1. Installs `pdfplumber`.
2. retrieves recent FWC PDFs and finalized ArcGIS records;
3. validates and saves `data/mortality.json`;
4. commits a changed dataset; and
5. deploys the complete repository to GitHub Pages.

The schedule is 8:00 a.m. Eastern daily using the
`America/New_York` timezone.
