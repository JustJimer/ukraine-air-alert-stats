"""Emit reference results from the Python implementation for the JS port.

    python parity.py            # writes web/data/parity.json

web/data/parity.json holds, for a spread of queries, exactly what
airalert.stats produces. The page at /parity.html replays the same queries
through stats.js and diffs the two, so any drift between the reference
implementation and the browser port surfaces as a failure rather than as
quietly wrong numbers.

The file is a test fixture, not part of the site — the deploy workflow runs
the check and then drops it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from airalert import data, stats

OUT = Path(__file__).resolve().parent / "web" / "data" / "parity.json"

# (label, kwargs for stats.report). Chosen to cover every branch that differs
# between merged and raw, each gazetteer level, the hour filter, the standing
# split, and the empty result.
SCENARIOS: list[tuple[str, dict]] = [
    ("country all time, auto", {}),
    ("country 2025, raw", {"start": "2025-01-01", "end": "2026-01-01", "merge": False}),
    ("country 2025, merged", {"start": "2025-01-01", "end": "2026-01-01", "merge": True}),
    ("country, standing off", {"standing_days": None}),
    ("country, standing 1 day", {"standing_days": 1.0}),
    ("country, night hours", {"hours": [22, 23, 0, 1]}),
    ("oblast auto", {"oblast": "Mykolaivska oblast"}),
    ("oblast raw", {"oblast": "Mykolaivska oblast", "merge": False}),
    ("oblast frontline merged", {"oblast": "Dnipropetrovska oblast", "merge": True}),
    ("oblast + period", {"oblast": "Kyivska oblast", "start": "2026-01-01", "end": "2026-08-01"}),
    ("oblast + hours", {"oblast": "Kyivska oblast", "hours": [3, 4, 5]}),
    ("raion", {"oblast": "Mykolaivska oblast", "raion": "Mykolaivskyi raion"}),
    ("raion raw", {"oblast": "Mykolaivska oblast", "raion": "Mykolaivskyi raion", "merge": False}),
    ("raion + period + hours", {"oblast": "Lvivska oblast", "raion": "Lvivskyi raion",
                                "start": "2024-01-01", "end": "2025-01-01", "hours": [12]}),
    ("hromada", {"oblast": "Lvivska oblast", "raion": "Lvivskyi raion",
                 "hromada": "Lvivska terytorialna hromada"}),
    ("empty period", {"oblast": "Lvivska oblast", "start": "2022-03-01", "end": "2022-03-02"}),
]


def timestamp(value: str | None) -> pd.Timestamp | None:
    return None if value is None else pd.Timestamp(value, tz="UTC")


def main() -> int:
    df = data.load()
    cases = []

    for label, kwargs in SCENARIOS:
        query = dict(kwargs)
        payload = stats.report(
            df,
            oblast=query.get("oblast"),
            raion=query.get("raion"),
            hromada=query.get("hromada"),
            start=timestamp(query.get("start")),
            end=timestamp(query.get("end")),
            merge=query.get("merge"),
            standing_days=query.get("standing_days", stats.STANDING_ALERT_DAYS),
            hours=query.get("hours"),
        )
        cases.append({"label": label, "query": query, "expected": payload})
        print(f"  {label:<28} alerts={payload['summary']['count']:>7}  mode={payload['mode']}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cases, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(f"wrote {len(cases)} scenarios to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
