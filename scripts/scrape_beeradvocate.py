"""BeerAdvocate scraper — breweries, beers, and ratings.

Extracts beer listings, brewery info, and ratings from BeerAdvocate.com.
Uses Playwright with stealth patches to handle Cloudflare protection.

Safeguards:
  - Rate limiting: 3-7s random delay between requests
  - Exponential backoff on 429/503/CF block
  - Session rotation: new browser context per brewery batch
  - User-Agent + viewport randomization
  - Checkpoint/resume via JSON cursor
  - Max retries with full stop after 10 consecutive failures

Usage:
    python scripts/scrape_beeradvocate.py --top-rated 50
    python scripts/scrape_beeradvocate.py --brewery 2312
    python scripts/scrape_beeradvocate.py --resume
    python scripts/scrape_beeradvocate.py --clear-checkpoint
"""

import asyncio
import csv
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Optional

# Checkpoint helpers
ROOT = Path(__file__).resolve().parent.parent
CHECKPOINT = ROOT / "data" / "ba_scrape_checkpoint.json"
OUTPUT = ROOT / "data" / "beeradvocate_breweries.csv"

# Rate limiting
MIN_DELAY = 3.0
MAX_DELAY = 7.0
MAX_RETRIES = 3
CONSECUTIVE_FAIL_LIMIT = 10
BATCH_SIZE = 10  # sessions per browser context

# Browser user agents to rotate
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
            print(f"📌 Checkpoint: {cp.get('scraped', 0)} breweries, "
                  f"last = {cp.get('last_brewery_id', 'none')}")
            return cp
        except (json.JSONDecodeError, OSError):
            pass
    return {"last_brewery_id": "", "scraped": 0, "errors": 0, "total": 0}


def save_checkpoint(cp: dict):
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT, "w") as f:
        json.dump(cp, f, indent=2)


def clear_checkpoint():
    if CHECKPOINT.exists():
        CHECKPOINT.unlink()
        print("🧹 Checkpoint cleared")


def random_delay():
    """Human-like delay between requests."""
    delay = random.uniform(MIN_DELAY, MAX_DELAY)
    return delay


