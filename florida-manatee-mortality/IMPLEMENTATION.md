# Florida Manatee Mortality — Interactive (handoff)

A self-contained, embeddable data interactive. No backend, no build step, no framework. Drop the folder on any static host (GitHub Pages) and embed `index.html` in an iframe.

```
index.html                 the whole interactive (HTML + inline CSS + vanilla JS)
data/mortality.json        generated official FWC dataset
scripts/update_data.py     fetches and normalizes official sources
scripts/validate_data.py   independent publication checks
assets/fonts/*.ttf         Effra (HTV Sales typeface)
```

External runtime deps (loaded from pinned, hash-verified CDN in `<head>`):
`d3@7.9.0`, `topojson-client@3.1.0` (for the county map only). County geometry
is fetched at runtime from `us-atlas@3.0.1/counties-10m.json`; if that fetch
fails the map degrades to a "map unavailable" panel and the ranked list + all
charts keep working.

---

## Deploying to GitHub Pages
1. Commit the folder to a repo and set Pages source to **GitHub Actions**.
2. Run **Update FWC data and deploy Pages** once from the Actions tab.
3. The interactive is `index.html`. Paths are all relative, so it works from any subpath.
4. Embed in an article:
```html
<iframe src="https://<org>.github.io/<repo>/" title="Florida manatee mortality"
        style="width:100%;border:0" height="900" loading="lazy" id="manatee"></iframe>
```

### Responsive iframe height (postMessage)
The interactive posts its height to the parent whenever content changes:
`{ type: "manatee-embed:height", height: <px> }`. Host page:
```html
<script>
addEventListener("message", e => {
  if (e.data && e.data.type === "manatee-embed:height")
    document.getElementById("manatee").style.height = e.data.height + "px";
});
</script>
```
Width is always `100%`; the layout is fluid from 320px to 1200px. Min height ≈ 680px.

---

## Data contract — `data/mortality.json`
The daily workflow generates this file from official FWC sources. The UI accepts
**either** a bare array of records
**or** `{ "_meta": {...}, "records": [...] }` (preferred — carries source/refresh info).

`_meta` (optional but recommended):
| key | purpose |
|---|---|
| `sample` | `true` shows the "Sample data" flag; set `false`/omit for production |
| `source` | source attribution string |
| `sourceUrl` | link to official FWC statistics (opens in new tab) |
| `fetchedAt` | ISO timestamp of the last successful data refresh (drives "last refreshed" + stale check) |
| `causeGlossary` | optional; UI already ships FWC definitions |

Each **record** (fields the UI reads):
`fieldId, date (YYYY-MM-DD), county, sex, lengthCm, waterway, city, cause,
causeCode, latitude, longitude, status ("preliminary"|"final"), source,
sourceAsOf (YYYY-MM-DD), fetchedAt`.

**Nothing is hard-coded.** Years, totals, the "reported through" date (max
`sourceAsOf` per year), the refresh date, county & cause option lists, and the
preliminary/final badge are all derived from the JSON at load time.

### Cause categories (FWC official wording — never merged in the UI)
`Watercraft` (WC) · `Flood Gate/Canal Lock` (GL) ·
`Human-Related, Other` (HR) · `Perinatal` (PN) · `Cold Stress` (CS) ·
`Natural` (NA) · `Undetermined: Too Decomposed` (UD) ·
`Undetermined: Other` (UO) · `Verified, Not Necropsied` (VN).
County joins the map by name via the `FL_FIPS` table in `index.html`.

### Official update path

The three most recent years are parsed from the individual mortality table PDF
linked by each annual FWC statistics page. The preceding three finalized years
come from the FWC ArcGIS mortality layer. The updater discovers PDF URLs rather
than hard-coding FWC's rotating media paths, validates row totals and duplicate
IDs, and replaces the JSON atomically. GitHub Actions runs it daily at 9:17 a.m.
America/New_York; a failed refresh stops deployment, preserving the last good
public version.

---

## Behavior notes

**Filters** (year / county / cause) + **Reset** — all `<select>`, keyboard & touch
operable, min 44px targets. On mobile the filter panel is a collapsible `<details>`
(open by default ≥720px). Every filter change re-derives all sections and
announces via an `aria-live` region.

**Headline** — big total for the selected year; a coral **Preliminary** badge (or
navy **Final**) derived from record `status`; "reported through" + "last refreshed"
dates; source link. A persistent note states totals are not population estimates.

**Cause breakdown** — labeled horizontal bars (label + count + % + plain-language
definition; never color-only). "View as table" toggles an accessible `<table>`.

**Cumulative chart** — SVG line, current year vs. previous year (on by default).
Both series are cut at the **same day-of-year** as the current reporting cutoff, with
an explicit note, so a partial year is never compared to a full one. Values are
read via pointer, tap, or ←/→/Home/End keys on a `role="slider"` overlay
(tooltip + `aria-valuetext`); full values also in the table view.

**Geography** — d3 choropleth (log color scale; legend with numeric ends + "none
reported"), county paths are focusable buttons that filter on click/Enter; a live
readout shows the focused county. Ranked county list beside/below (top 12; full list
in table view) — rows also filter. On mobile map stacks above the list.

**CSV** — client-side Blob download of the currently filtered records, all schema
columns, with a `# SAMPLE DATA` header line while `_meta.sample` is true.

**States** — loading (skeleton), normal, empty (filtered), stale (refresh older than
`CFG.STALE_DAYS`, default 10), update-failure (falls back to `localStorage`
last-known-good, shows notice, never zeros out), map-unavailable, and official
source warnings. The prototype-only state switcher has been removed.

**Accessibility** — WCAG 2.1 AA contrast, 16px+ body / 14px+ secondary, visible
3px focus rings, no hover-only info (everything reachable by tap/keyboard),
`prefers-reduced-motion` honored + a manual "Reduce motion" toggle, chart data
available as tables, descriptive `aria-label`s on map/charts/filters/status.

---

## Design tokens (HTV Sales + Florida coastal)
Defined as CSS custom properties at the top of `index.html`:
navy `#00102D`, Gulf blue `#1A6BE1`, sky `#5692D1`, gold `#F1D273`,
sea-glass `#2F7D5B`, sand `#EBDCBF`, coral `#B4341F` (emphasis/alerts only).
Cause colors: `--c-WC…--c-VN`. Typeface: Effra (300–800). Radius 8px, cool-tinted
shadows. Keep coral for emphasis only; don't add decorative gradients behind charts.

## Config knobs (`CFG` in index.html)
`DATA_URL`, `COUNTY_TOPO_URL`, `STALE_DAYS`, `LKG_KEY` (localStorage cache key).

## Data integrity rules baked in
- Preliminary records are never relabeled final.
- Both the "through" date and the site refresh date are always shown.
- Year-over-year comparison is like-for-like (same cutoff day).
- Mortality totals are explicitly framed as *not* a population trend.
