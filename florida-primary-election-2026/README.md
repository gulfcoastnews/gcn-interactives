# Florida Primary Election 2026 — Southwest Florida Results

A mobile-first, embeddable results interactive for the August 2026 Florida
primary. GitHub Pages hosts the static files; GitHub Actions mirrors the data
feeds into the repository every five minutes.

## Where to put these files

```text
gcn-interactives/
├── .github/
│   └── workflows/
│       └── election-update-and-deploy.yml   ← from this folder, moved to repo root
└── florida-primary-election-2026/
    ├── index.html
    ├── README.md
    └── data/
        ├── wbbh.xml          (refreshed by the workflow)
        ├── hub-593.json      (created by the workflow on first run)
        ├── hub-535.json      (snapshot included)
        └── freeze.json
```

`election-update-and-deploy.yml` ships inside this folder for convenience but
**must be moved to `.github/workflows/`** at the repository root — GitHub will
not detect it anywhere else. `index.html` is fully self-contained: fonts,
styles, and both logos are inlined, so there are no other assets to copy.

## Data sources

Two feeds, fetched in parallel and merged. If one is unavailable the other still
renders, and the last good data stays on screen.

1. **Associated Press via ENPS** — `https://s3.amazonaws.com/enps-bucket/election/wbbh.xml`
   State and federal contests, with per-county precinct breakdowns.
2. **Hearst Election Hub** — `https://ehub.htvapps.com/wbbh/wp-json/election-hub/v1/widget/{id}?_locale=user`
   Widgets **593** (Primary Election Feed) and **535** (Lee County): county
   commission, school board, judicial, municipal races, and ballot measures.

Widget 593 repeats many of the AP races, so the page de-duplicates across
sources on a normalized office-plus-party key, preferring the AP record because
only it carries the county breakdown. To add a Hub widget, add its id to
`HUB_IDS` in `index.html` **and** to `HUB_IDS` in the workflow.

The page reads `data/` from its own origin first and falls back to the live URLs,
so it works whether or not the mirror has run.

## Automatic refresh

The workflow runs every five minutes, on push to `main`, and on demand
(**Run workflow** in Actions). It fetches both feeds, refuses to publish an AP
response with no `<race>` elements or a Hub response with no `results` array,
commits any change, and deploys the repository to Pages. The page independently
polls every five minutes, so a browser left open stays current without a reload.

GitHub's five-minute cron is a floor, not a guarantee — runs can land late under
load.

## Freezing the results

1. **Automatic** (default) — once every race reports 100% of precincts the page
   stops polling, the status pill turns gold and reads "Final results," and the
   footnote says the totals are frozen.
2. **Flag file** — set `frozen` to `true` in `data/freeze.json` and commit. This
   also stops the workflow from fetching, so the mirrored data holds exactly
   what was on screen.
3. **URL** — add `?freeze=1` to the embed URL.

Set `frozen` back to `false` to reopen the page for a later canvass.

## Public URL

```text
https://gulfcoastnews.github.io/gcn-interactives/florida-primary-election-2026/
```

## Embed

The page posts its height to the parent frame:

```html
<iframe
  id="fl-primary-2026"
  src="https://gulfcoastnews.github.io/gcn-interactives/florida-primary-election-2026/"
  width="100%"
  height="3200"
  frameborder="0"
  scrolling="no"
  loading="lazy"
  title="Southwest Florida election results"
  style="display:block;width:100%;border:0;">
</iframe>

<script>
(() => {
  const frame = document.getElementById("fl-primary-2026");
  window.addEventListener("message", event => {
    if (event.source !== frame.contentWindow) return;
    if (event.data?.type === "gcn-election:height") {
      frame.style.height =
        `${Math.max(680, Math.ceil(Number(event.data.height) || 3200))}px`;
    }
  });
})();
</script>
```

Tighten the listener with an `event.origin` check once the Pages domain is
confirmed.

## Filters

Three dropdowns, each showing counts that respond to the other two:

- **County** — Lee, Collier, Charlotte, Hendry, Glades. AP races match on their
  reporting-unit counties. Hub races are matched by municipality (Cape Coral,
  Bonita Springs, Fort Myers and Estero to Lee; Naples and Marco Island to
  Collier, and so on), by district for U.S. and State House seats, and by
  circuit — the 20th Judicial Circuit is all five counties. A race whose
  footprint can't be determined stays visible under every county.
- **Category** — Governor & Cabinet, U.S. House, State legislature, County
  commission, School board, Judicial, Municipal, Referendums & amendments,
  Other county offices.
- **Party** — Democratic, Republican, Nonpartisan.

Running order: Governor, U.S. House, Agriculture Commissioner, CFO, State
House, local races, then ballot measures.

## Query parameters

| Parameter   | Effect                                                        |
| ----------- | ------------------------------------------------------------- |
| `?demo=1`   | Fills the current races with sample vote totals — rehearse the look before polls close. |
| `?freeze=1` | Locks the page on the results it has loaded.                   |

## Before results start flowing

Both feeds were at zero votes when this was built, so the key each uses for
candidate vote counts is unconfirmed. The AP parser accepts `vote_count`,
`votes`, `vote`, `votecount`, and `total` on any element inside a
`reporting_unit`, matched by candidate id or name, plus a `winner` attribute or
child. The Hub parser accepts `votes`, `vote_count`, and `total_votes` per
candidate; measures use the explicit `yes_votes` / `no_votes`. Load the page
against a live feed once counting starts and confirm the totals match AP's own
numbers before the embed goes wide.
