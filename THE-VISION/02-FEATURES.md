# Features Inventory

## Priority Tiers

| Tier | Label | Meaning |
|------|-------|---------|
| **P0** | 🚀 MVP (Phase 1) | Required for launch. Core loop works |
| **P1** | 📈 Phase 2 | Delighters. Makes the app sticky |
| **P2** | 🔮 Phase 3 | Vision features. Differentiation + scale |

---

## 1. Wine Identification

| Feature | Priority | Description | Competitor Status |
|---------|----------|-------------|-------------------|
| **Bottle label scan (OCR)** | P0 🚀 | Snap a label → OCR extracts producer, vintage, region → match against wine DB | ✅ Vivino, CellarTracker, Delectable all have this |
| **Glass photo analysis** | P0 🚀 | Snap your pour → AI reads color, opacity, legs → suggests wine/style | ❌ **Nobody does this.** Massive differentiator |
| **Manual add with live search** | P0 🚀 | Type producer/vintage → autocomplete against local + external wine DB | ✅ All major apps |
| **Barcode/UPC scan** | P2 🔮 | Scan UPC for instant lookup when label is blurry | ✅ Wine-Searcher |
| **Menu scan** | P2 🔮 | Photo of a restaurant wine list → scores + recs for every wine | ✅ Vivino (Premium), Sommo |
| **Counterfeit detection** | P2 🔮 | Label verification for rare/expensive bottles | ❌ No consumer app does this well |

### Scanner UX Flow (P0)
```
User taps "Scan" → Camera opens with label/glass toggle →
Label: center bottle in frame → auto-capture → OCR processes → top 3 matches shown →
User confirms → pre-fills wine details → prompts for rating + location
Glass: snap photo → color/legs analysis → suggests wine type or known matches →
User confirms or manually picks → prompts for rating + location
```

---

## 2. Wine Database & Search

| Feature | Priority | Description | Competitor Status |
|---------|----------|-------------|-------------------|
| **Local wine database (curated)** | P0 🚀 | Store wines added by users, seeded from external APIs | ✅ All major |
| **Live autocomplete search** | P0 🚀 | As-you-type suggestions from DB | ✅ Wine-Searcher, Vivino |
| **External API fallback** | P0 🚀 | Search GrapeMinds/VinoFYI when not in local DB | ✅ Vivino (internal DB) |
| **Community-contributed wines** | P1 📈 | Users can add wines not in DB (producer, region, vintage) | ✅ All major |
| **Wine detail page** | P0 🚀 | Producer, region, varietal, vintage, type, ABV, avg rating, reviews | ✅ All major |
| **Filter by varietal/region/type** | P1 📈 | Browse the database with filters | ✅ All major |

---

## 3. Location & Map

| Feature | Priority | Description | Competitor Status |
|---------|----------|-------------|-------------------|
| **Interactive map (Leaflet/OSM)** | P0 🚀 | All logged wines pinned on a map | ❌ **None.** Game-changing differentiator |
| **Personal map view** | P0 🚀 | See only YOUR pins, filterable | ❌ None |
| **Tag a venue** | P0 🚀 | Search/nominatim resolve: winery, restaurant, bar, home | ✅ Some apps let you text-notes it. None map it |
| **GeoJSON API** | P0 🚀 | Serve pins as GeoJSON for Leaflet consumption | — |
| **Global community map** | P1 📈 | See where others are drinking wines nearby | ❌ None |
| **Map filters** | P1 📈 | Filter pins by wine type, rating, date, user | ❌ None |
| **"What's near me"** | P1 📈 | Wines being drunk within X km of your current location | ❌ None |
| **Heatmap view** | P2 🔮 | See wine density hotspots (popular wine neighborhoods) | ❌ None |
| **Tasting route planner** | P2 🔮 | Plan a winery tour, add stops, share route | ❌ None |

### Map UX Flow (P0)
```
Map loads → Leaflet centered on user's region → pins render as wine-bottle markers →
User clicks a pin → popup shows wine name, rating, who logged it, date →
Pin filtered by: "My wines" / "Everyone" toggle →
Add new pin: scan/add wine → tap "Where?" → search venue or drop pin →
→ GeoJSON saves → pin appears on map
```

