"""Command line access to the same statistics the web app shows.

    python -m airalert.cli --oblast "Kyivska oblast" --from 2026-01-01
    python -m airalert.cli --list-oblasts
    python -m airalert.cli --update
"""

from __future__ import annotations

import argparse
import json

import pandas as pd

from . import data, stats


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="airalert", description="Ukraine air alert statistics")
    parser.add_argument("--dataset", default="official", choices=sorted(data.DATASETS))
    parser.add_argument("--update", action="store_true", help="force a fresh download")
    parser.add_argument("--oblast", help="oblast name, omit for whole country")
    parser.add_argument("--raion", help="raion name (requires --oblast)")
    parser.add_argument("--hromada", help="hromada name (requires --raion)")
    parser.add_argument("--from", dest="start", help="period start, YYYY-MM-DD")
    parser.add_argument("--to", dest="end", help="period end, YYYY-MM-DD (exclusive)")
    parser.add_argument("--raw", action="store_true", help="count each declaration separately")
    parser.add_argument("--merge", action="store_true", help="merge overlapping declarations into episodes")
    parser.add_argument(
        "--standing-days",
        type=float,
        default=stats.STANDING_ALERT_DAYS,
        help="alerts at least this long are reported separately, not averaged in (0 = keep them in)",
    )
    parser.add_argument("--hours", help="only alerts starting in these Kyiv hours, e.g. 22,23,0,1")
    parser.add_argument("--list-oblasts", action="store_true")
    parser.add_argument("--list-raions", metavar="OBLAST")
    parser.add_argument("--json", action="store_true", help="print the full payload as JSON")
    return parser.parse_args(argv)


def _timestamp(value: str | None) -> pd.Timestamp | None:
    return None if value is None else pd.Timestamp(value, tz="UTC")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.raion and not args.oblast:
        raise SystemExit("--raion requires --oblast")
    if args.hromada and not args.raion:
        raise SystemExit("--hromada requires --raion")

    df = data.load(args.dataset, force_download=args.update)
    tree = data.gazetteer(df)

    if args.list_oblasts:
        for oblast in tree:
            print(oblast)
        return 0

    if args.list_raions:
        for raion in tree.get(args.list_raions, {}):
            print(raion)
        return 0

    payload = stats.report(
        df,
        oblast=args.oblast,
        raion=args.raion,
        hromada=args.hromada,
        start=_timestamp(args.start),
        end=_timestamp(args.end),
        merge=True if args.merge else (False if args.raw else None),
        standing_days=args.standing_days or None,
        hours=[int(h) for h in args.hours.split(",") if h.strip().isdigit()] if args.hours else None,
    )

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    _print_report(payload, data.coverage(df))
    return 0


def _print_report(payload: dict, cov: dict) -> None:
    area = payload["area"]
    name = area["hromada"] or area["raion"] or area["oblast"] or "Ukraine (all country)"
    period = payload["period"]
    summary = payload["summary"]

    print()
    print(f"  {name}")
    print(f"  period   {period['start'] or cov['first'][:10]} .. {period['end'] or cov['last'][:10]}")
    print(f"  mode     {payload['mode']}  ({payload['declarations']} raw declarations)")
    print("  " + "-" * 52)

    if not summary["finished"]:
        print("  no completed alerts in this selection")
        return

    print(f"  alerts            {summary['count']}")
    print(f"  total time        {summary['total_hours']} h")
    print(f"  average length    {_hm(summary['avg_min'])}")
    print(f"  median length     {_hm(summary['median_min'])}")
    print(f"  90th percentile   {_hm(summary['p90_min'])}")
    print(f"  shortest          {_hm(summary['min_min'])}   {summary['shortest']['started_at'][:16]}")
    print(f"  longest           {_hm(summary['max_min'])}   {summary['longest']['started_at'][:16]}")

    standing = payload["standing"]
    if standing["count"]:
        print()
        print(f"  {standing['count']} standing alert(s) >= {standing['threshold_days']:g} days "
              f"({standing['hours']:,.0f} h) reported separately, not averaged in:")
        for row in standing["examples"][:3]:
            where = row["hromada"] or row["raion"] or row["oblast"] or "-"
            print(f"    {row['started_at'][:10]}  {row['duration_min'] / 1440:>6.1f} d   {where}")

    rank = payload["ranking"]
    if rank["rows"]:
        print()
        print("  busiest areas")
        for row in rank["rows"][:10]:
            print(f"    {row['count']:>6}  {row['hours']:>8.1f} h   {row['name']}")
        if rank["shared"]:
            print(f"  {rank['shared']} alert(s) were declared for the whole area, so they")
            print(f"  count towards every {rank['field']} above — the rows overlap by that much.")


def _hm(minutes: float | None) -> str:
    if minutes is None:
        return "-"
    hours, mins = divmod(int(round(minutes)), 60)
    return f"{hours}h {mins:02d}m" if hours else f"{mins}m"


if __name__ == "__main__":
    raise SystemExit(main())
