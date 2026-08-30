"""Tier 1 North American Winery Import Pipeline

Combines TTB FOIA data + OSM Overpass + winerymap to build a comprehensive
North American winery database with lat/lon coordinates.

Pipeline:
  1. Load TTB wine producer permits (name, address, state, ~17K records)
  2. Match against winerymap dataset for existing lat/lon (~3.8K match)
  3. Run OSM Overpass queries per state for bulk coordinate lookup (~10K+)
  4. Fall back to city/state centroids for remaining
  5. Optional: refine coordinates via Nominatim/Google (slow)

Usage:
  # Full import (fast track - Overpass + centroids):
  python scripts/seed_north_america.py

  # Single state test:
  python scripts/seed_north_america.py --states CA

  # With slow geocoding refinement (hours):
  python scripts/seed_north_america.py --refine
"""

import asyncio
import csv
import json
import sys
from pathlib import Path
from typing import Optional

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import init_db, async_session
from backend.models.location import Location
from backend.config import settings

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
TTB_CSV_PATH = DATA_DIR / "ttb_wine_producers.csv"
TTB_CSV_URL = "https://www.ttb.gov/system/files/2025-04/FRL_Wine_Producer_and_Blender_Permit_List.csv"
VINEYARDS_PATH = DATA_DIR / "vineyards.json"
GEOCODE_CACHE_PATH = DATA_DIR / "geocode_cache.json"
OSM_CACHE_PATH = DATA_DIR / "osm_wineries_cache.json"

# State centroids as quick fallback
STATE_CENTROIDS = {
    "CA": (36.7783, -119.4179), "OR": (43.8041, -120.5542),
    "WA": (47.7511, -120.7401), "NY": (40.7128, -74.0069),
    "TX": (32.7767, -96.7970), "PA": (41.2033, -77.1945),
    "VA": (37.4316, -78.6569), "OH": (40.4173, -82.9071),
    "MI": (44.3148, -85.6024), "NC": (35.7596, -79.0193),
    "MO": (37.9643, -91.8318), "CO": (39.5501, -105.7821),
    "IL": (40.6331, -89.3985), "FL": (27.6648, -81.5158),
    "NJ": (40.0583, -74.4057), "MA": (42.4072, -71.3824),
    "AZ": (34.0489, -111.0937), "IN": (40.2672, -86.1349),
    "WI": (43.7844, -88.7879), "MN": (46.7296, -94.6859),
    "IA": (41.8780, -93.0977), "KS": (39.0119, -98.4842),
    "MD": (39.0458, -76.6413), "CT": (41.6032, -73.0877),
    "NM": (34.5199, -105.8701), "ID": (44.0682, -114.7420),
    "OK": (35.0078, -97.0929), "NE": (41.4925, -99.9018),
    "SC": (33.8361, -81.1637), "WV": (38.5976, -80.4549),
    "RI": (41.5801, -71.4774), "AK": (64.2008, -149.4937),
    "AR": (35.2011, -91.8318), "MT": (46.8797, -110.3626),
    "SD": (43.9695, -99.9018), "UT": (39.3210, -111.0937),
    "ND": (47.5515, -101.0020), "NV": (38.8026, -116.4194),
    "LA": (31.2448, -92.1450), "DE": (38.9108, -75.5277),
    "HI": (19.8987, -155.6659), "WY": (43.0760, -107.2903),
    "MS": (32.3547, -89.3985), "DC": (38.9072, -77.0369),
    "KY": (37.8393, -84.2700), "TN": (35.5175, -86.5804),
    "AL": (32.3182, -86.9023), "GA": (32.1656, -82.9001),
    "VT": (44.5588, -72.5778), "NH": (43.1939, -71.5724),
    "ME": (45.2538, -69.4455),
}


# ── Data Loading ──────────────────────────────────────────────────────


