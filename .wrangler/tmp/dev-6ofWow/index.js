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
var worker_default = {
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

// node_modules/wrangler/templates/middleware/middleware-ensure-req-body-drained.ts
var drainBody = /* @__PURE__ */ __name(async (request, env, _ctx, middlewareCtx) => {
  try {
    return await middlewareCtx.next(request, env);
  } finally {
    try {
      if (request.body !== null && !request.bodyUsed) {
        const reader = request.body.getReader();
        while (!(await reader.read()).done) {
        }
      }
    } catch (e) {
      console.error("Failed to drain the unused request body.", e);
    }
  }
}, "drainBody");
var middleware_ensure_req_body_drained_default = drainBody;

// node_modules/wrangler/templates/middleware/middleware-scheduled.ts
var scheduled = /* @__PURE__ */ __name(async (request, env, _ctx, middlewareCtx) => {
  const url = new URL(request.url);
  if (url.pathname === "/__scheduled") {
    const cron = url.searchParams.get("cron") ?? "";
    await middlewareCtx.dispatch("scheduled", { cron });
    return new Response("Ran scheduled event");
  }
  const resp = await middlewareCtx.next(request, env);
  if (request.headers.get("referer")?.endsWith("/__scheduled") && url.pathname === "/favicon.ico" && resp.status === 500) {
    return new Response(null, { status: 404 });
  }
  return resp;
}, "scheduled");
var middleware_scheduled_default = scheduled;

// node_modules/wrangler/templates/middleware/middleware-miniflare3-json-error.ts
function reduceError(e) {
  return {
    name: e?.name,
    message: e?.message ?? String(e),
    stack: e?.stack,
    cause: e?.cause === void 0 ? void 0 : reduceError(e.cause)
  };
}
__name(reduceError, "reduceError");
var jsonError = /* @__PURE__ */ __name(async (request, env, _ctx, middlewareCtx) => {
  try {
    return await middlewareCtx.next(request, env);
  } catch (e) {
    const error = reduceError(e);
    const body = JSON.stringify(error);
    const headers = {
      "Content-Type": "application/json",
      "MF-Experimental-Error-Stack": "true"
    };
    const encoded = encodeURIComponent(body);
    if (encoded.length <= 8192) {
      headers["MF-Experimental-Error-Stack-Payload"] = encoded;
    }
    return new Response(body, { status: 500, headers });
  }
}, "jsonError");
var middleware_miniflare3_json_error_default = jsonError;

// .wrangler/tmp/bundle-CsCQY9/middleware-insertion-facade.js
var __INTERNAL_WRANGLER_MIDDLEWARE__ = [
  middleware_ensure_req_body_drained_default,
  middleware_scheduled_default,
  middleware_miniflare3_json_error_default
];
var middleware_insertion_facade_default = worker_default;

// node_modules/wrangler/templates/middleware/common.ts
var __facade_middleware__ = [];
function __facade_register__(...args) {
  __facade_middleware__.push(...args.flat());
}
__name(__facade_register__, "__facade_register__");
function __facade_invokeChain__(request, env, ctx, dispatch, middlewareChain) {
  const [head, ...tail] = middlewareChain;
  const middlewareCtx = {
    dispatch,
    next(newRequest, newEnv) {
      return __facade_invokeChain__(newRequest, newEnv, ctx, dispatch, tail);
    }
  };
  return head(request, env, ctx, middlewareCtx);
}
__name(__facade_invokeChain__, "__facade_invokeChain__");
function __facade_invoke__(request, env, ctx, dispatch, finalMiddleware) {
  return __facade_invokeChain__(request, env, ctx, dispatch, [
    ...__facade_middleware__,
    finalMiddleware
  ]);
}
__name(__facade_invoke__, "__facade_invoke__");

// .wrangler/tmp/bundle-CsCQY9/middleware-loader.entry.ts
var __Facade_ScheduledController__ = class ___Facade_ScheduledController__ {
  constructor(scheduledTime, cron, noRetry) {
    this.scheduledTime = scheduledTime;
    this.cron = cron;
    this.#noRetry = noRetry;
  }
  scheduledTime;
  cron;
  static {
    __name(this, "__Facade_ScheduledController__");
  }
  #noRetry;
  noRetry() {
    if (!(this instanceof ___Facade_ScheduledController__)) {
      throw new TypeError("Illegal invocation");
    }
    this.#noRetry();
  }
};
function wrapExportedHandler(worker) {
  if (__INTERNAL_WRANGLER_MIDDLEWARE__ === void 0 || __INTERNAL_WRANGLER_MIDDLEWARE__.length === 0) {
    return worker;
  }
  for (const middleware of __INTERNAL_WRANGLER_MIDDLEWARE__) {
    __facade_register__(middleware);
  }
  const fetchDispatcher = /* @__PURE__ */ __name(function(request, env, ctx) {
    if (worker.fetch === void 0) {
      throw new Error("Handler does not export a fetch() function.");
    }
    return worker.fetch(request, env, ctx);
  }, "fetchDispatcher");
  return {
    ...worker,
    fetch(request, env, ctx) {
      const dispatcher = /* @__PURE__ */ __name(function(type, init) {
        if (type === "scheduled" && worker.scheduled !== void 0) {
          const controller = new __Facade_ScheduledController__(
            Date.now(),
            init.cron ?? "",
            () => {
            }
          );
          return worker.scheduled(controller, env, ctx);
        }
      }, "dispatcher");
      return __facade_invoke__(request, env, ctx, dispatcher, fetchDispatcher);
    }
  };
}
__name(wrapExportedHandler, "wrapExportedHandler");
function wrapWorkerEntrypoint(klass) {
  if (__INTERNAL_WRANGLER_MIDDLEWARE__ === void 0 || __INTERNAL_WRANGLER_MIDDLEWARE__.length === 0) {
    return klass;
  }
  for (const middleware of __INTERNAL_WRANGLER_MIDDLEWARE__) {
    __facade_register__(middleware);
  }
  return class extends klass {
    #fetchDispatcher = /* @__PURE__ */ __name((request, env, ctx) => {
      this.env = env;
      this.ctx = ctx;
      if (super.fetch === void 0) {
        throw new Error("Entrypoint class does not define a fetch() function.");
      }
      return super.fetch(request);
    }, "#fetchDispatcher");
    #dispatcher = /* @__PURE__ */ __name((type, init) => {
      if (type === "scheduled" && super.scheduled !== void 0) {
        const controller = new __Facade_ScheduledController__(
          Date.now(),
          init.cron ?? "",
          () => {
          }
        );
        return super.scheduled(controller);
      }
    }, "#dispatcher");
    fetch(request) {
      return __facade_invoke__(
        request,
        this.env,
        this.ctx,
        this.#dispatcher,
        this.#fetchDispatcher
      );
    }
  };
}
__name(wrapWorkerEntrypoint, "wrapWorkerEntrypoint");
var WRAPPED_ENTRY;
if (typeof middleware_insertion_facade_default === "object") {
  WRAPPED_ENTRY = wrapExportedHandler(middleware_insertion_facade_default);
} else if (typeof middleware_insertion_facade_default === "function") {
  WRAPPED_ENTRY = wrapWorkerEntrypoint(middleware_insertion_facade_default);
}
var middleware_loader_entry_default = WRAPPED_ENTRY;
export {
  __INTERNAL_WRANGLER_MIDDLEWARE__,
  middleware_loader_entry_default as default
};
//# sourceMappingURL=index.js.map
