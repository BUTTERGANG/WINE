# THE-VISION: WINE Technical Documentation

## Documents

| # | Document | Description |
|---|----------|-------------|
| 01 | [Application Architecture](01-APPLICATION-ARCHITECTURE.md) | High-level system architecture, tech stack, data flow, directory structure |
| 02 | [Features](02-FEATURES.md) | Complete features inventory — photo scan, location map, community, search |
| 03 | [MVP Plan](03-MVP-PLAN.md) | Phased MVP build plan with milestones, acceptance criteria, and timeline |

---

## Quick Reference

**Stack:** Python 3.11+ / FastAPI / SQLite → PostgreSQL / Jinja2 + HTMX / Tailwind CSS / Leaflet.js (OpenStreetMap)

**Core Pillars:**
- 🍷 **Photo Scan** — bottle label OCR + glass photo color/legs analysis
- 📍 **Location Map** — every wine pinned on an interactive OpenStreetMap
- 👥 **Community** — reviews, follows, groups, feed of what people are drinking near you
- 🔍 **Live Search** — autocomplete from the community wine database

**Key Flows:**
- Scan/Manual Add → Wine Match → Tag Location → Rate & Review → Map Pin
- Browse Map → Filter by Wine/Region/Rating → See Others' Reviews
- Live Search → Select from DB → Add Your Tasting Note + Location

## Competitor Landscape (2026)

| App | Users | Core Strength | Our Advantage |
|-----|-------|--------------|--------------|
| Vivino | 70M+ | Label scanning + crowd ratings | **Location map** — they have none |
| CellarTracker | 8.8M | Cellar inventory, drink windows | **Social map discovery** — no map exists |
| Delectable | Niche | Following sommeliers | Abandoned (last iOS update 2021) |
| Wine-Searcher | 2.5M | Price comparison engine | **Community + map** — they're just a search engine |
| Swirl | Startup | Personal taste profiles | **Location tagging** — no map view |
| Sommo | Startup | AI label analysis | **Open platform** — they're closed/subscription |