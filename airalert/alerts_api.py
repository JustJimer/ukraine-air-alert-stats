"""Client for the alerts.in.ua API.

The official dataset this project was built on stopped on 2026-09-07, when
Ukraine split air alerts into yellow and red levels (CabMin resolution 1092,
in force from 6 September) and the message format its parser reads changed
with it. This is the replacement source: it carries `alert_level`, the
individual `threats` behind an alert, and locations down to hromada.

Two endpoints matter:

  history(uid)  one month back for one region. Rate limited to 2 requests a
                minute, so a full sweep of the 27 regions takes about a
                quarter of an hour. Because every run re-reads a whole month,
                the archive repairs itself: a week of failed runs costs
                nothing as long as one run lands within the month.

  active()      everything currently on, in one request. The levels are
                documented as always present here and only sometimes in
                history, so this is the fallback for filling them in.

Needs a token from https://devs.alerts.in.ua in ALERTS_IN_UA_TOKEN.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

BASE = "https://api.alerts.in.ua/v1"

TOKEN_ENV = "ALERTS_IN_UA_TOKEN"

# Published in the API docs. Numbering is theirs and is not contiguous.
OBLAST_UIDS = {
    3: "Хмельницька область", 4: "Вінницька область", 5: "Рівненська область",
    8: "Волинська область", 9: "Дніпропетровська область", 10: "Житомирська область",
    11: "Закарпатська область", 12: "Запорізька область", 13: "Івано-Франківська область",
    14: "Київська область", 15: "Кіровоградська область", 16: "Луганська область",
    17: "Миколаївська область", 18: "Одеська область", 19: "Полтавська область",
    20: "Сумська область", 21: "Тернопільська область", 22: "Харківська область",
    23: "Херсонська область", 24: "Черкаська область", 25: "Чернігівська область",
    26: "Чернівецька область", 27: "Львівська область", 28: "Донецька область",
    29: "Автономна Республіка Крим", 30: "м. Севастополь", 31: "м. Київ",
}

# Transliteration turns "Луганська область" into "Luhanska oblast" and
# "Бахмутський район" into "Bakhmutskyi raion", which is exactly how the
# dataset names them. These three do not follow that pattern: the dataset
# calls them by name rather than by the "м." prefix the API uses.
NAME_OVERRIDES = {
    "м. Київ": "Kyiv City",
    "м. Севастополь": "Sevastopol",
    "Автономна Республіка Крим": "Avtonomna Respublika Krym",
}

# The API reports a city's oblast but never its raion, so without this a query
# for Kharkivskyi raion would miss every alert for Kharkiv the city sitting
# inside it. Seven cities appear in the feed; each raion here was read out of
# the same boundary source the map uses, by looking up the city's own "міська
# громада" — not matched by name, because "Криворізька сільська громада" is a
# different place in Donetska oblast entirely.
CITY_RAION = {
    "м. Харків": "Харківський район",
    "м. Світловодськ": "Олександрійський район",
    "м. Кривий Ріг": "Криворізький район",
    "м. Запоріжжя": "Запорізький район",
    "м. Нікополь": "Нікопольський район",
    "м. Дніпро": "Дніпровський район",
    "м. Марганець": "Нікопольський район",
}

HISTORY_INTERVAL = 31.0   # seconds between history calls; the limit is 2/min
GENERAL_INTERVAL = 7.0    # the soft limit elsewhere is 8-10/min


class AlertsApiError(RuntimeError):
    pass


class AlertsApi:
    def __init__(self, token: str | None = None, *, pause=time.sleep):
        self.token = token or os.environ.get(TOKEN_ENV, "")
        if not self.token:
            raise AlertsApiError(
                f"no API token — set {TOKEN_ENV} (apply at https://devs.alerts.in.ua)"
            )
        self._pause = pause
        self._next_allowed = 0.0

    def _get(self, path: str, interval: float) -> dict:
        wait = self._next_allowed - time.monotonic()
        if wait > 0:
            self._pause(wait)

        request = urllib.request.Request(
            f"{BASE}/{path}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                # Asked for by the docs so they can tell clients apart.
                "User-Agent": "ukraine-air-alert-stats (github.com/JustJimer)",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            # 429 is the one worth naming: it means the pacing below is wrong
            # rather than that anything is broken.
            detail = {
                401: "token missing, wrong, revoked or expired",
                403: "IP blocked, or the API is not available from this country",
                429: "rate limit exceeded — the pacing in this client is too fast",
            }.get(error.code, error.reason)
            raise AlertsApiError(f"{path}: HTTP {error.code} — {detail}") from error
        finally:
            self._next_allowed = time.monotonic() + interval

        return payload

    def history(self, uid: int, period: str = "month_ago") -> list[dict]:
        """Alerts for one region over the period. Only month_ago is supported."""
        return self._get(f"regions/{uid}/alerts/{period}.json", HISTORY_INTERVAL).get("alerts", [])

    def active(self) -> list[dict]:
        return self._get("alerts/active.json", GENERAL_INTERVAL).get("alerts", [])


def area_names(alert: dict) -> tuple[str | None, str | None, str | None]:
    """Map one API alert onto the dataset's (oblast, raion, hromada) columns.

    The API names the alert's own location in `location_title` and its parents
    in `location_oblast` / `location_raion`, so which column `location_title`
    belongs in depends on `location_type`.
    """
    from airalert.geo import translit

    def name(value: str | None) -> str | None:
        if not value:
            return None
        return NAME_OVERRIDES.get(value) or translit(value)

    kind = alert.get("location_type")
    oblast_raw = alert.get("location_oblast")
    oblast = name(oblast_raw)
    title = alert.get("location_title")

    if kind == "raion":
        return oblast, name(title), None
    if kind == "hromada":
        return oblast, name(alert.get("location_raion")), name(title)
    if kind == "oblast" or title == oblast_raw:
        return oblast or name(title), None, None

    # A city, and anything unrecognised that is not the oblast itself: an area
    # inside the oblast, finer than a raion. It goes in the hromada column,
    # never the oblast one. An oblast-level row is read as covering every raion
    # beneath it, so filing "м. Харків" there would have counted a city alert
    # against all seven Kharkiv raions — and there are 280 such records for
    # that oblast in a single month.
    #
    # The raion comes from CITY_RAION, since the API does not give one. A city
    # missing from that table keeps an empty raion, which is the old behaviour:
    # worse, but not wrong, and sync_live reports it so it can be added.
    return oblast, name(CITY_RAION.get(title)), (city_name(title) if kind == "city" else name(title))


def city_name(title: str | None) -> str | None:
    """"м. Харків" -> "Kharkiv city", matching how Kyiv City already reads.

    Only for the city type: an unrecognised type keeps its plain name, since
    calling it a city would be inventing something the API did not say.
    """
    if not title:
        return None
    from airalert.geo import translit

    bare = title.removeprefix("м. ").strip()
    return f"{translit(bare)} city"
