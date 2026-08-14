/* node worker/live.test.mjs
 *
 * Covers the parts that would fail quietly: the Kyiv-to-UTC conversion across
 * both DST offsets, and the transition folding that turns a stream of
 * snapshots into alert episodes.
 */

import assert from "node:assert/strict";
import { kyivToUtcIso, readSnapshot, applySnapshot, OBLAST_BY_UK } from "./live.mjs";

let passed = 0;
const test = (name, fn) => {
  try { fn(); passed++; console.log(`pass  ${name}`); }
  catch (error) { console.error(`FAIL  ${name}\n        ${error.message}`); process.exitCode = 1; }
};

test("summer timestamps convert at +3 (EEST)", () => {
  assert.equal(kyivToUtcIso("2026-08-14 01:46:30"), "2026-08-13T22:46:30.000Z");
});

test("winter timestamps convert at +2 (EET), not a fixed +3", () => {
  assert.equal(kyivToUtcIso("2026-01-15 10:00:00"), "2026-01-15T08:00:00.000Z");
});

test("missing or unparseable timestamps yield null", () => {
  assert.equal(kyivToUtcIso(null), null);
  assert.equal(kyivToUtcIso("not a date"), null);
});

test("all 25 feed regions map onto oblasts", () => {
  assert.equal(Object.keys(OBLAST_BY_UK).length, 25);
  assert.equal(new Set(Object.values(OBLAST_BY_UK)).size, 25);
});

test("unknown regions are dropped rather than renamed", () => {
  const snap = readSnapshot({
    states: {
      "Львівська область": { alertnow: true, changed: "2026-08-14 10:00:00" },
      "Somewhere new": { alertnow: true, changed: "2026-08-14 10:00:00" },
    },
  });
  assert.deepEqual(Object.keys(snap.states), ["Lvivska oblast"]);
});

const snapshot = (active, changed) => readSnapshot({
  states: { "Львівська область": { alertnow: active, changed } },
  cachedat: "2026-08-14 12:00:00",
});

test("first sighting of a quiet oblast records nothing", () => {
  const { record } = applySnapshot(null, snapshot(false, "2026-08-14 09:00:00"), "2026-08-14T09:05:00.000Z");
  assert.deepEqual(record.episodes, []);
});

test("first sighting of a running alert opens it at its real start", () => {
  // The feed reports when the alert began, so it can be captured in full
  // rather than lost because we happened to start watching mid-alert.
  const { record } = applySnapshot(null, snapshot(true, "2026-08-14 09:00:00"), "2026-08-14T09:05:00.000Z");
  assert.equal(record.episodes.length, 1);
  assert.equal(record.episodes[0].started_at, "2026-08-14T06:00:00.000Z");
  assert.equal(record.episodes[0].finished_at, null);
});

test("an alert first seen running is closed properly when it ends", () => {
  const base = applySnapshot(null, snapshot(true, "2026-08-14 09:00:00"), "2026-08-14T09:05:00.000Z").record;
  const { record } = applySnapshot(base, snapshot(false, "2026-08-14 10:30:00"), "2026-08-14T10:31:00.000Z");
  assert.equal(record.episodes.length, 1);
  assert.equal(record.episodes[0].started_at, "2026-08-14T06:00:00.000Z");
  assert.equal(record.episodes[0].finished_at, "2026-08-14T07:30:00.000Z");
});

test("an off-to-on transition opens an episode at the feed's own time", () => {
  const base = applySnapshot(null, snapshot(false, "2026-08-14 08:00:00"), "2026-08-14T08:01:00.000Z").record;
  const { record } = applySnapshot(base, snapshot(true, "2026-08-14 09:00:00"), "2026-08-14T09:02:00.000Z");

  assert.equal(record.episodes.length, 1);
  // 09:00 Kyiv, not the 09:02 poll time.
  assert.equal(record.episodes[0].started_at, "2026-08-14T06:00:00.000Z");
  assert.equal(record.episodes[0].finished_at, null);
});

test("an on-to-off transition closes the open episode", () => {
  let state = applySnapshot(null, snapshot(false, "2026-08-14 08:00:00"), "2026-08-14T08:01:00.000Z").record;
  state = applySnapshot(state, snapshot(true, "2026-08-14 09:00:00"), "2026-08-14T09:02:00.000Z").record;
  const { record } = applySnapshot(state, snapshot(false, "2026-08-14 10:30:00"), "2026-08-14T10:31:00.000Z");

  assert.equal(record.episodes.length, 1);
  assert.equal(record.episodes[0].finished_at, "2026-08-14T07:30:00.000Z");
});

test("an unchanged snapshot reports no change and adds nothing", () => {
  const base = applySnapshot(null, snapshot(true, "2026-08-14 09:00:00"), "2026-08-14T09:05:00.000Z").record;
  const next = applySnapshot(base, snapshot(true, "2026-08-14 09:00:00"), "2026-08-14T09:07:00.000Z");

  assert.equal(next.changed, false);
  assert.deepEqual(next.record.episodes, base.episodes);
});

test("repeated cycles accumulate separate episodes", () => {
  let state = applySnapshot(null, snapshot(false, "2026-08-14 08:00:00"), "2026-08-14T08:01:00.000Z").record;
  for (const [active, at] of [[true, "09:00"], [false, "09:40"], [true, "11:00"], [false, "11:20"]]) {
    state = applySnapshot(state, snapshot(active, `2026-08-14 ${at}:00`), `2026-08-14T${at}:30.000Z`).record;
  }
  assert.equal(state.episodes.length, 2);
  assert.ok(state.episodes.every(e => e.finished_at));
});

test("finished episodes older than a week are pruned, open ones are kept", () => {
  const previous = {
    states: { "Lvivska oblast": { active: false, since: "2026-08-01T00:00:00.000Z" } },
    episodes: [
      { oblast: "Odeska oblast", started_at: "2026-07-01T00:00:00.000Z", finished_at: "2026-07-01T01:00:00.000Z" },
      { oblast: "Luhanska oblast", started_at: "2022-04-04T16:45:39.000Z", finished_at: null },
    ],
  };
  const { record } = applySnapshot(previous, snapshot(false, "2026-08-14 08:00:00"), "2026-08-14T08:01:00.000Z");

  assert.deepEqual(record.episodes.map(e => e.oblast), ["Luhanska oblast"]);
});

console.log(`\n${passed} passed`);
