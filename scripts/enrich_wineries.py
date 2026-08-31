"""Enrich wineries by crawling their websites — adapted from business-recon methods.

For each winery with a website:
  - Fetch homepage + contact page
  - Detect site platform (Wix, WordPress, Squarespace, Shopify, custom)
  - Extract social links (Instagram, Facebook, Twitter)
  - Check for online ordering / e-commerce / wine club
  - Detect booking / tasting appointment system
  - SSL validity
  - Staleness signal (copyright year)
  - Extract description/meta tags

Usage:
    python scripts/enrich_wineries.py --crawl 500
    python scripts/enrich_wineries.py --crawl 50 --state CA
    python scripts/enrich_wineries.py --crawl 0  # just check what needs crawling
"""

import asyncio
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import settings
from backend.database import init_db, async_session
from backend.models.location import Location
from sqlalchemy import select, func, or_

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "winery_enrichment.csv"

# Same patterns as business-recon/scripts/deep_recon.py
PLATFORMS = [
    ("wix.com", "Wix"), ("wixstatic", "Wix"),
    ("squarespace", "Squarespace"), ("squarespacecdn", "Squarespace"),
    ("godaddy", "GoDaddy"), ("shopify", "Shopify"),
    ("wp-content", "WordPress"), ("wordpress", "WordPress"),
    ("weebly", "Weebly"), ("square.site", "Square"),
    ("webflow", "Webflow"), ("duda", "Duda"),
    ("googlesites", "Google Sites"), ("wixsite.com", "Wix"),
    ("godaddysites.com", "GoDaddy"),
]

SOCIAL_RE = re.compile(
    r"(?:facebook|instagram|twitter|x)\.com/[A-Za-z0-9_.\-]{2,}", re.I
)

WINE_BOOKING_HINTS = [
    "book a tasting", "book tasting", "schedule tasting", "wine club",
    "join the club", "order wine", "buy wine", "shop wine",
    "tasting appointment", "visit us", "reserve a tasting",
    "calendly", "tock", "opentable", "reserve",
]

WINE_ECOM_HINTS = [
    "add to cart", "checkout", "/product/", "/shop/",
    "wine club", "purchase wine", "buy online", "order online",
    "ship to", "add to bag",
]

# Known USDA/state codes for common winery-looking states
US_STATE_ABBR = {s.upper() for s in [
    "AL","AK","AZ","AR","CA","CO","CT","DE","DC","FL","GA","HI","ID",
    "IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO",
    "MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA",
    "RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY",
]}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


