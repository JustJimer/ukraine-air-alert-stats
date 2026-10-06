"""Fetching, caching and loading the air-raid alert dataset.

Source: https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset
Public domain / no authentication, refreshed daily.

Columns: oblast, raion, hromada, level, started_at, finished_at, source
`level` is the granularity at which the alert was *declared* ("oblast",
"raion" or "hromada"), not the granularity of the affected territory: an
oblast-level alert covers every raion inside that oblast.
"""

from __future__ import annotations

import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

DATASETS = {
    "official": "https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/main/datasets/official_data_en.csv",
    "volunteer": "https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/main/datasets/volunteer_data_en.csv",
}

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MAX_AGE_SECONDS = 6 * 60 * 60  # refresh at most 4x/day


def cache_path(dataset: str = "official") -> Path:
    return DATA_DIR / f"{dataset}_data_en.csv"


def download(dataset: str = "official", force: bool = False) -> Path:
    """Download the CSV unless a fresh copy is already cached."""
    if dataset not in DATASETS:
        raise ValueError(f"unknown dataset {dataset!r}, expected one of {list(DATASETS)}")

    path = cache_path(dataset)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not force and path.exists():
        age = time.time() - path.stat().st_mtime
        if age < MAX_AGE_SECONDS:
            return path

    tmp = path.with_suffix(".csv.tmp")
    with urllib.request.urlopen(DATASETS[dataset], timeout=120) as response:
        tmp.write_bytes(response.read())
    tmp.replace(path)
    return path


def load(dataset: str = "official", force_download: bool = False) -> pd.DataFrame:
    """Return the alert table with parsed UTC timestamps and durations.

    Adds:
      duration_min : float, NaN while an alert is still running
      ongoing      : bool, no finished_at recorded yet
    """
    path = download(dataset, force=force_download)
    df = pd.read_csv(
        path,
        dtype={"oblast": "string", "raion": "string", "hromada": "string", "level": "string"},
    )

    for column in ("started_at", "finished_at"):
        df[column] = pd.to_datetime(df[column], utc=True, errors="coerce", format="ISO8601")

    df = df.dropna(subset=["started_at", "oblast"])

    # The upstream feed repeats a large share of its rows verbatim (~39% as of
    # 2026-08). Two distinct alerts for the same area cannot share a start and
    # end timestamp to the second, so identical rows are duplicates, not events.
    # Left in, they inflate every count and total-duration figure.
    before = len(df)
    df = df.drop_duplicates(subset=["oblast", "raion", "hromada", "level", "started_at", "finished_at"])
    df.attrs["duplicates_dropped"] = before - len(df)

    df["ongoing"] = df["finished_at"].isna()
    df["duration_min"] = (df["finished_at"] - df["started_at"]).dt.total_seconds() / 60.0

    # A handful of rows in the upstream feed close before they open. Blank them
    # with NaN rather than pd.NA: assigning pd.NA upcasts the column to object
    # dtype, which silently breaks every numeric method downstream.
    df["duration_min"] = df["duration_min"].where(df["duration_min"] >= 0)

    # mergesort for stability. The default quicksort reorders rows that share
    # a timestamp arbitrarily, and one oblast-wide siren appears as eight rows
    # with identical start and end times — so an unstable sort silently changes
    # which of them is reported as the longest alert.
    return df.sort_values("started_at", kind="mergesort", ignore_index=True)


ARCHIVE = Path(__file__).resolve().parent.parent / "archive" / "alerts_in_ua.csv"

# Ukraine split alerts into yellow and red levels on this date, and the old
# feed's parser broke on the same change. Using it as the seam means the join
# falls on a real change in how alerts are declared, rather than in the middle
# of a week for reasons only this project knows about. The last day and a half
# of the old feed is dropped in favour of the new source, which covers the same
# hours and carries the levels.
CUTOVER = pd.Timestamp("2026-09-06", tz="UTC")


