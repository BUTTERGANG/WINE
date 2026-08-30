# Application Architecture

## Overview

WINE is a social wine tracking and discovery platform. Users photograph or search for wines, tag locations on an interactive map, rate and review them, and engage with a community of wine drinkers.

**Stack:** Python 3.11+ / FastAPI / SQLite (dev) → PostgreSQL + PostGIS (prod) / Jinja2 + HTMX / Tailwind CSS / Leaflet.js (OpenStreetMap)

---

## High-Level Architecture

```
                         +----------------------+
                         |   Client (Mobile/Web) |
                         |   HTMX + Tailwind CSS |
                         +----------+-----------+
                                    |
                         +----------v-----------+
                         |    FastAPI Server      |
                         |  REST + HTML (HTMX)    |
                         +----+----+----+----+---+
                              |    |    |    |
              +---------------+    |    |    +---------------+
              |                     |    |                     |
       +------v------+    +--------v-v----+     +-------------v------+
       |  Wine API    |    |  Location API  |     |  Social/Community  |
       |  (Scan/Search)|   |  (Map/GeoJSON) |     |  (Feed/Follows)    |
       +------+-------+    +-------+-------+     +---------+---------+
              |                     |                       |
       +------v-------+    +-------v-------+     +---------v---------+
       |  Wine DB      |    |  PostGIS      |     |  Social DB        |
       |  (SQLite/PG)  |    |  (Geo Queries)|     |  (SQLite/PG)      |
       +---------------+    +---------------+     +-------------------+
              |
       +------v-------+
       |  Label Scan   |
       |  OCR + Vision |
       +------+--------+
              |
    +---------v----------+
    | External Wine APIs  |
    | GrapeMinds/VinoFYI  |
    +---------------------+
```

---

## Directory Structure

```
WINE/
├── backend/
│   ├── main.py                 # FastAPI app entry, CORS, middleware
│   ├── config.py               # Settings from env
│   ├── routers/
│   │   ├── wines.py            # Wine CRUD, search, scan
│   │   ├── locations.py        # Map pins, GeoJSON endpoints
│   │   ├── community.py        # Feed, follows, groups
│   │   ├── users.py            # Auth, profiles
│   │   └── pages.py            # HTML page routes (HTMX)
│   ├── models/
│   │   ├── wine.py             # Wine + TastingNote models
│   │   ├── location.py         # Location/venue model (lat, lon, name)
│   │   ├── user.py             # User model
│   │   └── community.py        # Follow, Group, Feed models
│   ├── services/
│   │   ├── label_scanner.py    # OCR + visual matching logic
│   │   ├── glass_scanner.py    # Color/opacity/legs analysis
│   │   ├── wine_db.py          # External wine API integration
│   │   ├── geocoder.py         # Address → lat/lon (Nominatim)
│   │   └── search.py           # Autocomplete, fuzzy matching
│   ├── templates/
│   │   ├── base.html           # Layout shell (Tailwind CSS)
│   │   ├── index.html          # Map + feed landing
│   │   ├── wine/
│   │   │   ├── detail.html     # Wine detail page
│   │   │   ├── add.html        # Add wine form
│   │   │   └── scan.html       # Scan interface
│   │   ├── location/
│   │   │   └── map.html        # Map component
│   │   ├── community/
│   │   │   ├── feed.html       # Activity feed
│   │   │   └── profile.html    # User profile
│   │   └── components/
│   │       ├── wine_card.html  # Reusable wine card partial
│   │       └── pin_popup.html  # Map pin popup template
│   └── static/
│       ├── css/
│       │   └── app.css         # Tailwind output
│       └── js/
│           └── map.js          # Leaflet.js map setup
├── THE-VISION/                 # Design docs
├── SCRUM/                      # Project management
├── data/                       # SQLite (dev) + uploads
├── tests/
│   ├── test_wines.py
│   ├── test_locations.py
│   └── test_community.py
├── docs/                       # Setup guides
├── scripts/                    # Dev helpers
├── .env.example
├── .gitignore
├── CLAUDE.md
├── KANBAN.md
└── requirements.txt
```

---

## Tech Stack Decisions

