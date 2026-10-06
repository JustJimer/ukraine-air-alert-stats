"""Pull the last month of alerts from alerts.in.ua into the tracked archive.

Run daily from CI. Each run re-reads a whole month for every region and
upserts on the API's own record id, which makes the archive self-healing: a
run can fail, or be skipped for a fortnight, and nothing is lost as long as
one run lands inside the month. It also means an alert that was still running
when first seen gets its end time filled in by a later run.

The archive stores the API's fields verbatim rather than this project's
columns. Mapping happens at build time, so if the mapping turns out to be
wrong — the exact shape of these records is documented thinly and was not
verifiable before a token existed — it can be corrected and replayed over
data already collected, instead of having been lost at write time.

    python sync_live.py             # update archive/alerts_in_ua.csv
    python sync_live.py --dry-run   # fetch and report, write nothing
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from airalert import alerts_api

ARCHIVE = Path(__file__).resolve().parent / "archive" / "alerts_in_ua.csv"

# Verbatim API fields. `id` is the upsert key; the rest are what the build
# needs to place an alert in space, time and severity.
COLUMNS = [
    "id", "location_uid", "location_type", "location_title",
    "location_oblast", "location_raion",
    "started_at", "finished_at", "alert_type", "alert_level", "threats",
]


def read_archive() -> dict[str, dict]:
    if not ARCHIVE.exists():
        return {}
    with ARCHIVE.open(encoding="utf-8", newline="") as handle:
        return {row["id"]: row for row in csv.DictReader(handle)}


def write_archive(rows: dict[str, dict]) -> None:
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    # Sorted by start time so the daily diff is an append in the common case
    # rather than a reshuffle of the whole file.
    ordered = sorted(rows.values(), key=lambda r: (r.get("started_at") or "", r.get("id") or ""))
    with ARCHIVE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ordered)


def flatten(alert: dict) -> dict:
    """One API alert as a flat row, keeping only what the build can use."""
    threats = alert.get("threats") or []
    return {
        "id": str(alert.get("id", "")),
        "location_uid": alert.get("location_uid") or "",
        "location_type": alert.get("location_type") or "",
        "location_title": alert.get("location_title") or "",
        "location_oblast": alert.get("location_oblast") or "",
        "location_raion": alert.get("location_raion") or "",
        "started_at": alert.get("started_at") or "",
        "finished_at": alert.get("finished_at") or "",
        "alert_type": alert.get("alert_type") or "",
        "alert_level": alert.get("alert_level") or "",
        # Threat levels can differ from the alert's own level and can change
        # during one alert, which is the behaviour that matters here. Kept as
        # a compact "type:level" list rather than a second table.
        "threats": ";".join(
            f"{t.get('threat_type','?')}:{t.get('level','?')}" for t in threats
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sync_live")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--uid", type=int, action="append",
                        help="limit to these region uids (default: all)")
    args = parser.parse_args(argv)

    api = alerts_api.AlertsApi()
    uids = args.uid or sorted(alerts_api.OBLAST_UIDS)

    existing = read_archive()
    before = len(existing)
    added = updated = 0
    levelled = deep = 0

    print(f"archive holds {before:,} records")
    print(f"sweeping {len(uids)} regions (~{len(uids) * alerts_api.HISTORY_INTERVAL / 60:.0f} min "
          f"at the documented 2 requests a minute)")

    for n, uid in enumerate(uids, 1):
        alerts = api.history(uid)
        fresh = changed = 0
        for alert in alerts:
            row = flatten(alert)
            if not row["id"]:
                continue
            if row["alert_level"]:
                levelled += 1
            if row["location_type"] not in ("", "oblast"):
                deep += 1

            previous = existing.get(row["id"])
            if previous is None:
                fresh += 1
            elif previous != row:
                changed += 1
            existing[row["id"]] = row

        added += fresh
        updated += changed
        print(f"  [{n:>2}/{len(uids)}] uid {uid:<3} {alerts_api.OBLAST_UIDS[uid]:<28} "
              f"{len(alerts):>4} alerts  +{fresh} new  ~{changed} updated")

    print(f"\n{added:,} new, {updated:,} updated, {len(existing):,} total")
    print(f"records carrying a level: {levelled:,}")
    print(f"records below oblast level: {deep:,}")

    if args.dry_run:
        print("dry run — archive not written")
        return 0

    if added or updated:
        write_archive(existing)
        print(f"wrote {ARCHIVE}")
    else:
        print("nothing changed — archive left alone")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
