# THE-VISION: WINE Technical Documentation (Built 2026-08-30)

## Documents

| # | Document | Description |
|---|----------|-------------|
| 01 | [Application Architecture](01-APPLICATION-ARCHITECTURE.md) | High-level system architecture, tech stack, data flow, directory structure |
| 02 | [Features](02-FEATURES.md) | Complete features inventory — photo scan, location map, community, search |
| 03 | [Build Summary](03-BUILD-SUMMARY.md) | Completed build summary with all features shipped across all phases |

---

## Quick Reference

**Stack:** Python 3.11+ / FastAPI / SQLite / Jinja2 + HTMX / Tailwind CSS / Leaflet.js (OpenStreetMap)

**Status:** All 3 phases complete. Fully functional MVP.

**Stats:**
- 49,958 wineries across 60+ countries
- 34,177 global wineries with lat/lon from winerymap dataset
- 16,951 US wineries from TTB FOIA + winerymap
- 44 smoke tests, all passing
- 17 HTML templates, 8 route modules, 7 service modules

**Core Pillars:**
- 🍷 **Photo Scan** — bottle label OCR + glass photo color/legs analysis
- 📍 **Location Map** — every wine pinned on an interactive OpenStreetMap with marker clustering
- 👥 **Community** — reviews, follows, groups, feed, personal taste profiles
- 🔍 **Live Search** — autocomplete from 50K-wine database
- 🏘️ **Wineries** — 50K wineries searchable, mappable, with venue detail pages
- ⭐ **Wishlist** — save wines to try later
- 📋 **Menu Scanner** — upload a wine list, get matched wines with ratings

## Competitor Landscape (2026)

| App | Users | Core Strength | Our Advantage |
|-----|-------|--------------|--------------|
| Vivino | 70M+ | Label scanning + crowd ratings | **Location map** — they have none |
| CellarTracker | 8.8M | Cellar inventory, drink windows | **Social map discovery** — no map exists |
| Delectable | Niche | Following sommeliers | Abandoned (last iOS update 2021) |
| Wine-Searcher | 2.5M | Price comparison engine | **Community + map** — they're just a search engine |
| Swirl | Startup | Personal taste profiles | **Location tagging** — no map view |
| Sommo | Startup | AI label analysis | **Open platform** — they're closed/subscription |

## Key Flows
- Scan/Manual Add → Wine Match → Tag Location → Rate & Review → Map Pin
- Browse Map → Filter by Wine/Region/Rating → See Others' Reviews
- Live Search → Select from DB → Add Your Tasting Note + Location
- Menu Scan → OCR → Wine DB Match → Ratings + Prices → Save to Wishlist
- Winery Search → Browse → Venue Detail → See What's Been Poured There