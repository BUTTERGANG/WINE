# MVP Plan

## Phase 1 — The Core Loop ("Snap, Sip, Pin")

**Goal:** A user can add a wine (by scanning a bottle label, analyzing a glass photo, or manually searching), tag where they drank it on a map, rate it, and see all their wines pinned on an interactive map.

**Target: 2–3 weeks of build**

---

### Milestone 1: Project Scaffold & Auth

**Acceptance:**
- FastAPI app boots, serves HTML pages
- SQLite database initialized with core tables
- User can register, login, logout
- Session auth protects mutation routes

**Tasks:**
- [ ] Initialize FastAPI project with cookiecutter-style layout
- [ ] Set up config.py from .env
- [ ] Create SQLite schema: wines, tasting_notes, locations, users, wine_locations
- [ ] Implement register/login/logout with pydantic validation
- [ ] Create base.html template with Tailwind CSS + dark theme
- [ ] Seed 20–50 wines from external API into local DB for dev/testing

**Deliverables:**
- `backend/main.py` boots and serves `GET /` landing page
- `/register`, `/login`, `/logout` all functional
- Database has schema + seed data

---

### Milestone 2: Wine Search & Manual Add

**Acceptance:**
- User can type into a search box and see autocomplete suggestions
- Selecting a wine auto-fills a form
- User adds rating + notes + location and submits
- Wine + tasting note saved to DB

**Tasks:**
- [ ] Build `/api/wines/search?q=...` endpoint with LIKE/fuzzy matching
- [ ] Build `/wine/add` page with autocomplete input (HTMX-driven)
- [ ] Create wine detail template
- [ ] Build POST `/api/wines` endpoint (create wine + tasting note)
- [ ] Wire up HTMX: search results swap into dropdown, form submission via hx-post

**Deliverables:**
- `/wine/add` page with live autocomplete search
- Submitting form creates a wine record and redirects to its detail page
- `/api/wines/search?q=cab` returns seeded matches

---

### Milestone 3: Location Pinning & Map

**Acceptance:**
- When adding a wine, user can search for a venue name → resolves to lat/lon
- Wine appears as a pin on an interactive Leaflet map
- User can filter map to show only their wines
- Clicking a pin shows wine name, rating, date

**Tasks:**
- [ ] Build POST `/api/locations` endpoint (resolve address → Nominatim geocoding)
- [ ] Create GET `/api/locations/nearby?lat=&lon=&radius=` returning GeoJSON
- [ ] Integrate Leaflet.js with OpenStreetMap tiles
- [ ] Build wine/location join on wine creation
- [ ] Create `/map` page with full-screen Leaflet view
- [ ] Add pin popups showing wine name, rating, user, date
- [ ] Add "My Wines" / "Everyone" filter toggle

**Deliverables:**
- Map renders with accurate pins from logged tastings
- Pin popups show wine details
- Filter toggle works

---

### Milestone 4: Bottle Label Scan

**Acceptance:**
- User taps "Scan" → camera opens (or file upload on desktop)
- Upload label photo → OCR extracts text → matches against wine DB
- Top 1–3 candidates shown for user to confirm
- Confirmed wine pre-fills the add form

**Tasks:**
- [ ] Build `/wine/scan` page with file upload (HTMX + multipart)
- [ ] Integrate OCR API (Google Cloud Vision or api4.ai wine recognition)
- [ ] Build `/api/wines/scan` endpoint: receives image → OCR → match against wine DB
- [ ] Build match/confidence scoring logic
- [ ] Wire UI: show candidates → user taps one → pre-fills add form with rating + location

**Deliverables:**
- `/wine/scan` uploads a bottle label, returns matched candidates
- User can confirm a match and proceed to add tasting note + location

---

### Milestone 5: Glass Photo Scan (MVP)

**Acceptance:**
- User switches scanner to "Glass" mode
- Uploads photo of their poured glass → analysis returns suggested wine style/type
- User confirms or manually corrects → proceeds to add form