async def check_website(url: str, client: httpx.AsyncClient) -> dict:
    """Check a winery website and return enrichment data."""
    result = {
        "reachable": False,
        "status_code": None,
        "platform": "",
        "ssl_valid": False,
        "socials": [],
        "has_online_ordering": False,
        "has_booking": False,
        "copyright_year": "",
        "title": "",
        "description": "",
        "pages_found": [],
        "notes": [],
    }

    if not url:
        return result

    base = url if url.startswith("http") else "https://" + url
    base = base.rstrip("/")

    try:
        resp = await client.get(base, follow_redirects=True, timeout=15)
        result["status_code"] = resp.status_code
        result["reachable"] = resp.status_code == 200
        result["ssl_valid"] = str(resp.url).startswith("https")

        if resp.status_code == 200 and resp.text:
            html = resp.text
            low = html.lower()

            # Platform detection
            for pat, label in PLATFORMS:
                if pat in low:
                    result["platform"] = label
                    break

            # Title
            m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
            if m:
                result["title"] = re.sub(r"\s+", " ", m.group(1)).strip()[:200]

            # Meta description
            m = re.search(
                r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\'<]+)',
                html, re.I
            )
            if not m:
                m = re.search(
                    r'<meta[^>]+content=["\']([^"\'<]+)["\'][^>]+name=["\']description',
                    html, re.I
                )
            if m:
                result["description"] = m.group(1).strip()[:300]

            # Social links
            socials = SOCIAL_RE.findall(html)
            result["socials"] = list(set(s.split("/")[0] for s in socials))[:5]

            # Copyright year
            m = re.search(r"copyright\s*(?:©|&copy;)?\s*(20\d\d)", low)
            if m:
                result["copyright_year"] = m.group(1)

            # Online ordering / wine club
            for hint in WINE_ECOM_HINTS:
                if hint in low:
                    result["has_online_ordering"] = True
                    break

            # Booking / tasting
            for hint in WINE_BOOKING_HINTS:
                if hint in low:
                    result["has_booking"] = True
                    break

            result["pages_found"].append("home")

            # Try contact page
            try:
                cresp = await client.get(base + "/contact", timeout=10, follow_redirects=True)
                if cresp.status_code == 200:
                    result["pages_found"].append("contact")
                    clow = cresp.text.lower()
                    for hint in WINE_BOOKING_HINTS:
                        if hint in clow:
                            result["has_booking"] = True
                            break
                    for hint in WINE_ECOM_HINTS:
                        if hint in clow:
                            result["has_online_ordering"] = True
                            break
            except Exception:
                pass

            # Try /about
            try:
                aresp = await client.get(base + "/about", timeout=10, follow_redirects=True)
                if aresp.status_code == 200:
                    result["pages_found"].append("about")
            except Exception:
                pass

            # Try /visit
            try:
                vresp = await client.get(base + "/visit", timeout=10, follow_redirects=True)
                if vresp.status_code == 200:
                    result["pages_found"].append("visit")
            except Exception:
                pass

    except httpx.TimeoutException:
        result["notes"].append("timeout")
    except Exception:
        result["notes"].append("unreachable")

    return result