| Layer | Choice | Why |
|-------|--------|-----|
| **Backend** | FastAPI | Proven stack in BUTTERGANG repos. Async, auto-docs, great for HTMX |
| **Templating** | Jinja2 + HTMX | No SPA complexity. HTMX gives SPA-like UX without JS framework. SEO-friendly |
| **CSS** | Tailwind CSS | Rapid UI, consistent with other BUTTERGANG projects |
| **Map** | Leaflet.js + OpenStreetMap | Free. No API keys. Works offline-capable with tile caching |
| **DB (dev)** | SQLite | Zero config for local development |
| **DB (prod)** | PostgreSQL + PostGIS | Geospatial queries (radius search, map clustering) |
| **Auth** | Session-based (fastapi-sessions or similar) | Simple, no OAuth dependency for MVP |
| **Label OCR** | Google Cloud Vision / api4.ai | Best accuracy on decorative wine labels |
| **Wine Data API** | GrapeMinds (290K wines, free tier) or VinoFYI (741K records, free) | Seed database without building from scratch |
| **Glass Analysis** | Custom color/hue analysis pipeline | Unique feature — no off-the-shelf solution exists |
| **Runtime** | Uvicorn | Standard ASGI server |

---

## Key Data Flows

### Flow 1: Add a Wine (Scan)
```
User snaps label → FastAPI receives image → OCR extracts text →
→ Search wine DB (GrapeMinds/VinoFYI) for match →
→ Return top candidates to user for confirmation →
→ User confirms → WINE saves to local DB with user's rating + notes
```

### Flow 2: Add a Wine (Manual + Live Search)
```
User types in search box → AJAX autocomplete hits /api/wines/search →
→ Results filtered from local DB + external API →
→ User taps/selects a wine → Form auto-fills producer, vintage, region →
→ User adds rating, notes, and tags a location
```

### Flow 3: Tag a Location
```
User adds/searchs for a venue → Geocoding (Nominatim/OSM) resolves to lat/lon →
→ Pin saved to locations table tied to this tasting note →
→ Map re-renders with new pin via HTMX swap
```

### Flow 4: Browse Map
```
User opens map page → FastAPI serves /api/locations/nearby →
→ PostGIS queries wines within viewport bounds →
→ Returns GeoJSON FeatureCollection →
→ Leaflet renders pins with popup previews
```

---

## API Routes (Planned)

### Wines
- `GET /api/wines/search?q=...` — live autocomplete
- `POST /api/wines/scan` — upload bottle/glass photo, return candidates
- `POST /api/wines` — create wine entry with rating + location
- `GET /api/wines/{id}` — wine detail with reviews
- `GET /api/wines/{id}/reviews` — community reviews for a wine

### Locations
- `GET /api/locations/nearby?lat=&lon=&radius=` — GeoJSON pins
- `POST /api/locations` — create a location pin
- `GET /api/locations/{id}/wines` — wines tasted at this location

### Community
- `GET /api/feed` — activity feed (recent public tastings)
- `POST /api/follow/{user_id}` — follow/unfollow
- `GET /api/groups/{id}/feed` — group activity

### Users
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/users/{id}` — profile with map + tasting history

### Pages (HTML)
- `GET /` — landing page with map + feed
- `GET /wine/add` — add wine page
- `GET /wine/scan` — scan page
- `GET /wine/{id}` — wine detail page
- `GET /map` — full-screen map view
- `GET /profile/{id}` — user profile timeline
- `GET /feed` — community feed

---

## Database Schema (Initial)

**Core tables:**

```
wines            — producer, name, vintage, region, varietal, type, abv, image
tasting_notes     — wine_id, user_id, rating, notes, appearance, nose, palate, finish, created_at
locations         — name, address, lat, lon, venue_type (winery/restaurant/bar/home)
wine_locations    — tasting_note_id, location_id (join: which wine was drunk where)
users             — username, email, password_hash, avatar, bio
follows           — follower_id, followed_id
groups            — name, description, private/public
group_members     — group_id, user_id
feed_events       — user_id, event_type, target_id, created_at (denormalized feed)
```

PostGIS geography column on `locations` for geospatial queries.

---

## Security

- **Auth** — Session-based with bcrypt password hashing
- **Input validation** — Zod-inspired pydantic schemas on all mutation routes
- **CSRF** — HTMX headers + session-based CSRF tokens
- **File uploads** — Validate image types, limit to 10MB, store outside web root
- **Rate limiting** — On scan/search endpoints to prevent abuse of external APIs
- **Map data** — Users control public/private visibility of their locations

---

## Future Considerations

- **Progressive Web App** — making the mobile-web experience feel native (add-to-homescreen, offline map tiles)
- **Native mobile** — Expo React Native wrapper once web MVP validates
- **Real-time feed** — WebSocket push for new tastings near you
- **ML recommendations** — Personal taste profile from rating history
- **Barcode/UPC scan** — Fallback identification when label OCR fails
- **Export** — Personal tasting journal as CSV/PDF