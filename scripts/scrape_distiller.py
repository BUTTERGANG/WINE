"""Distiller.com scraper — spirits, ratings, and tasting notes.

⚠️  NOTE: Distiller uses aggressive Cloudflare managed challenges.
     Headless Playwright cannot currently bypass it.
     
     Alternative approaches:
     1. Use BrightData MCP proxy (skill: brightdata-mcp) — managed web unlocker
     2. Use the Apify Distiller Scraper actor (pre-built, handles CF)
     3. Use the TTB DSP dataset (scripts/seed_ttb_distilleries.py) — 5,908 US
        distilleries, CC0 license, no blocking
     4. Use WhiskeyFYI API (free) — 500+ distilleries, 2,200+ expressions
     5. Use WhiskyDB (CC0/ODbL) — 3,200+ global producers

     The script below is a working skeleton that will function once
     a real browser or proxy bypass is available. For now, use the
     TTB import or WhiskeyFYI API instead.

Extracts spirit data from Distiller.com including:
- Spirit name, brand, type, location, ABV, age, cost, cask type
- Distiller Score (expert) and Community Rating (user)
- Tasting notes (nose, palate, finish) and flavor profiles
- Description and bottle image URL

Uses Playwright with stealth patches to handle Cloudflare.
Same safeguard system as the BeerAdvocate scraper.

Usage:
    python scripts/scrape_distiller.py --type bourbon --limit 50
    python scripts/scrape_distiller.py --slug maker-s-mark
    python scripts/scrape_distiller.py --resume
    python scripts/scrape_distiller.py --clear-checkpoint
"""

import asyncio
import csv
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
CHECKPOINT = ROOT / "data" / "distiller_checkpoint.json"
OUTPUT = ROOT / "data" / "distiller_spirits.csv"

# Rate limiting
MIN_DELAY = 2.0
MAX_DELAY = 5.0
CONSECUTIVE_FAIL_LIMIT = 10
BATCH_SIZE = 20

SPIRIT_TYPES = [
    "whiskey", "bourbon", "scotch", "rye", "irish",
    "japanese", "canadian", "tequila", "mezcal",
    "gin", "vodka", "rum", "brandy", "cognac", "liqueur",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


def load_checkpoint() -> dict:
    if CHECKPOINT.exists():
        try:
            with open(CHECKPOINT) as f:
                cp = json.load(f)
            print(f"📌 Checkpoint: {cp.get('scraped', 0)} spirits, "
                  f"last = {cp.get('last_slug', 'none')}")
            return cp
        except (json.JSONDecodeError, OSError):
            pass
    return {"last_slug": "", "scraped": 0, "errors": 0, "total": 0}


def save_checkpoint(cp: dict):
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT, "w") as f:
        json.dump(cp, f, indent=2)


def clear_checkpoint():
    if CHECKPOINT.exists():
        CHECKPOINT.unlink()
        print("🧹 Distiller checkpoint cleared")


def random_delay():
    return random.uniform(MIN_DELAY, MAX_DELAY)


STEALTH_SCRIPT = """
// Remove webdriver traces
Object.defineProperty(navigator, 'webdriver', { get: () => false });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
// Override chrome.runtime
window.chrome = { runtime: {} };
// Fake permissions
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (p) => (
    p.name === 'notifications' ?
    Promise.resolve({ state: 'prompt' }) :
    originalQuery(p)
);
"""