async def crawl_and_enrich(limit: int = 100, state_filter: str = ""):
    """Crawl winery websites and update their DB records."""
    if not httpx:
        print("⚠️  httpx required")
        return

    await init_db()
    async with async_session() as s:
        # Find wineries with websites that haven't been enriched
        query = select(Location).where(
            Location.venue_type == "winery",
            Location.website != "",
            Location.website.isnot(None),
            or_(
                Location.description == "",
                Location.description.is_(None),
                Location.description.ilike("Located in%"),
            )
        )
        if state_filter:
            query = query.where(Location.state_or_region == state_filter.upper())

        query = query.order_by(func.random()).limit(limit)
        result = await s.execute(query)
        wineries = list(result.scalars().all())

        print(f"📊 Crawling {len(wineries)} winery websites...")

        enriched = 0
        errors = 0
        start = time.time()

        async with httpx.AsyncClient(
            headers=HEADERS,
            timeout=httpx.Timeout(15.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            verify=False,
        ) as client:
            for i, w in enumerate(wineries):
                try:
                    data = await check_website(w.website, client)

                    if data["reachable"]:
                        changed = False

                        # Build a rich description
                        desc_parts = []
                        if data["title"] and data["title"] != w.name:
                            pass  # title is usually the winery name, skip
                        if data["description"]:
                            desc_parts.append(data["description"][:200])
                        if data["platform"]:
                            desc_parts.append(f"Built on {data['platform']}")
                        if data["has_online_ordering"]:
                            desc_parts.append("🛒 Online ordering")
                        if data["has_booking"]:
                            desc_parts.append("📅 Book a tasting")
                        if data["socials"]:
                            desc_parts.append(f"Social: {', '.join(data['socials'][:3])}")
                        if data["copyright_year"]:
                            desc_parts.append(f"©{data['copyright_year']}")

                        new_desc = " · ".join(desc_parts)
                        if new_desc and new_desc != w.description:
                            w.description = new_desc[:500]
                            changed = True

                        enriched += 1
                        if changed:
                            pass  # await s.flush() done periodically

                    if (i + 1) % 50 == 0:
                        await s.flush()
                        elapsed = time.time() - start
                        rate = (i + 1) / elapsed
                        eta = (len(wineries) - i - 1) / rate / 60
                        print(f"   {i+1}/{len(wineries)} ({rate:.1f}/s, ETA {eta:.0f}m) — "
                              f"{enriched} enriched, {errors} errors")

                except Exception as e:
                    errors += 1
                    if (i + 1) % 50 == 0:
                        print(f"   {i+1}/{len(wineries)} — {errors} errors so far")

                # Rate limit: 5 req/s
                if (i + 1) % 5 == 0:
                    await asyncio.sleep(0.2)

        await s.commit()
        elapsed = time.time() - start
        print(f"\n✅ Done: {enriched} enriched, {errors} errors, {elapsed:.0f}s")


async def count_unenriched(state_filter: str = ""):
    """Count wineries that need enrichment."""
    await init_db()
    async with async_session() as s:
        query = select(func.count()).select_from(Location).where(
            Location.venue_type == "winery",
            Location.website != "",
            Location.website.isnot(None),
            or_(
                Location.description == "",
                Location.description.is_(None),
                Location.description.ilike("Located in%"),
            )
        )
        if state_filter:
            query = query.where(Location.state_or_region == state_filter.upper())
        count = (await s.execute(query)).scalar() or 0

        total = (await s.execute(
            select(func.count()).select_from(Location).where(
                Location.venue_type == "winery",
                Location.website != "",
                Location.website.isnot(None),
            )
        )).scalar() or 0

        print(f"📊 Wineries with websites: {total}")
        print(f"📊 Need enrichment: {count}")
        print(f"✅ Already enriched: {total - count}")


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--crawl", type=int, default=0, help="Number of wineries to crawl websites")
    parser.add_argument("--state", type=str, default="", help="Filter by state (CA, OR, etc.)")
    parser.add_argument("--count", action="store_true", help="Just count unenriched wineries")
    parser.add_argument("--google-enrich", type=int, default=0, help="Enrich N wineries via Google Places")
    parser.add_argument("--google-search", type=str, default="", help="Search Google Places for wineries")
    parser.add_argument("--radius", type=int, default=50000, help="Search radius in meters for Google Places")
    args = parser.parse_args()

    if args.count:
        await count_unenriched(args.state)
    elif args.crawl:
        await crawl_and_enrich(args.crawl, args.state)
    elif args.google_enrich:
        await _google_enrich(args.google_enrich)
    elif args.google_search:
        await _google_search_and_import(args.google_search, args.radius)
    else:
        parser.print_help()


# ── Google Places enrichment (from previous version) ──


async def _google_search(query: str, radius: int = 50000) -> list[dict]:
    """Search Google Places for wineries near a location."""
    from backend.config import settings
    key = settings.google_maps_api_key
    if not key:
        print("⚠️  No GOOGLE_MAPS_API_KEY set in .env")
        return []

    print(f"🔍 Searching Google Places for: '{query}' (radius={radius}m)")
    async with httpx.AsyncClient(timeout=10) as client:
        geo = await client.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": query, "key": key},
        )
        if geo.status_code != 200 or not geo.json().get("results"):
            print(f"   Could not geocode: {query}")
            return []
        loc = geo.json()["results"][0]["geometry"]["location"]
        print(f"   Centered on: {loc['lat']:.4f}, {loc['lng']:.4f}")

        all_results = []
        next_token = None
        for page in range(3):
            params = {
                "location": f"{loc['lat']},{loc['lng']}",
                "radius": radius,
                "type": "point_of_interest",
                "keyword": "winery",
                "key": key,
            }
            if next_token:
                params["pagetoken"] = next_token
                await asyncio.sleep(2)
            resp = await client.get(
                "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
                params=params, timeout=15,
            )
            if resp.status_code != 200:
                break
            data = resp.json()
            results = data.get("results", [])
            all_results.extend(results)
            next_token = data.get("next_page_token")
            if not next_token:
                break
        print(f"   Total found: {len(all_results)}")
        return all_results


