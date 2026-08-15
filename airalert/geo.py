"""Boundary geometry for the map, packed as ready-to-draw SVG paths.

The dataset names areas in Latin script ("Bakhmutskyi raion"); every open
boundary file names them in Ukrainian ("Бахмутський район"). Rather than
hand-maintain a 143-entry lookup table, this transliterates the Ukrainian
names with the Ukrainian National standard (KMU resolution 55, 2010) — the
same standard the feed itself uses. That matches 24 of 25 oblasts and 116 of
118 raions outright, and the leftovers are named explicitly below.

Geometry is projected, simplified and quantised here so the browser only has
to draw path strings. Everything lands in one coordinate space, so drilling
into an oblast is a change of viewBox rather than a second set of paths.

Source: github.com/slawomirmatuszak/ukrainian_geodata (CC BY 4.0), which
carries the post-2020 raions — the reform cut 490 raions to 136, and the
older boundary sets still ship the pre-reform ones.
"""

from __future__ import annotations

import json
import math
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

REPO = "https://raw.githubusercontent.com/slawomirmatuszak/ukrainian_geodata/master"
SOURCES = {"regiony": f"{REPO}/regiony.geojson", "rayony": f"{REPO}/rayony.geojson"}

ATTRIBUTION = {
    "name": "slawomirmatuszak/ukrainian_geodata",
    "url": "https://github.com/slawomirmatuszak/ukrainian_geodata",
    "licence": "CC BY 4.0",
}

# Renamed after the boundary file was published, so transliteration alone
# cannot bridge them. Both are decommunisation renames of an existing area,
# not boundary changes, so the geometry still applies.
RENAMED = {
    "Novomoskovskyi raion": "Samarivskyi raion",    # renamed 2024
    "Novohrad-Volynskyi raion": "Zviahelskyi raion",  # renamed 2023
}

# Kyiv is a region in its own right and the only one absent from the region
# file — it is present as a hole punched through the surrounding oblast.
KYIV = "Kyiv City"
KYIV_OBLAST = "Kyivska oblast"

# Latitude the projection is true to. Ukraine spans 44.4..52.4, so standing
# the scale factor up at the middle keeps the shape honest at both edges.
REF_LAT = 48.4

WIDTH = 1000.0      # projected coordinate space; the viewBox is derived from it
TOLERANCE = 0.35    # simplification, in those units — comfortably sub-pixel
PRECISION = 1


# --------------------------------------------------------------------------
# transliteration

_SIMPLE = {
    "а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d", "е": "e",
    "ж": "zh", "з": "z", "и": "y", "і": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ь": "", "'": "", "ʼ": "", "’": "",
}

# These take one form at the start of a word and another inside it.
_POSITIONAL = {
    "є": ("ye", "ie"), "ї": ("yi", "i"), "й": ("y", "i"),
    "ю": ("yu", "iu"), "я": ("ya", "ia"),
}

_APOSTROPHES = "'ʼ’"


def _translit_word(word: str) -> str:
    out, i = [], 0
    while i < len(word):
        char = word[i]
        lower = char.lower()

        # зг is romanised zgh, keeping it distinct from ж (zh).
        if lower == "з" and i + 1 < len(word) and word[i + 1].lower() == "г":
            piece, step = "zgh", 2
        elif lower in _POSITIONAL:
            piece, step = _POSITIONAL[lower][0 if i == 0 else 1], 1
        else:
            piece, step = _SIMPLE.get(lower, lower if lower.isalpha() else char), 1

        if char.isupper() and piece:
            piece = piece[0].upper() + piece[1:]
        out.append(piece)
        i += step
    return "".join(out)


def translit(text: str) -> str:
    """Ukrainian National transliteration, applied per word.

    Per word because the positional letters depend on it, and because
    "Івано-Франківська" is two words for that purpose.
    """
    parts, buffer = [], ""
    for char in text:
        if char.isalpha() or char in _APOSTROPHES:
            buffer += char
        else:
            if buffer:
                parts.append(_translit_word(buffer))
                buffer = ""
            parts.append(char)
    if buffer:
        parts.append(_translit_word(buffer))
    return "".join(parts)