def load_live() -> pd.DataFrame:
    """The alerts.in.ua archive, mapped onto this project's columns.

    The archive stores the API's own fields, so the mapping lives here and can
    be corrected and replayed over everything already collected.
    """
    from airalert.alerts_api import area_names

    if not ARCHIVE.exists():
        return pd.DataFrame(
            columns=["oblast", "raion", "hromada", "level", "started_at",
                     "finished_at", "source", "alert_level"]
        )

    raw = pd.read_csv(ARCHIVE, dtype="string")
    if raw.empty:
        return pd.DataFrame(
            columns=["oblast", "raion", "hromada", "level", "started_at",
                     "finished_at", "source", "alert_level"]
        )

    areas = [area_names(row) for row in raw.to_dict("records")]
    df = pd.DataFrame(areas, columns=["oblast", "raion", "hromada"], dtype="string")

    for column in ("started_at", "finished_at"):
        df[column] = pd.to_datetime(raw[column], utc=True, errors="coerce", format="ISO8601")

    # Derived rather than taken from location_type, so it always agrees with
    # which columns are actually set — which is the rule build.py enforces.
    df["level"] = np.where(df["hromada"].notna(), "hromada",
                  np.where(df["raion"].notna(), "raion", "oblast"))
    df["level"] = df["level"].astype("string")
    df["source"] = "alerts.in.ua"
    df["alert_level"] = raw["alert_level"].replace("", pd.NA)

    return df.dropna(subset=["started_at", "oblast"])


def load_combined(force_download: bool = False) -> pd.DataFrame:
    """The frozen official archive before the cutover, alerts.in.ua after it.

    The two sources count differently — the old one is a Telegram parse, the
    new one an API — so they are joined at the regime change rather than
    blended, and the seam is stated in the metadata for the page to show.
    """
    official = load("official", force_download=force_download)
    live = load_live()
    after = live[live["started_at"] >= CUTOVER] if len(live) else live

    # Only cut the old feed short when there is something to put in its place.
    # Otherwise a missing or empty archive — a failed sync, a fresh clone —
    # would silently drop the old feed's last day and a half and replace it
    # with nothing, which looks exactly like a quiet period in the data.
    before = official[official["started_at"] < CUTOVER] if len(after) else official

    if "alert_level" not in before.columns:
        before = before.assign(alert_level=pd.Series(pd.NA, index=before.index, dtype="string"))

    # Concatenating an empty frame would upcast the timestamp columns to
    # object dtype and break .dt downstream, which is the same trap empty
    # frames set in stats.merge_overlaps.
    combined = pd.concat([before, after], ignore_index=True) if len(after) else before.copy()
    combined["ongoing"] = combined["finished_at"].isna()
    combined["duration_min"] = (
        combined["finished_at"] - combined["started_at"]
    ).dt.total_seconds() / 60.0
    combined["duration_min"] = combined["duration_min"].where(combined["duration_min"] >= 0)

    combined.attrs["duplicates_dropped"] = official.attrs.get("duplicates_dropped", 0)
    combined.attrs["cutover"] = CUTOVER.isoformat()
    combined.attrs["live_rows"] = int(len(after))
    combined.attrs["official_rows"] = int(len(before))
    return combined.sort_values("started_at", kind="mergesort", ignore_index=True)


def gazetteer(df: pd.DataFrame) -> dict:
    """Build the oblast -> raion -> hromada tree present in the data."""
    tree: dict[str, dict[str, list[str]]] = {}

    for oblast, raion, hromada in zip(df["oblast"], df["raion"], df["hromada"]):
        raions = tree.setdefault(oblast, {})
        if pd.isna(raion):
            continue
        hromadas = raions.setdefault(raion, set())
        if not pd.isna(hromada):
            hromadas.add(hromada)

    return {
        oblast: {raion: sorted(hromadas) for raion, hromadas in sorted(raions.items())}
        for oblast, raions in sorted(tree.items())
    }


def coverage(df: pd.DataFrame) -> dict:
    """First/last timestamps and row count, for display in the UI."""
    return {
        "rows": int(len(df)),
        "first": df["started_at"].min().isoformat(),
        "last": df["started_at"].max().isoformat(),
        "ongoing": int(df["ongoing"].sum()),
        "duplicates_dropped": int(df.attrs.get("duplicates_dropped", 0)),
    }
