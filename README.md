# Ukraine Air Alert Stats

Statistics over Ukrainian air raid alerts: **how many**, **how long on average**,
**shortest** and **longest**, filtered by **period** and by **gazetteer level**
(all country / oblast / raion / hromada).

> **Treat these figures as estimates.** Source data comes from the
> [ukrainian-air-raid-sirens-dataset](https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset),
> and the processing behind them may contain mistakes. The page carries the
> same notice.

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

## How it is hosted

The site is **static**. `build.py` fetches the CSV, dedupes it and packs the
whole dataset into a 2.8 MB binary (0.97 MB gzipped) that ships with the page,
and `web/stats.js` does all the filtering in the browser — no API, no server,
no cold starts. A filter takes about 3 ms.

The target is **Workers static assets** (`wrangler.jsonc`), not Pages. There is
no Worker script — Cloudflare simply serves `web/`. Pages would also work, but
Cloudflare now documents Workers as the path for static sites and Pages as the
thing to migrate away from.

### Setting it up

Create it as a **Worker**, not a Pages project — *Create → Workers → Import a
repository*. Pages ignores `wrangler.jsonc` (it looks for `wrangler.toml` with
`pages_build_output_dir`), so with no output directory configured it tries to
upload the whole repository and fails on the cached upstream CSV in `data/`:

```
Error: Pages only supports files up to 25 MiB in size
  data/official_data_en.csv is 28.8 MiB
```

That is a real failure, not a hypothetical — it is how the first attempt at a
second deployment ended. Raising the limit would not have helped either: Cron
Triggers are a Workers feature, so on Pages the live recorder and `/api/live`
would simply not exist, and the site would look deployed while quietly missing
half of itself.

Then set:

| Setting | Value |
|---|---|
| Build command | `npm run build` |
| Deploy command | `npx wrangler deploy` |

Both commands live in `package.json`, so what CI runs stays in version control
rather than drifting inside the dashboard. Cloudflare's build image already has
Python 3.13 and Node, so `npm run build` installs the Python dependencies,
fetches the feed, packs it, runs the parity check and drops the test fixture —
and a parity failure fails the build before anything deploys.

No API token is needed: Cloudflare's GitHub App handles the connection.

### The live layer (testing branch)

The upstream dataset is rebuilt once a day, but alerts happen all day, so
everything since the last rebuild is missing from it — and no free API hands
you "the last 24 hours of alerts" ready made. What is available is the current
state per oblast plus the moment it last changed, so `worker/` watches that and
derives episodes from the transitions.

- `worker/index.js` — a Cron Trigger polls the feed every two minutes and
  serves the record at `/api/live`. Everything else falls through to the static
  assets, so the site is unchanged.
- `worker/live.mjs` — the logic, kept separate so it runs under plain Node.
- `worker/live.test.mjs` — 13 checks, including the Kyiv-to-UTC conversion at
  both DST offsets and the transition folding. Run them with
  `node worker/live.test.mjs`; the build runs them too, so CI skips nothing.

  They are invoked directly rather than through an `npm` script on purpose.
  `main` has no `worker/` to run, so any script entry defined here and not
  there is an insertion the two branches disagree about — and package.json
  conflicts on every merge between them.

Source: [ubilling.net.ua/aerialalerts](https://wiki.ubilling.net.ua/doku.php?id=aerialalertsapi),
no key required. It reports Kyiv local time, which is converted to UTC.

Two deliberate limits:

- **Oblast level only** — that is all the free feed reports. The panel is shown
  separately and is *not* folded into the statistics, because the dataset
  records raions; averaging the two together would compare different things.
- **Transitions are timestamped from the feed's own clock**, not from when we
  polled, so the two-minute cadence sets how quickly the page notices a change,
  not how accurate the recorded times are.

Writes to KV happen only when something actually changed (plus a half-hourly
heartbeat), which keeps a 720-tick day well inside the free tier's write
allowance. The page hides the panel entirely when `/api/live` is absent, so the
same `web/` works on a static-only deployment.

### Keeping the data fresh

Workers Builds rebuilds on every push, but has no schedule of its own. So:

1. Create a **Deploy Hook** under *Workers & Pages → the Worker → Settings →
   Builds → Deploy Hooks*, pointed at `main`.
2. Save its URL as the repository secret `CLOUDFLARE_DEPLOY_HOOK_URL`.

`.github/workflows/daily-refresh.yml` then POSTs it at **04:00 UTC — 07:00
Kyiv** daily, and on demand via *Run workflow*. The hook only rebuilds this
project, so it is far less sensitive than an account API token.

That hour is picked from the upstream feed's own behaviour: its commits land
between 01:23 and 03:19 UTC, so 04:00 clears the latest by about 40 minutes.
GitHub's scheduler is best-effort and often runs a few minutes late, which only
widens that gap. Cron is UTC only, so the run reads 06:00 Kyiv in winter — still
after the feed, which keeps its own UTC schedule.

*Alternative:* GitHub Actions can do the whole build and deploy itself with
`cloudflare/wrangler-action` and `CLOUDFLARE_API_TOKEN` +
`CLOUDFLARE_ACCOUNT_ID` secrets, instead of connecting the repo to Cloudflare.
That keeps everything in one place but means minting a broader token. See
`git show 1843815:.github/workflows/deploy.yml` for that version.

## Install

Needs Python 3.11+:

```bash
pip install -r requirements.txt
```

## Running it locally

```bash
python build.py && python -m airalert.server
```

`build.py` downloads the feed into `data/` (~30 MB, cached 6 h) and writes
`web/data/`; the server then serves `web/` at <http://127.0.0.1:8777>, exactly
as Cloudflare does. Force a fresh download with `python build.py --update`.

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

## Two implementations, kept honest

`airalert/stats.py` is the reference implementation and powers the CLI.
`web/stats.js` is a port of it that runs in the browser. They must agree.

`parity.py` dumps what Python produces for 16 queries — covering both counting
modes, all three gazetteer levels, the hour filter, the standing split and an
empty result — and `check_parity.js` replays them through the real `stats.js`
and diffs, to a tolerance of 1e-6. CI fails if they ever disagree. Open
`/parity.html` for the same check in a browser.

Getting to an exact match turned up three things worth knowing: the pack must
store **seconds** rather than minutes, and derive them from the timestamps
rather than from `duration_min` (a float round-trip truncates a second per
row); and the JS must reproduce Python's **round-half-to-even**, since both
`Math.round(x * 10) / 10` and `toFixed(1)` disagree with it in different cases.

## Layout

```
build.py             fetch, dedupe and pack the dataset for the browser
parity.py            dump Python's answers for the parity scenarios
check_parity.js      replay them through web/stats.js and diff (CI)
airalert/data.py     download, cache, load, dedupe
airalert/stats.py    reference implementation: selection, merging, metrics
airalert/cli.py      command line reports
airalert/server.py   local static server, plus the legacy JSON API
web/index.html       the dashboard
web/stats.js         browser port of airalert/stats.py
web/data/            generated by build.py (gitignored)
data/                cached CSV (gitignored)
```
