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

    return df.sort_values("started_at", ignore_index=True)


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
