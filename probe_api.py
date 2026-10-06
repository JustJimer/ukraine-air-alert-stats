"""Ask the live API what it actually returns, before anything is built on it.

The documentation leaves three things open, and each one changes the design:

  * is `alert_level` present on historical alerts, or only on active ones?
    The documented history example has no level at all — but that example is
    an alert from 2022, years before levels existed, so it settles nothing.
  * does asking for an oblast's history also return the raion and hromada
    alerts inside it, or only oblast-wide ones? Raion granularity is the
    whole reason for preferring this source over the volunteer feed.
  * how far back does "month_ago" really reach?

    python probe_api.py            # names check only, no token needed
    python probe_api.py --live     # the above plus three real API calls

Reports; writes nothing.
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from airalert import alerts_api

META = Path(__file__).resolve().parent / "web" / "data" / "meta.json"

# Two busy oblasts and one quiet one, so the sample is not all frontline.
SAMPLE_UIDS = [22, 31, 27]   # Kharkivska, Kyiv City, Lvivska


def check_names() -> bool:
    """Do the API's region names map onto the gazetteer? No token needed."""
    print("== region names ==")
    if not META.exists():
        print("  web/data/meta.json missing — run build.py first")
        return False

    known = set(json.loads(META.read_text(encoding="utf-8"))["oblasts"])
    bad = []
    for uid, ukrainian in sorted(alerts_api.OBLAST_UIDS.items()):
        alert = {"location_type": "oblast", "location_title": ukrainian,
                 "location_oblast": ukrainian}
        mapped = alerts_api.area_names(alert)[0]
        ok = mapped in known
        # Crimea and Sevastopol are not in the dataset and are not expected to be.
        expected_absent = ukrainian in ("Автономна Республіка Крим", "м. Севастополь")
        flag = "ok " if ok else ("n/a" if expected_absent else "MISS")
        if not ok and not expected_absent:
            bad.append((ukrainian, mapped))
        print(f"  {uid:>2} {flag} {ukrainian:<28} -> {mapped}")

    print(f"  {len(alerts_api.OBLAST_UIDS) - len(bad)}/{len(alerts_api.OBLAST_UIDS)} usable")
    return not bad


def describe(alerts: list[dict], label: str) -> None:
    print(f"\n-- {label}: {len(alerts)} alerts --")
    if not alerts:
        print("   (none)")
        return

    fields = collections.Counter()
    for a in alerts:
        fields.update(a.keys())
    print("   fields seen (count of alerts carrying each):")
    for key, n in fields.most_common():
        print(f"     {key:<22} {n}")

    for key in ("location_type", "alert_level", "alert_type"):
        values = collections.Counter(a.get(key, "<absent>") for a in alerts)
        print(f"   {key}: {dict(values)}")

    starts = sorted(a["started_at"] for a in alerts if a.get("started_at"))
    if starts:
        print(f"   started_at range: {starts[0]} .. {starts[-1]}")

    with_threats = [a for a in alerts if a.get("threats")]
    print(f"   alerts carrying threats: {len(with_threats)}")
    if with_threats:
        print("   example threat:", json.dumps(with_threats[0]["threats"][0], ensure_ascii=False))

    # One example of each location_type, because how location_title relates to
    # location_oblast / location_raion depends on it, and a city sitting inside
    # an oblast is the case most likely to be mapped into the wrong column.
    seen = {}
    for a in alerts:
        seen.setdefault(a.get("location_type"), a)
    for kind, a in sorted(seen.items(), key=lambda kv: str(kv[0])):
        print(f"   [{kind}] title={a.get('location_title')!r} oblast={a.get('location_oblast')!r} "
              f"raion={a.get('location_raion')!r} uid={a.get('location_uid')!r}")
        print(f"        -> {alerts_api.area_names(a)}")

    ongoing = sum(1 for a in alerts if not a.get("finished_at"))
    closed = sorted(a["started_at"] for a in alerts if a.get("finished_at"))
    print(f"   ongoing (no finished_at): {ongoing}")
    if closed:
        print(f"   earliest *closed* alert : {closed[0]}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="make real API calls")
    args = parser.parse_args()

    names_ok = check_names()
    if not args.live:
        print("\n(names only — pass --live to query the API)")
        return 0 if names_ok else 1

    api = alerts_api.AlertsApi()
    describe(api.active(), "active now")

    for uid in SAMPLE_UIDS:
        alerts = api.history(uid)
        describe(alerts, f"history uid={uid} ({alerts_api.OBLAST_UIDS[uid]})")

        levelled = sum(1 for a in alerts if a.get("alert_level"))
        deep = sum(1 for a in alerts if a.get("location_type") != "oblast")
        print(f"   >> levels on history : {levelled}/{len(alerts)}")
        print(f"   >> below oblast level: {deep}/{len(alerts)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
