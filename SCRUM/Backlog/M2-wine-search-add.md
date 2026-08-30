---
status: backlog
priority: p0
agent_claimed: false
claimed_at:
updated: 2026-08-30
---

## M2: Wine Search & Manual Add

**Description:** Users can search the wine database with live autocomplete and manually add wines with ratings and tasting notes.

**Context:** The manual add flow is the fallback for when scanning doesn't work, and the primary flow for glass analysis results.

**Acceptance Criteria:**
- `/api/wines/search?q=` endpoint returns autocomplete results (fuzzy match on producer, name, vintage)
- `/wine/add` page renders with search input that triggers HTMX-driven suggestions
- Selecting a suggestion populates the form (producer, name, vintage, region, varietal)
- User can submit a tasting note (rating 1-5, appearance, nose, palate, finish, free text)
- Submission creates wine + tasting_note records in DB
- Redirect to wine detail page after submission
- Wine detail page shows producer, region, varietal, vintage, avg rating, all reviews

**Technical Notes:**
- Search endpoint should first check local DB, then fall back to external API
- HTMX: `hx-get="/api/wines/search?q="`, target suggestion dropdown, `hx-trigger="keyup changed delay:200ms"`
- Tasting note form: star rating (CSS-only), structured fields + free text