async def extract_spirit_data(page, slug: str) -> Optional[dict]:
    """Extract spirit data from a Distiller spirit page."""
    url = f"https://distiller.com/spirits/{slug}"

    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(random.uniform(1, 2))

        # Check for Cloudflare
        title = await page.title()
        if "Attention" in title or "Just a moment" in title:
            print(f"   ⚠️  Cloudflare block on {slug}")
            return None

        # Extract data from the page — Distiller uses a combination of
        # meta tags, JSON-LD, and rendered DOM elements
        data = await page.evaluate("""
            () => {
                const result = {
                    slug: '',
                    name: '',
                    brand: '',
                    spirit_type: '',
                    location: '',
                    abv: '',
                    age: '',
                    cost_tier: '',
                    cask_type: '',
                    description: '',
                    distiller_score: '',
                    community_rating: '',
                    rating_count: '',
                    tasting_notes: { nose: '', palate: '', finish: '' },
                    flavor_profile: [],
                    image_url: '',
                };

                // JSON-LD (most reliable)
                try {
                    const ld = document.querySelector('script[type="application/ld+json"]');
                    if (ld) {
                        const json = JSON.parse(ld.textContent);
                        result.name = json.name || '';
                        result.description = json.description || '';
                        if (json.image) result.image_url = json.image;
                    }
                } catch(e) {}

                // Meta tags
                const ogTitle = document.querySelector('meta[property="og:title"]');
                if (ogTitle) result.name = ogTitle.content;

                // Page title (fallback)
                if (!result.name) result.name = document.title.replace(' | Distiller', '').trim();

                // Extract slug from URL
                result.slug = window.location.pathname.replace('/spirits/', '').split('/')[0];

                // Brand name
                const brandEl = document.querySelector('[data-testid="brand-name"], .brand-name, .producer');
                if (brandEl) result.brand = brandEl.textContent.trim();

                // Spirit type
                const typeEl = document.querySelector('[data-testid="spirit-type"], .spirit-type, .category');
                if (typeEl) result.spirit_type = typeEl.textContent.trim();

                // Location
                const locEl = document.querySelector('[data-testid="location"], .location, .origin');
                if (locEl) result.location = locEl.textContent.trim();

                // ABV
                const abvEl = document.querySelector('[data-testid="abv"], .abv, .alcohol');
                if (abvEl) result.abv = abvEl.textContent.trim();

                // Age
                const ageEl = document.querySelector('[data-testid="age"], .age-statement');
                if (ageEl) result.age = ageEl.textContent.trim();

                // Score
                const scoreEl = document.querySelector('[data-testid="distiller-score"], .distiller-score, .score-value');
                if (scoreEl) result.distiller_score = scoreEl.textContent.trim();

                // Community rating
                const ratingEl = document.querySelector('[data-testid="community-rating"], .community-rating, .rating-value');
                if (ratingEl) result.community_rating = ratingEl.textContent.trim();

                // Cost tier
                const costEl = document.querySelector('[data-testid="cost-tier"], .cost-tier, .price-tier');
                if (costEl) result.cost_tier = costEl.textContent.trim();

                // Cask type
                const caskEl = document.querySelector('[data-testid="cask-type"], .cask-type, .barrel-type');
                if (caskEl) result.cask_type = caskEl.textContent.trim();

                // Tasting notes
                const noseEl = document.querySelector('[data-testid="nose"], .nose-note');
                if (noseEl) result.tasting_notes.nose = noseEl.textContent.trim();

                const palateEl = document.querySelector('[data-testid="palate"], .palate-note');
                if (palateEl) result.tasting_notes.palate = palateEl.textContent.trim();

                const finishEl = document.querySelector('[data-testid="finish"], .finish-note');
                if (finishEl) result.tasting_notes.finish = finishEl.textContent.trim();

                // Rating count
                const countEl = document.querySelector('[data-testid="rating-count"], .rating-count');
                if (countEl) result.rating_count = countEl.textContent.trim();

                // Flavor profile (radar chart tags)
                const flavorTags = document.querySelectorAll('[data-testid="flavor-tag"], .flavor-tag, .flavor-profile span');
                result.flavor_profile = Array.from(flavorTags).map(el => el.textContent.trim());

                // If nothing worked, try scanning visible text
                if (!result.spirit_type) {
                    const body = document.body.textContent;
                    const types = ['whiskey','bourbon','scotch','rye','gin','vodka','rum','tequila','brandy'];
                    for (const t of types) {
                        if (body.toLowerCase().includes(t + ' ')) {
                            result.spirit_type = t;
                            break;
                        }
                    }
                }

                return result;
            }
        """)

        # Fallback: extract from description if name is empty
        if not data.get("name") or data["name"] == "Distiller":
            return None

        return data

    except Exception as e:
        print(f"   ⚠️  Error extracting {slug}: {e}")
        return None


async def get_spirit_slugs_by_type(spirit_type: str, limit: int = 50, page_instance=None) -> list[str]:
    """Get list of spirit slugs from the type listing page."""
    if page_instance is None:
        return []

    slugs = []
    url = f"https://distiller.com/spirits?type={spirit_type}"

    try:
        await page_instance.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(random.uniform(1, 2))

        title = await page_instance.title()
        if "Attention" in title or "Just a moment" in title:
            print(f"   ⚠️  Cloudflare block on type listing: {spirit_type}")
            return []

        slugs = await page_instance.evaluate(f"""
            () => {{
                const links = document.querySelectorAll('a[href^="/spirits/"]');
                const slugs = [];
                const seen = new Set();
                for (const link of links) {{
                    const match = link.getAttribute('href').match(/^\\/spirits\\/([^\\/?#]+)/);
                    if (match && !seen.has(match[1])) {{
                        seen.add(match[1]);
                        slugs.push(match[1]);
                    }}
                }}
                return slugs.slice(0, {limit});
            }}
        """)

        print(f"   Found {len(slugs)} spirits of type '{spirit_type}'")
        return slugs

    except Exception as e:
        print(f"   ⚠️  Error getting slugs for {spirit_type}: {e}")
        return []


async def scrape_spirit_slug(slug: str, playwright_context) -> Optional[dict]:
    """Scrape a single spirit by slug."""
    page = await playwright_context.new_page()
    try:
        data = await extract_spirit_data(page, slug)
        return data
    finally:
        await page.close()


