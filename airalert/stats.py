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


def _empty_episodes() -> pd.DataFrame:
    """An episode frame with no rows but the right dtypes.

    Building it from an empty list instead would give object-dtype columns,
    and numeric methods such as nlargest reject those — so a merged query that
    happened to match nothing used to raise instead of reporting zero.
    """
    return pd.DataFrame(
        {
            "started_at": pd.Series(dtype="datetime64[ns, UTC]"),
            "finished_at": pd.Series(dtype="datetime64[ns, UTC]"),
            "parts": pd.Series(dtype="int64"),
            "duration_min": pd.Series(dtype="float64"),
            "ongoing": pd.Series(dtype="bool"),
        }
    )


def merge_overlaps(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse overlapping intervals into single territory-wide episodes."""
    if df.empty:
        return _empty_episodes()

    frame = df.dropna(subset=["finished_at"]).sort_values("started_at")
    episodes: list[list] = []

    for started, finished in zip(frame["started_at"], frame["finished_at"]):
        if episodes and started <= episodes[-1][1]:
            episodes[-1][1] = max(episodes[-1][1], finished)
            episodes[-1][2] += 1
        else:
            episodes.append([started, finished, 1])

    if not episodes:
        return _empty_episodes()

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

    def total(period) -> float:
        # A month with no finished alerts sums to NaN under min_count=1, and
        # `nan or 0.0` yields NaN because NaN is truthy — which then serialises
        # as a bare NaN token and makes the payload invalid JSON.
        value = hours.get(period, 0.0)
        return round(float(value), 1) if pd.notna(value) else 0.0

    return [
        {"month": period.strftime("%Y-%m"), "count": int(count), "hours": total(period)}
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


def ranking(
    df: pd.DataFrame,
    children: Sequence[str],
    field: str = "oblast",
    limit: int = 15,
) -> dict:
    """How many alerts covered each child area, with their average duration.

    An alert declared for a whole oblast has no raion, but it still put every
    raion in that oblast under alert. Grouping on the raion column alone drops
    those rows, which is how an oblast showing 8,932 alerts could break down
    into raions totalling only 5,251.

    So rows with a null `field` are treated as covering every child and added
    to each child's total. Children therefore sum to more than the parent —
    correct, because one oblast-wide siren covers every raion at once. The
    shared figure is reported separately so the overlap stays visible.
    """
    if df.empty or field not in df:
        return {"field": field, "shared": 0, "rows": []}

    covers_all = df[df[field].isna()]
    shared_count = len(covers_all)
    shared_finished = int(covers_all["duration_min"].notna().sum())
    shared_hours = float(covers_all["duration_min"].sum()) / 60.0 if shared_count else 0.0

    own = df.dropna(subset=[field])
    grouped = own.groupby(field, observed=True)
    counts, finished = grouped.size(), grouped["duration_min"].count()
    hours = grouped["duration_min"].sum(min_count=1) / 60.0

    rows = []
    for name in children:
        count = int(counts.get(name, 0)) + shared_count
        if not count:
            continue
        total = float(hours.get(name, 0.0) or 0.0) + shared_hours
        done = int(finished.get(name, 0)) + shared_finished
        rows.append(
            {
                "name": str(name),
                "count": count,
                "own": int(counts.get(name, 0)),
                "hours": round(total, 1),
                "avg_min": round(total * 60.0 / done, 1) if done else None,
            }
        )

    rows.sort(key=lambda row: row["count"], reverse=True)
    return {"field": field, "shared": shared_count, "rows": rows[:limit]}


def children_of(df: pd.DataFrame, oblast: str | None, raion: str | None) -> list[str]:
    """Every child area of the selection that appears anywhere in the data.

    Taken from the whole dataset, not the current selection, so a raion that
    only ever saw oblast-wide alerts still gets a row rather than vanishing.
    """
    if oblast is None:
        return sorted(df["oblast"].dropna().unique())
    scope = df[df["oblast"] == oblast]
    if raion is None:
        return sorted(scope["raion"].dropna().unique())
    return sorted(scope[scope["raion"] == raion]["hromada"].dropna().unique())


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
    ranking_limit: int = 15,
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
        # The table shows a top 15; the map needs every child area, so the
        # limit is caller's choice rather than fixed here.
        "ranking": ranking(
            declarations,
            children_of(df, oblast, raion),
            "hromada" if raion else "raion" if oblast else "oblast",
            ranking_limit,
        ),
    }