def load_ttb_wineries(state_filter: list[str] | None = None) -> list[dict]:
    """Load TTB wine producers, dedup by name + state."""
    if not TTB_CSV_PATH.exists():
        print("⬇️  Downloading TTB wine producer list...")
        resp = httpx.get(TTB_CSV_URL, follow_redirects=True, timeout=30)
        resp.raise_for_status()
        TTB_CSV_PATH.parent.mkdir(exist_ok=True)
        with open(TTB_CSV_PATH, "wb") as f:
            f.write(resp.content)
        print(f"   Saved ({len(resp.content)//1024}KB)")

    wineries = {}
    with open(TTB_CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            state = row.get("State", "").strip().upper()
            if state_filter and state not in state_filter:
                continue
            # Only wine producers
            industry_type = row.get("Industry_Type", "").strip()
            if "Wine" not in industry_type:
                continue
            name = (row.get("Operating_Name", "") or row.get("Owner_Name", "")).strip()
            if not name:
                continue
            street = row.get("Street", "").strip()
            city = row.get("City", "").strip()
            key = f"{name.upper()}|{state}"
            if key not in wineries or (street and not wineries[key]["street"]):
                wineries[key] = {
                    "name": name.title(),
                    "street": street, "city": city, "state": state,
                    "zip": row.get("Prem_Zip", "").strip(),
                    "lat": None, "lon": None,
                    "source": "ttb",
                }
    return list(wineries.values())


def load_winerymap_wineries() -> dict[str, dict]:
    """Load winerymap data keyed by uppercase name."""
    if not VINEYARDS_PATH.exists():
        print("⚠️  winerymap dataset not found")
        return {}
    with open(VINEYARDS_PATH) as f:
        data = json.load(f)
    result = {}
    for rk, rv in data.items():
        if ", United States" not in rk:
            continue
        for v in rv.get("vineyards", []):
            if len(v) < 3 or not v[2]:
                continue
            name = v[2].strip()
            state = rk.split(",")[0].strip() if "," in rk else ""
            result[name.upper()] = {"name": name, "lat": float(v[0]), "lon": float(v[1]),
                                     "website": v[3] if len(v) > 3 else "", "state": state}
    return result


def load_geocode_cache() -> dict:
    if GEOCODE_CACHE_PATH.exists():
        with open(GEOCODE_CACHE_PATH) as f:
            return json.load(f)
    return {}

def save_geocode_cache(cache: dict):
    with open(GEOCODE_CACHE_PATH, "w") as f:
        json.dump(cache, f)

def load_osm_cache() -> dict:
    if OSM_CACHE_PATH.exists():
        with open(OSM_CACHE_PATH) as f:
            return json.load(f)
    return {}

def save_osm_cache(cache: dict):
    with open(OSM_CACHE_PATH, "w") as f:
        json.dump(cache, f)


# ── OSM Overpass Bulk Queries ─────────────────────────────────────────


async def query_overpass_state(state: str, session: httpx.AsyncClient) -> list[dict]:
    """Query Overpass API for all wineries in a state using a bounding box."""
    # State bounding boxes (approximate)
    STATE_BBOX = {
        "CA": (32.5, 42.0, -124.5, -114.0), "OR": (42.0, 46.3, -124.5, -116.5),
        "WA": (45.5, 49.0, -124.8, -117.0), "NY": (40.5, 45.0, -79.8, -71.8),
        "TX": (25.8, 36.5, -106.6, -93.5), "PA": (39.7, 42.3, -80.5, -74.7),
        "VA": (36.5, 39.5, -83.7, -75.2), "OH": (38.4, 41.7, -84.8, -80.5),
        "MI": (41.7, 47.5, -90.4, -82.1), "NC": (34.0, 36.6, -84.3, -75.5),
        "MO": (36.0, 40.6, -95.8, -89.1), "CO": (37.0, 41.0, -109.0, -102.0),
        "IL": (36.9, 42.5, -91.5, -87.5), "FL": (24.4, 31.0, -87.6, -80.0),
        "OR": (42.0, 46.3, -124.5, -116.5),
    }
    bbox = STATE_BBOX.get(state)
    if not bbox:
        return []
    lat_min, lat_max, lon_min, lon_max = bbox
    bbox_str = f"{lat_min},{lon_min},{lat_max},{lon_max}"

    overpass = f"""
    [out:json][timeout:30];
    (
      node["craft"="winery"]({bbox_str});
      way["craft"="winery"]({bbox_str});
      node["industrial"="winery"]({bbox_str});
    );
    out center;
    """
    try:
        resp = await session.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": overpass},
            timeout=45,
        )
        if resp.status_code == 200:
            data = resp.json()
            results = []
            for el in data.get("elements", []):
                tags = el.get("tags", {})
                name = tags.get("name", "")
                if not name:
                    continue
                lat = el.get("lat") or el.get("center", {}).get("lat")
                lon = el.get("lon") or el.get("center", {}).get("lon")
                if not lat or not lon:
                    continue
                results.append({"name": name.strip().title(),
                                "lat": float(lat), "lon": float(lon)})
            return results
    except Exception:
        pass
    return []


