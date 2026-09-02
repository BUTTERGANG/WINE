# WINE — Agent Startup

## Project Identity
- **Repo:** BUTTERGANG/WINE
- **Stack:** FastAPI / SQLAlchemy async / SQLite / Jinja2 + HTMX / Tailwind CSS / Leaflet.js (OSM)
- **Location:** `~/code/BUTTERGANG/WINE/`
- **Port:** 8002 (local dev)
- **Tests:** 44 smoke tests (run against live server)
- **Vision:** Social wine tracking — snap a bottle or glass, tag where you're drinking it, rate it, and see what your community is drinking nearby

## Architecture State (Built 2026-08-30)
All 3 phases complete. Fully functional MVP with 49,958 wineries, 30 wines, 20 tasting notes, 5 seed users.

## What's Built
### Core Features
| Feature | Status | Details |
|---------|--------|---------|
| Auth | ✅ | Session cookies, bcrypt passwords |
| Wine search + add | ✅ | Live autocomplete, structured WSET tasting notes, simplified quick-add form |
| Location map | ✅ | Leaflet + OSM, marker clustering, personal/all/winery/distillery modes, interactive home mini-map |
| Bottle label scan | ✅ | Camera upload, OCR (api4.ai when key set) |
| Glass photo analysis | ✅ | Color/legs/opacity → wine type + varietal guesses |
| Public feed | ✅ | Global + personal (followed users), photo-first grid layout, working load-more |
| Follow system | ✅ | Follow/unfollow with instant UI toggle |
| Wine groups | ✅ | Create/join, shared tasting feed |
| Photo uploads | ✅ | Upload to tastings, served from /static/uploads/, click-to-expand lightbox |
| Taste profile | ✅ | Analyzes rating history → favorite type/varietal/region |
| Recommendations | ✅ | Suggests untasted wines matching palate |
| Heatmap | ✅ | Leaflet.heat layer by rating + recency |
| Near Me | ✅ | Geo-location button, radius slider (5-500km) |
| CSV export | ✅ | Full journal with 23 columns |
| Winery database | ✅ | 49,958 wineries across 60+ countries |
| Winery search | ✅ | Name, region, state, country — with map pins |
| Venue detail pages | ✅ | Stats, wines poured, recent tastings |
| Wishlist | ✅ | Save wines to try later, toggle from wine detail |
| Menu scanner | ✅ | Upload wine list photo, OCR, match against 50K wines |
| Marker clustering | ✅ | Leaflet.markercluster for crowded map areas |
| Spirits | ✅ | Whiskey/bourbon/scotch/rye with distilleries, feed, wishlist |
| Wine of the Day | ✅ | Server-rendered random wine on home page |
| Photo lightbox | ✅ | Click any tasting photo to expand |
| Nav reorganization | ✅ | "More" dropdown grouped by Wine/Spirits/You |

### Test Accounts
| Username | Email | Password |
|----------|-------|----------|
| wine_lover | wine@example.com | password |
| sommelier_sam | sam@example.com | password |
| cabernet_queen | queen@example.com | password |
| sparkling_steve | steve@example.com | password |
| demo_taster | demo@example.com | password |

## Key Endpoints
| Route | Method | Description |
|-------|--------|-------------|
| /api/wines/search?q= | GET | Wine autocomplete |
| /api/wines | POST | Create wine + tasting note |
| /api/wines/export | GET | CSV journal download |
| /api/wines/wishlist | GET | User's wishlist |
| /api/wines/wishlist/{id} | POST | Toggle save wine |
| /api/wines/wine-of-the-day | GET | Random wine with tasting note |
| /api/feed | GET | Global public feed |
| /api/feed/personal | GET | Feed from followed users |
| /api/locations/nearby | GET | GeoJSON map pins |
| /api/locations/heatmap | GET | Heatmap data |
| /api/wineries/search | GET | Winery search |
| /api/wineries/nearby | GET | Winery map pins |
| /api/menu/scan | POST | Upload wine list photo |
| /api/profile/{id}/taste | GET | Taste profile |
| /api/recommendations | GET | AI wine recommendations |
| /api/spirits/search | GET | Spirit autocomplete |
| /api/spirits/feed | GET | Spirit public feed |
| /api/spirits/feed/groups | GET | Spirit feed from group members |
| /api/spirits/distilleries/search | GET | Distillery search |
| /api/spirits/distilleries/nearby | GET | Distillery map pins |
| /api/spirits/wishlist | GET | User's spirit wishlist |
| /api/spirits/wishlist/{id} | POST | Toggle save spirit |

## Quick Commands
```bash
cd ~/code/BUTTERGANG/WINE
source .venv/bin/activate
.venv/bin/uvicorn backend.main:app --reload --port 8002
# Full reseed:
rm -f data/wine.db && .venv/bin/python scripts/seed.py
# Run tests (server must be running):
.venv/bin/python -m pytest tests/ -v
```

## Key Issues / Gotchas
- Jinja2 pinned to <3.1.5 due to cache hash bug with Starlette 1.6
- Session store is in-memory — resets on server restart. Swap to Redis for prod
- No PostGIS — SQLite bounding-box approximation for geo queries
- Glass scan is experimental — labeled as "AI Guess" with confidence meter
- Country data for wineries derived from lat/lon bounding boxes (approximate)
