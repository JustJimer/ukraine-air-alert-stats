# Ukraine Air Alert Stats

Statistics over Ukrainian air raid alerts: **how many**, **how long on average**,
**shortest** and **longest**, filtered by **period** and by **gazetteer level**
(all country / oblast / raion / hromada).

No logger was needed — a complete, free, daily-updated historical dataset already exists.

## Data source

[`Vadimkin/ukrainian-air-raid-sirens-dataset`](https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset)
— CSV, no API key, no rate limit, refreshed daily.

| | |
|---|---|
| Coverage | 2022-03-15 → today (`official`), 2022-02-25 → today (`volunteer`) |
| Rows | ~291,000 alert records |
| Columns | `oblast, raion, hromada, level, started_at, finished_at, source` |
| Granularity | oblast-level until Dec 2025, raion/hromada-level since |

Alternatives, both requiring a free API key and offering less history in one call:
[alerts.in.ua](https://devs.alerts.in.ua/) (`/v1/regions/{uid}/alerts/{period}.json`)
and the official [api.ukrainealarm.com](https://api.ukrainealarm.com) (`/api/history`).
Add them in `data.py` if you ever need live polling.

## Install

Needs Python 3.11+ and pandas (already present on this machine):

```bash
pip install -r requirements.txt
```

## Web app

```bash
python -m airalert.server
```

Opens <http://127.0.0.1:8777>. Dataset is downloaded on first run into `data/`
(~30 MB, cached 6 h) and held in memory, so filtering is instant and works
offline afterwards. Force a refresh with `--update`.

Filters: oblast → raion → hromada cascade, from/to dates, quick period presets,
counting mode. Shows headline cards, alerts per month, start-hour distribution
and a busiest-areas table.

**The charts are filters.** Click a month bar to zoom the period to that month;
click hour bars to toggle an hour-of-day filter (multi-select, and the histogram
keeps showing the full distribution so you can still see what you are selecting
against); click a row in the busiest-areas table to drill one gazetteer level
deeper. The active hour filter appears as a chip you can clear.

**Hold and drag across bars to select a range** — a date range on the month
chart, a time range on the hour chart. A band follows the pointer while you
drag. A drag that never leaves its starting bar is treated as a click, so
single-bar behaviour is unchanged.

**Clearing a chart filter**: each chart grows a *Reset* button while its own
filter is active, and clicking a chart anywhere off the bars clears that
chart's filter too. Each resets only its own dimension — the area selection
stays put. *Reset filters*, by the presets, clears everything.

**The last used selection is restored** on the next visit, held in
`localStorage`, so nothing leaves the machine.

## Command line

```bash
python -m airalert.cli --oblast "Kyivska oblast" --from 2026-01-01
```

```bash
python -m airalert.cli --list-oblasts
```

| Flag | Meaning |
|---|---|
| `--oblast` / `--raion` / `--hromada` | gazetteer filter, omit all for whole country |
| `--from` / `--to` | period, `YYYY-MM-DD`, `--to` is exclusive |
| `--raw` / `--merge` | override the counting mode |
| `--standing-days N` | threshold for standing alerts, `0` to include them |
| `--hours` | only alerts starting in these Kyiv hours, e.g. `22,23,0,1` |
| `--update` | force a fresh download |
| `--json` | full payload instead of the text report |

## Data cleaning applied on load

**Duplicate rows.** ~39% of the upstream feed is repeated verbatim (113,845 of
291,611 rows as of 2026-08-14). Two distinct alerts for the same area cannot
share a start *and* end timestamp to the second, so identical rows are
duplicates, not events. `data.load()` drops them — otherwise every count and
total-hours figure is inflated by up to ~64%. The number removed is shown in
the app header.

**Standing alerts.** Frontline territories keep a siren declared continuously
for months — the record for Lypetska hromada runs 604 days. These are real, but
averaging them in makes "longest" and "average" meaningless. Alerts of 7 days or
more are reported in their own section instead of being mixed into the
statistics. Change the threshold, or fold them back in, from the
**Standing alerts** dropdown (`--standing-days` on the CLI, `0` to disable).

## Two counting modes — read this before quoting numbers

Alerts are declared at mixed granularity, and a query for one raion must also
pick up the oblast-wide alerts that covered it. That makes intervals overlap,
so there are two honest ways to count:

- **Raw** — every declaration counted separately. Correct for *all-country*
  figures and for comparing how often each area was individually alerted.
- **Merged** — overlapping declarations collapsed into one territory-wide
  episode ("the siren was on somewhere in this area from A to B"). Correct for
  *a chosen* oblast/raion/hromada.

`Auto` (the default) picks merged when an area is selected and raw for the whole
country. Merging the whole country is degenerate — a siren is on somewhere
almost always, so a year collapses into ~20 month-long episodes.

Alerts are assigned to a period by their **start** time, so each is counted once
and durations are never clipped.

## Why the breakdown adds up to more than the parent

The busiest-areas table counts, for each child area, **how many alerts covered
it** — not how many name it. An alert declared for a whole oblast carries no
raion, but it put every raion in that oblast under alert, so it counts towards
each of them.

Grouping on the raion column alone would drop those rows entirely. That is how
Mykolaivska oblast could show 8,932 alerts and break down into raions totalling
only 5,251 — the 3,681 oblast-wide alerts vanished. They are now included, and
the *Own* column shows what each area was individually declared for:

```
8,932 oblast total  =  5,251 raion/hromada-level  +  3,681 oblast-wide
Mykolaivskyi raion  =  1,480 own                  +  3,681 shared  =  5,161
```

Rows therefore sum to more than the parent, which is correct: one oblast-wide
siren is a single alert that covers four raions at once. The shared figure is
stated under the table so the overlap is never hidden. Clicking a row drills in
and reproduces that row's number exactly, in raw mode.

## Layout

```
airalert/data.py     download, cache, load, gazetteer tree
airalert/stats.py    area/period selection, overlap merging, metrics
airalert/cli.py      command line reports
airalert/server.py   stdlib HTTP server + JSON API
web/index.html       single-file dashboard, no build step, no CDN
data/                cached CSV (gitignored)
```
