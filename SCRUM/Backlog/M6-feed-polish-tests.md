---
status: backlog
priority: p0
agent_claimed: false
claimed_at:
updated: 2026-08-30
---

## M6: Public Feed & Polish

**Description:** Landing page shows recent public tastings. Smoke tests pass. Seed data makes the app look alive.

**Context:** The feed closes the loop. Without it, the app feels single-player. With it, people see what's possible.

**Acceptance Criteria:**
- Landing page (`/`) shows a feed of recent public tasting notes
- Each feed item shows: wine name + vintage, rating, user, location, date
- Feed items link to map pin + wine detail page
- A small embedded map on the landing page shows recent pins
- Seed data: 15-20 demo tasting notes, 5 users, 5 venues, 30+ wines
- Smoke tests: search, add, scan, map, auth flows all tested
- Input validation on all mutation endpoints (pydantic)
- CSP headers set in production mode

**Technical Notes:**
- Feed endpoint: `SELECT ... FROM tasting_notes JOIN wines JOIN users ... ORDER BY created_at DESC LIMIT 20`
- HTMX infinite scroll: `hx-trigger="revealed"` on last feed item
- Seed script: `scripts/seed.py` that populates DB with realistic demo data
- Smoke tests in `tests/` using TestClient