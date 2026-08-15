var __defProp = Object.defineProperty;
var __name = (target, value) => __defProp(target, "name", { value, configurable: true });

// worker/live.mjs
var SOURCE_URL = "https://ubilling.net.ua/aerialalerts/";
var OBLAST_BY_UK = {
  "\u0412\u0456\u043D\u043D\u0438\u0446\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Vinnytska oblast",
  "\u0412\u043E\u043B\u0438\u043D\u0441\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Volynska oblast",
  "\u0414\u043D\u0456\u043F\u0440\u043E\u043F\u0435\u0442\u0440\u043E\u0432\u0441\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Dnipropetrovska oblast",
  "\u0414\u043E\u043D\u0435\u0446\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Donetska oblast",
  "\u0416\u0438\u0442\u043E\u043C\u0438\u0440\u0441\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Zhytomyrska oblast",
  "\u0417\u0430\u043A\u0430\u0440\u043F\u0430\u0442\u0441\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Zakarpatska oblast",
  "\u0417\u0430\u043F\u043E\u0440\u0456\u0437\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Zaporizka oblast",
  "\u0406\u0432\u0430\u043D\u043E-\u0424\u0440\u0430\u043D\u043A\u0456\u0432\u0441\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Ivano-Frankivska oblast",
  "\u041A\u0438\u0457\u0432\u0441\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Kyivska oblast",
  "\u041A\u0456\u0440\u043E\u0432\u043E\u0433\u0440\u0430\u0434\u0441\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Kirovohradska oblast",
  "\u041B\u0443\u0433\u0430\u043D\u0441\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Luhanska oblast",
  "\u041B\u044C\u0432\u0456\u0432\u0441\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Lvivska oblast",
  "\u041C\u0438\u043A\u043E\u043B\u0430\u0457\u0432\u0441\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Mykolaivska oblast",
  "\u041E\u0434\u0435\u0441\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Odeska oblast",
  "\u041F\u043E\u043B\u0442\u0430\u0432\u0441\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Poltavska oblast",
  "\u0420\u0456\u0432\u043D\u0435\u043D\u0441\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Rivnenska oblast",
  "\u0421\u0443\u043C\u0441\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Sumska oblast",
  "\u0422\u0435\u0440\u043D\u043E\u043F\u0456\u043B\u044C\u0441\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Ternopilska oblast",
  "\u0425\u0430\u0440\u043A\u0456\u0432\u0441\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Kharkivska oblast",
  "\u0425\u0435\u0440\u0441\u043E\u043D\u0441\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Khersonska oblast",
  "\u0425\u043C\u0435\u043B\u044C\u043D\u0438\u0446\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Khmelnytska oblast",
  "\u0427\u0435\u0440\u043A\u0430\u0441\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Cherkaska oblast",
  "\u0427\u0435\u0440\u043D\u0456\u0432\u0435\u0446\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Chernivetska oblast",
  "\u0427\u0435\u0440\u043D\u0456\u0433\u0456\u0432\u0441\u044C\u043A\u0430 \u043E\u0431\u043B\u0430\u0441\u0442\u044C": "Chernihivska oblast",
  "\u043C. \u041A\u0438\u0457\u0432": "Kyiv City"
};
var KYIV = "Europe/Kyiv";
var PART = new Intl.DateTimeFormat("en-US", {
  timeZone: KYIV,
  hour12: false,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit"
});
function kyivToUtcIso(naive) {
  if (!naive) return null;
  const asIfUtc = /* @__PURE__ */ new Date(`${naive.replace(" ", "T")}Z`);
  if (Number.isNaN(asIfUtc.getTime())) return null;
  const parts = {};
  for (const { type, value } of PART.formatToParts(asIfUtc)) parts[type] = value;
  const shifted = Date.UTC(
    +parts.year,
    +parts.month - 1,
    +parts.day,
    +parts.hour % 24,
    +parts.minute,
    +parts.second
  );
  return new Date(asIfUtc.getTime() - (shifted - asIfUtc.getTime())).toISOString();
}
__name(kyivToUtcIso, "kyivToUtcIso");
function readSnapshot(payload) {
  const states = {};
  for (const [ukrainian, value] of Object.entries(payload?.states ?? {})) {
    const oblast = OBLAST_BY_UK[ukrainian];
    if (!oblast) continue;
    states[oblast] = { active: Boolean(value.alertnow), since: kyivToUtcIso(value.changed) };
  }
  return { states, cachedAt: kyivToUtcIso(payload?.cachedat) };
}
__name(readSnapshot, "readSnapshot");
function applySnapshot(previous, snapshot, now = (/* @__PURE__ */ new Date()).toISOString()) {
  const episodes = (previous?.episodes ?? []).map((e) => ({ ...e }));
  const before = previous?.states ?? {};
  let changed = false;
  for (const [oblast, state] of Object.entries(snapshot.states)) {
    const was = before[oblast];
    if (!was) {
      changed = true;
      if (state.active) episodes.push({ oblast, started_at: state.since ?? now, finished_at: null });
      continue;
    }
    if (was.active === state.active) continue;
    changed = true;
    if (state.active) {
      episodes.push({ oblast, started_at: state.since ?? now, finished_at: null });
    } else {
      const open = lastOpenFor(episodes, oblast);
      if (open) open.finished_at = state.since ?? now;
    }
  }
  return {
    changed,
    record: {
      states: snapshot.states,
      episodes: prune(episodes, now),
      cachedAt: snapshot.cachedAt,
      checkedAt: now
    }
  };
}
__name(applySnapshot, "applySnapshot");
function lastOpenFor(episodes, oblast) {
  for (let i = episodes.length - 1; i >= 0; i--) {
    if (episodes[i].oblast === oblast && !episodes[i].finished_at) return episodes[i];
  }
  return null;
}
__name(lastOpenFor, "lastOpenFor");
var KEEP_MS = 7 * 24 * 60 * 60 * 1e3;
function prune(episodes, now) {
  const cutoff = Date.parse(now) - KEEP_MS;
  return episodes.filter((e) => !e.finished_at || Date.parse(e.finished_at) >= cutoff);
}
__name(prune, "prune");

// worker/index.js
var KEY = "live";
var HEARTBEAT_MS = 30 * 60 * 1e3;
async function poll(env) {
  const response = await fetch(SOURCE_URL, {
    headers: { "User-Agent": "ukraine-air-alert-stats (github.com/JustJimer)" },
    cf: { cacheTtl: 30, cacheEverything: true }
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
__name(poll, "poll");
var json = /* @__PURE__ */ __name((body, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "public, max-age=60",
    "Access-Control-Allow-Origin": "*"
  }
}), "json");
var index_default = {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(poll(env));
  },
  async fetch(request, env) {
    const { pathname } = new URL(request.url);
    if (pathname === "/api/live") {
      const record = await env.ALERTS.get(KEY, "json");
      if (!record) return json({ states: {}, episodes: [], checkedAt: null, warming_up: true });
      return json(record);
    }
    return env.ASSETS.fetch(request);
  }
};
export {
  index_default as default
};
//# sourceMappingURL=index.js.map
