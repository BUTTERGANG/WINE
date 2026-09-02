# WINE — KANBAN

## Sprint View

| Stage | In Progress | Ready | Blocked | Done |
|-------|-------------|-------|---------|------|
| **Design** | | | | Architecture, Features, MVP Plan |
| **Scaffold** | | | | Repo, dirs, CLAUDE.md |
| **Phase 1 Build** | | | | M1–M6 (auth, wine search/add, map, label scan, glass scan, feed + tests) |
| **Phase 2 Build** | | | | Follows, groups, taste profile, recommendations, heatmap, Near Me, CSV export |
| **Phase 3 Build** | | | | Winery DB (~50K), venue pages + enrichment, wishlist, menu scanner, marker clustering |
| **Post-MVP** | Winery/venue enrichment (~33% rich) | | | Spirits + distilleries, spirit groups, notifications, password reset, rate limiting, BeerAdvocate import (data only) |

---

## Active Tasks

- Ongoing winery/venue enrichment — website crawl + Google Places, resumable via
  `data/enrichment_checkpoint.json`. ~33% of ~50,214 wineries have rich descriptions.

---

## Backlog

See [SCRUM/Backlog/](SCRUM/Backlog/) for the original M1–M6 milestone specs (all complete).

Ideas not yet scheduled:
- Swap in-memory session + rate-limit stores for Redis (prod)
- Move geo queries to PostGIS (currently SQLite bounding-box approximation)
- Beer as a first-class feature (only scraper + CSV import exist today)
- Email delivery for password-reset links (flow works, no mailer wired)

---

## Legend

| Symbol | Meaning |
|--------|---------|
| 🚀 | MVP (Phase 1) |
| 📈 | Phase 2 |
| 🔮 | Phase 3 |
