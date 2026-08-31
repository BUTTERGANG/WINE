"""Import TTB DSP (Distilled Spirits Plant) data into the distilleries table.

Downloads the COLA Cloud TTB permittee CSV (CC0 licensed) and imports
all Distilled Spirits Plants as Distillery records.

The CSV is updated daily and contains 5,908 active US distilleries
with company name, state, ZIP, and permit type.

Usage:
    python scripts/seed_ttb_distilleries.py
    python scripts/seed_ttb_distilleries.py --limit 100
    python scripts/seed_ttb_distilleries.py --state KY
    python scripts/seed_ttb_distilleries.py --download-only
"""

import asyncio
import csv
import io
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import init_db, async_session
from backend.models.spirit import Distillery
from backend.models.location import Location
from sqlalchemy import select, func, or_

TTB_URL = "https://dyuie4zgfxmt6.cloudfront.net/open-data/permittees.csv"
ROOT = Path(__file__).resolve().parent.parent


async def download_ttb_csv() -> list[dict]:
    """Download the TTB permittee CSV and filter to DSPs."""
    print(f"📥 Downloading TTB permittee data from {TTB_URL}...")
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        resp = await client.get(TTB_URL, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        content = resp.text
        print(f"   Downloaded {len(content):,} bytes")

    # Parse CSV
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    print(f"   Total permittees: {len(rows)}")

    # Filter to Distilled Spirits Plants
    dsp_rows = [r for r in rows if r.get("permittee_type", "").strip() == "Distilled Spirits Plant"]
    print(f"   Distilled Spirits Plants: {len(dsp_rows)}")

    return dsp_rows


async def geocode_zip(zip_code: str) -> tuple[float, float] | None:
    """Simple ZIP centroid lookup."""
    # This is a placeholder — we'd use a ZIP database for accuracy
    # For now, we'll use state centroids
    return None


STATE_CENTROIDS = {
    "AL": (32.8, -86.9), "AK": (61.4, -152.3), "AZ": (34.2, -111.7), "AR": (34.9, -92.4),
    "CA": (36.1, -119.7), "CO": (39.0, -105.5), "CT": (41.6, -72.7), "DE": (39.0, -75.5),
    "DC": (38.9, -77.0), "FL": (28.1, -81.6), "GA": (32.6, -83.4), "HI": (19.7, -155.6),
    "ID": (44.2, -114.2), "IL": (40.0, -89.2), "IN": (40.0, -86.1), "IA": (42.0, -93.4),
    "KS": (38.5, -98.3), "KY": (37.5, -85.0), "LA": (31.2, -91.8), "ME": (44.7, -69.4),
    "MD": (39.0, -76.7), "MA": (42.2, -71.8), "MI": (43.0, -84.5), "MN": (45.6, -94.0),
    "MS": (32.7, -89.6), "MO": (38.4, -92.5), "MT": (46.9, -110.4), "NE": (41.5, -99.7),
    "NV": (38.5, -117.0), "NH": (43.5, -71.6), "NJ": (40.1, -74.6), "NM": (34.5, -106.0),
    "NY": (42.1, -75.5), "NC": (35.5, -79.4), "ND": (47.4, -100.3), "OH": (40.2, -82.8),
    "OK": (35.5, -97.5), "OR": (43.9, -120.6), "PA": (41.2, -77.5), "RI": (41.7, -71.5),
    "SC": (33.9, -80.9), "SD": (44.4, -100.2), "TN": (35.8, -86.3), "TX": (31.0, -100.0),
    "UT": (39.3, -111.7), "VT": (44.0, -72.7), "VA": (37.5, -78.5), "WA": (47.2, -120.5),
    "WV": (38.7, -80.7), "WI": (44.5, -89.5), "WY": (42.9, -107.5),
    "PR": (18.2, -66.6),
}


async def import_dsps(dsp_rows: list[dict], limit: int = 0, state_filter: str = ""):
    """Import DSP rows into the Distillery table."""
    await init_db()
    async with async_session() as s:
        created = 0
        skipped = 0

        # Check if already imported
        existing = (await s.execute(select(func.count()).select_from(Distillery))).scalar() or 0
        if existing > 5000:
            print(f"📊 Already have {existing} distilleries. Skipping import.")
            return

        for i, row in enumerate(dsp_rows):
            if limit and i >= limit:
                break

            state = row.get("company_state", "").strip().upper()
            if state_filter and state != state_filter.upper():
                continue

            name = row.get("company_name", "").strip()
            if not name:
                skipped += 1
                continue

            # Check for duplicates
            result = await s.execute(
                select(Distillery.id).where(Distillery.name == name, Distillery.state_or_region == state)
            )
            if result.first() is not None:
                skipped += 1
                continue

            # Get coordinates (state centroid as fallback)
            lat, lon = STATE_CENTROIDS.get(state, (0, 0))

            dist = Distillery(
                name=name,
                state_or_region=state,
                country="USA",
                lat=lat, lon=lon,
                venue_type="distillery",
                address=f"{state} {row.get('company_zip_code', '')}",
                spirit_types="whiskey",
            )
            s.add(dist)
            created += 1

            if (i + 1) % 500 == 0:
                await s.flush()
                print(f"   Progress: {i+1}/{len(dsp_rows)} ({created} created, {skipped} skipped)")

        await s.commit()
        print(f"\n✅ Imported {created} distilleries ({skipped} skipped)")

        # Update total
        total = (await s.execute(select(func.count()).select_from(Distillery))).scalar() or 0
        print(f"📊 Total distilleries: {total}")


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Max distilleries to import")
    parser.add_argument("--state", type=str, default="", help="Filter by state code")
    parser.add_argument("--download-only", action="store_true", help="Just download, don't import")
    args = parser.parse_args()

    dsp_rows = await download_ttb_csv()

    if args.download_only:
        # Save to CSV for inspection
        out_path = ROOT / "data" / "ttb_distilleries.csv"
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=dsp_rows[0].keys())
            w.writeheader()
            w.writerows(dsp_rows)
        print(f"📄 Saved to {out_path}")
        return

    await import_dsps(dsp_rows, args.limit, args.state)


if __name__ == "__main__":
    asyncio.run(main())