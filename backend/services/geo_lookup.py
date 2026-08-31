"""Offline place lookup — resolve a state name/abbreviation or US ZIP to a
map location. No network required; used to fly the map to a search target."""

from __future__ import annotations

import json
import re
from pathlib import Path

_ZIP_CENTROIDS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "zip_centroids.json"


def _load_zip_centroids() -> dict[str, list[float]]:
    try:
        with open(_ZIP_CENTROIDS_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


# zip5 -> [lat, lon]; ~41k US ZIP code centroids from GeoNames.
ZIP_CENTROIDS: dict[str, list[float]] = _load_zip_centroids()

# Approximate geographic centers of US states/territories: abbr -> (lat, lon).
US_STATE_CENTROIDS: dict[str, tuple[float, float]] = {
    "AL": (32.806, -86.791), "AK": (61.370, -152.404), "AZ": (33.729, -111.431),
    "AR": (34.970, -92.373), "CA": (36.117, -119.682), "CO": (39.059, -105.311),
    "CT": (41.598, -72.755), "DE": (39.319, -75.507), "DC": (38.897, -77.026),
    "FL": (27.766, -81.687), "GA": (33.040, -83.643), "HI": (21.094, -157.498),
    "ID": (44.240, -114.479), "IL": (40.349, -88.986), "IN": (39.849, -86.258),
    "IA": (42.011, -93.210), "KS": (38.526, -96.726), "KY": (37.668, -84.670),
    "LA": (31.169, -91.867), "ME": (44.693, -69.381), "MD": (39.064, -76.802),
    "MA": (42.230, -71.530), "MI": (43.326, -84.536), "MN": (45.694, -93.900),
    "MS": (32.741, -89.678), "MO": (38.456, -92.288), "MT": (46.921, -110.454),
    "NE": (41.125, -98.268), "NV": (38.313, -117.055), "NH": (43.452, -71.564),
    "NJ": (40.298, -74.521), "NM": (34.841, -106.248), "NY": (42.166, -74.948),
    "NC": (35.630, -79.806), "ND": (47.529, -99.784), "OH": (40.389, -82.764),
    "OK": (35.565, -96.928), "OR": (44.572, -122.071), "PA": (40.590, -77.209),
    "RI": (41.680, -71.512), "SC": (33.856, -80.945), "SD": (44.299, -99.438),
    "TN": (35.747, -86.692), "TX": (31.055, -97.563), "UT": (40.150, -111.862),
    "VT": (44.045, -72.710), "VA": (37.769, -78.170), "WA": (47.400, -121.490),
    "WV": (38.491, -80.954), "WI": (44.268, -89.616), "WY": (42.756, -107.302),
}

US_STATE_ABBR_TO_NAME: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}

# Approximate state bounding boxes: abbr -> (lat_min, lat_max, lon_min, lon_max).
# Border regions can be misclassified; good enough to group wine regions.
US_STATE_BOUNDS: dict[str, tuple[float, float, float, float]] = {
    "AL": (30.14, 35.01, -88.48, -84.89), "AZ": (31.33, 37.01, -114.82, -109.04),
    "AR": (33.00, 36.50, -94.62, -89.64), "CA": (32.53, 42.01, -124.48, -114.13),
    "CO": (36.99, 41.01, -109.07, -102.04), "CT": (40.98, 42.05, -73.73, -71.79),
    "DE": (38.45, 39.84, -75.79, -75.05), "DC": (38.79, 39.00, -77.12, -76.91),
    "FL": (24.52, 31.00, -87.63, -80.03), "GA": (30.36, 35.00, -85.61, -80.84),
    "HI": (18.91, 22.24, -160.25, -154.81), "ID": (41.99, 49.00, -117.24, -111.04),
    "IL": (36.97, 42.51, -91.51, -87.02), "IN": (37.77, 41.76, -88.06, -84.78),
    "IA": (40.38, 43.50, -96.64, -90.14), "KS": (36.99, 40.00, -102.05, -94.59),
    "KY": (36.50, 39.15, -89.57, -81.96), "LA": (28.93, 33.02, -94.04, -88.82),
    "ME": (43.06, 47.46, -71.08, -66.95), "MD": (37.91, 39.72, -79.49, -75.05),
    "MA": (41.24, 42.89, -73.51, -69.93), "MI": (41.70, 48.19, -90.42, -82.41),
    "MN": (43.50, 49.38, -97.24, -89.49), "MS": (30.17, 34.99, -91.66, -88.10),
    "MO": (35.99, 40.61, -95.77, -89.10), "MT": (44.36, 49.00, -116.05, -104.04),
    "NE": (39.99, 43.00, -104.05, -95.31), "NV": (35.00, 42.00, -120.01, -114.04),
    "NH": (42.70, 45.31, -72.56, -70.61), "NJ": (38.93, 41.36, -75.56, -73.89),
    "NM": (31.33, 37.00, -109.05, -103.00), "NY": (40.50, 45.01, -79.76, -71.86),
    "NC": (33.84, 36.59, -84.32, -75.46), "ND": (45.94, 49.00, -104.05, -96.55),
    "OH": (38.40, 42.32, -84.82, -80.52), "OK": (33.62, 37.00, -103.00, -94.43),
    "OR": (41.99, 46.29, -124.57, -116.46), "PA": (39.72, 42.27, -80.52, -74.69),
    "RI": (41.15, 42.02, -71.86, -71.12), "SC": (32.03, 35.22, -83.35, -78.54),
    "SD": (42.48, 45.95, -104.06, -96.44), "TN": (34.98, 36.68, -90.31, -81.65),
    "TX": (25.84, 36.50, -106.65, -93.51), "UT": (36.99, 42.00, -114.05, -109.04),
    "VT": (42.73, 45.02, -73.44, -71.46), "VA": (36.54, 39.47, -83.68, -75.24),
    "WA": (45.54, 49.00, -124.85, -116.92), "WV": (37.20, 40.64, -82.64, -77.72),
    "WI": (42.49, 47.31, -92.89, -86.81), "WY": (40.99, 45.01, -111.06, -104.05),
}