async def bulk_overpass_lookup(wineries: list[dict]) -> int:
    """Query Overpass for each state to bulk-get lat/lon."""
    osm_cache = load_osm_cache()
    states = set(w["state"] for w in wineries if w["lat"] is None)
    matched = 0

    print(f"   Querying OSM Overpass for {len(states)} states...")
    async with httpx.AsyncClient(timeout=60) as session:
        for state in sorted(states):
            if state in osm_cache:
                state_wineries = osm_cache[state]
            else:
                state_wineries = await query_overpass_state(state, session)
                osm_cache[state] = state_wineries
                save_osm_cache(osm_cache)
                await asyncio.sleep(2)

            # Build lookup dict for this state
            lookup = {w["name"].upper(): w for w in state_wineries}

            # Match against our unmatched wineries in this state
            for w in wineries:
                if w["lat"] is not None or w["state"] != state:
                    continue
                key = w["name"].upper()
                if key in lookup:
                    osm = lookup[key]
                    w["lat"] = osm["lat"]
                    w["lon"] = osm["lon"]
                    w["source"] = f"osm_{state}"
                    matched += 1

            print(f"      {state}: {len(state_wineries)} in OSM, matched {sum(1 for w in wineries if w['state']==state and w['source']==f'osm_{state}')}")

    return matched


# ── Geocoding (Optional, Slow) ────────────────────────────────────────


