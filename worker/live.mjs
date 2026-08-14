/* Pure logic for the live recorder, kept out of the Worker entry point so it
 * can be unit tested under plain Node.
 *
 * Why this exists: the upstream dataset is rebuilt once a day, but alerts
 * happen all day. Between rebuilds the page would be missing everything that
 * has happened since — and no free API hands you "the last 24 hours of alerts"
 * ready made. What is available is the *current* state per oblast plus the
 * moment it last changed, so this derives episodes by watching that change.
 *
 * The upstream feed stays the source of record. This layer only covers the
 * window the dataset has not caught up with yet, and only at oblast level,
 * which is all the free source reports.
 */

export const SOURCE_URL = "https://ubilling.net.ua/aerialalerts/";

/* The feed names regions in Ukrainian; the packed dataset uses the English
   transliterations. Every one of the 25 maps onto an oblast we already know. */
export const OBLAST_BY_UK = {
  "Вінницька область": "Vinnytska oblast",
  "Волинська область": "Volynska oblast",
  "Дніпропетровська область": "Dnipropetrovska oblast",
  "Донецька область": "Donetska oblast",
  "Житомирська область": "Zhytomyrska oblast",
  "Закарпатська область": "Zakarpatska oblast",
  "Запорізька область": "Zaporizka oblast",
  "Івано-Франківська область": "Ivano-Frankivska oblast",
  "Київська область": "Kyivska oblast",
  "Кіровоградська область": "Kirovohradska oblast",
  "Луганська область": "Luhanska oblast",
  "Львівська область": "Lvivska oblast",
  "Миколаївська область": "Mykolaivska oblast",
  "Одеська область": "Odeska oblast",
  "Полтавська область": "Poltavska oblast",
  "Рівненська область": "Rivnenska oblast",
  "Сумська область": "Sumska oblast",
  "Тернопільська область": "Ternopilska oblast",
  "Харківська область": "Kharkivska oblast",
  "Херсонська область": "Khersonska oblast",
  "Хмельницька область": "Khmelnytska oblast",
  "Черкаська область": "Cherkaska oblast",
  "Чернівецька область": "Chernivetska oblast",
  "Чернігівська область": "Chernihivska oblast",
  "м. Київ": "Kyiv City",
};

const KYIV = "Europe/Kyiv";
const PART = new Intl.DateTimeFormat("en-US", {
  timeZone: KYIV, hour12: false,
  year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit", second: "2-digit",
});

/* The feed stamps times in Kyiv local time with no offset attached. Convert by
   measuring the zone's offset at that instant, so both EET and EEST are handled
   rather than a fixed +3 that would be an hour out all winter. */
export function kyivToUtcIso(naive) {
  if (!naive) return null;
  const asIfUtc = new Date(`${naive.replace(" ", "T")}Z`);
  if (Number.isNaN(asIfUtc.getTime())) return null;

  const parts = {};
  for (const { type, value } of PART.formatToParts(asIfUtc)) parts[type] = value;
  const shifted = Date.UTC(
    +parts.year, +parts.month - 1, +parts.day,
    +parts.hour % 24, +parts.minute, +parts.second,
  );
  return new Date(asIfUtc.getTime() - (shifted - asIfUtc.getTime())).toISOString();
}

/* Normalise one feed response into { oblast: { active, since } }, dropping any
   region we cannot map rather than inventing a name for it. */
export function readSnapshot(payload) {
  const states = {};
  for (const [ukrainian, value] of Object.entries(payload?.states ?? {})) {
    const oblast = OBLAST_BY_UK[ukrainian];
    if (!oblast) continue;
    states[oblast] = { active: Boolean(value.alertnow), since: kyivToUtcIso(value.changed) };
  }
  return { states, cachedAt: kyivToUtcIso(payload?.cachedat) };
}

/* Fold a new snapshot into the recorded log.
 *
 * Transitions are timestamped with the feed's own `changed` value rather than
 * the moment we polled, so an episode keeps its real start and end even though
 * we only look every couple of minutes.
 */
export function applySnapshot(previous, snapshot, now = new Date().toISOString()) {
  const episodes = (previous?.episodes ?? []).map(e => ({ ...e }));
  const before = previous?.states ?? {};
  let changed = false;

  for (const [oblast, state] of Object.entries(snapshot.states)) {
    const was = before[oblast];
    if (!was) {
      // First sighting. An alert already running is still worth opening: the
      // feed reports when it started, so the episode can be recorded in full
      // and closed later rather than being missed entirely. Consumers drop
      // anything the packed dataset already covers.
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
      checkedAt: now,
    },
  };
}

function lastOpenFor(episodes, oblast) {
  for (let i = episodes.length - 1; i >= 0; i--) {
    if (episodes[i].oblast === oblast && !episodes[i].finished_at) return episodes[i];
  }
  return null;
}

/* Keep a week. The packed dataset overtakes this within a day, so anything
   older is redundant, and an unbounded list would eventually outgrow the value
   size limit. Open episodes are always kept — Luhansk has had one running
   since 2022 and dropping it would strand it forever. */
const KEEP_MS = 7 * 24 * 60 * 60 * 1000;

function prune(episodes, now) {
  const cutoff = Date.parse(now) - KEEP_MS;
  return episodes.filter(e => !e.finished_at || Date.parse(e.finished_at) >= cutoff);
}
