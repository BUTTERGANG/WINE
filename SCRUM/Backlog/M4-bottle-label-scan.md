---
status: backlog
priority: p0
agent_claimed: false
claimed_at:
updated: 2026-08-30
---

## M4: Bottle Label Scan

**Description:** Users snap a photo of a wine bottle label and the app identifies the wine via OCR.

**Context:** Label scanning is table-stakes. Vivino set the expectation. We need parity plus the map differentiator.

**Acceptance Criteria:**
- `/wine/scan` page renders with camera/file upload interface
- Toggle between "Bottle" and "Glass" mode on the scan page
- Uploading a bottle label photo hits `POST /api/wines/scan`
- OCR extracts: producer, wine name, vintage, region from the label
- Matched against wine DB (local + external)
- Returns top 1-3 candidates with confidence scores
- User taps a candidate → pre-fills the add form (same as manual add)
- User can correct/override any field before submitting

**Technical Notes:**
- Use Google Cloud Vision OCR or api4.ai wine recognition API
- Image pre-processing: crop to label area, enhance contrast
- Acceptance: if confidence < 70% on all candidates, show "No match found" with manual entry fallback
- Camera: HTML `<input type="file" accept="image/*" capture="environment">` works on mobile
- Desktop: standard file upload