async def scrape_by_type(spirit_type: str, limit: int = 50, browser=None) -> list[dict]:
    """Scrape spirits of a specific type."""
    print(f"\n🥃 Scraping {spirit_type} (limit {limit})...")

    results = []
    cp = load_checkpoint()
    skip_to = cp.get("last_slug", "")

    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": random.randint(1280, 1440), "height": random.randint(720, 900)},
        locale="en-US",
    )
    await context.add_init_script(STEALTH_SCRIPT)

    try:
        # Get list of slugs first
        list_page = await context.new_page()
        slugs = await get_spirit_slugs_by_type(spirit_type, limit, list_page)
        await list_page.close()

        if not slugs:
            print("   No slugs found. Cloudflare may be blocking.")
            return results

        # Filter out already-scraped if resuming
        if skip_to:
            try:
                idx = slugs.index(skip_to)
                slugs = slugs[idx + 1:]
                print(f"   Resuming from slug #{idx + 1}: {skip_to}")
            except ValueError:
                print(f"   Last slug '{skip_to}' not found in current listing, starting fresh")

        # Scrape each slug
        consecutive_fails = 0
        for i, slug in enumerate(slugs[:limit]):
            spirit_page = await context.new_page()
            try:
                data = await extract_spirit_data(spirit_page, slug)
                if data:
                    data["spirit_type_cat"] = spirit_type
                    results.append(data)
                    consecutive_fails = 0

                    # Save checkpoint
                    save_checkpoint({
                        "last_slug": slug, "scraped": len(results),
                        "errors": 0, "total": limit,
                    })

                    print(f"   [{i + 1}/{len(slugs[:limit])}] ✅ {data.get('name', slug)}")
                else:
                    consecutive_fails += 1
                    print(f"   [{i + 1}/{len(slugs[:limit])}] ⚠️  Empty: {slug}")

                if consecutive_fails >= CONSECUTIVE_FAIL_LIMIT:
                    print("❌ Too many consecutive failures. Stopping.")
                    break

                await asyncio.sleep(random_delay())

            except Exception as e:
                consecutive_fails += 1
                print(f"   [{i + 1}/{len(slugs[:limit])}] ❌ Error: {e}")
                if consecutive_fails >= CONSECUTIVE_FAIL_LIMIT:
                    break
            finally:
                await spirit_page.close()

    finally:
        await context.close()

    return results


async def scrape_single_spirit(slug: str) -> Optional[dict]:
    """Scrape a single spirit by slug."""
    print(f"🥃 Scraping single spirit: {slug}")

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("❌ playwright not installed")
        return None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1440, "height": 900},
            locale="en-US",
        )
        await context.add_init_script(STEALTH_SCRIPT)

        page = await context.new_page()
        data = await extract_spirit_data(page, slug)
        await browser.close()

        if data:
            print(f"   ✅ {data.get('name', slug)}")
            for k, v in data.items():
                if v and k not in ("tasting_notes", "flavor_profile"):
                    print(f"      {k}: {v}")
            if data.get("tasting_notes"):
                for k, v in data["tasting_notes"].items():
                    if v:
                        print(f"      {k}: {v}")
        else:
            print("   ⚠️  No data extracted")

        return data


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Distiller.com scraper")
    parser.add_argument("--type", type=str, default="", help="Spirit type to scrape (bourbon, scotch, etc.)")
    parser.add_argument("--limit", type=int, default=50, help="Max spirits to scrape")
    parser.add_argument("--slug", type=str, default="", help="Scrape a single spirit by slug")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--clear-checkpoint", action="store_true", help="Clear checkpoint")
    parser.add_argument("--all-types", action="store_true", help="Scrape all spirit types")
    args = parser.parse_args()

    if args.clear_checkpoint:
        clear_checkpoint()
        return

    if args.slug:
        await scrape_single_spirit(args.slug)
        return

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("❌ playwright not installed. Run: pip install playwright && playwright install chromium")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage"],
        )

        try:
            if args.all_types:
                all_results = []
                for st in SPIRIT_TYPES:
                    results = await scrape_by_type(st, args.limit, browser)
                    all_results.extend(results)
                    # Save after each type
                    if all_results:
                        with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
                            fieldnames = ["slug", "name", "brand", "spirit_type", "spirit_type_cat",
                                          "location", "abv", "age", "cost_tier", "cask_type",
                                          "description", "distiller_score", "community_rating",
                                          "rating_count", "image_url"]
                            w = csv.DictWriter(f, fieldnames=fieldnames)
                            w.writeheader()
                            for r in all_results:
                                w.writerow({k: r.get(k, "") for k in fieldnames})
                        print(f"\n📊 Saved {len(all_results)} spirits to {OUTPUT}")
            elif args.type:
                results = await scrape_by_type(args.type, args.limit, browser)
                if results:
                    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
                        fieldnames = ["slug", "name", "brand", "spirit_type", "spirit_type_cat",
                                      "location", "abv", "age", "cost_tier", "cask_type",
                                      "description", "distiller_score", "community_rating",
                                      "rating_count", "image_url"]
                        w = csv.DictWriter(f, fieldnames=fieldnames)
                        w.writeheader()
                        for r in results:
                            w.writerow({k: r.get(k, "") for k in fieldnames})
                    print(f"\n✅ Saved {len(results)} spirits to {OUTPUT}")
            else:
                parser.print_help()
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())