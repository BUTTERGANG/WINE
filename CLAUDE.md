# WINE — Agent Startup

## Project Identity
- **Repo:** BUTTERGANG/WINE
- **Stack:** FastAPI / Jinja2 + HTMX / Tailwind CSS / Leaflet.js (OSM) / SQLite → PostgreSQL
- **Location:** `~/code/BUTTERGANG/WINE/`
- **Vision:** Social wine tracking with bottle/glass scan, location map, and community

## Architecture State
- **Phase:** Design (pre-build). THE-VISION/ folder has architecture, features, and MVP plan.
- **No code yet** — this is a fresh bootstrap.

## Key Design Decisions (pre-verified)
1. **HTMX over SPA** — server-rendered HTML with partial swaps. No JS framework needed for MVP.
2. **Leaflet + OpenStreetMap** — free, no API keys. PostGIS for production geo queries.
3. **Bottle scan via OCR API** — Google Cloud Vision or api4.ai. Glass scan via custom color/legs analysis.
4. **External wine DB** — GrapeMinds (free tier, 290K wines) or VinoFYI (free, 741K records) for seed + fallback.
5. **Session auth** — simple, fast to implement. OAuth can come later.
6. **Dark theme** — consistent with BUTTERGANG design language.

## Route Map
- **Phase 1 (MVP):** Scaffold → Auth → Wine Search/Add → Map Pins → Bottle Scan → Glass Scan → Feed
- **Phase 2:** Follows, groups, community map, photo attachments, profiles, "near me"
- **Phase 3:** Taste profiling, recommendations, exports, heatmaps, menu scan

## Critical Constraints
- No external internet on VPS → build depends on local dev first
- Replit for web dashboards if needed — VPS crons fetch & push
- Follow BUTTERGANG conventions: THE-VISION/, SCRUM/, README.md section pattern

## Quick Commands
```bash
cd ~/code/BUTTERGANG/WINE
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
fastapi dev backend/main.py
```