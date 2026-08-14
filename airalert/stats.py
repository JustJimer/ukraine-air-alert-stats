"""Filtering and statistics over the alert intervals.

Two things make this less trivial than "group by and average":

1. Alerts are declared at mixed granularity. Before December 2025 almost
   everything was oblast-wide; since then raion-level declarations are the
   norm. A query for one raion must therefore also pick up the oblast-wide
   rows that covered it, otherwise the pre-2026 history looks empty.

2. Once parent-level rows are included, intervals overlap. Counting rows
   would double-count a single event. `merge_overlaps` collapses them into
   territory-wide episodes: "the siren was on somewhere in this area from
   A to B". Raw mode keeps every declaration separately, which is what you
   want when comparing how often each area was individually alerted.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

KYIV = "Europe/Kyiv"

# Frontline territories keep a siren declared continuously for months at a
# time. Those records are real, but mixing them into duration statistics makes
# "longest alert" meaningless and drags the average up, so they are reported
# separately rather than averaged in. Anything running this long is a standing
# alert, not an event.
STANDING_ALERT_DAYS = 7.0


def select_area(
    df: pd.DataFrame,
    oblast: str | None = None,
    raion: str | None = None,
    hromada: str | None = None,
) -> pd.DataFrame:
    """Rows whose declared area covers, or sits inside, the requested area."""
    if oblast is None:
        return df

    mask = df["oblast"] == oblast

    if raion is not None:
        # Oblast-wide rows (raion is null) cover this raion too.
        mask &= df["raion"].isna() | (df["raion"] == raion)

        if hromada is not None:
            mask &= df["raion"].isna() | df["hromada"].isna() | (df["hromada"] == hromada)

    return df[mask]


def select_period(
    df: pd.DataFrame,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Alerts whose *start* falls inside [start, end).

    Selecting on start time keeps every alert counted exactly once and keeps
    reported durations equal to the real duration rather than a clipped one.
    """
    result = df
    if start is not None:
        result = result[result["started_at"] >= start]
    if end is not None:
        result = result[result["started_at"] < end]
    return result


