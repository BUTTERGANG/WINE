# WINE — Build Summary

## Completed: All 3 Phases Build (2026-08-30)

---

## Phase 1 — Core Loop ("Snap, Sip, Pin")

### Milestone 1: Project Scaffold & Auth ✅
- FastAPI app boots with uvicorn, serves HTML pages with Tailwind CSS
- SQLite database with 7 tables: wines, tasting_notes, locations, users, follows, groups, group_members
- User registration (email + password) with bcrypt hashing
- Session-based login/logout with cookie auth
- Dark theme base template

### Milestone 2: Wine Search & Manual Add ✅
- Live autocomplete via `/api/wines/search?q=` with fuzzy matching
- Add wine form with structured WSET-inspired tasting notes (appearance, nose, palate, finish)
- Wine detail page with average rating and reviews
- HTMX-driven search suggestions

### Milestone 3: Location Pinning & Map ✅
- Full-screen Leaflet map with OpenStreetMap tiles
- `GET /api/locations/nearby?lat=&lon=&radius=` returns GeoJSON FeatureCollection
- "My Wines" / "All" / "Wineries" filter toggle
- Pin popups with wine name, rating, user, location, notes
- Radius slider (5-500km) and wine type filter

### Milestone 4: Bottle Label Scan ✅
- Camera/file upload on `/wine/scan` page
- Bottle/glass mode toggle
- OCR via api4.ai wine recognition API (when key set)
- Top 3 candidates with manual override

### Milestone 5: Glass Photo Analysis ✅
- Upload photo of poured glass → color analysis (K-means clustering)
- Legs/tears detection (viscosity indicator)
- Wine type (red/white/rosé/sparkling) + varietal suggestions
- Labeled as "AI Guess" with confidence meter

### Milestone 6: Public Feed & Polish ✅
- HTMX-driven public feed on landing page and `/feed`
- Seed data: 30 wines, 5 users, 8 venues, 20 tasting notes
- 16/16 smoke tests (expanded to 44)

---

## Phase 2 — Social Layer

### Follow System ✅
- Follow/unfollow with instant UI toggle
- `/api/follow/{id}`, `/api/follow/{id}/status`, follower counts
- Personal feed filtered to followed users

### Wine Groups ✅
- Create/join public groups
- Group detail page with member list and shared tasting feed
- `/groups` page with HTMX-driven list

### Photo Uploads ✅
- Upload photos to tasting notes via `/api/upload/photo`
- Served from `/static/uploads/`
- Photo indicator on profile cards

### Profile Stats ✅
- Tasting count, unique wines, unique venues, followers/following
- Taste profile card on own profile page (HTMX-loaded)

---

## Phase 3 — Intelligence & Scale

### Taste Profile ✅
- Analyzes rating history → favorite type, varietal, region, body, sweetness
- `/api/profile/{id}/taste` returns structured JSON
- `/dashboard` page with full profile visualization

### Recommendations ✅
- Recommends untasted wines matching user's profile preferences
- `/api/recommendations` endpoint
- Recommendation grid on dashboard page

### Heatmap ✅
- `/api/locations/heatmap` returns weighted [lat, lon, intensity] points
- Rating (0.2-0.8) + recency bonus (up to 1.0)
- Wine type filter support
- Leaflet.heat integration with custom gradient

### CSV Export ✅
- `/api/wines/export` returns authenticated user's full journal as CSV
- 23 columns: Date, Wine, Producer, Vintage, Region, Varietal, Type, Rating, etc.
- Formula injection protection

### What's Near Me ✅
- Geo-location button on map
- Radius slider controls search radius
- Wine type dropdown filter

---

## Phase 4+ — Post-MVP Features

### Winery Database (49,958 wineries) ✅
- TTB FOIA wine producer list (~18K US wineries, public domain)
- winerymap dataset (~34K global wineries, MIT licensed)
- State centroids for remaining (~13K)
- 60+ countries covered

### Marker Clustering ✅
- Leaflet.markercluster handles 50K+ wineries on map
- Clusters at zoom < 16, spiderfies on click
- Touch-friendly mobile options

### Venue Detail Pages ✅
- `/venue/{id}` for all venue types (winery, restaurant, bar, home, shop)
- Stats card: tastings, wines, visitors, avg rating
- "Wines Poured Here" grid with rating summary
- Recent tastings timeline

### Menu Scanner ✅
- Upload restaurant wine list photo
- OCR extracts wine names, vintages, prices
- Matches against 50K-wine database
- Shows ratings, prices, and save-to-wishlist buttons

### Wishlist ✅
- WishlistEntry model with unique user+wine constraint
- Toggle save from any wine detail page
- `/wishlist` page with HTMX-driven list and remove

---

## Test Coverage

44 smoke tests covering:
- Health check
- All pages render (login, register, map, feed, groups, add, scan, dashboard, wineries, wishlist, menu scan)
- Wine search, feed API, personal feed
- Follow status + counts
- Group creation + listing
- Location nearby + heatmap
- Wine detail + reviews
- Profile lookup + taste profile
- Recommendations
- CSV export (auth + no auth)
- Winery search + nearby + detail
- Venue page (wines poured)
- Add wine validation (rating required, wine info required)
- Privacy (unchecked is_public stays private)
- Follow unknown user (404 not 500)
- Follow by username
- Group creation returns list
- Session stateless cookie
- CSV formula escape
- Recent wines + reverse geocode