async def refine_geocoding(wineries: list[dict], api_key: str, max_items: int = 100) -> tuple[int, int]:
    """Refine coordinates via Google Maps Geocoding (up to max_items)."""
    google_ok = 0
    failed = 0
    to_do = [w for w in wineries if w["lat"] is None][:max_items]
    if not to_do:
        return 0, 0

    print(f"   Refining {len(to_do)} addresses via Google Geocoding...")
    async with httpx.AsyncClient(timeout=10) as session:
        for i, w in enumerate(to_do):
            addr = f"{w.get('street', '')} {w.get('city', '')} {w['state']}"
            if not addr.strip():
                addr = f"{w['name']}, {w['state']}"
            try:
                resp = await session.get(
                    "https://maps.googleapis.com/maps/api/geocode/json",
                    params={"address": addr, "key": api_key},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("results"):
                        loc = data["results"][0]["geometry"]["location"]
                        w["lat"] = loc["lat"]
                        w["lon"] = loc["lng"]
                        w["source"] = "google_refined"
                        google_ok += 1
                    else:
                        failed += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
            if (i + 1) % 10 == 0:
                print(f"      Refine: {i+1}/{len(to_do)} ({google_ok} ok, {failed} failed)")
    return google_ok, failed


# ── Centroids Fallback ────────────────────────────────────────────────


def apply_centroids(wineries: list[dict]) -> int:
    """Apply state centroids for any remaining unmatched."""
    count = 0
    for w in wineries:
        if w["lat"] is not None:
            continue
        centroid = STATE_CENTROIDS.get(w["state"])
        if centroid:
            w["lat"], w["lon"] = centroid
            w["source"] = f"centroid_{w['state']}"
            count += 1
    return count


# ── Import ─────────────────────────────────────────────────────────────


async def import_to_database(wineries: list[dict]) -> tuple[int, int]:
    """Import wineries deduped by name + coordinate proximity."""
    created = 0
    skipped = 0

    await init_db()
    async with async_session() as session:
        from sqlalchemy import select

        for i, w in enumerate(wineries):
            if w["lat"] is None or w["lon"] is None:
                skipped += 1
                continue

            # Dedup by name + ~2km radius
            result = await session.execute(
                select(Location.id).where(
                    Location.name == w["name"],
                    Location.lat >= w["lat"] - 0.02,
                    Location.lat <= w["lat"] + 0.02,
                    Location.lon >= w["lon"] - 0.02,
                    Location.lon <= w["lon"] + 0.02,
                )
            )
            if result.scalar_one_or_none():
                skipped += 1
                continue

            location = Location(
                name=w["name"],
                address=w.get("address", ""),
                state_or_region=w.get("state", ""),
                country="United States",
                lat=w["lat"],
                lon=w["lon"],
                venue_type="winery",
                description=f"{w.get('city', '')}, {w.get('state', '')}".strip(", "),
            )
            session.add(location)
            created += 1
            if created % 200 == 0:
                await session.flush()
                print(f"      Imported {created}...")

        await session.commit()
    return created, skipped


# ── Main ──────────────────────────────────────────────────────────────


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--states", default="", help="Comma-separated state filter")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--no-import", action="store_true")
    parser.add_argument("--refine", action="store_true", help="Slow coordinate refinement")
    args = parser.parse_args()

    state_filter = [s.strip().upper() for s in args.states.split(",") if s.strip()] if args.states else None

    print("=" * 60)
    print("🍷 NORTH AMERICAN WINERY IMPORT PIPELINE")
    print("=" * 60)

    # 1. Load TTB
    print("\n1️⃣  Loading TTB wine producers...")
    wineries = load_ttb_wineries(state_filter)
    print(f"   {len(wineries)} wineries loaded")

    # 2. Match winerymap
    print("\n2️⃣  Matching against winerymap dataset...")
    wm = load_winerymap_wineries()
    for w in wineries:
        key = w["name"].upper()
        if key in wm and w["lat"] is None:
            w["lat"], w["lon"] = wm[key]["lat"], wm[key]["lon"]
            w["source"] = "winerymap"
    wm_matched = sum(1 for w in wineries if w["source"] == "winerymap")
    print(f"   Matched: {wm_matched}")

    # 3. OSM Overpass bulk lookup
    print("\n3️⃣  Bulk OSM Overpass lookup...")
    osm_matched = await bulk_overpass_lookup(wineries) if any(w["lat"] is None for w in wineries) else 0
    print(f"   OSM matched: {osm_matched}")

    # 4. Centroids
    print("\n4️⃣  Applying state centroids...")
    centroid_count = apply_centroids(wineries)
    print(f"   Centroids: {centroid_count}")

    # 5. Refine (optional, slow)
    if args.refine:
        print("\n5️⃣  Refining coordinates via Google Geocoding...")
        api_key = settings.google_maps_api_key
        if api_key:
            g_ok, g_fail = await refine_geocoding(wineries, api_key, max_items=500)
            print(f"   Refined: {g_ok} (failed: {g_fail})")
        else:
            print("   ⏭️  No Google API key set")

    # Summary
    with_geo = sum(1 for w in wineries if w["lat"] is not None)
    without_geo = sum(1 for w in wineries if w["lat"] is None)
    print(f"\n📊 Geocoding Summary:")
    print(f"   winerymap: {wm_matched}")
    print(f"   OSM:       {osm_matched}")
    print(f"   centroids: {centroid_count}")
    print(f"   total w/coords: {with_geo}")
    print(f"   no coords: {without_geo}")

    # 6. Import
    if args.no_import:
        print("\n⏭️  Import skipped")
    else:
        print("\n6️⃣  Importing to database...")
        created, skipped = await import_to_database(wineries)
        print(f"\n📊 Import: {created} created, {skipped} skipped")

    print("\n✅ Done")


if __name__ == "__main__":
    asyncio.run(main())