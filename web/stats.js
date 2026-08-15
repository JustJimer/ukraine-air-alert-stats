/* Client-side port of airalert/stats.py.
 *
 * The Python module stays the reference implementation and the CLI; this runs
 * the identical logic over the packed arrays from build.py so the static site
 * needs no server. parity.py drives both over the same queries and diffs them,
 * so any drift between the two shows up as a failing check rather than as
 * quietly wrong numbers on the page.
 *
 * Month and Kyiv-hour buckets are precomputed by the build, which keeps DST
 * handling in pandas where it is already correct.
 */
/* Attached to `window` in the browser and to `globalThis` under Node, so the
   CI parity check can exercise this exact file without a browser. */
(function (root) {
  "use strict";

  const SECOND = 1000;
  let D = null;

  function load(meta, buffer) {
    const n = meta.rows, o = meta.offsets;
    D = {
      n,
      base: Date.parse(meta.base),
      baseMonth: meta.base_month,
      noDuration: meta.no_duration,
      standingDays: meta.standing_alert_days,
      starts: new Uint32Array(buffer, o.starts, n),
      durations: new Uint32Array(buffer, o.durations, n),
      months: new Uint16Array(buffer, o.months, n),
      hours: new Uint8Array(buffer, o.hours, n),
      oblast: new Uint8Array(buffer, o.oblast, n),
      raion: new Uint16Array(buffer, o.raion, n),
      hromada: new Uint16Array(buffer, o.hromada, n),
      oblasts: meta.oblasts,
      raions: meta.raions,
      hromadas: meta.hromadas,
      tree: meta.tree,
      coverage: meta.coverage,
    };
    D.oblastIx = index(meta.oblasts, 0);
    D.raionIx = index(meta.raions, 1);
    D.hromadaIx = index(meta.hromadas, 1);
    return D;
  }

  const index = (names, from) => {
    const map = new Map();
    names.forEach((name, i) => map.set(name, i + from));
    return map;
  };

  /* ---------- gazetteer ---------- */

  /* oblast -> raion -> hromada, by name, for the cascade. Built from the whole
     dataset so an area that only saw parent-level alerts still appears. */
  function gazetteer() {
    const out = {};
    for (const [oi, raions] of Object.entries(D.tree)) {
      const branch = {};
      for (const [ri, hromadas] of Object.entries(raions)) {
        branch[D.raions[+ri - 1]] = hromadas.map(hi => D.hromadas[hi - 1]);
      }
      out[D.oblasts[+oi]] = branch;
    }
    return out;
  }

  function childrenOf(oblastName, raionName) {
    if (!oblastName) return D.oblasts.slice();
    const branch = D.tree[D.oblastIx.get(oblastName)] || {};
    if (!raionName) return Object.keys(branch).map(ri => D.raions[+ri - 1]).sort(cmp);
    const ri = D.raionIx.get(raionName);
    return (branch[ri] || []).map(hi => D.hromadas[hi - 1]).sort(cmp);
  }

  const cmp = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

  /* ---------- selection ---------- */

  const toSeconds = iso => (Date.parse(iso + "T00:00:00Z") - D.base) / SECOND;

  /* Rows whose declared area covers, or sits inside, the requested area —
     the same rule as stats.select_area. An oblast-wide alert has no raion but
     still covered every raion in that oblast, so it is kept. */
  function selectRows(oblastName, raionName, hromadaName, start, end) {
    const oi = oblastName ? D.oblastIx.get(oblastName) : -1;
    const ri = raionName ? D.raionIx.get(raionName) : 0;
    const hi = hromadaName ? D.hromadaIx.get(hromadaName) : 0;
    const from = start ? toSeconds(start) : -Infinity;
    const to = end ? toSeconds(end) : Infinity;

    const rows = [];
    for (let i = 0; i < D.n; i++) {
      if (oi >= 0 && D.oblast[i] !== oi) continue;
      if (ri > 0) {
        const r = D.raion[i];
        if (r !== 0 && r !== ri) continue;
        if (hi > 0 && r !== 0) {
          const h = D.hromada[i];
          if (h !== 0 && h !== hi) continue;
        }
      }
      const s = D.starts[i];
      if (s < from || s >= to) continue;
      rows.push(i);
    }
    return rows;
  }

  /* Intervals carry start/end in seconds and duration in minutes, the unit the
     statistics report in — matching stats.py, which divides total_seconds by
     60. `row` is -1 once merged, because an episode spans a territory rather
     than one declared area. */
  function toIntervals(rows) {
    return rows.map(i => {
      const known = D.durations[i] !== D.noDuration;
      return {
        start: D.starts[i],
        end: known ? D.starts[i] + D.durations[i] : null,
        duration: known ? D.durations[i] / 60 : null,
        month: D.months[i],
        hour: D.hours[i],
        row: i,
      };
    });
  }

  /* Collapse overlapping intervals into territory-wide episodes. Rows arrive
     in start order and unfinished alerts are dropped, matching the Python. */
  function mergeOverlaps(intervals) {
    const episodes = [];
    for (const it of intervals) {
      if (it.duration === null) continue;
      const last = episodes[episodes.length - 1];
      if (last && it.start <= last.end) {
        last.end = Math.max(last.end, it.end);
        last.duration = (last.end - last.start) / 60;
      } else {
        // An episode starts at a real row's start, so it inherits that row's
        // precomputed month and hour buckets.
        episodes.push({ start: it.start, end: it.end, duration: it.duration,
                        month: it.month, hour: it.hour, row: -1 });
      }
    }
    return episodes;
  }

  const isStanding = (it, days) =>
    days != null && it.duration !== null && it.duration >= days * 1440;

  /* ---------- statistics ---------- */

  /* pandas Series.quantile with linear interpolation, over sorted values. */
  function quantile(sorted, q) {
    if (!sorted.length) return null;
    const pos = (sorted.length - 1) * q;
    const lo = Math.floor(pos), hi = Math.ceil(pos);
    if (lo === hi) return sorted[lo];
    return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
  }

  /* Python's round(x, 1): round half to even, judged on the double's exact
     value. Neither shortcut works alone — Math.round(x * 10) / 10 lets the
     multiply nudge 37.0499... up to exactly 370.5 and rounds it away, while
     toFixed(1) rounds a real tie like 37.25 to 37.3 where Python gives 37.2.
     So read the exact decimal expansion and apply the rule directly. */
  function round1(x) {
    if (x == null) return null;
    if (!Number.isFinite(x)) return x;

    const negative = x < 0;
    const [whole, fraction = ""] = Math.abs(x).toFixed(20).split(".");
    let tenths = Number(whole) * 10 + Number(fraction[0] || 0);
    const rest = fraction.slice(1);

    if (/^50*$/.test(rest)) {
      if (tenths % 2) tenths += 1;              // exact tie: settle on even
    } else if (rest && Number(rest[0]) >= 5) {
      tenths += 1;
    }
    return negative ? -(tenths / 10) : tenths / 10;
  }
  const iso = seconds => new Date(D.base + seconds * SECOND).toISOString().replace(".000Z", "+00:00");

  function describe(it) {
    const out = {
      started_at: iso(it.start),
      finished_at: iso(it.end),
      duration_min: round1(it.duration),
      oblast: null, raion: null, hromada: null, level: null,
    };
    if (it.row >= 0) {
      const r = D.raion[it.row], h = D.hromada[it.row];
      out.oblast = D.oblasts[D.oblast[it.row]];
      out.raion = r ? D.raions[r - 1] : null;
      out.hromada = h ? D.hromadas[h - 1] : null;
      // Not packed: implied by which fields are set, and build.py asserts it.
      out.level = h ? "hromada" : r ? "raion" : "oblast";
    }
    return out;
  }

  function summarise(intervals) {
    const finished = intervals.filter(it => it.duration !== null);
    const summary = {
      count: intervals.length, finished: finished.length,
      ongoing: intervals.length - finished.length,
      total_hours: null, avg_min: null, median_min: null, p90_min: null,
      min_min: null, max_min: null, shortest: null, longest: null,
    };
    if (!finished.length) return summary;

    let total = 0, shortest = finished[0], longest = finished[0];
    for (const it of finished) {
      total += it.duration;
      if (it.duration < shortest.duration) shortest = it;   // strict: keep the first
      if (it.duration > longest.duration) longest = it;
    }
    const sorted = finished.map(it => it.duration).sort((a, b) => a - b);

    summary.total_hours = round1(total / 60);
    summary.avg_min = round1(total / finished.length);
    summary.median_min = round1(quantile(sorted, 0.5));
    summary.p90_min = round1(quantile(sorted, 0.9));
    summary.min_min = round1(sorted[0]);
    summary.max_min = round1(sorted[sorted.length - 1]);
    summary.shortest = describe(shortest);
    summary.longest = describe(longest);
    return summary;
  }

  /* Every calendar month between the first and last alert, gaps included, so
     the chart keeps a continuous axis. Mirrors resample("MS"). */
  function byMonth(intervals) {
    if (!intervals.length) return [];
    let lo = Infinity, hi = -Infinity;
    for (const it of intervals) { if (it.month < lo) lo = it.month; if (it.month > hi) hi = it.month; }

    const counts = new Map(), hours = new Map();
    for (const it of intervals) {
      counts.set(it.month, (counts.get(it.month) || 0) + 1);
      if (it.duration !== null) hours.set(it.month, (hours.get(it.month) || 0) + it.duration);
    }

    const [baseY, baseM] = D.baseMonth.split("-").map(Number);
    const out = [];
    for (let m = lo; m <= hi; m++) {
      const total = baseM - 1 + m, y = baseY + Math.floor(total / 12), mm = (total % 12) + 1;
      out.push({
        month: `${y}-${String(mm).padStart(2, "0")}`,
        count: counts.get(m) || 0,
        hours: round1((hours.get(m) || 0) / 60),
      });
    }
    return out;
  }

  function byHour(intervals) {
    const out = new Array(24).fill(0);
    for (const it of intervals) out[it.hour]++;
    return out;
  }

  /* How many alerts covered each child area. Rows with no value for `field`
     were declared for the whole parent, so they cover every child and are
     added to each — see the docstring on stats.ranking. */
  function ranking(rows, children, field, limit) {
    const column = field === "oblast" ? D.oblast : field === "raion" ? D.raion : D.hromada;
    const names = field === "oblast" ? D.oblasts : field === "raion" ? D.raions : D.hromadas;
    const offset = field === "oblast" ? 0 : 1;

    let sharedCount = 0, sharedFinished = 0, sharedMinutes = 0;
    const count = new Map(), finished = new Map(), minutes = new Map();

    for (const i of rows) {
      const value = column[i];
      const duration = D.durations[i] === D.noDuration ? null : D.durations[i] / 60;
      if (field !== "oblast" && value === 0) {
        sharedCount++;
        if (duration !== null) { sharedFinished++; sharedMinutes += duration; }
        continue;
      }
      const name = names[value - offset];
      count.set(name, (count.get(name) || 0) + 1);
      if (duration !== null) {
        finished.set(name, (finished.get(name) || 0) + 1);
        minutes.set(name, (minutes.get(name) || 0) + duration);
      }
    }

    const out = [];
    for (const name of children) {
      const own = count.get(name) || 0;
      const total = own + sharedCount;
      if (!total) continue;
      const mins = (minutes.get(name) || 0) + sharedMinutes;
      const done = (finished.get(name) || 0) + sharedFinished;
      out.push({
        name, count: total, own,
        hours: round1(mins / 60),
        avg_min: done ? round1(mins / done) : null,
      });
    }
    out.sort((a, b) => b.count - a.count);
    return { field, shared: sharedCount, rows: out.slice(0, limit == null ? 15 : limit) };
  }

  /* ---------- the report the page renders ---------- */

  function report(opts) {
    const o = opts || {};
    const oblast = o.oblast || null, raion = o.raion || null, hromada = o.hromada || null;
    const merge = o.merge == null ? oblast !== null : o.merge;
    const standingDays = o.standingDays === undefined ? D.standingDays : o.standingDays;
    const hours = (o.hours || []).slice().sort((a, b) => a - b);
    const hourSet = new Set(hours);

    const rows = selectRows(oblast, raion, hromada, o.start, o.end);
    let intervals = merge ? mergeOverlaps(toIntervals(rows)) : toIntervals(rows);

    const standing = [];
    if (standingDays != null) {
      const kept = [];
      for (const it of intervals) (isStanding(it, standingDays) ? standing : kept).push(it);
      intervals = kept;
    }

    // Built before the hour filter, so the chart keeps showing the whole
    // distribution you are selecting against.
    const hourDistribution = byHour(intervals);
    if (hours.length) intervals = intervals.filter(it => hourSet.has(it.hour));

    let declarations = standingDays == null
      ? rows : rows.filter(i => {
          const d = D.durations[i];   // seconds
          return !(d !== D.noDuration && d >= standingDays * 86400);
        });
    if (hours.length) declarations = declarations.filter(i => hourSet.has(D.hours[i]));

    standing.sort((a, b) => b.duration - a.duration);

    return {
      area: { oblast, raion, hromada },
      period: { start: o.start || null, end: o.end || null },
      mode: merge ? "merged" : "raw",
      hours,
      summary: summarise(intervals),
      declarations: rows.length,
      standing: {
        threshold_days: standingDays,
        count: standing.length,
        hours: round1(standing.reduce((sum, it) => sum + (it.duration || 0), 0) / 60),
        examples: standing.slice(0, 5).map(describe),
      },
      by_month: byMonth(intervals),
      by_hour: hourDistribution,
      // The table shows a top 15; the map needs every child area, so the
      // limit is caller's choice rather than fixed here.
      ranking: ranking(
        declarations,
        childrenOf(oblast, raion),
        raion ? "hromada" : oblast ? "raion" : "oblast",
        o.rankingLimit === undefined ? 15 : o.rankingLimit,
      ),
    };
  }

  root.AlertStats = { load, report, gazetteer, childrenOf, get data() { return D; } };
})(typeof window !== "undefined" ? window : globalThis);