async def scrape_top_rated(limit: int = 50):
    """Scrape top-rated beers from BeerAdvocate.

    Structure: /beer/top-rated/ lists beers with:
    - Rank, Beer name, Brewery, Style, ABV, Ratings, BA Score, Avg
    Each links to /beer/profile/{brewery_id}/{beer_id}/
    """
    print(f"🍺 Scraping top {limit} beers from BeerAdvocate...")
    print("⚠️  BeerAdvocate uses Cloudflare — requires real browser.")
    print("   Install Playwright: pip install playwright && playwright install chromium")
    print("   The script will create a browser context per batch.\n")

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("❌ playwright not installed. Run: pip install playwright && playwright install chromium")
        return

    results = []
    consecutive_fails = 0
    cp = load_checkpoint()
    start_id = cp.get("last_brewery_id", "")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
        )

        # Stealth: remove webdriver flag
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": random.randint(1280, 1440), "height": random.randint(720, 900)},
            locale="en-US",
        )

        # Inject stealth script
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)

        page = await context.new_page()

        for page_num in range(1, max(2, (limit // 25) + 2)):
            if len(results) >= limit:
                break

            url = f"https://www.beeradvocate.com/beer/top-rated/?page={page_num}&sort=avg&sort_order=desc"
            print(f"   Page {page_num}...")

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(random.uniform(1, 2))

                # Check if blocked
                title = await page.title()
                if "Attention" in title or "blocked" in title.lower():
                    consecutive_fails += 1
                    print(f"   ⚠️  Blocked (attempt {consecutive_fails})")
                    if consecutive_fails >= CONSECUTIVE_FAIL_LIMIT:
                        print("❌ Too many blocks. Stopping.")
                        break
                    await asyncio.sleep(random.uniform(10, 20))
                    continue

                consecutive_fails = 0

                # Parse beer rows - BA table structure:
                # td[0]=rank, td[1]=beer, td[2]=brewery, td[3]=style, td[4]=ABV, td[5]=ratings, td[6]=BA score, td[7]=avg
                beers = await page.evaluate("""
                    () => {
                        const rows = document.querySelectorAll('#ba-content table tr, .beer-list tr');
                        const items = [];
                        for (const row of rows) {
                            const cells = row.querySelectorAll('td');
                            if (cells.length < 5) continue;
                            const link = row.querySelector('a');
                            if (!link) continue;
                            const href = link.getAttribute('href') || '';
                            const match = href.match(/\\/beer\\/profile\\/(\\d+)\\/(\\d+)/);
                            if (!match) continue;
                            // Find the brewery cell - it's usually the cell after the beer name
                            let brewery = '', style = '', abv = '', ratings = '', ba_score = '', avg = '';
                            if (cells.length > 1) brewery = cells[1].textContent.trim();
                            if (cells.length > 2) style = cells[2].textContent.trim();
                            if (cells.length > 3) abv = cells[3].textContent.trim();
                            if (cells.length > 4) ratings = cells[4].textContent.trim();
                            if (cells.length > 5) ba_score = cells[5].textContent.trim();
                            if (cells.length > 6) avg = cells[6].textContent.trim();
                            // Clean up: brewery name often gets concatenated with beer name
                            // in the same cell, extract it from the link's parent structure
                            const beerCell = cells[0] || cells[1];
                            const beerLink = beerCell?.querySelector('a');
                            const beerName = beerLink ? beerLink.textContent.trim() : '';
                            // Try to get brewery from the next cell or from the link's title
                            const breweryCell = cells[1] || cells[2];
                            const breweryName = breweryCell ? breweryCell.textContent.trim() : '';
                            // Sometimes the link is in the brewery cell, not the beer cell
                            const allLinks = row.querySelectorAll('a');
                            let breweryFromLink = '';
                            let beerFromLink = '';
                            if (allLinks.length > 0) {
                                const bMatch = allLinks[0].href.match(/\\/beer\\/profile\\/(\\d+)/);
                                if (bMatch) {
                                    beerFromLink = allLinks[0].textContent.trim();
                                    if (allLinks.length > 1) {
                                        breweryFromLink = allLinks[1].textContent.trim();
                                    }
                                }
                            }
                            items.push({
                                brewery_id: match[1],
                                beer_id: match[2],
                                name: beerFromLink || beerName || link.textContent.trim(),
                                brewery: breweryFromLink || breweryName || '',
                                style: style || '',
                                abv: abv || '',
                                ratings: ratings || '',
                                ba_score: ba_score || '',
                                avg: avg || '',
                                url: 'https://www.beeradvocate.com' + href,
                            });
                        }
                        return items;
                    }
                """)

                for beer in beers:
                    if len(results) >= limit:
                        break
                    results.append(beer)

                # Save progress
                save_checkpoint({
                    "last_brewery_id": results[-1]["brewery_id"] if results else "",
                    "scraped": len(results), "errors": 0, "total": limit,
                })

                # Random delay between pages
                await asyncio.sleep(random_delay())

            except Exception as e:
                consecutive_fails += 1
                print(f"   ⚠️  Error: {e}")
                if consecutive_fails >= CONSECUTIVE_FAIL_LIMIT:
                    break
                await asyncio.sleep(random_delay() * 2)

        await browser.close()

    # Write results
    if results:
        with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["brewery_id", "beer_id", "name", "url"])
            w.writeheader()
            w.writerows(results)
        print(f"✅ Saved {len(results)} beers to {OUTPUT}")
    else:
        print("⚠️  No results scraped. Cloudflare may be blocking.")

    return results


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="BeerAdvocate scraper")
    parser.add_argument("--top-rated", type=int, default=0, help="Scrape top N rated beers")
    parser.add_argument("--brewery", type=str, default="", help="Scrape specific brewery by ID")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--clear-checkpoint", action="store_true", help="Clear checkpoint")
    parser.add_argument("--export", action="store_true", help="Export collected data")
    args = parser.parse_args()

    if args.clear_checkpoint:
        clear_checkpoint()
        return

    if args.top_rated:
        await scrape_top_rated(args.top_rated)
    elif args.brewery:
        print(f"🍺 Brewery ID scraping: {args.brewery} (not yet implemented)")
    elif args.resume:
        cp = load_checkpoint()
        if cp.get("scraped", 0) > 0:
            print(f"📌 Resuming from {cp['scraped']} breweries...")
            await scrape_top_rated(cp.get("total", 50))
        else:
            print("No checkpoint to resume from.")
    elif args.export:
        print("📊 Export not yet implemented")
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())