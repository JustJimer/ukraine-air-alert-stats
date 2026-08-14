/* Cloudflare Worker: serves the static site and records live alerts.
 *
 * The site itself is still static assets. This adds two things the packed
 * dataset cannot provide on its own:
 *
 *   scheduled()  polls the alert feed and records oblast-level transitions,
 *                covering the window since the dataset was last rebuilt.
 *   /api/live    hands that record to the page.
 *
 * State lives in one KV key, written only when something actually changed (or
 * every half hour as a heartbeat), because KV's free tier allows far fewer
 * writes per day than this cron has ticks.
 */

import { SOURCE_URL, readSnapshot, applySnapshot } from "./live.mjs";

const KEY = "live";
const HEARTBEAT_MS = 30 * 60 * 1000;

async function poll(env) {
  const response = await fetch(SOURCE_URL, {
    headers: { "User-Agent": "ukraine-air-alert-stats (github.com/JustJimer)" },
    cf: { cacheTtl: 30, cacheEverything: true },
  });
  if (!response.ok) throw new Error(`feed responded ${response.status}`);

  const snapshot = readSnapshot(await response.json());
  if (!Object.keys(snapshot.states).length) throw new Error("feed returned no known regions");

  const previous = await env.ALERTS.get(KEY, "json");
  const { changed, record } = applySnapshot(previous, snapshot);

  const stale = !previous?.checkedAt || Date.now() - Date.parse(previous.checkedAt) > HEARTBEAT_MS;
  if (changed || stale) await env.ALERTS.put(KEY, JSON.stringify(record));

  return record;
}

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "public, max-age=60",
      "Access-Control-Allow-Origin": "*",
    },
  });

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(poll(env));
  },

  async fetch(request, env) {
    const { pathname } = new URL(request.url);

    if (pathname === "/api/live") {
      const record = await env.ALERTS.get(KEY, "json");
      // Absent only before the first cron tick has run.
      if (!record) return json({ states: {}, episodes: [], checkedAt: null, warming_up: true });
      return json(record);
    }

    // Everything else is the static site.
    return env.ASSETS.fetch(request);
  },
};
