---
status: backlog
priority: p0
agent_claimed: false
claimed_at:
updated: 2026-08-30
---

## M5: Glass Photo Analysis

**Description:** Users snap a photo of their glass of wine and the app suggests what it is based on color, opacity, and legs.

**Context:** This is the unique differentiator. No other wine app identifies wine from a glass photo.

**Acceptance Criteria:**
- "Glass" mode on the scan page: user uploads a photo of a wine glass
- Analysis extracts: dominant color, color intensity, opacity (clear/hazy/cloudy), legs/tears (viscosity indicator)
- AI suggests wine type (red/white/rosé/sparkling/fortified) and probable varietal
- Results shown as suggestions (not definitive matches) with "How sure we are" indicator
- User confirms suggestion or manually searches/corrects
- Proceeds to the same add form
- Works on red, white, rosé, and sparkling wines

**Technical Notes:**
- Color analysis: K-means clustering on pixel hues from the glass region
- Legs analysis: edge detection for droplet tracks on glass wall
- This is experimental — clearly label as "AI Guess" with confidence meter
- Always allow manual override
- Build a test set of 20+ glass photos from known wines to calibrate