def state_for_point(lat: float | None, lon: float | None) -> str | None:
    """Return the state abbr whose bounding box best contains the point.

    Ties broken by the smallest box (more specific)."""
    if lat is None or lon is None:
        return None
    best: str | None = None
    best_area = 1e9
    for abbr, (la0, la1, lo0, lo1) in US_STATE_BOUNDS.items():
        if la0 <= lat <= la1 and lo0 <= lon <= lo1:
            area = (la1 - la0) * (lo1 - lo0)
            if area < best_area:
                best, best_area = abbr, area
    return best


US_STATE_NAMES: dict[str, str] = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "district of columbia": "DC", "washington dc": "DC", "washington d.c.": "DC",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI",
    "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}

# First digit of a US ZIP -> rough regional center (lat, lon). Coarse, but enough
# to put the map over the right part of the country when a precise match fails.
ZIP1_REGIONS: dict[str, tuple[float, float]] = {
    "0": (42.8, -72.0), "1": (41.2, -75.5), "2": (38.5, -78.0), "3": (31.5, -84.0),
    "4": (40.0, -84.5), "5": (44.5, -92.5), "6": (38.5, -95.0), "7": (32.5, -95.5),
    "8": (39.0, -108.0), "9": (39.0, -121.5),
}

ZIP_RE = re.compile(r"^\s*(\d{5})(?:-\d{4})?\s*$")


def resolve_state(query: str) -> tuple[str, float, float] | None:
    """Return (abbr, lat, lon) if the query names a US state, else None."""
    q = query.strip().lower()
    if q.upper() in US_STATE_CENTROIDS:
        abbr = q.upper()
        lat, lon = US_STATE_CENTROIDS[abbr]
        return abbr, lat, lon
    if q in US_STATE_NAMES:
        abbr = US_STATE_NAMES[q]
        lat, lon = US_STATE_CENTROIDS[abbr]
        return abbr, lat, lon
    return None


def resolve_zip(query: str) -> tuple[str, float, float, bool] | None:
    """Resolve a US ZIP to (zip5, lat, lon, exact).

    ``exact`` is True for a real GeoNames centroid, False for the coarse
    first-digit fallback used when a ZIP isn't in the dataset.
    """
    m = ZIP_RE.match(query or "")
    if not m:
        return None
    zip5 = m.group(1)
    pt = ZIP_CENTROIDS.get(zip5)
    if pt:
        return zip5, pt[0], pt[1], True
    lat, lon = ZIP1_REGIONS.get(zip5[0], (39.5, -98.35))
    return zip5, lat, lon, False


def is_zip(query: str) -> str | None:
    """Return the 5-digit ZIP if the query is one, else None."""
    m = ZIP_RE.match(query or "")
    return m.group(1) if m else None
