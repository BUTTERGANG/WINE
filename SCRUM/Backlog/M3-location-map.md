---
status: backlog
priority: p0
agent_claimed: false
claimed_at:
updated: 2026-08-30
---

## M3: Location Pinning & Map

**Description:** Users tag a venue/place when logging a wine. All tastings appear on an interactive Leaflet map with OpenStreetMap tiles.

**Context:** This is the core differentiator. Location + map is what sets WINE apart from every existing app.

**Acceptance Criteria:**
- When adding a wine, user can search for a venue name or address
- Venue search resolves via Nominatim (OpenStreetMap) to lat/lon
- User can also drop a pin directly on a mini-map
- Tasting is stored with location_id linking to locations table
- `/map` page renders full-screen Leaflet map with OpenStreetMap tiles
- `GET /api/locations/nearby?lat=&lon=&radius=` returns GeoJSON FeatureCollection
- Each pin on the map shows wine name, rating, user, date in popup
- "My Wines" / "Everyone" toggle filters pins
- Map re-centers on user's last known location or all pins

**Technical Notes:**
- Leaflet.js with OpenStreetMap tiles (no API key needed)
- Nominatim has rate limits (1 req/sec) — cache geocoded results in DB
- GeoJSON format: `{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Point","coordinates":[lon,lat]},"properties":{...}}]}`
- Pin icons: custom wine-bottle SVG markers (Leaflet DivIcon)
- Mobile: ensure map is touch-friendly, pins are tappable