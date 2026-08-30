# WINE

Social wine tracking & discovery app — snap a bottle or a glass, tag where you're drinking it on a map, rate it, and see what your community is uncorking nearby.

**Vision:** The first wine app that combines photo identification (bottle *and* glass), location-based discovery on an interactive map, and a genuine community feed — closing the gap between "what am I drinking" and "where should I drink next."

Scaffolded from [AGENT-PLAYBOOK](https://github.com/BUTTERGANG/AGENT-PLAYBOOK) on 2026-08-30.

---

## Why This Exists

The wine app market has 70M+ users across Vivino, CellarTracker, Wine-Searcher, and Delectable — yet every major app misses the same three things:

1. **No location map** — Every app lets you text-notes where you tried a wine. None gives you an interactive map of *everywhere you've tasted wine* or shows what people are drinking near you.
2. **No glass photo ID** — Every scanner requires a bottle label. Nobody identifies wine from a photo of the *glass* (color, legs, opacity). That's the moment you actually want to log a wine.
3. **No real social discovery** — Vivino has a feed but it's marketplace-driven. Delectable was the best social app but got abandoned. There's no app where you follow friends and see what they're drinking on a map.

**WINE fixes all three.** One app. Bottle scan, glass scan, map every pour, share with your people.

---

## Core Pillars

### 🍷 Photo ID (Bottle + Glass)
- **Label scan** — OCR + visual matching against a curated wine database. Point, snap, identified.
- **Glass scan** — AI color/opacity/legs analysis to guess the wine from the pour. Nobody else does this.
- **Manual entry** — type producer + vintage + region with live autocomplete search against the DB.
- **Structured tasting notes** — WSET-inspired framework: appearance, nose, palate, finish, rating.

### 📍 Location Map
- Every wine logged gets pinned to an **interactive OpenStreetMap** using Leaflet.js.
- Filter your personal map by wine type, vintage, rating, region.
- Browse a **global community map** — see what others are drinking at restaurants, wineries, homes.
- Tag the specific venue (winery, restaurant, bar, friend's house) — make it a social record.

### 👥 Community
- **Follow friends & tastemakers** — build a feed of what they're drinking.
- **Public/private tastings** — share a specific bottle to the feed or keep it private.
- **Wine groups** — by region, varietal, wine club. Share notes and recommendations.
- **"What's being poured near me"** — discover bottles people are rating at places nearby.

### 🔍 Live Search & Database
- Autocomplete as you type against a curated wine database.
- Built on open wine data (GrapeMinds / VinoFYI / Apify wine APIs — 3,500–290K+ wines available).
- Community-contributed — once you scan or add a wine, it's in the DB for the next person.

---

## Documentation

| File | Description |
|------|-------------|
| [THE-VISION/00-INDEX.md](THE-VISION/00-INDEX.md) | Full documentation index |
| [THE-VISION/01-APPLICATION-ARCHITECTURE.md](THE-VISION/01-APPLICATION-ARCHITECTURE.md) | System architecture, data flow, stack decisions |
| [THE-VISION/02-FEATURES.md](THE-VISION/02-FEATURES.md) | Complete feature inventory with priority tiers |
| [THE-VISION/03-MVP-PLAN.md](THE-VISION/03-MVP-PLAN.md) | Phased build plan with milestones and acceptance criteria |

---

## Getting Started

```bash
# Clone
git clone https://github.com/BUTTERGANG/WINE.git
cd WINE

# Set up Python backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy and edit env
cp .env.example .env

# Run
fastapi dev main.py
```

*Full setup instructions coming in Phase 1 of the MVP.*