# --------------------------------------------------------------------------
# geometry

def fetch(name: str, force: bool = False) -> dict:
    path = DATA_DIR / f"{name}.geojson"
    if force or not path.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        print(f"  downloading {name}.geojson ...")
        with urllib.request.urlopen(SOURCES[name], timeout=180) as response:
            path.write_bytes(response.read())
    return json.loads(path.read_text(encoding="utf-8"))


def project(lon: float, lat: float) -> tuple[float, float]:
    """Equirectangular, true to scale at REF_LAT.

    A conic would be marginally better across 8 degrees of latitude, but this
    keeps the inverse trivial and the error invisible at the size drawn.
    """
    return lon * math.cos(math.radians(REF_LAT)), -lat


def simplify(points: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    """Ramer-Douglas-Peucker, iterative so a long ring cannot blow the stack.

    Neighbouring areas are simplified independently, which in general opens
    slivers along shared borders. At a tolerance well under a pixel the
    slivers are subpixel too, and each path is stroked, which covers them.
    """
    if len(points) < 3:
        return points

    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]

    while stack:
        start, end = stack.pop()
        if end <= start + 1:
            continue

        ax, ay = points[start]
        bx, by = points[end]
        dx, dy = bx - ax, by - ay
        span = math.hypot(dx, dy)

        worst, worst_at = -1.0, start
        for i in range(start + 1, end):
            px, py = points[i]
            if span == 0:
                distance = math.hypot(px - ax, py - ay)
            else:
                distance = abs(dy * px - dx * py + bx * ay - by * ax) / span
            if distance > worst:
                worst, worst_at = distance, i

        if worst > tolerance:
            keep[worst_at] = True
            stack.append((start, worst_at))
            stack.append((worst_at, end))

    return [p for p, k in zip(points, keep) if k]


def rings(geometry: dict) -> list[list[list[float]]]:
    """Every ring of a Polygon or MultiPolygon, outer and inner alike."""
    if geometry["type"] == "Polygon":
        return list(geometry["coordinates"])
    return [ring for polygon in geometry["coordinates"] for ring in polygon]


def to_path(ring_list: list[list[tuple[float, float]]]) -> str:
    out = []
    for ring in ring_list:
        if len(ring) < 3:
            continue
        coords = [f"{round(x, PRECISION):g},{round(y, PRECISION):g}" for x, y in ring]
        out.append("M" + "L".join(coords) + "Z")
    return "".join(out)


def area_of(ring: list[tuple[float, float]]) -> float:
    """Signed area, used to pick out the largest ring for label placement."""
    total = 0.0
    for i in range(len(ring) - 1):
        total += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
    return total / 2


def centroid(ring_list: list[list[tuple[float, float]]]) -> tuple[float, float]:
    """Centroid of the largest ring — a label anchor, not a true centroid.

    The largest ring rather than all of them, so an oblast with offshore
    islands does not drag its label into the sea.
    """
    ring = max(ring_list, key=lambda r: abs(area_of(r)))
    signed = area_of(ring)
    if abs(signed) < 1e-12:
        return ring[0]

    cx = cy = 0.0
    for i in range(len(ring) - 1):
        x0, y0 = ring[i]
        x1, y1 = ring[i + 1]
        cross = x0 * y1 - x1 * y0
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    return cx / (6 * signed), cy / (6 * signed)


def bounds(ring_list: list[list[tuple[float, float]]]) -> list[float]:
    xs = [x for ring in ring_list for x, _ in ring]
    ys = [y for ring in ring_list for _, y in ring]
    return [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]


