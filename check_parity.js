/* Headless version of web/parity.html, for CI.
 *
 *   node check_parity.js
 *
 * Loads the real web/stats.js, replays every scenario from parity.py and
 * exits non-zero on the first disagreement, so a change that makes the
 * browser diverge from the Python reference fails the build instead of
 * shipping wrong numbers.
 */
"use strict";

const fs = require("fs");
const path = require("path");

const ROOT = __dirname;
const DATA = path.join(ROOT, "web", "data");
const TOLERANCE = 1e-6;

// The browser file is loaded as-is, so this checks the code that actually
// ships. It has no exports; running it attaches AlertStats to globalThis.
require("./web/stats.js");
const { AlertStats } = globalThis;

const meta = JSON.parse(fs.readFileSync(path.join(DATA, "meta.json"), "utf8"));
const cases = JSON.parse(fs.readFileSync(path.join(DATA, "parity.json"), "utf8"));
const bytes = fs.readFileSync(path.join(DATA, "alerts.bin"));
const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);

AlertStats.load(meta, buffer);

function diff(expected, actual, at, out) {
  if (expected === null || expected === undefined) {
    if (actual !== null && actual !== undefined) out.push(`${at}: expected null, got ${actual}`);
  } else if (typeof expected === "number") {
    if (typeof actual !== "number" || Math.abs(expected - actual) > TOLERANCE) {
      out.push(`${at}: ${expected} vs ${actual}`);
    }
  } else if (typeof expected === "string" || typeof expected === "boolean") {
    if (expected !== actual) out.push(`${at}: "${expected}" vs "${actual}"`);
  } else if (Array.isArray(expected)) {
    if (!Array.isArray(actual)) out.push(`${at}: not an array`);
    else if (expected.length !== actual.length) out.push(`${at}: length ${expected.length} vs ${actual.length}`);
    else expected.forEach((value, i) => diff(value, actual[i], `${at}[${i}]`, out));
  } else {
    for (const key of Object.keys(expected)) {
      diff(expected[key], actual ? actual[key] : undefined, at ? `${at}.${key}` : key, out);
    }
  }
}

// `period` is skipped: Python reports ISO timestamps, the page keeps the
// YYYY-MM-DD the user picked. Every other field must agree.
const COMPARED = ["mode", "hours", "area", "summary", "declarations", "standing", "by_month", "by_hour", "ranking"];

let failed = 0;
for (const { label, query, expected } of cases) {
  const actual = AlertStats.report({
    oblast: query.oblast, raion: query.raion, hromada: query.hromada,
    start: query.start, end: query.end,
    merge: query.merge === undefined ? null : query.merge,
    standingDays: "standing_days" in query ? query.standing_days : undefined,
    hours: query.hours || [],
  });

  const problems = [];
  for (const key of COMPARED) diff(expected[key], actual[key], key, problems);

  if (problems.length) {
    failed++;
    console.error(`FAIL  ${label}`);
    for (const problem of problems.slice(0, 10)) console.error(`        ${problem}`);
  } else {
    console.log(`pass  ${label}`);
  }
}

console.log(`\n${cases.length - failed} / ${cases.length} scenarios match`);
process.exit(failed ? 1 : 0);