def merge_overlaps(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse overlapping intervals into single territory-wide episodes."""
    if df.empty:
        return pd.DataFrame(columns=["started_at", "finished_at", "duration_min", "ongoing", "parts"])

    frame = df.dropna(subset=["finished_at"]).sort_values("started_at")
    episodes: list[list] = []

    for started, finished in zip(frame["started_at"], frame["finished_at"]):
        if episodes and started <= episodes[-1][1]:
            episodes[-1][1] = max(episodes[-1][1], finished)
            episodes[-1][2] += 1
        else:
            episodes.append([started, finished, 1])

    merged = pd.DataFrame(episodes, columns=["started_at", "finished_at", "parts"])
    merged["duration_min"] = (merged["finished_at"] - merged["started_at"]).dt.total_seconds() / 60.0
    merged["ongoing"] = False
    return merged


def summarise(df: pd.DataFrame) -> dict:
    """Headline metrics over a set of intervals."""
    finished = df.dropna(subset=["duration_min"])
    durations = finished["duration_min"]

    summary = {
        "count": int(len(df)),
        "finished": int(len(finished)),
        "ongoing": int(df["ongoing"].sum()) if "ongoing" in df else 0,
        "total_hours": None,
        "avg_min": None,
        "median_min": None,
        "p90_min": None,
        "min_min": None,
        "max_min": None,
        "shortest": None,
        "longest": None,
    }

    if durations.empty:
        return summary

    shortest = finished.loc[durations.idxmin()]
    longest = finished.loc[durations.idxmax()]

    summary.update(
        {
            "total_hours": round(float(durations.sum()) / 60.0, 1),
            "avg_min": round(float(durations.mean()), 1),
            "median_min": round(float(durations.median()), 1),
            "p90_min": round(float(durations.quantile(0.90)), 1),
            "min_min": round(float(durations.min()), 1),
            "max_min": round(float(durations.max()), 1),
            "shortest": _describe(shortest),
            "longest": _describe(longest),
        }
    )
    return summary


def _describe(row: pd.Series) -> dict:
    described = {
        "started_at": row["started_at"].isoformat(),
        "finished_at": row["finished_at"].isoformat(),
        "duration_min": round(float(row["duration_min"]), 1),
    }
    for field in ("oblast", "raion", "hromada", "level"):
        value = row.get(field)
        described[field] = None if value is None or pd.isna(value) else str(value)
    return described


def by_month(df: pd.DataFrame) -> list[dict]:
    """Alert count and total hours per calendar month."""
    if df.empty:
        return []

    grouped = df.set_index("started_at").resample("MS")
    counts = grouped.size()
    hours = grouped["duration_min"].sum(min_count=1) / 60.0

    return [
        {
            "month": period.strftime("%Y-%m"),
            "count": int(count),
            "hours": round(float(hours.get(period, 0.0) or 0.0), 1),
        }
        for period, count in counts.items()
    ]


def local_hour(df: pd.DataFrame) -> pd.Series:
    """Hour of day each alert started, in Kyiv local time."""
    return df["started_at"].dt.tz_convert(KYIV).dt.hour


def select_hours(df: pd.DataFrame, hours: Sequence[int] | None) -> pd.DataFrame:
    """Alerts that started during any of the given Kyiv hours."""
    if not hours or df.empty:
        return df
    return df[local_hour(df).isin(list(hours))]


def by_hour(df: pd.DataFrame) -> list[int]:
    """How many alerts started in each hour of the day, Kyiv local time."""
    if df.empty:
        return [0] * 24
    counts = local_hour(df).value_counts()
    return [int(counts.get(hour, 0)) for hour in range(24)]


def ranking(df: pd.DataFrame, field: str = "oblast", limit: int = 15) -> list[dict]:
    """Busiest areas by alert count, with their average duration."""
    if df.empty or field not in df:
        return []

    grouped = df.groupby(field, dropna=True, observed=True)
    table = pd.DataFrame(
        {
            "count": grouped.size(),
            "hours": grouped["duration_min"].sum(min_count=1) / 60.0,
            "avg_min": grouped["duration_min"].mean(),
        }
    ).sort_values("count", ascending=False).head(limit)

    return [
        {
            "name": str(name),
            "count": int(row["count"]),
            "hours": round(float(row["hours"]), 1) if pd.notna(row["hours"]) else 0.0,
            "avg_min": round(float(row["avg_min"]), 1) if pd.notna(row["avg_min"]) else None,
        }
        for name, row in table.iterrows()
    ]


def _standing_mask(df: pd.DataFrame, standing_days: float) -> pd.Series:
    """True for alerts running at least `standing_days`. Ongoing alerts (no
    end time, so NaN duration) are never standing — they are simply unfinished."""
    return (df["duration_min"] >= standing_days * 24 * 60).fillna(False)


def _drop_standing(df: pd.DataFrame, standing_days: float | None) -> pd.DataFrame:
    if standing_days is None or df.empty:
        return df
    return df[~_standing_mask(df, standing_days)]


def report(
    df: pd.DataFrame,
    oblast: str | None = None,
    raion: str | None = None,
    hromada: str | None = None,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
    merge: bool | None = None,
    standing_days: float | None = STANDING_ALERT_DAYS,
    hours: Sequence[int] | None = None,
) -> dict:
    """Full statistics payload for one area/period selection.

    `merge=None` picks the sensible default: merging is right for a chosen
    territory, but merging the whole country collapses into a handful of
    month-long episodes, because some siren is on somewhere almost always.
    """
    if merge is None:
        merge = oblast is not None

    selected = select_period(select_area(df, oblast, raion, hromada), start, end)
    intervals = merge_overlaps(selected) if merge else selected

    standing = intervals.iloc[:0]
    if standing_days is not None and not intervals.empty:
        is_standing = _standing_mask(intervals, standing_days)
        standing = intervals[is_standing]
        intervals = intervals[~is_standing]

    # The hour histogram is built before the hour filter is applied, so the
    # chart keeps showing the whole distribution you are selecting against
    # instead of collapsing to the hours already chosen.
    hour_distribution = by_hour(intervals)

    hours = sorted({int(h) for h in hours}) if hours else []
    intervals = select_hours(intervals, hours)
    declarations = select_hours(_drop_standing(selected, standing_days), hours)

    return {
        "area": {"oblast": oblast, "raion": raion, "hromada": hromada},
        "period": {
            "start": start.isoformat() if start is not None else None,
            "end": end.isoformat() if end is not None else None,
        },
        "mode": "merged" if merge else "raw",
        "hours": hours,
        "summary": summarise(intervals),
        "declarations": int(len(selected)),
        "standing": {
            "threshold_days": standing_days,
            "count": int(len(standing)),
            "hours": round(float(standing["duration_min"].sum()) / 60.0, 1) if len(standing) else 0.0,
            "examples": [_describe(row) for _, row in standing.nlargest(5, "duration_min").iterrows()],
        },
        "by_month": by_month(intervals),
        "by_hour": hour_distribution,
        "ranking": ranking(declarations, "raion" if oblast else "oblast"),
    }