def build(force: bool = False) -> dict:
    regions = fetch("regiony", force)
    raions = fetch("rayony", force)

    # Pass one: project everything, and note the extent so the whole country
    # can be scaled into the coordinate space in pass two.
    shapes: dict[str, dict] = {}

    def collect(name: str, geometry: dict, kind: str, parent: str | None = None) -> None:
        projected = [[project(x, y) for x, y in ring] for ring in rings(geometry)]
        shapes[name] = {"kind": kind, "rings": projected, "parent": parent}

    kyiv_hole = None
    for feature in regions["features"]:
        ukrainian = feature["properties"]["region"]
        name = translit(ukrainian)

        if name == KYIV_OBLAST:
            # The hole in the surrounding oblast is Kyiv itself. Verified by
            # extent and area (846 km2 against the city's 839) rather than
            # assumed from ring order.
            for polygon in feature["geometry"]["coordinates"]:
                for ring in polygon[1:]:
                    lons = [p[0] for p in ring]
                    lats = [p[1] for p in ring]
                    if 30.2 < min(lons) and max(lons) < 30.9 and 50.1 < min(lats) and max(lats) < 50.7:
                        kyiv_hole = ring
        collect(name, feature["geometry"], "oblast")

    if kyiv_hole is None:
        raise SystemExit("Kyiv City not found as a hole in Kyivska oblast — check the region file")
    collect(KYIV, {"type": "Polygon", "coordinates": [kyiv_hole]}, "oblast")

    # Raion to oblast, resolved by which oblast contains the raion's centroid.
    # The raion file carries no parent field, and the dataset's own tree only
    # lists raions that have been individually alerted, which would leave
    # holes in an oblast that has only ever had oblast-wide sirens.
    oblast_rings = {n: s["rings"] for n, s in shapes.items() if s["kind"] == "oblast" and n != KYIV}

    for feature in raions["features"]:
        name = translit(feature["properties"]["rayon"])
        name = RENAMED.get(name, name)
        collect(name, feature["geometry"], "raion")

    for name, shape in shapes.items():
        if shape["kind"] != "raion":
            continue
        point = centroid(shape["rings"])
        shape["parent"] = next(
            (oblast for oblast, rgs in oblast_rings.items() if contains(rgs, point)), None
        )

    # Pass two: scale into the coordinate space, simplify, quantise.
    every = [ring for shape in shapes.values() for ring in shape["rings"]]
    min_x, min_y, span_x, span_y = bounds(every)
    scale = WIDTH / span_x
    height = round(span_y * scale, PRECISION)

    out_oblasts, out_raions, children = {}, {}, {}

    for name, shape in shapes.items():
        placed = [
            [((x - min_x) * scale, (y - min_y) * scale) for x, y in ring]
            for ring in shape["rings"]
        ]
        reduced = [r for r in (simplify(ring, TOLERANCE) for ring in placed) if len(r) >= 4]
        if not reduced:
            continue

        entry = {
            "d": to_path(reduced),
            "c": [round(v, PRECISION) for v in centroid(reduced)],
            "box": [round(v, PRECISION) for v in bounds(reduced)],
        }
        if shape["kind"] == "oblast":
            out_oblasts[name] = entry
        else:
            entry["parent"] = shape["parent"]
            out_raions[name] = entry
            children.setdefault(shape["parent"], []).append(name)

    return {
        "attribution": ATTRIBUTION,
        "viewBox": [0, 0, WIDTH, height],
        "oblasts": out_oblasts,
        "raions": out_raions,
        "raionsOf": {k: sorted(v) for k, v in children.items() if k},
    }


def contains(ring_list: list[list[tuple[float, float]]], point: tuple[float, float]) -> bool:
    """Even-odd point in polygon across every ring, so holes exclude."""
    x, y = point
    inside = False
    for ring in ring_list:
        for i in range(len(ring) - 1):
            x0, y0 = ring[i]
            x1, y1 = ring[i + 1]
            if (y0 > y) != (y1 > y):
                cross = x0 + (y - y0) / (y1 - y0) * (x1 - x0)
                if cross > x:
                    inside = not inside
    return inside
