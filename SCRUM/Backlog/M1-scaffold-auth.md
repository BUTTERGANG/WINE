---
status: backlog
priority: p0
agent_claimed: false
claimed_at:
updated: 2026-08-30
---

## M1: Project Scaffold & Auth

**Description:** Initialize the FastAPI project structure, get auth working, set up the database schema and seed data.

**Context:** Everything builds on this. Must be solid before any feature work starts.

**Acceptance Criteria:**
- FastAPI app boots with uvicorn, serves HTML pages with Tailwind CSS
- SQLite database initializes with all core tables (wines, tasting_notes, locations, users, wine_locations)
- User registration (email + password) works with validation
- User login/logout works with session auth
- Unauthenticated users are redirected to login on mutation pages
- 30-50 seed wines loaded from external API (GrapeMinds/VinoFYI)
- Dark theme base template renders consistently

**Technical Notes:**
- Use FastAPI's built-in session middleware or `fastapi-sessions`
- Templates directory under `backend/templates/`
- Static files under `backend/static/`
- Config from `.env` via pydantic-settings
- Database tables created on first startup (Alembic migrations for prod only)