"""Pack the alert dataset into a form the browser can load directly.

Run before deploying (and daily, from CI):

    python build.py            # writes web/data/
    python build.py --update   # force a fresh download first

The whole dataset is under a megabyte gzipped, so the static site ships it
and does all the filtering client side. No API, no server.

Month and Kyiv-local-hour buckets are precomputed here rather than in the
browser: pandas already handles Ukraine's DST correctly, and baking the
result in keeps the JavaScript free of timezone logic that could silently
disagree with the Python reference implementation.
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

from airalert import data, stats

OUT_DIR = Path(__file__).resolve().parent / "web" / "data"

NO_DURATION = 0xFFFFFFFF  # sentinel for an alert with no recorded end


def pack(df: pd.DataFrame) -> tuple[bytes, dict]:
    """Columnar little-endian buffer plus the metadata describing it."""
    n = len(df)

    oblasts = sorted(df["oblast"].dropna().unique())
    raions = sorted(df["raion"].dropna().unique())
    hromadas = sorted(df["hromada"].dropna().unique())

    if len(oblasts) > 255:
        raise SystemExit("oblast index no longer fits in a uint8")
    if max(len(raions), len(hromadas)) > 65534:
        raise SystemExit("raion or hromada index no longer fits in a uint16")

    base = df["started_at"].min().normalize()

    # Seconds, not minutes: the feed records alerts to the second, and
    # truncating to minutes shifted durations, moved merge boundaries and made
    # sub-minute alerts tie at zero, so the browser disagreed with Python.
    #
    # Both come straight from the timestamps. Deriving seconds by multiplying
    # duration_min back by 60 round-trips through a division whose result can
    # land just under the integer, and the cast to uint32 then truncates a
    # second away — small per row, visible once summed over 177k of them.
    starts = np.rint((df["started_at"] - base).dt.total_seconds()).to_numpy(dtype=np.uint32)

    elapsed = (df["finished_at"] - df["started_at"]).dt.total_seconds()
    elapsed = elapsed.where(df["duration_min"].notna())  # respect blanked negatives
    durations = np.where(
        elapsed.isna(), NO_DURATION, np.rint(elapsed.fillna(0.0))
    ).astype(np.uint32)

    # Month buckets follow UTC calendar months, matching stats.by_month, which
    # resamples a UTC-indexed frame. Drop the tz explicitly so the conversion
    # states that intent instead of relying on a warning-laden implicit one.
    naive = df["started_at"].dt.tz_convert("UTC").dt.tz_localize(None)
    base_month = base.tz_convert("UTC").tz_localize(None).to_period("M")
    months = (naive.dt.to_period("M") - base_month).apply(lambda x: x.n).to_numpy(dtype=np.uint16)
    hours = stats.local_hour(df).to_numpy(dtype=np.uint8)

    oblast_ix = {name: i for i, name in enumerate(oblasts)}
    raion_ix = {name: i + 1 for i, name in enumerate(raions)}
    hromada_ix = {name: i + 1 for i, name in enumerate(hromadas)}

    oblast_col = df["oblast"].map(oblast_ix).to_numpy(dtype=np.uint8)
    raion_col = df["raion"].map(raion_ix).fillna(0).to_numpy(dtype=np.uint16)
    hromada_col = df["hromada"].map(hromada_ix).fillna(0).to_numpy(dtype=np.uint16)

    # `level` is not packed because it is implied by which area fields are set.
    # Verify that here so the build fails loudly if the feed ever stops
    # following the pattern, rather than the page inventing a wrong label.
    derived = np.where(hromada_col > 0, "hromada", np.where(raion_col > 0, "raion", "oblast"))
    mismatched = int((derived != df["level"].to_numpy()).sum())
    if mismatched:
        raise SystemExit(f"level is no longer derivable from the area fields ({mismatched} rows differ)")

    columns = [
        ("starts", starts), ("durations", durations), ("months", months),
        ("hours", hours), ("oblast", oblast_col), ("raion", raion_col),
        ("hromada", hromada_col),
    ]

    buffer, offsets, cursor = bytearray(), {}, 0
    for name, column in columns:
        payload = column.tobytes()
        if cursor % column.dtype.itemsize:
            raise SystemExit(f"section {name} would be misaligned at {cursor}")
        offsets[name] = cursor
        buffer += payload
        cursor += len(payload)

    meta = {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "rows": n,
        "base": base.isoformat(),
        "base_month": str(base_month),
        "units": "seconds",
        "no_duration": NO_DURATION,
        "offsets": offsets,
        "bytes": cursor,
        "oblasts": [str(x) for x in oblasts],
        "raions": [str(x) for x in raions],
        "hromadas": [str(x) for x in hromadas],
        "tree": build_tree(df, oblast_ix, raion_ix, hromada_ix),
        "coverage": data.coverage(df),
        "standing_alert_days": stats.STANDING_ALERT_DAYS,
    }
    return bytes(buffer), meta


def build_tree(df: pd.DataFrame, oblast_ix: dict, raion_ix: dict, hromada_ix: dict) -> dict:
    """oblast index -> raion index -> hromada indices, as the cascade needs.

    Built from the whole dataset so an area that only ever saw parent-level
    alerts still appears, matching stats.children_of.
    """
    tree: dict[int, dict[int, list[int]]] = {}

    for oblast, raion, hromada in zip(df["oblast"], df["raion"], df["hromada"]):
        raions = tree.setdefault(oblast_ix[oblast], {})
        if pd.isna(raion):
            continue
        hromadas = raions.setdefault(raion_ix[raion], set())
        if not pd.isna(hromada):
            hromadas.add(hromada_ix[hromada])

    return {
        str(oblast): {str(raion): sorted(hromadas) for raion, hromadas in sorted(raions.items())}
        for oblast, raions in sorted(tree.items())
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build")
    parser.add_argument("--update", action="store_true", help="force a fresh download")
    parser.add_argument("--dataset", default="official", choices=sorted(data.DATASETS))
    args = parser.parse_args(argv)

    print(f"loading {args.dataset} dataset ...")
    df = data.load(args.dataset, force_download=args.update)

    buffer, meta = pack(df)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    (OUT_DIR / "alerts.bin").write_bytes(buffer)
    (OUT_DIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    # Both are written, and the page asks for the .gz first.
    #
    # Cloudflare compresses text responses but leaves application/octet-stream
    # alone, so the raw file goes over the wire at full size — meta.json comes
    # back brotli-encoded while alerts.bin does not. Serving a pre-compressed
    # copy and inflating it with DecompressionStream cuts the download to a
    # third. alerts.bin stays for browsers without that API.
    compressed = gzip.compress(buffer, 9)
    (OUT_DIR / "alerts.bin.gz").write_bytes(compressed)

    print(f"  {meta['rows']:,} alerts, {meta['coverage']['first'][:10]} .. {meta['coverage']['last'][:10]}")
    print(f"  {len(buffer) / 1e6:.2f} MB packed, {len(compressed) / 1e6:.2f} MB over the wire (gzip)")
    print(f"  wrote {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