async def _google_enrich_winery(winery, api_key: str) -> bool:
    """Enrich a single winery with Google Places data."""
    if not api_key or winery.website:
        return False
    query = f"{winery.name} winery {winery.state_or_region or ''}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://maps.googleapis.com/maps/api/place/findplacefromtext/json",
            params={
                "input": query,
                "inputtype": "textquery",
                "fields": "place_id,name,formatted_address,geometry,rating,user_ratings_total,website,formatted_phone_number",
                "key": api_key,
            },
        )
        if resp.status_code != 200:
            return False
        candidates = resp.json().get("candidates", [])
        if not candidates:
            return False
        c = candidates[0]
        changed = False
        if c.get("website") and not winery.website:
            winery.website = c["website"]
            changed = True
        if c.get("formatted_phone_number") and not winery.phone:
            winery.phone = c["formatted_phone_number"]
            changed = True
        if c.get("rating") and not winery.description:
            total = c.get("user_ratings_total", 0)
            winery.description = f"⭐ {c['rating']}/5 ({total} reviews)" if total else f"⭐ {c['rating']}/5"
            changed = True
        return changed


async def _google_enrich(limit: int):
    """Enrich existing wineries with Google Places data."""
    from backend.config import settings
    key = settings.google_maps_api_key
    if not key:
        print("⚠️  No GOOGLE_MAPS_API_KEY set in .env")
        return
    await init_db()
    async with async_session() as s:
        result = await s.execute(
            select(Location)
            .where(Location.venue_type == "winery", Location.website == "")
            .limit(limit)
        )
        wineries = list(result.scalars().all())
        print(f"📊 Enriching up to {len(wineries)} wineries from Google Places...")
        enriched = 0
        for i, w in enumerate(wineries):
            ok = await _google_enrich_winery(w, key)
            if ok:
                enriched += 1
            if (i + 1) % 50 == 0:
                await s.flush()
                print(f"   Progress: {i+1}/{len(wineries)} ({enriched} enriched)")
        await s.commit()
        print(f"✅ Enriched {enriched} wineries with Google Places data")


async def _google_search_and_import(query: str, radius: int = 50000):
    """Search Google Places for wineries and import them into the DB."""
    from backend.config import settings
    key = settings.google_maps_api_key
    if not key:
        print("⚠️  No GOOGLE_MAPS_API_KEY set in .env")
        return
    results = await _google_search(query, radius)
    if not results:
        return
    await init_db()
    async with async_session() as s:
        imported = 0
        skipped = 0
        for place in results:
            name = place.get("name", "").strip()
            if not name:
                skipped += 1
                continue
            lat = place["geometry"]["location"]["lat"]
            lng = place["geometry"]["location"]["lng"]
            existing = await s.execute(
                select(Location.id).where(
                    Location.name == name,
                    Location.lat >= lat - 0.02,
                    Location.lat <= lat + 0.02,
                    Location.lon >= lng - 0.02,
                    Location.lon <= lng + 0.02,
                )
            )
            if existing.first() is not None:
                skipped += 1
                continue
            address = place.get("vicinity", "")
            rating = place.get("rating")
            total = place.get("user_ratings_total")
            desc = f"⭐ {rating}/5 ({total} reviews)" if rating else ""
            loc = Location(
                name=name, address=address, lat=lat, lon=lng,
                venue_type="winery", description=desc,
            )
            for part in address.split(","):
                part = part.strip()
                if len(part) == 2 and part.isupper():
                    loc.state_or_region = part
                    break
            s.add(loc)
            imported += 1
        await s.commit()
        print(f"✅ Imported {imported} new wineries from Google ({skipped} skipped)")


if __name__ == "__main__":
    asyncio.run(main())