---

## 4. Tasting Notes & Ratings

| Feature | Priority | Description |
|---------|----------|-------------|
| **5-star rating** | P0 🚀 | Simple star rating for each wine |
| **Structured tasting notes** | P0 🚀 | WSET-inspired: appearance, nose, palate, finish, body, acidity, tannins |
| **Free-text notes** | P0 🚀 | Open field for anything else |
| **Photo attachment** | P1 📈 | Attach a photo of the glass/bottle to the note |
| **Food pairing tags** | P1 📈 | What food was paired with this wine |
| **Price paid** | P1 📈 | Optional field for reference |
| **Drink window recommendation** | P2 🔮 | "Drink now" / "Hold until YYYY" based on wine data |

---

## 5. Community & Social

| Feature | Priority | Description | Competitor Status |
|---------|----------|-------------|-------------------|
| **Public activity feed** | P0 🚀 | Recent public tastings from all users, with map pin links | ✅ Delectable (abandoned) |
| **User profiles** | P0 🚀 | Tasting history, personal map, bio, followers | ✅ All major |
| **Follow system** | P1 📈 | Follow/unfollow other users | ✅ Vivino, Delectable |
| **Personal feed** | P1 📈 | Feed filtered to just people you follow | ✅ Delectable |
| **Wine groups** | P1 📈 | Create/join groups (e.g., "Napa Cab Lovers", "2023 Bordeaux Futures") | ✅ Swirl (basic) |
| **Group feed + map** | P1 📈 | See what your group is drinking, on a shared map | ❌ None |
| **"What's near me" feed** | P1 📈 | See recent tastings at venues near you | ❌ None |
| **Comments on tastings** | P2 🔮 | Reply to someone's note, discuss | ✅ Vivino |
| **Wine club subscriptions** | P2 🔮 | Track club shipments, remind to pick up | ❌ None |
| **Private journal mode** | P2 🔮 | Mark tastings as private (not shared to community feed) | ✅ VinoMemo |

---

## 6. User Accounts & Auth

| Feature | Priority | Description |
|---------|----------|-------------|
| **Email + password registration** | P0 🚀 | Simple session-based auth |
| **Profile page** | P0 🚀 | Username, avatar, bio, tasting stats |
| **Session management** | P0 🚀 | Login/logout, session expiry |
| **Password reset** | P1 📈 | Email-based reset flow |
| **Username/display name** | P1 📈 | Public-facing identity |
| **Avatar upload** | P1 📈 | Custom profile photo |

---

## 7. Scoring System & Gamification

| Feature | Priority | Description |
|---------|----------|-------------|
| **Wine score (user avg)** | P0 🚀 | Average rating for each wine from all users |
| **Tasting count badge** | P1 📈 | "Logged 10 wines" — simple user stats |
| **Varietal explorer badge** | P2 🔮 | "Tried wines from 10+ varietals" |
| **Location explorer badge** | P2 🔮 | "Tasted wine at 20+ different venues" |
| **Leaderboard (friends)** | P2 🔮 | Who in your group has logged the most |

---

## 8. Advanced / Future

| Feature | Priority | Description |
|---------|----------|-------------|
| **Personal taste profile** | P2 🔮 | ML that learns your preferences and recommends |
| **AI pairing suggestions** | P2 🔮 | "This wine goes with grilled salmon" |
| **Wishlist / Want to Try** | P2 🔮 | Save wines to a "to drink" list |
| **Export journal** | P2 🔮 | Download your complete tasting history as CSV/PDF |
| **Wine shop locator** | P2 🔮 | Find stores near you that stock this wine |
| **Price history** | P2 🔮 | Track price changes for wines you follow |

---

## Feature Summary by Phase

| Phase | # Features | Headline |
|-------|-----------|----------|
| **Phase 1 (MVP)** | ~18 P0 features | The core loop: scan/add a wine, tag a location, rate it, see it on the map |
| **Phase 2** | ~15 P1 features | Social layers: follows, groups, personal feed, global map, photo attachments |
| **Phase 3** | ~12 P2 features | Intelligence: taste profiling, recommendations, exports, heatmaps |

Total features identified: **45** (18 P0, 15 P1, 12 P2) as of initial design.