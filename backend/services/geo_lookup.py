"""Offline place lookup — resolve a state name/abbreviation or US ZIP to a
map location. No network required; used to fly the map to a search target."""

from __future__ import annotations

import re

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


def zip_prefix_region(query: str) -> tuple[str, float, float] | None:
    """Return (zip5, lat, lon) using the ZIP's first-digit region, else None."""
    m = ZIP_RE.match(query or "")
    if not m:
        return None
    zip5 = m.group(1)
    lat, lon = ZIP1_REGIONS.get(zip5[0], (39.5, -98.35))
    return zip5, lat, lon


def is_zip(query: str) -> str | None:
    """Return the 5-digit ZIP if the query is one, else None."""
    m = ZIP_RE.match(query or "")
    return m.group(1) if m else None