**Tasks:**
- [ ] Build color analysis pipeline (dominant color, opacity, clarity)
- [ ] Build legs/tears analysis (alcohol/viscosity estimation)
- [ ] Build wine style suggestion logic (red/white/rosé → varietal guess)
- [ ] Wire "Glass" mode into `/wine/scan` page with toggle

**Deliverables:**
- Glass photo analysis returns a suggested wine style/type
- User can correct and proceed to add

---

### Milestone 6: Public Feed & Polish

**Acceptance:**
- Landing page shows recent public tasting activity
- Each feed item shows wine, rating, user, location, and links to map pin
- Seed data demonstrates the full loop end-to-end
- All core routes tested

**Tasks:**
- [ ] Build `GET /api/feed` — recent public tasting notes
- [ ] Build landing page with feed + small embedded map
- [ ] Add "Recent Tastings" sidebar to wine detail pages
- [ ] Write smoke tests for all core flows (search, add, scan, map, auth)
- [ ] Seed 15–20 demo entries showing real-looking data
- [ ] HTTPS/CSP/input validation hardening

**Deliverables:**
- Full MVP loop works end-to-end:
  `Scan/Add → Tag Location → Rate → Map Pin → Public Feed`
- Smoke tests pass
- Deployed and live for demo

---

## Phase 2 — Social Layer

**Target: 1–2 weeks after MVP**

| Milestone | Features | Acceptance |
|-----------|----------|------------|
| Follows | Follow/unfollow users, personal feed | Seeing only followed users' tastings |
| Global community map | Toggle to see all users' pins | Community map with filters |
| Wine groups | Create/join groups, group map | Group page shows shared map of members' wines |
| Photo attachments | Upload photos to tasting notes | Notes show attached bottle/glass photos |
| User profiles | Bio, stats (count of wines, venues visited), map | Complete profile page |
| "What's near me" | Show tastings within X km of my location | Geospatial radius query returns results |

---

## Phase 3 — Intelligence & Scale

**Target: Ongoing after social layer**

| Feature | Description |
|---------|-------------|
| Personal taste profile | ML learns preferences from rating history, recommends |
| Food pairing suggestions | AI-powered pairing with scanned wine |
| Heatmap view | Density map of wine activity in a region |
| Barcode/UPC scan | Fallback identification |
| Drinking windows | Recommendations from wine data |
| Export journal | Download tasting history as CSV/PDF |
| Leaderboards | Gamification (most wines logged, most venues visited) |
| Menu scan | Photo of wine list → recommendations |

---

## Seed Data Plan

For MVP dev/testing, seed the local DB with:

- **30–50 wines** across 5 varietals (Cabernet Sauvignon, Pinot Noir, Chardonnay, Sauvignon Blanc, Rosé)
- **3 regions** (Napa Valley, Bordeaux, Tuscany)
- **5 venues** (2 restaurants, 1 wine bar, 1 winery, 1 home)
- **5 test users** with varying tasting histories
- **25 tasting notes** distributed across users/locations to populate the map

This gives a realistic-feeling demo without requiring live scanning every time.

---

## Deployment Target

| Environment | Stack | When |
|-------------|-------|------|
| Dev | Local FastAPI + SQLite | Phase 1 |
| Staging | VPS (existing infra) + SQLite | End of Phase 1 |
| Production | VPS + PostgreSQL + PostGIS | End of Phase 2 |

The VPS already runs FastAPI apps. Deployment follows the same pattern as WeddingOS / petcare-companion: uvicorn behind systemd, nginx reverse proxy.

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| OCR accuracy on decorative labels | High | Provide manual edit + fallback to text search |
| Glass photo analysis too inaccurate | High | Ship as experimental, always allow manual override |
| External wine API goes down | Medium | Cache results locally, add multiple API backends |
| Nominatim geocoding rate limits | Medium | Cache geocoded addresses, batch requests |
| Map tile loading on mobile | Medium | Use offline-capable Leaflet config + lighter tiles |
| User adoption (cold start) | Medium | Seed with rich demo data, invite beta testers to populate |